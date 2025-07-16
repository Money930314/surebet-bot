"""main.py – Flask API + Telegram Bot

* `/healthz`      → 簡易健康檢查（Render 用）
* `/surebets`     → REST 查詢：?sport=soccer&stake=150&days=7&min_roi=0
* Telegram Bot    → 背景執行，指令邏輯在 `telegram_notifier.py`
"""
import os
import threading
import logging
from flask import Flask, jsonify, request

from scraper import fetch_surebets
from telegram_notifier import (
    start_bot_polling,
    SPORT_ALIASES,
    DEFAULT_STAKE,
    DEFAULT_DAYS,
    MAX_DAYS,
)

DEFAULT_ROI = float(os.getenv("MIN_ROI", 0.0))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("surebet-main")

app = Flask(__name__)

# ------------------ Routes ------------------

@app.route("/healthz")
def health():
    return "ok", 200

@app.route("/surebets")
def surebets_route():
    """e.g. /surebets?sport=soccer&stake=150&days=7&min_roi=5"""
    min_roi = request.args.get("min_roi", default=DEFAULT_ROI, type=float)
    stake = request.args.get("stake", default=DEFAULT_STAKE, type=float)
    days = request.args.get("days", default=DEFAULT_DAYS, type=int)
    days = max(1, min(days, MAX_DAYS))

    sport_arg = request.args.get("sport")
    sports = None
    if sport_arg:
        key = SPORT_ALIASES.get(sport_arg.lower())
        if not key:
            return jsonify({"error": f"unsupported sport '{sport_arg}'"}), 400
        sports = [key]

    bets = fetch_surebets(sports=sports, min_roi=min_roi, total_stake=stake, days_window=days)
    return jsonify(bets[:5])

# ------------------ Start ------------------

def run_app():
    # 背景跑 Telegram Bot
    threading.Thread(target=start_bot_polling, daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    logger.info("SureBet API running on port %s", port)
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    run_app()
