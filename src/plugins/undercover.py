'''
Date: 2025-03-06 17:21:21
LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
LastEditTime: 2025-06-11 16:49:12
FilePath: /team-bot/jx3-team-bot/src/plugins/undercover.py
'''
# src/plugins/undercover.py
from nonebot import on_regex, on_command, on_message, require
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Bot, Message, PrivateMessageEvent
from nonebot.permission import SUPERUSER
import random
import time
import asyncio
import aiohttp
import json
from typing import Dict, List, Tuple, Set, Optional
from .game_score import update_player_score
# require('nonebot_plugin_saa')
# from nonebot_plugin_saa import enable_auto_select_bot
# enable_auto_select_bot()
# from nonebot_plugin_saa import PlatformTarget, TargetQQPrivate, TargetQQGroup, MessageFactory

# 游戏状态
class UndercoverGameStatus:
    WAITING = 0    # 等待开始
    SIGNUP = 1     # 报名中
    PLAYING = 2    # 游戏中
    VOTING = 3     # 投票中
    ENDED = 4      # 已结束

# 游戏数据
class UndercoverGame:
    def __init__(self, group_id: int):
        self.group_id = group_id
        self.status = UndercoverGameStatus.WAITING
        self.players = {}  # user_id -> {"nickname": str, "word": str, "is_undercover": bool, "eliminated": bool}
        self.current_round = 0
        self.max_rounds = 0
        self.words = ("", "")  # (普通词, 卧底词)
        self.speaking_order = []
        self.current_speaker_index = 0
        self.votes = {}  # 投票结果: voter_id -> target_id
        self.speaking_timer = None
        self.vote_timer = None
        self.player_speeches = {}  # 存储玩家发言: user_id -> [发言1, 发言2, ...]
        self.change_word_timer = None  # 换词计时器

# 存储每个群的游戏状态
games: Dict[int, UndercoverGame] = {}

