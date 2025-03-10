'''
Date: 2025-03-04 13:17:55
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-03-06 13:54:36
FilePath: /bott/bot-dd/src/utils/table_position.py
'''
from typing import Any, List, Dict, Optional

def init_table(rows: int = 5, cols: int = 5) -> List[str]:
    """
    初始化一个指定大小的团队成员表格，并生成所有位置编号的列表。
    每个位置编号由行号和列号组成，例如第一行第一列为 '11'，第二行第一列为 '12'，以此类推。
    :param rows: 表格的行数，默认为 5
    :param cols: 表格的列数，默认为 5
    :return: 包含所有位置编号的列表，例如 ['11', '12', '21', '22', ...]
    """
    if rows <= 0 or cols <= 0:
        raise ValueError("行数和列数必须为正整数")

    all_positions: List[str] = []
    for col in range(1, cols + 1):  # 列号从 1 到 cols
        for row in range(1, rows + 1):  # 行号从 1 到 rows
            all_positions.append(f"{row}{col}")  # 生成位置编号并添加到列表中
    return all_positions

def find_empyt_positions(list1: List[str], list2: List[str])-> List[str]:
    """
    找出 list2 中没有的元素，并生成一个新的列表。
    :param list1: 第一个列表
    :param list2: 第二个列表
    :return: list2 中没有的元素组成的列表
    """
    set2 = set(list2)  # 将 list2 转换为集合
    empyt_positions = [item for item in list1 if item not in set2]
    return sorted(empyt_positions, key=lambda x: int(x))
    
def get_duty_positions(duty: str) -> list:
    """
    根据心法类型返回可用的位置列表
    """
    all_positions = init_table()
    if duty == "内功":
        return [pos for pos in all_positions if pos.startswith(('1', '2'))]
    elif duty == "外功":
        return [pos for pos in all_positions if pos.startswith(('3', '4'))]
    elif duty == "坦克":
        return [pos for pos in all_positions if pos.startswith('5')]
    elif duty == "治疗":
        return [pos for pos in all_positions if pos.startswith(('5', '4'))]
    return all_positions

def find_position_by_duty(duty: str, occupied_positions: list) -> str:
    """
    根据心法类型分配位置
    """
    # 获取该心法可用的位置列表
    available_positions = get_duty_positions(duty)
    # 找出未被占用的位置
    empty_positions = [pos for pos in available_positions if pos not in occupied_positions]
    
    # 如果该心法对应区域已满
    if not empty_positions:
        # 获取所有位置
        all_positions = init_table()
        # 找出所有未被占用的位置
        empty_positions = [pos for pos in all_positions if pos not in occupied_positions]
    
    return empty_positions[0] if empty_positions else None