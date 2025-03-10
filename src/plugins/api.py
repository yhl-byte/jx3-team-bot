'''
Date: 2025-02-19 15:31:53
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-03-06 17:13:54
FilePath: /bott/bot-dd/src/plugins/api.py
'''
from .database import TeamRecordDB
from ..utils.table_position import init_table,find_empyt_positions,find_position_by_duty

# 初始化数据库
db = TeamRecordDB()
db.init_db()

# # 创建团队
def create_team(data):
    code = db.insert('teams', data)
    if code == -1:
        return code
    teamName = data.get('team_name')
    team = db.fetch_one('teams', f"team_name = ?", (teamName,))
    return team

# # 修改队名
def update_team_name(data, teamName):
    db.update('teams', {"team_name": data}, f"team_name = '{teamName}'")

# # 更换默认团队
def update_team_default(teamName):
    db.update('teams', {"team_default": 0}, None)
    db.update('teams', {"team_default": 1}, f"team_name = '{teamName}'")
    return db.fetch_one('teams', f"team_name = ?", (teamName,))

# # 关闭指定团队
def close_team(teamId):
    affected_rows = db.delete("teams", "id = ?", (teamId,))
    db.delete("team_member", "team_id = ?", [teamId,])
    if affected_rows > 0:
        print(f"删除成功，受影响的行数: {affected_rows}")
    elif affected_rows == 0:
        print("没有找到匹配的记录")
        return -1
    else:
        print("删除失败")
        return -1
    
# # 关闭所有团队
def clear_teams():
    db.clear_table("teams")
    code = db.clear_table("team_member")
    if code == -1:
       return code
    
# # 查看团队列表
def team_list(group_id: int) -> list:
    return db.fetch_all('teams', f"group_id = {group_id}")

# # 查看团队详情
def team_info(teamName):
    return db.fetch_one('teams', f"team_name = ?", (teamName,))

# # 查看团队详情根据id
def team_info_by_id(team_id):
    return db.fetch_one('teams', f"id = ?", (team_id,))

# # 检测当前是否有默认团队
def check_default_team_exists(group_id: int) -> bool:
    """
    检查当前群组中是否存在 team_default 为 1 的团队
    :param group_id: 群组 ID
    :return: 如果存在返回 True，否则返回 False
    """
    result =  db.fetch_one('teams', f"group_id = ? AND team_default = 1", (group_id,))
    return result


# # 报名 添加成员
def enroll_member(member):
    # 获取必要的字段
    team_id = member.get('team_id')
    xf_duty = member.get('xf_duty')
    name = member.get('role_name')

    # 校验必要字段是否存在
    if not all([team_id, xf_duty, name]):
        print("报名失败：缺少必要的字段（team_id, member_role_career, member_role_name）")
        return -1
    
    # # 查询 team_id 团队中的全部成员
    # all_user = db.fetch_all('team_member', f"team_id = {team_id}")
    # if len(all_user) == 25:
    #     print("报名失败: 当前团队已满员")
    #     return -1
    # # 查询被占用的位置
    # occupy_position = [item["table_position"] for item in all_user]
    # # 获取剩余空位
    # empty_position = find_empyt_positions(init_table(), occupy_position)
    # # 分配位置
    # position = empty_position[0]
     # 查询 team_id 团队中的全部成员
    all_user = db.fetch_all('team_member', f"team_id = {team_id}")
    if len(all_user) == 25:
        print("报名失败: 当前团队已满员")
        return -1

    # 查询被占用的位置
    occupy_position = [item["table_position"] for item in all_user]
    
    # 根据心法分配位置
    position = find_position_by_duty(xf_duty, occupy_position)

    if not position:
        print(f"团队 {team_id} 的团员 {name} 分配位置失败")
        return -1

    # 将位置信息添加到成员字典中
    member['table_position'] = position

    # 插入数据库
    code = db.insert('team_member', member)
    if code == -1:
        print(f"团队 {team_id} 的团员 {name} 插入数据库失败")
        return -1

    print(f"团队 {team_id} 的团员 {name} 已成功报名，位置: {position}")
    return 0

