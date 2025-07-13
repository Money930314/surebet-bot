import requests
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_message(match):
    message = f"""
🏟️ {match['venue']}
📅 {match['time']}
💰 套利報酬率 {match['roi']}%
請下注 ${match['stake']}
"""
