import requests

def send_message(bot_token, chat_id, match):
    message = f"""📢 套利機會！

🏆 {match['sport']} - {match['league']}
🕒 {match['datetime']}
🏟️ {match['venue']}

🔢 套利報酬率：{match['roi']}%
1️⃣ {match['bookmaker1']} 賠率：{match['odds1']}
2️⃣ {match['bookmaker2']} 賠率：{match['odds2']}

🔗 {match['url']}
"""

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message.strip()
    }

    response = requests.post(url, data=data)
    print("📤 發送內容：", message)
    print("📡 回傳結果：", response.text)
