"""telegram_notifier.py – Telegram Bot handlers"""
import os
import logging
import textwrap
import asyncio
from html import escape
from typing import Dict, Any, List

from datetime import datetime
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from scraper import fetch_surebets, FRIENDLY_BOOKMAKERS

BOOKMAKER_URLS = {
    "pinnacle": "https://www.pinnacle.com/",
    "betfair_ex": "https://www.betfair.com/exchange/",
    "smarkets": "https://smarkets.com/",
}

SPORT_ALIASES = {
    "basketball": "basketball_nba",
    "tennis": "tennis_atp",
    "volleyball": "volleyball_world",
    "soccer": "soccer_epl",
    "baseball": "baseball_mlb",
}
DEFAULT_STAKE = 100.0

# ---------- format helpers ----------

def _fmt_time(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso_ts or "TBD"


def _fmt_match(match: Dict[str, Any]):
    lines: List[str] = [
        f"<b>🏅 {escape(match['sport'])} – {escape(match['league'])}</b>",
        f"⚔️  {escape(match['home_team'])} vs {escape(match['away_team'])}",
        f"🕒 開賽時間：{_fmt_time(match['match_time'])}",
        "",
    ]
    for bet in match["bets"]:
        key = bet["bookmaker"].lower().replace(" ", "_")
        url = BOOKMAKER_URLS.get(key, f"https://google.com/search?q={escape(bet['bookmaker'])}")
        lines.append(
            f"🎲 <a href='{url}'><b>{escape(bet['bookmaker'])}</b></a> @ {bet['odds']} → 投 {bet['stake']}"
        )
    lines.append("")
    lines.append(f"💰 ROI：<b>{match['roi']}%</b> | 預期獲利：{match['profit']}")
    if match.get("url"):
        lines.append(f"🔗 <a href='{escape(match['url'])}'>查看賽事詳情</a>")
    return "\n".join(lines)

# ---------- commands ----------

async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 嗨，您好！\n\n"
        "歡迎加入 <b>SureBet Radar</b> 📡 — 你的即時套利雷達！\n"
        "我會 24 小時為...
