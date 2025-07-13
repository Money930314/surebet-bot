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

    # ✅ 傳入完整假資料
    match = {
        "sport": "足球",
        "league": "英超",
        "datetime": "2025-07-13 20:00",
        "venue": "曼聯球場",
        "roi": "12.3%",
        "bookmaker1": "Pinnacle",
        "bookmaker2": "Betfair",
        "odds1": "2.1",
        "odds2": "2.05",
        "url": "https://www.oddsportal.com/test-match",
        "custom_message": "💰 測試套利成功"
    }

    send_message(bot_token, chat_id, match)
    return "✅ 測試訊息已發送"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
