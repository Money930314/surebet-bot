from flask import Flask
from telegram_notifier import send_message
from oddsportal_scraper_selenium import scrape_oddsportal_surebets

app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Surebet Bot is running on Render!"

@app.route("/trigger")
def trigger_surebet():
    data = scrape_oddsportal_surebets()
    if not data:
        return "❌ 沒有找到套利機會"

    match = data[0]
    send_message({
        "sport": match['sport'],
        "venue": match['match'],
        "match_time": "",
        "bets": match['odds'],
        "roi": float(match['profit'].replace('%','')),
        "profit": 0,
        "custom_message": "📊 Render 推播測試"
    })
    return "✅ 已推播至 Telegram"