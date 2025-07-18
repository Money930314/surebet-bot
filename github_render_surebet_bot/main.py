import os
import threading
import logging
from flask import Flask, jsonify

# 修改：使用新的 top_surebets 取代 fetch_surebets
from scraper import top_surebets
from telegram_notifier import start_bot_polling

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("surebet-main")

app = Flask(__name__)


@app.route("/healthz")
def health():
    return "ok", 200


@app.route("/surebets")
def route_surebets():
    """REST：直接回傳最新五筆 ROI 最高的套利"""
    data = top_surebets()
    return jsonify(data)


# 背景啟動 Telegram Bot
threading.Thread(target=start_bot_polling, daemon=True).start()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
