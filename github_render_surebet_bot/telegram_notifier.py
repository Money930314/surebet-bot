import requests

def send_message(bot_token, chat_id, match):
    message = f"""
🏅 {match['sport']} - {match['league']}
🏟️ {match['home_team']} vs {match['away_team']}
🕒 開賽時間：{match['match_time']}

📈 套利機會（ROI：{match['roi']}%）
💸 建議下注平台與金額：
""" + '\n'.join([
    f"- {entry['bookmaker']} @ {entry['odds']} → 下注 ${entry['stake']}"
    for entry in match['bets']
]) + f"""

💰 預估利潤：${match['profit']}（{match['roi']}%）
🔗 詳情連結：{match['url']}
✅ 請盡快下單套利！
"""

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message.strip()
    }
    response = requests.post(url, data=data)
    print("📬 Telegram API 回應：", response.text)
