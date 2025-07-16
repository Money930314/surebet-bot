"""main.py
Render 執行入口：定時抓取 surebets 並推 Telegram。
"""
import os
import threading
import time
import logging
from flask import Flask, jsonify

from scraper import fetch_surebets
from telegram_notifier import notify_telegram

TELEGRAM_ENABLED = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL", 300))
MIN_ROI = float(os.getenv("MIN_ROI", 1))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("surebet-main")

app = Flask(__name__)
_latest = []

@app.route("/healthz")
def health():
    return "ok", 200

@app.route("/surebets")
def surebets_route():
    return jsonify(_latest)

def worker():
    global _latest
    while True:
        try:
            bets = fetch_surebets(min_roi=MIN_ROI)
            _latest = bets
            logger.info("抓到 %d 筆 surebet (ROI≥%.1f)", len(bets), MIN_ROI)
            if TELEGRAM_ENABLED and bets:
                notify_telegram(bets[0])
        except Exception:
            logger.exception("worker error")
        time.sleep(FETCH_INTERVAL)

threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

# === 說明 ===
# 1. 修正 KeyError: 'league'（scraper now returns `league` key）。
# 2. DEFAULT_SPORTS 更新：移除未知 sport、加入 UEFA Champions League。
