from flask import Flask
import sys
import logging
from datetime import datetime

# 配置 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Surebet Bot 運行中！"

@app.route('/trigger')
def trigger_bot():
    """手動觸發套利推播"""
    logger.info("=== 開始執行 /trigger 端點 ===")
    
    try:
        # 導入爬蟲函數
        logger.info("📥 正在導入爬蟲模組...")
        from scraper import scrape_oddsportal_surebets
        logger.info("✅ 爬蟲模組導入成功")
        
        # 執行爬蟲
        logger.info("🚀 開始執行爬蟲...")
        surebet_data = scrape_oddsportal_surebets()
        logger.info(f"📊 爬蟲執行完成，回傳 {len(surebet_data) if surebet_data else 0} 筆資料")
        
        if not surebet_data:
            logger.warning("⚠️ 沒有找到套利機會")
            return "❌ 沒有套利比賽"
        
        # 導入 Telegram 推播函數
        logger.info("📱 正在導入 Telegram 模組...")
        from telegram_notifier import send_message, format_surebet_message
        logger.info("✅ Telegram 模組導入成功")
        
        # 格式化並發送訊息
        logger.info("📝 正在格式化訊息...")
        message = format_surebet_message(surebet_data)
        logger.info(f"📝 訊息格式化完成，長度: {len(message)} 字元")
        
        logger.info("📤 正在發送 Telegram 訊息...")
        success = send_message(message)
        
        if success:
            logger.info("✅ Telegram 訊息發送成功")
            return f"✅ 推播成功！找到 {len(surebet_data)} 筆套利機會"
        else:
            logger.error("❌ Telegram 訊息發送失敗")
            return "❌ 推播失敗"
            
    except ImportError as e:
        logger.error(f"❌ 模組導入錯誤: {str(e)}")
        return f"❌ 模組導入錯誤: {str(e)}"
        
    except Exception as e:
        logger.error(f"❌ 執行過程發生錯誤: {str(e)}")
        logger.error(f"錯誤類型: {type(e).__name__}")
        import traceback
        logger.error(f"完整錯誤追蹤:\n{traceback.format_exc()}")
        return f"❌ 執行錯誤: {str(e)}"

@app.route('/debug')
def debug_scraper():
    """調試爬蟲功能"""
    logger.info("=== 開始執行 /debug 端點 ===")
    
    try:
        logger.info("🔍 測試 Chrome 瀏覽器...")
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        import time
        
        # 測試 Chrome 是否能正常啟動
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        logger.info("🚀 正在啟動 Chrome...")
        driver = webdriver.Chrome(options=chrome_options)
        logger.info("✅ Chrome 啟動成功")
        
        try:
            # 測試訪問 OddsPortal
            logger.info("🌐 正在訪問 OddsPortal...")
            driver.get("https://www.oddsportal.com/sure-bets/")
            logger.info("✅ 頁面載入成功")
            
            time.sleep(5)
            
            # 檢查頁面標題
            title = driver.title
            logger.info(f"📄 頁面標題: {title}")
            
            # 檢查是否有表格
            from selenium.webdriver.common.by import By
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            logger.info(f"📊 找到 {len(rows)} 筆表格資料")
            
            # 檢查前幾筆資料
            sample_data = []
            for i, row in enumerate(rows[:3]):
                try:
                    row_text = row.text.strip()
                    sample_data.append(f"Row {i+1}: {row_text[:100]}...")
                except:
                    sample_data.append(f"Row {i+1}: 解析失敗")
            
            debug_info = {
                "chrome_status": "✅ 成功",
                "page_title": title,
                "total_rows": len(rows),
                "sample_data": sample_data
            }
            
            logger.info("🎯 調試資訊收集完成")
            return f"<pre>{debug_info}</pre>"
            
        finally:
            driver.quit()
            logger.info("🔚 Chrome 瀏覽器已關閉")
            
    except Exception as e:
        logger.error(f"❌ 調試過程發生錯誤: {str(e)}")
        import traceback
        logger.error(f"完整錯誤追蹤:\n{traceback.format_exc()}")
        return f"<pre>❌ 錯誤: {str(e)}</pre>"

@app.route('/test-telegram')
def test_telegram():
    """測試 Telegram 推播"""
    logger.info("=== 開始執行 /test-telegram 端點 ===")
    
    try:
        logger.info("📱 正在導入 Telegram 模組...")
        from telegram_notifier import send_message
        logger.info("✅ Telegram 模組導入成功")
        
        # 發送測試訊息
        test_message = f"🧪 測試訊息\n時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n這是來自 Render 的測試推播"
        
        logger.info("📤 正在發送測試訊息...")
        success = send_message(test_message)
        
        if success:
            logger.info("✅ Telegram 測試訊息發送成功")
            return "✅ Telegram 測試成功！請查看手機"
        else:
            logger.error("❌ Telegram 測試訊息發送失敗")
            return "❌ Telegram 測試失敗"
            
    except Exception as e:
        logger.error(f"❌ Telegram 測試錯誤: {str(e)}")
        import traceback
        logger.error(f"完整錯誤追蹤:\n{traceback.format_exc()}")
        return f"❌ Telegram 錯誤: {str(e)}"

if __name__ == '__main__':
    logger.info("🚀 Surebet Bot 啟動中...")
    app.run(host='0.0.0.0', port=10000, debug=False)
