# src/plugins/deepseek_ai.py
from nonebot import on_regex
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message
import aiohttp
import json
from typing import Dict, List, Optional
import uuid
from datetime import datetime
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL
from .database import TeamRecordDB

# 初始化数据库
db = TeamRecordDB()
db.init_db()

# DeepSeek AI对话命令
DeepSeekChat = on_regex(pattern=r'^ds\s+(.+)$', priority=1)
@DeepSeekChat.handle()
async def handle_deepseek_chat(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查插件是否启用
    if not db.get_plugin_status('deepseek_ai', str(event.group_id)):
        return
    
    matched = state["_matched"]
    user_message = matched.group(1).strip()
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    if not user_message:
        await DeepSeekChat.finish("请输入要对话的内容，例如：ds 你好")
    
    try:
        # 发送处理提示
        processing_msg = await bot.send(event=event, message="我正在思考，请稍候...")
        # 获取或创建对话会话
        conversation_id = await get_or_create_conversation(user_id, group_id)
        
        # 获取历史对话记录
        history = await get_conversation_history(conversation_id, limit=10)
        
        # 构建消息列表
        messages = [
            {"role": "system", "content": "你是一个友善、有帮助的AI助手。请用简洁明了的方式回答问题。"}
        ]
        
        # 添加历史对话
        for record in history:
            messages.append({
                "role": record['role'],
                "content": record['content']
            })
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})
        
        # 调用DeepSeek API
        response = await call_deepseek_api(messages)
        
        if response:
            # 保存用户消息
            await save_conversation_message(conversation_id, user_id, group_id, "user", user_message)
            
            # 保存AI回复
            await save_conversation_message(conversation_id, user_id, group_id, "assistant", response)
            
            # 发送回复
            await DeepSeekChat.send(f"🤖 DeepSeek AI:\n{response}")
        else:
            await DeepSeekChat.finish("❌ AI服务暂时不可用，请稍后重试")
            
    except Exception as e:
        print(f"DeepSeek AI对话错误: {e}")
        await DeepSeekChat.finish("❌ 对话过程中出现错误，请稍后重试")

# 新建对话命令
NewConversation = on_regex(pattern=r'^ds新对话(?:\s+(.+))?$', priority=1)
@NewConversation.handle()
async def handle_new_conversation(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查插件是否启用
    if not db.get_plugin_status('deepseek_ai', str(event.group_id)):
        return
    
    matched = state["_matched"]
    session_name = matched.group(1).strip() if matched.group(1) else None
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    try:
        # 创建新的对话会话
        conversation_id = str(uuid.uuid4())
        
        # 保存会话信息
        session_data = {
            'user_id': user_id,
            'group_id': group_id,
            'conversation_id': conversation_id,
            'session_name': session_name
        }
        
        db.insert('ai_sessions', session_data)
        
        session_info = f"会话名称: {session_name}" if session_name else "默认会话"
        await NewConversation.finish(f"✅ 已创建新的AI对话会话\n{session_info}\n会话ID: {conversation_id[:8]}...")
        
    except Exception as e:
        print(f"创建新对话会话错误: {e}")
        await NewConversation.finish("❌ 创建新对话会话失败，请稍后重试")

# 对话历史命令
ConversationHistory = on_regex(pattern=r'^ds历史(?:\s+(\d+))?$', priority=1)
@ConversationHistory.handle()
async def handle_conversation_history(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 检查插件是否启用
    if not db.get_plugin_status('deepseek_ai', str(event.group_id)):
        return
    
    matched = state["_matched"]
    limit = int(matched.group(1)) if matched.group(1) else 5
    user_id = str(event.user_id)
    group_id = str(event.group_id)
    
    try:
        # 获取当前对话会话
        conversation_id = await get_or_create_conversation(user_id, group_id)
        
        # 获取历史记录
        history = await get_conversation_history(conversation_id, limit=limit)
        
        if not history:
            await ConversationHistory.finish("📝 暂无对话历史记录")
        
        # 构建历史记录消息
        msg_lines = ["📝 最近的对话历史:"]
        for i, record in enumerate(history[-limit:], 1):
            role_icon = "👤" if record['role'] == 'user' else "🤖"
            timestamp = record['timestamp'][:16]  # 只显示到分钟
            content = record['content'][:100] + "..." if len(record['content']) > 100 else record['content']
            msg_lines.append(f"{i}. {role_icon} [{timestamp}] {content}")
        
        msg_lines.append("\n💡 使用 'ds 消息内容' 继续对话")
        msg_lines.append("💡 使用 'ds新对话' 开始新的对话")
        
        await ConversationHistory.finish("\n".join(msg_lines))
        
    except Exception as e:
        print(f"获取对话历史错误: {e}")
        await ConversationHistory.finish("❌ 获取对话历史失败，请稍后重试")

# 辅助函数
async def call_deepseek_api(messages: List[Dict]) -> Optional[str]:
    """调用DeepSeek API"""
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'model': 'deepseek-chat',
        'messages': messages,
        'max_tokens': 1000,
        'temperature': 0.7
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['choices'][0]['message']['content']
                else:
                    print(f"DeepSeek API错误: {response.status}")
                    return None
    except Exception as e:
        print(f"调用DeepSeek API异常: {e}")
        return None

async def get_or_create_conversation(user_id: str, group_id: str) -> str:
    """获取或创建对话会话"""
    # 查找用户最近的会话
    recent_session = db.fetch_one(
        'ai_sessions',
        'user_id = ? AND group_id = ? ORDER BY updated_at DESC',
        (user_id, group_id)
    )
    
    if recent_session:
        # 更新会话时间
        db.update(
            'ai_sessions',
            {'updated_at': datetime.now().isoformat()},
            f'conversation_id = "{recent_session["conversation_id"]}"'
        )
        return recent_session['conversation_id']
    else:
        # 创建新会话
        conversation_id = str(uuid.uuid4())
        session_data = {
            'user_id': user_id,
            'group_id': group_id,
            'conversation_id': conversation_id
        }
        db.insert('ai_sessions', session_data)
        return conversation_id

async def get_conversation_history(conversation_id: str, limit: int = 10) -> List[Dict]:
    """获取对话历史"""
    return db.fetch_all(
        'ai_conversations',
        f'conversation_id = "{conversation_id}" ORDER BY timestamp DESC LIMIT {limit}'
    )

async def save_conversation_message(conversation_id: str, user_id: str, group_id: str, role: str, content: str):
    """保存对话消息"""
    message_data = {
        'user_id': user_id,
        'group_id': group_id,
        'conversation_id': conversation_id,
        'role': role,
        'content': content
    }
    db.insert('ai_conversations', message_data)