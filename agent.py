"""
Agent control loop. One GenerativeModel + function-calling chat session
per Telegram chat_id, held in memory. `/new` drops the chat's history
(chat_histories[chat_id]) but never touches the database -- that's what
makes owner preferences (and all store data) survive a fresh chat while
the conversation buffer resets, per the "memory across sessions" requirement.

This loop is intentionally explicit (not the SDK's "automatic function
calling") so the control flow -- and every tool call/result -- is visible
and can be logged, capped, and used to collect files to send back.
"""
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

import config
from tool_schemas import FUNCTION_DECLARATIONS, call_tool

genai.configure(api_key=config.GEMINI_API_KEY)

SYSTEM_INSTRUCTION = f"""
You are the operations agent for {config.SHOP_NAME}, an Indian kirana
(grocery) store, running entirely inside a Telegram chat with the shop
owner. The owner types in plain, terse, real-shopkeeper English.

Hard rules -- these are not suggestions:
1. NEVER invent a product, price, GST rate, or stock number. Always call a
   tool to look it up. If a tool call is needed to answer, call it before
   replying.
2. If a product name is ambiguous (a tool returns "ambiguous": true),
   ask the owner to choose between the candidates. Do not guess.
3. A bill is built over multiple turns: start_bill once, then
   add_item_to_bill / edit_bill_item / remove_item_from_bill as the owner
   adds or changes items, then finalize_bill only when the owner confirms
   or clearly says to close it out (e.g. names a payment mode). Stock is
   only touched at finalize -- say so if asked.
4. If finalize_bill returns an oversell error, tell the owner exactly
   which items are short and by how much. Never override this by
   re-calling with different numbers unless the owner reduces the
   quantity themselves.
5. At the start of any billing or document-generation exchange, call
   get_all_preferences() and silently apply standing preferences (default
   payment mode, preferred brand for a generic item name, shop details for
   invoices) unless the owner says otherwise in this message.
6. When the owner asks to remember something for the future ("always
   assume UPI unless I say cash", "default atta = Aashirvaad 5kg"), call
   set_preference with a short, stable key. Confirm briefly once saved.
7. Never settle a khata, delete stock, or sell below cost without the
   tool's own confirmation -- if a tool returns an error/guardrail
   message, relay it plainly rather than working around it.
8. Keep replies short and concrete, like a text to a busy shop owner --
   confirm what happened, the running bill/balance, and nothing else
   unless asked.
9. All money is INR (₹). All bills must reflect the CGST/SGST split and
   totals a tool returns -- never compute tax yourself in the reply.
"""

MODEL = genai.GenerativeModel(
    model_name=config.GEMINI_MODEL,
    system_instruction=SYSTEM_INSTRUCTION,
    tools=[{"function_declarations": FUNCTION_DECLARATIONS}],
)

# chat_id -> google.generativeai ChatSession
_chat_sessions: dict = {}

MAX_TOOL_HOPS = 8  # guard against runaway tool-call loops in one turn


def reset_chat(chat_id):
    """Implements /new: drops conversation memory only, not store data."""
    _chat_sessions.pop(chat_id, None)


def _get_session(chat_id):
    if chat_id not in _chat_sessions:
        _chat_sessions[chat_id] = MODEL.start_chat(history=[], enable_automatic_function_calling=False)
    return _chat_sessions[chat_id]


def _send_with_retry(chat, content, max_retries=3):
    for attempt in range(max_retries):
        try:
            return chat.send_message(content)
        except ResourceExhausted:
            wait = 15 * (attempt + 1)
            time.sleep(wait)
    return chat.send_message(content)


def handle_message(chat_id, user_text: str):
    """
    Runs one full observe->reason->act->feed-back->continue turn.
    Returns (reply_text, list_of_file_paths) -- file paths come from any
    tool result that included a "file_path" (invoice PDF / analysis PPTX),
    so bot.py can send them as Telegram documents.
    """
    chat = _get_session(chat_id)
    files_to_send = []

    response = _send_with_retry(chat, user_text)

    hops = 0
    while hops < MAX_TOOL_HOPS:
        function_calls = [
            part.function_call
            for part in response.candidates[0].content.parts
            if getattr(part, "function_call", None) and part.function_call.name
        ]
        if not function_calls:
            break

        tool_response_parts = []
        for fc in function_calls:
            args = dict(fc.args) if fc.args else {}
            result = call_tool(fc.name, args)
            if isinstance(result, dict) and result.get("file_path"):
                files_to_send.append(result["file_path"])
            tool_response_parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name, response={"result": result},
                    )
                )
            )

        response = _send_with_retry(chat, genai.protos.Content(parts=tool_response_parts))
        hops += 1

    reply_text = response.text if response.parts else "(no response)"
    return reply_text, files_to_send
