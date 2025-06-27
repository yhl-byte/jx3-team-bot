'''
Date: 2025-02-18 13:32:40
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-27 14:45:21
FilePath: /team-bot/jx3-team-bot/src/plugins/database.py
'''
# src/plugins/chat_plugin/database.py
import sqlite3
import os
from contextlib import contextmanager
from src.config import DATABASE_PATH
from typing import List, Dict, Any, Optional
from datetime import datetime

class NianZaiDB:
    def __init__(self):
        self.db_path = DATABASE_PATH

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 创建 teams 表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                team_name TEXT NOT NULL,
                team_state BOOLEAN DEFAULT 1,  -- 开启/关闭
                team_default BOOLEAN DEFAULT 1,  -- 是否默认
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # 创建 team_member 表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS team_member (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                team_id INTEGER NOT NULL,
                table_position TEXT NOT NULL,
                role_name TEXT NOT NULL,
                role_area TEXT,
                role_xf TEXT NOT NULL,
                xf_id INTEGER NOT NULL,
                xf_duty TEXT NOT NULL,
                agent TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams(id)
            )
            ''')

            # 创建 roles 表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL,
                role_area TEXT NOT NULL,
                role_career TEXT NOT NULL
            )
            ''')

            # 创建游戏玩家积分表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                total_score INTEGER DEFAULT 0,
                participation_count INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # 创建游戏记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                score_change INTEGER NOT NULL,
                game_role TEXT,
                game_result TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            # 创建黑本记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                date TEXT NOT NULL,
                role_name TEXT NOT NULL,
                dungeon_name TEXT NOT NULL,
                key_drop TEXT,
                salary_j INTEGER NOT NULL,
                salary_display TEXT NOT NULL,
                remark TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
            ''')
            # 创建玄晶记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS xuanjing_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                date TEXT NOT NULL,
                participants TEXT NOT NULL,
                price_j INTEGER NOT NULL,
                price_display TEXT NOT NULL,
                remark TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
            ''')
            # 创建插件配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS plugin_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name TEXT NOT NULL,
                group_id INTEGER NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(plugin_name, group_id)
            )
            ''')
             # 创建群组配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL UNIQUE,

                -- 报名格式配置
                is_xf_first INTEGER DEFAULT 1,  -- 1: 心法+昵称, 0: 昵称+心法

                -- 服务器配置
                default_server TEXT DEFAULT NULL,  -- 群组默认服务器
                
                -- 功能开关配置
                enable_gold_price INTEGER DEFAULT 1,  -- 是否启用金价换算
                enable_daily_query INTEGER DEFAULT 1,  -- 是否启用日常查询
                enable_role_query INTEGER DEFAULT 1,  -- 是否启用角色查询
                enable_ai_chat INTEGER DEFAULT 1,     -- 是否启用AI对话
                enable_sandbox_monitor INTEGER DEFAULT 1,  -- 是否启用沙盘记录轮询和播报
                enable_daily_broadcast INTEGER DEFAULT 0,  -- 是否启用日常播报
                -- 其他配置
                welcome_message TEXT DEFAULT NULL,    -- 入群欢迎消息
                auto_reply_keywords TEXT DEFAULT NULL, -- 自动回复关键词(JSON格式)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            # 创建金价缓存表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS gold_price_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT NOT NULL,
                date TEXT NOT NULL,
                wanbaolou_price TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(server, date)
            )
            ''')
             # 创建积分礼包表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS score_gift_packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                packet_id TEXT NOT NULL UNIQUE,
                group_id TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                total_amount INTEGER NOT NULL,
                packet_count INTEGER NOT NULL,
                amounts TEXT NOT NULL,  -- JSON格式存储金额数组
                status INTEGER DEFAULT 0,  -- 0: 进行中, 1: 已完成, 2: 已过期
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expired_at DATETIME
            )
            ''')
            
            # 创建积分礼包领取记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS score_gift_grabs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                packet_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                amount INTEGER NOT NULL,
                grabbed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (packet_id) REFERENCES score_gift_packets(packet_id)
            )
            ''')
            # 创建AI对话记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,  -- 'user' 或 'assistant'
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # 创建AI对话会话表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL UNIQUE,
                session_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            # 签到记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkin_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                checkin_date TEXT NOT NULL,
                exp_gained INTEGER DEFAULT 0,
                score_gained INTEGER DEFAULT 0,
                consecutive_days INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id, checkin_date)
            )
            ''')
            
            # 用户经验等级表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                total_exp INTEGER DEFAULT 0,
                current_level INTEGER DEFAULT 1,
                makeup_cards INTEGER DEFAULT 0,
                last_checkin_date TEXT,
                consecutive_days INTEGER DEFAULT 0,
                total_checkin_days INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id)
            )
            ''')
            # 创建宠物表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS virtual_pets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                pet_name TEXT NOT NULL,
                pet_type TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                hunger INTEGER DEFAULT 50,
                happiness INTEGER DEFAULT 50,
                cleanliness INTEGER DEFAULT 50,
                total_interactions INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id)
            )
            ''')
            
            # 创建宠物互动记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pet_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                interaction_type TEXT NOT NULL,
                result TEXT,
                score_gained INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            # 创建修仙者表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS cultivators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                realm_level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                hp INTEGER DEFAULT 100,
                max_hp INTEGER DEFAULT 100,
                mp INTEGER DEFAULT 50,
                max_mp INTEGER DEFAULT 50,
                attack INTEGER DEFAULT 10,
                defense INTEGER DEFAULT 5,
                equipped_weapon TEXT DEFAULT NULL,
                equipped_accessory TEXT DEFAULT NULL,
                last_cultivation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_battles INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id)
            )
            ''')
            
            # 创建背包表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS cultivation_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # 创建技能表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS cultivation_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                skill_level INTEGER DEFAULT 1,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id, skill_name)
            )
            ''')
            
            # 创建战斗记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS cultivation_battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                dungeon_name TEXT NOT NULL,
                monster_name TEXT NOT NULL,
                result TEXT NOT NULL,
                exp_gained INTEGER DEFAULT 0,
                score_gained INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            # 创建训练师表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_trainers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                trainer_name TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                pokeballs INTEGER DEFAULT 10,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                last_heal_time INTEGER DEFAULT 0,
                last_recovery_time INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id)
            )
            ''')
            
            # 创建精灵表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                pokemon_name TEXT NOT NULL,
                nickname TEXT,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                hp INTEGER NOT NULL,
                max_hp INTEGER NOT NULL,
                attack INTEGER NOT NULL,
                defense INTEGER NOT NULL,
                speed INTEGER NOT NULL,
                is_in_team BOOLEAN DEFAULT FALSE,
                team_position INTEGER DEFAULT NULL,
                friendship INTEGER DEFAULT 50,
                nature TEXT DEFAULT '勤奋',
                caught_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_trained TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # 创建精灵技能表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pokemon_id INTEGER NOT NULL,
                skill_name TEXT NOT NULL,
                current_pp INTEGER NOT NULL,
                max_pp INTEGER NOT NULL,
                learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pokemon_id) REFERENCES pokemon_collection(id),
                UNIQUE(pokemon_id, skill_name)
            )
            ''')
            
            # 创建战斗记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trainer1_id TEXT NOT NULL,
                trainer2_id TEXT,
                group_id TEXT NOT NULL,
                battle_type TEXT NOT NULL,
                winner_id TEXT,
                exp_gained INTEGER DEFAULT 0,
                score_gained INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            # 抽奖
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS lottery_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id, date)
            )
            ''')
            conn.commit()  

            # 升级现有表结构
            self.upgrade_group_config_table()   

    def upgrade_group_config_table(self):
        """
        升级 pokemon_trainers 表，添加 last_heal_time 和 last_recovery_time 字段
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 检查字段是否已存在
                cursor.execute("PRAGMA table_info(pokemon_trainers)")
                columns = [column[1] for column in cursor.fetchall()]
                
                # 检查并添加 last_heal_time 字段
                if 'last_heal_time' not in columns:
                    cursor.execute("""
                        ALTER TABLE pokemon_trainers 
                        ADD COLUMN last_heal_time INTEGER DEFAULT 1
                    """)
                    conn.commit()
                    print("✅ 成功添加 last_heal_time 字段")
                else:
                    print("ℹ️ last_heal_time 字段已存在")
                
                # 检查并添加 last_recovery_time 字段
                if 'last_recovery_time' not in columns:
                    cursor.execute("""
                        ALTER TABLE pokemon_trainers 
                        ADD COLUMN last_recovery_time INTEGER DEFAULT 1
                    """)
                    conn.commit()
                    print("✅ 成功添加 last_recovery_time 字段")
                else:
                    print("ℹ️ last_recovery_time 字段已存在")
                    
            except Exception as e:
                print(f"❌ 升级数据库表失败: {e}")

    def insert(self, table_name: str, data: Dict[str, Any]):
        """
        插入数据
        :param table_name: 表名
        :param data: 插入的数据，例如 {"name": "Alice", "age": 25}
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(insert_sql, tuple(data.values()))
                conn.commit()
                new_id = cursor.lastrowid
                if new_id:
                    return new_id
                else:
                    return -1
            except sqlite3.Error as e:
                print(f"插入失败: {e}")
                return -1
        

    def fetch_all(self, table_name: str, condition: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        查询所有数据
        :param table_name: 表名
        :param condition: 查询条件，例如 "age > 20"
        :return: 查询结果列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query_sql = f"SELECT * FROM {table_name}"
            if condition:
                query_sql += f" WHERE {condition}"
            cursor.execute(query_sql)
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    def fetch_one(self, table_name: str, condition: Optional[str] = None, params: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        查询单条数据
        :param table_name: 表名
        :param condition: 查询条件，例如 "id = 1"
        :return: 查询结果字典，如果没有数据则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query_sql = f"SELECT * FROM {table_name}"
            if condition:
                query_sql += f" WHERE {condition}"
            cursor.execute(query_sql, params or ())
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
            return None

    def update(self, table_name: str, data: Dict[str, Any], condition: str):
        """
        更新数据
        :param table_name: 表名
        :param data: 更新的数据，例如 {"name": "Bob"}
        :param condition: 更新条件，例如 "id = 1"
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            set_values = ', '.join([f"{key} = ?" for key in data.keys()])
            if condition:
                update_sql = f"UPDATE {table_name} SET {set_values} WHERE {condition}"
            else:
                update_sql = f"UPDATE {table_name} SET {set_values}"
            cursor.execute(update_sql, tuple(data.values()))
            conn.commit()
            

    def delete(self, table_name: str, condition: str, params: Optional[tuple] = None) -> int:
        """
        删除数据
        :param table_name: 表名
        :param condition: 删除条件，例如 "id = ?"
        :param params: 条件参数，例如 (1,)
        :return: 受影响的行数，如果失败返回 -1
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 构建 DELETE 语句
                delete_sql = f"DELETE FROM {table_name} WHERE {condition}"
                # 执行 DELETE 操作
                cursor.execute(delete_sql, params or ())
                conn.commit()
                # 返回受影响的行数
                return cursor.rowcount
            except sqlite3.Error as e:
                print(f"删除失败: {e}")
                return -1
    def clear_table(self,table_name: str,) -> int:
        """
        清空teams表数据
        :return: 受影响的行数，如果失败返回 -1
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 删除表中的所有数据
                cursor.execute(f"DELETE FROM {table_name};")
                # 重置自增主键
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name = '{table_name}';")
                conn.commit()
                print("表 'teams' 中的数据已成功清空，并且自增主键已重置")
                return cursor.rowcount
            except sqlite3.Error as e:
                print(f"操作失败: {e}")
                return -1
            finally:
                conn.close()
    
    def get_plugin_status(self, plugin_name: str, group_id: str) -> bool:
        """获取插件启用状态"""
        result = self.fetch_one('plugin_config', 'plugin_name = ? AND group_id = ?', (plugin_name, group_id))
        if result:
            return bool(result['enabled'])
        # 如果没有记录，默认启用
        return True

    def get_enabled_groups(self, plugin_name: str) -> List[int]:
        """
        获取启用了指定插件的所有群组ID列表
        
        Args:
            plugin_name: 插件名称
        
        Returns:
            启用了该插件的群组ID列表
        """
        try:
             # 获取所有群组ID（从group_config表或其他方式）
            all_groups = self.fetch_all('group_config', '')
            enabled_groups = []
            
            for group in all_groups:
                group_id = group['group_id']
                # 使用get_plugin_status检查状态（包含默认值逻辑）
                if self.get_plugin_status(plugin_name, group_id):
                    enabled_groups.append(int(group_id))
            
            return enabled_groups
        except Exception as e:
            print(f"获取启用群组列表失败: {e}")
            return []

    
    def set_plugin_status(self, plugin_name: str, group_id: str, enabled: bool) -> bool:
        """设置插件启用状态"""
        existing = self.fetch_one('plugin_config', 'plugin_name = ? AND group_id = ?', (plugin_name, group_id))
        if existing:
            # 更新现有记录
            self.update('plugin_config', 
                       {'enabled': enabled, 'updated_at': 'CURRENT_TIMESTAMP'}, 
                       f'plugin_name = "{plugin_name}" AND group_id = "{group_id}"')
        else:
            # 插入新记录
            self.insert('plugin_config', {
                'plugin_name': plugin_name,
                'group_id': group_id,
                'enabled': enabled
            })
        return True
    
    def get_all_plugin_status(self, group_id: int) -> dict:
        """获取指定群组所有插件的状态"""
        results = self.fetch_all('plugin_config', f'group_id = {group_id}')
        
        return {row['plugin_name']: bool(row['enabled']) for row in results}

    def get_signup_format(self, group_id: str) -> bool:
        """
        获取群组的报名格式设置
        
        Args:
            group_id: 群组ID
        
        Returns:
            True: 心法+昵称格式, False: 昵称+心法格式
        """
        result = self.fetch_one('group_config', 'group_id = ?', (group_id,))
        if result:
            return bool(result['is_xf_first'])
        # 如果没有记录，默认为心法在前
        return True
    
    def set_signup_format(self, group_id: str, is_xf_first: bool) -> bool:
        """
        设置群组的报名格式
        
        Args:
            group_id: 群组ID
            is_xf_first: True为心法+昵称格式，False为昵称+心法格式
        
        Returns:
            操作是否成功
        """
        try:
            existing = self.fetch_one('group_config', 'group_id = ?', (group_id,))
            if existing:
                # 更新现有记录
                self.update('group_config', 
                           {'is_xf_first': int(is_xf_first), 'updated_at': 'CURRENT_TIMESTAMP'}, 
                           f'group_id = "{group_id}"')
            else:
                # 插入新记录
                self.insert('group_config', {
                    'group_id': group_id,
                    'is_xf_first': int(is_xf_first)
                })
            return True
        except Exception as e:
            print(f"设置报名格式失败: {e}")
            return False
    
    def get_all_signup_formats(self) -> dict:
        """
        获取所有群组的报名格式设置
        
        Returns:
            {group_id: is_xf_first} 格式的字典
        """
        results = self.fetch_all('group_config')
        return {row['group_id']: bool(row['is_xf_first']) for row in results}
    
    def get_today_gold_price(self, server: str) -> Optional[Dict[str, Any]]:
        """
        获取今日金价缓存
        """
        today = datetime.now().strftime('%Y-%m-%d')
        return self.fetch_one(
            'gold_price_cache', 
            'server = ? AND date = ?', 
            (server, today)
        )

    def save_gold_price(self, server: str, date: str, wanbaolou_price: str) -> bool:
        """
        保存金价到缓存
        """
        try:
            data = {
                'server': server,
                'date': date,
                'wanbaolou_price': wanbaolou_price
            }
            # 使用 INSERT OR REPLACE 避免重复
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO gold_price_cache 
                    (server, date, wanbaolou_price) 
                    VALUES (?, ?, ?)
                ''', (server, date, wanbaolou_price))
                conn.commit()
                return True
        except Exception as e:
            print(f"保存金价失败: {e}")
            return False

    def get_group_config(self, group_id: str) -> Optional[Dict[str, Any]]:
        """
        获取群组配置
        """
        return self.fetch_one('group_config', 'group_id = ?', (group_id,))

    def update_group_config(self, group_id: str, config_data: Dict[str, Any]) -> bool:
        """
        更新群组配置
        """
        try:
            # 先检查是否存在
            existing = self.get_group_config(group_id)
            if existing:
                # 更新
                set_clause = ', '.join([f"{k} = ?" for k in config_data.keys()])
                sql = f"UPDATE group_config SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE group_id = ?"
                values = list(config_data.values()) + [group_id]
            else:
                # 插入
                config_data['group_id'] = group_id
                return self.insert('group_config', config_data) > 0
                
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                conn.commit()
                return True
        except Exception as e:
            print(f"更新群组配置失败: {e}")
            return False
                



