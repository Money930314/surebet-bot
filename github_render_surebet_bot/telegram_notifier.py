import requests
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_message(bot_token, chat_id, match):
    message = f"""
🏟️ {match['venue']}
📅 {match['time']}
💰 套利報酬率 {match['roi']}%
請下注 ${match['stake']}
"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, json=payload)

