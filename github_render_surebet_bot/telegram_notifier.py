# -*- coding: utf-8 -*-
"""
telegram_notifier.py  –  Telegram Bot 指令 (2025-07-18 fix-2)
--------------------------------------------------------------
• /sport 改純文字回覆，並加 try/except 確保一定回訊息
• /scan 先回「掃描中…」→ 後續編輯結果；任何例外皆捕捉
"""
from __future__ import annotations
import os, html, logging, asyncio, datetime as _dt
from typing import List, Tuple

import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from scraper import (
    fetch_surebets,
    active_tracked_sports,
    TRACKED_SPORT_KEYS,
    SPORT_TITLES,
)

# ---------- 基本設定 ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_notifier")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_STAKE = 100.0
DEFAULT_DAYS  = 2
MAX_DAYS      = 60

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
def _fmt(m: dict) -> str:
    """格式化單筆 surebet 為 HTML。"""
    home, away = m["teams"]
    t = _dt.datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))

    lines = [
        f"🏅 <b>{html.escape(m['sport'])}</b>",
        f"⚔️  {html.escape(home)} vs {html.escape(away)}",
        f"🕒 開賽時間：{t:%Y-%m-%d %H:%M UTC}",
        "",
    ]
    b1, b2 = m["bookie1"], m["bookie2"]
    lines.append(
        f"🎲 <a href='{BOOKMAKER_URLS.get(b1,'')}'>{html.escape(b1.title())}</a> "
        f"@ {m['odd1']} → 投 {m['stake1']}"
    )
    lines.append(
        f"🎲 <a href='{BOOKMAKER_URLS.get(b2,'')}'>{html.escape(b2.title())}</a> "
        f"@ {m['odd2']} → 投 {m['stake2']}"
    )
    lines.append("")
    lines.append(f"💰 ROI：{m['roi']}%　預期獲利：{m['profit']}")
    return "\n".join(lines)

# ---------- 參數解析 ----------
def _parse_scan_args(tokens: List[str]) -> Tuple[float, int, List[str] | None]:
    """解析 /scan 參數：sport stake days"""
    stake, days, sport = DEFAULT_STAKE, DEFAULT_DAYS, None
    for tok in tokens:
        t = tok.lower()
        if t in TRACKED_SPORT_KEYS and not sport:
            sport = t
        elif t.replace(".", "", 1).isdigit():
            if stake == DEFAULT_STAKE:
                stake = float(t)
            else:
                days = int(float(t))
    days = min(max(days, 1), MAX_DAYS)
    return stake, days, ([sport] if sport else None)

# ---------- 指令 ----------
async def _cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 嗨！\n<b>SureBet Radar</b> 📡 — 你的即時套利雷達。\n"
        "輸入 /help 查看指令，或直接 /scan 試試看！",
        parse_mode="HTML",
    )

async def _cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sports = ", ".join(SPORT_TITLES[k] for k in TRACKED_SPORT_KEYS)
    await update.message.reply_text(
        "🛠 <b>使用說明</b>\n"
        "/start – 打招呼\n"
        "/help – 說明\n"
        "/scan [運動] [注金] [天數] – 掃描套利 (moneyline)\n"
        "  範例：/scan tennis_atp 150 7\n"
        "/sport – 查看目前有開賽的追蹤運動\n"
        "/bookies – 友善莊家名單\n\n"
        f"追蹤運動：{sports}",
        parse_mode="HTML",
    )

async def _cmd_bookies(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    txt = "🤝 友善莊家：\n" + "\n".join(f"• {b.title()}" for b in BOOKMAKER_URLS)
    await update.message.reply_text(txt)

async def _cmd_sport(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        active = active_tracked_sports()
        if not active:
            await update.message.reply_text("😴 目前追蹤運動皆休季或 Odds API 無盤。")
            return
        txt = "📅 目前開賽運動：\n" + "\n".join(
            f"• {title} ({key})" for key, title in active
        )
        await update.message.reply_text(txt)
    except Exception as exc:                                     # noqa: BLE001
        logger.exception("sport cmd error: %s", exc)
        await update.message.reply_text(f"⚠️ 讀取運動列表時發生錯誤：{exc}")

async def _cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    stake, days, sports = _parse_scan_args(update.message.text.split()[1:])
    sport_tag = sports[0] if sports else "多運動"

    # 先回應「掃描中…」
    wait_msg = await update.message.reply_text(f"🔍 正在掃描 {sport_tag} …")

    try:
        # 如指定運動但不在 active → 直接提示
        if sports and sports[0] not in [k for k, _ in active_tracked_sports()]:
            await wait_msg.edit_text(
                f"📌 {sport_tag} 目前休季或未開盤，請先用 /sport 查詢可投注聯盟。"
            )
            return

        bets = fetch_surebets(
            sports=sports,
            total_stake=stake,
            days_window=days,
        )[:5]

        if not bets:
            await wait_msg.edit_text(
                "🙈 找不到符合條件的套利（可能還沒開盤或 ROI≤0）。"
                "試著換個運動 / 天數再查詢。"
            )
            return

        await wait_msg.edit_text(
            "\n\n".join(_fmt(b) for b in bets),
            parse_mode="HTML",
            disable_web_page_preview=False,
        )

    except requests.exceptions.Timeout:
        await wait_msg.edit_text("⏰ Odds API 逾時，稍後再試。")
    except Exception as exc:                                      # noqa: BLE001
        logger.exception("scan cmd error: %s", exc)
        await wait_msg.edit_text(f"⚠️ 執行時發生錯誤：{exc}")

async def _unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("指令無法識別，請 /help 查看。")

# ---------- 啟動 ----------
def start_bot_polling() -> None:
    if not BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN 未設定，Bot 不啟動")
        return

    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help",  _cmd_help))
    app.add_handler(CommandHandler("scan",  _cmd_scan))
    app.add_handler(CommandHandler("sport", _cmd_sport))
    app.add_handler(CommandHandler("bookies", _cmd_bookies))
    app.add_handler(MessageHandler(filters.COMMAND, _unknown))  # fallback

    logger.info("🚀 Telegram Bot polling running…")
    app.run_polling(stop_signals=None)
