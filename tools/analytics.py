"""
ANALYTICS SKILL
Rolls up finalized bills into daily/period summaries. close_day is
idempotent -- closing an already-closed day just returns the saved
snapshot rather than recomputing (protects against a duplicate
"close the day" message re-triggering work).
"""
from collections import defaultdict
from datetime import datetime, timedelta

from db import Bill, BillItem, DailyClose, SessionLocal
from utils import r2


def _day_bounds(date_str=None):
    if date_str:
        day = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        day = datetime.utcnow()
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end, start.strftime("%Y-%m-%d")


def get_daily_summary(date=None):
    """Compute (without saving) totals, tax collected, payment split, top items."""
    session = SessionLocal()
    try:
        start, end, date_str = _day_bounds(date)
        bills = session.query(Bill).filter(
            Bill.status == "finalized",
            Bill.finalized_at >= start,
            Bill.finalized_at < end,
        ).all()

        total_sales = r2(sum(b.total for b in bills))
        tax_collected = r2(sum(b.cgst + b.sgst for b in bills))
        by_mode = defaultdict(float)
        for b in bills:
            by_mode[b.payment_mode or "unknown"] += b.total

        item_qty = defaultdict(float)
        item_revenue = defaultdict(float)
        for b in bills:
            for it in b.items:
                item_qty[it.product_name_snapshot] += it.qty
                item_revenue[it.product_name_snapshot] += it.line_total
        top_items = sorted(item_revenue.items(), key=lambda kv: kv[1], reverse=True)[:5]

        return {
            "date": date_str,
            "bill_count": len(bills),
            "total_sales": total_sales,
            "tax_collected": tax_collected,
            "by_payment_mode": {k: r2(v) for k, v in by_mode.items()},
            "top_items": [{"product": name, "qty_sold": item_qty[name],
                            "revenue": r2(rev)} for name, rev in top_items],
        }
    finally:
        session.close()


def close_day(date=None):
    """Finalize and persist the day's summary. Idempotent per calendar date."""
    session = SessionLocal()
    try:
        _, _, date_str = _day_bounds(date)
        existing = session.get(DailyClose, date_str)
        if existing:
            return {"already_closed": True, "date": date_str,
                    "total_sales": existing.total_sales,
                    "tax_collected": existing.tax_collected,
                    "cash_total": existing.cash_total,
                    "upi_total": existing.upi_total,
                    "card_total": existing.card_total,
                    "credit_total": existing.credit_total}

        summary = get_daily_summary(date_str)
        by_mode = summary["by_payment_mode"]
        row = DailyClose(
            date=date_str,
            total_sales=summary["total_sales"],
            tax_collected=summary["tax_collected"],
            cash_total=by_mode.get("cash", 0.0),
            upi_total=by_mode.get("upi", 0.0),
            card_total=by_mode.get("card", 0.0),
            credit_total=by_mode.get("credit", 0.0),
        )
        session.add(row)
        session.commit()
        return {"success": True, **summary}
    finally:
        session.close()


def get_sales_range(start_date, end_date):
    """Day-by-day sales totals between two YYYY-MM-DD dates, for decks/reports."""
    session = SessionLocal()
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        bills = session.query(Bill).filter(
            Bill.status == "finalized",
            Bill.finalized_at >= start,
            Bill.finalized_at < end,
        ).all()
        by_day = defaultdict(float)
        for b in bills:
            by_day[b.finalized_at.strftime("%Y-%m-%d")] += b.total
        return {"daily_totals": [{"date": d, "total": r2(v)}
                                  for d, v in sorted(by_day.items())]}
    finally:
        session.close()
