"""
Declares every tool the model can call (Gemini function-calling schema)
and maps each name to the actual Python function. This file is the single
seam between "skills" (tools/*.py) and the agent's control loop -- the
model only ever sees names/descriptions/JSON-schemas here, never SQL.
"""
from tools import analytics, billing, documents, inventory, khata, preferences

NUM = {"type": "number"}
STR = {"type": "string"}

FUNCTION_DECLARATIONS = [
    # ---- inventory ----
    {"name": "add_product", "description": "Register a brand-new SKU with unit, GST rate, cost price and MRP.",
     "parameters": {"type": "object", "properties": {
         "name": STR, "unit": {"type": "string", "description": "kg|g|litre|ml|packet|dozen|piece"},
         "gst_rate": NUM, "cost_price": NUM, "mrp": NUM, "hsn_code": STR,
         "initial_stock": NUM, "reorder_level": NUM, "brand": STR,
         "is_loose": {"type": "boolean"},
     }, "required": ["name", "unit", "gst_rate", "cost_price", "mrp"]}},

    {"name": "receive_stock", "description": "Record incoming stock for an existing product (a delivery).",
     "parameters": {"type": "object", "properties": {
         "product_name": STR, "qty": NUM, "cost_price": NUM, "mrp": NUM,
     }, "required": ["product_name", "qty"]}},

    {"name": "get_stock", "description": "Check current stock level for a product.",
     "parameters": {"type": "object", "properties": {"product_name": STR}, "required": ["product_name"]}},

    {"name": "get_low_stock", "description": "List all SKUs at or below their reorder level.",
     "parameters": {"type": "object", "properties": {}}},

    {"name": "list_products", "description": "List all products, optionally filtered by a search string.",
     "parameters": {"type": "object", "properties": {"query": STR}}},

    # ---- billing ----
    {"name": "start_bill", "description": "Open a new draft bill, optionally for a named customer.",
     "parameters": {"type": "object", "properties": {"customer_name": STR}}},

    {"name": "add_item_to_bill", "description": "Add a line item to a draft bill by product name and quantity.",
     "parameters": {"type": "object", "properties": {
         "bill_id": {"type": "integer"}, "product_name": STR, "qty": NUM, "unit": STR,
     }, "required": ["bill_id", "product_name", "qty"]}},

    {"name": "edit_bill_item", "description": "Set a line item on a draft bill to an exact new quantity.",
     "parameters": {"type": "object", "properties": {
         "bill_id": {"type": "integer"}, "product_name": STR, "new_qty": NUM,
     }, "required": ["bill_id", "product_name", "new_qty"]}},

    {"name": "remove_item_from_bill", "description": "Remove a line item entirely from a draft bill.",
     "parameters": {"type": "object", "properties": {
         "bill_id": {"type": "integer"}, "product_name": STR,
     }, "required": ["bill_id", "product_name"]}},

    {"name": "preview_bill", "description": "Show the current contents/totals of a draft or finalized bill.",
     "parameters": {"type": "object", "properties": {"bill_id": {"type": "integer"}}, "required": ["bill_id"]}},

    {"name": "finalize_bill", "description": "Commit a draft bill: validates stock, decrements it, charges payment. "
                                              "Use payment_mode='credit' for khata sales.",
     "parameters": {"type": "object", "properties": {
         "bill_id": {"type": "integer"},
         "payment_mode": {"type": "string", "description": "cash|upi|card|credit"},
         "payment_ref": STR, "idempotency_key": STR,
     }, "required": ["bill_id", "payment_mode"]}},

    {"name": "void_bill", "description": "Reverse a finalized bill and restock its items.",
     "parameters": {"type": "object", "properties": {
         "bill_id": {"type": "integer"}, "reason": STR,
     }, "required": ["bill_id", "reason"]}},

    # ---- khata ----
    {"name": "add_credit", "description": "Put an amount on a customer's khata (credit ledger).",
     "parameters": {"type": "object", "properties": {
         "customer_name": STR, "amount": NUM, "note": STR,
     }, "required": ["customer_name", "amount"]}},

    {"name": "settle_credit", "description": "Record a payment against a customer's outstanding khata balance.",
     "parameters": {"type": "object", "properties": {
         "customer_name": STR, "amount": NUM, "mode": STR,
     }, "required": ["customer_name", "amount"]}},

    {"name": "get_khata_balance", "description": "Look up a customer's current khata balance.",
     "parameters": {"type": "object", "properties": {"customer_name": STR}, "required": ["customer_name"]}},

    {"name": "list_khata_customers", "description": "List all customers with a nonzero khata balance.",
     "parameters": {"type": "object", "properties": {}}},

    # ---- analytics ----
    {"name": "get_daily_summary", "description": "Get sales/tax/payment-mode summary for a date (default: today).",
     "parameters": {"type": "object", "properties": {"date": {"type": "string", "description": "YYYY-MM-DD"}}}},

    {"name": "close_day", "description": "Finalize and persist the day's sales snapshot. Idempotent per date.",
     "parameters": {"type": "object", "properties": {"date": {"type": "string", "description": "YYYY-MM-DD"}}}},

    {"name": "get_sales_range", "description": "Day-by-day sales totals between two dates.",
     "parameters": {"type": "object", "properties": {
         "start_date": STR, "end_date": STR,
     }, "required": ["start_date", "end_date"]}},

    # ---- documents ----
    {"name": "generate_invoice_pdf", "description": "Generate a GST-correct PDF invoice for a finalized bill.",
     "parameters": {"type": "object", "properties": {"bill_id": {"type": "integer"}}, "required": ["bill_id"]}},

    {"name": "generate_analysis_deck", "description": "Generate a PPTX sales-analysis deck with charts for a date range.",
     "parameters": {"type": "object", "properties": {
         "start_date": STR, "end_date": STR, "period_label": STR,
     }, "required": ["start_date", "end_date"]}},

    # ---- preferences ----
    {"name": "set_preference", "description": "Save a standing owner preference "
                                               "(e.g. default_payment_mode, default_atta_brand, shop_name).",
     "parameters": {"type": "object", "properties": {"key": STR, "value": STR}, "required": ["key", "value"]}},

    {"name": "get_preference", "description": "Read one standing preference by key.",
     "parameters": {"type": "object", "properties": {"key": STR}, "required": ["key"]}},

    {"name": "get_all_preferences", "description": "Read every standing owner preference. "
                                                    "Call this at the start of billing/document flows.",
     "parameters": {"type": "object", "properties": {}}},
]

