from flask import Flask
from telegram_notifier import send_message
from oddsportal_scraper_selenium import scrape_oddsportal_surebets
import os

app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Surebet Bot is running."

@app.route("/trigger")
def trigger():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    data = scrape_oddsportal_surebets()
    print("📊 爬蟲回傳資料：", data)

    if not data:
        print("⚠️ 沒有找到任何套利比賽，可能是資料抓不到或不符合條件")
        return "❌ 沒有套利比賽"

    for match in data:
        print("📤 準備發送訊息給 Telegram，內容：", match)
        send_message(bot_token, chat_id, match)

    return "📬 Messages sent!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
