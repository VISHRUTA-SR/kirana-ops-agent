# Billing Skill

Multi-turn bill lifecycle: `start_bill` → `add_item_to_bill` /
`edit_bill_item` / `remove_item_from_bill` (any number of turns, any order)
→ `preview_bill` → `finalize_bill`. `void_bill` reverses a finalized bill.

Rules enforced here, not in the prompt:
- Stock is untouched until `finalize_bill` commits.
- `finalize_bill` re-checks live stock for every line **inside a process
  lock**, right before writing — the oversell guard. If any line is short,
  nothing is charged or decremented.
- `finalize_bill` is idempotent: calling it again on an already-finalized
  bill (e.g. a Telegram retry) returns the original result instead of
  double-decrementing stock.
- GST is split CGST/SGST per line, each rounded independently to 2dp
  (`utils.gst_split`), so invoice totals always foot correctly.
- `payment_mode="credit"` automatically posts the bill total to the
  customer's khata via the khata skill.