# 词库API
async def fetch_word_pairs() -> List[Tuple[str, str]]:
    """从网络获取谁是卧底词库"""
    try:
        async with aiohttp.ClientSession() as session:
            # 这里使用一个示例API，实际使用时请替换为可用的API
            async with session.get('https://api.example.com/undercover/words') as response:
                if response.status == 200:
                    data = await response.json()
                    return data['word_pairs']
    except Exception as e:
        print(f"获取词库失败: {e}")
    
    # 如果API获取失败，使用内置词库
    return [
        ("苹果", "梨"), ("可乐", "雪碧"), ("篮球", "鼠标"), ("电脑", "手机"), ("眼睛", "耳朵"), ("电影", "电视剧"),("老师", "教授"),
        ("警察", "保安"),("医生", "护士"),("飞机", "直升机"),("汽车", "自行车"),("西瓜", "哈密瓜"),("钢琴", "吉他"),("猫", "老虎"),
        ("金刚狼", "黑寡妇"),("甄嬛传", "芈月传"),("哈利波特", "伏地魔"),("蜘蛛侠", "蜘蛛精"),("高跟鞋", "增高鞋"),("汉堡包", "肉夹馍"),
        ("古筝", "古琴"),("王者荣耀", "英雄联盟"),("眉毛", "胡须"),("海豹", "海象"),("孔雀", "凤凰"),("京剧", "越剧"),("星巴克", "瑞幸"),
        ("微信", "QQ"),("抖音", "快手"),("饺子", "包子"),("火锅", "麻辣烫"),("剑三", "逆水寒"),("麻将", "扑克"),("支付宝", "微信支付"),
        ("淘宝", "京东"),("小米", "华为"),("海底捞", "小龙坎"),("肯德基", "麦当劳"),("必胜客", "达美乐"),("喜茶", "奈雪的茶"),("咖啡", "奶茶"),("地铁", "公交"),
        ("滴滴", "花小猪"),("支付宝", "云闪付"),("知乎", "小红书"),("B站", "抖音"),("爱情", "友情"),("螺蛳粉", "酸辣粉"),("奶茶", "椰奶"),
        ("香菜", "折耳根"),("保安", "保镖"),("敦煌壁画", "埃及金字塔"),("京剧脸谱", "日本浮世绘"),("人工智能", "仿生机器人"),("柯南", "福尔摩斯"),("中央空调", "暖男"),
        ("大众", "五菱"),("小龙虾", "大闸蟹"),("粽子", "咸鸭蛋"),("春节", "元宵节"),("指甲刀", "美工刀"),("蚊子", "苍蝇"),("美瞳", "隐形眼镜"),
        ("电饭煲", "高压锅"),("空调", "电风扇"),("火车", "高铁"),("剑网三", "天刀"),("原神", "崩坏星穹铁道"),("米哈游", "网易"),("外卖", "堂食"),
        ("KTV", "录音棚"),("健身房", "体育馆"),("超市", "便利店"),("电影院", "剧场"),("动漫", "漫画"),("漫展", "游戏展"),("笔记本", "平板"),
        ("卫生巾", "护垫"),("煎饼果子", "鸡蛋灌饼"),("大黄蜂", "小蜜蜂"),("政教处", "教导处"),("九阴白骨爪", "降龙十八掌"),("葵花宝典", "辟邪剑谱"),("dota", "lol"),
        ("童话", "寓言"),("那英", "王菲"),("同学", "同桌"),("张韶涵", "张含韵"),("橙子", "橘子"),("婚纱", "喜服"),("森马", "以纯"),
        ("皇帝", "太子"),("辣椒", "芥末"),("董永", "许仙"),("金庸", "古龙"),("酒吧", "茶楼"),("狄仁杰", "包青天"),("魔术师", "魔法师"),
        ("泡泡糖", "棒棒糖"),("铁观音", "碧螺春"),("牛肉干", "猪肉脯"),("前女友", "前男友"),("双胞胎", "龙凤胎"),("富二代", "高富帅"),("神雕侠侣", "天龙八部"),
        ("拉面", "刀削面"),("奥利奥", "趣多多"),("早餐", "宵夜"),("相亲", "联谊"),("加班", "值班"),("年终奖", "绩效奖"),("请假条", "辞职信"),
        ("结婚", "订婚"),("恋爱", "暗恋"),("男朋友", "备胎"),("女朋友", "闺蜜"),("相亲角", "婚介所"),("催婚", "催生"),("丈母娘", "婆婆"),
        ("岳父", "公公"),("AA制", "请客"),("网红", "明星"),("键盘侠", "网络喷子"),("南京条约", "马关条约"),("赤壁之战", "官渡之战"),("贞观之治", "开元盛世"),
        ("文景之治", "康乾盛世"),("郑和下西洋", "张骞出使西域"),("香港", "澳门"),("武则天", "慈禧"),("朱元璋", "朱棣"),("秦始皇", "汉武帝"),("康熙", "乾隆"),
        ("雍正", "嘉庆"),("速度与激情", "极品飞车"),("盗梦空间", "黑客帝国"),("阿甘正传", "楚门的世界"),("霍比特人", "魔戒"),("仙剑奇侠传", "古剑奇谭"),("武林外传", "家有儿女"),
        ("大长今", "宫"),("傲娇", "病娇"),("天然呆", "三无少女"),("元气少女", "御姐"),("中二病", "社恐"),("吃货", "宅女"),("灌篮高手", "排球少年"),
        ("钢之炼金术师", "魔法禁书目录"),("鬼灭之刃", "咒术回战"),("进击的巨人", "东京喰种"),("刀剑神域", "鬼滅之刃"),("魔卡少女樱", "美少女战士"),("银魂", "齐木楠雄的灾难"),("穿越", "重生"),
        ("皇子", "王爷"),("公主", "格格"),("侠客", "刺客"),("剑客", "刀客"),("书生", "才子"),("丫鬟", "侍女"),("捕快", "衙役"),
        ("将军", "元帅"),("宰相", "丞相"),("才女", "佳人"),("道士", "和尚"),("仙女", "妖精"),("南派三叔", "天下霸唱"),("诛仙", "斗破苍穹"),("盗墓笔记", "鬼吹灯"),
        ("三体", "流浪地球"),("围城", "平凡的世界"),("莫言", "余华"),("令狐冲", "杨过"),("郭靖", "张无忌"),("段誉", "萧峰"),("黄蓉", "小龙女"),("王语嫣", "赵敏"),
        ("东方不败", "任我行"),("岳不群", "左冷禅"),("风清扬", "独孤求败"),("洪七公", "黄药师"),("林黛玉", "薛宝钗"),("贾宝玉", "贾探春"),("孙悟空", "猪八戒"),
        ("刘备", "曹操"),("诸葛亮", "司马懿"),("关羽", "张飞"),("武松", "鲁智深"),("宋江", "林冲"),("潘金莲", "西门庆"),("李逵", "李鬼"),
        ("叶修", "苏沐橙"),("唐三", "萧炎"),("故宫", "颐和园"),("充电宝", "充电器"),
        ("红烧肉", "糖醋排骨"),("宫保鸡丁", "鱼香肉丝"),("回锅肉", "梅菜扣肉"),("麻婆豆腐", "家常豆腐"),("油焖大虾", "白灼虾"),
        ("寿司", "刺身"),("汉堡", "三明治"),("披萨", "意面"),("薯条", "薯片"),("冰淇淋", "雪糕"),
        ("珍珠奶茶", "果茶"),("拿铁", "卡布奇诺"),("橙汁", "苹果汁"),("酸奶", "乳酸菌饮料"),
        ("康师傅", "统一"),("旺旺", "上好佳"),("德芙", "费列罗"),("可口可乐", "百事可乐"),("伊利", "蒙牛"),
        ("羽绒服", "棉衣"),("毛衣", "针织衫"),("牛仔裤", "休闲裤"),("连衣裙", "半身裙"),("运动鞋", "板鞋"),
        ("耐克", "阿迪达斯"),("李宁", "安踏"),("ZARA", "H&M"),("优衣库", "无印良品"),("香奈儿", "迪奥"),
        ("手表", "手环"),("项链", "手链"),("戒指", "耳环"),("眼镜", "墨镜"),("帽子", "围巾"),
        ("手机", "平板"),("电脑", "笔记本"),("电视", "投影仪"),("冰箱", "冰柜"),("洗衣机", "烘干机"),
        ("苹果", "华为"),("小米", "vivo"),("OPPO", "荣耀"),("三星", "索尼"),("联想", "戴尔"),
        ("微信", "QQ"),("淘宝", "京东"),("抖音", "快手"),("支付宝", "微信支付"),("百度", "谷歌"),
        ("王者荣耀", "和平精英"),("原神", "崩坏"),("英雄联盟", "DOTA"),("开心消消乐", "天天爱消除"),("植物大战僵尸", "保卫萝卜"),
        ("电影", "电视剧"),("演唱会", "音乐会"),("话剧", "舞台剧"),("相声", "小品"),("魔术", "杂技"),
        ("迪士尼", "欢乐谷"),("电影院", "KTV"),("酒吧", "清吧"),("餐厅", "咖啡馆"),("游乐场", "主题公园"),
        ("猫", "狗"),("兔子", "仓鼠"),("金鱼", "乌龟"),("小鸟", "鹦鹉"),("刺猬", "龙猫"),
        ("狮子", "老虎"),("大象", "长颈鹿"),("猴子", "猩猩"),("熊猫", "棕熊"),("狐狸", "狼"),
        ("公交车", "地铁"),("出租车", "网约车"),("自行车", "电动车"),("摩托车", "汽车"),("火车", "高铁"),
        ("飞机", "直升机"),("轮船", "游艇"),("卡车", "货车"),("救护车", "消防车"),("警车", "工程车"),
        ("学校", "幼儿园"),("医院", "诊所"),("银行", "信用社"),("超市", "便利店"),("商场", "购物中心"),
        ("公园", "广场"),("图书馆", "书店"),("电影院", "剧院"),("体育馆", "健身房"),("博物馆", "科技馆"),
        ("春天", "夏天"),("秋天", "冬天"),("晴天", "阴天"),("雨天", "雪天"),("刮风", "下雨"),
        ("太阳", "月亮"),("星星", "流星"),("云朵", "彩虹"),("闪电", "打雷"),("雪花", "冰雹"),
        ("山", "水"),("树", "花"),("草", "木"),("石头", "沙子"),("泥土", "土地"),
        ("红色", "绿色"),("蓝色", "黄色"),("紫色", "粉色"),("橙色", "黑色"),("白色", "灰色"),
        ("正方形", "长方形"),("圆形", "椭圆形"),("三角形", "梯形"),("菱形", "平行四边形"),("五角形", "六角形"),
        ("筷子", "勺子"),("碗", "盘子"),("杯子", "茶壶"),("锅", "铲子"),("菜刀", "案板"),
        ("毛巾", "浴巾"),("牙刷", "牙膏"),("梳子", "镜子"),("肥皂", "沐浴露"),("洗发水", "护发素"),
        ("床", "沙发"),("桌子", "椅子"),("衣柜", "鞋柜"),("书架", "电视柜"),("茶几", "餐桌"),
        ("铅笔", "钢笔"),("圆珠笔", "中性笔"),("笔记本", "作业本"),("橡皮", "修正带"),("尺子", "圆规"),
        ("书", "杂志"),("报纸", "海报"),("地图", "画册"),("字帖", "乐谱"),("漫画", "小说"),
        ("警察", "交警"),("医生", "护士"),("老师", "教授"),("厨师", "服务员"),("司机", "快递员"),
        ("演员", "歌手"),("作家", "画家"),("摄影师", "设计师"),("工程师", "程序员"),("律师", "法官"),
        ("爷爷", "奶奶"),("爸爸", "妈妈"),("哥哥", "姐姐"),("弟弟", "妹妹"),("叔叔", "阿姨"),
        ("春节", "中秋节"),("端午节", "元宵节"),("国庆节", "劳动节"),("圣诞节", "情人节"),("万圣节", "复活节"),
        ("跳绳", "踢毽子"),("拔河", "接力赛"),("跑步", "跳远"),("跳高", "铅球"),("篮球", "足球"),
        ("乒乓球", "羽毛球"),("网球", "排球"),("游泳", "跳水"),("滑冰", "滑雪"),("体操", "舞蹈"),
        ("钢琴", "吉他"),("小提琴", "二胡"),("古筝", "琵琶"),("鼓", "锣"),("口琴", "笛子"),
        ("魔术", "杂技"),("马戏", "木偶戏"),("皮影戏", "手影戏"),("变脸", "喷火"),("柔术", "杂耍"),
        ("孙悟空", "猪八戒"),("唐僧", "沙僧"),("贾宝玉", "林黛玉"),("宋江", "李逵"),("刘备", "曹操"),
        ("哈利・波特", "赫敏"),("蜘蛛侠", "蝙蝠侠"),("超人", "钢铁侠"),("神奇女侠", "雷神"),("绿巨人", "美国队长"),
        ("白雪公主", "灰姑娘"),("小红帽", "睡美人"),("美人鱼", "拇指姑娘"),("青蛙王子", "豌豆公主"),
        ("故宫", "长城"),("兵马俑", "大雁塔"),("西湖", "黄山"),("泰山", "华山"),("桂林山水", "张家界"),
        ("巴黎铁塔", "埃菲尔铁塔"),("自由女神像", "白宫"),("大本钟", "伦敦塔桥"),("悉尼歌剧院", "悉尼港"),("富士山", "东京塔"),
        ("火锅", "串串香"),("烧烤", "铁板烧"),("寿司", "手卷"),("拉面", "刀削面"),("炒饭", "盖浇饭"),
        ("蛋挞", "泡芙"),("蛋糕", "面包"),("饼干", "曲奇"),("果冻", "布丁"),("糖葫芦", "棉花糖"),
        ("龙井", "碧螺春"),("普洱", "铁观音"),("菊花", "枸杞"),("红枣", "桂圆"),("蜂蜜", "红糖"),
        ("毛毯", "棉被"),("枕头", "抱枕"),("拖鞋", "棉鞋"),("睡衣", "家居服"),("围裙", "袖套"),
        ("钥匙", "锁"),("剪刀", "胶水"),("锤子", "钉子"),("螺丝刀", "扳手"),("电钻", "电锯"),
        ("口罩", "眼罩"),("耳塞", "手套"),("袜子", "鞋垫"),("皮带", "领带"),("发卡", "头绳"),
        ("日历", "台历"),("手表", "闹钟"),("镜子", "梳子"),("香水", "香薰"),("蜡烛", "火柴"),
        ("黑板", "白板"),("粉笔", "马克笔"),("投影仪", "电子白板"),("讲台", "课桌"),("书包", "文具袋"),
        ("羽毛球拍", "乒乓球拍"),("网球拍", "排球"),("篮球", "足球"),("跳绳", "毽子"),("呼啦圈", "哑铃"),
        ("钢琴凳", "吉他架"),("小提琴盒", "二胡包"),("古筝架", "琵琶套"),("鼓槌", "锣锤"),("口琴袋", "笛子套"),
        ("魔术棒", "杂技球"),("马戏圈", "木偶"),("皮影", "手影道具"),("变脸面具", "喷火道具"),("柔术垫", "杂耍球"),
        ("孙悟空金箍棒", "猪八戒九齿钉耙"),("唐僧袈裟", "沙僧禅杖"),("贾宝玉通灵宝玉", "林黛玉手帕"),("宋江令牌", "李逵板斧"),("刘备双股剑", "曹操倚天剑"),
        ("哈利・波特魔杖", "赫敏魔法书"),("蜘蛛侠蛛丝发射器", "蝙蝠侠蝙蝠车"),("超人披风", "钢铁侠战甲"),("神奇女侠真言套索", "雷神之锤"),("绿巨人拳头", "美国队长盾牌"),
        ("白雪公主苹果", "灰姑娘水晶鞋"),("小红帽帽子", "睡美人纺锤"),("美人鱼梳子", "拇指姑娘叶子"),("青蛙王子王冠", "豌豆公主床垫"),
        ("故宫龙椅", "长城烽火台"),("兵马俑兵器", "大雁塔佛像"),("西湖断桥", "黄山迎客松"),("泰山玉皇顶", "华山长空栈道"),("桂林山水竹筏", "张家界奇峰"),
        ("巴黎铁塔观景台", "埃菲尔铁塔电梯"),("自由女神像火炬", "白宫椭圆办公室"),("大本钟表盘", "伦敦塔桥桥面"),("悉尼歌剧院舞台", "悉尼港渡轮"),("富士山缆车", "东京塔瞭望台"),
        ("杨幂", "刘诗诗"),("赵丽颖", "刘亦菲"),("彭于晏", "胡歌"),("迪丽热巴", "古力娜扎"),
        ("榴莲", "山竹"),("杨梅", "草莓"),("车厘子", "樱桃"),("猕猴桃", "奇异果"),("芒果", "菠萝蜜"),
        ("《琅琊榜》", "《甄嬛传》"),("《盗墓笔记》", "《鬼吹灯》"),("《老友记》", "《生活大爆炸》"),("《哈利・波特》系列电影", "《指环王》系列电影"),("《疯狂动物城》", "《寻梦环游记》"),
        ("耳机", "耳塞"),("充电宝", "移动电源"),("自拍杆", "三脚架"),("蓝牙音箱", "普通音箱"),("投影仪", "电视盒子"),
        ("故宫", "颐和园"),("长城", "兵马俑"),("埃菲尔铁塔", "巴黎圣母院"),("自由女神像", "白宫"),("悉尼歌剧院", "悉尼港大桥"),
        ("吉他", "尤克里里"),("钢琴", "电子琴"),("小提琴", "中提琴"),("鼓", "架子鼓"),("二胡", "板胡"),
        ("瑜伽", "普拉提"),("滑雪", "滑冰"),("潜水", "浮潜"),("登山", "徒步"),("射箭", "飞镖"),
        ("口红", "唇釉"),("眼影", "腮红"),("粉底", "粉饼"),("睫毛膏", "眼线笔"),("香水", "香氛"),
        ("微波炉", "烤箱"),("空气炸锅", "电饼铛"),("吸尘器", "扫地机器人"),("电熨斗", "挂烫机"),("榨汁机", "破壁机"),
        ("童话", "神话"),("小说", "散文"),("诗歌", "歌词"),("漫画", "绘本"),("传记", "回忆录"),
        ("孙悟空", "二郎神"),("哪吒", "红孩儿"),("嫦娥", "玉兔"),("七仙女", "织女"),("牛魔王", "铁扇公主"),
        ("蓝牙", "WiFi"),("U 盘", "移动硬盘"),("二维码", "条形码"),("表情包", "动图"),("搜索引擎", "浏览器"),
        ("美甲", "美睫"),("纹眉", "纹唇"),("按摩", "推拿"),("汗蒸", "桑拿"),("足疗", "采耳"),
        ("狼人杀", "剧本杀"),("三国杀", "英雄杀"),("大富翁", "强手棋"),("跳棋", "五子棋"),("拼图", "积木"),
        ("保温杯", "保温壶"),("雨伞", "遮阳伞"),("围巾", "披肩"),("手套", "mittens"),("墨镜", "太阳镜"),
        ("红烧肉", "东坡肉"),("糖醋鲤鱼", "红烧鱼"),("宫保虾球", "腰果虾仁"),("蚂蚁上树", "肉末粉条"),("拔丝地瓜", "拔丝苹果"),
        ("甜筒", "圣代"),("马卡龙", "纸杯蛋糕"),("提拉米苏", "慕斯蛋糕"),("糖葫芦", "糖雪球"),("驴打滚", "艾窝窝"),
        ("拿铁", "摩卡"),("乌龙茶", "红茶"),("椰汁", "杏仁露"),("酸梅汤", "绿豆汤"),("鸡尾酒", "预调酒"),
        ("海底捞番茄锅", "呷哺呷哺番茄锅"),("德克士", "华莱士"),("DQ", "冰雪皇后"),("一点点", "coco"),("瑞幸生椰拿铁", "库迪生椰拿铁"),
        ("羽绒服", "冲锋衣"),("牛仔裤", "工装裤"),("马丁靴", "切尔西靴"),("棒球帽", "渔夫帽"),("连衣裙", "连体裤"),
        ("周大福", "周生生"),("周大生", "周六福"),("施华洛世奇", "潘多拉"),("卡地亚", "蒂芙尼"),("浪琴", "天梭"),
        ("电动牙刷", "普通牙刷"),("牙线", "牙签"),("洗脸巾", "毛巾"),("护手霜", "身体乳"),("卷发棒", "直发器"),
        ("沙发", "躺椅"),("茶几", "边几"),("衣柜", "衣帽间"),("书架", "置物架"),("餐桌", "书桌"),
        ("中性笔", "圆珠笔"),("马克笔", "水彩笔"),("笔记本", "便签本"),("订书机", "打孔器"),("胶水", "胶棒"),
        ("科幻片", "奇幻片"),("动作片", "武侠片"),("文艺片", "剧情片"),("喜剧片", "闹剧片"),("恐怖片", "惊悚片"),
        ("迪士尼乐园", "环球影城"),("欢乐谷", "方特欢乐世界"),("海洋馆", "动物园"),("科技馆", "博物馆"),("游乐场", "主题乐园"),
        ("金毛", "拉布拉多"),("博美", "约克夏"),("暹罗猫", "布偶猫"),("乌龟", "鳖"),("金鱼", "锦鲤"),
        ("高铁", "动车"),("自行车", "共享单车"),("电动车", "摩托车"),("游轮", "邮轮"),("直升机", "私人飞机"),
        ("医院", "诊所"),("学校", "培训机构"),("银行", "信用社"),("超市", "便利店"),("商场", "购物中心"),
        ("广场舞", "健美操"),("太极拳", "八段锦"),("瑜伽球", "健身球"),("跑步机", "椭圆机"),("哑铃", "杠铃"),
        ("古筝曲《渔舟唱晚》", "二胡曲《二泉映月》"),("钢琴曲《梦中的婚礼》", "小提琴曲《梁祝》"),("流行歌曲", "民谣"),("美声唱法", "通俗唱法"),("摇滚", "朋克"),
        ("旗袍", "汉服"),("唐装", "中山装"),("和服", "韩服"),("婚纱", "礼服"),("睡衣", "家居服"),
        ("充电宝", "蓄电池"),("耳机", "耳麦"),("键盘", "鼠标"),("摄像头", "扫描仪"),("路由器", "交换机"),
        ("日历", "台历"),("闹钟", "定时器"),("镜子", "化妆镜"),("梳子", "发刷"),("香水", "古龙水"),
        ("黑板", "白板"),("粉笔", "无尘粉笔"),("投影仪", "电子白板"),("讲台", "课桌"),("书包", "双肩包"),
        ("乒乓球拍", "羽毛球拍"),("网球拍", "壁球拍"),("篮球鞋", "足球鞋"),("护腕", "护膝"),("跳绳", "健身绳"),
        ("钢琴凳", "琴椅"),("吉他包", "琴盒"),("小提琴弓", "琴弓"),("二胡弦", "琴弦"),("鼓槌", "鼓棒"),
        ("孙悟空金箍棒", "哪吒乾坤圈"),("唐僧紧箍咒", "观音净瓶"),("贾宝玉通灵宝玉", "林黛玉香囊"),("宋江招安诏书", "李逵板斧"),("刘备雌雄双股剑", "孙权佩剑"),
        ("哈利・波特魔法袍", "赫敏魔法棒"),("蜘蛛侠战衣", "蝙蝠侠披风"),("超人紧身衣", "钢铁侠战衣"),("神奇女侠套装", "雷神盔甲"),("绿巨人短裤", "美国队长制服"),
        ("白雪公主城堡", "灰姑娘南瓜车"),("小红帽森林", "睡美人城堡"),("美人鱼海底宫殿", "拇指姑娘花朵"),("青蛙王子池塘", "豌豆公主城堡"),
        ("故宫太和殿", "天坛祈年殿"),("兵马俑一号坑", "二号坑"),("西湖三潭映月", "断桥残雪"),("黄山莲花峰", "天都峰"),("泰山玉皇顶", "南天门"),("桂林象鼻山", "九马画山"),
        ("纯阳・气纯", "纯阳・剑纯"),("七秀・冰心", "七秀・云裳"),("天策・傲血", "天策・铁牢"),("万花・花间游", "万花・离经易道"),
        ("五毒・毒经", "五毒・补天诀"),("少林・易筋经", "少林・洗髓经"),("明教・焚影圣诀", "明教・明尊琉璃体"),("唐门・惊羽诀", "唐门・田螺"),
        ("藏剑・山居剑意", "藏剑・问水诀"),("长歌・相知", "长歌・莫问"),("凌雪阁・踏雪", "凌雪阁・飞影"),
        ("蓬莱・凌海诀", "衍天宗・太玄经"),("霸刀・北傲诀", "丐帮・笑尘诀"),("李承恩", "杨宁"),
        ("叶英", "祁进"),("唐简", "方乾"),("曲云", "孙飞亮"),("莫雨", "穆玄英"),("谢云流", "李忘生"),("王遗风", "谢渊"),("公孙幽", "公孙盈"),
        ("于睿", "萧白胭"),("陈月", "林白轩"),("柳静海", "周墨"),("曹雪阳", "高绛婷"),("燕云", "可人"),("阿幼朵", "阿萨辛"),("荻花圣殿・沙利亚", "荻花圣殿・阿萨辛"),
        ("七秀坊・公孙大娘", "七秀坊・叶芷青"),("纯阳宫・吕洞宾", "纯阳宫・广成子"),
        ("万花谷・东方宇轩", "万花谷・裴元"),("五毒教・乌蒙贵", "五毒教・艾黎"),("明教・陆危楼", "明教・米丽古丽"),
        ("唐门・唐傲天", "唐门・唐老太太"),("丐帮・郭岩", "丐帮・马天忌"),("藏剑山庄・叶孟秋", "藏剑山庄・叶凡"),("长歌门・杨逸飞", "长歌门・琴魔"),
        ("凌雪阁・楚承恩", "凌雪阁・曲明性"),("衍天宗・李令问", "衍天宗・李重茂"),("蓬莱・方鹤影", "蓬莱・陈徽"),("霸刀山庄・柳惊涛", "霸刀山庄・柳夕"),
        ("八卦洞玄", "四象轮回"),("江海凝光", "玳弦急曲"),("龙牙", "龙吟"),("听风吹雪", "风来吴山"),("阳明指", "玉石俱焚"),("千蝶吐瑞", "冰蚕牵丝"),
        ("韦陀献杵", "立地成佛"),("烈日斩", "幽月轮"),("暴雨梨花针", "追命箭"),("亢龙有悔", "笑醉狂"),("平湖断月", "黄龙吐翠"),("高山流水", "梅花三弄"),
        ("血覆黄泉", "影刃"),("星移斗转", "天衍奇术"),("梯云纵", "乘风破浪"),("项王击鼎", "碎星辰"),("九转归一", "春泥护花"),("风袖低昂", "天地低昂"),
        ("渊", "突"),("剑冲阴阳", "人剑合一"),("满堂势", "孤注一掷"),("梵音大悲", "轮回诀"),("圣明佑", "贪魔体"),("化血镖", "裂伤"),("龙跃于渊", "龙腾"),
        ("莺啼柳", "鹊踏枝"),("剑影留痕", "云栖松"),("清绝影", "羽凌翔"),("踏冰", "封内"),("推栏望月", "断潮"),("江海余韵", "剑心通明"),("纯阳宫・太极广场", "纯阳宫・紫霄宫"),
        ("七秀坊・瘦西湖", "七秀坊・忆盈楼"),("天策府・演武场", "天策府・神策后营"),("万花谷・花海", "万花谷・杏林"),("五毒教・灵蛇岛", "五毒教・圣蝎堂"),
        ("少林寺・大雄宝殿", "少林寺・藏经阁"),("明教・光明顶", "明教・密道"),("唐门・唐家堡", "唐门・密室"),("丐帮・君山岛", "丐帮・忠义堂"),
        ("藏剑山庄・西湖", "藏剑山庄・剑冢"),("长歌门・微山书院", "长歌门・剑胆琴心岛"),
        ("春节", "国庆"),("端午节", "中秋节"),("清明节", "寒食节"),("元宵节", "重阳节"),("七夕节", "情人节"),
        ("北京", "上海"),("广州", "深圳"),("杭州", "苏州"),("成都", "重庆"),("南通", "南京"),
        ("清华大学", "北京大学"),("复旦大学", "上海交大"),("浙江大学", "南京大学"),("中山大学", "华南理工"),("武汉大学", "华中科技"),
        ("语文", "数学"),("英语", "物理"),("化学", "生物"),("历史", "地理"),("政治", "思品"),
        ("春天", "秋天"),("夏天", "冬天"),("晴天", "雨天"),("雪天", "雾天"),("台风", "龙卷风"),
        ("玫瑰", "百合"),("康乃馨", "郁金香"),("向日葵", "菊花"),("牡丹", "芍药"),("茉莉", "桂花"),
        ("早餐", "晚餐"),("午餐", "夜宵"),("正餐", "点心"),("主食", "配菜"),("汤", "粥"),
        ("米饭", "面条"),("包子", "饺子"),("馒头", "花卷"),("烧饼", "油条"),("粽子", "汤圆"),
        ("炒菜", "炖菜"),("蒸菜", "烤菜"),("凉菜", "热菜"),("素菜", "荤菜"),("甜菜", "咸菜"),
        ("筷子", "叉子"),("勺子", "刀子"),("碗", "盘子"),("杯子", "茶壶"),("锅", "铲子"),
        ("牙刷", "牙膏"),("毛巾", "浴巾"),("肥皂", "洗发水"),("沐浴露", "护发素"),("面膜", "爽肤水"),
        ("洗衣机", "烘干机"),("冰箱", "冰柜"),("空调", "暖气"),("热水器", "饮水机"),("油烟机", "消毒柜"),
        ("项链", "手链"),("戒指", "耳环"),("手表", "眼镜"),("包包", "钱包"),("皮带", "领带"),
        ("公园", "广场"),("海滩", "山顶"),("森林", "草原"),("湖泊", "河流"),("沙漠", "雪山"),
        ("小提琴", "大提琴"),("笛子", "萨克斯"),("架子鼓", "电子琴"),
        ("小说", "诗歌"),("散文", "戏剧"),("童话", "寓言"),("传记", "历史"),("科幻", "奇幻"),
        ("哲学", "心理学"),("医学", "法学"),("工程学", "建筑学"),("计算机", "电子"),("机械", "材料"),("环境", "能源"),
        ("春联", "窗花"),("灯笼", "鞭炮"),("年糕", "饺子"),("红包", "压岁钱"),("拜年", "守岁"),
        ("月饼", "桂花"),("嫦娥", "玉兔"),("团圆", "赏月"),("灯谜", "花灯"),("中秋", "仲秋"),
        ("粽子", "艾草"),("龙舟", "香包"),("屈原", "端午"),("雄黄酒", "五彩绳"),("菖蒲", "艾叶"),
        ("汤圆", "花灯"),("猜谜", "舞龙"),("元宵", "正月"),("团圆", "赏灯"),("烟花", "爆竹"),
        ("扫墓", "踏青"),("清明", "寒食"),("柳枝", "纸钱"),("祭祖", "插柳"),("青团", "寒食饼"),
        ("牛郎", "织女"),("鹊桥", "银河"),("七夕", "乞巧"),("针线", "巧果"),("爱情", "相会"),
        ("重阳", "登高"),("菊花", "茱萸"),("敬老", "赏菊"),("九月", "重九"),("菊花酒", "重阳糕"),
        ("腊八", "腊八粥"),("腊月", "年关"),("腊肉", "腊肠"),("祭灶", "小年"),("年货", "办年"),
        ("立春", "雨水"),("惊蛰", "春分"),("清明", "谷雨"),("立夏", "小满"),("芒种", "夏至"),
        ("小暑", "大暑"),("立秋", "处暑"),("白露", "秋分"),("寒露", "霜降"),("立冬", "小雪"),
        ("大雪", "冬至"),("小寒", "大寒"),("节气", "农历"),("阳历", "阴历"),("公历", "农历"),
        ("勇敢", "胆小"),("聪明", "愚笨"),("勤奋", "懒惰"),("诚实", "虚伪"),("善良", "邪恶"),
        ("成功", "失败"),("胜利", "失败"),("进步", "退步"),("提高", "下降"),("增加", "减少"),
        ("开始", "结束"),("出发", "到达"),("离开", "回来"),("进入", "出去"),("上升", "下降"),
        ("春雨", "秋风"),("夏日", "冬雪"),("朝阳", "夕阳"),("星空", "月夜"),("彩虹", "闪电"),
        ("山峰", "海浪"),("森林", "沙漠"),("花园", "菜园"),("果园", "茶园"),("竹林", "松林"),
        ("小溪", "大河"),("池塘", "湖泊"),("瀑布", "温泉"),("井水", "泉水"),("雨水", "雪水"),
        ("白云", "乌云"),("晴空", "阴天"),("微风", "狂风"),("细雨", "暴雨"),("小雪", "大雪"),
        ("日出", "日落"),("黎明", "黄昏"),("正午", "午夜"),("清晨", "深夜"),("傍晚", "凌晨"),
        ("童年", "青年"),("中年", "老年"),("少年", "成年"),("幼儿", "儿童"),("青春", "暮年"),
        
    ]

