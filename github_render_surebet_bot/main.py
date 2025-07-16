"""main.py – Flask API + Telegram Bot (polling)

* 域名 /surebets  → 即時查詢 ROI 最高的套利 JSON
* Telegram Bot   → 由 telegram_notifier.start_bot_polling() 啟動

App 本身不做背景推播；所有查詢都由使用者指令或 REST API 觸發。
"""
import os
import threading
import logging
from flask import Flask, jsonify, request

from scraper import fetch_surebets
from telegram_notifier import start_bot_polling

# ===== 基本設定 =====
DEFAULT_MIN_ROI = float(os.getenv("MIN_ROI", 0))  # API 預設 ROI 下限
DEFAULT_STAKE = float(os.getenv("DEFAULT_STAKE", 100))  # Bot /scan 預設下注總額

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("surebet-main")

app = Flask(__name__)

# ===== 路由 =====

@app.route("/healthz")
def health():
    """簡易健康檢查"""
    return "ok", 200

@app.route("/surebets")
def surebets_route():
    """GET /surebets?min_roi=5&stake=200&sport=soccer"""
    min_roi = request.args.get("min_roi", default=DEFAULT_MIN_ROI, type=float)
    stake = request.args.get("stake", default=DEFAULT_STAKE, type=float)
    sport = request.args.get("sport")  # e.g. basketball

    sports = None
    if sport:
        from telegram_notifier import SPORT_ALIASES
        key = SPORT_ALIASES.get(sport.lower())
        if key:
            sports = [key]
        else:
            return jsonify({"error": "sport not supported"}), 400

    bets = fetch_surebets(sports=sports, min_roi=min_roi, total_stake=stake)
    return jsonify(bets[:5])

# ===== 啟動 Telegram Bot (非阻塞) =====
threading.Thread(target=start_bot_polling, daemon=True).start()

# ===== 執行 =====
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info("SureBet API running on port %s", port)
    app.run(host="0.0.0.0", port=port)
