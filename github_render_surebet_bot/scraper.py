# scraper.py

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# 日誌
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 緩存設定
CACHE_DURATION = 60  # seconds
last_request_time = None
last_results = None

def create_webdriver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def extract_match_info(container):
    """從 requests + BeautifulSoup 提取比賽資訊 (備援)"""
    try:
        cells = container.find_all("td")
        if len(cells) < 7:
            return None
        match_time = cells[0].get_text(strip=True)
        teams = cells[1].get_text(strip=True).split(" - ")
        if len(teams) != 2:
            return None
        home, away = teams
        bm1, odd1 = cells[2].get_text(strip=True), cells[3].get_text(strip=True)
        bm2, odd2 = cells[4].get_text(strip=True), cells[5].get_text(strip=True)
        roi_text = cells[6].get_text(strip=True).rstrip("%")
        roi = float(roi_text)
        total_stake = 100
        profit = total_stake * roi / 100.0
        bets = [
            {"bookmaker": bm1, "odds": odd1, "stake": round(total_stake / 2, 2)},
            {"bookmaker": bm2, "odds": odd2, "stake": round(total_stake / 2, 2)},
        ]
        link = container.find("a")
        url = link["href"] if link and link.has_attr("href") else None
        return {
            "sport": "Unknown",
            "league": "Unknown",
            "home_team": home,
            "away_team": away,
            "match_time": match_time,
            "bets": bets,
            "roi": roi,
            "profit": profit,
            "url": url,
        }
    except Exception as e:
        logger.debug(f"提取比賽資訊時發生錯誤: {e}")
        return None

def scrape_with_requests():
    """備援：使用 requests + BeautifulSoup 爬取"""
    try:
        resp = requests.get("https://www.oddsportal.com/sure-bets/", timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tr")
        results = []
        for row in rows:
            info = extract_match_info(row)
            if info:
                results.append(info)
        return results
    except Exception as e:
        logger.warning(f"❌ requests 爬取失敗: {e}")
        return []

def extract_selenium_match_data(row_element):
    """從 Selenium 抓到的 <tr> 元素中提取比賽資料"""
    try:
        cells = row_element.find_elements(By.TAG_NAME, "td")
        if len(cells) < 7:
            return None
        match_time = cells[0].text.strip()
        teams = cells[1].text.strip().split(" - ")
        if len(teams) != 2:
            return None
        home, away = teams
        bm1, odd1 = cells[2].text.strip(), cells[3].text.strip()
        bm2, odd2 = cells[4].text.strip(), cells[5].text.strip()
        roi_text = cells[6].text.strip().rstrip("%")
        roi = float(roi_text)
        total_stake = 100
        profit = total_stake * roi / 100.0
        bets = [
            {"bookmaker": bm1, "odds": odd1, "stake": round(total_stake / 2, 2)},
            {"bookmaker": bm2, "odds": odd2, "stake": round(total_stake / 2, 2)},
        ]
        try:
            link = row_element.find_element(By.TAG_NAME, "a")
            url = link.get_attribute("href")
        except:
            url = None
        return {
            "sport": "Unknown",
            "league": "Unknown",
            "home_team": home,
            "away_team": away,
            "match_time": match_time,
            "bets": bets,
            "roi": roi,
            "profit": profit,
            "url": url,
        }
    except Exception as e:
        logger.debug(f"提取比賽資料時發生錯誤: {e}")
        return None

def parse_selenium_data(driver):
    bets = []
    possible_selectors = [
        "table.table-main", "[data-cy='table']", ".odds-table", ".surebet-table", "table", ".table"
    ]
    table_elements = []
    for selector in possible_selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, selector)
            if els:
                table_elements = els
                break
        except:
            continue
    if not table_elements:
        return []
    for table in table_elements:
        rows = table.find_elements(By.TAG_NAME, "tr")
        for row in rows:
            data = extract_selenium_match_data(row)
            if data:
                bets.append(data)
    return bets

def scrape_oddsportal_surebets():
    """主流程：先檢查緩存，再 fallback requests，最後 selenium"""
    global last_request_time, last_results
    now = time.time()
    if last_request_time and last_results is not None and now - last_request_time < CACHE_DURATION:
        return last_results

    # 1) requests
    results = scrape_with_requests()
    if results:
        last_request_time, last_results = now, results
        return results

    # 2) selenium
    driver = create_webdriver()
    try:
        driver.set_page_load_timeout(30)
        driver.get("https://www.oddsportal.com/sure-bets/")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(random.uniform(2, 4))
        results = parse_selenium_data(driver)
        last_request_time, last_results = now, results
        return results
    except Exception as e:
        logger.error(f"❌ Selenium 爬取失敗: {e}")
        return []
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    # 本地測試
    data = scrape_oddsportal_surebets()
    logger.info(f"測試結束，共抓到 {len(data)} 筆資料")
    for d in data:
        logger.info(d)
