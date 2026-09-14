"""
BILLING SKILL
A bill is built over several turns (start -> add/edit/remove items ->
preview -> finalize). Stock is NEVER touched until finalize_bill commits.
finalize_bill is where the oversell guard and idempotency live -- both are
enforced at the tool/DB layer, never hoped for in the prompt.
"""
from datetime import datetime

from db import Bill, BillItem, Customer, Product, SessionLocal, StockMovement
from lock import DB_LOCK
from utils import find_products, gst_split, r2


def _get_or_create_customer(session, name):
    if not name:
        return None
    c = session.query(Customer).filter(Customer.name.ilike(name)).first()
    if not c:
        c = Customer(name=name)
        session.add(c)
        session.flush()
    return c


def _serialize_bill(session, bill: Bill):
    items = []
    for it in bill.items:
        items.append({
            "product": it.product_name_snapshot,
            "qty": it.qty,
            "unit_price": it.unit_price,
            "gst_rate": it.gst_rate,
            "cgst_amt": it.cgst_amt,
            "sgst_amt": it.sgst_amt,
            "line_total": it.line_total,
        })
    return {
        "bill_id": bill.id,
        "status": bill.status,
        "customer": bill.customer.name if bill.customer else None,
        "items": items,
        "subtotal": bill.subtotal,
        "cgst": bill.cgst,
        "sgst": bill.sgst,
        "total": bill.total,
        "payment_mode": bill.payment_mode,
    }


def _recompute_totals(bill: Bill):
    subtotal = sum(r2(it.qty * it.unit_price) for it in bill.items)
    cgst = r2(sum(it.cgst_amt for it in bill.items))
    sgst = r2(sum(it.sgst_amt for it in bill.items))
    bill.subtotal = subtotal
    bill.cgst = cgst
    bill.sgst = sgst
    bill.total = r2(subtotal + cgst + sgst)


def start_bill(customer_name=None):
    """Open a new draft bill, optionally tied to a khata customer."""
    session = SessionLocal()
    try:
        customer = _get_or_create_customer(session, customer_name)
        bill = Bill(status="draft", customer_id=customer.id if customer else None)
        session.add(bill)
        session.commit()
        return {"success": True, "bill_id": bill.id,
                "customer": customer.name if customer else None}
    finally:
        session.close()


def add_item_to_bill(bill_id, product_name, qty, unit=None):
    """
    Add a line item to a draft bill. If the product name is ambiguous
    (e.g. "atta" matches both loose atta and Aashirvaad Atta 5kg), returns
    candidates instead of guessing -- the model should ask the owner which
    one they meant. Does NOT touch stock; that only happens on finalize.
    """
    session = SessionLocal()
    try:
        bill = session.get(Bill, bill_id)
        if not bill or bill.status != "draft":
            return {"error": f"No open draft bill with id {bill_id}."}
        matches = find_products(session, product_name)
        if len(matches) == 0:
            return {"error": f"No product matching '{product_name}'."}
        if len(matches) > 1:
            return {"ambiguous": True,
                    "candidates": [{"id": m.id, "name": m.name, "unit": m.unit}
                                   for m in matches]}
        product = matches[0]
        if qty is None or qty <= 0:
            return {"error": "qty must be a positive number."}
        if qty > product.stock_qty:
            # Soft, early warning -- the hard block is at finalize under lock.
            return {"warning": "insufficient_stock_at_add_time",
                    "available": product.stock_qty, "requested": qty,
                    "message": f"Only {product.stock_qty} {product.unit} of "
                               f"{product.name} in stock right now. You can still "
                               f"add it, but finalize will refuse to oversell."}

        line_subtotal = r2(qty * product.mrp)
        cgst_amt, sgst_amt, line_total = gst_split(line_subtotal, product.gst_rate)

        existing_item = next((it for it in bill.items if it.product_id == product.id), None)
        if existing_item:
            existing_item.qty += qty
            new_subtotal = r2(existing_item.qty * product.mrp)
            existing_item.cgst_amt, existing_item.sgst_amt, existing_item.line_total = \
                gst_split(new_subtotal, product.gst_rate)
        else:
            session.add(BillItem(
                bill_id=bill.id, product_id=product.id,
                product_name_snapshot=product.name, qty=qty,
                unit_price=product.mrp, gst_rate=product.gst_rate,
                cgst_amt=cgst_amt, sgst_amt=sgst_amt, line_total=line_total,
            ))
        session.flush()
        session.refresh(bill)
        _recompute_totals(bill)
        session.commit()
        return _serialize_bill(session, bill)
    finally:
        session.close()


