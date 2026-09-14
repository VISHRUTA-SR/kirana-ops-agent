# Supermarket Ops Agent — Nebula KnowLab Take-Home

Telegram bot: **@your_bot_username_here** ← *fill in after you create the bot with @BotFather*

## Harness choice — and why

Gemini 2.0 Flash via `google-generativeai`, with manual (not "automatic")
function calling in `agent.py`. Reasoning:

- **Free of cost** with a generous daily quota — important for a 5-day
  build-and-iterate cycle and for keeping the bot live during review.
- Native, first-class function calling with parallel tool calls, which is
  what lets the model chain several tool calls in one turn (e.g. look up
  a product, then add it to a bill).
- I hand-roll the control loop instead of using the SDK's automatic
  function-calling mode so that every tool call/result is visible,
  loggable, capped (`MAX_TOOL_HOPS`), and inspectable for files to send
  back to Telegram — this is the graded "control loop," so it shouldn't
  be hidden inside a library.

This plays the same role the brief describes for Claude Agent SDK /
deep agents / Vercel AI SDK: a thin loop around a tool-calling model, with
all business logic living in the tools, not the prompt.

## Control loop

```
Telegram update
   -> dedupe by update_id (bot.py)
   -> agent.handle_message(chat_id, text)
        -> chat.send_message(text)                      [observe]
        -> model returns text OR function_call(s)        [reason]
        -> call_tool(name, args) against tools/*.py       [act]
        -> feed FunctionResponse back into the chat        [feed back]
        -> repeat until model returns plain text (capped)  [continue]
   -> reply_text sent back to Telegram
   -> any tool result with "file_path" sent as a document
```

Per-`chat_id` `ChatSession` objects hold the conversation buffer in
memory only. `/new` (`agent.reset_chat`) drops that buffer. It never
touches the database — see "Memory across sessions" below.

## Skill / tool design

One module per business capability, under `tools/`, each with a matching
`skills/*.md` describing its contract and guardrails:

| Skill | File | Tools |
|---|---|---|
| Inventory | `tools/inventory.py` | add_product, receive_stock, get_stock, get_low_stock, list_products |
| Billing | `tools/billing.py` | start_bill, add_item_to_bill, edit_bill_item, remove_item_from_bill, preview_bill, finalize_bill, void_bill |
| Khata | `tools/khata.py` | add_credit, settle_credit, get_khata_balance, list_khata_customers |
| Analytics | `tools/analytics.py` | get_daily_summary, close_day, get_sales_range |
| Documents | `tools/documents.py` | generate_invoice_pdf, generate_analysis_deck |
| Preferences | `tools/preferences.py` | set_preference, get_preference, get_all_preferences |

`tool_schemas.py` is the only file that translates these into Gemini's
function-calling JSON schema and dispatches by name — the model never
sees SQL or table names, only tool names/descriptions/parameters.

Tools are kept **thin but not dumb**: each one owns exactly the invariant
it's responsible for (stock non-negativity, khata existence, idempotent
finalize/close) so the model can compose them freely without needing to
know the rules itself.

## How each hard part is solved

1. **Grounding** — every price/GST/stock value the model states comes
   from a tool return value (`inventory.get_stock`, `billing.preview_bill`,
   etc). The system prompt explicitly forbids inventing numbers.
2. **Oversell guard** — enforced in `billing.finalize_bill`, under
   `DB_LOCK`, by re-reading live `stock_qty` for every line immediately
   before writing. A short line aborts the whole finalize with no partial
   writes. `add_item_to_bill` gives an earlier *soft* warning for UX, but
   the hard block is at the DB layer.
3. **GST correctness** — `utils.gst_split` computes CGST = SGST =
   rate/2 per line, each rounded to 2dp independently (not the total
   rounded once), which is what makes invoice line items foot exactly.
   HSN code and rate are pulled from `products`, never typed by the model.
4. **Multi-turn bills** — `Bill.status="draft"` rows accumulate
   `BillItem`s over as many messages as needed; stock is untouched until
   `finalize_bill`. Edits (`edit_bill_item`) recompute that line's GST
   and the bill totals immediately so `preview_bill` is always accurate.
5. **Idempotency** — `finalize_bill` short-circuits to the existing
   result if `bill.status == "finalized"` already, and additionally
   checks a caller-supplied `idempotency_key`. `close_day` is idempotent
   per calendar date. `bot.py` also dedupes Telegram's own `update_id`
   before it ever reaches the agent.
6. **Concurrency** — a process-wide `DB_LOCK` (`lock.py`) wraps every
   write that touches `stock_qty` (receive_stock, finalize_bill,
   void_bill), so a sale and a stock-in can't interleave and corrupt
   quantities. SQLite runs in WAL mode. Documented upgrade path to
   Postgres `SELECT ... FOR UPDATE` if you outgrow single-process SQLite.
