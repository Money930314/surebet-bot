"""telegram_notifier.py
Telegram Bot：被動指令互動（不主動推播）。
Commands:
    /start   – welcome
    /help    – usage
    /scan    – same as /roi (top 5 bets)
    /roi [sport] – top 5 bets with optional sport filter
    /bookies – list friendly bookmakers
"""
import os
import logging
import textwrap
import asyncio
from html import escape
from datetime import datetime, timezone
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
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from scraper import fetch_surebets, FRIENDLY_BOOKMAKERS  # after BOT_TOKEN loaded

# ------------------ Message formatter ------------------

def _fmt_time(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso_ts or "TBD"

def _format_match_html(match: Dict[str, Any]) -> str:
    """Return Telegram‑safe HTML (no <br>)"""
    lines: List[str] = []
    lines.append(f"<b>🏅 {escape(match['sport'])} – {escape(match['league'])}</b>")
    lines.append(f"⚔️  {escape(match['home_team'])} vs {escape(match['away_team'])}")
    lines.append(f"🕒 開賽時間：{_fmt_time(match.get('match_time'))}")
    lines.append("")  # blank line
    for bet in match["bets"]:
        lines.append(f"🎲 <b>{escape(bet['bookmaker'])}</b> @ {bet['odds']} → 投 {bet['stake']}")
    lines.append("")
    lines.append(f"💰 ROI：<b>{match['roi']}%</b>  |  預期獲利：{match['profit']}")
    if match.get("url"):
        lines.append(f"🔗 <a href='{escape(match['url'])}'>查看賽事詳情</a>")
    return "\\n".join(lines)


# ------------------ Low‑level sender ------------------

def _send_html(chat_id: str, html_text: str):
    if not BOT_TOKEN:
        return False
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=10,
    )
    ok = resp.ok and resp.json().get("ok")
    if not ok:
        logger.error("❌ Telegram 發送失敗 %s", resp.text[:200])
    return ok

# ------------------ Command handlers ------------------
async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = textwrap.dedent(
        """👋 嗨，您好！\n\n"""
    )
    msg += (
        "歡迎加入 <b>SureBet Radar</b> 📡 — 你的即時套利雷達！\n"
        "我會 24 小時為你搜尋全球博彩公司中的「無風險投注」機會，讓你穩穩把利潤帶回家。\n\n"
        "輸入 /help 看看完整指令，或馬上打 /scan 來感受一下我的魔力吧！💰"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = textwrap.dedent(
        """🛠 <b>使用說明</b>\n只要幾個簡單指令，就能把 SureBet Radar 玩得溜溜轉：\n\n"""
    )
    msg += (
        "/start – 和我打招呼並初始化。\n"
        "/help – 查看使用說明。\n"
        "/scan – 立即掃描最新 surebet，並列出 5 筆最高賠率差。\n"
        "/roi  [sport] – 功能同 /scan，可加運動過濾。\n"
        "/bookies – 查看目前支援的博彩公司清單。\n\n"
        "祝你下注愉快，穩穩獲利！🚀"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def _cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cmd_roi(update, context)

async def _cmd_roi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sport_filter = context.args[0] if context.args else None
    bets = fetch_surebets()
    if sport_filter:
        bets = [b for b in bets if sport_filter.lower() in b["sport"].lower()]
    bets = bets[:5]
    if not bets:
        await update.message.reply_text("目前沒有符合條件的套利機會 🙇‍♂️")
        return
    for match in bets:
        await update.message.reply_text(_format_match_html(match), parse_mode="HTML")

async def _cmd_bookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bookies = "\n".join([f"• {b.title()}" for b in FRIENDLY_BOOKMAKERS])
    await update.message.reply_text(f"目前支援的博彩公司：\n{bookies}")

async def _unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("未支援的指令，請輸入 /help 查看。")

# ------------------ Polling starter ------------------

def start_bot_polling():
    if not BOT_TOKEN:
        logger.warning("未設定 TELEGRAM_BOT_TOKEN，跳過 Bot Polling")
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
