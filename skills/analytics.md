# Analytics Skill

Tools: `get_daily_summary`, `close_day`, `get_sales_range`.

- `get_daily_summary` is read-only and can be called any number of times.
- `close_day` is idempotent per calendar date: if the day is already
  closed, it returns the saved snapshot instead of recomputing — a
  duplicate "close the day" message can't create two different totals.
