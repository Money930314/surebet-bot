from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime, timedelta
import logging

def scrape_oddsportal_surebets():
    """
    爬取 OddsPortal 的套利投注資料
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)
    bets = []
    
    try:
        print("🔍 開始爬取 OddsPortal 套利資料...")
        driver.get("https://www.oddsportal.com/sure-bets/")
        
        # 使用 WebDriverWait 等待頁面載入
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr")))
        
        # 額外等待確保資料完全載入
        time.sleep(3)
        
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        print(f"📊 找到 {len(rows)} 筆資料")
        
        for i, row in enumerate(rows):
            try:
                # 1. 提取基本資料
                sport_element = row.find_element(By.CSS_SELECTOR, "td:nth-child(1)")
                match_element = row.find_element(By.CSS_SELECTOR, "td:nth-child(2)")
                odds_1_element = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)")
                odds_2_element = row.find_element(By.CSS_SELECTOR, "td:nth-child(4)")
                profit_element = row.find_element(By.CSS_SELECTOR, "td:nth-child(5)")
                
                sport = sport_element.text.strip()
                match = match_element.text.strip()
                odds_1 = odds_1_element.text.strip()
                odds_2 = odds_2_element.text.strip()
                profit = profit_element.text.strip()
                
                # 2. 運動類型篩選
                target_sports = ["Soccer", "Basketball", "Volleyball", "Tennis", "Football"]
                if not any(s.lower() in sport.lower() for s in target_sports):
                    print(f"⏭️  跳過運動: {sport}")
                    continue
                
                # 3. ROI 解析與篩選
                try:
                    roi_str = profit.replace("%", "").replace("+", "").strip()
                    roi = float(roi_str)
                    
                    # 修正：ROI 需要 >= 10%
                    if roi < 10.0:
                        print(f"⏭️  ROI 過低: {roi}%")
                        continue
                        
                except (ValueError, AttributeError) as e:
                    print(f"⚠️  ROI 解析失敗: {profit} - {e}")
                    continue
                
                # 4. 隊伍名稱解析
                home_team = "Unknown"
                away_team = "Unknown"
                
                if " - " in match:
                    teams = match.split(" - ")
                    if len(teams) >= 2:
                        home_team = teams[0].strip()
                        away_team = teams[1].strip()
                elif " vs " in match:
                    teams = match.split(" vs ")
                    if len(teams) >= 2:
                        home_team = teams[0].strip()
                        away_team = teams[1].strip()
                else:
                    # 嘗試其他分隔符
                    for sep in [" x ", " @ ", " v "]:
                        if sep in match:
                            teams = match.split(sep)
                            if len(teams) >= 2:
                                home_team = teams[0].strip()
                                away_team = teams[1].strip()
                                break
                
                # 5. 賠率驗證
                try:
                    odds_1_float = float(odds_1)
                    odds_2_float = float(odds_2)
                    
                    if odds_1_float <= 1.0 or odds_2_float <= 1.0:
                        print(f"⚠️  賠率異常: {odds_1}, {odds_2}")
                        continue
                        
                except (ValueError, TypeError):
                    print(f"⚠️  賠率格式錯誤: {odds_1}, {odds_2}")
                    continue
                
                # 6. 計算投注金額（總投注上限 $400）
                total_stake = 400
                # 簡化計算：按賠率反比分配
                odds_sum = odds_1_float + odds_2_float
                stake_1 = round((odds_2_float / odds_sum) * total_stake, 2)
                stake_2 = round((odds_1_float / odds_sum) * total_stake, 2)
                
                # 7. 預設比賽時間（未來 24 小時後）
                future_time = datetime.now() + timedelta(days=1)
                match_time = future_time.strftime("%Y-%m-%d %H:%M")
                
                # 8. 構建套利資料
                bet_data = {
                    "sport": sport,
                    "league": "暫無資料",
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_time": match_time,
                    "roi": roi,
                    "profit": round(total_stake * (roi / 100), 2),  # 實際預期利潤
                    "url": driver.current_url,
                    "bets": [
                        {"bookmaker": "Pinnacle", "odds": odds_1, "stake": stake_1},
                        {"bookmaker": "BetInAsia", "odds": odds_2, "stake": stake_2},
                    ]
                }
                
                bets.append(bet_data)
                print(f"✅ 成功解析: {home_team} vs {away_team} (ROI: {roi}%)")
                
            except Exception as e:
                print(f"⚠️  解析第 {i+1} 筆資料時發生錯誤: {e}")
                continue
        
        print(f"🎯 總共找到 {len(bets)} 筆符合條件的套利機會")
        return bets
        
    except Exception as e:
        print(f"❌ 爬蟲過程發生嚴重錯誤: {e}")
        return []
        
    finally:
        driver.quit()
        print("🔚 瀏覽器已關閉")

# 測試用函數
def test_scraper():
    """
    測試爬蟲功能
    """
    results = scrape_oddsportal_surebets()
    
    if results:
        print(f"\n📋 測試結果: 找到 {len(results)} 筆套利機會")
        for i, bet in enumerate(results[:3]):  # 只顯示前 3 筆
            print(f"\n{i+1}. {bet['home_team']} vs {bet['away_team']}")
            print(f"   運動: {bet['sport']}")
            print(f"   ROI: {bet['roi']}%")
            print(f"   投注: {bet['bets'][0]['stake']} + {bet['bets'][1]['stake']} = {bet['bets'][0]['stake'] + bet['bets'][1]['stake']}")
    else:
        print("❌ 沒有找到套利機會")

if __name__ == "__main__":
    test_scraper()
