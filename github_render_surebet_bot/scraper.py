import os
import logging
import datetime as _dt
import requests

logger = logging.getLogger("scraper")

API_KEY = os.getenv("THE_ODDS_API_KEY", "")
FRIENDLY_BOOKMAKERS = {"pinnacle", "betfair_ex", "smarkets"}

# -----------------------------------------------------------
#  1) 先把官方 sport_key 全抓下來，分群存在 SPORT_GROUPS
# -----------------------------------------------------------
def _load_all_sport_keys() -> dict[str, list[str]]:
    url = f"https://api.the-odds-api.com/v4/sports?apiKey={API_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
    except Exception as e:                      # noqa: BLE001
        logger.error("load sports list error: %s", e)
        return {}

    groups: dict[str, list[str]] = {}
    for item in data:
        key = item["key"]                      # 例：soccer_epl
        group = key.split("_", 1)[0]           # 例：soccer
        groups.setdefault(group, []).append(key)
    return groups


SPORT_GROUPS: dict[str, list[str]] = _load_all_sport_keys()

# -----------------------------------------------------------
#  2) Odds API 抓盤 + 計算 surebet
# -----------------------------------------------------------
def _fetch_odds_for_key(key: str) -> list[dict]:
    url = (
        "https://api.the-odds-api.com/v4/sports/"
        f"{key}/odds?regions=eu&markets=h2h"
        f"&oddsFormat=decimal&dateFormat=iso&apiKey={API_KEY}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        logger.debug("HTTPError %s (%s)", e.response.status_code, key)
    except Exception as e:                      # noqa: BLE001
        logger.error("fetch odds error: %s – %s", key, e)
    return []


def fetch_surebets(
    sports: list[str] | None = None,
    *,
    min_roi: float = 0.0,
    total_stake: float = 100.0,
    days_window: int = 2,
) -> list[dict]:
    """回傳依 ROI 由高到低排序的 surebet list（最多 100 筆）"""

    # ---- 解析 sports 參數：可傳大分類，也可傳精確 key ----
    if not sports:
        sport_keys = [k for keys in SPORT_GROUPS.values() for k in keys]
    else:
        sport_keys: list[str] = []
        for s in sports:
            s = s.lower()
            sport_keys.extend(SPORT_GROUPS.get(s, [s]))
        # 去重
        sport_keys = list(dict.fromkeys(sport_keys))

    today = _dt.date.today()
    end_date = today + _dt.timedelta(days=days_window)
    results: list[dict] = []

    for key in sport_keys:
        for ev in _fetch_odds_for_key(key):
            # 只要「今天～days_window 天後」的賽事
            c_time = _dt.datetime.fromisoformat(
                ev["commence_time"].replace("Z", "+00:00")
            )
            if not (today <= c_time.date() <= end_date):
                continue

            # 只留白名單莊家
            bms = [bm for bm in ev.get("bookmakers", []) if bm["key"] in FRIENDLY_BOOKMAKERS]
            if len(bms) < 2:
                continue

            # 擷取每家莊家 Moneyline 兩隊賠率
            lines: list[tuple[str, float, float]] = []
            for bm in bms:
                for m in bm["markets"]:
                    if m["key"] != "h2h":
                        continue
                    o1, o2 = m["outcomes"]
                    lines.append((bm["key"], o1["price"], o2["price"]))
            if len(lines) < 2:
                continue

            # 任取兩家莊家做組合，計算 ROI
            for i in range(len(lines)):
                for j in range(i + 1, len(lines)):
                    bm1, p1_home, p1_away = lines[i]
                    bm2, p2_home, p2_away = lines[j]

                    # 只考慮同一隊伍對位
                    if p1_home <= p2_home:          # 取賠率較高的一邊
                        odd_home, bm_home = p2_home, bm2
                        odd_away, bm_away = p1_away, bm1
                    else:
                        odd_home, bm_home = p1_home, bm1
                        odd_away, bm_away = p2_away, bm2

                    inv_sum = 1 / odd_home + 1 / odd_away
                    if inv_sum >= 1:
                        continue

                    roi = round((1 / inv_sum - 1) * 100, 2)
                    if roi < min_roi:
                        continue

                    stake_home = round(total_stake * (1 / odd_home) / inv_sum, 2)
                    stake_away = round(total_stake - stake_home, 2)

                    results.append(
                        {
                            "sport": ev["sport_title"],
                            "sport_key": ev["sport_key"],
                            "league": key,
                            "teams": ev["teams"],
                            "commence_time": ev["commence_time"],
                            "bookie1": bm_home,
                            "odd1": odd_home,
                            "stake1": stake_home,
                            "bookie2": bm_away,
                            "odd2": odd_away,
                            "stake2": stake_away,
                            "roi": roi,
                            "profit": round(total_stake * roi / 100, 2),
                        }
                    )

    results.sort(key=lambda x: x["roi"], reverse=True)
    return results[:100]   # 最多回傳 100 筆
