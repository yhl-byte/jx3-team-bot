from nonebot import on_regex
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Bot
import random
import asyncio
import time
from typing import Dict, List

# 存储每个群的掷骰子记录
# 格式: {group_id: {"records": [(nickname, rolls, timestamp)], "cleanup_task": task}}
group_dice_records: Dict[str, Dict] = {}

# 掷骰子命令
dice_roll = on_regex(pattern=r"^(掷骰子|roll|投骰子)(?:\s+(\d+))?(?:d(\d+))?$", priority=5)
dice_history = on_regex(pattern=r"^(骰子记录|掷骰子记录|roll记录)$", priority=5)
clear_dice = on_regex(pattern=r"^(清除骰子记录|清除掷骰子记录)$", priority=5)

@dice_roll.handle()
async def handle_dice_roll(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        nickname = user_info.get('nickname', f'用户{user_id}')
    except:
        nickname = f'用户{user_id}'
    
    # 解析命令参数
    import re
    match = re.match(r"^(掷骰子|roll|投骰子)(?:\s+(\d+))?(?:d(\d+))?$", event.get_plaintext())
    
    dice_count = 1  # 默认1个骰子
    dice_sides = 6  # 默认6面骰子
    
    if match:
        if match.group(2):
            dice_count = min(int(match.group(2)), 10)  # 最多10个骰子
        if match.group(3):
            dice_sides = min(int(match.group(3)), 100)  # 最多100面骰子
    
    # 掷骰子
    rolls = [random.randint(1, dice_sides) for _ in range(dice_count)]
    total = sum(rolls)
    current_time = time.time()
    
    # 初始化群记录
    if group_id not in group_dice_records:
        group_dice_records[group_id] = {"records": [], "cleanup_task": None}
    
    # 添加记录
    record = (nickname, rolls, current_time)
    group_dice_records[group_id]["records"].append(record)
    
    # 启动清理任务（如果还没有的话）
    if group_dice_records[group_id]["cleanup_task"] is None:
        group_dice_records[group_id]["cleanup_task"] = asyncio.create_task(
            cleanup_records(group_id)
        )
    
    # 格式化输出
    if len(rolls) == 1:
        result_msg = f"🎲 {nickname} 掷出：{rolls[0]}点"
    else:
        dice_str = " + ".join(map(str, rolls))
        result_msg = f"🎲 {nickname} 掷出：{dice_str} = {total}点"
    
    await dice_roll.finish(result_msg)

@dice_history.handle()
async def handle_dice_history(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    if group_id not in group_dice_records or not group_dice_records[group_id]["records"]:
        await dice_history.finish("📝 当前群还没有掷骰子记录")
    
    records = group_dice_records[group_id]["records"]
    current_time = time.time()
    
    # 只显示最近的10条记录
    recent_records = records[-10:] if len(records) > 10 else records
    
    history_msg = "🎲 最近的掷骰子记录：\n\n"
    
    for nickname, rolls, timestamp in recent_records:
        # 计算时间差
        time_diff = int(current_time - timestamp)
        if time_diff < 60:
            time_str = f"{time_diff}秒前"
        else:
            time_str = f"{time_diff // 60}分钟前"
        
        if len(rolls) == 1:
            roll_str = f"{rolls[0]}点"
        else:
            roll_str = f"{' + '.join(map(str, rolls))} = {sum(rolls)}点"
        
        history_msg += f"• {nickname}：{roll_str} ({time_str})\n"
    
    if len(records) > 10:
        history_msg += f"\n📊 共有 {len(records)} 条记录，仅显示最近10条"
    
    await dice_history.finish(history_msg)

@clear_dice.handle()
async def handle_clear_dice(bot: Bot, event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 检查权限（群管理员可以清除记录）
    try:
        member_info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        if member_info.get('role') not in ['admin', 'owner']:
            await clear_dice.finish("❌ 只有群管理员可以清除骰子记录")
    except:
        await clear_dice.finish("❌ 获取权限信息失败")
    
    if group_id not in group_dice_records or not group_dice_records[group_id]["records"]:
        await clear_dice.finish("📝 当前群没有掷骰子记录")
    
    # 取消清理任务
    if group_dice_records[group_id]["cleanup_task"]:
        group_dice_records[group_id]["cleanup_task"].cancel()
    
    # 清除记录
    record_count = len(group_dice_records[group_id]["records"])
    del group_dice_records[group_id]
    
    await clear_dice.finish(f"✅ 已清除 {record_count} 条掷骰子记录")

async def cleanup_records(group_id: str):
    """10分钟后自动清除记录"""
    try:
        await asyncio.sleep(600)  # 等待10分钟（600秒）
        
        if group_id in group_dice_records:
            record_count = len(group_dice_records[group_id]["records"])
            del group_dice_records[group_id]
            print(f"自动清除群 {group_id} 的 {record_count} 条掷骰子记录")
    
    except asyncio.CancelledError:
        # 任务被取消（可能是手动清除或新的掷骰子重置了计时器）
        pass
    except Exception as e:
        print(f"清理掷骰子记录时出错: {e}")