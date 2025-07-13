from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

def scrape_oddsportal_surebets():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.get("https://www.oddsportal.com/sure-bets/")
        time.sleep(5)
        bets = []
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            try:
                sport = row.find_element(By.CSS_SELECTOR, "td:nth-child(1)").text.strip()
                if not any(s in sport for s in ["Soccer", "Basketball", "Volleyball", "Tennis"]):
                    continue
                match = row.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text.strip()
                odds_1 = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)").text.strip()
                odds_2 = row.find_element(By.CSS_SELECTOR, "td:nth-child(4)").text.strip()
                profit = row.find_element(By.CSS_SELECTOR, "td:nth-child(5)").text.strip()
                bets.append({
                    "sport": sport,
                    "match": match,
                    "odds": [odds_1, odds_2],
                    "profit": profit
                })
            except:
                continue
        return bets
    finally:
        driver.quit()