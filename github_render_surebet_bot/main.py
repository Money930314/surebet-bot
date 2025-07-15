from flask import Flask
import sys
import logging
from datetime import datetime
from threading import Thread
import asyncio
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
import signal
import time

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

# 全局 Telegram 應用實例
telegram_app = None
is_processing = False  # 防止重複處理

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
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "is_processing": is_processing
    }

@app.route('/clear-cache')
def clear_cache():
    """清除爬蟲緩存"""
    try:
        from scraper import clear_cache
        clear_cache()
        return "✅ 緩存已清除"
    except Exception as e:
        return f"❌ 清除緩存失敗: {str(e)}"

@app.route('/stop-bot')
def stop_bot():
    """停止 Telegram Bot（解決衝突）"""
    global telegram_app
    if telegram_app:
        try:
            telegram_app.stop()
            logger.info("🛑 Telegram Bot 已停止")
            return "✅ Telegram Bot 已停止"
        except Exception as e:
            logger.error(f"❌ 停止 Bot 時發生錯誤: {e}")
            return f"❌ 停止失敗: {str(e)}"
    return "⚠️ Bot 未運行"

def run_scraper_and_notify():
    """執行爬蟲並發送通知"""
    global is_processing
    
    if is_processing:
        logger.warning("⚠️ 正在處理中，跳過重複請求")
        return "⚠️ 正在處理中，請稍候..."
    
    is_processing = True
    
    try:
        logger.info("📥 正在導入爬蟲模組...")
        from scraper import scrape_oddsportal_surebets
        from telegram_notifier import send_message_simple
        logger.info("✅ 模組導入成功")

        logger.info("🚀 開始執行爬蟲...")
        surebet_data = scrape_oddsportal_surebets()
        logger.info(f"📊 爬蟲完成，共 {len(surebet_data)} 筆資料")

        if not surebet_data:
            logger.warning("⚠️ 沒有找到套利機會")
            # 發送無套利機會的通知
            no_data_message = f"""❌ **目前沒有找到套利機會**

🕒 **檢查時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💡 **可能原因:**
• 目標網站存在反爬蟲保護
• 當前沒有符合條件的套利機會
• 網站暫時無法訪問
• 網站結構已變更

🔧 **建議操作:**
• 等待 15-30 分鐘後再試
• 檢查網站是否正常運作
• 確認網路連接狀態

⚠️ **注意**: 此系統只顯示真實爬取到的資料，不會提供模擬資料"""
            
            send_message_simple(no_data_message)
            return "⚠️ 沒有找到套利機會，已發送通知"

        # 如果有真實資料，格式化並發送訊息
        from telegram_notifier import format_surebet_message
        message = format_surebet_message(surebet_data)
        logger.info("📤 正在發送訊息到 Telegram...")
        
        if send_message_simple(message):
            success_msg = f"✅ 推播成功，共 {len(surebet_data)} 筆真實套利機會"
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
    finally:
        is_processing = False

# Telegram 指令處理器
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /start 指令"""
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        logger.info(f"💬 收到 /start 指令，用戶: {user_id}")
        
        # 檢查是否為授權用戶
        if str(user_id) != TELEGRAM_CHAT_ID:
            logger.warning(f"⚠️ 未授權用戶嘗試使用: {user_id}")
            await context.bot.send_message(
                chat_id=chat_id, 
                text="❌ 抱歉，您沒有使用權限"
            )
            return
        
        welcome_message = """🤖 **歡迎使用 Surebet Bot！**

📋 **指令列表：**
• `$$$` - 搜尋套利機會
• `/help` - 顯示使用說明
• `/start` - 顯示歡迎訊息
• `/clear` - 清除快取資料

⚙️ **搜尋條件：**
• 只顯示真實爬取到的資料
• 不會提供模擬或假資料
• 運動類型：足球、籃球、網球、排球、美式足球

💡 **重要說明：**
• 此系統只提供真實套利機會
• 如網站有反爬蟲保護，將顯示無資料
• 資料每5分鐘更新一次
• 套利機會稍縱即逝，建議盡快下注

