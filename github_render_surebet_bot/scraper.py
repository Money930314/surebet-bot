# -*- coding: utf-8 -*-
"""
scraper.py  ─ 找出 ROI 最高且最近開賽的 surebet（前 5 筆）

‣ 不再分運動、不再接收外部條件
‣ 預設掃描 6 個跨季熱門聯盟（EPL、NBA、MLB、NHL、ATP、NFL）
‣ 只抓 h2h (moneyline)；先用白名單莊家，不足 2 家就退回全部莊家
‣ 快取 2 小時，保障月用量 < 500 次
"""

from __future__ import annotations
import os, time, logging, datetime as _dt, requests

logger = logging.getLogger("scraper")
API_KEY = os.getenv("THE_ODDS_API_KEY", "").strip()

# ---------------- 追蹤聯盟 ----------------
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

# 可自行增刪
FRIENDLY_BOOKMAKERS = {
    "pinnacle", "betfair_ex", "smarkets",
    "bet365", "williamhill", "unibet",
    "betfair", "ladbrokes", "marathonbet",
}

# ---------------- 快取 ----------------
_ODDS_CACHE: dict[str, dict] = {}
_CACHE_TTL = 7200  # 2 h

def _odds_for(key: str) -> list[dict]:
    """抓指定 sport_key 的 moneyline 盤；結果快取 2 h。"""
    now = time.time()
    if key in _ODDS_CACHE and now - _ODDS_CACHE[key]["ts"] < _CACHE_TTL:
        return _ODDS_CACHE[key]["data"]

    if not API_KEY:
        return []
    url = (
        f"https://api.the-odds-api.com/v4/sports/{key}/odds"
        f"?regions=eu,us,uk&markets=h2h&oddsFormat=decimal"
        f"&dateFormat=iso&apiKey={API_KEY}"
    )
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
        _ODDS_CACHE[key] = {"ts": now, "data": data}
        return data
    except Exception as exc:                   # noqa: BLE001
        logger.error("fetch odds error (%s): %s", key, exc)
        return []

# ---------------- 計算 surebet ----------------
def top_surebets(
    *,
    total_stake: float = 100.0,
    days_ahead: int = 3,
    max_results: int = 5,
) -> list[dict]:
    """
    回傳 ROI 最高且最近開賽的前 `max_results` 筆 surebet。
    """
    today = _dt.date.today()
    end   = today + _dt.timedelta(days=days_ahead)
    bets: list[dict] = []

    for skey in TRACKED_SPORT_KEYS:
        for ev in _odds_for(skey):
            # 1) 只看未來 3 天內賽事
            t = _dt.datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            if not (today <= t.date() <= end):
                continue

            # 2) 撈適用的莊家
            white = [bm for bm in ev["bookmakers"] if bm["key"] in FRIENDLY_BOOKMAKERS]
            bms   = white if len(white) >= 2 else ev["bookmakers"]
            if len(bms) < 2:
                continue

            # 3) 取得兩隊 moneyline 最佳賠率
            best = {}
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
            if inv >= 1:           # 無套利
                continue
            roi = round((1/inv - 1)*100, 2)

            stake_home = round(total_stake * (1/best[next(iter(best))]["price"])/inv, 2)
            stake_away = round(total_stake - stake_home, 2)
            team_home, team_away = list(best.keys())

            bets.append({
                "sport_key": skey,
                "sport": SPORT_TITLES.get(skey, ev["sport_title"]),
                "commence_dt": t,
                "teams": [team_home, team_away],
                "bm_home": best[team_home]["bm"], "odd_home": best[team_home]["price"],
                "bm_away": best[team_away]["bm"], "odd_away": best[team_away]["price"],
                "stake_home": stake_home,
                "stake_away": stake_away,
                "roi": roi
