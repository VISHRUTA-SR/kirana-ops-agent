# Preferences Skill

Tools: `set_preference`, `get_preference`, `get_all_preferences`.

Keyed by the shop, not by `chat_id` or conversation — this is what
survives a Telegram `/new`. The agent's system instruction tells it to
call `get_all_preferences()` at the top of any billing or document flow
and silently apply standing defaults (payment mode, preferred brand,
shop name/GSTIN for invoices).
