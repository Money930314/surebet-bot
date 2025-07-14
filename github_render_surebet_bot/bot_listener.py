import os
import time
import logging
import telegram
from telegram.ext import Updater, MessageHandler, Filters
from oddsportal_scraper_selenium import scrape_oddsportal_surebets
from telegram_notifier import send_message

# 初始化 bot
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
bot = telegram.Bot(token=TOKEN)

logging.basicConfig(level=logging.INFO)

def handle_message(update, context):
    text = update.message.text.strip()
    if text == "$$$":
        logging.info("✅ 收到 $$$ 指令，開始抓取套利資訊...")
        data = scrape_oddsportal_surebets()
        if not data:
            bot.send_message(chat_id=CHAT_ID, text="❌ 沒有套利比賽")
            return

        for match in data:
            send_message(TOKEN, CHAT_ID, match)

def main():
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    logging.info("🤖 Telegram bot 已啟動，等待 $$$ 指令中...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
