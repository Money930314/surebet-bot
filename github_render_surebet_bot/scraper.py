# -*- coding: utf-8 -*-
"""
scraper.py  ─ 專責抓取賠率並挑出 ROI 最高的 surebet
2025‑07‑18  重構：
1. 不再硬寫 TRACKED_SPORT_KEYS，而是動態抓取「所有 active 運動」
   但一次最多打 API 5 種運動，避免日額度爆掉。
2. 新增 get_api_quota()，供 /quota 指令查詢 API 餘額。
"""
from __future__ import annotations
import os, time, logging, datetime as _dt, requests, itertools

logger = logging.getLogger("scraper")
API_KEY = os.getenv("THE_ODDS_API_KEY", "").strip()

# --- NEW: 最多掃描 5 個運動，避免瞬間耗光額度 ---
MAX_SPORTS_PER_SCAN = 5

# 白名單莊家
FRIENDLY_BOOKMAKERS: set[str] = {
    "pinnacle", "betfair_ex", "smarkets",
    "bet365", "williamhill", "unibet",
    "betfair", "ladbrokes", "marathonbet",
}

# 不同 API 要求的快取
_CACHE_TTL = 2 * 60 * 60                # odds  cache 2h
_SPORTS_TTL = 6 * 60 * 60               # sports cache 6h
_odds_cache: dict[str, dict] = {}
_sports_cache: dict[str, dict] = {}

# --------------------------------------------------------
# 公用：查 API 配額（給 /quota 指令用）
# --------------------------------------------------------
def get_api_quota() -> tuple[int | None, int | None]:
    """回傳 (剩餘次數, 已用次數)。取不到時回 (None, None)"""
    if not API_KEY:
        return None, None
    try:
        r = requests.get("https://api.the-odds-api.com/v4/sports",
                         params={"apiKey": API_KEY}, timeout=6)
        return (
            int(r.headers.get("x-requests-remaining", -1)),
            int(r.headers.get("x-requests-used", -1)),
        )
    except Exception as exc:             # noqa: BLE001
        logger.error("quota check error: %s", exc)
        return None, None

# --------------------------------------------------------
# 動態取得「目前 active」且有 friendly bookmaker 的 sport_key
# --------------------------------------------------------
def _active_sport_keys() -> list[str]:
    now = time.time()
    if "data" in _sports_cache and now - _sports_cache["ts"] < _SPORTS_TTL:
        return _sports_cache["data"]

    if not API_KEY:
        return []

    try:
        data = requests.get(
            "https://api.the-odds-api.com/v4/sports",
            params={"apiKey": API_KEY}, timeout=8
        ).json()
    except Exception as exc:             # noqa: BLE001
        logger.error("sports list error: %s", exc)
        return []

    # 只留下「active=True」且任何 bookmaker 落在白名單的運動
    active_keys: list[str] = []
    for s in data:
        if not s.get("active"):
            continue
        # The‑Odds‑API 無法事先知道 bookmaker，這邊先全部納入
        active_keys.append(s["key"])

    _sports_cache.update({"ts": now, "data": active_keys})
    return active_keys

# --------------------------------------------------------
def _fetch_odds(sport_key: str) -> list[dict]:
    now = time.time()
    if sport_key in _odds_cache and now - _odds_cache[sport_key]["ts"] < _CACHE_TTL:
        return _odds_cache[sport_key]["data"]

    if not API_KEY:
        return []
    try:
        resp = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
            params={
                "regions": "us,uk,eu,au",
                "markets": "h2h",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
                "apiKey": API_KEY,
            },
            timeout=8)
        resp.raise_for_status()
        data = resp.json()
        _odds_cache[sport_key] = {"ts": now, "data": data}
        return data
    except Exception as exc:             # noqa: BLE001
        logger.error("fetch odds error (%s): %s", sport_key, exc)
        return []

# --------------------------------------------------------
def top_surebets(
    *,
    total_stake: float = 100.0,
    days_ahead: int = 3,
    max_results: int = 5,
) -> list[dict]:
    """
    回傳 ROI 最高且開賽時間最近的 surebet。
    - total_stake: 假設總投注金額
    - days_ahead: 搜尋未來幾天內的賽事
    """
    today = _dt.date.today()
    end   = today + _dt.timedelta(days=days_ahead)
    bets: list[dict] = []

    # 取前 MAX_SPORTS_PER_SCAN 個運動，避免一次炸 API
    for sk in itertools.islice(_active_sport_keys(), MAX_SPORTS_PER_SCAN):
        for ev in _fetch_odds(sk):
            t = _dt.datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            if not (today <= t.date() <= end):
                continue

            # 選擇友善莊家 bookmaker，若不足 2 家就全用
            white = [bm for bm in ev["bookmakers"] if bm["key"] in FRIENDLY_BOOKMAKERS]
            bms   = white if len(white) >= 2 else ev["bookmakers"]
            if len(bms) < 2:
                continue

            # 找出每個 outcome 的最高賠率
            best: dict[str, dict] = {}
            for bm in bms:
                for mk in bm.get("markets", []):
                    if mk["key"] != "h2h":
                        continue
                    for oc in mk["outcomes"]:
                        n, p = oc["name"], oc["price"]
                        if p <= 1:
                            continue
                        if n not in best or p > best[n]["price"]:
                            best[n] = {"price": p, "bm": bm["key"]}
            if len(best) < 2:
                continue

            inv = sum(1/v["price"] for v in best.values())
            if inv >= 1:                                     # 不是正套利
                continue

            roi = round((1/inv - 1)*100, 2)
            (home, away) = list(best.keys())[:2]
            stake_home = round(total_stake*(1/best[home]["price"])/inv, 2)
            stake_away = round(total_stake - stake_home, 2)

            bets.append({
                "sport_key": sk,
                "sport": ev.get("sport_title", sk),
                "commence_dt": t,
                "teams": [home, away],
                "bm_home": best[home]["bm"], "odd_home": best[home]["price"],
                "bm_away": best[away]["bm"], "odd_away": best[away]["price"],
                "stake_home": stake_home,
                "stake_away": stake_away,
                "roi": roi,
            })

    bets.sort(key=lambda x: (-x["roi"], x["commence_dt"]))
    return bets[:max_results]
