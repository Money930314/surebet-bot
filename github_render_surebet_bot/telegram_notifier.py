"""telegram_notifier.py
兩層功能：
1. 被主程式呼叫 `notify_telegram(match)` → 推播單一 surebet
2. 啟動一個 Telegram Bot (`/start /help /roi`) 供使用者互動查詢
"""
import os
import logging
import textwrap
from typing import Dict, Any, List

import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # 可選：推播用；指令互動不需要固定 chat_id

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# 共用：格式化訊息
# ---------------------------------------------------------------------------

def _format_match(match: Dict[str, Any]) -> str:
    lines = [
        f"🏅 *{match['sport']}* - {match['league']}",
        f"{match['home_team']} vs {match['away_team']}",
        "",
    ]
    for bet in match["bets"]:
        lines.append(f"{bet['bookmaker']} @{bet['odds']} → 投 {bet['stake']}")
    lines.append("")
    lines.append(f"ROI: {match['roi']}%  預期獲利: {match['profit']}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# 1) 推播給固定 chat_id
# ---------------------------------------------------------------------------

def send_message(token: str, chat_id: str, match: Dict[str, Any]) -> bool:
    text = _format_match(match)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }, timeout=10)
    ok = resp.status_code == 200 and resp.json().get("ok")
    if ok:
        logger.info("✅ Telegram 訊息發送成功")
    else:
        logger.error("❌  Telegram 發送失敗 %s", resp.text[:200])
    return ok

def notify_telegram(match: Dict[str, Any]):
    if BOT_TOKEN and CHAT_ID:
        send_message(BOT_TOKEN, CHAT_ID, match)

# ---------------------------------------------------------------------------
# 2) Telegram Bot 指令互動
# ---------------------------------------------------------------------------
async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! 我是 Surebet Bot，輸入 /roi 可取得目前 ROI 最高的套利組合，或 /help 看指令。"
    )

async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(textwrap.dedent(
        """可用指令：
        /roi          ➜ 取得 ROI 最高的 5 筆 Surebet
        /roi <sport>  ➜ 只看指定運動（如 soccer、basketball）
        /help         ➜ 這段說明
        """
    ))

from scraper import fetch_surebets  # 避免循環 import 放後面

async def _cmd_roi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    sport_filter = args[0] if args else None
    bets: List[Dict[str, Any]] = fetch_surebets()
    if sport_filter:
        bets = [b for b in bets if sport_filter.lower() in b["sport"].lower()]
    bets = bets[:5]
    if not bets:
        await update.message.reply_text("目前沒有符合條件的套利機會 🙇‍♂️")
        return
    for match in bets:
        await update.message.reply_text(_format_match(match), parse_mode=ParseMode.MARKDOWN)

async def _unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("指令未支援，請輸入 /help 查看。")

# ---------------------- 啟動 polling (給 main.py 呼叫) ----------------------

def start_bot_polling():
    if not BOT_TOKEN:
        logger.warning("未設定 TELEGRAM_BOT_TOKEN，跳過 Bot Polling")
        return
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("roi", _cmd_roi))
    app.add_handler(CommandHandler(None, _unknown))  # fallback

    logger.info("🚀 Telegram Bot polling 開始…")
    app.run_polling()
