# -*- coding: utf-8 -*-
"""
telegram_notifier.py  –  Telegram Bot 指令處理
------------------------------------------------
• 先註冊所有 /roi 類指令，再放 _unknown fallback，避免被攔截
• 預設 DEBUG log，方便排錯
"""

from __future__ import annotations
import os, html, asyncio, logging, datetime as _dt
from typing import List, Tuple

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from scraper import fetch_surebets, SPORT_GROUPS

# ---------- 基本設定 ----------
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("telegram_notifier")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

DEFAULT_STAKE = 100.0
DEFAULT_DAYS  = 2
MAX_DAYS      = 60

BOOKMAKER_URLS = {
    "pinnacle": "https://www.pinnacle.com",
    "betfair_ex": "https://www.betfair.com/exchange",
    "smarkets": "https://smarkets.com",
    "bet365": "https://www.bet365.com",
    "williamhill": "https://sports.williamhill.com",
    "unibet": "https://www.unibet.com",
    "betfair": "https://www.betfair.com/sport",
    "ladbrokes": "https://sports.ladbrokes.com",
    "marathonbet": "https://www.marathonbet.com",
}

# ---------- 訊息格式 ----------
def _fmt(m: dict) -> str:
    home, away = m["teams"]
    lines = [
        f"🏅 <b>{html.escape(m['sport'])}</b>",
        f"⚔️  {html.escape(home)} vs {html.escape(away)}",
    ]
    t = _dt.datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
    lines.append(f"🕒 開賽時間：{t:%Y-%m-%d %H:%M UTC}")
    lines.append("")

    b1 = m["bookie1"]; b2 = m["bookie2"]
    lines.append(
        f"🎲 <a href='{BOOKMAKER_URLS.get(b1, '')}'>{html.escape(b1.title())}</a> "
        f"@ {m['odd1']} → 投 {m['stake1']}"
    )
    lines.append(
        f"🎲 <a href='{BOOKMAKER_URLS.get(b2, '')}'>{html.escape(b2.title())}</a> "
        f"@ {m['odd2']} → 投 {m['stake2']}"
    )
    lines.append("")
    lines.append(f"💰 ROI：{m['roi']}% | 預期獲利：{m['profit']}")
    return "\n".join(lines)

# ---------- 指令解析 ----------
def _parse_roi_args(cmd: str, tokens: List[str]) -> Tuple[float, int, List[str]]:
    stake, days, sport = DEFAULT_STAKE, DEFAULT_DAYS, None
    if cmd.startswith("roi") and len(cmd) > 3:
        sport = cmd[3:]

    for tok in tokens:
        if tok.isalpha() and not sport:
            sport = tok
        elif tok.replace(".", "", 1).isdigit():
            if stake == DEFAULT_STAKE:
                stake = float(tok)
            else:
                days = int(float(tok))

    days = min(max(days, 1), MAX_DAYS)
    sports = [sport] if sport else None
    return stake, days, sports

# ---------- 指令處理 ----------
async def _cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 嗨，您好！\n<b>SureBet Radar</b> 📡 — 你的即時套利雷達！\n"
        "輸入 /help 查看指令，或直接 /scan 試試吧！",
        parse_mode="HTML",
    )

async def _cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sports = ", ".join(sorted(SPORT_GROUPS.keys()))
    await update.message.reply_text(
        "🛠 <b>使用說明</b>\n"
        "/start – 打招呼\n"
        "/help – 說明\n"
        "/scan – 同 /roi\n"
        "/roi [運動] [注金] [天數] – 查套利\n"
        "  例：/roi soccer 150 7\n"
        "/bookies – 友善莊家名單\n"
        f"支援運動：{sports}",
        parse_mode="HTML",
    )

async def _cmd_bookies(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤝 友善莊家：\n" + "\n".join(f"• {b.title()}" for b in BOOKMAKER_URLS),
        parse_mode="HTML",
    )

async def _cmd_roi(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cmd     = update.message.text.split()[0][1:]  # 去掉 '/'
    tokens  = update.message.text.split()[1:]
    stake, days, sports = _parse_roi_args(cmd, tokens)
    logger.debug("ROI cmd args sports=%s stake=%s days=%s", sports, stake, days)

    matches = fetch_surebets(
        sports=sports, total_stake=stake, days_window=days
    )[:5]

    if not matches:
        await update.message.reply_text(
            "😔 找不到符合條件的套利，可能 API 無盤或配額不足，試其他運動或天數。"
        )
        return

    for m in matches:
        await update.message.reply_text(
            _fmt(m), parse_mode="HTML", disable_web_page_preview=False
        )

async def _unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("指令無法識別，請 /help 查看。")

# ---------- 啟動 Polling ----------
def start_bot_polling() -> None:
    if not (BOT_TOKEN and CHAT_ID):
        logger.warning("Telegram Bot token 或 chat_id 未設定，Bot 不啟動")
        return

    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()

    # 先註冊所有已知指令
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help",  _cmd_help))
    app.add_handler(CommandHandler("scan",  _cmd_roi))
    app.add_handler(CommandHandler("bookies", _cmd_bookies))
    app.add_handler(CommandHandler("roi",   _cmd_roi))

    # 快捷 /roisoccer, /roibaseball…
    for g in SPORT_GROUPS:
        app.add_handler(CommandHandler(f"roi{g}", _cmd_roi))

    # *最後* 再放 unknown fallback
    app.add_handler(MessageHandler(filters.COMMAND, _unknown))

    logger.info("🚀 Telegram Bot polling 開始…")
    app.run_polling(stop_signals=None)
