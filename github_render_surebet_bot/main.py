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
        from telegram_notifier import format_surebet_message, send_message_simple
        logger.info("✅ 模組導入成功")

        logger.info("🚀 開始執行爬蟲...")
        surebet_data = scrape_oddsportal_surebets()
        logger.info(f"📊 爬蟲完成，共 {len(surebet_data)} 筆資料")

        if not surebet_data:
            logger.warning("⚠️ 沒有找到套利機會")
            error_message = "❌ 目前沒有找到符合條件的套利機會\n\n💡 可能原因：\n• 市場波動較小\n• 賠率已調整\n• 網站暫時限制訪問\n\n🔄 建議15分鐘後再試"
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
• ROI ≥ 2%
• 運動類型：足球、籃球、網球、排球、美式足球
• 總投注額：$400

💡 **提醒：**
• 套利機會稍縱即逝，建議盡快下注
• 資料每5分鐘更新一次
• 確保各平台帳戶有足夠資金

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

⚙️ **搜尋條件：**
• ROI ≥ 2%
• 運動類型：足球、籃球、網球、排球、美式足球
• 總投注額：$400

💰 **套利原理：**
利用不同博彩公司的賠率差異，無論比賽結果如何都能獲利

💡 **使用提醒：**
1. 套利機會稍縱即逝，建議盡快下注
2. 確保在各平台都有足夠資金
3. 注意各平台的投注限額
4. 資料每5分鐘自動更新

🔄 **快取機制：**
• 為避免頻繁請求，系統會快取5分鐘
• 如需強制更新，請使用 `/clear` 清除快取

🚀 **快速開始：**
發送 `$$$` 立即搜尋套利機會"""
        
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
