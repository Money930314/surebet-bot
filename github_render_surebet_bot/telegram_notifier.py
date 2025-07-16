import os
import html
import asyncio
import logging
import datetime as _dt
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

logger = logging.getLogger("telegram_notifier")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DEFAULT_STAKE = 100.0
DEFAULT_DAYS = 2
MAX_DAYS = 60

BOOKMAKER_URLS = {
    "pinnacle": "https://www.pinnacle.com",
    "betfair_ex": "https://www.betfair.com/exchange",
    "smarkets": "https://smarkets.com",
}

# -----------------------------------------------------------
#  1) 訊息格式
# -----------------------------------------------------------
def _fmt(m: dict) -> str:
    """格式化為 Telegram <HTML> 訊息"""
    home, away = m["teams"]
    lines = [
        f"🏅 <b>{html.escape(m['sport'])}</b>",
        f"⚔️  {html.escape(home)} vs {html.escape(away)}",
    ]

    t = _dt.datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
    lines.append(f"🕒 開賽時間：{t:%Y-%m-%d %H:%M UTC}")
    lines.append("")

    b1_url = BOOKMAKER_URLS.get(m["bookie1"], "")
    b2_url = BOOKMAKER_URLS.get(m["bookie2"], "")
    lines.append(
        f"🎲 <a href='{b1_url}'>{html.escape(m['bookie1'].title())}</a> @ {m['odd1']} → 投 {m['stake1']}"
    )
    lines.append(
        f"🎲 <a href='{b2_url}'>{html.escape(m['bookie2'].title())}</a> @ {m['odd2']} → 投 {m['stake2']}"
    )
    lines.append("")
    lines.append(f"💰 ROI：{m['roi']}% | 預期獲利：{m['profit']}")
    return "\n".join(lines)


# -----------------------------------------------------------
#  2) 指令處理
# -----------------------------------------------------------
def _parse_roi_args(cmd: str, words: List[str]) -> Tuple[float, int, List[str]]:
    """
    解析 /roi 指令：
        /roi soccer 150 7   → sport=soccer, stake=150, days=7
        /roibasketball 200  → sport=basketball, stake=200, days=DEFAULT_DAYS
        /roi 300            → 無 sport, stake=300
    """
    stake = DEFAULT_STAKE
    days = DEFAULT_DAYS
    sport = None

    # roisoccer  /roibasketball…
    if cmd.startswith("roi") and len(cmd) > 3:
        sport = cmd[3:]

    # 逐字解析
    for w in words:
        if w.isalpha() and not sport:
            sport = w
        elif w.replace(".", "", 1).isdigit():            # 數字
            if stake == DEFAULT_STAKE:
                stake = float(w)
            else:
                days = int(float(w))

    if days < 1:
        days = DEFAULT_DAYS
    if days > MAX_DAYS:
        days = MAX_DAYS

    sports = []
    if sport:
        sports.append(SPORT_GROUPS.get(sport.lower(), [sport])[0])

    return stake, days, sports


async def _cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 嗨，您好！\n\n"
        "<b>SureBet Radar</b> 📡 — 你的即時套利雷達！\n"
        "輸入 /help 查看指令，或直接 /scan 試試吧！",
        parse_mode="HTML",
    )


async def _cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sports_list = ", ".join(sorted(SPORT_GROUPS.keys()))
    await update.message.reply_text(
        "🛠 <b>使用說明</b>\n"
        "/start – 打招呼並初始化\n"
        "/help – 查看說明\n"
        "/scan – 等同 /roi（抓預設 2 天）\n"
        "/roi [運動] [總注] [天數] – 查即時套利\n"
        "  例：/roi soccer 150 7\n"
        "/bookies – 友善莊家名單\n\n"
        f"支援運動：{sports_list}",
        parse_mode="HTML",
    )


async def _cmd_bookies(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤝 友善莊家：\n" + "\n".join(f"• {k.title()}" for k in BOOKMAKER_URLS), parse_mode="HTML"
    )


async def _cmd_roi(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cmd = update.message.text.split()[0][1:]
    stake, days, sports = _parse_roi_args(cmd, update.message.text.split()[1:])

    matches = fetch_surebets(
        sports=sports, total_stake=stake, days_window=days
    )[:5]

    if not matches:
        await update.message.reply_text(
            "😔 找不到符合條件的套利，可能 API 目前無盤口或配額不足，再試其他運動 / 天數！"
        )
        return

    for m in matches:
        await update.message.reply_text(
            _fmt(m), parse_mode="HTML", disable_web_page_preview=False
        )


async def _unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("指令無法識別，請 /help 查看。")


# -----------------------------------------------------------
#  3) 啟動 polling
# -----------------------------------------------------------
def start_bot_polling() -> None:
    if not (BOT_TOKEN and CHAT_ID):
        logger.warning("Telegram Bot token 或 chat_id 未設定，Bot 不啟動")
        return

    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("scan", _cmd_roi))
    app.add_handler(CommandHandler("bookies", _cmd_bookies))
    app.add_handler(CommandHandler("roi", _cmd_roi))

    # 快捷 /roisoccer, /roibasketball…
    for g in SPORT_GROUPS:
        app.add_handler(CommandHandler(f"roi{g}", _cmd_roi))

    app.add_handler(MessageHandler(filters.COMMAND, _unknown))
    logger.info("🚀 Telegram Bot polling 開始…")
    app.run_polling(stop_signals=None)
