"""
Central config. Reads from environment variables (works with a .env file
loaded via python-dotenv, or Colab's userdata secrets copied into os.environ
before this module is imported -- see colab_bootstrap in README).
"""
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./store.db")
INVOICE_DIR = os.environ.get("INVOICE_DIR", "./invoices")
DECK_DIR = os.environ.get("DECK_DIR", "./decks")

SHOP_NAME = os.environ.get("SHOP_NAME", "Nebula Kirana Store")
SHOP_GSTIN = os.environ.get("SHOP_GSTIN", "22AAAAA0000A1Z5")
SHOP_ADDRESS = os.environ.get("SHOP_ADDRESS", "123 Market Road, Coimbatore, TN")

os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
os.makedirs(INVOICE_DIR, exist_ok=True)
os.makedirs(DECK_DIR, exist_ok=True)