# 开始游戏命令
StartGame = on_regex(pattern=r'^开始谁是卧底$', priority=1)
@StartGame.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    # 检查是否已有游戏在进行
    if group_id in games and games[group_id].status != UndercoverGameStatus.WAITING and games[group_id].status != UndercoverGameStatus.ENDED:
        await StartGame.finish(message="游戏已经在进行中，请等待当前游戏结束")
        return
    
    # 创建新游戏
    games[group_id] = UndercoverGame(group_id)
    games[group_id].status = UndercoverGameStatus.SIGNUP
    
    await StartGame.finish(message="谁是卧底游戏开始报名！请想参加的玩家发送「报名卧底」。发送「结束报名」开始游戏。")
    
    # 300秒后自动结束报名
    await asyncio.sleep(300)
    
    if group_id in games and games[group_id].status == UndercoverGameStatus.SIGNUP:
        if len(games[group_id].players) < 3:
            await bot.send_group_msg(group_id=group_id, message="报名人数不足3人，游戏取消")
            del games[group_id]
        else:
            await start_game_process(bot, group_id)


# 报名命令
SignupGame = on_regex(pattern=r'^报名卧底$', priority=1)
@SignupGame.handle()
async def handle_signup(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].status != UndercoverGameStatus.SIGNUP:
        await SignupGame.finish(message="当前没有谁是卧底游戏正在报名")
        return
    
    if user_id in games[group_id].players:
        await SignupGame.finish(message="你已经报名了")
        return
    
    # 添加玩家
    games[group_id].players[user_id] = {
        "nickname": event.sender.nickname,
        "user_id": event.user_id,
        "word": "",
        "is_undercover": False,
        "eliminated": False,
        "code": len(games[group_id].players) + 1  # 为每个玩家分配一个编号，从1开始
    }

    msg = (
            MessageSegment.at(event.user_id) + 
            Message(f"{event.sender.nickname} (编号:{len(games[group_id].players)})报名成功！当前已有 {len(games[group_id].players)} 人报名")
    )
    await SignupGame.finish(message=Message(msg))
    
    # await SignupGame.finish(message=f"{event.sender.nickname} (编号:{len(games[group_id].players)})报名成功！当前已有 {len(games[group_id].players)} 人报名")

