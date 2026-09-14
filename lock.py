"""
SQLite does not give us row-level SELECT ... FOR UPDATE the way Postgres does.
To make stock decrements and bill finalization atomic under concurrent
requests (two bills in flight, or a sale racing a stock-in), every write
that touches `products.stock_qty` takes this process-wide lock for the
duration of its transaction.

This is a deliberate, documented tradeoff for a single-process SQLite bot.
If you swap DATABASE_PATH for a Postgres URL in db.py, replace this lock
with `SELECT ... FOR UPDATE` inside the same transaction and you get real
multi-process safety for free -- the tool functions call `with DB_LOCK:`
in exactly the places you'd otherwise add `.with_for_update()`.
"""
import threading

DB_LOCK = threading.RLock()
