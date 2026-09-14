"""
KHATA SKILL
The customer credit ledger -- a first-class kirana concept. Guardrail:
you cannot settle a khata that doesn't exist or has no outstanding balance.
"""
from db import Customer, KhataTransaction, SessionLocal
from lock import DB_LOCK


def _balance(session, customer: Customer) -> float:
    txns = session.query(KhataTransaction).filter_by(customer_id=customer.id).all()
    credit = sum(t.amount for t in txns if t.type == "credit")
    settled = sum(t.amount for t in txns if t.type == "settle")
    return round(credit - settled, 2)


def add_credit(customer_name, amount, note=None):
    """Put an amount on a customer's khata (they owe the shop this much)."""
    with DB_LOCK:
        session = SessionLocal()
        try:
            if amount is None or amount <= 0:
                return {"error": "amount must be positive."}
            customer = session.query(Customer).filter(
                Customer.name.ilike(customer_name)).first()
            if not customer:
                customer = Customer(name=customer_name)
                session.add(customer)
                session.flush()
            session.add(KhataTransaction(
                customer_id=customer.id, type="credit", amount=amount,
                note=note or "credit sale",
            ))
            session.commit()
            return {"success": True, "customer": customer.name,
                    "new_balance": _balance(session, customer)}
        finally:
            session.close()


def settle_credit(customer_name, amount, mode=None):
    """
    Record a payment against a customer's khata. Refuses if the customer
    has no khata record, or if they have no outstanding balance at all --
    this is a guardrail, not just a UX nicety.
    """
    with DB_LOCK:
        session = SessionLocal()
        try:
            customer = session.query(Customer).filter(
                Customer.name.ilike(customer_name)).first()
            if not customer:
                return {"error": f"No khata record exists for '{customer_name}'."}
            balance = _balance(session, customer)
            if balance <= 0:
                return {"error": f"{customer.name} has no outstanding khata balance "
                                  f"(currently ₹{balance})."}
            if amount is None or amount <= 0:
                return {"error": "amount must be positive."}
            if amount > balance:
                return {"error": f"{customer.name} only owes ₹{balance}; "
                                  f"cannot settle ₹{amount}.",
                        "outstanding_balance": balance}
            session.add(KhataTransaction(
                customer_id=customer.id, type="settle", amount=amount, mode=mode,
                note="payment received",
            ))
            session.commit()
            return {"success": True, "customer": customer.name,
                    "paid": amount, "remaining_balance": _balance(session, customer)}
        finally:
            session.close()


def get_khata_balance(customer_name):
    """Look up a customer's current outstanding balance."""
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter(
            Customer.name.ilike(customer_name)).first()
        if not customer:
            return {"error": f"No khata record exists for '{customer_name}'."}
        return {"customer": customer.name, "balance": _balance(session, customer)}
    finally:
        session.close()


def list_khata_customers():
    """List all customers with a nonzero outstanding balance."""
    session = SessionLocal()
    try:
        rows = []
        for c in session.query(Customer).all():
            bal = _balance(session, c)
            if bal != 0:
                rows.append({"customer": c.name, "balance": bal})
        return {"customers": rows}
    finally:
        session.close()