# 结束报名命令
EndSignup = on_regex(pattern=r'^结束报名$', priority=1)
@EndSignup.handle()
async def handle_end_signup(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    
    if group_id not in games or games[group_id].status != UndercoverGameStatus.SIGNUP:
        await EndSignup.finish(message="当前没有谁是卧底游戏正在报名")
        return
    
    if len(games[group_id].players) < 3:
        await EndSignup.finish(message="报名人数不足3人，无法开始游戏")
        return
    
    await start_game_process(bot, group_id)

# 开始游戏流程
async def start_game_process(bot: Bot, group_id: int):
    game = games[group_id]
    game.status = UndercoverGameStatus.PLAYING
    
   # 获取词库并分配词语和身份
    await assign_words_and_roles(bot, group_id)
    
    # 发送换词提示
    change_word_msg = f"词语已分配完成，是否需要更换词语和身份？\n发送「换词」重新分配，发送「不换词」开始游戏。\n30秒后将自动开始游戏。"
    await bot.send_group_msg(group_id=group_id, message=change_word_msg)
    
    # 设置换词计时器
    if game.change_word_timer:
        game.change_word_timer.cancel()
    game.change_word_timer = asyncio.create_task(change_word_timer(bot, group_id))

# 分配词语和身份
async def assign_words_and_roles(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 获取词库
    word_pairs = await fetch_word_pairs()
    chosen_pair = random.choice(word_pairs)
    game.words = chosen_pair
    
    # 决定谁是卧底
    player_ids = list(game.players.keys())
    num_players = len(player_ids)
    
    # 根据人数决定卧底数量
    num_undercovers = 1
    if num_players >= 6:
        num_undercovers = 2
    if num_players >= 9:
        num_undercovers = 3
    
    # 随机选择卧底
    undercover_indices = random.sample(range(num_players), num_undercovers)
    
    # 分配词语
    for i, player_id in enumerate(player_ids):
        is_undercover = i in undercover_indices
        game.players[player_id]["is_undercover"] = is_undercover
        game.players[player_id]["word"] = game.words[1] if is_undercover else game.words[0]
    
    # 决定发言顺序
    game.speaking_order = player_ids.copy()
    random.shuffle(game.speaking_order)
    game.current_speaker_index = 0
    game.current_round = 1
    
    # 发送游戏开始消息
    await bot.send_group_msg(group_id=group_id, message=f"游戏开始！共有{num_players}名玩家，其中{num_undercovers}名卧底。我已经私聊告知大家各自的词语，请查看。")
    
    # 私聊发送词语
    failed_users = []
    for player_id, player_info in game.players.items():
        try:
            await bot.send_private_msg(user_id=player_id, message=f"你的词语是：{player_info['word']}")
        except Exception as e:
            print(f"向玩家 {player_id} 发送私聊失败: {e}")
            failed_users.append(player_id)
    
    # 如果有私聊发送失败的用户，提醒他们添加机器人为好友
    if failed_users:
        reminder_msg = "部分玩家无法接收私聊消息。请通过私聊机器人发送「查询身份」来获取你的身份牌。"
        await bot.send_group_msg(group_id=group_id, message=reminder_msg)
        await asyncio.sleep(5)

# 换词计时器
async def change_word_timer(bot: Bot, group_id: int):
    await asyncio.sleep(30)
    
    if group_id in games and games[group_id].status == UndercoverGameStatus.PLAYING:
        game = games[group_id]
        if game.change_word_timer and not game.change_word_timer.cancelled():
            await bot.send_group_msg(group_id=group_id, message="时间到，开始游戏！")
            # 开始第一轮发言
            await start_speaking_round(bot, group_id)

# 换词命令
ChangeWord = on_regex(pattern=r'^换词$', priority=1)
@ChangeWord.handle()
async def handle_change_word(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].status != UndercoverGameStatus.PLAYING:
        await ChangeWord.finish(message="当前没有进行中的谁是卧底游戏")
        return
    
    game = games[group_id]
    
    # 检查是否是游戏参与者
    if user_id not in game.players:
        await ChangeWord.finish(message="只有游戏参与者才能发起换词")
        return
    
    # 检查是否在换词阶段
    if not game.change_word_timer or game.change_word_timer.cancelled():
        await ChangeWord.finish(message="当前不在换词阶段")
        return
    
    # 取消计时器
    game.change_word_timer.cancel()
    
    await bot.send_group_msg(group_id=group_id, message="正在重新分配词语和身份...")
    
    # 重新分配词语和身份
    await assign_words_and_roles(bot, group_id)
    
    # 重新发送换词提示
    change_word_msg = f"词语已重新分配，是否需要更换词语和身份？\n发送「换词」重新分配，发送「不换词」开始游戏。\n30秒后将自动开始游戏。"
    await bot.send_group_msg(group_id=group_id, message=change_word_msg)
    
    # 重新设置换词计时器
    game.change_word_timer = asyncio.create_task(change_word_timer(bot, group_id))

# 不换词命令
KeepWord = on_regex(pattern=r'^不换词$', priority=1)
@KeepWord.handle()
async def handle_keep_word(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    if group_id not in games or games[group_id].status != UndercoverGameStatus.PLAYING:
        await KeepWord.finish(message="当前没有进行中的谁是卧底游戏")
        return
    
    game = games[group_id]
    
    # 检查是否是游戏参与者
    if user_id not in game.players:
        await KeepWord.finish(message="只有游戏参与者才能决定是否换词")
        return
    
    # 检查是否在换词阶段
    if not game.change_word_timer or game.change_word_timer.cancelled():
        await KeepWord.finish(message="当前不在换词阶段")
        return
    
    # 取消计时器
    game.change_word_timer.cancel()
    
    await bot.send_group_msg(group_id=group_id, message="开始游戏！")
    
    # 开始第一轮发言
    await start_speaking_round(bot, group_id)

# 添加新的命令处理器用于私聊查询身份
QueryIdentity = on_regex(pattern=r'^查询身份$', priority=1)
@QueryIdentity.handle()
async def handle_query_identity(bot: Bot, event: PrivateMessageEvent, state: T_State):
    user_id = event.user_id
    
    # 查找用户所在的游戏
    user_game = None
    user_group_id = None
    for group_id, game in games.items():
        if user_id in game.players and game.status == UndercoverGameStatus.PLAYING:
            user_game = game
            user_group_id = group_id
            break
    
    if not user_game:
        await QueryIdentity.finish(message="你当前没有参加任何进行中的谁是卧底游戏")
        return
    
    # 发送身份信息
    player_info = user_game.players[user_id]
    await QueryIdentity.finish(message=f"你的词语是：{player_info['word']}")

# 开始一轮发言
async def start_speaking_round(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 检查游戏是否应该结束
    if should_end_game(game):
        await end_game(bot, group_id)
        return
    
    await bot.send_group_msg(group_id=group_id, message=f"第 {game.current_round} 轮发言开始！")
    
    # 开始第一个人发言
    await next_player_speak(bot, group_id)

# 下一个玩家发言
async def next_player_speak(bot: Bot, group_id: int):
    game = games[group_id]
    
    # 检查是否所有人都发言完毕
    if game.current_speaker_index >= len(game.speaking_order):
        # 一轮结束，开始投票
        game.current_speaker_index = 0
        game.status = UndercoverGameStatus.VOTING
        game.votes = {}
        result_msg = ""

        # 添加本轮发言记录
        result_msg += f"\n【第 {game.current_round} 轮发言记录】\n"
        for i, player_id in enumerate(game.speaking_order):
            player_info = game.players[player_id]
            if not player_info["eliminated"]:
                player_speech = "未发言"
                if player_id in game.player_speeches and len(game.player_speeches[player_id]) >= game.current_round:
                    player_speech = game.player_speeches[player_id][game.current_round - 1]
                result_msg += f"{player_info['code']}号 {player_info['nickname']}: ({player_speech})\n"

        result_msg += "\n【玩家列表】\n"
    
        for player_id, player_info in game.players.items():
            status = "（已淘汰）" if player_info["eliminated"] else "（存活）"
            result_msg += f"编号：【{player_info['code']}】{player_info['nickname']}： {status}\n"
        
        await bot.send_group_msg(group_id=group_id, message=f"本轮发言结束，开始投票！请发送「投票 玩家昵称|编号」进行投票。60秒后投票结束。{result_msg}")
        
        # 设置投票计时器
        if game.vote_timer:
            game.vote_timer.cancel()
        game.vote_timer = asyncio.create_task(vote_timer(bot, group_id))
        return
    
    # 获取当前发言人
    current_speaker_id = game.speaking_order[game.current_speaker_index]
    current_speaker = game.players[current_speaker_id]
    
    # 检查玩家是否已被淘汰
    if current_speaker["eliminated"]:
        game.current_speaker_index += 1
        await next_player_speak(bot, group_id)
        return
    
    msg = (
        MessageSegment.at(current_speaker['user_id']) + 
        Message(f"请 {current_speaker['code']} 号玩家 - {current_speaker['nickname']} 发言（请以【发言】开头），60秒后结束。")
    )
    await bot.send_group_msg(group_id=group_id, message=msg)
    
    # 设置发言计时器
    if game.speaking_timer:
        game.speaking_timer.cancel()
    game.speaking_timer = asyncio.create_task(speaking_timer(bot, group_id))

# 发言计时器
async def speaking_timer(bot: Bot, group_id: int):
    await asyncio.sleep(60)
    
    if group_id in games and games[group_id].status == UndercoverGameStatus.PLAYING:
        game = games[group_id]
        current_speaker_id = game.speaking_order[game.current_speaker_index]
        current_speaker = game.players[current_speaker_id]
        
        await bot.send_group_msg(
            group_id=group_id, 
            message=f"{current_speaker['nickname']} 超时未发言！请记得以【发言】开头进行发言。"
        )
        
        # 移动到下一个发言人
        game.current_speaker_index += 1
        await next_player_speak(bot, group_id)

# 投票计时器
async def vote_timer(bot: Bot, group_id: int):
    await asyncio.sleep(60)
    
    if group_id in games and games[group_id].status == UndercoverGameStatus.VOTING:
        await end_voting(bot, group_id)

# 处理投票
VoteCommand = on_regex(pattern=r'^投票\s+(.+)$', priority=1)
@VoteCommand.handle()
async def handle_vote(bot: Bot, event: MessageEvent, state: T_State):
    user_id = event.user_id
    
    # 查找用户所在的游戏
    user_game = None
    user_group_id = None
    for group_id, game in games.items():
        if user_id in game.players and game.status == UndercoverGameStatus.VOTING and not game.players[user_id]["eliminated"]:
            user_game = game
            user_group_id = group_id
            break
    if not user_game:
        await VoteCommand.finish(message="你没有参加任何正在投票的谁是卧底游戏")
        return
    
    # 获取投票目标
    vote_target = state["_matched"].group(1).strip()
    target_id = None
    
    # 支持通过编号或昵称进行投票
    try:
        # 尝试将输入解析为编号
        target_code = int(vote_target)
        # 通过编号查找玩家
        for pid, pinfo in user_game.players.items():
            if pinfo["code"] == target_code and not pinfo["eliminated"]:
                target_id = pid
                break
    except ValueError:
        # 如果不是编号，则按昵称查找
        for pid, pinfo in user_game.players.items():
            if pinfo["nickname"] == vote_target and not pinfo["eliminated"]:
                target_id = pid
                break
    
    if not target_id:
        await VoteCommand.finish(message=f"找不到玩家 {vote_target}，请确认玩家昵称或编号是否正确")
        return
    
    if target_id == user_id:
        await VoteCommand.finish(message="不能投票给自己")
        return
    
    # 记录投票
    user_game.votes[user_id] = target_id
    
    # 获取被投票玩家的昵称
    target_nickname = user_game.players[target_id]["nickname"]
    target_code = user_game.players[target_id]["code"]
    
    await VoteCommand.send(message=f"{user_game.players[user_id]['nickname']} 投票给了 {target_code}号玩家 {target_nickname}")
    
    # 检查是否所有存活玩家都已投票
    alive_players = [pid for pid, pinfo in user_game.players.items() if not pinfo["eliminated"]]
    if all(pid in user_game.votes for pid in alive_players):
        # 如果所有存活玩家都已投票，立即结束投票
        if user_game.vote_timer:
            user_game.vote_timer.cancel()
        await end_voting(bot, user_group_id)

# 结束投票
async def end_voting(bot: Bot, group_id: int):
    game = games[group_id]
    game.status = UndercoverGameStatus.PLAYING
    
       # 统计投票结果
    vote_count = {}
    for target_id in game.votes.values():
        vote_count[target_id] = vote_count.get(target_id, 0) + 1
    
    # 找出得票最多的玩家
    max_votes = 0
    eliminated_player_id = None
    
    for player_id, votes in vote_count.items():
        if votes > max_votes:
            max_votes = votes
            eliminated_player_id = player_id
    
    
    # 处理平票情况
    tied_players = [pid for pid, votes in vote_count.items() if votes == max_votes]
    if len(tied_players) > 1:
        # 平票随机选择一人
        eliminated_player_id = random.choice(tied_players)
    
    if eliminated_player_id:
        # 标记玩家为已淘汰
        game.players[eliminated_player_id]["eliminated"] = True
        eliminated_player = game.players[eliminated_player_id]

        result_msg = ""
        result_msg += "\n【玩家列表】\n"
        
        for player_id, player_info in game.players.items():
            status = "（已淘汰）" if player_info["eliminated"] else "（存活）"
            result_msg += f"编号：【{player_info['code']}】{player_info['nickname']}： {status}\n"
        
        # 发送淘汰消息
        await bot.send_group_msg(group_id=group_id, message=f"投票结束，{eliminated_player['nickname']} 被淘汰！{result_msg}")
        
        # 检查游戏是否结束
        if should_end_game(game):
            await end_game(bot, group_id)
            return
        
        # 进入下一轮
        game.current_round += 1
        #  # 统计存活的卧底和平民数量
        # alive_undercovers = 0
        # alive_civilians = 0
        
        # for player_id, player_info in game.players.items():
        #     if not player_info["eliminated"]:
        #         if player_info["is_undercover"]:
        #             alive_undercovers += 1
        #         else:
        #             alive_civilians += 1
        # # 如果只剩下2名平民和1名卧底，进入最终投票
        # if alive_civilians == 2 and alive_undercovers == 1:
        #     # 所有轮次结束，进入最终投票
        #     await final_vote(bot, group_id)
        #     return
        # if game.current_round > game.max_rounds:
        #     # 所有轮次结束，进入最终投票
        #     await final_vote(bot, group_id)
        #     return
        
        # 开始新一轮发言
        await start_speaking_round(bot, group_id)
    else:
        result_msg = ""
        result_msg += "\n【玩家列表】\n"
        
        for player_id, player_info in game.players.items():
            status = "（已淘汰）" if player_info["eliminated"] else "（存活）"
            result_msg += f"编号：【{player_info['code']}】{player_info['nickname']}： {status}\n"
        # 没有人被淘汰，继续游戏
        await bot.send_group_msg(group_id=group_id, message=f"本轮没有人被淘汰，继续游戏！{result_msg}")
        game.current_round += 1
        await start_speaking_round(bot, group_id)

# 最终投票
async def final_vote(bot: Bot, group_id: int):
    game = games[group_id]
    
    await bot.send_group_msg(group_id=group_id, message="所有轮次已结束，进入最终投票！请发送「投票 玩家昵称」进行最终投票。30秒后投票结束。")
    
    game.status = UndercoverGameStatus.VOTING
    game.votes = {}
    
    # 设置投票计时器
    if game.vote_timer:
        game.vote_timer.cancel()
    game.vote_timer = asyncio.create_task(vote_timer(bot, group_id))

# 检查游戏是否应该结束
def should_end_game(game: UndercoverGame) -> bool:
    # 统计存活的卧底和平民数量
    alive_undercovers = 0
    alive_civilians = 0
    
    for player_id, player_info in game.players.items():
        if not player_info["eliminated"]:
            if player_info["is_undercover"]:
                alive_undercovers += 1
            else:
                alive_civilians += 1

    # 如果卧底全部被淘汰，平民胜利
    if alive_undercovers == 0:
        return True
    
    # 如果卧底数量大于等于平民数量，卧底胜利
    if alive_undercovers >= alive_civilians:
        return True
    
    return False

# 结束游戏
async def end_game(bot: Bot, group_id: int):
    game = games[group_id]
    game.status = UndercoverGameStatus.ENDED
    # 统计存活的卧底和平民数量
    alive_undercovers = 0
    alive_civilians = 0
    
    for player_id, player_info in game.players.items():
        if not player_info["eliminated"]:
            if player_info["is_undercover"]:
                alive_undercovers += 1
            else:
                alive_civilians += 1
    # 确定胜利方并更新积分
    try:
        if alive_undercovers == 0:
            winner = "平民"
            # 平民胜利，所有平民+10分
            for player_id, player_info in game.players.items():
                if not player_info["is_undercover"]:
                    print(f"正在给平民 {player_info['nickname']} 添加积分")
                    await update_player_score(
                        str(player_id),
                        str(group_id),
                        10,
                        'undercover',
                        '平民',
                        'win'
                    )
        else:
            winner = "卧底"
            # 卧底胜利，所有卧底+15分
            for player_id, player_info in game.players.items():
                if player_info["is_undercover"]:
                    print(f"正在给卧底 {player_info['nickname']} 添加积分")
                    await update_player_score(
                        str(player_id),
                        str(group_id),
                        15,
                        'undercover',
                        '卧底',
                        'win'
                    )
        print("胜利方积分更新完成")
    except Exception as e:
        print(f"更新胜利方积分时出错：{str(e)}")
    # 给所有参与者加5分参与奖励
    for player_id in game.players:
        await update_player_score(
            str(player_id),
            str(group_id),
            5,
            'undercover',
            '参与奖励',
            'participation'
        )
    
    # 生成游戏结果消息
    result_msg = f"游戏结束！{winner}获胜！\n\n"
    result_msg += f"平民词语：{game.words[0]}\n"
    result_msg += f"卧底词语：{game.words[1]}\n\n"
    result_msg += "玩家身份：\n"
    
    for player_id, player_info in game.players.items():
        role = "卧底" if player_info["is_undercover"] else "平民"
        status = "（已淘汰）" if player_info["eliminated"] else "（存活）"
        result_msg += f"{player_info['nickname']}：{role} {status}\n"
    
    await bot.send_group_msg(group_id=group_id, message=result_msg)
    
    # 清理游戏数据
    if group_id in games:
        del games[group_id]

# 强制结束游戏命令
ForceEndGame = on_regex(pattern=r'^结束谁是卧底$', priority=1)
@ForceEndGame.handle()
async def handle_force_end_game(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    
    if group_id not in games:
        await ForceEndGame.finish(message="当前没有进行中的谁是卧底游戏")
        return
    
    # 检查是否是管理员
    admins = await bot.get_group_member_list(group_id=event.group_id)
    user_id = event.user_id
    is_admin = any(
        admin["user_id"] == user_id and 
        (admin["role"] in ["admin", "owner"]) 
        for admin in admins
    )
    
    if not is_admin:
        await ForceEndGame.finish(message="只有管理员才能强制结束游戏")
        return
    
    if games[group_id].status != UndercoverGameStatus.ENDED:
        await end_game(bot, group_id)
    else:
        await ForceEndGame.finish(message="游戏已经结束")

# 查看游戏状态命令
CheckGameStatus = on_regex(pattern=r'^谁是卧底状态$', priority=1)
@CheckGameStatus.handle()
async def handle_game_status(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    
    if group_id not in games:
        await CheckGameStatus.finish(message="当前没有进行中的谁是卧底游戏")
        return
    
    game = games[group_id]
    status_text = ""
    
    if game.status == UndercoverGameStatus.WAITING:
        status_text = "等待开始"
    elif game.status == UndercoverGameStatus.SIGNUP:
        status_text = "报名中"
    elif game.status == UndercoverGameStatus.PLAYING:
        status_text = f"游戏进行中，第{game.current_round}轮"
    elif game.status == UndercoverGameStatus.VOTING:
        status_text = "投票中"
    elif game.status == UndercoverGameStatus.ENDED:
        status_text = "已结束"
    
    player_count = len(game.players)
    alive_count = sum(1 for p in game.players.values() if not p["eliminated"])
    
    msg = f"谁是卧底游戏状态：{status_text}\n"
    msg += f"玩家数量：{player_count}人，存活：{alive_count}人\n"
    
    if game.status == UndercoverGameStatus.PLAYING or game.status == UndercoverGameStatus.VOTING:
        msg += "存活玩家：\n"
        for player_id, player_info in game.players.items():
            if not player_info["eliminated"]:
                msg += f"- {player_info['nickname']}\n"
    
    await CheckGameStatus.finish(message=msg)

# 谁是卧底游戏帮助命令
UndercoverHelp = on_regex(pattern=r'^谁是卧底帮助$', priority=1)
@UndercoverHelp.handle()
async def handle_undercover_help(bot: Bot, event: GroupMessageEvent, state: T_State):
    help_msg = """谁是卧底游戏指令说明：
1. 开始谁是卧底 - 开始一局新游戏并进入报名阶段
2. 报名卧底 - 报名参加游戏
3. 结束报名 - 提前结束报名阶段并开始游戏
4. 投票 玩家昵称|编号 - 在投票阶段通过私聊投票淘汰可疑玩家
5. 谁是卧底状态 - 查看当前游戏状态
6. 结束谁是卧底 - 强制结束当前游戏（仅管理员可用）
7. 谁是卧底帮助 - 显示此帮助信息
8. 发言 内容 - 在发言阶段发言

游戏规则：
1. 每位玩家会收到一个词语，其中大多数人收到相同的词（平民），少数人收到不同的词（卧底）
2. 每轮游戏中，所有玩家轮流描述自己拿到的词语，但不能直接说出该词
3. 每轮结束后进行投票，票数最多的玩家将被淘汰
4. 如果所有卧底被淘汰，平民获胜；如果卧底数量大于等于平民数量，卧底获胜
"""
    await UndercoverHelp.finish(message=help_msg)

# 添加发言命令处理
Speaking = on_regex(pattern=r'^发言\s*(.*)$', priority=1)
@Speaking.handle()
async def handle_speak_message(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    user_id = event.user_id
    
    # 检查是否在游戏中且轮到该玩家发言
    if group_id not in games or games[group_id].status != UndercoverGameStatus.PLAYING:
        return
    
    game = games[group_id]
    # if game.current_speaker_index >= len(game.speaking_order):
    #     return
    # 检查是否轮到该玩家发言
    if game.current_speaker_index >= len(game.speaking_order) or game.speaking_order[game.current_speaker_index] != user_id:
        return
        
    # 获取发言内容
    speech_content = state["_matched"].group(1).strip()
    if not speech_content:
        await SpeakCommand.finish(message="发言内容不能为空")
        return

    current_speaker_id = game.speaking_order[game.current_speaker_index]
    if user_id != current_speaker_id:
        return

    # 记录发言
    if user_id not in game.player_speeches:
        game.player_speeches[user_id] = []
    game.player_speeches[user_id].append(speech_content)
    
    # 取消发言计时器
    if game.speaking_timer:
        game.speaking_timer.cancel()
    
    # 移动到下一个发言人
    game.current_speaker_index += 1

    # await SpeakCommand.finish(message=f"{game.players[user_id]['nickname']} 发言完毕")

    await next_player_speak(bot, group_id)