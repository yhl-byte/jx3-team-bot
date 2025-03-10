'''
Date: 2025-02-21 10:56:53
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-03-06 10:38:08
FilePath: /bott/bot-dd/src/utils/index.py
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