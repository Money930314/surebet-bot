"""main.py
Render 執行入口：定時（每 5 分鐘）抓取 surebets，並將最高 ROI 的結果發送到 Telegram。
在 Render 的 web service 模式下，我們啟動一個簡單的 Flask 伺服器以保持運行，同時用背景 thread 定時抓資料。
"""
import os
import threading
import time
import logging
from flask import Flask, jsonify

from scraper import fetch_surebets
from telegram_notifier import notify_telegram

# --------------------------------------------------
# 環境變數
# --------------------------------------------------
TELEGRAM_ENABLED = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL", 300))  # seconds
MIN_ROI = float(os.getenv("MIN_ROI", 1.0))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("surebet-main")

app = Flask(__name__)

_latest_cache = []

@app.route("/healthz")
def health_check():
    return "ok", 200

@app.route("/surebets")
def get_surebets():
    return jsonify(_latest_cache)

def _worker_loop():
    global _latest_cache
    while True:
        try:
            bets = fetch_surebets(min_roi=MIN_ROI)
            _latest_cache = bets
            logger.info("抓到 %d 筆 surebets (ROI >= %.2f)", len(bets), MIN_ROI)
            if TELEGRAM_ENABLED and bets:
                top = bets[0]
                notify_telegram(top)
        except Exception as e:
            logger.exception("背景抓取發生錯誤: %s", e)
        time.sleep(FETCH_INTERVAL)

# 在啟動 Flask 前就跑背景執行緒
threading.Thread(target=_worker_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# === 說明 ===
# 1. 若要在本地測試，請建立 .env：
#    THE_ODDS_API_KEY=e9c7f8945b8fcab5d904fc7f6ef6c2da
#    TELEGRAM_BOT_TOKEN=<your-bot-token>
#    TELEGRAM_CHAT_ID=<your-chat-id>
# 2. Render.yaml 指向 `python main.py` 即可
# 3. 需要曝光 port，Render 預設會提供 PORT 環境變數
