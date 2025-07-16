"""scraper.py
改版：改用 The Odds API 取代爬蟲，並計算 surebet（雙邊賠率套利）。
"""
import os
import time
import logging
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv

# --------------------------------------------------
# 設定與常數
# --------------------------------------------------
load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

API_KEY = os.getenv("THE_ODDS_API_KEY", "e9c7f8945b8fcab5d904fc7f6ef6c2da")
BASE_URL = "https://api.the-odds-api.com/v4"

# 對套利玩家相對友善的莊家（bookmaker key 取自 The Odds API 文件）
FRIENDLY_BOOKMAKERS = [
    "pinnacle",       # Pinnacle Sports
    "betfair_ex",    # Betfair Exchange
    "smarkets"       # Smarkets Exchange
]

# 只抓 2-way moneyline 市場，因為三向 (1X2) 計算方式不同，可以之後擴充
MARKET_KEY = "h2h"  # head-to-head / moneyline

# 只抓最常見的幾個運動，可再自行擴充
DEFAULT_SPORTS = [
    "basketball_nba",
    "basketball_euroleague",
    "soccer_epl",
    "tennis_atp",
]

# Cache 設定（秒）
CACHE_SECONDS = 30
_cache: Dict[str, Any] = {"time": 0, "results": []}

def _call_odds_api(endpoint: str, params: Dict[str, Any]) -> Any:
    """包裝 GET 請求，處理錯誤與日誌"""
    url = f"{BASE_URL}{endpoint}"
    params["apiKey"] = API_KEY
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        logger.error(f"HTTPError {e.response.status_code}: {e.response.text[:200]}")
        return None
    except requests.RequestException as e:
        logger.error(f"RequestException: {e}")
        return None

def _calc_two_way_surebet(odds_a: float, odds_b: float) -> float:
    """return ROI 百分比 (正值代表有 surebet)"""
    inv_sum = 1 / odds_a + 1 / odds_b
    if inv_sum >= 1:
        return -1  # 無套利
    roi = (1 / inv_sum - 1) * 100
    return round(roi, 2)

def _stake_split(total: float, odds_a: float, odds_b: float) -> (float, float):
    inv_sum = 1 / odds_a + 1 / odds_b
    stake_a = total / (odds_a * inv_sum)
    stake_b = total / (odds_b * inv_sum)
    return round(stake_a, 2), round(stake_b, 2)

def fetch_surebets(sports: List[str] = None, min_roi: float = 0.5) -> List[Dict[str, Any]]:
    """向 The Odds API 取資料並回傳 surebet list"""
    if sports is None:
        sports = DEFAULT_SPORTS

    # 使用簡易快取避免超過配額
    now = time.time()
    if now - _cache["time"] < CACHE_SECONDS:
        return _cache["results"]

    surebets: List[Dict[str, Any]] = []
    for sport in sports:
        params = {
            "regions": "eu",  # 歐洲盤口時區
            "markets": MARKET_KEY,
            "oddsFormat": "decimal",
            "bookmakers": ",".join(FRIENDLY_BOOKMAKERS),
        }
        data = _call_odds_api(f"/sports/{sport}/odds", params)
        if not data:
            continue

        for event in data:
            event_id = event.get("id")
            commence_time = event.get("commence_time")
            home, away = event.get("home_team"), event.get("away_team")
            # 蒐集每個 outcome 在不同 bookmaker 的最佳賠率
            best_odds: Dict[str, Dict[str, Any]] = {}
            for bm in event.get("bookmakers", [])
:
                bm_key = bm.get("key")
                bm_title = bm.get("title")
                for market in bm.get("markets", []):
                    if market.get("key") != MARKET_KEY:
                        continue
                    for outcome in market.get("outcomes", []):
                        name = outcome.get("name")
                        price = outcome.get("price")
                        if name not in best_odds or price > best_odds[name]["price"]:
                            best_odds[name] = {"price": price, "bookmaker": bm_title}
            if len(best_odds) < 2:
                continue  # 不是二選一市場
            # 假設第一個是主隊，第二個是客隊
            teams = list(best_odds.keys())
            odds_a = best_odds[teams[0]]["price"]
            odds_b = best_odds[teams[1]]["price"]
            roi = _calc_two_way_surebet(odds_a, odds_b)
            if roi < min_roi:
                continue
            stake_a, stake_b = _stake_split(100, odds_a, odds_b)
            surebets.append({
                "sport": event.get("sport_title", sport),
                "league": event.get("sport_key", sport),
                "home_team": home,
                "away_team": away,
                "match_time": commence_time,
                "bets": [
                    {"bookmaker": best_odds[teams[0]]["bookmaker"], "odds": odds_a, "stake": stake_a},
                    {"bookmaker": best_odds[teams[1]]["bookmaker"], "odds": odds_b, "stake": stake_b},
                ],
                "roi": roi,
                "profit": round(100 * roi / 100, 2),
                "url": f"https://the-odds-api.com/event/{event_id}" if event_id else None,
            })
    # 依 ROI 排序
    surebets.sort(key=lambda x: x["roi"], reverse=True)
    # 更新 cache
    _cache["time"] = now
    _cache["results"] = surebets
    return surebets

# 允許 CLI 測試
if __name__ == "__main__":
    bets = fetch_surebets()
    logger.info("抓到 %d 筆 surebet", len(bets))
    if bets:
        logger.info(bets[0])
