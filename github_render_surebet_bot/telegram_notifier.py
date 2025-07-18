# -*- coding: utf-8 -*-
"""
telegram_notifier.py  (2025‑07‑18)
新增：
1. /bookies 連結化
2. /quota 指令 – 查 The‑Odds‑API 剩餘額度
3. /help 更新
"""
from __future__ import annotations
import os, html, logging, asyncio, requests
import datetime as _dt
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters,
)
from scraper import top_surebets, get_api_quota, _active_sport_keys

# ---------- 基本設定 ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg_bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_STAKE = 100.0

BOOKMAKER_URLS: dict[str, str] = {
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

    return "\n".join([
        "📣 <b>Surebet 速報</b> 🔥",
        f"🏟️ <b>{html.escape(b['sport'])}</b>",
        f"⚔️  {html.escape(home)}  vs  {html.escape(away)}",
        f"🗓️  {t}",
        "",
        "💰 <b>下注分配</b>",
        f"  🎲 <a href='{BOOKMAKER_URLS.get(b['bm_home'],'')}'>{b['bm_home'].title()}</a> "
        f"→ {html.escape(home)} @ {b['odd_home']}  ➡️  投 {b['stake_home']}",
        f"  🎲 <a href='{BOOKMAKER_URLS.get(b['bm_away'],'')}'>{b['bm_away'].title()}</a> "
        f"→ {html.escape(away)} @ {b['odd_away']}  ➡️  投 {b['stake_away']}",
        "",
        f"🤑 <b>ROI</b>：{b['roi']}%",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ])

# ---------- 指令 ----------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:      # noqa: D401
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
        "/scan  – 搜尋 ROI 最高的套利\n"
        "/sport – 查看目前開賽聯盟\n"
        "/bookies – 友善莊家名單\n"
        "/quota – 查看 The‑Odds‑API 剩餘額度",
        parse_mode="HTML",
    )

async def cmd_bookies(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [
        "🤝 <b>友善莊家</b>",
        *(
            f"• <a href='{url}'>{name.title()}</a>"
            for name, url in BOOKMAKER_URLS.items()
        ),
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def cmd_sport(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    active = _active_sport_keys()
    if not active:
        await update.message.reply_text("😴 目前沒有掛盤的聯盟。")
        return
    await update.message.reply_text(
        "📅 <b>目前開賽聯盟（前 20 筆）</b>\n" +
        "\n".join(f"• {k}" for k in active[:20]),
        parse_mode="HTML",
    )

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
    except Exception as exc:                         # noqa: BLE001
        logger.exception("scan error: %s", exc)
        await wait.edit_text(f"⚠️ 執行時發生錯誤：{exc}")

# --- NEW: /quota 指令 ----------------------------------
async def cmd_quota(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    remaining, used = get_api_quota()
    if remaining is None:
        await update.message.reply_text("⚠️ 無法取得 API 配額，請確認 API_KEY 是否設定正確。")
        return
    await update.message.reply_text(
        f"📊 <b>The‑Odds‑API 使用情況</b>\n"
        f"剩餘查詢次數：{remaining}\n"
        f"已用查詢次數：{used}",
        parse_mode="HTML",
    )

async def cmd_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("指令無法識別，請 /help 查看。")

# ---------- 啟動 ----------
def start_bot_polling() -> None:
    if not BOT_TOKEN:
        logger.error("環境變數 TELEGRAM_BOT_TOKEN 未設定，Bot 無法啟動")
        return

    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("scan",   cmd_scan))
    app.add_handler(CommandHandler("sport",  cmd_sport))
    app.add_handler(CommandHandler("bookies", cmd_bookies))
    app.add_handler(CommandHandler("quota",  cmd_quota))       # --- NEW
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    logger.info("🚀 Telegram Bot polling running…")
    app.run_polling(stop_signals=None)
