"""telegram_notifier.py – Telegram Bot for SureBet Radar.

重點更新：
* /roi [sport] [stake] [days]  — 第 3 個參數可指定抓取「未來 N 天」(1‑60)，預設 2。
* 快捷 /roisoccer 150 7 同樣支援。
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
DEFAULT_DAYS = 2
MAX_DAYS = 60

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

# ---------- core fetch ----------

def _resolve_sport(alias: str | None):
    if not alias:
        return None
    return SPORT_ALIASES.get(alias.lower())

async def _reply_surebets(update: Update, sport_key: str | None, stake: float, days: int):
    sports = [sport_key] if sport_key else None
    bets = fetch_surebets(sports=sports, total_stake=stake, days_window=days)
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
        "/scan – 掃描最新 surebet (預設下注 100, 2 天內賽事)\n"
        "/roi [sport] [stake] [days] – 查詢 surebet，可加運動、下注額、天數 (1‑60)\n"
        "/bookies – 查看友善莊家清單\n\n"
        "亦支援快捷： /roibasketball 200 7  等同  /roi basketball 200 7"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def _cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply_surebets(update, None, DEFAULT_STAKE, DEFAULT_DAYS)

async def _cmd_roi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sport_key = None
    stake = DEFAULT_STAKE
    days = DEFAULT_DAYS

    # 解析參數
    params = context.args
    for p in params:
        if p.isdigit():
            val = int(p)
            if 1 <= val <= MAX_DAYS and days == DEFAULT_DAYS:
                days = val
            else:
                stake = float(val)
        else:
            sport_key = _resolve_sport(p)

    await _reply_surebets(update, sport_key, stake, days)

async def _cmd_bookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = "\n".join([f"• {b.title()}" for b in FRIENDLY_BOOKMAKERS])
    await update.message.reply_text(f"目前支援的博彩公司：\n{txt}")

async def _unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lstrip("/")
    if text.lower().startswith("roi"):
        parts = text[3:].split()
        sport = None
        stake = DEFAULT_STAKE
        days = DEFAULT_DAYS
        for p in parts:
            if p.isdigit():
                v = int(p)
                if 1 <= v <= MAX_DAYS and days == DEFAULT_DAYS:
                    days = v
                else:
                    stake = float(v)
            else:
                sport = p
        await _reply_surebets(update, _resolve_sport(sport), stake, days)
        return
    await update.message.reply_text("未支援的指令，請輸入 /help 查看。")

# ---------- polling ----------

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
