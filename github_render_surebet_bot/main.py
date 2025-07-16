"""main.py
改版：
* 移除自動推播邏輯，只保留 API 與 Telegram 指令互動。
* /surebets 路由動態呼叫 `fetch_surebets`，無需背景 worker。
"""
import os
import threading
import logging
from flask import Flask, jsonify, request

from scraper import fetch_surebets
from telegram_notifier import start_bot_polling

FETCH_MIN_ROI = float(os.getenv("MIN_ROI", 1))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("surebet-main")

app = Flask(__name__)

@app.route("/healthz")
def health():
    return "ok", 200

@app.route("/surebets")
def surebets_route():
    roi = request.args.get("min_roi", default=FETCH_MIN_ROI, type=float)
    return jsonify(fetch_surebets(min_roi=roi))

# 啟動 Telegram Bot (非阻塞)
threading.Thread(target=start_bot_polling, daemon=True).start()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- End of file ---
