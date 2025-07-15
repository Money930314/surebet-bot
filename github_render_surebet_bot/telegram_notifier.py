import requests
import logging

logger = logging.getLogger(__name__)

def send_message(bot_token, chat_id, match):
    """發送單筆套利機會訊息"""
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
    
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Telegram 訊息發送成功")
            return True
        else:
            logger.error(f"❌ Telegram API 錯誤: {response.status_code} - {response.text}")
            return False
    except requests.RequestException as e:
        logger.error(f"❌ 網路錯誤: {e}")
        return False

def format_surebet_message(matches):
    """格式化多筆套利資料為單一訊息"""
    if not matches:
        return "❌ 目前沒有符合條件的套利機會"
    
    header = f"🎯 找到 {len(matches)} 筆套利機會！\n{'='*30}\n"
    
    messages = []
    for i, match in enumerate(matches, 1):
        bet_info = '\n'.join([
            f"  • {bet['bookmaker']}: {bet['odds']} (${bet['stake']})"
            for bet in match['bets']
        ])
        
        message = f"""
{i}. 🏅 {match['sport']} - {match['home_team']} vs {match['away_team']}
⏰ {match['match_time']}
📊 ROI: {match['roi']}% | 利潤: ${match['profit']}
💰 投注分配:
{bet_info}
"""
        messages.append(message)
    
    # 限制訊息長度，避免 Telegram 4096 字符限制
    full_message = header + '\n'.join(messages)
    
    if len(full_message) > 4000:
        # 如果訊息太長，只顯示前幾筆
        truncated_matches = matches[:3]
        messages = []
        for i, match in enumerate(truncated_matches, 1):
            bet_info = '\n'.join([
                f"  • {bet['bookmaker']}: {bet['odds']} (${bet['stake']})"
                for bet in match['bets']
            ])
            
            message = f"""
{i}. 🏅 {match['sport']} - {match['home_team']} vs {match['away_team']}
⏰ {match['match_time']}
📊 ROI: {match['roi']}% | 利潤: ${match['profit']}
💰 投注分配:
{bet_info}
"""
            messages.append(message)
        
        footer = f"\n⚠️ 訊息過長，僅顯示前 3 筆，共 {len(matches)} 筆機會"
        full_message = header + '\n'.join(messages) + footer
    
    return full_message

def send_message_simple(message_text):
    """簡化版發送訊息（給 main.py 使用）"""
    import os
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        logger.error("❌ 缺少 Telegram 配置")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message_text
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Telegram 訊息發送成功")
            return True
        else:
            logger.error(f"❌ Telegram API 錯誤: {response.status_code}")
            return False
    except requests.RequestException as e:
        logger.error(f"❌ 網路錯誤: {e}")
        return False
