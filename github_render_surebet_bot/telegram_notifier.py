import requests
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")


def send_message(bot_token, chat_id, match):
    message = f"""\
🏐 {match['sport']} {match['league']}
🏟️ {match['venue']}
🕒 開賽時間：{match['time']}
📈 套利機會：
- {match['team1']} @ {match['odds1']} → 下注 ${match['stake1']}
- {match['team2']} @ {match['odds2']} → 下注 ${match['stake2']}
💰 預估利潤：${match['profit']}（{match['roi']}%）
✅ 請盡快下單套利！
"""
print("🔑 Token:", bot_token)
print("🆔 Chat ID:", chat_id)
print("📤 發送內容：", message)
print("📡 回傳結果：", response.text)

    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
    }
    requests.post(url, json=payload)
