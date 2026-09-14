"""
Run once to seed a realistic starting catalog, per the SKUs named in the
brief. Safe to re-run -- add_product() refuses to create duplicates.
"""
from db import init_db
from tools.inventory import add_product

SEED_PRODUCTS = [
    # name, unit, gst_rate, cost, mrp, hsn, stock, reorder, brand, is_loose
    ("Aashirvaad Atta 5kg", "packet", 0, 210, 245, "1101", 40, 8, "Aashirvaad", False),
    ("Loose Atta", "kg", 0, 38, 45, "1101", 60, 10, None, True),
    ("Tata Salt 1kg", "packet", 5, 18, 22, "2501", 80, 15, "Tata", False),
    ("Amul Butter 100g", "packet", 12, 52, 62, "0405", 50, 10, "Amul", False),
    ("Fortune Sunflower Oil 1L", "packet", 5, 118, 138, "1512", 45, 10, "Fortune", False),
    ("Maggi 70g", "packet", 12, 10, 14, "1902", 200, 30, "Nestle", False),
    ("Parle-G", "packet", 18, 8, 10, "1905", 150, 25, "Parle", False),
    ("Surf Excel 1kg", "packet", 18, 95, 115, "3402", 30, 8, "Surf Excel", False),
    ("Loose Sugar", "kg", 0, 40, 48, "1701", 100, 15, None, True),
    ("Loose Rice", "kg", 0, 42, 52, "1006", 120, 20, None, True),
    ("Loose Toor Dal", "kg", 0, 110, 130, "0713", 60, 10, None, True),
]


def run():
    init_db()
    for name, unit, gst, cost, mrp, hsn, stock, reorder, brand, loose in SEED_PRODUCTS:
        result = add_product(
            name=name, unit=unit, gst_rate=gst, cost_price=cost, mrp=mrp,
            hsn_code=hsn, initial_stock=stock, reorder_level=reorder,
            brand=brand, is_loose=loose,
        )
        print(result)


if __name__ == "__main__":
    run()
