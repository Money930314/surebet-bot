import os
import logging
import threading
from flask import Flask, jsonify, request

from scraper import fetch_surebets
from telegram_notifier import start_bot_polling

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("surebet-main")

app = Flask(__name__)


@app.route("/healthz")
def health() -> tuple[str, int]:
    return "ok", 200


@app.route("/surebets")
def route_surebets():
    """REST：/surebets?sport=soccer&stake=150&days=7&min_roi=2"""
    sport = request.args.get("sport")
    sports = [sport] if sport else None

    stake = float(request.args.get("stake", 100))
    days = max(1, min(int(request.args.get("days", 2)), 60))
    min_roi = float(request.args.get("min_roi", 0))

    data = fetch_surebets(
        sports=sports,
        total_stake=stake,
        days_window=days,
        min_roi=min_roi,
    )[:5]
    return jsonify(data)


# --- 背景啟動 Telegram Bot ---
threading.Thread(target=start_bot_polling, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
