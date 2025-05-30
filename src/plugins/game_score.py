'''
Date: 2025-05-30 16:17:02
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-05-30 17:24:57
FilePath: /team-bot/jx3-team-bot/src/plugins/game_score.py
'''
from .database import TeamRecordDB
from nonebot import on_command,on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Bot, Message, MessageSegment

db = TeamRecordDB()
db.init_db()  # 确保数据库表已创建

check_score =  on_regex(pattern=r"^查询积分$", priority=5)
check_ranking =  on_regex(pattern=r"^积分排行$", priority=5)
check_score_rules = on_regex(pattern=r"^积分说明$", priority=5)

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

async def get_group_ranking(group_id: str, limit: int = 10):
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
    rules += "   - 失败（猜中数字）：扣除50分\n"
    
    await check_score_rules.finish(rules)