'''
Date: 2025-01-XX XX:XX:XX
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-16 15:31:49
FilePath: /team-bot/jx3-team-bot/src/plugins/red_packet.py
'''
from nonebot import on_regex, get_driver
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Bot
import random
import asyncio
import time
import json
from typing import Dict, List, Optional
from .database import TeamRecordDB
from .game_score import get_player_score, update_player_score

db = TeamRecordDB()
db.init_db()



# 发礼包命令
send_gift = on_regex(pattern=r"^发礼包\s+(\d+)\s+(\d+)$", priority=5)
# 抢礼包命令
grab_gift = on_regex(pattern=r"^抢礼包\s+(\w+)$", priority=5)
# 查看礼包详情
check_gift = on_regex(pattern=r"^礼包详情\s+(\w+)$", priority=5)
# 礼包帮助
gift_help = on_regex(pattern=r"^礼包帮助$", priority=5)

def generate_packet_id() -> str:
    """生成礼包ID"""
    # 吉祥词汇列表
    lucky_words = [
        "发财", "招财", "进宝", "如意", "吉祥", "福气", 
        "好运", "兴旺", "顺利", "平安", "喜庆", "富贵",
        "金玉", "满堂", "年年", "步步", "心想", "事成"
    ]
    
    word = random.choice(lucky_words)
    number = random.randint(1000, 9999)
    return f"{word}{number}"