7. **Guardrails** — selling below cost / negative stock is structurally
   impossible (finalize checks `qty <= stock_qty`); `settle_credit`
   refuses a nonexistent or zero-balance khata; there is no `delete_stock`
   tool at all — only `receive_stock` (in) and sale/void (out), both
   logged to `stock_movements`.
8. **Real artifacts** — `documents.generate_invoice_pdf` renders
   `templates/invoice.html` via WeasyPrint (real tax-breakup PDF, not a
   screenshot); `generate_analysis_deck` builds native `python-pptx`
   chart objects (line/bar/pie) from live analytics — not embedded
   matplotlib images and not plain text.
9. **Memory across sessions** — `preferences` is a plain key/value table
   keyed by shop, not by `chat_id`. `/new` clears `agent._chat_sessions`
   (the LLM conversation buffer) but the table is untouched, and the
   system prompt instructs the model to call `get_all_preferences()` at
   the top of billing/document flows — so a preference set last week
   still applies after a brand-new chat.

## Setup — Colab (development) + always-on host (review window)

**Colab is used to build and test.** Its disk resets and sessions
disconnect after idle/12h limits, which is incompatible with "keep it
running while we review." The mitigation: point `DATABASE_PATH` /
`INVOICE_DIR` / `DECK_DIR` at a mounted Google Drive folder so nothing is
lost between Colab sessions, and redeploy the same code to a free
always-on box (Oracle Cloud Free Tier VM, or PythonAnywhere always-on
task) for the actual review period. The code is identical either way —
only the three path env vars change.

### Colab cells

```python
# 1. Mount Drive so DB/invoices/decks survive Colab disconnects
from google.colab import drive
drive.mount('/content/drive')

# 2. Get the code onto Colab (clone your repo, or upload the zip)
!git clone https://github.com/<you>/kirana-ops-agent.git
%cd kirana-ops-agent

# 3. Install dependencies
!pip install -q -r requirements.txt
!apt-get -qq install -y libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0  # WeasyPrint system libs

# 4. Secrets (Colab -> key icon in left sidebar -> add secrets, then:)
import os
from google.colab import userdata
os.environ["TELEGRAM_TOKEN"] = userdata.get("TELEGRAM_TOKEN")
os.environ["GEMINI_API_KEY"] = userdata.get("GEMINI_API_KEY")
os.environ["DATABASE_PATH"] = "/content/drive/MyDrive/kirana_bot/store.db"
os.environ["INVOICE_DIR"]   = "/content/drive/MyDrive/kirana_bot/invoices"
os.environ["DECK_DIR"]      = "/content/drive/MyDrive/kirana_bot/decks"

# 5. Seed a realistic starting catalog (safe to re-run)
!python seed_data.py

# 6. Run the bot (blocks the cell -- this is expected; stop the cell to stop the bot)
import nest_asyncio; nest_asyncio.apply()
!python bot.py
```

### Getting a Telegram token
Message **@BotFather** on Telegram → `/newbot` → follow the prompts →
copy the token it gives you into `TELEGRAM_TOKEN`.

### Getting a free Gemini key
https://aistudio.google.com/apikey → "Create API key" → copy into
`GEMINI_API_KEY`.

## Demo script (matches the required recording)

1. `50 packets of Maggi came in, cost ₹12, MRP ₹14` — receive stock
2. `make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI`
3. `drop the butter, make it 6 Maggi` — multi-turn edit
4. `bill 9999 amul butter` on a fresh bill — oversell guard fires
5. `put ₹500 on Ramesh's credit` → `Ramesh paid ₹300` → `Ramesh's balance?`
6. `send me that bill as a PDF`
7. `make this week's sales analysis deck`
8. `always assume UPI unless I say cash` → `/new` → ask something that
   needs the default → shows it's still remembered

## Repo layout

```
config.py            env-driven settings
db.py                SQLAlchemy models + engine (SQLite, WAL mode)
lock.py              process-wide write lock (concurrency)
utils.py             fuzzy product lookup, GST math
tool_schemas.py       Gemini function-calling schemas + dispatch
agent.py             control loop, system prompt, per-chat sessions
bot.py               Telegram polling front door, update dedupe
seed_data.py         realistic starting catalog
tools/               one module per skill (see table above)
skills/*.md          human-readable contract for each skill
templates/invoice.html   Jinja2 invoice template rendered by WeasyPrint
```

## Stretch ideas not implemented (time-boxed to core brief)

Branded invoice themes, scheduled weekly deck auto-send, reorder
suggestions from sales velocity, expiry/FEFO batch tracking, voice-note
orders, Hindi/Tamil, barcode lookup, khata reminders — the skill
boundaries above (`inventory`, `billing`, `khata`, `analytics`,
`documents`, `preferences`) are designed so each of these slots in as a
new tool in an existing module rather than a new architecture.
