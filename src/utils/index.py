'''
Date: 2025-02-21 10:56:53
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-05-09 16:02:53
FilePath: /team-bot/jx3-team-bot/src/utils/index.py
'''
import json
import base64
import requests
from typing import Any, List, Dict, Optional
from src.config import STATIC_PATH


def find_earliest_team(teams: List[Dict[str, Any]], filterName:str) -> Optional[Dict[str, Any]]:
    """
    在列表中查找非 team_name 为 filterName 的其他团队，
    若存在，则返回最早创建的团队信息；若没有，则返回 None。
    :param teams: 包含团队信息的列表，每个团队是一个字典
    :return: 最早创建的团队信息，或 None
    """
    # 过滤掉 team_name 为 'A' 的团队
    filtered_teams = [team for team in teams if team.get("team_name") != filterName]
    
    if not filtered_teams:
        return None  # 如果没有符合条件的团队，返回 None

    # 找到最早创建的团队
    earliest_team = min(filtered_teams, key=lambda team: team.get("timestamp", float("inf")))
    
    return earliest_team

def find_id_by_team_name(team_list, target_team_name):
    """
    在列表中查找指定 teamName 的数据并返回 id
    :param team_list: 包含字典的列表
    :param target_team_name: 要查找的 teamName
    :return: 对应的 id 或 None（如果未找到）
    """
    for team in team_list:
        if team.get("team_name") == target_team_name:
            return team.get("id")
    return None

def find_default_team(team_list):
    """
    在列表中查找指定 teamName 的数据并返回 id
    :param team_list: 包含字典的列表
    :return: 对应的 team 或 None（如果未找到）
    """
    for team in team_list:
        if team.get("team_default") == 1:
            return team
    return None

def format_teams(teams):
    """
    将团队信息拼接成指定格式的字符串。
    :param teams: 包含团队信息的列表
    :return: 格式化后的字符串
    """
    formatted_teams = []
    for team in teams:
        team_name = team['team_name']
        team_id = team['id']
        default_status = "（默认团队）" if team['team_default'] == 1 else ""
        formatted_teams.append(f"团队名称：{team_name}，编号为：{team_id}{default_status}；")
    
    return "\n".join(formatted_teams)





# 从 JSON 文件加载数据
def load_professions_from_json(file_path: str) -> dict:
    """从 JSON 文件加载心法名称到编码的映射"""
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return {value: key for key, value in data.items()}  # 创建名称到编码的映射

file_path = f"{STATIC_PATH}/xfid.json"

# 加载 JSON 数据
name_to_code_dict = load_professions_from_json(file_path)

# 获取编码的函数
def get_code_by_name(name: str) -> Optional[str]:
    """通过名称获取编码"""
    return name_to_code_dict.get(name)


# 从 JSON 文件加载数据
def load_json(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data

file_xf_path = f"{STATIC_PATH}/mount_equip.json"

# 加载 JSON 数据
mount_group_dict = load_json(file_xf_path)

# 查询函数
def get_info_by_id(id: int) -> str:
    """通过 id 获取分类"""
    return mount_group_dict.get(id)

def render_team_template():
    # 读取颜色配置文件
    with open(f'{STATIC_PATH}/colors.json', 'r', encoding='utf-8') as f:
        colors_config = json.load(f)
    return colors_config


def upload_image(image_path: str) -> str:
    """
    上传图片到图床并返回 URL
    TODO 缺少登录
    """
    url = "https://sm.ms/api/v2/upload"
    with open(image_path, "rb") as file:
        response = requests.post(url, files={"smfile": file})
        result = response.json()
        if result["code"] == "success":
            return result["data"]["url"]
        else:
            raise Exception(f"图片上传失败: {result['message']}")
        
def path_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as file:
        base64_data = base64.b64encode(file.read()).decode("utf-8")
        image_segment = f"base64://{base64_data}"
        return image_segment


def format_daily_data(data: dict) -> str:
    """格式化日常数据"""
    # 构建格式化字符串
    formatted = f"{data['date']}星期{data['week']}\n"
    formatted += f"大战：{data['war']}\n"
    formatted += f"战场：{data['battle']}\n"
    formatted += f"宗门：{data['school']}\n"
    formatted += f"画像：{data['draw']}\n" 
    formatted += f"福缘：{','.join(data['luck'])}\n"
    formatted += f"驰援：{data['rescue']}\n"
    
    # 家园声望
    formatted += "【家园声望·加倍道具】\n"
    formatted += f"{','.join(data['card'])}\n"
    
    # 武林通鉴相关任务
    team_tasks = data['team']
    if len(team_tasks) >= 2:
        formatted += "【武林通鉴·公共任务】\n"
        formatted += f"{team_tasks[0]}\n"
        
        formatted += "【武林通鉴·秘境任务】\n"
        formatted += f"{team_tasks[1]}\n"
        
        formatted += "【武林通鉴·团队秘境】\n"
        formatted += f"{team_tasks[2]}"
    
    return formatted


def format_role_data(data: dict) -> str:
    """格式化角色详情数据"""
    # 构建格式化字符串
    formatted = f"【角色】{data['roleName']}\n"
    formatted += f"【归属】{data['serverName']}·{data['campName']}\n"
    formatted += f"【门派】{data['forceName']}·{data['bodyName']}\n" 
    formatted += f"【帮会】{data['tongName']}\n"
    formatted += f"【uid】{data['roleId']}\n"
    formatted += f"【全服uid】{data['globalRoleId']}"
    
    return formatted

def generate_team_stats(memberslist: List[Dict[str, Any]], team: dict) -> str:
    """生成团队统计信息"""
    members = memberslist
    total = len(members)
    remaining = 25 - total  # 假设总坑位为25
    
    role_counts = {
        '外功': 0,
        '内功': 0,
        '治疗': 0, 
        '坦克': 0,
    }
    
    for member in members:
        duty = member.get('xf_duty')
        if duty in role_counts:
            role_counts[duty] += 1
            
    return (
        f"当前团队：[ {team['team_name']} ]\n"
        f"剩余 {remaining} 个坑位\n"
        f"外功已有：{role_counts['外功']} 人\n"
        f"内功已有：{role_counts['内功']} 人\n"
        f"奶妈已有：{role_counts['治疗']} 人\n"
        f"坦克已有：{role_counts['坦克']} 人\n"
    )

# 将十六进制颜色转换为RGB值
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# 将RGB值转换回十六进制颜色
def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

# 加深颜色
def darken_color(hex_color, factor=0.7):
    rgb = hex_to_rgb(hex_color)
    darkened = tuple(int(c * factor) for c in rgb)
    return rgb_to_hex(darkened)