🚀 **開始使用：**
直接發送 `$$$` 開始搜尋套利機會"""
        
        await context.bot.send_message(
            chat_id=chat_id, 
            text=welcome_message,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ 處理 /start 指令時發生錯誤: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ 指令處理失敗，請稍後再試"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /help 指令"""
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        logger.info(f"💬 收到 /help 指令，用戶: {user_id}")
        
        # 檢查是否為授權用戶
        if str(user_id) != TELEGRAM_CHAT_ID:
            logger.warning(f"⚠️ 未授權用戶嘗試使用: {user_id}")
            await context.bot.send_message(
                chat_id=chat_id, 
                text="❌ 抱歉，您沒有使用權限"
            )
            return
        
        help_message = """🤖 **Surebet Bot 使用說明**

📋 **指令列表：**
• `$$$` - 搜尋套利機會
• `/help` - 顯示此說明
• `/start` - 顯示歡迎訊息
• `/clear` - 清除快取資料

⚙️ **系統特色：**
• 只提供真實爬取到的套利資料
• 不會顯示模擬或假資料
• 當網站有反爬蟲保護時會如實告知
• 資料每5分鐘自動更新

💰 **套利原理：**
利用不同博彩公司的賠率差異，無論比賽結果如何都能獲利

💡 **使用提醒：**
1. 套利機會稍縱即逝，建議盡快下注
2. 確保在各平台都有足夠資金
3. 注意各平台的投注限額
4. 如顯示無資料，可能是網站限制訪問

🔄 **快取機制：**
• 為避免頻繁請求，系統會快取5分鐘
• 如需強制更新，請使用 `/clear` 清除快取

🚀 **快速開始：**
發送 `$$$` 立即搜尋套利機會

⚠️ **重要說明：**
此系統承諾只提供真實資料，絕不提供假資料或模擬資料"""
        
        await context.bot.send_message(
            chat_id=chat_id, 
            text=help_message,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ 處理 /help 指令時發生錯誤: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ 指令處理失敗，請稍後再試"
        )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /clear 指令"""
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        logger.info(f"💬 收到 /clear 指令，用戶: {user_id}")
        
        # 檢查是否為授權用戶
        if str(user_id) != TELEGRAM_CHAT_ID:
            logger.warning(f"⚠️ 未授權用戶嘗試使用: {user_id}")
            await context.bot.send_message(
                chat_id=chat_id, 
                text="❌ 抱歉，您沒有使用權限"
            )
            return
        
        from scraper import clear_cache
        clear_cache()
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ 緩存已清除，您可以重新發送 $$$ 取得最新套利資訊"
        )

    except Exception as e:
        logger.error(f"❌ 處理 /clear 指令時發生錯誤: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ 指令處理失敗，請稍後再試"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理一般訊息"""
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        message_text = update.message.text
        
        logger.info(f"💬 收到訊息: {message_text}，用戶: {user_id}")
        
        # 檢查是否為授權用戶
        if str(user_id) != TELEGRAM_CHAT_ID:
            logger.warning(f"⚠️ 未授權用戶嘗試使用: {user_id}")
            await context.bot.send_message(
                chat_id=chat_id, 
                text="❌ 抱歉，您沒有使用權限"
            )
            return
        
        # 處理套利搜尋指令
        if message_text.strip() == "$$$":
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔍 正在搜尋套利機會，請稍候...\n\n⚠️ 注意：只會顯示真實爬取到的資料"
            )
            
            # 執行爬蟲
            result = run_scraper_and_notify()
            
            if "沒有找到套利機會" in result:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ 沒有找到套利機會，請稍後再試"
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="✅ 已成功發送套利資訊，請查看訊息"
                )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ 指令無效，請使用 /help 查看可用指令"
            )

    except Exception as e:
        logger.error(f"❌ 處理訊息時發生錯誤: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ 系統錯誤，請稍後再試"
        )

# 啟動 Telegram Bot 的背景執行緒
async def telegram_bot():
    global telegram_app
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    telegram_app = application
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.updater.idle()

# 啟動 Flask 與 Telegram Bot
if __name__ == "__main__":
    Thread(target=lambda: asyncio.run(telegram_bot()), daemon=True).start()
    logger.info("🚀 Flask HTTP API 服務啟動中...")
    app.run(host="0.0.0.0", port=10000)
