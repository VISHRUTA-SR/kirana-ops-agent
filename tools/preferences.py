"""
PREFERENCES SKILL
Standing owner preferences (default payment mode, preferred brand for a
generic term, shop name/GSTIN on invoices). Stored in a plain key-value
table, independent of any chat's message history -- this is what survives
a Telegram /new. The agent is instructed (system prompt) to call
get_all_preferences() at the top of any billing/document flow.
"""
from db import Preference, SessionLocal


def set_preference(key, value):
    """Save or update a standing preference, e.g. key='default_payment_mode'."""
    session = SessionLocal()
    try:
        row = session.get(Preference, key)
        if row:
            row.value = str(value)
        else:
            session.add(Preference(key=key, value=str(value)))
        session.commit()
        return {"success": True, "key": key, "value": str(value)}
    finally:
        session.close()


def get_preference(key):
    session = SessionLocal()
    try:
        row = session.get(Preference, key)
        return {"key": key, "value": row.value if row else None}
    finally:
        session.close()


def get_all_preferences():
    """Return every standing preference. Call this at the start of a flow."""
    session = SessionLocal()
    try:
        rows = session.query(Preference).all()
        return {r.key: r.value for r in rows}
    finally:
        session.close()