# # 取消报名 删除成员
def del_member(teamId, userId, agent: str = None):
    # 构造查询条件
    condition = "team_id = ? AND user_id = ?"
    params = [teamId, userId]

    if agent is not None:
        condition += " AND agent = ?"
        params.append(agent)
    else:
        # 如果 agent 为 None，匹配 agent 为 NULL 的数据
        condition += " AND agent IS NULL"
    affected_rows = db.delete("team_member", condition, params)
    if affected_rows > 0:
        print(f"删除成功，受影响的行数: {affected_rows}")
    elif affected_rows == 0:
        print("没有找到匹配的记录")
        return -1
    else:
        print("删除失败")
        return -1
    
# # 查询指定团队中的成员信息-代报名||报名。
def check_enroll(team_id: int, user_id: str = None, agent: bool | str = False):
    """
    查询指定团队中的成员信息。
    :param team_id: 团队 ID
    :param user_id: 用户 ID（可选）
    :param agent: 是否只返回有代理信息的成员（默认为 False）
    :return: 查询结果列表
    """
    # 构造查询条件
    condition = f"team_id = {team_id}"
    
    if user_id is not None:
        condition += f" AND user_id = {user_id}"
    
    if isinstance(agent, str):
        # 查询特定代理标识的成员
        condition += f" AND agent = '{agent}'"
    elif agent is True:
        # 返回所有代理成员
        condition += " AND agent IS NOT NULL"
    else:
        # 返回非代理成员
        condition += " AND agent IS NULL"
    
    # 查询团队中的全部成员
    all_user = db.fetch_all('team_member', condition)
    
    return all_user

# # 查询指定团队中的成员信息。
def check_member(team_id: int, role_name: str = None):
    """
    查询指定团队中的成员信息。
    :param team_id: 团队 ID
    :param user_id: 用户 ID（可选）
    :param role_name: 角色名称（可选）
    :return: 查询结果字典，如果没有找到则返回 None
    """
    # 构造查询条件   
    condition = f"team_id = {team_id}"

    if role_name:
        condition += f" AND role_name = '{role_name}'"
    # 查询团队中的成员
    users = db.fetch_all('team_member', condition)
    
    return users


def move_member(team_id: int, user_id: int, old_position: str, new_position: str):
    """
    移动团队成员位置
    :param team_id: 团队ID
    :param old_position: 原位置
    :param new_position: 新位置
    :return: 成功返回0，失败返回-1
    """
    try:
        # 获取要移动的成员
        member_to_move = db.fetch_one(
            'team_member', 
            f"team_id = ? AND table_position = ?", 
            (team_id, old_position)
        )
        
        if not member_to_move:
            print(f"位置 {old_position} 没有找到成员")
            return -1
            
        # 检查新位置是否已被占用
        member_in_new_pos = db.fetch_one(
            'team_member', 
            f"team_id = ? AND table_position = ?", 
            (team_id, new_position)
        )
        
        if member_in_new_pos:
            # 使用临时位置进行交换
            temp_position = "temp_pos"
            
            # 1. 将原位置成员移到临时位置
            db.update(
                'team_member',
                {"table_position": temp_position},
                f"team_id = {team_id} AND table_position = '{old_position}'"
            )
            
            # 2. 将新位置成员移到原位置
            db.update(
                'team_member',
                {"table_position": old_position},
                f"team_id = {team_id} AND table_position = '{new_position}'"
            )
            
            # 3. 将临时位置的成员移到新位置
            db.update(
                'team_member',
                {"table_position": new_position},
                f"team_id = {team_id} AND table_position = '{temp_position}'"
            )
        else:
            # 如果新位置未被占用，直接更新位置
            db.update(
                'team_member',
                {"table_position": new_position},
                f"team_id = {team_id} AND table_position = '{old_position}'"
            )
        
        return 0
        
    except Exception as e:
        print(f"移动位置失败: {str(e)}")
        return -1
