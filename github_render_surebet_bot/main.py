from flask import Flask
import sys
import logging
from datetime import datetime
from threading import Thread
import asyncio
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

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
            error_message = "❌ 目前沒有找到符合條件的套利機會\n\n條件設定：\n- ROI ≥ 3%\n- 運動類型：足球、籃球、網球、排球、美式足球"
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

# Telegram 指令處理器
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /start 指令"""
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
    
    welcome_message = """
🤖 **歡迎使用 Surebet Bot！**

📋 **指令列表：**
• `$$$` - 搜尋套利機會
• `/help` - 顯示使用說明
• `/start` - 顯示歡迎訊息

⚙️ **搜尋條件：**
• ROI ≥ 3%
• 運動類型：足球、籃球、網球、排球、美式足球
• 總投注額：$400

💡 **提醒：**
套利機會稍縱即逝，建議盡快下注！

🚀 **開始使用：**
直接發送 `$$$` 開始搜尋套利機會
"""
    await context.bot.send_message(chat_id=chat_id, text=welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /help 指令"""
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
    
    help_message = """
🤖 **Surebet Bot 使用說明**

📋 **指令列表：**
• `$$$` - 搜尋套利機會
• `/help` - 顯示此說明
• `/start` - 顯示歡迎訊息

⚙️ **搜尋條件：**
• ROI ≥ 3%
• 運動類型：足球、籃球、網球、排球、美式足球
• 總投注額：$400

💰 **套利原理：**
利用不同博彩公司的賠率差異，無論比賽結果如何都能獲利

💡 **使用提醒：**
1. 套利機會稍縱即逝，建議盡快下注
2. 確保在各平台都有足夠資金
3. 注意各平台的投注限額

🚀 **快速開始：**
發送 `$$$` 立即搜尋套利機會
"""
    await context.bot.send_message(chat_id=chat_id, text=help_message)

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
                
        elif text.lower() in ["help", "幫助"]:
            await help_command(update, context)
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❓ 不認識的指令\n\n📋 可用指令：\n• `$$$` - 搜尋套利機會\n• `/help` - 查看詳細說明\n• `/start` - 顯示歡迎訊息"
            )
            
    except Exception as e:
        logger.error(f"❌ 處理訊息時發生錯誤: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ 處理訊息時發生錯誤，請稍後再試"
        )

def setup_telegram_bot():
    """設定 Telegram 機器人"""
    global telegram_app
    try:
        # 創建應用程式
        telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # 添加指令處理器
        telegram_app.add_handler(CommandHandler("start", start_command))
        telegram_app.add_handler(CommandHandler("help", help_command))
        
        # 添加訊息處理器
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("🤖 Telegram Bot 設定完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ Telegram Bot 設定失敗: {e}")
        return False

def flask_server():
    """Flask 伺服器函數"""
    logger.info("🚀 Flask 伺服器啟動中...")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# 🔃 啟動應用
if __name__ == '__main__':
    # 設定 Telegram Bot
    if not setup_telegram_bot():
        logger.error("❌ 無法設定 Telegram Bot，程式退出")
        sys.exit(1)
    
    # 在子線程中啟動 Flask
    flask_thread = Thread(target=flask_server, daemon=True)
    flask_thread.start()
    
    logger.info("🤖 Telegram Bot 監聽器啟動中...")
    
    # 在主線程中運行 Telegram Bot
    try:
        # 修復衝突：添加更多配置選項
        telegram_app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            timeout=30,  # 增加超時時間
            bootstrap_retries=5,  # 增加重試次數
            read_timeout=20,  # 讀取超時
            write_timeout=20,  # 寫入超時
            connect_timeout=20,  # 連接超時
            pool_timeout=20  # 池超時
        )
    except KeyboardInterrupt:
        logger.info("👋 程式被使用者中斷")
    except Exception as e:
        logger.error(f"❌ Telegram Bot 運行錯誤: {e}")
        # 如果是衝突錯誤，嘗試重新啟動
        if "Conflict" in str(e):
            logger.info("🔄 偵測到衝突，正在重新啟動...")
            import time
            time.sleep(5)  # 等待 5 秒後重新啟動
            try:
                telegram_app.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True
                )
            except Exception as restart_error:
                logger.error(f"❌ 重新啟動失敗: {restart_error}")
    finally:
        logger.info("🔚 程式結束")
