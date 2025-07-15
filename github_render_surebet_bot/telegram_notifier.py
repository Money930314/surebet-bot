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
        "text": message.strip(),
        "parse_mode": "HTML"  # 啟用 HTML 格式
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
        return "❌ 目前沒有符合條件的套利機會\n\n💡 可能原因：\n• 市場波動較小\n• 博彩公司調整及時\n• 網站暫時無法訪問\n\n🔄 建議稍後再試或調整搜尋條件"
    
    # 按 ROI 排序
    matches = sorted(matches, key=lambda x: x['roi'], reverse=True)
    
    header = f"🎯 找到 {len(matches)} 筆套利機會！\n{'='*30}\n"
    
    messages = []
    total_profit = 0
    
    for i, match in enumerate(matches, 1):
        bet_info = '\n'.join([
            f"  💳 {bet['bookmaker']}: {bet['odds']} → ${bet['stake']}"
            for bet in match['bets']
        ])
        
        total_profit += match['profit']
        
        # 添加運動圖標
        sport_icon = get_sport_icon(match['sport'])
        
        message = f"""
{i}. {sport_icon} {match['sport']} - {match['home_team']} vs {match['away_team']}
⏰ {match['match_time']}
📊 ROI: {match['roi']}% | 利潤: ${match['profit']}
💰 投注分配:
{bet_info}
"""
        messages.append(message)
    
    # 限制訊息長度，避免 Telegram 4096 字符限制
    full_message = header + '\n'.join(messages)
    
    if len(full_message) > 3800:  # 留一些空間給統計資訊
        # 只顯示前3筆最高ROI的機會
        truncated_matches = matches[:3]
        messages = []
        total_profit = 0
        
        for i, match in enumerate(truncated_matches, 1):
            bet_info = '\n'.join([
                f"  💳 {bet['bookmaker']}: {bet['odds']} → ${bet['stake']}"
                for bet in match['bets']
            ])
            
            total_profit += match['profit']
            sport_icon = get_sport_icon(match['sport'])
            
            message = f"""
{i}. {sport_icon} {match['sport']} - {match['home_team']} vs {match['away_team']}
⏰ {match['match_time']}
📊 ROI: {match['roi']}% | 利潤: ${match['profit']}
💰 投注分配:
{bet_info}
"""
            messages.append(message)
        
        footer = f"\n⚠️ 僅顯示前 3 筆最高ROI機會（共 {len(matches)} 筆）"
        full_message = header + '\n'.join(messages) + footer
    
    # 添加統計資訊
    stats = f"""
📈 **投資統計**
• 總投資: ${400 * len(matches[:3])}
• 預估總利潤: ${total_profit:.2f}
• 平均ROI: {sum(m['roi'] for m in matches[:3])/len(matches[:3]):.1f}%

⚡️ **重要提醒**
• 套利機會稍縱即逝，請盡快行動
• 確保各平台帳戶有足夠資金
• 注意各平台投注限額

🔔 發送時間: {get_current_time()}
"""
    
    return full_message + stats

def get_sport_icon(sport):
    """根據運動類型返回對應圖標"""
    sport_icons = {
        'Soccer': '⚽',
        'Football': '⚽',
        'Basketball': '🏀',
        'Tennis': '🎾',
        'Baseball': '⚾',
        'Volleyball': '🏐',
        'Hockey': '🏒',
        'Golf': '⛳',
        'Boxing': '🥊',
        'Racing': '🏁'
    }
    return sport_icons.get(sport, '🏆')

def get_current_time():
    """獲取當前時間字符串"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        "text": message_text,
        "parse_mode": "HTML"
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

def send_error_notification(error_message):
    """發送錯誤通知"""
    import os
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        return False
    
    message = f"""
🚨 **系統錯誤通知**

❌ 錯誤描述: {error_message}
🕒 發生時間: {get_current_time()}

🔧 **建議解決方案:**
• 檢查網路連接
• 確認目標網站狀態
• 稍後重新嘗試

💡 這是自動生成的錯誤報告
"""
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except:
        return False
