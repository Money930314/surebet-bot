from flask import Flask
import sys
import logging
from datetime import datetime
from threading import Thread
import asyncio
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

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

# 檢查必要環境變數
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.error("❌ 缺少必要的環境變數 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
    sys.exit(1)

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
    from telegram_notifier import send_message_simple
    test_message = f"🧪 測試訊息\n時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n這是來自 Render 的測試推播"
    if send_message_simple(test_message):
        return "✅ Telegram 測試成功！請查看手機"
    else:
        return "❌ Telegram 測試失敗"

@app.route('/health')
def health_check():
    """健康檢查"""
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    }

def run_scraper_and_notify():
    """執行爬蟲並發送通知"""
    try:
        logger.info("📥 正在導入爬蟲模組...")
        from scraper import scrape_oddsportal_surebets
        from telegram_notifier import format_surebet_message, send_message_simple
        logger.info("✅ 模組導入成功")

        logger.info("🚀 開始執行爬蟲...")
        surebet_data = scrape_oddsportal_surebets()
        logger.info(f"📊 爬蟲完成，共 {len(surebet_data)} 筆資料")

        if not surebet_data:
            logger.warning("⚠️ 沒有找到套利機會")
            error_message = "❌ 目前沒有找到符合條件的套利機會\n\n條件設定：\n- ROI ≥ 10%\n- 運動類型：足球、籃球、網球、排球、美式足球"
            send_message_simple(error_message)
            return error_message

        # 格式化並發送訊息
        message = format_surebet_message(surebet_data)
        logger.info("📤 正在發送訊息到 Telegram...")
        
        if send_message_simple(message):
            success_msg = f"✅ 推播成功，共 {len(surebet_data)} 筆套利機會"
            logger.info(success_msg)
            return success_msg
        else:
            error_msg = "❌ 推播失敗，請檢查網路連接"
            logger.error(error_msg)
            return error_msg

    except ImportError as e:
        error_msg = f"❌ 模組導入失敗: {str(e)}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ 執行錯誤: {str(e)}"
        logger.error(error_msg)
        return error_msg

# Telegram 訊息處理器
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 Telegram 訊息"""
    try:
        text = update.message.text.strip()
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        logger.info(f"💬 收到訊息: '{text}' 來自用戶: {user_id}")
        
        # 檢查是否為授權用戶
        if str(user_id) != TELEGRAM_CHAT_ID:
            logger.warning(f"⚠️ 未授權用戶嘗試使用: {user_id}")
            await context.bot.send_message(
                chat_id=chat_id, 
                text="❌ 抱歉，您沒有使用權限"
            )
            return
        
        if text == "$$$":
            logger.info("💬 收到 Telegram 指令 $$$，開始執行...")
            
            # 發送處理中訊息
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔄 正在搜尋套利機會，請稍候..."
            )
            
            # 執行爬蟲
            reply = run_scraper_and_notify()
            
            # 如果是透過 run_scraper_and_notify 已經發送過訊息，則不再重複發送
            if "推播成功" not in reply:
                await context.bot.send_message(chat_id=chat_id, text=reply)
                
        elif text.lower() in ["/start", "/help", "help", "幫助"]:
            help_message = """
🤖 **Surebet Bot 使用說明**

📋 **指令列表：**
• `$$$` - 搜尋套利機會
• `/help` - 顯示此說明

⚙️ **搜尋條件：**
• ROI ≥ 10%
• 運動類型：足球、籃球、網球、排球、美式足球
• 總投注額：$400

💡 **提醒：**
套利機會稍縱即逝，建議盡快下注！
"""
            await context.bot.send_message(chat_id=chat_id, text=help_message)
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❓ 不認識的指令，請發送 `$$$` 搜尋套利機會，或 `/help` 查看說明"
            )
            
    except Exception as e:
        logger.error(f"❌ 處理訊息時發生錯誤: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ 處理訊息時發生錯誤，請稍後再試"
        )

async def run_telegram_bot():
    """運行 Telegram 機器人"""
    try:
        # 創建應用程式
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # 添加訊息處理器
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("🤖 Telegram Bot 啟動中，等待 $$ 指令...")
        
        # 使用 run_polling 方法，這是 v20.x 的推薦方式
        await application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        logger.info("✅ Telegram Bot 已啟動，監聽訊息中...")
        
    except Exception as e:
        logger.error(f"❌ Telegram Bot 啟動失敗: {e}")
        raise e

def telegram_listener():
    """Telegram 監聽器包裝函數"""
    try:
        # 為 Telegram bot 創建新的事件循環
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_telegram_bot())
    except Exception as e:
        logger.error(f"❌ Telegram 監聽器錯誤: {e}")

# 🔃 啟動 Flask 與 Telegram 監聽
if __name__ == '__main__':
    # 啟動 Telegram 監聽器
    telegram_thread = Thread(target=telegram_listener, daemon=True)
    telegram_thread.start()
    
    logger.info("🚀 Surebet Bot 正在啟動 Flask 應用...")
    
    # 啟動 Flask 應用
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
