"""telegram_notifier.py – Telegram Bot for SureBet Radar.

功能概述：
* /start     → 歡迎訊息
* /help      → 使用說明
* /scan      → 等同 /roi
* /roi [sport] [stake]  → 查詢最高 ROI（明、後兩天賽事），可指定運動與投注總額
* /bookies   → 顯示友善莊家
* /roibasketball 等「黏在一起」的快速指令亦支援
"""
import os
import logging
import textwrap
import asyncio
from html import escape
from datetime import datetime
from typing import Dict, Any, List

import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from scraper import fetch_surebets, FRIENDLY_BOOKMAKERS, DEFAULT_SPORTS

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

# ---------- helpers ----------

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

# ---------- core fetch & reply ----------

def _resolve_sport(arg: str | None):
    if not arg:
        return None
    key = arg.lower()
    return SPORT_ALIASES.get(key)

async def _reply_surebets(update: Update, sport_key: str | None, total_stake: float):
    sports = [sport_key] if sport_key else None
    bets = fetch_surebets(sports=sports, total_stake=total_stake)
    bets = bets[:5]
    if not bets:
        await update.message.reply_text("目前沒有符合條件的套利機會 🙇‍♂️")
        return
    for m in bets:
        await update.message.reply_text(_fmt_match(m), parse_mode="HTML", disable_web_page_preview=False)

# ---------- command handlers ----------

async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 嗨，您好！\n\n"
        "歡迎加入 <b>SureBet Radar</b> 📡 — 你的即時套利雷達！\n"
        "我會 24 小時為你搜尋全球博彩公司中的「無風險投注」機會，讓你穩穩把利潤帶回家。\n\n"
        "輸入 /help 看看完整指令，或馬上打 /scan 來感受一下我的魔力吧！💰",
        parse_mode="HTML",
    )

async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = textwrap.dedent(
        """🛠 <b>使用說明</b>\n指令一覽：\n\n"""
    ) + (
        "/start – 初始化歡迎訊息\n"
        "/help – 查看使用說明\n"
        "/scan – 掃描最新 surebet (預設下注 100)\n"
        "/roi [sport] [stake] – 查詢 surebet，可加運動與下注額\n"
        "/bookies – 查看友善莊家清單\n\n"
        "亦支援快捷： /roibasketball 200  等同  /roi basketball 200"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def _cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply_surebets(update, None, DEFAULT_STAKE)

async def _cmd_roi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    sport_arg = args[0] if args else None
    stake = DEFAULT_STAKE
    if args:
        # if first arg numeric treat as stake
        if args[0].isdigit():
            stake = float(args[0])
            sport_arg = None
        elif len(args) >= 2 and args[1].isdigit():
            stake = float(args[1])
    sport_key = _resolve_sport(sport_arg)
    await _reply_surebets(update, sport_key, stake)

async def _cmd_bookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = "\n".join([f"• {b.title()}" for b in FRIENDLY_BOOKMAKERS])
    await update.message.reply_text(f"目前支援的博彩公司：\n{txt}")

async def _unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lstrip("/")
    if text.lower().startswith("roi"):
        # fast command: /roibasketball 150
        cmd = text[3:]  # remove 'roi'
        parts = cmd.split()
        sport = parts[0] if parts and parts[0] else None
        stake = float(parts[1]) if len(parts) > 1 and parts[1].isdigit() else DEFAULT_STAKE
        sport_key = _resolve_sport(sport)
        await _reply_surebets(update, sport_key, stake)
        return
    await update.message.reply_text("未支援的指令，請輸入 /help 查看。")

# ---------- run polling ----------

def start_bot_polling():
    if not BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN 未設定，Bot 不會啟動")
        return
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("scan", _cmd_scan))
    app.add_handler(CommandHandler("roi", _cmd_roi))
    app.add_handler(CommandHandler("bookies", _cmd_bookies))
    app.add_handler(MessageHandler(filters.COMMAND, _unknown))

    logger.info("🚀 Telegram Bot polling 開始…")
    app.run_polling(stop_signals=None)
