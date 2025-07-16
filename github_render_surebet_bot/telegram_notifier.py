import os
import requests
import logging

logger = logging.getLogger(__name__)

# 建議函數：發送單筆套利機會訊息
def send_message(bot_token: str, chat_id: str, match: dict) -> bool:
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
🔗 詳情連結：{match.get('url', 'N/A')}
✅ 請盡快下單套利！
"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message.strip(), "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        if resp.status_code == 200:
            logger.info("✅ Telegram 訊息發送成功")
            return True
        else:
            logger.error(f"❌ Telegram API 錯誤: {resp.status_code} - {resp.text}")
            return False
    except requests.RequestException as e:
        logger.error(f"❌ 網路錯誤: {e}")
        return False

# 格式化多筆套利資料為單一訊息
def format_surebet_message(matches: list[dict]) -> str:
    if not matches:
        return "❌ 目前沒有符合條件的套利機會\n\n💡 可能原因：\n• 市場波動較小\n• 博彩公司調整及時\n• 網站暫時無法訪問\n\n🔄 建議稍後再試或調整搜尋條件"
    matches = sorted(matches, key=lambda x: x['roi'], reverse=True)
    header = f"🎯 找到 {len(matches)} 筆套利機會！\n{'='*30}\n"
    messages = []
    total_profit = 0.0
    for i, match in enumerate(matches, 1):
        bets = '\n'.join([
            f"  💳 {bets['bookmaker']}: {bets['odds']} → ${bets['stake']}" for bets in match['bets']
        ])
        total_profit += match['profit']
        icon = get_sport_icon(match['sport'])
        messages.append(
            f"{i}. {icon} {match['sport']} - {match['home_team']} vs {match['away_team']}\n"
            f"⏰ {match['match_time']}\n"
            f"📊 ROI: {match['roi']}% | 利潤: ${match['profit']}\n"
            f"💰 投注分配:\n{bets}\n"
        )
    full = header + '\n'.join(messages)
    # 簡化截斷
    return full

# 簡易發送文字訊息（給 Flask 端測試等用途）
def send_message_simple(message_text: str) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        logger.error("❌ 缺少 Telegram 環境變數")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message_text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        return resp.status_code == 200
    except requests.RequestException:
        return False

# 發送錯誤通知
def send_error_notification(error_message: str) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return False
    msg = f"🚨 系統錯誤通知\n\n❌ 錯誤描述: {error_message}\n🕒 時間: {get_current_time()}"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    try:
        return requests.post(url, data=data, timeout=10).status_code == 200
    except:
        return False

# 新增：讓 main.py 可以 import

def notify_telegram(match: dict) -> bool:
    """Wrapper: 發送單筆 match dict"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        logger.error("❌ 缺少 Telegram 環境變數")
        return False
    return send_message(bot_token, chat_id, match)

# 運動圖標對應
def get_sport_icon(sport: str) -> str:
    icons = {
        'Soccer':'⚽','Football':'⚽','Basketball':'🏀','Tennis':'🎾',
        'Baseball':'⚾','Volleyball':'🏐','Hockey':'🏒','Golf':'⛳','Boxing':'🥊','Racing':'🏁'
    }
    return icons.get(sport, '🏆')

# 取得當前時間文字
def get_current_time() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
