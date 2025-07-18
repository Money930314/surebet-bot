# main.py
import os
import logging
from flask import Flask, jsonify

from scraper import top_surebets
from telegram_notifier import start_bot_polling

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("surebet-main")

app = Flask(__name__)


@app.get("/healthz")
def health():
    return "ok", 200


@app.get("/surebets")
def route_surebets():
    """REST：直接回傳最新五筆 ROI 最高的套利"""
    return jsonify(top_surebets())


if __name__ == "__main__":
    # 🟢 只啟動一次 polling，避免 Conflict
    start_bot_polling()
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
