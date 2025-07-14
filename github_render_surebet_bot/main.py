from flask import Flask
import sys
import logging
from datetime import datetime
from threading import Thread
from telegram.ext import Updater, MessageHandler, Filters
import os

# 配置 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 讀取環境變數
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 初始化 Flask 應用
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Surebet Bot 運行中！"

@app.route('/trigger')
def trigger_bot():
    """手動觸發套利推播"""
    return run_scraper_and_notify()

@app.route('/test-telegram')
def test_telegram():
    """測試 Telegram 推播"""
    from telegram_notifier import send_message
    test_message = f"🧪 測試訊息\n時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n這是來自 Render 的測試推播"
    if send_message(test_message):
        return "✅ Telegram 測試成功！請查看手機"
    else:
        return "❌ Telegram 測試失敗"

def run_scraper_and_notify():
    try:
        logger.info("📥 正在導入爬蟲模組...")
        from scraper import scrape_oddsportal_surebets
        from telegram_notifier import send_message, format_surebet_message
        logger.info("✅ 模組導入成功")

        logger.info("🚀 開始執行爬蟲...")
        surebet_data = scrape_oddsportal_surebets()
        logger.info(f"📊 爬蟲完成，共 {len(surebet_data)} 筆資料")

        if not surebet_data:
            logger.warning("⚠️ 沒有找到套利機會")
            return "❌ 沒有套利比賽"

        message = format_surebet_message(surebet_data)
        logger.info("📤 正在發送訊息到 Telegram...")
        if send_message(message):
            return f"✅ 推播成功，共 {len(surebet_data)} 筆套利機會"
        else:
            return "❌ 推播失敗"

    except Exception as e:
        logger.error(f"❌ 錯誤: {str(e)}")
        return f"❌ 執行錯誤: {str(e)}"

# 🎯 處理 Telegram 指令 $$$
def telegram_listener():
    def handle_message(update, context):
        text = update.message.text.strip()
        if text == "$$$":
            logger.info("💬 收到 Telegram 指令 $$$")
            reply = run_scraper_and_notify()
            context.bot.send_message(chat_id=update.effective_chat.id, text=reply)

    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    logger.info("🤖 Telegram Bot 啟動中，等待 $$$ 指令...")
    updater.start_polling()

# 🔃 啟動 Flask 與 Telegram 監聽
if __name__ == '__main__':
    Thread(target=telegram_listener, daemon=True).start()
    logger.info("🚀 Surebet Bot 正在啟動 Flask 應用...")
    app.run(host='0.0.0.0', port=10000, debug=False)
