# -*- coding: utf-8 -*-
"""
telegram_notifier.py  –  Telegram Bot 指令 (2025-07-18 修正版)
--------------------------------------------------------------
• /scan 先送「正在掃描」訊息，完成後再編輯結果
• 如指定運動目前休季 / 無盤，立即回覆原因
• 加入 try/except，任何錯誤都能回報而不會安靜失敗
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

# ---------- 參數解析 ----------
def _parse_scan_args(tokens: List[str]) -> Tuple[float, int, List[str] | None]:
    """tokens: [sport?] [stake?] [days?]"""
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
    sports = ", ".join(SPORT_TITLES[k] for k in TRACKED_SPORT_KEYS)
    await update.message.reply_text(
        "🛠 <b>使用說明</b>\n"
        "/start – 打招呼\n"
        "/help – 說明\n"
        "/scan [運動] [注金] [天數] – 掃描套利 (moneyline)\n"
        "  範例：/scan tennis_atp 150 7\n"
        "/sport – 查看目前有開賽的追蹤運動\n"
        "/bookies – 友善莊家名單\n"
        f"追蹤運動：{sports}",
        parse_mode="HTML",
    )

async def _cmd_bookies(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤝 友善莊家：\n" + "\n".join(f"• {b.title()}" for b in BOOKMAKER_URLS),
        parse_mode="HTML",
    )

async def _cmd_sport(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    active = active_tracked_sports()
    if not active:
        await update.message.reply_text("😴 目前追蹤的運動都在休季。")
        return
    txt = "📅 目前開賽運動：\n" + "\n".join(f"• {title} (`{key}`)" for key, title in active)
    await update.message.reply_markdown_v2(txt, disable_web_page_preview=True)

async def _cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    # ---- 解析參數 ----
    tokens = update.message.text.split()[1:]
    stake, days, sports = _parse_scan_args(tokens)
    sport_str = sports[0] if sports else "*多運動*"
    logger.info("SCAN args sports=%s stake=%s days=%s", sports, stake, days)

    # ---- 先告知正在掃描 ----
    wait_msg = await update.message.reply_text("🔍 正在掃描，請稍候…")

    try:
        # 若有指定運動且目前不在 active list，直接提示
        if sports and sports[0] not in [k for k, _ in active_tracked_sports()]:
            await wait_msg.edit_text(
                f"📌 `{sport_str}` 目前休季或 Odds API 尚未開盤，"
                "請改用 /sport 查詢可投注聯盟。",
                parse_mode="Markdown",
            )
            return

        matches = fetch_surebets(
            sports=sports, total_stake=stake, days_window=days
        )[:5]

        if not matches:
            await wait_msg.edit_text(
                "🙈 找不到符合條件的套利，可能還沒開盤或 ROI < 0%。"
                "也許換個運動 / 天數再試看看！"
            )
            return

        await wait_msg.edit_text(
            "\n\n".join(_fmt(m) for m in matches),
            parse_mode="HTML",
            disable_web_page_preview=False,
        )

    except requests.exceptions.Timeout:
        await wait_msg.edit_text("⏰ Odds API 逾時，稍後再試吧！")
    except Exception as exc:                                    # noqa: BLE001
        logger.exception("scan error: %s", exc)
        await wait_msg.edit_text(f"⚠️ 執行時發生錯誤：{exc}")

async def _unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("指令無法識別，請 /help 查看。")

# ---------- 啟動 Polling ----------
def start_bot_polling() -> None:
    if not BOT_TOKEN:
        logger.warning("Telegram Bot token 未設定，Bot 不啟動")
        return

    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help",  _cmd_help))
    app.add_handler(CommandHandler("scan",  _cmd_scan))
    app.add_handler(CommandHandler("sport", _cmd_sport))
    app.add_handler(CommandHandler("bookies", _cmd_bookies))

    # *最後* fallback
    app.add_handler(MessageHandler(filters.COMMAND, _unknown))

    logger.info("🚀 Telegram Bot polling 開始…")
    app.run_polling(stop_signals=None)
