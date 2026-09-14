"""
Telegram front door. Polling mode (no public URL needed -- works fine
from Colab or any box with outbound HTTPS). Every update_id is logged
before processing so a Telegram redelivery is dropped here, on top of
the bill-level idempotency in tools/billing.py.
"""
import logging
import os

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters

import agent
import config
from db import SessionLocal, TelegramUpdateLog, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kirana-bot")


def _already_processed(update_id: int) -> bool:
    session = SessionLocal()
    try:
        if session.get(TelegramUpdateLog, update_id):
            return True
        session.add(TelegramUpdateLog(update_id=update_id))
        session.commit()
        return False
    finally:
        session.close()


async def on_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _already_processed(update.update_id):
        return
    agent.reset_chat(update.effective_chat.id)
    await update.message.reply_text(
        "Started a fresh chat. Your stock, bills, khata and preferences are all still saved."
    )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if _already_processed(update.update_id):
        log.info("Skipping duplicate update_id=%s", update.update_id)
        return

    chat_id = update.effective_chat.id
    text = update.message.text
    log.info("chat=%s text=%r", chat_id, text)

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    try:
        reply_text, files = agent.handle_message(chat_id, text)
    except Exception as e:  # noqa: BLE001
        log.exception("agent error")
        await update.message.reply_text(f"Something went wrong on my end: {e}")
        return

    await update.message.reply_text(reply_text)
    for path in files:
        if os.path.exists(path):
            with open(path, "rb") as f:
                await context.bot.send_document(chat_id=chat_id, document=f,
                                                  filename=os.path.basename(path))


def main():
    init_db()
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("new", on_new))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    log.info("Bot starting (polling)...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
