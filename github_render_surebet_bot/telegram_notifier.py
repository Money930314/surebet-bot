"""telegram_notifier.py
1. `notify_telegram(match)`：推播單一 surebet 給固定 chat_id。
2. Telegram Bot：支援 /start /help /roi 指令。
   * 使用 HTML `<pre>` 包裝純文字，並明確傳 `parse_mode='HTML'`，避免預設 Markdown 造成 400。
   * 在獨立 thread 中手動建立 asyncio event loop，解決 `RuntimeError: There is no current event loop`。
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
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # 推播用；互動不需固定 chat_id
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ------------------ 共用：格式化訊息 ------------------

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
    return "
".join(lines)

# ------------------ 推播 ------------------

def send_message(token: str, chat_id: str, match: Dict[str, Any]) -> bool:
    text_plain = _format_match_plain(match)
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

def notify_telegram(match: Dict[str, Any]):
    if BOT_TOKEN and CHAT_ID:
        send_message(BOT_TOKEN, CHAT_ID, match)

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

from scraper import fetch_surebets  # 避免循環 import

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
    if not BOT_TOKEN:
        logger.warning("未設定 TELEGRAM_BOT_TOKEN，跳過 Bot Polling")
        return

    # 在線程內手動建立 event loop
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("roi", _cmd_roi))
    app.add_handler(MessageHandler(filters.COMMAND, _unknown))  # 其他指令

    logger.info("🚀 Telegram Bot polling 開始…")
    app.run_polling()
