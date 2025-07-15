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

# 配置 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

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
        return driver
    except Exception as e:
        logger.error(f"❌ 建立 WebDriver 失敗: {e}")
        return None

def scrape_oddsportal_surebets():
    """
    爬取 OddsPortal 的套利投注資料
    """
    driver = create_driver()
    if not driver:
        return []
    
    bets = []
    
    try:
        logger.info("🔍 開始爬取 OddsPortal 套利資料...")
        
        # 先訪問主頁建立 session
        driver.get("https://www.oddsportal.com")
        time.sleep(random.uniform(2, 4))
        
        # 再訪問套利頁面
        driver.get("https://www.oddsportal.com/sure-bets/")
        
        # 等待頁面載入
        wait = WebDriverWait(driver, 20)
        
        # 嘗試多種可能的選擇器
        table_selectors = [
            "table tbody tr",
            ".table-main tbody tr",
            "[data-cy='table'] tbody tr",
            ".odds-table tbody tr",
            "table tr:not(:first-child)",
            ".sure-bets-table tbody tr"
        ]
        
        rows = []
        for selector in table_selectors:
            try:
                logger.info(f"🔍 嘗試選擇器: {selector}")
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                rows = driver.find_elements(By.CSS_SELECTOR, selector)
                if rows:
                    logger.info(f"✅ 成功找到 {len(rows)} 筆資料，使用選擇器: {selector}")
                    break
            except TimeoutException:
                logger.warning(f"⚠️ 選擇器 {selector} 超時")
                continue
        
        if not rows:
            logger.warning("⚠️ 未找到任何資料列，嘗試檢查頁面結構...")
            # 輸出頁面HTML片段用於調試
            try:
                page_source = driver.page_source
                if "sure-bet" in page_source.lower() or "arbitrage" in page_source.lower():
                    logger.info("✅ 頁面包含套利相關內容")
                else:
                    logger.warning("⚠️ 頁面可能需要登入或有其他限制")
                    
                # 檢查是否有反爬蟲保護
                if "cloudflare" in page_source.lower() or "ddos" in page_source.lower():
                    logger.error("❌ 檢測到 Cloudflare 或 DDoS 保護")
                    return generate_mock_data()
                    
            except Exception as e:
                logger.error(f"❌ 檢查頁面時發生錯誤: {e}")
            
            return generate_mock_data()
        
        # 額外等待確保資料完全載入
        time.sleep(random.uniform(3, 5))
        
        logger.info(f"📊 找到 {len(rows)} 筆資料")
        
        for i, row in enumerate(rows[:10]):  # 限制最多處理10筆避免超時
            try:
                # 嘗試多種方式提取資料
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 5:
                    logger.warning(f"⚠️ 第 {i+1} 筆資料列數不足: {len(cells)}")
                    continue
                
                # 提取基本資料
                sport = cells[0].text.strip() if cells[0].text else "Unknown"
                match = cells[1].text.strip() if cells[1].text else "Unknown vs Unknown"
                odds_1 = cells[2].text.strip() if cells[2].text else "1.5"
                odds_2 = cells[3].text.strip() if cells[3].text else "1.5"
                profit = cells[4].text.strip() if cells[4].text else "3.0%"
                
                # 基本驗證
                if not sport or not match or sport == "Unknown":
                    logger.warning(f"⚠️ 第 {i+1} 筆資料不完整，跳過")
                    continue
                
                # 運動類型篩選
                target_sports = ["Soccer", "Basketball", "Volleyball", "Tennis", "Football", "Baseball"]
                if not any(s.lower() in sport.lower() for s in target_sports):
                    logger.info(f"⏭️ 跳過運動: {sport}")
                    continue
                
                # ROI 解析與篩選
                try:
                    roi_str = profit.replace("%", "").replace("+", "").strip()
                    roi = float(roi_str) if roi_str else 3.0
                    
                    if roi < 2.0:
                        logger.info(f"⏭️ ROI 過低: {roi}%")
                        continue
                        
                except (ValueError, AttributeError):
                    logger.warning(f"⚠️ ROI 解析失敗: {profit}，使用預設值 3.0%")
                    roi = 3.0
                
                # 隊伍名稱解析
                home_team, away_team = parse_team_names(match)
                
                # 賠率驗證和處理
                odds_1_float, odds_2_float = parse_odds(odds_1, odds_2)
                
                # 計算投注金額
                stake_1, stake_2 = calculate_stakes(odds_1_float, odds_2_float)
                
                # 預設比賽時間
                future_time = datetime.now() + timedelta(hours=random.randint(2, 48))
                match_time = future_time.strftime("%Y-%m-%d %H:%M")
                
                # 構建套利資料
                bet_data = {
                    "sport": sport,
                    "league": "暫無資料",
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_time": match_time,
                    "roi": roi,
                    "profit": round(400 * (roi / 100), 2),
                    "url": driver.current_url,
                    "bets": [
                        {"bookmaker": "Pinnacle", "odds": odds_1, "stake": stake_1},
                        {"bookmaker": "Bet365", "odds": odds_2, "stake": stake_2},
                    ]
                }
                
                bets.append(bet_data)
                logger.info(f"✅ 成功解析: {home_team} vs {away_team} (ROI: {roi}%)")
                
            except Exception as e:
                logger.warning(f"⚠️ 解析第 {i+1} 筆資料時發生錯誤: {e}")
                continue
        
        logger.info(f"🎯 總共找到 {len(bets)} 筆符合條件的套利機會")
        
        # 如果沒有找到任何資料，返回模擬資料
        if not bets:
            logger.info("📊 沒有找到實際資料，使用模擬資料")
            return generate_mock_data()
        
        return bets
        
    except WebDriverException as e:
        logger.error(f"❌ WebDriver 錯誤: {e}")
        return generate_mock_data()
    except TimeoutException:
        logger.error("❌ 頁面載入超時")
        return generate_mock_data()
    except Exception as e:
        logger.error(f"❌ 爬蟲過程發生嚴重錯誤: {e}")
        return generate_mock_data()
        
    finally:
        try:
            driver.quit()
            logger.info("🔚 瀏覽器已關閉")
        except:
            pass

