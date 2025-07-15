from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import time
from datetime import datetime, timedelta
import logging
import sys
import random
import requests
from bs4 import BeautifulSoup
import re

# 配置 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 全局變量來跟蹤上次請求時間和結果
last_request_time = None
last_results = None
CACHE_DURATION = 300  # 5分鐘緩存

def create_driver():
    """建立 Chrome WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # 添加 User-Agent 避免被識別為機器人
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        # 隱藏 webdriver 特徵
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logger.info("✅ WebDriver 創建成功")
        return driver
    except Exception as e:
        logger.error(f"❌ 建立 WebDriver 失敗: {e}")
        return None

def scrape_with_requests():
    """使用 requests 嘗試爬取資料"""
    logger.info("🔄 嘗試使用 requests 爬取資料...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        # 嘗試訪問 OddsPortal 主頁
        session = requests.Session()
        session.headers.update(headers)
        
        response = session.get("https://www.oddsportal.com/", timeout=10)
        if response.status_code != 200:
            logger.warning(f"⚠️ 主頁訪問失敗: {response.status_code}")
            return []
        
        # 嘗試訪問套利頁面
        response = session.get("https://www.oddsportal.com/sure-bets/", timeout=10)
        if response.status_code != 200:
            logger.warning(f"⚠️ 套利頁面訪問失敗: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 檢查是否有反爬蟲保護
        page_content = response.text.lower()
        if any(keyword in page_content for keyword in ['cloudflare', 'ddos', 'bot detection', 'access denied', 'blocked']):
            logger.warning("⚠️ 檢測到反爬蟲保護 (requests)")
            return []
        
        # 嘗試解析套利資料
        return parse_surebet_data(soup)
            
    except requests.RequestException as e:
        logger.error(f"❌ requests 爬取失敗: {e}")
        return []

def parse_surebet_data(soup):
    """解析套利資料"""
    bets = []
    
    try:
        # 嘗試找到套利資料表格或容器
        # 這裡需要根據實際網站結構來調整選擇器
        surebet_containers = soup.find_all(['div', 'table', 'tr'], class_=re.compile(r'sure|bet|arbitrage', re.I))
        
        if not surebet_containers:
            logger.info("❌ 未找到套利資料容器")
            return []
        
        for container in surebet_containers:
            try:
                # 嘗試提取比賽資訊
                match_info = extract_match_info(container)
                if match_info:
                    bets.append(match_info)
            except Exception as e:
                logger.debug(f"解析容器時發生錯誤: {e}")
                continue
        
        logger.info(f"✅ 成功解析 {len(bets)} 筆套利資料")
        return bets
        
    except Exception as e:
        logger.error(f"❌ 解析套利資料時發生錯誤: {e}")
        return []

def extract_match_info(container):
    """從容器中提取比賽資訊"""
    try:
        # 這裡需要根據實際的HTML結構來實現
        # 目前返回 None 表示無法提取
        return None
    except Exception as e:
        logger.debug(f"提取比賽資訊時發生錯誤: {e}")
        return None

def scrape_oddsportal_surebets():
    """
    爬取 OddsPortal 的套利投注資料 - 只返回真實資料
    """
    global last_request_time, last_results
    
    # 檢查緩存
    current_time = time.time()
    if (last_request_time and last_results is not None and 
        current_time - last_request_time < CACHE_DURATION):
        logger.info("📦 使用緩存資料")
        return last_results
    
    # 首先嘗試使用 requests
    results = scrape_with_requests()
    if results:
        logger.info("✅ requests 爬取成功")
        last_request_time = current_time
        last_results = results
        return results
    
    # 如果 requests 失敗，嘗試 Selenium
    driver = create_driver()
    if not driver:
        logger.error("❌ 無法創建 WebDriver")
        # 更新緩存為空結果
        last_request_time = current_time
        last_results = []
        return []
    
    bets = []
    
    try:
        logger.info("🔍 開始使用 Selenium 爬取 OddsPortal 套利資料...")
        
        # 設置頁面載入超時
        driver.set_page_load_timeout(30)
        
        # 先訪問主頁建立 session
        logger.info("🌐 訪問 OddsPortal 主頁...")
        driver.get("https://www.oddsportal.com")
        time.sleep(random.uniform(2, 4))
        
        # 再訪問套利頁面
        logger.info("🌐 訪問套利頁面...")
        driver.get("https://www.oddsportal.com/sure-bets/")
        
        # 等待頁面載入
        wait = WebDriverWait(driver, 20)
        
        # 檢查頁面是否正常載入
        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            logger.info("✅ 頁面載入完成")
        except TimeoutException:
            logger.error("❌ 頁面載入超時")
            last_request_time = current_time
            last_results = []
            return []
        
        # 檢查是否有反爬蟲保護
        page_source = driver.page_source.lower()
        if any(keyword in page_source for keyword in ['cloudflare', 'ddos', 'bot detection', 'access denied', 'blocked']):
            logger.warning("⚠️ 檢測到反爬蟲保護 (Selenium)")
            last_request_time = current_time
            last_results = []
            return []
        
        # 嘗試解析套利資料
        bets = parse_selenium_data(driver)
        
        if not bets:
            logger.info("❌ 未找到套利資料")
            last_request_time = current_time
            last_results = []
            return []
        
        logger.info(f"✅ 成功爬取 {len(bets)} 筆套利資料")
        last_request_time = current_time
        last_results = bets
        return bets
        
    except WebDriverException as e:
        logger.error(f"❌ WebDriver 錯誤: {e}")
        last_request_time = current_time
        last_results = []
        return []
    except TimeoutException:
        logger.error("❌ 頁面載入超時")
        last_request_time = current_time
        last_results = []
        return []
    except Exception as e:
        logger.error(f"❌ 爬蟲過程發生錯誤: {e}")
        last_request_time = current_time
        last_results = []
        return []
        
    finally:
        try:
            if driver:
                driver.quit()
                logger.info("🔚 WebDriver 已關閉")
        except Exception as e:
            logger.error(f"❌ 關閉 WebDriver 時發生錯誤: {e}")

def parse_selenium_data(driver):
    """使用 Selenium 解析套利資料"""
    bets = []
    
    try:
        # 嘗試找到套利資料表格
        # 這裡需要根據實際的網站結構來調整選擇器
        possible_selectors = [
            "table.table-main",
            "[data-cy='table']",
            ".odds-table",
            ".surebet-table",
            "table",
            ".table"
        ]
        
        table_elements = []
        for selector in possible_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    table_elements.extend(elements)
                    logger.info(f"✅ 找到表格元素: {selector}")
                    break
            except Exception as e:
                logger.debug(f"選擇器 {selector} 失敗: {e}")
                continue
        
        if not table_elements:
            logger.warning("⚠️ 未找到資料表格")
            return []
        
        # 嘗試解析表格資料
        for table in table_elements:
            try:
                rows = table.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    match_data = extract_selenium_match_data(row)
                    if match_data:
                        bets.append(match_data)
            except Exception as e:
                logger.debug(f"解析表格時發生錯誤: {e}")
                continue
        
        return bets
        
    except Exception as e:
        logger.error(f"❌ 使用 Selenium 解析資料時發生錯誤: {e}")
        return []

def extract_selenium_match_data(row_element):
    """從表格行中提取比賽資料"""
    try:
        # 這裡需要根據實際的HTML結構來實現
        # 目前返回 None 表示無法提取
        return None
    except Exception as e:
        logger.debug(f"提取比賽資料時發生錯誤: {e}")
        return None

def clear_cache():
    """清除緩存"""
    global last_request_time, last_results
    last_request_time = None
    last_results = None
    logger.info("🧹 緩存已清除")

def test_scraper():
    """測試爬蟲功能"""
    logger.info("🧪 開始測試爬蟲...")
    
    # 清除緩存確保獲取新資料
    clear_cache()
    
    results = scrape_oddsportal_surebets()
    
    if results:
        logger.info(f"\n📋 測試結果: 找到 {len(results)} 筆套利機會")
        for i, bet in enumerate(results):
            logger.info(f"\n{i+1}. {bet.get('sport', 'Unknown')} - {bet.get('league', 'Unknown')}")
            logger.info(f"   比賽: {bet.get('home_team', 'Unknown')} vs {bet.get('away_team', 'Unknown')}")
            logger.info(f"   時間: {bet.get('match_time', 'Unknown')}")
            logger.info(f"   ROI: {bet.get('roi', 'Unknown')}%")
            logger.info(f"   利潤: ${bet.get('profit', 'Unknown')}")
    else:
        logger.info("❌ 沒有找到套利機會")
    
    return results

if __name__ == "__main__":
    test_scraper()
