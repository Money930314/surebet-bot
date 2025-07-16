"""scraper.py – call The Odds API, compute surebet list."""
import os
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

API_KEY = os.getenv("THE_ODDS_API_KEY", "e9c7f8945b8fcab5d904fc7f6ef6c2da")
BASE_URL = "https://api.the-odds-api.com/v4"

FRIENDLY_BOOKMAKERS = ["pinnacle", "betfair_ex", "smarkets"]
DEFAULT_SPORTS = [
    "basketball_nba",
    "tennis_atp",
    "volleyball_world",
    "soccer_epl",
    "baseball_mlb",
]
MARKET_KEY = "h2h"

CACHE_SECONDS = 30
_cache: Dict[str, Any] = {"time": 0, "params": {}, "results": []}

# ------------- helpers ------------------

def _call(endpoint: str, params: Dict[str, Any]):
    params["apiKey"] = API_KEY
    url = f"{BASE_URL}{endpoint}"
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logger.error("Odds API error: %s", e)
        return None

def _calc_roi(o1: float, o2: float) -> float:
    inv_sum = 1 / o1 + 1 / o2
    if inv_sum >= 1:
        return -1
    return round((1 / inv_sum - 1) * 100, 2)

def _stake_split(total: float, o1: float, o2: float):
    inv_sum = 1 / o1 + 1 / o2
    return round(total / (o1 * inv_sum), 2), round(total / (o2 * inv_sum), 2)

# ------------- main ----------------------

def fetch_surebets(
    sports: Optional[List[str]] = None,
    min_roi: float = 0.0,
    total_stake: float = 100.0,
    days_window: int = 2,
):
    """Return list of surebets filtered by roi and commence_time (tomorrow~+days_window)."""
    if sports is None:
        sports = DEFAULT_SPORTS

    # cache key
    key = (tuple(sorted(sports)), min_roi, total_stake, days_window)
    now = time.time()
    if key == _cache.get("params") and now - _cache["time"] < CACHE_SECONDS:
        return _cache["results"]

    start = datetime.now(timezone.utc).date() + timedelta(days=1)
    end = start + timedelta(days=days_window - 1)

    results: List[Dict[str, Any]] = []
    for sport in sports:
        data = _call(
            f"/sports/{sport}/odds",
            {
                "regions": "eu",
                "markets": MARKET_KEY,
                "oddsFormat": "decimal",
                "bookmakers": ",".join(FRIENDLY_BOOKMAKERS),
            },
        )
        if not data:
            continue
        for ev in data:
            comm = ev.get("commence_time")
            try:
                comm_dt = datetime.fromisoformat(comm.replace("Z", "+00:00"))
            except Exception:
                continue
            if not (start <= comm_dt.date() <= end):
                continue
            best: Dict[str, Dict[str, Any]] = {}
            for bm in ev.get("bookmakers", []):
                title = bm.get("title")
                for m in bm.get("markets", []):
                    if m.get("key") != MARKET_KEY:
                        continue
                    for out in m.get("outcomes", []):
                        name = out.get("name")
                        price = out.get("price")
                        if name not in best or price > best[name]["price"]:
                            best[name] = {"price": price, "bookmaker": title}
            if len(best) < 2:
                continue
            teams = list(best.keys())
            o1, o2 = best[teams[0]]["price"], best[teams[1]]["price"]
            roi = _calc_roi(o1, o2)
            if roi < min_roi:
                continue
            s1, s2 = _stake_split(total_stake, o1, o2)
            results.append(
                {
                    "sport": ev.get("sport_title", sport),
                    "league": ev.get("sport_key", sport),
                    "home_team": ev.get("home_team"),
                    "away_team": ev.get("away_team"),
                    "match_time": comm,
                    "bets": [
                        {"bookmaker": best[teams[0]]["bookmaker"], "odds": o1, "stake": s1},
                        {"bookmaker": best[teams[1]]["bookmaker"], "odds": o2, "stake": s2},
                    ],
                    "roi": roi,
                    "profit": round(total_stake * roi / 100, 2),
                    "url": f"https://the-odds-api.com/event/{ev.get('id')}" if ev.get("id") else None,
                }
            )
    results.sort(key=lambda x: x["roi"], reverse=True)
    _cache["time"] = now
    _cache["params"] = key
    _cache["results"] = results
    return results

# quick test
if __name__ == "__main__":
    print(fetch_surebets(total_stake=200)[:2])
