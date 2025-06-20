'''
Date: 2025-05-30 16:17:02
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-20 17:16:28
FilePath: /team-bot/jx3-team-bot/src/plugins/game_score.py
'''
from .database import NianZaiDB
from nonebot import on_command,on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment

db = NianZaiDB()
db.init_db()  # 确保数据库表已创建

check_score =  on_regex(pattern=r"^查询积分$", priority=5)
check_ranking =  on_regex(pattern=r"^积分排行$", priority=5)
check_score_rules = on_regex(pattern=r"^积分说明$", priority=5)
back_door_score = on_regex(pattern=r"^backdoor.*$", priority=5)


 # # 替换为你的实际user_id和group_id
    # user_id1 = "939225853"  # 例如："123456789"
    # group_id1 = "1034970817"  # 例如："987654321"

    # # 添加10000积分
    # await update_player_score(user_id1, group_id1, 10000, "开发者奖励", "开发者", "系统奖励")

async def update_player_score(user_id: str, group_id: str, score_change: int, game_type: str, game_role: str = None, game_result: str = None):
    # 更新玩家总积分
    player = db.fetch_one('game_players', f"user_id = ? AND group_id = ?", (user_id, group_id))
    if not player:
        db.insert('game_players', {
            'user_id': user_id,
            'group_id': group_id,
            'total_score': score_change,
            'participation_count': 1
        })
    else:
         db.update(
                'game_players',
                {"total_score": player['total_score'] + score_change, 'participation_count': player['participation_count'] + 1},
                f"user_id = {user_id} AND group_id = '{group_id}'"
            )
        # db.update('game_players', 
        #           {'total_score': player['total_score'] + score_change,
        #            'participation_count': player['participation_count'] + 1},
        #           f"user_id = ? AND group_id = ?", (user_id, group_id))
    
    # 记录游戏记录
    db.insert('game_records', {
        'game_type': game_type,
        'user_id': user_id,
        'group_id': group_id,
        'score_change': score_change,
        'game_role': game_role,
        'game_result': game_result
    })

async def get_player_score(user_id: str, group_id: str):
    return db.fetch_one('game_players', f"user_id = ? AND group_id = ?", (user_id, group_id))

async def get_group_ranking(group_id: str, limit: int = 50):
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM game_players WHERE group_id = ? ORDER BY total_score DESC LIMIT ?",
            (group_id, limit)
        )
        rows = cursor.fetchall()
        # 获取列名
        columns = [col[0] for col in cursor.description]
        # 将结果转换为字典列表
        return [dict(zip(columns, row)) for row in rows]


@check_score.handle()
async def handle_check_score(bot: Bot, event: GroupMessageEvent):
    score_info = await get_player_score(str(event.user_id), str(event.group_id))
    if not score_info:
        await check_score.finish("您还没有参与过游戏！")
        return
    
    msg = f"您的游戏积分：\n"
    msg += f"总积分：{score_info['total_score']}\n"
    msg += f"参与游戏次数：{score_info['participation_count']}"
    await check_score.finish(msg)

@check_ranking.handle()
async def handle_check_ranking(bot: Bot, event: GroupMessageEvent):
    rankings = await get_group_ranking(str(event.group_id))
    if not rankings:
        await check_ranking.finish("暂无排行榜数据！")
        return
    
    msg = "游戏积分排行榜：\n"
    for i, player in enumerate(rankings, 1):
        user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(player['user_id']))
        msg += f"{i}. {user_info['nickname']}: {player['total_score']}分 (参与{player['participation_count']}次)\n"
    
    await check_ranking.finish(msg)