DISPATCH = {
    "add_product": inventory.add_product,
    "receive_stock": inventory.receive_stock,
    "get_stock": inventory.get_stock,
    "get_low_stock": inventory.get_low_stock,
    "list_products": inventory.list_products,

    "start_bill": billing.start_bill,
    "add_item_to_bill": billing.add_item_to_bill,
    "edit_bill_item": billing.edit_bill_item,
    "remove_item_from_bill": billing.remove_item_from_bill,
    "preview_bill": billing.preview_bill,
    "finalize_bill": billing.finalize_bill,
    "void_bill": billing.void_bill,

    "add_credit": khata.add_credit,
    "settle_credit": khata.settle_credit,
    "get_khata_balance": khata.get_khata_balance,
    "list_khata_customers": khata.list_khata_customers,

    "get_daily_summary": analytics.get_daily_summary,
    "close_day": analytics.close_day,
    "get_sales_range": analytics.get_sales_range,

    "generate_invoice_pdf": documents.generate_invoice_pdf,
    "generate_analysis_deck": documents.generate_analysis_deck,

    "set_preference": preferences.set_preference,
    "get_preference": preferences.get_preference,
    "get_all_preferences": preferences.get_all_preferences,
}


def call_tool(name, args: dict):
    fn = DISPATCH.get(name)
    if not fn:
        return {"error": f"Unknown tool '{name}'."}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
    except Exception as e:  # noqa: BLE001 - surface to the model, don't crash the bot
        return {"error": f"Tool '{name}' failed: {e}"}
