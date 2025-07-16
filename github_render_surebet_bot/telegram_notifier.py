"""telegram_notifier.py
推播 + 使用者指令互動。現在只在收到使用者指令時回覆，不主動推播賽事。
"""
import os
import logging
import textwrap
import asyncio
from html import escape
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

# ------------------ 訊息格式 ------------------

def _format_match_plain(match: Dict[str, Any]) -> str:
    lines = [
        f"🏅 {match['sport']} - {match['league']}",
        f"{match['home_team']} vs {match['away_team']}",
        "",
    ]
    for bet in match["bets"]:
        lines.append(f"{bet['bookmaker']} @ {bet['odds']} → 投 {bet['stake']}")
    lines.append("")
    lines.append(f"ROI: {match['roi']}%  預期獲利: {match['profit']}")
    return "\n".join(lines)

# ------------------ 被動推播（選填，可保留函式供未來使用） ------------------

def send_message(token: str, chat_id: str, text_plain: str) -> bool:
    html_text = f"<pre>{escape(text_plain)}</pre>"
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    ok = resp.ok and resp.json().get("ok")
    if ok:
        logger.info("✅ Telegram 訊息發送成功")
    else:
        logger.error("❌ Telegram 發送失敗 %s", resp.text[:200])
    return ok

# ------------------ Bot 指令 ------------------
async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! 我是 Surebet Bot，輸入 /roi 可取得目前 ROI 最高的套利組合，或 /help 看指令。"
    )

async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        textwrap.dedent(
            """可用指令：
/roi          ➜ 取得 ROI 最高的 5 筆 Surebet
/roi <sport>  ➜ 只看指定運動（如 soccer、basketball）
/help         ➜ 這段說明
"""
        )
    )

from scraper import fetch_surebets

async def _cmd_roi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sport_filter = context.args[0] if context.args else None
    bets: List[Dict[str, Any]] = fetch_surebets()
    if sport_filter:
        bets = [b for b in bets if sport_filter.lower() in b["sport"].lower()]
    bets = bets[:5]
    if not bets:
        await update.message.reply_text("目前沒有符合條件的套利機會 🙇‍♂️")
        return
    for match in bets:
        await update.message.reply_text(
            f"<pre>{escape(_format_match_plain(match))}</pre>", parse_mode="HTML"
        )

async def _unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("未支援的指令，請輸入 /help 查看。")

# ------------------ 啟動 polling ------------------

def start_bot_polling():
    """在子執行緒啟動 telegram polling，不註冊 signals。"""
    if not BOT_TOKEN:
        logger.warning("未設定 TELEGRAM_BOT_TOKEN，跳過 Bot Polling")
        return

    asyncio.set_event_loop(asyncio.new_event_loop())
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("roi", _cmd_roi))
    app.add_handler(MessageHandler(filters.COMMAND, _unknown))

    logger.info("🚀 Telegram Bot polling 開始…")
    app.run_polling(stop_signals=None)
