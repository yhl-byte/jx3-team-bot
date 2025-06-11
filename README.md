<!--
 * @Date: 2025-03-10 11:39:44
 * @LastEditors: yhl yuhailong@thalys-tech.onaliyun.com
 * @LastEditTime: 2025-06-11 16:30:37
 * @FilePath: /team-bot/jx3-team-bot/README.md
-->
# 年崽机器人 (JX3 Team Bot)

一个基于 NoneBot2 开发的多功能 QQ 机器人，专为剑网3玩家和游戏爱好者设计。

## ✨ 功能特色

### 🎮 剑网3 相关功能
- **角色查询**：角色属性、装备、奇遇记录等
- **服务器信息**：开服状态、沙盘信息等
- **团队管理**：团队创建、成员管理、位置分配

### 🎯 游戏娱乐
- **谁是卧底**：经典推理游戏
- **猜歌游戏**：音乐竞猜挑战
- **21点**：经典纸牌游戏
- **俄罗斯轮盘**：刺激的运气游戏
- **人生重开**：模拟人生体验
- **海龟汤**：逻辑推理游戏
- **其他小游戏**：掷骰子、猜词等

### 🛠️ 实用工具
- **天气查询**：实时天气信息
- **游戏积分**：积分统计和排行榜
- **HTML生成**：自定义页面生成

## 🚀 快速开始

### 环境要求
- Python 3.9+
- Poetry（推荐）或 pip
- wkhtmltopdf（用于图片生成）

### 安装方式

#### 方式一：使用 Poetry（推荐）
```bash
# 克隆项目
git clone <repository-url>
cd jx3-team-bot

# 安装依赖
poetry install

# 激活虚拟环境
poetry shell

# 运行机器人
nb run
```
#### 方式二：使用 pip
```bash
# 克隆项目
git clone <repository-url>
cd jx3-team-bot

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 运行机器人
nb run
```
#### 方式三：Docker 部署
```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d
```

jx3-team-bot/
├── src/
│   ├── plugins/          # 插件目录
│   │   ├── jx3_api.py   # 剑网3 API 功能
│   │   ├── jx3_team.py  # 团队管理
│   │   ├── games/       # 游戏插件
│   │   └── utils/       # 工具插件
│   ├── utils/           # 工具模块
│   ├── templates/       # HTML 模板
│   ├── static/          # 静态资源
│   ├── data/           # 数据文件
│   └── config.py       # 配置文件
├── pyproject.toml      # 项目配置
├── requirements.txt    # 依赖列表
├── docker-compose.yml  # Docker 配置
└── README.md          # 项目说明


##  使用指南
### 基础命令
- 帮助 - 查看所有可用命令
- 天气 [城市] - 查询天气信息
- 掷骰子 [面数] - 掷骰子游戏
### 剑网3 功能
- 角色 [服务器] [角色名] - 查询角色信息
- 开服 [服务器] - 查询服务器状态
- 创建团队 [团队名] - 创建新团队
### 游戏功能
- 谁是卧底 - 开始谁是卧底游戏
- 猜歌 - 开始猜歌游戏
- 21点 - 开始21点游戏
- 俄罗斯轮盘 - 开始俄罗斯轮盘
## 🔧 开发指南
### 添加新插件
1. 在 src/plugins/ 目录下创建新的 Python 文件
2. 使用 NoneBot2 的插件开发规范
3. 在插件中实现相应的命令处理逻辑


##  更新日志
### v0.1.0
- 初始版本发布
- 实现基础的剑网3功能
- 添加多种游戏插件
- 支持天气查询等实用功能
## 🤝 贡献指南
1. Fork 本项目
2. 创建特性分支 ( git checkout -b feature/AmazingFeature )
3. 提交更改 ( git commit -m 'Add some AmazingFeature' )
4. 推送到分支 ( git push origin feature/AmazingFeature )
5. 开启 Pull Request
## 📄 许可证
本项目采用 MIT 许可证 - 查看 LICENSE 文件了解详情

## 🙏 致谢
- NoneBot2 - 优秀的 Python 异步机器人框架
- 剑网3 API - 提供剑网3相关数据接口
- 所有贡献者和用户的支持
## 📞 联系方式
- 作者：yuhailong
- 项目地址： GitHub Repository
如果这个项目对你有帮助，请给个 ⭐ Star 支持一下