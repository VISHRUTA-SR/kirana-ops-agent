"""
INVENTORY SKILL
Owns product master data and stock levels. Every SKU has a cost price,
MRP, unit, GST slab/HSN, and a reorder level. Stock changes here are
always logged to stock_movements for audit.
"""
from db import Product, SessionLocal, StockMovement
from utils import find_products


def add_product(name, unit, gst_rate, cost_price, mrp, hsn_code=None,
                 initial_stock=0.0, reorder_level=0.0, brand=None, is_loose=False):
    """Register a brand-new SKU. Refuses to create a duplicate by name."""
    session = SessionLocal()
    try:
        existing = session.query(Product).filter(Product.name.ilike(name)).first()
        if existing:
            return {"error": f"'{name}' already exists (id={existing.id}). "
                              f"Use receive_stock to add quantity instead."}
        p = Product(
            name=name, brand=brand, unit=unit, is_loose=is_loose,
            hsn_code=hsn_code, gst_rate=gst_rate, cost_price=cost_price,
            mrp=mrp, stock_qty=initial_stock, reorder_level=reorder_level,
        )
        session.add(p)
        session.commit()
        return {"success": True, "product_id": p.id, "name": p.name,
                "unit": p.unit, "gst_rate": p.gst_rate, "mrp": p.mrp,
                "stock_qty": p.stock_qty}
    finally:
        session.close()


def receive_stock(product_name, qty, cost_price=None, mrp=None):
    """
    Record incoming stock (a delivery). Atomically increments stock_qty
    and logs a stock_movement. Optionally updates cost/MRP if the owner
    quotes new prices on this delivery.
    """
    from lock import DB_LOCK
    with DB_LOCK:
        session = SessionLocal()
        try:
            if qty is None or qty <= 0:
                return {"error": "qty must be a positive number."}
            matches = find_products(session, product_name)
            if len(matches) == 0:
                return {"error": f"No product matching '{product_name}'. "
                                  f"Add it first with add_product."}
            if len(matches) > 1:
                return {"ambiguous": True,
                        "candidates": [{"id": m.id, "name": m.name, "brand": m.brand}
                                       for m in matches]}
            p = matches[0]
            p.stock_qty += qty
            if cost_price is not None:
                p.cost_price = cost_price
            if mrp is not None:
                p.mrp = mrp
            session.add(StockMovement(product_id=p.id, type="in", qty=qty,
                                       note="stock received"))
            session.commit()
            return {"success": True, "product": p.name, "added": qty,
                    "new_stock": p.stock_qty, "unit": p.unit}
        finally:
            session.close()


def get_stock(product_name):
    """Look up current stock for a product (or matching products)."""
    session = SessionLocal()
    try:
        matches = find_products(session, product_name)
        if not matches:
            return {"error": f"No product matching '{product_name}'."}
        return {"products": [
            {"name": m.name, "stock_qty": m.stock_qty, "unit": m.unit,
             "mrp": m.mrp, "reorder_level": m.reorder_level}
            for m in matches
        ]}
    finally:
        session.close()


def get_low_stock():
    """List every SKU at or below its reorder level."""
    session = SessionLocal()
    try:
        rows = session.query(Product).filter(Product.stock_qty <= Product.reorder_level).all()
        return {"low_stock": [
            {"name": p.name, "stock_qty": p.stock_qty, "unit": p.unit,
             "reorder_level": p.reorder_level}
            for p in rows
        ]}
    finally:
        session.close()


def list_products(query=None):
    """List all products, or those matching a search string."""
    session = SessionLocal()
    try:
        rows = find_products(session, query) if query else session.query(Product).all()
        return {"products": [
            {"id": p.id, "name": p.name, "unit": p.unit, "mrp": p.mrp,
             "gst_rate": p.gst_rate, "stock_qty": p.stock_qty}
            for p in rows
        ]}
    finally:
        session.close()