@check_score_rules.handle()
async def handle_score_rules(bot: Bot, event: GroupMessageEvent):
    rules = "游戏积分规则说明：\n"
    rules += "1. 参与游戏基础分：\n"
    rules += "   - 参与任意游戏可获得5分\n\n"
    rules += "2. 谁是卧底：\n"
    rules += "   - 平民获胜：每位平民额外获得10分\n"
    rules += "   - 卧底获胜：每位卧底额外获得15分\n\n"
    rules += "3. 21点：\n"
    rules += "   - 闲家获胜：获得10分\n"
    rules += "   - 庄家获胜：根据赢的玩家数量，每赢一人获得10分\n\n"
    rules += "4. 开口中：\n"
    rules += "   - 获胜：获得30分\n"
    rules += "   - 失败（猜中数字）：扣除50分\n\n"
    rules += "5. 俄罗斯转盘：\n"
    rules += "   - 存活到最后：获得50分\n"
    rules += "   - 中弹淘汰：扣除100分\n\n"
    rules += "6. 猜词游戏：\n"
    rules += "   - 猜中词语：获得5分\n"
    rules += "   - 成功描述（有人猜中）：获得n*5分\n\n"
    rules += "7. 猜歌游戏：\n"
    rules += "   - 答对题目：10分\n"
    rules += "8. 台词大作战：\n"
    rules += "   - 答对题目：基础3分 + 时间奖励(最高10分) + 难度奖励(1-4分)\n"
    rules += "   - 第1名：额外获得8分\n"
    rules += "   - 第2名：额外获得5分\n"
    rules += "   - 第3名：额外获得3分\n\n"
    rules += "9. 害你在心口难开：\n"
    rules += "   - 基础参与分：-10分\n"
    rules += "   - 每说一次自己的禁词：-5分\n"
    rules += "   - 每说一句超过3个字的话：+1分\n\n"
    rules += "10. 海龟汤：\n"
    rules += "   - 猜中真相：获得20分\n"
    rules += "   - 出题者（有人猜中）：获得15分\n"
    rules += "   - 参与提问：每个有效问题获得1分\n\n"
    rules += "11. 瓶子排序游戏：\n"
    rules += "   - 完成排序：基础20分 + 时间奖励(最高15分)\n"
    rules += "   - 第1名：额外获得10分\n"
    rules += "   - 第2名：额外获得6分\n"
    rules += "   - 第3名：额外获得3分\n\n"
    rules += "12. 井字棋竞猜：\n"
    rules += "   - 参与游戏：获得5分\n"
    rules += "   - 获胜：额外获得20分\n\n"
    rules += "13. 五子棋：\n"
    rules += "   - 参与游戏：获得5分\n"
    rules += "   - 获胜：额外获得25分\n"
    rules += "   - 平局：获得10分\n"
    rules += "   - 对手认输：获得30分\n\n"
    rules += "14. 狼人杀：\n"
    rules += "   - 参与游戏：获得5分\n"
    rules += "   - 村民阵营获胜：每位村民额外获得15分\n"
    rules += "   - 狼人阵营获胜：每位狼人额外获得20分\n"
    rules += "   - 存活到游戏结束：额外获得5分\n"
    rules += "   - 预言家/女巫/猎人/守卫成功使用技能：额外获得3分\n\n"
    rules += "15. 炸金花：\n"
    rules += "   - 参与游戏：获得5分\n"
    rules += "   - 获胜：额外获得20分\n"
    rules += "   - 比牌获胜：额外获得5分\n\n"
    rules += "16. 斗地主：\n"
    rules += "   - 参与游戏：获得5分\n"
    rules += "   - 地主获胜：额外获得30分\n"
    rules += "   - 农民获胜：每位农民额外获得15分\n"
    rules += "   - 春天/反春天：额外获得10分\n\n"
    rules += "17. 四川麻将血流成河：\n"
    rules += "   - 参与游戏：获得5分\n"
    rules += "   - 胡牌：基础15分\n"
    rules += "   - 自摸：额外获得5分\n"
    rules += "   - 杠牌：明杠3分，暗杠5分\n"
    rules += "   - 听牌状态：额外获得2分\n"
    rules += "   - 点炮：扣除3分\n\n"
    rules += "💡 提示：积分可通过【查询积分】和【积分排行】查看"
    
    
    await check_score_rules.finish(rules)

@back_door_score.handle()
async def handle_back_door_score(bot: Bot, event: GroupMessageEvent):
    # 检查是否为管理员或特定用户
    admin_users = ["939225853"]  # 可以添加更多管理员ID
    if str(event.user_id) not in admin_users:
        await back_door_score.finish("❌ 权限不足，无法使用此命令")
        return
    
    # 解析命令参数
    message_text = str(event.message).strip()
    
    # 如果只输入 backdoor，显示使用说明
    if message_text == "backdoor":
        usage = "🔧 后门命令使用说明：\n"
        usage += "格式：backdoor <user_id> <group_id> <score>\n"
        usage += "示例：backdoor 123456789 987654321 1000\n"
        usage += "参数说明：\n"
        usage += "- user_id: 目标用户QQ号\n"
        usage += "- group_id: 群号\n"
        usage += "- score: 积分变化（正数增加，负数减少）"
        await back_door_score.finish(usage)
        return
    
    # 解析参数
    try:
        parts = message_text.split()
        if len(parts) != 4 or parts[0] != "backdoor":
            await back_door_score.finish("❌ 参数格式错误！\n请使用：backdoor <user_id> <group_id> <score>")
            return
        
        target_user_id = parts[1]
        target_group_id = parts[2]
        score_change = int(parts[3])
        
        # 验证参数
        if not target_user_id.isdigit() or not target_group_id.isdigit():
            await back_door_score.finish("❌ user_id 和 group_id 必须为数字")
            return
        
        if abs(score_change) > 100000:  # 限制单次调整的积分范围
            await back_door_score.finish("❌ 单次积分调整不能超过100000")
            return
        
    except ValueError:
        await back_door_score.finish("❌ 积分必须为整数")
        return
    except Exception as e:
        await back_door_score.finish(f"❌ 参数解析错误：{str(e)}")
        return
    
    try:
        # 获取目标用户信息（用于显示昵称）
        try:
            user_info = await bot.get_group_member_info(group_id=int(target_group_id), user_id=int(target_user_id))
            user_nickname = user_info['nickname']
        except:
            user_nickname = f"用户{target_user_id}"
        
        # 获取调整前的积分
        before_score_info = await get_player_score(target_user_id, target_group_id)
        before_score = before_score_info['total_score'] if before_score_info else 0
        
        # 更新积分
        await update_player_score(
            user_id=target_user_id,
            group_id=target_group_id,
            score_change=score_change,
            game_type="管理员调整",
            game_role="系统",
            game_result=f"管理员{event.user_id}手动调整"
        )
        
        # 获取调整后的积分
        after_score_info = await get_player_score(target_user_id, target_group_id)
        after_score = after_score_info['total_score'] if after_score_info else score_change
        
        # 发送结果消息
        result_msg = f"✅ 积分调整成功！\n"
        result_msg += f"目标用户：{user_nickname}({target_user_id})\n"
        result_msg += f"群组：{target_group_id}\n"
        result_msg += f"积分变化：{score_change:+d}\n"
        result_msg += f"调整前积分：{before_score}\n"
        result_msg += f"调整后积分：{after_score}\n"
        result_msg += f"操作员：{event.user_id}"
        
    except Exception as e:
        await back_door_score.finish(f"❌ 积分调整失败：{str(e)}")

    await back_door_score.finish(result_msg)