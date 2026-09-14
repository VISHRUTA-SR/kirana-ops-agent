from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String,
    UniqueConstraint, create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

import config

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    brand = Column(String)
    unit = Column(String, nullable=False)          # kg, g, litre, ml, packet, dozen, piece
    is_loose = Column(Boolean, default=False)
    hsn_code = Column(String)
    gst_rate = Column(Float, default=0.0)           # e.g. 5.0 means 5%
    cost_price = Column(Float, nullable=False)
    mrp = Column(Float, nullable=False)
    stock_qty = Column(Float, default=0.0)
    reorder_level = Column(Float, default=0.0)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    phone = Column(String)


class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True)
    status = Column(String, default="draft")        # draft | finalized | void
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finalized_at = Column(DateTime)
    payment_mode = Column(String)                    # cash | upi | card | credit
    payment_ref = Column(String)
    subtotal = Column(Float, default=0.0)
    cgst = Column(Float, default=0.0)
    sgst = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    idempotency_key = Column(String, unique=True, nullable=True)

    items = relationship("BillItem", backref="bill", cascade="all, delete-orphan")
    customer = relationship("Customer")


class BillItem(Base):
    __tablename__ = "bill_items"
    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey("bills.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    product_name_snapshot = Column(String)
    qty = Column(Float)
    unit_price = Column(Float)
    gst_rate = Column(Float)
    cgst_amt = Column(Float)
    sgst_amt = Column(Float)
    line_total = Column(Float)


class KhataTransaction(Base):
    __tablename__ = "khata_transactions"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    type = Column(String)                            # credit | settle
    amount = Column(Float)
    mode = Column(String)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    type = Column(String)                            # in | out | adjust
    qty = Column(Float)
    ref_bill_id = Column(Integer, nullable=True)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Preference(Base):
    """
    Standing owner preferences (default payment mode, preferred brands,
    shop name/GSTIN for invoices, etc). Keyed globally -- NOT by chat_id --
    which is what makes these survive a Telegram /new chat: the LLM
    conversation buffer resets, this table does not.
    """
    __tablename__ = "preferences"
    key = Column(String, primary_key=True)
    value = Column(String)


class DailyClose(Base):
    __tablename__ = "daily_closes"
    date = Column(String, primary_key=True)          # YYYY-MM-DD
    total_sales = Column(Float)
    tax_collected = Column(Float)
    cash_total = Column(Float)
    upi_total = Column(Float)
    card_total = Column(Float)
    credit_total = Column(Float)
    closed_at = Column(DateTime, default=datetime.utcnow)


class TelegramUpdateLog(Base):
    """Dedupes Telegram's own redelivered updates (network retries)."""
    __tablename__ = "telegram_update_log"
    update_id = Column(Integer, primary_key=True)


engine = create_engine(
    f"sqlite:///{config.DATABASE_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        # WAL mode = readers don't block the writer; helps with concurrent
        # Telegram updates hitting the DB at once.
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
