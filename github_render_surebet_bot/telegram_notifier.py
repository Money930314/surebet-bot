# -*- coding: utf-8 -*-
"""
telegram_notifier.py  (2025-07-18 全面簡化版)
-------------------------------------------------
/scan   ⇢ 不收任何參數，直接秀「距今日最近、ROI 最高的 5 筆 surebet」
/sport  ⇢ 列出目前 active 的追蹤聯盟
其餘指令：/start、/help、/bookies
"""
from __future__ import annotations
import os, html, logging, asyncio
import datetime as _dt
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import requests

from scraper import top_surebets, active_tracked_sports, SPORT_TITLES

# ---------- 基本設定 ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg_bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_STAKE = 100.0            # 內部 default，外部不再輸入

BOOKMAKER_URLS = {
    "pinnacle":        "https://www.pinnacle.com",
    "betfair_ex":      "https://www.betfair.com/exchange",
    "smarkets":        "https://smarkets.com",
    "bet365":          "https://www.bet365.com",
    "williamhill":     "https://sports.williamhill.com",
    "unibet":          "https://www.unibet.com",
    "betfair":         "https://www.betfair.com/sport",
    "ladbrokes":       "https://sports.ladbrokes.com",
    "marathonbet":     "https://www.marathonbet.com",
}

# ---------- 訊息格式 ----------
def _fmt(b: dict) -> str:
    home, away = b["teams"]
    t = b["commence_dt"].strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "📣 <b>Surebet 速報</b> 🔥",
        f"🏟️ <b>{html.escape(b['sport'])}</b>",
        f"⚔️  {html.escape(home)}  vs  {html.escape(away)}",
        f"🗓️  {t}",
        "",
        "💰 <b>下注分配</b>",
        f"  🎲 <a href='{
