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
        f"  🎲 <a href='{BOOKMAKER_URLS.get(b['bm_home'],'')}'>{b['bm_home'].title()}</a> → "
        f"{html.escape(home)} @ {b['odd_home']}  ➡️  投 {b['stake_home']}",
        f"  🎲 <a href='{BOOKMAKER_URLS.get(b['bm_away'],'')}'>{b['bm_away'].title()}</a> → "
        f"{html.escape(away)} @ {b['odd_away']}  ➡️  投 {b['stake_away']}",
        "",
        f"🤑 <b>ROI</b>：{b['roi']}%",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)

# ---------- 指令 ----------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 嗨！歡迎使用 <b>SureBet Radar</b> 📡\n"
        "輸入 /scan 立刻查看 ROI 最高的套利！",
        parse_mode="HTML",
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🛠 <b>指令列表</b>\n"
        "/start – 打招呼\n"
        "/help  – 本說明\n"
        "/scan  – 搜尋「ROI 最高且最近開賽」的 5 筆套利\n"
        "/sport – 查看目前有開賽的追蹤聯盟\n"
        "/bookies – 友善莊家名單\n\n"
        "⚠️ 機器人只顯示 ROI>0 的前 5 筆，若無結果代表暫時沒有套利！",
        parse_mode="HTML",
    )

async def cmd_bookies(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤝 <b>友善莊家</b>\n" + "\n".join(f"• {b.title()}" for b in BOOKMAKER_URLS),
        parse_mode="HTML",
    )

async def cmd_sport(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        active = active_tracked_sports()
        if not active:
            await update.message.reply_text("😴 目前追蹤聯盟皆休季或尚未掛盤。")
            return
        txt = "📅 <b>目前開賽聯盟</b>\n" + "\n".join(
            f"• {title} ({key})" for key, title in active
        )
        await update.message.reply_text(txt, parse_mode="HTML")
    except Exception as exc:                                    # noqa: BLE001
        logger.exception("sport cmd error: %s", exc)
        await update.message.reply_text(f"⚠️ 讀取運動列表時發生錯誤：{exc}")

async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    wait = await update.message.reply_text("🔍 正在掃描最新套利，請稍候…")
    try:
        bets = top_surebets(total_stake=DEFAULT_STAKE)
        if not bets:
            await wait.edit_text("🙈 暫時沒有符合條件的套利，稍後再試！")
            return
        await wait.edit_text(
            "\n\n".join(_fmt(b) for b in bets),
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
    except requests.exceptions.Timeout:
        await wait.edit_text("⏰ Odds API 逾時，稍後再試！")
    except Exception as exc:                                    # noqa: BLE001
        logger.exception("scan error: %s", exc)
        await wait.edit_text(f"⚠️ 執行時發生錯誤：{exc}")

async def cmd_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("指令無法識別，請 /help 查看。")

# ---------- 啟動 ----------
def start_bot_polling() -> None:
    if not BOT_TOKEN:
        logger.error("環境變數 TELEGRAM_BOT_TOKEN 未設定，Bot 無法啟動")
        return

    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("scan",  cmd_scan))
    app.add_handler(CommandHandler("sport", cmd_sport))
    app.add_handler(CommandHandler("bookies", cmd_bookies))
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))  # fallback

    logger.info("🚀 Telegram Bot polling running…")
    app.run_polling(stop_signals=None)
