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

FRIENDLY_BOOKMAKERS = [
    "pinnacle",       # Pinnacle Sports
    "betfair_ex",    # Betfair Exchange
    "smarkets",      # Smarkets Exchange
]

MARKET_KEY = "h2h"  # 2‑way moneyline

DEFAULT_SPORTS = [
    "basketball_nba",
    "basketball_euroleague",
    "soccer_epl",
    "soccer_uefa_champs_league",
]

CACHE_SECONDS = 30
_cache: Dict[str, Any] = {"time": 0, "results": []}

def _call_odds_api(endpoint: str, params: Dict[str, Any]) -> Any:
    url = f"{BASE_URL}{endpoint}"
    params["apiKey"] = API_KEY
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            logger.debug("%s %s", endpoint, e.response.json().get("message"))
        else:
            logger.error("HTTPError %s: %.200s", e.response.status_code, e.response.text)
        return None
    except requests.RequestException as e:
        logger.error("RequestException: %s", e)
        return None

def _calc_two_way_surebet(odds_a: float, odds_b: float) -> float:
    inv_sum = 1 / odds_a + 1 / odds_b
    if inv_sum >= 1:
        return -1
    return round((1 / inv_sum - 1) * 100, 2)

def _stake_split(total: float, odds_a: float, odds_b: float):
    inv_sum = 1 / odds_a + 1 / odds_b
    stake_a = total / (odds_a * inv_sum)
    stake_b = total / (odds_b * inv_sum)
    return round(stake_a, 2), round(stake_b, 2)

def fetch_surebets(sports: List[str] | None = None, min_roi: float = 0.5):
    if sports is None:
        sports = DEFAULT_SPORTS
    now = time.time()
    if now - _cache["time"] < CACHE_SECONDS:
        return _cache["results"]
    surebets: List[Dict[str, Any]] = []
    for sport in sports:
        params = {
            "regions": "eu",
            "markets": MARKET_KEY,
            "oddsFormat": "decimal",
            "bookmakers": ",".join(FRIENDLY_BOOKMAKERS),
        }
        data = _call_odds_api(f"/sports/{sport}/odds", params)
        if not data:
            continue
        for event in data:
            best_odds: Dict[str, Dict[str, Any]] = {}
            for bm in event.get("bookmakers", []):
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
                continue
            teams = list(best_odds.keys())
            odds_a = best_odds[teams[0]]["price"]
            odds_b = best_odds[teams[1]]["price"]
            roi = _calc_two_way_surebet(odds_a, odds_b)
            if roi < min_roi:
                continue
            stake_a, stake_b = _stake_split(100, odds_a, odds_b)
            surebets.append({
                "home_team": event.get("home_team"),
                "away_team": event.get("away_team"),
                "sport": event.get("sport_title", sport),
                "league": event.get("sport_key", sport),
                "match_time": event.get("commence_time"),
                "roi": roi,
                "profit": round(100 * roi / 100, 2),
                "bets": [
                    {"bookmaker": best_odds[teams[0]]["bookmaker"], "odds": odds_a, "stake": stake_a},
                    {"bookmaker": best_odds[teams[1]]["bookmaker"], "odds": odds_b, "stake": stake_b},
                ],
            })
    surebets.sort(key=lambda x: x["roi"], reverse=True)
    _cache["time"] = now
    _cache["results"] = surebets
    return surebets

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(fetch_surebets()[:3])
