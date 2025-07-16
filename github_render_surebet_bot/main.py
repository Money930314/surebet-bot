import time
import random
import logging
from datetime import datetime

import requests
from requests.exceptions import HTTPError
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# 日誌設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 緩存設定
CACHE_DURATION = 60  # seconds
data_cache = {
    "time": None,
    "results": None
}

def create_webdriver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    )
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def extract_match_info(container):
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
    """
    使用 requests 爬取，若遇到 429 Too Many Requests，直接返回空列表以便使用 Selenium
    """
    url = "https://www.oddsportal.com/sure-bets/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.oddsportal.com/",
    }
    try:
        resp = requests.get(url, timeout=15, headers=headers)
        if resp.status_code == 429:
            logger.warning("❌ requests 爬取失敗: 429 Too Many Requests，切換到 Selenium 模式")
            return []
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tr")
        results = []
        for row in rows:
            info = extract_match_info(row)
            if info:
                results.append(info)
        return results
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            logger.warning("❌ HTTPError 429，切換到 Selenium 模式")
            return []
        logger.warning(f"❌ requests 爬取失敗: {e}")
        return []
    except Exception as e:
        logger.warning(f"❌ requests 爬取失敗: {e}")
        return []


def extract_selenium_match_data(row_element):
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
    selectors = ["table.table-main", "[data-cy='table']", ".odds-table", ".surebet-table", "table"]
    for sel in selectors:
        try:
            tables = driver.find_elements(By.CSS_SELECTOR, sel)
            if tables:
                for table in tables:
                    for row in table.find_elements(By.TAG_NAME, "tr"):
                        data = extract_selenium_match_data(row)
                        if data:
                            bets.append(data)
                if bets:
                    return bets
        except Exception:
            continue
    return bets


def scrape_oddsportal_surebets():
    """
    主流程：先檢查緩存，再用 requests，最後用 Selenium
    """
    now = time.time()
    if data_cache["time"] and data_cache["results"] is not None and now - data_cache["time"] < CACHE_DURATION:
        return data_cache["results"]

    # 1) 試用 requests
    results = scrape_with_requests()
    if results:
        data_cache["time"] = now
        data_cache["results"] = results
        return results

    # 2) Selenium fallback
    driver = create_webdriver()
    try:
        driver.set_page_load_timeout(30)
        driver.get("https://www.oddsportal.com/sure-bets/")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(random.uniform(2, 4))
        results = parse_selenium_data(driver)
        data_cache["time"] = now
        data_cache["results"] = results
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
    data = scrape_oddsportal_surebets()
    logger.info(f"測試結束，共抓到 {len(data)} 筆資料")
    for d in data:
        logger.info(d)
