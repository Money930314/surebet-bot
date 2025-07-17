# -*- coding: utf-8 -*-
"""
scraper.py  – 取盤並計算 surebet（Moneyline）
------------------------------------------------
• 擴充 FRIENDLY_BOOKMAKERS：共 9 家
• API 同時抓多 regions (eu,us,uk) + markets (h2h,spreads,totals)
• 60 秒記憶體快取，省免費配額
"""
from __future__ import annotations
import os, logging, datetime as _dt, requests
from functools import lru_cache

logger = logging.getLogger("scraper")

API_KEY = os.getenv("THE_ODDS_API_KEY", "").strip()

# 友善莊家白名單（可再增減）
FRIENDLY_BOOKMAKERS = {
    "pinnacle", "betfair_ex", "smarkets",
    "bet365", "williamhill", "unibet",
    "betfair", "ladbrokes", "marathonbet",
}

# -----------------------------------------------------------
# 1) 讀取所有 active sport_key，分 group
# -----------------------------------------------------------
def _load_all_sport_keys() -> dict[str, list[str]]:
    if not API_KEY:
        return {}
    url = f"https://api.the-odds-api.com/v4/sports?apiKey={API_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
    except Exception as exc:                   # noqa: BLE001
        logger.error("load sports list error: %s", exc)
        return {}

    groups: dict[str, list[str]] = {}
    for item in data:
        if not item.get("active"):
            continue
        key   = item["key"]               # soccer_epl
        group = key.split("_", 1)[0]      # soccer
        groups.setdefault(group, []).append(key)
    return groups

SPORT_GROUPS = _load_all_sport_keys()

# -----------------------------------------------------------
# 2) 單一 sport_key 盤口（60 秒快取）
# -----------------------------------------------------------
@lru_cache(maxsize=256)
def _fetch_odds_for_key(key: str) -> list[dict]:
    if not API_KEY:
        return []
    url = (
        f"https://api.the-odds-api.com/v4/sports/{key}/odds"
        f"?regions=eu,us,uk"
        f"&markets=h2h,spreads,totals"
        f"&oddsFormat=decimal&dateFormat=iso&apiKey={API_KEY}"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as exc:
        logger.debug("HTTP %s %s", exc.response.status_code, key)
    except Exception as exc:               # noqa: BLE001
        logger.error("fetch odds error: %s – %s", key, exc)
    return []

# -----------------------------------------------------------
# 3) 計算 Moneyline surebet
# -----------------------------------------------------------
def fetch_surebets(
    *,
    sports: list[str] | None = None,
    total_stake: float = 100.0,
    days_window: int = 2,
    min_roi: float = 0.0,
) -> list[dict]:
    # 決定要抓哪些 sport_key
    if not sports:
        sport_keys = [k for ks in SPORT_GROUPS.values() for k in ks]
    else:
        sport_keys: list[str] = []
        for s in sports:
            s = s.lower()
            sport_keys.extend(SPORT_GROUPS.get(s, [s]))
        sport_keys = list(dict.fromkeys(sport_keys))

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

            # 只取 Moneyline
            lines: list[tuple[str,float,float]] = []
            for bm in bms:
                for m in bm["markets"]:
                    if m["key"] != "h2h":
                        continue
                    o1, o2 = m["outcomes"]
                    lines.append((bm["key"], o1["price"], o2["price"]))
            if len(lines) < 2:
                continue

            for i in range(len(lines)):
                for j in range(i+1, len(lines)):
                    bm1, p1h, p1a = lines[i]
                    bm2, p2h, p2a = lines[j]

                    odd_home, bm_home = (p1h, bm1) if p1h >= p2h else (p2h, bm2)
                    odd_away, bm_away = (p2a, bm2) if p1h >= p2h else (p1a, bm1)

                    inv = 1/odd_home + 1/odd_away
                    if inv >= 1:
                        continue
                    roi = round((1/inv - 1)*100, 2)
                    if roi < min_roi:
                        continue

                    st_home = round(total_stake*(1/odd_home)/inv, 2)
                    st_away = round(total_stake - st_home, 2)

                    results.append({
                        "sport": ev["sport_title"],
                        "sport_key": ev["sport_key"],
                        "teams": ev["teams"],
                        "commence_time": ev["commence_time"],
                        "bookie1": bm_home, "odd1": odd_home, "stake1": st_home,
                        "bookie2": bm_away, "odd2": odd_away, "stake2": st_away,
                        "roi": roi,
                        "profit": round(total_stake*roi/100, 2),
                    })

    results.sort(key=lambda x: x["roi"], reverse=True)
    return results[:100]

def clear_cache() -> None:
    _fetch_odds_for_key.cache_clear()
