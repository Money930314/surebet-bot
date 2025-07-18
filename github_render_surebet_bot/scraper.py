# -*- coding: utf-8 -*-
"""
scraper.py  ─ 掃描 6 個熱門聯盟，回傳 ROI 最高且最近開賽的 5 筆 surebet
"""

from __future__ import annotations
import os, time, logging, datetime as _dt, requests

logger = logging.getLogger("scraper")
API_KEY = os.getenv("THE_ODDS_API_KEY", "").strip()

# 追蹤聯盟（全年分布）
TRACKED_SPORT_KEYS = [
    "soccer_epl", "basketball_nba", "baseball_mlb",
    "icehockey_nhl", "tennis_atp", "americanfootball_nfl",
]
SPORT_TITLES = {
    "soccer_epl": "英超足球",
    "basketball_nba": "NBA 籃球",
    "baseball_mlb": "MLB 棒球",
    "icehockey_nhl": "NHL 冰球",
    "tennis_atp": "ATP 網球",
    "americanfootball_nfl": "NFL 美式足球",
}

FRIENDLY_BOOKMAKERS = {
    "pinnacle", "betfair_ex", "smarkets",
    "bet365", "williamhill", "unibet",
    "betfair", "ladbrokes", "marathonbet",
}

# -------- 快取 --------
_CACHE_TTL = 7200            # 2 小時
_odds_cache: dict[str, dict] = {}
_sports_cache: dict[str, dict] = {}

def _fetch_odds(sport_key: str) -> list[dict]:
    now = time.time()
    if sport_key in _odds_cache and now - _odds_cache[sport_key]["ts"] < _CACHE_TTL:
        return _odds_cache[sport_key]["data"]

    if not API_KEY:
        return []
    url = (f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
           f"?regions=eu,us,uk&markets=h2h&oddsFormat=decimal&dateFormat=iso"
           f"&apiKey={API_KEY}")
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        _odds_cache[sport_key] = {"ts": now, "data": data}
        return data
    except Exception as exc:                     # noqa: BLE001
        logger.error("fetch odds error (%s): %s", sport_key, exc)
        return []

def active_tracked_sports() -> list[tuple[str, str]]:
    """給 /sport 用：回傳 (sport_key, title) 清單。"""
    now = time.time()
    if "data" in _sports_cache and now - _sports_cache["ts"] < 21600:
        return _sports_cache["data"]

    if not API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports?apiKey={API_KEY}"
    try:
        data = requests.get(url, timeout=8).json()
    except Exception as exc:                     # noqa: BLE001
        logger.error("sports list error: %s", exc)
        return []

    active = [
        (i["key"], SPORT_TITLES.get(i["key"], i["title"]))
        for i in data
        if i["key"] in TRACKED_SPORT_KEYS and i.get("active")
    ]
    _sports_cache.update({"ts": now, "data": active})
    return active

# -------- 核心：找套利 --------
def top_surebets(
    *,
    total_stake: float = 100.0,
    days_ahead: int = 3,
    max_results: int = 5,
) -> list[dict]:
    today = _dt.date.today()
    end   = today + _dt.timedelta(days=days_ahead)
    bets: list[dict] = []

    for sk in TRACKED_SPORT_KEYS:
        for ev in _fetch_odds(sk):
            t = _dt.datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            if not (today <= t.date() <= end):
                continue

            white = [bm for bm in ev["bookmakers"] if bm["key"] in FRIENDLY_BOOKMAKERS]
            bms   = white if len(white) >= 2 else ev["bookmakers"]
            if len(bms) < 2:
                continue

            best: dict[str, dict] = {}
            for bm in bms:
                for mk in bm.get("markets", []):
                    if mk["key"] != "h2h":
                        continue
                    for oc in mk["outcomes"]:
                        name, price = oc["name"], oc["price"]
                        if name not in best or price > best[name]["price"]:
                            best[name] = {"price": price, "bm": bm["key"]}
            if len(best) < 2:
                continue

            inv = sum(1/v["price"] for v in best.values())
            if inv >= 1:
                continue

            roi = round((1/inv - 1)*100, 2)
            team_home, team_away = list(best.keys())[:2]
            stake_home = round(total_stake*(1/best[team_home]["price"])/inv, 2)
            stake_away = round(total_stake - stake_home, 2)

            bets.append({
                "sport_key": sk,
                "sport": SPORT_TITLES.get(sk, ev.get("sport_title", sk)),
                "commence_dt": t,
                "teams": [team_home, team_away],
                "bm_home": best[team_home]["bm"], "odd_home": best[team_home]["price"],
                "bm_away": best[team_away]["bm"], "odd_away": best[team_away]["price"],
                "stake_home": stake_home,
                "stake_away": stake_away,
                "roi": roi,
            })

    bets.sort(key=lambda x: (-x["roi"], x["commence_dt"]))
    return bets[:max_results]
