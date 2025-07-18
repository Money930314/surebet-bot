# scraper.py  (2025‑07‑18)
from __future__ import annotations
import os, time, logging, datetime as _dt, requests, itertools

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("scraper")

API_KEY = os.getenv("THE_ODDS_API_KEY", "").strip()

# ▸ 一次最多掃描 10 個運動
MAX_SPORTS_PER_SCAN = 10
OUTRIGHT_PAT = ("winner", "outright", "championship")

FRIENDLY_BOOKMAKERS = {
    "pinnacle", "betfair_ex", "smarkets",
    "bet365", "williamhill", "unibet",
    "betfair", "ladbrokes", "marathonbet",
}

_CACHE_TTL = 2 * 60 * 60
_SPORTS_TTL = 6 * 60 * 60
_odds_cache, _sports_cache = {}, {}


# ---------- API quota ----------
def get_api_quota() -> tuple[int | None, int | None]:
    if not API_KEY:
        return None, None
    try:
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports",
            params={"apiKey": API_KEY},
            timeout=6,
        )
        return (
            int(r.headers.get("x-requests-remaining", -1)),
            int(r.headers.get("x-requests-used", -1)),
        )
    except Exception as exc:             # noqa: BLE001
        logger.error("quota check error: %s", exc)
        return None, None


# ---------- 運動清單 ----------
def _active_sport_keys() -> list[str]:
    now = time.time()
    if "data" in _sports_cache and now - _sports_cache["ts"] < _SPORTS_TTL:
        return _sports_cache["data"]

    if not API_KEY:
        return []

    try:
        data = requests.get(
            "https://api.the-odds-api.com/v4/sports",
            params={"apiKey": API_KEY},
            timeout=8,
        ).json()
    except Exception as exc:             # noqa: BLE001
        logger.error("sports list error: %s", exc)
        return []

    active = [s["key"] for s in data if s.get("active")]
    _sports_cache.update({"ts": now, "data": active})
    return active


# ---------- 抓賠率 ----------
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
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        _odds_cache[sport_key] = {"ts": now, "data": data}
        return data
    except Exception as exc:             # noqa: BLE001
        logger.error("fetch odds error (%s): %s", sport_key, exc)
        return []


# ---------- 主函式 ----------
def top_surebets(
    *, total_stake: float = 100.0, days_ahead: int = 3, max_results: int = 5
) -> list[dict]:
    today = _dt.date.today()
    end   = today + _dt.timedelta(days=days_ahead)
    bets: list[dict] = []

    for sk in itertools.islice(_active_sport_keys(), MAX_SPORTS_PER_SCAN):
        if any(t in sk for t in OUTRIGHT_PAT):
            continue

        fetched = _fetch_odds(sk)
        logger.info("sport=%s events=%d", sk, len(fetched))

        for ev in fetched:
            t = _dt.datetime.fromisoformat(
                ev["commence_time"].replace("Z", "+00:00")
            )
            if not (today <= t.date() <= end):
                continue

            # 友善莊家優先，若不足 2 家→ 取前 2 家
            white = [
                bm for bm in ev["bookmakers"]
                if bm["key"] in FRIENDLY_BOOKMAKERS
            ]
            if len(white) >= 2:
                bms = white
            elif len(ev["bookmakers"]) >= 2:
                bms = ev["bookmakers"][:2]
            else:
                continue

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

            inv = sum(1 / v["price"] for v in best.values())
            if inv >= 1:
                continue

            roi = round((1 / inv - 1) * 100, 2)
            home, away = list(best.keys())[:2]
            stake_home = round(total_stake * (1 / best[home]["price"]) / inv, 2)
            stake_away = round(total_stake - stake_home, 2)

            bets.append(
                {
                    "sport_key": sk,
                    "sport": ev.get("sport_title", sk),
                    "commence_dt": t,
                    "teams": [home, away],
                    "bm_home": best[home]["bm"],
                    "odd_home": best[home]["price"],
                    "bm_away": best[away]["bm"],
                    "odd_away": best[away]["price"],
                    "stake_home": stake_home,
                    "stake_away": stake_away,
                    "roi": roi,
                }
            )

    bets.sort(key=lambda x: (-x["roi"], x["commence_dt"]))
    return bets[:max_results]
