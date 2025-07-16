# main.py

from flask import Flask
import sys
import logging
from datetime import datetime
from threading import Thread
# import asyncio      # asyncio 可留可刪
import os

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

from scraper import scrape_oddsportal_surebets
from telegram_notifier import notify_telegram

# 日誌設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 讀取環境變數
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ 未設定 TELEGRAM_BOT_TOKEN")
    sys.exit(1)

app = Flask(__name__)
telegram_app = None
is_processing = False  # 防止重複處理

@app.route("/")
def home():
    return "🤖 Surebet Bot 運行中！"

@app.route("/trigger")
def trigger_bot():
    """手動觸發套利推播"""
    return run_scraper_and_notify()

@app.route("/test-telegram")
def test_telegram():
    """測試 Telegram 推播"""
    try:
        notify_telegram({"text": "📣 測試訊息，Bot 正常運作！"})
        return "✅ 已發送測試訊息"
    except Exception as e:
        logger.error(f"❌ 發送測試訊息失敗: {e}")
        return f"❌ {e}"

def run_scraper_and_notify():
    global is_processing
    if is_processing:
        return "⏳ 正在處理中，請稍後再試"
    is_processing = True

    try:
        results = scrape_oddsportal_surebets()
        if not results:
            return "❌ 未抓到套利機會"

        for match in results:
            notify_telegram(match)

        return f"📤 已發送 {len(results)} 筆套利機會"
    except Exception as e:
        logger.error(f"❌ 推播時發生錯誤: {e}")
        return f"❌ {e}"
    finally:
        is_processing = False

# ---------- 同步啟動 Telegram Bot ----------
def start_bot():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    # 註冊指令與訊息處理
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("👋 歡迎使用 Surebet Bot！輸入 /help 查看指令。")

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "/start - 開始\n"
            "/help - 幫助\n"
            "/clear - 清除狀態\n"
            "直接傳送任意文字可觸發套利檢索"
        )

    async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("🗑️ 已清除狀態。")

    async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 任何文字訊息同樣觸發一次推播
        await update.message.reply_text("🔍 正在搜尋套利機會...")
        result = run_scraper_and_notify()
        await update.message.reply_text(result)

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
    )

    logger.info("🤖 Telegram Bot 開始運行 (polling)")
    application.run_polling()


if __name__ == "__main__":
    # 背景執行 Telegram Bot
    Thread(target=start_bot, daemon=True).start()
    logger.info("🚀 Flask HTTP API 服務啟動中...")
    app.run(host="0.0.0.0", port=10000)