def edit_bill_item(bill_id, product_name, new_qty):
    """Set a line item to an exact new quantity (e.g. 'make it 6 Maggi')."""
    session = SessionLocal()
    try:
        bill = session.get(Bill, bill_id)
        if not bill or bill.status != "draft":
            return {"error": f"No open draft bill with id {bill_id}."}
        matches = [it for it in bill.items
                   if product_name.lower() in it.product_name_snapshot.lower()]
        if len(matches) == 0:
            return {"error": f"'{product_name}' is not on this bill."}
        if len(matches) > 1:
            return {"ambiguous": True,
                    "candidates": [it.product_name_snapshot for it in matches]}
        item = matches[0]
        if new_qty <= 0:
            bill.items.remove(item)
            session.delete(item)
        else:
            product = session.get(Product, item.product_id)
            item.qty = new_qty
            new_subtotal = r2(new_qty * item.unit_price)
            item.cgst_amt, item.sgst_amt, item.line_total = gst_split(new_subtotal, item.gst_rate)
        session.flush()
        session.refresh(bill)
        _recompute_totals(bill)
        session.commit()
        return _serialize_bill(session, bill)
    finally:
        session.close()


def remove_item_from_bill(bill_id, product_name):
    """Drop a line item entirely (e.g. 'drop the butter')."""
    return edit_bill_item(bill_id, product_name, 0)


def preview_bill(bill_id):
    """Read-only: show current draft bill contents and totals."""
    session = SessionLocal()
    try:
        bill = session.get(Bill, bill_id)
        if not bill:
            return {"error": f"No bill with id {bill_id}."}
        return _serialize_bill(session, bill)
    finally:
        session.close()


def finalize_bill(bill_id, payment_mode, payment_ref=None, idempotency_key=None):
    """
    Commit a draft bill: locks affected products, re-validates stock,
    decrements it, and marks the bill finalized. This is the ONLY place
    stock changes for a sale.

    Idempotency: if this bill is already finalized (e.g. Telegram
    redelivered the "finalize" update and the agent called this twice),
    we return the original result instead of double-decrementing stock.
    An optional idempotency_key gives a second layer of protection if the
    caller supplies one.
    """
    with DB_LOCK:
        session = SessionLocal()
        try:
            bill = session.get(Bill, bill_id)
            if not bill:
                return {"error": f"No bill with id {bill_id}."}

            if bill.status == "finalized":
                return {"already_finalized": True, **_serialize_bill(session, bill)}
            if bill.status == "void":
                return {"error": "This bill was voided and cannot be finalized."}
            if not bill.items:
                return {"error": "Cannot finalize an empty bill."}

            if idempotency_key:
                dup = session.query(Bill).filter(
                    Bill.idempotency_key == idempotency_key,
                    Bill.id != bill.id,
                ).first()
                if dup:
                    return {"already_finalized": True, **_serialize_bill(session, dup)}

            # --- Oversell guard: re-check every line under the lock, against
            # live stock, right before committing. Nothing is written until
            # every line passes. ---
            shortfalls = []
            for item in bill.items:
                product = session.get(Product, item.product_id)
                if item.qty > product.stock_qty:
                    shortfalls.append({
                        "product": product.name, "requested": item.qty,
                        "available": product.stock_qty,
                    })
            if shortfalls:
                return {"error": "oversell_blocked", "shortfalls": shortfalls,
                        "message": "Not enough stock to complete this bill. "
                                   "Nothing was charged or decremented."}

            for item in bill.items:
                product = session.get(Product, item.product_id)
                product.stock_qty = r2(product.stock_qty - item.qty)
                session.add(StockMovement(
                    product_id=product.id, type="out", qty=item.qty,
                    ref_bill_id=bill.id, note="sale",
                ))

            _recompute_totals(bill)
            bill.status = "finalized"
            bill.finalized_at = datetime.utcnow()
            bill.payment_mode = payment_mode
            bill.payment_ref = payment_ref
            bill.idempotency_key = idempotency_key or f"bill-{bill.id}"

            if payment_mode == "credit":
                if not bill.customer_id:
                    return {"error": "Credit sale needs a customer name on the bill."}
                from tools.khata import add_credit as _add_credit  # local import: avoid cycle
                session.commit()
                _add_credit(bill.customer.name, bill.total,
                            note=f"bill #{bill.id}")
                session.refresh(bill)
                return _serialize_bill(session, bill)

            session.commit()
            return _serialize_bill(session, bill)
        finally:
            session.close()


def void_bill(bill_id, reason):
    """Reverse a finalized bill: restock every line, mark it void."""
    with DB_LOCK:
        session = SessionLocal()
        try:
            bill = session.get(Bill, bill_id)
            if not bill or bill.status != "finalized":
                return {"error": "Only a finalized bill can be voided."}
            for item in bill.items:
                product = session.get(Product, item.product_id)
                product.stock_qty = r2(product.stock_qty + item.qty)
                session.add(StockMovement(
                    product_id=product.id, type="adjust", qty=item.qty,
                    ref_bill_id=bill.id, note=f"void: {reason}",
                ))
            bill.status = "void"
            session.commit()
            return {"success": True, "bill_id": bill.id, "reason": reason}
        finally:
            session.close()
