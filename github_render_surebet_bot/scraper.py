# -*- coding: utf-8 -*-
"""
scraper.py  –  只抓 Moneyline 盤並計算 surebet
------------------------------------------------
滿足新需求：
1. 僅抓 h2h (moneyline)；不再抓 spreads / totals
2. 預設僅追蹤 6 個跨季熱門聯盟，全年都有球可下
3. 內建 2 小時記憶體快取 → 每個 sport_key 最多 12 次 / 日
4. 提供 active_tracked_sports() 供 /sport 指令使用
"""
from __future__ import annotations
import os, time, logging, datetime as _dt, requests

logger = logging.getLogger("scraper")
API_KEY = os.getenv("THE_ODDS_API_KEY", "").strip()

# ---------------- 熱門運動常量 ----------------
TRACKED_SPORT_KEYS = [
    "soccer_epl",          # 8 月–5 月
    "basketball_nba",      # 10 月–6 月
    "baseball_mlb",        # 3 月–10 月
    "icehockey_nhl",       # 10 月–6 月
    "tennis_atp",          # 全年
    "americanfootball_nfl" # 9 月–2 月
]
SPORT_TITLES = {
    "soccer_epl": "英超足球",
    "basketball_nba": "NBA 籃球",
    "baseball_mlb": "MLB 棒球",
    "icehockey_nhl": "NHL 冰球",
    "tennis_atp": "ATP 網球",
    "americanfootball_nfl": "NFL 美式足球",
}

# 友善莊家白名單（可再增減）
FRIENDLY_BOOKMAKERS = {
    "pinnacle", "betfair_ex", "smarkets",
    "bet365", "williamhill", "unibet",
    "betfair", "ladbrokes", "marathonbet",
}

# ---------------- API 快取 ----------------
_ODDS_CACHE: dict[str, dict] = {}
_CACHE_TTL = 7200  # 秒；2 小時

def _fetch_odds_for_key(key: str) -> list[dict]:
    """抓指定 sport_key 的 moneyline 盤；結果 2 小時快取。"""
    now = time.time()
    if key in _ODDS_CACHE and now - _ODDS_CACHE[key]["ts"] < _CACHE_TTL:
        return _ODDS_CACHE[key]["data"]

    if not API_KEY:
        return []
    url = (
        f"https://api.the-odds-api.com/v4/sports/{key}/odds"
        f"?regions=eu,us,uk"
        f"&markets=h2h"
        f"&oddsFormat=decimal&dateFormat=iso&apiKey={API_KEY}"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        _ODDS_CACHE[key] = {"ts": now, "data": data}
        return data
    except Exception as exc:                   # noqa: BLE001
        logger.error("fetch odds error (%s): %s", key, exc)
        return []

def clear_cache() -> None:
    _ODDS_CACHE.clear()

# ---------------- /sport 用 ----------------
_SPORTS_CACHE: dict[str, dict] = {}

def active_tracked_sports() -> list[tuple[str, str]]:
    """回傳目前 `active=true` 的追蹤運動 [(key, title), ...]；6 小時快取。"""
    now = time.time()
    if "data" in _SPORTS_CACHE and now - _SPORTS_CACHE["ts"] < 21600:
        return _SPORTS_CACHE["data"]

    if not API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports?apiKey={API_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
    except Exception as exc:                   # noqa: BLE001
        logger.error("load sports list error: %s", exc)
        return []

    active = [
        (item["key"], SPORT_TITLES.get(item["key"], item["title"]))
        for item in data
        if item["key"] in TRACKED_SPORT_KEYS and item.get("active")
    ]
    _SPORTS_CACHE.update({"ts": now, "data": active})
    return active

# ---------------- 計算 surebet ----------------
def fetch_surebets(
    *,
    sports: list[str] | None = None,
    total_stake: float = 100.0,
    days_window: int = 2,
    min_roi: float = 0.0,
) -> list[dict]:
    """
    回傳 surebet 列表，每筆：
    {sport, sport_key, teams[], commence_time, bookmaker/odd/stake 1&2, roi, profit}
    """
    # 決定要抓哪些 sport_key
    if not sports:
        sport_keys = TRACKED_SPORT_KEYS
    else:
        sport_keys = [s for s in sports if s in TRACKED_SPORT_KEYS]
        if not sport_keys:
            sport_keys = TRACKED_SPORT_KEYS

    today = _dt.date.today()
    end   = today + _dt.timedelta(days=days_window)
    results: list[dict] = []

    for key in sport_keys:
        for ev in _fetch_odds_for_key(key):
            # 日期篩選
            t = _dt.datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            if not (today <= t.date() <= end):
                continue

            # 白名單莊家
            bms = [bm for bm in ev["bookmakers"] if bm["key"] in FRIENDLY_BOOKMAKERS]
            if len(bms) < 2:
                continue

            # Moneyline
            lines: list[tuple[str,float,float]] = []
            for bm in bms:
                for m in bm["markets"]:
                    if m["key"] != "h2h":
                        continue
                    o1, o2 = m["outcomes"]
                    lines.append((bm["key"], o1["price"], o2["price"]))
            if len(lines) < 2:
                continue

            # 任兩家莊家組合
            for i in range(len(lines)):
                for j in range(i+1, len(lines)):
                    bm1, p1h, p1a = lines[i]
                    bm2, p2h, p2a = lines[j]

                    odd_home, bm_home = (p1h, bm1) if p1h >= p2h else (p2h, bm2)
                    odd_away, bm_away = (p2a, bm2) if p1a >= p2a else (p1a, bm1)

                    inv = 1/odd_home + 1/odd_away
                    if inv >= 1:
                        continue
                    roi = round((1/inv - 1)*100, 2)
                    if roi < min_roi:
                        continue

                    st_home = round(total_stake*(1/odd_home)/inv, 2)
                    st_away = round(total_stake - st_home, 2)

                    results.append({
                        "sport": SPORT_TITLES.get(key, ev["sport_title"]),
                        "sport_key": key,
                        "teams": ev["teams"],
                        "commence_time": ev["commence_time"],
                        "bookie1": bm_home, "odd1": odd_home, "stake1": st_home,
                        "bookie2": bm_away, "odd2": odd_away, "stake2": st_away,
                        "roi": roi,
                        "profit": round(total_stake*roi/100, 2),
                    })

    results.sort(key=lambda x: x["roi"], reverse=True)
    return results[:100]
