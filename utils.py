from decimal import ROUND_HALF_UP, Decimal

from db import Product


def find_products(session, query: str):
    """
    Fuzzy, case-insensitive substring match on product name/brand.
    Returns a list -- callers must handle 0 (not found), 1 (use it),
    or >1 (ambiguous -> let the model ask the owner which one) matches.
    Business logic never guesses on your behalf.
    """
    q = f"%{query.strip()}%"
    return (
        session.query(Product)
        .filter((Product.name.ilike(q)) | (Product.brand.ilike(q)))
        .all()
    )


def r2(value) -> float:
    """Round to 2dp using HALF_UP, the convention GST invoices use."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def gst_split(line_subtotal: float, gst_rate: float):
    """
    Intra-state GST split: CGST = SGST = gst_rate / 2, each rounded
    independently to 2dp (this is what makes a real invoice's numbers
    add up exactly, rather than drifting from rounding the total once).
    Returns (cgst_amt, sgst_amt, line_total).
    """
    half_rate = gst_rate / 2
    cgst_amt = r2(line_subtotal * half_rate / 100)
    sgst_amt = r2(line_subtotal * half_rate / 100)
    line_total = r2(line_subtotal + cgst_amt + sgst_amt)
    return cgst_amt, sgst_amt, line_total