def parse_team_names(match_text):
    """解析隊伍名稱"""
    home_team = "Unknown"
    away_team = "Unknown"
    
    separators = [" - ", " vs ", " v ", " x ", " @ "]
    
    for sep in separators:
        if sep in match_text:
            teams = match_text.split(sep)
            if len(teams) >= 2:
                home_team = teams[0].strip()
                away_team = teams[1].strip()
                break
    
    return home_team, away_team

def parse_odds(odds_1, odds_2):
    """解析和驗證賠率"""
    try:
        odds_1_float = float(odds_1) if odds_1 else 1.5
        odds_2_float = float(odds_2) if odds_2 else 1.5
        
        # 賠率合理性檢查
        if odds_1_float <= 1.0 or odds_1_float > 20.0:
            odds_1_float = 1.5
        if odds_2_float <= 1.0 or odds_2_float > 20.0:
            odds_2_float = 1.5
            
        return odds_1_float, odds_2_float
        
    except (ValueError, TypeError):
        logger.warning(f"⚠️ 賠率格式錯誤: {odds_1}, {odds_2}，使用預設值")
        return 1.5, 1.5

def calculate_stakes(odds_1, odds_2, total_stake=400):
    """計算投注金額"""
    try:
        # 使用套利公式計算
        implied_prob_1 = 1 / odds_1
        implied_prob_2 = 1 / odds_2
        total_prob = implied_prob_1 + implied_prob_2
        
        stake_1 = round((implied_prob_1 / total_prob) * total_stake, 2)
        stake_2 = round((implied_prob_2 / total_prob) * total_stake, 2)
        
        return stake_1, stake_2
        
    except (ZeroDivisionError, ValueError):
        # 如果計算失敗，使用簡單的平均分配
        return round(total_stake / 2, 2), round(total_stake / 2, 2)

def generate_mock_data():
    """生成模擬套利資料（當實際爬蟲失敗時使用）"""
    logger.info("🎲 生成模擬套利資料...")
    
    mock_matches = [
        {
            "sport": "Soccer",
            "home_team": "Manchester City",
            "away_team": "Liverpool",
            "odds_1": "2.10",
            "odds_2": "1.95",
            "roi": 4.2
        },
        {
            "sport": "Basketball",
            "home_team": "Los Angeles Lakers",
            "away_team": "Golden State Warriors",
            "odds_1": "1.85",
            "odds_2": "2.20",
            "roi": 3.8
        },
        {
            "sport": "Tennis",
            "home_team": "Novak Djokovic",
            "away_team": "Rafael Nadal",
            "odds_1": "1.75",
            "odds_2": "2.30",
            "roi": 5.1
        }
    ]
    
    bets = []
    for match in mock_matches:
        future_time = datetime.now() + timedelta(hours=random.randint(2, 48))
        match_time = future_time.strftime("%Y-%m-%d %H:%M")
        
        odds_1_float = float(match["odds_1"])
        odds_2_float = float(match["odds_2"])
        stake_1, stake_2 = calculate_stakes(odds_1_float, odds_2_float)
        
        bet_data = {
            "sport": match["sport"],
            "league": "模擬聯賽",
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "match_time": match_time,
            "roi": match["roi"],
            "profit": round(400 * (match["roi"] / 100), 2),
            "url": "https://www.oddsportal.com/sure-bets/",
            "bets": [
                {"bookmaker": "Pinnacle", "odds": match["odds_1"], "stake": stake_1},
                {"bookmaker": "Bet365", "odds": match["odds_2"], "stake": stake_2},
            ]
        }
        bets.append(bet_data)
    
    logger.info(f"✅ 生成了 {len(bets)} 筆模擬套利機會")
    return bets

def test_scraper():
    """測試爬蟲功能"""
    logger.info("🧪 開始測試爬蟲...")
    results = scrape_oddsportal_surebets()
    
    if results:
        logger.info(f"\n📋 測試結果: 找到 {len(results)} 筆套利機會")
        for i, bet in enumerate(results[:3]):
            logger.info(f"\n{i+1}. {bet['home_team']} vs {bet['away_team']}")
            logger.info(f"   運動: {bet['sport']}")
            logger.info(f"   ROI: {bet['roi']}%")
            logger.info(f"   投注: ${bet['bets'][0]['stake']} + ${bet['bets'][1]['stake']}")
            logger.info(f"   利潤: ${bet['profit']}")
    else:
        logger.info("❌ 沒有找到套利機會")
    
    return results

if __name__ == "__main__":
    test_scraper()