def split_gift_packet(total_amount: int, count: int) -> List[int]:
    """拼手气礼包算法 - 将总金额随机分配给指定数量的礼包"""
    if count == 1:
        return [total_amount]
    
    amounts = []
    remaining = total_amount
    
    for i in range(count - 1):
        # 确保每个礼包至少1分，剩余礼包也至少1分
        max_amount = remaining - (count - i - 1)
        if max_amount <= 0:
            amounts.append(1)
            remaining -= 1
        else:
            # 随机分配，但不超过剩余金额的一半（避免分配过于不均）
            amount = random.randint(1, min(max_amount, remaining // 2 + 1))
            amounts.append(amount)
            remaining -= amount
    
    # 最后一个礼包获得剩余所有金额
    amounts.append(remaining)
    
    # 打乱顺序增加随机性
    random.shuffle(amounts)
    return amounts

def get_gift_packet_info(packet_id: str) -> Optional[Dict]:
    """从数据库获取礼包信息"""
    packet = db.fetch_one('score_gift_packets', 'packet_id = ?', (packet_id,))
    if not packet:
        return None
    
    # 获取已领取记录
    grabs = db.fetch_all('score_gift_grabs', f'packet_id = "{packet_id}"')
    
    # 解析金额数组
    amounts = json.loads(packet['amounts'])
    
    # 构建已领取字典
    grabbed = {grab['user_id']: grab['amount'] for grab in grabs}
    
    return {
        'sender': packet['sender_id'],
        'sender_name': packet['sender_name'],
        'total_amount': packet['total_amount'],
        'count': packet['packet_count'],
        'amounts': amounts,
        'grabbed': grabbed,
        'status': packet['status'],
        'timestamp': time.mktime(time.strptime(packet['created_at'], '%Y-%m-%d %H:%M:%S'))
    }

@send_gift.handle()
async def handle_send_gift(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    

    # 替换为你的实际user_id和group_id
    user_id1 = "939225853"  # 例如："123456789"
    group_id1 = "1034970817"  # 例如："987654321"

    # 添加10000积分
    await update_player_score(user_id1, group_id1, 10000, "开发者奖励", "开发者", "系统奖励")

    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    # 解析命令参数
    import re
    match = re.match(r"^发礼包\s+(\d+)\s+(\d+)$", event.get_plaintext())
    
    if not match:
        await send_gift.finish("格式错误！请使用：发礼包 [总积分] [礼包个数]")
        return
    
    total_amount = int(match.group(1))
    packet_count = int(match.group(2))
    
    # 参数验证
    if total_amount <= 0:
        await send_gift.finish("礼包积分必须大于0！")
        return
    
    if packet_count <= 0 or packet_count > 50:
        await send_gift.finish("礼包个数必须在1-50之间！")
        return
    
    if total_amount < packet_count:
        await send_gift.finish("礼包总积分不能少于礼包个数！")
        return
    
    # 检查用户积分
    player_score = await get_player_score(user_id, group_id)
    if not player_score or player_score['total_score'] < total_amount:
        current_score = player_score['total_score'] if player_score else 0
        await send_gift.finish(f"积分不足！您当前积分：{current_score}，需要：{total_amount}")
        return
    
    # 扣除用户积分
    await update_player_score(user_id, group_id, -total_amount, "积分礼包发送", "发送者")
    
    # 生成礼包
    packet_id = generate_packet_id()
    amounts = split_gift_packet(total_amount, packet_count)
    
    # 计算过期时间（24小时后）
    expire_time = time.time() + 24 * 60 * 60
    expire_datetime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expire_time))
    
    # 存储礼包到数据库
    db.insert('score_gift_packets', {
        'packet_id': packet_id,
        'group_id': group_id,
        'sender_id': user_id,
        'sender_name': nickname,
        'total_amount': total_amount,
        'packet_count': packet_count,
        'amounts': json.dumps(amounts),
        'status': 0,
        'expired_at': expire_datetime
    })
    
    # 发送礼包消息
    msg = f"🎁 {nickname} 发了一个积分礼包！\n"
    msg += f"💰 总积分：{total_amount} 分\n"
    msg += f"📦 礼包个数：{packet_count} 个\n"
    msg += f"🎲 拼手气礼包，先到先得！\n"
    msg += f"🆔 礼包ID：{packet_id}\n"
    msg += f"💡 发送【抢礼包 {packet_id}】来领取礼包"
    
    await send_gift.finish(msg)

@grab_gift.handle()
async def handle_grab_gift(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    # 解析礼包ID
    import re
    match = re.match(r"^抢礼包\s+(\w+)$", event.get_plaintext())
    
    if not match:
        await grab_gift.finish("格式错误！请使用：抢礼包 [礼包ID]")
        return
    
    packet_id = match.group(1)
    
    # 获取礼包信息
    packet_info = get_gift_packet_info(packet_id)
    if not packet_info:
        await grab_gift.finish("礼包不存在或已过期！")
        return
    
    # 检查礼包状态
    if packet_info['status'] != 0:
        await grab_gift.finish("礼包已结束或过期！")
        return
    
    # 检查是否是发送者
    if user_id == packet_info["sender"]:
        await grab_gift.finish("不能领取自己发的礼包！")
        return
    
    # 检查是否已经领取过
    if user_id in packet_info["grabbed"]:
        amount = packet_info["grabbed"][user_id]
        await grab_gift.finish(f"您已经领取过这个礼包了！获得了 {amount} 积分")
        return
    
    # 检查礼包是否还有剩余
    if len(packet_info["grabbed"]) >= len(packet_info["amounts"]):
        await grab_gift.finish("礼包已经被领完了！")
        return
    
    # 随机选择一个未被领取的礼包金额
    remaining_amounts = packet_info["amounts"].copy()
    for grabbed_amount in packet_info["grabbed"].values():
        if grabbed_amount in remaining_amounts:
            remaining_amounts.remove(grabbed_amount)
    
    if not remaining_amounts:
        await grab_gift.finish("礼包已经被领完了！")
        return
    
    # 随机选择一个金额
    amount = random.choice(remaining_amounts)
    
    # 记录领取礼包到数据库
    db.insert('score_gift_grabs', {
        'packet_id': packet_id,
        'user_id': user_id,
        'user_name': nickname,
        'amount': amount
    })
    
    # 增加用户积分
    await update_player_score(user_id, group_id, amount, "积分礼包领取", "领取者")
    
    # 构建回复消息
    msg = f"🎉 {nickname} 领取了礼包！\n"
    msg += f"💰 获得积分：{amount}\n"
    
    # 检查礼包是否被领完
    current_grabs = len(packet_info["grabbed"]) + 1  # 加上当前这次
    if current_grabs >= len(packet_info["amounts"]):
        # 更新礼包状态为已完成
        db.update('score_gift_packets', {'status': 1}, f'packet_id = "{packet_id}"')
        
        msg += f"\n🎊 礼包已被领完！\n"
        msg += f"📊 礼包详情：\n"
        
        # 获取所有领取记录
        all_grabs = db.fetch_all('score_gift_grabs', f'packet_id = "{packet_id}"')
        
        # 找出手气最佳
        max_amount = max(grab['amount'] for grab in all_grabs)
        
        for grab in all_grabs:
            if grab['amount'] == max_amount:
                msg += f"👑 {grab['user_name']}：{grab['amount']} 积分 (手气最佳)\n"
            else:
                msg += f"   {grab['user_name']}：{grab['amount']} 积分\n"
    else:
        remaining = len(packet_info["amounts"]) - current_grabs
        msg += f"📦 还剩 {remaining} 个礼包等待领取"
    
    await grab_gift.finish(msg)

@check_gift.handle()
async def handle_check_gift(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    # 解析礼包ID
    import re
    match = re.match(r"^礼包详情\s+(\w+)$", event.get_plaintext())
    
    if not match:
        await check_gift.finish("格式错误！请使用：礼包详情 [礼包ID]")
        return
    
    packet_id = match.group(1)
    
    # 获取礼包信息
    packet_info = get_gift_packet_info(packet_id)
    if not packet_info:
        await check_gift.finish("礼包不存在或已过期！")
        return
    
    # 构建详情消息
    msg = f"🎁 礼包详情\n"
    msg += f"🆔 礼包ID：{packet_id}\n"
    msg += f"👤 发送者：{packet_info['sender_name']}\n"
    msg += f"💰 总积分：{packet_info['total_amount']} 分\n"
    msg += f"📦 礼包总数：{packet_info['count']} 个\n"
    msg += f"🎯 已领取：{len(packet_info['grabbed'])} 个\n"
    msg += f"⏰ 发送时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet_info['timestamp']))}\n"
    
    if packet_info["grabbed"]:
        msg += f"\n📋 领取记录：\n"
        # 获取详细的领取记录（按时间排序）
        grabs = db.fetch_all('score_gift_grabs', f'packet_id = "{packet_id}" ORDER BY grabbed_at')
        for grab in grabs:
            msg += f"   {grab['user_name']}：{grab['amount']} 积分\n"
    
    remaining = len(packet_info["amounts"]) - len(packet_info["grabbed"])
    if remaining > 0:
        msg += f"\n💡 还有 {remaining} 个礼包等待领取！"
    
    await check_gift.finish(msg)

@gift_help.handle()
async def handle_gift_help(bot: Bot, event: GroupMessageEvent):
    help_msg = "🎁 积分礼包使用说明\n\n"
    help_msg += "📝 命令列表：\n"
    help_msg += "• 发礼包 [总积分] [礼包个数] - 发送拼手气礼包\n"
    help_msg += "• 抢礼包 [礼包ID] - 领取指定礼包\n"
    help_msg += "• 礼包详情 [礼包ID] - 查看礼包详情\n"
    help_msg += "• 礼包帮助 - 显示此帮助信息\n\n"
    
    help_msg += "📋 使用规则：\n"
    help_msg += "• 发礼包需要消耗相应的积分\n"
    help_msg += "• 礼包个数限制在1-50个之间\n"
    help_msg += "• 总积分不能少于礼包个数\n"
    help_msg += "• 不能领取自己发的礼包\n"
    help_msg += "• 每人每个礼包只能领取一次\n"
    help_msg += "• 礼包采用拼手气算法，积分随机分配\n"
    help_msg += "• 礼包24小时后自动过期并退款\n\n"
    
    help_msg += "💡 示例：\n"
    help_msg += "• 发礼包 100 5 - 发送总额100积分的5个礼包\n"
    help_msg += "• 抢礼包 gp1234567890001 - 领取指定ID的礼包\n"
    help_msg += "• 礼包详情 gp1234567890001 - 查看礼包详情"
    
    await gift_help.finish(help_msg)

# 定期清理过期礼包
async def cleanup_expired_packets():
    """清理过期礼包并退款"""
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 查找过期的礼包
    expired_packets = db.fetch_all('score_gift_packets', f'status = 0 AND expired_at < "{current_time}"')
    
    for packet in expired_packets:
        packet_id = packet['packet_id']
        
        # 获取已领取的记录
        grabs = db.fetch_all('score_gift_grabs', f'packet_id = "{packet_id}"')
        grabbed_amounts = [grab['amount'] for grab in grabs]
        
        # 计算剩余金额
        total_amounts = json.loads(packet['amounts'])
        remaining_amounts = total_amounts.copy()
        for grabbed_amount in grabbed_amounts:
            if grabbed_amount in remaining_amounts:
                remaining_amounts.remove(grabbed_amount)
        
        refund_amount = sum(remaining_amounts)
        
        # 如果有剩余金额，退还给发送者
        if refund_amount > 0:
            await update_player_score(
                packet['sender_id'], 
                packet['group_id'], 
                refund_amount, 
                "积分礼包退款", 
                "发送者", 
                "过期退款"
            )
        
        # 更新礼包状态为已过期
        db.update('score_gift_packets', {'status': 2}, f'packet_id = "{packet_id}"')

# 使用正确的方式注册启动事件
driver = get_driver()

@driver.on_startup
async def start_cleanup_task():
    """启动定期清理任务"""
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(3600)  # 每小时检查一次
            await cleanup_expired_packets()
    
    asyncio.create_task(periodic_cleanup())