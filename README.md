# BT种子管理系统 (Private Tracker)

一个功能完整的私有 BT (BitTorrent) 种子追踪站点，基于 Flask 3.1 + SQLAlchemy 2.0 + Bootstrap 5.3 构建。

---

## 免责声明

**本项目仅供学习和技术研究使用，严禁用于任何违法用途。**

1. **版权声明**：本项目不提供任何版权内容。所有种子文件仅包含元数据（文件名、大小、哈希值），不包含受版权保护的实际文件内容。

2. **使用限制**：使用者应遵守所在国家/地区的法律法规。禁止利用本系统传播盗版、侵权或非法内容。

3. **责任豁免**：开发者不对使用者利用本系统进行的任何行为承担责任。使用本系统即表示您同意自行承担所有相关法律责任。

4. **数据安全**：本系统涉及用户IP地址、上传/下载记录等隐私数据，部署者应妥善保护数据安全，遵守相关隐私法规。

5. **无担保声明**：本软件按"原样"提供，不提供任何明示或暗示的担保，包括但不限于适销性、特定用途适用性和非侵权的担保。

6. **合规提醒**：
   - 不要在未授权的服务器上部署此系统
   - 不要使用此系统分享受版权保护的内容
   - 如发现侵权内容，应立即删除
   - 建议仅在内网或授权环境中运行

---

## 目录

1. [系统架构](#系统架构)
2. [核心原理](#核心原理)
3. [功能特性](#功能特性)
4. [技术栈](#技术栈)
5. [快速开始](#快速开始)
6. [项目结构](#项目结构)
7. [数据库模型](#数据库模型)
8. [权限体系](#权限体系)
9. [Tracker协议](#tracker协议)
10. [分享率与H&R](#分享率与hr)
11. [用户等级体系](#用户等级体系)
12. [积分经济系统](#积分经济系统)
13. [管理后台](#管理后台)
14. [QBitTorrent集成](#qbittorrent集成)
15. [IP管理与安全](#ip管理与安全)
16. [配置说明](#配置说明)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                              │
│                   (Bootstrap 5.3 + Chart.js)                 │
└──────────┬──────────────────────────────────────┬───────────┘
           │ HTTP/HTTPS                           │ HTTP/HTTPS
           ▼                                      ▼
┌──────────────────────┐              ┌───────────────────────┐
│   Web 应用层          │              │    Tracker 追踪层      │
│   (Flask Blueprints) │              │   (Bencode协议)        │
│                      │              │                       │
│  • main   首页/浏览   │              │ /announce/<passkey>   │
│  • auth   认证/注册   │              │ /scrape               │
│  • torrent 种子管理  │              │                       │
│  • user   用户中心    │              │  BitTorrent客户端     │
│  • bonus  积分中心    │              │  (qBittorrent等)      │
│  • forum  论坛        │              └───────────┬───────────┘
│  • admin  管理后台    │                          │
│  • api    JSON API    │                          │
│  • rss    RSS订阅     │                          │
└──────────┬───────────┘                          │
           │                                      │
           ▼                                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    业务服务层 (Services)                       │
│                                                             │
│  • tracker_logic      Announce/Scrape核心逻辑                │
│  • bencode_service    Bencode编解码                          │
│  • bonus_calculator   积分计算                                │
│  • hnr_checker        H&R检测                                │
│  • admin_permission   精细权限验证                            │
│  • ip_service         IP管理/多账号检测                       │
│  • ban_service        封禁系统                                │
│  • promotion_service  自动升降级                              │
│  • qbittorrent_service QB集成                                 │
│  • stats_service      流量统计                                │
└──────────┬──────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                   数据持久层 (SQLAlchemy ORM)                  │
│                                                             │
│  15+ 数据模型: User, Torrent, Peer, Snatch, Category,        │
│  BonusShopItem, BanLog, IpLog, UserClass, ...                │
└──────────┬──────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────┐  ┌───────────────────────────────────┐
│   SQLite 数据库       │  │   APScheduler 后台任务调度         │
│   (WAL模式)           │  │                                   │
│                      │  │  • Peer过期清理 (每10分钟)          │
│                      │  │  • 积分发放 (每小时)               │
│                      │  │  • 每日重置 (凌晨0点)              │
│                      │  │  • H&R扫描 (每6小时)              │
│                      │  │  • 自动解封 (每小时)               │
│                      │  │  • 自动升降级 (每3小时)            │
│                      │  │  • QB同步 (每30分钟)               │
│                      │  │  • 做种时间累计 (每10分钟)         │
└──────────────────────┘  └───────────────────────────────────┘
```

### 架构设计原则

1. **分层架构**：Web层 → 服务层 → 数据层，职责清晰分离
2. **蓝本模式**：Flask Blueprint实现模块化路由，9个蓝本各司其职
3. **装饰器模式**：`@role_required` / `@permission_required` 实现声明式权限控制
4. **服务层抽象**：核心业务逻辑独立为Service类，可在路由和CLI中复用
5. **事件驱动**：Tracker Announce事件驱动Peer状态更新和统计累计

---

## 核心原理

### 1. BitTorrent协议与私有Tracker

#### 1.1 BitTorrent基础

BitTorrent是一种点对点(P2P)文件分发协议。核心概念：

- **种子文件(.torrent)**：包含元数据——文件名、大小、分片大小(Piece Length)、分片哈希值列表、Tracker URL
- **Info Hash**：种子文件中"info"字典的SHA-1哈希，是种子的唯一标识符(40字符hex)
- **Peer**：参与下载/上传的客户端节点
- **Seeder(做种者)**：拥有完整文件并正在上传的Peer
- **Leecher(下载者)**：正在下载文件的Peer
- **Tracker**：协调Peer之间通信的中心服务器

#### 1.2 私有Tracker原理

```
                    ┌──────────┐
                    │  Tracker │  ← 本项目的核心
                    └────┬─────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────┴────┐     ┌────┴────┐     ┌────┴────┐
   │ Seeder  │     │ Leecher │     │ Leecher │
   │ 100%    │     │  45%    │     │  0%     │
   └─────────┘     └─────────┘     └─────────┘
        │                │                │
        └────────────────┴────────────────┘
                  直接P2P传输
```

**Announce流程**：

1. BT客户端定期(默认30分钟)向Tracker发送HTTP GET请求
2. 请求携带`info_hash`、`peer_id`、`port`、`uploaded`、`downloaded`、`left`等参数
3. Tracker返回可用Peer列表(compact格式)
4. 客户端之间建立P2P连接进行数据传输
5. Tracker记录统计数据(上传/下载量、做种/下载时间)

**私有标志**：Torrent模型的`is_private=True`会在种子文件中设置`private=1`标志，
DHT和PEX等去中心化发现机制将被禁用，确保所有Peer发现都通过中心Tracker。

#### 1.3 分享率机制

```
分享率(Ratio) = 上传量 ÷ 下载量

- Ratio ≥ 2.0  → 优秀 (绿色)  — 可下载所有内容
- Ratio ≥ 1.0  → 良好 (蓝色)  — 可下载所有内容
- Ratio ≥ 0.5  → 警告 (黄色)  — 部分限制
- Ratio < 0.4   → 危险 (红色)  — 禁止下载新种子
```

系统记录**两类统计数据**：
- **名义上传/下载**(uploaded/downloaded)：受促销策略影响的实际统计量(免费的种子下载不计入)
- **真实上传/下载**(real_uploaded/real_downloaded)：不受促销影响的物理传输量

**促销策略**：
- **Freeleech(免费)**：下载不计入统计(`effective_down = 0`)，上传正常计算
- **Double Upload(双倍上传)**：上传量按2倍计算(`effective_up *= 2`)
- **Half Download(半下载)**：下载量按50%计算(`effective_down /= 2`)

### 2. 用户等级体系 (UserClass)

系统通过自动化的5级等级体系激励用户贡献：

```
Lv0 普通用户 (User)
  │  条件: 上传 ≥ 50GB, 分享率 ≥ 1.05, 做种 ≥ 72h, 注册 ≥ 30天, 完成 ≥ 5个种子
  ▼
Lv1 高级用户 (PowerUser)
  │  条件: 上传 ≥ 500GB, 分享率 ≥ 2.0, 做种 ≥ 240h, 注册 ≥ 90天, 发帖 ≥ 10, 完成 ≥ 30
  ▼
Lv2 VIP会员 (VIP)
  │  (仅手动授予)
  ▼
Lv3 版主 (Moderator)
  │  (仅手动授予)
  ▼
Lv4 管理员 (Admin)
```

**升级条件(全部满足才升级)**：最低上传量、最低分享率、最低做种时间、最低注册天数、最低发帖数、最低完成数

**降级条件(任一不满足即降级)**：保持最低分享率低于阈值

**等级特权差异**：
| 特权 | 普通用户 | 高级用户 | VIP | 版主 |
|------|---------|---------|-----|------|
| 下载槽位 | 2 | 3 | 10 | 20 |
| 每月邀请 | 0 | 2 | 5 | 10 |
| 积分倍率 | 1x | 1.5x | 2x | 3x |
| 私信容量 | 100 | 200 | 500 | 1000 |
| 查看Peer | ✗ | ✗ | ✓ | ✓ |
| 免费令牌 | ✗ | ✗ | ✓ | ✓ |
| H&R豁免 | ✗ | ✗ | ✗ | ✓ |
| 下载等待 | 30s | 15s | 0 | 0 |

### 3. H&R (Hit-and-Run) 防逃跑机制

H&R是维护Tracker健康度的重要机制。当用户下载完一个种子后，必须做种达到一定条件，否则记为违规。

```
检测条件（任一满足即通过）：
  ├── 做种时间 ≥ 72小时 (HNR_MIN_SEED_HOURS)
  └── 分享率 ≥ 1.0 (HNR_MIN_RATIO)（在此种子上传/下载比)

豁免期：完成下载后168小时(HNR_GRACE_HOURS)才开始检查
```

**处理流程**：
```
下载完成 → 豁免期(7天) → H&R检查 → 未满足条件 → 创建违规记录
                                              │
                                    用户重新做种到满足条件
                                              │
                                              ▼
                                         自动解决问题
```

### 4. 积分经济系统

```
积分获取：
  做种积分 = Σ(每个做种种子 × 对应积分率)
  
  积分率按种子大小分级：
    • 0-1GB:   0.5 积分/小时
    • 1-10GB:  1.0 积分/小时
    • 10-50GB: 2.0 积分/小时
    • 50GB以上: 3.0 积分/小时

积分消费（商店）：
  • 上传量 +10GB    → 500积分
  • 上传量 +50GB    → 2000积分
  • 邀请码 ×1       → 3000积分
  • VIP 30天        → 10000积分
  (管理员可在后台管理商品)
```

---

## 功能特性

### 用户端功能
- 用户注册(开放/邀请两种模式)
- 种子浏览/搜索/下载
- 种子上传(支持.torrent文件解析)
- 个人主页(统计/最近上传/勋章)
- 书签/感谢系统
- 私信系统
- 积分中心(积分查看/商店/交易记录)
- 邀请系统(生成/管理邀请码)
- 论坛(版块/主题/回复)
- RSS订阅
- 个人设置(主题/通知偏好/签名)
- QBittorrent连接配置

### 管理端功能 (64个管理端点)
- **控制面板**：站点统计概览、最近活动
- **用户管理**：搜索/过滤/编辑/封禁/解封/IP历史/权限配置
- **种子管理**：搜索/编辑/批量设置促销(免费/双倍/半下载/置顶)/禁用/删除
- **等级管理**：UserClass定义(升级/降级条件/特权配置)
- **分类/标签管理**：CRUD操作
- **勋章管理**：CRUD + 手动授予
- **积分商店管理**：商品CRUD + 手动积分调整
- **邀请管理**：生成/撤销邀请码
- **举报处理**：处理流程(确认违规/驳回) + 通知举报人
- **H&R管理**：违规查看/手动处理
- **IP管理**：IP封禁(支持CIDR)/白名单/多账号检测/IP日志
- **论坛管理**：版块CRUD
- **新闻/公告管理**：发布/编辑/删除
- **操作日志**：完整的审计日志(严重程度/旧值/新值)
- **数据统计**：日/周/月流量图表(Chart.js)
- **站点设置**：基础/追踪器/分享率/H&R参数配置
- **QB配置**：全局QB同步设置

---

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **Web框架** | Flask | 3.1 |
| **ORM** | SQLAlchemy + Flask-SQLAlchemy | 2.0 |
| **数据库** | SQLite (WAL模式) | - |
| **认证** | Flask-Login + Werkzeug | 0.6 |
| **表单/CSRF** | Flask-WTF | 1.2 |
| **缓存** | Flask-Caching | 2.3 |
| **迁移** | Flask-Migrate (Alembic) | 4.0 |
| **调度** | APScheduler | 3.10 |
| **Markdown** | mistune | 3.1 |
| **图片** | Pillow | 11.1 |
| **前端UI** | Bootstrap 5.3 + Bootstrap Icons | CDN |
| **图表** | Chart.js | 4.4 CDN |
| **安全** | bcrypt, bleach | 4.2, 6.2 |
| **Tracker** | 自定义Bencode实现 | - |

---

## 快速开始

### 环境要求
- Python 3.10+
- pip

### 安装

```bash
# 1. 克隆项目
cd BT

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用(首次运行自动建表和种子数据)
python run.py

# 4. 访问
# Web界面: http://127.0.0.1:5000
# Tracker: http://127.0.0.1:5000/announce/<passkey>
```

### 默认账号

| 角色 | 用户名 | 密码 | 权限 |
|------|--------|------|------|
| 系统管理员 | admin | admin123 | 全部(18项) |
| 版主 | moderator | mod123 | 审核(7项) |

### 配置

主要配置在 `config.py` 中：

```python
# Tracker
ANNOUNCE_INTERVAL = 1800       # 汇报间隔(秒)
PEER_EXPIRE_SECONDS = 1800     # Peer过期时间
PEER_LIMIT = 50                # 最大返回Peer数

# H&R
HNR_MIN_SEED_HOURS = 72        # 最低做种时间
HNR_MIN_RATIO = 1.0            # 最低分享率
HNR_GRACE_HOURS = 168          # 豁免期(7天)

# 分享率
MIN_RATIO_TO_DOWNLOAD = 0.4    # 下载最低分享率要求

# 积分
DEFAULT_BONUS_PER_HOUR = 1.0   # 基础积分率
```

大部分配置项也可在管理面板 → 站点设置中在线修改。

---

## 项目结构

```
BT/
├── run.py                    # 应用入口
├── config.py                 # 配置类(开发/生产)
├── requirements.txt          # Python依赖
│
├── app/
│   ├── __init__.py           # 工厂函数 + 种子数据
│   ├── extensions.py         # Flask扩展初始化
│   ├── helpers.py            # 辅助函数/过滤器/装饰器
│   │
│   ├── models/               # 数据模型层
│   │   ├── __init__.py       # 模型汇总导出
│   │   ├── user.py           # User, Invite, UserMedal
│   │   ├── torrent.py        # Category, Tag, Torrent, File, Comment, Bookmark, Thank
│   │   ├── tracker.py        # Peer, Snatch, HnrViolation
│   │   ├── bonus.py          # SeedBonusRate, SeedBonusLog, BonusShopItem, BonusPurchase
│   │   ├── system.py         # SiteSetting, News, Report, Log, Medal, Warning, Announcement
│   │   ├── message.py        # PrivateMessage
│   │   ├── forum.py          # Forum, ForumTopic, ForumPost
│   │   ├── admin.py          # BanLog, IpLog, IpBan, IpWhitelist, UserClass, PromotionLog
│   │   └── qbittorrent.py   # QBittorrentConfig, QBittorrentSyncLog
│   │
│   ├── blueprints/           # 路由层(蓝本)
│   │   ├── main/             # 首页/浏览/搜索/规则/FAQ/新闻
│   │   ├── auth/             # 登录/注册/邀请注册
│   │   ├── torrent/          # 种子详情/上传/下载/书签/感谢/评论
│   │   ├── user/             # 个人主页/设置/私信/书签/邀请
│   │   ├── bonus/            # 积分中心/商店/交易记录
│   │   ├── admin/            # 管理后台(15个路由模块, 64个端点)
│   │   ├── api/              # JSON API(搜索/统计/验证)
│   │   ├── rss/              # RSS种子订阅
│   │   ├── forum/            # 论坛(版块/主题/回复)
│   │   └── tracker/          # BitTorrent Tracker (announce/scrape)
│   │
│   ├── services/             # 业务服务层
│   │   ├── tracker_logic.py          # Announce/Scrape核心逻辑
│   │   ├── bencode_service.py        # Bencode编解码
│   │   ├── bonus_calculator.py       # 积分计算
│   │   ├── hnr_checker.py            # H&R检测
│   │   ├── admin_permission_service.py  # 精细权限(18种)
│   │   ├── ip_service.py             # IP管理/多账号检测
│   │   ├── ban_service.py            # 封禁系统(7种类型)
│   │   ├── promotion_service.py      # 自动升降级
│   │   ├── qbittorrent_service.py    # QB集成
│   │   └── stats_service.py          # 流量统计
│   │
│   ├── tasks/                # 后台调度任务
│   │   └── scheduler.py      # APScheduler配置(8个定时任务)
│   │
│   ├── templates/            # Jinja2模板
│   │   ├── base.html         # 基础布局
│   │   ├── macros.html       # 宏(分页/种子卡片)
│   │   ├── admin/            # 管理后台模板(35个)
│   │   │   └── layout.html   # 管理侧边栏布局
│   │   ├── auth/             # 认证模板
│   │   ├── main/             # 首页/浏览/新闻
│   │   ├── torrent/          # 种子详情/上传
│   │   ├── user/             # 用户中心
│   │   ├── bonus/            # 积分中心
│   │   ├── forum/            # 论坛
│   │   ├── errors/           # 错误页面
│   │   └── layout/           # 共享组件(导航栏/页脚/搜索栏)
│   │
│   └── static/               # 静态资源
│       ├── css/style.css
│       └── js/main.js
│
└── storage/                  # 文件存储
    └── torrents/             # .torrent文件存储
```

---

## 数据库模型

### 核心业务表

| 表名 | 模型 | 说明 |
|------|------|------|
| `user` | User | 用户核心表(统计/状态/偏好/权限) |
| `torrent` | Torrent | 种子表(元数据/促销/媒体信息) |
| `peer` | Peer | 活跃连接表(用户-种子-IP-端口) |
| `snatch` | Snatch | 下载完成记录(做种/吸血时间追踪) |
| `category` | Category | 种子分类(树形结构) |
| `tag` | Tag | 种子标签 |
| `file` | File | 种子内文件列表 |
| `comment` | Comment | 种子评论 |
| `bookmark` | Bookmark | 用户收藏 |
| `thank` | Thank | 用户感谢 |

### 积分系统表

| 表名 | 说明 |
|------|------|
| `seed_bonus_rate` | 做种积分率(按大小分级) |
| `seed_bonus_log` | 积分变动日志 |
| `bonus_shop_item` | 商店商品 |
| `bonus_purchase` | 购买记录 |

### 管理系统表

| 表名 | 说明 |
|------|------|
| `site_setting` | 站点配置(键值对) |
| `news` | 新闻文章 |
| `report` | 用户举报 |
| `log` | 管理员操作日志(Audit Trail) |
| `warning` | 用户警告 |
| `announcement` | 系统公告 |
| `medal` | 勋章定义 |
| `user_medal` | 用户勋章关联 |
| `ban_log` | 封禁审计记录 |
| `ip_log` | IP活动日志 |
| `ip_ban` | IP黑名单 |
| `ip_whitelist` | IP白名单 |
| `user_class` | 用户等级定义 |
| `promotion_log` | 升降级审计 |
| `qbittorrent_config` | QB连接配置 |
| `qbittorrent_sync_log` | QB同步日志 |

### 社交表

| 表名 | 说明 |
|------|------|
| `private_message` | 私信 |
| `forum` | 论坛版块 |
| `forum_topic` | 论坛主题 |
| `forum_post` | 论坛回复 |
| `invite` | 邀请码 |
| `hnr_violation` | H&R违规记录 |

---

## 权限体系

### 角色层级

```
Sysop (系统管理员) Lv5 → 隐式拥有所有权限，不可被降级/封禁
  │
Admin (管理员) Lv4 → 通常拥有大部分管理权限
  │
Moderator (版主) Lv3 → 默认7项审核权限
  │
VIP Lv2 → 用户特权，无管理权限
  │
PowerUser (高级用户) Lv1 → 升级用户，无管理权限
  │
User (普通用户) Lv0 → 基础用户
```

### 18项精细管理权限

| 权限键 | 中文说明 | 默认分配 |
|--------|---------|---------|
| `can_manage_users` | 用户管理 | Moderator+ |
| `can_manage_torrents` | 种子管理 | Moderator+ |
| `can_manage_forums` | 论坛管理 | Moderator+ |
| `can_manage_bonus` | 积分管理 | Admin+ |
| `can_view_logs` | 日志查看 | Admin+ |
| `can_manage_settings` | 站点设置 | Admin+ |
| `can_manage_invites` | 邀请管理 | Moderator+ |
| `can_ban_users` | 封禁管理 | Admin+ |
| `can_view_ip` | IP查看 | Moderator+ |
| `can_manage_categories` | 分类管理 | Admin+ |
| `can_manage_medals` | 勋章管理 | Admin+ |
| `can_manage_news` | 公告管理 | Moderator+ |
| `can_resolve_reports` | 举报处理 | Moderator+ |
| `can_manage_hnr` | H&R管理 | Moderator+ |
| `can_batch_operations` | 批量操作 | Admin+ |
| `can_manage_ip_bans` | IP封禁 | Admin+ |
| `can_promote_users` | 升降级 | Admin+ |
| `can_view_stats` | 数据统计 | Admin+ |

### 权限实现原理

```
请求 → @login_required → @permission_required('can_xxx')
                                    │
                          ┌─────────┴──────────┐
                          │  user.role ==      │
                          │  'Sysop'?          │
                          │  → YES: 直接通过    │
                          │  → NO: 检查JSON     │
                          └─────────┬──────────┘
                                    │
                          user.admin_permissions (JSON)
                          {"can_manage_users": true, ...}
                                    │
                          ┌─────────┴──────────┐
                          │  有此权限?          │
                          │  → YES: 通过       │
                          │  → NO: 403 Forbidden│
                          └─────────────────────┘
```

---

## Tracker协议

### Announce端点

```
GET /announce/<passkey>?info_hash=xxx&peer_id=xxx&port=xxx&uploaded=0&downloaded=0&left=xxx&compact=1

参数说明:
  info_hash   - 种子文件中info字典的SHA-1哈希(URL编码, 20字节原始长度)
  peer_id     - 客户端生成的20字节随机ID
  port        - 客户端监听端口
  uploaded    - 本次会话已上传字节数(累计)
  downloaded  - 本次会话已下载字节数(累计)
  left        - 剩余需要下载的字节数(0=做种者)
  event       - 事件类型: started/stopped/completed (可选)
  compact     - 是否使用compact格式返回Peer列表(1=是)
  numwant     - 期望返回的Peer数量(默认50, 上限50)
```

### 响应格式 (Bencode)

```python
# 标准响应
{
    b'interval': 1800,         # 下次汇报间隔(秒)
    b'min interval': 900,      # 最小汇报间隔(秒)
    b'tracker id': b'BT-01',   # Tracker标识
    b'complete': 42,           # 当前做种者数量
    b'incomplete': 13,         # 当前下载者数量
    b'peers': b'\x7f\x00...', # Compact IPv4格式(6字节/peer)
}

# 失败响应
{
    b'failure reason': b'info_hash not found'
}
```

### Scrape端点

```
GET /scrape?info_hash=xxx&info_hash=yyy

响应:
{
    b'files': {
        b'<info_hash_1>': {
            b'complete': 42,     # 做种者数
            b'incomplete': 13,   # 下载者数
            b'downloaded': 100,  # 历史完成次数
        }
    }
}
```

### Peer过期机制

```
时间线:
  t=0     Announce → Peer记录创建/更新
  t=1     ...数据交换...
  t=30min Announce → Peer记录更新
  t=60min 无Announce → Peer被视为过期(PEER_EXPIRE_SECONDS)
  t=70min Peer清理任务执行 → 删除过期Peer → 更新用户/种子计数
```

---

## 分享率与H&R

### 有效统计计算

```python
# process_announce() 中的核心逻辑

effective_up = uploaded_delta     # 本次增量上传
effective_down = downloaded_delta  # 本次增量下载

if torrent.is_freeleech:
    effective_down = 0              # 免费: 下载不计入

if torrent.is_double_upload:
    effective_up *= 2              # 双倍上传

if torrent.is_half_download:
    effective_down //= 2           # 半下载

user.uploaded += effective_up      # 名义上传量
user.downloaded += effective_down  # 名义下载量
user.real_uploaded += uploaded_delta   # 真实上传量
user.real_downloaded += downloaded_delta  # 真实下载量
```

### H&R状态机

```
           下载中
             │
             │ event=completed
             ▼
        ┌─────────┐
        │ 已完成   │ → 豁免期(7天)
        │ Finished │
        └────┬─────┘
             │
    ┌────────┴────────┐
    │                  │
    ▼                  ▼
 ┌──────┐        ┌──────────┐
 │ 通过  │        │  未通过   │
 │ ✅    │        │   ❌      │
 │做种≥72h│       │做种<72h   │
 │或比例≥1│       │且比例<1   │
 └──────┘        └────┬─────┘
                      │
                      ▼
                 ┌──────────┐
                 │ H&R违规  │
                 │ 已记录    │
                 └────┬─────┘
                      │
            用户重新做种至满足条件
                      │
                      ▼
                 ┌──────────┐
                 │ 违规解除  │
                 │ Resolved │
                 └──────────┘
```

---

## 用户等级体系

### 自动升降级流程

```
调度器(每3小时)
  │
  ▼
遍历所有活跃用户
  │
  ├→ check_user_promotion(user)
  │     │
  │     ├→ 计算当前统计: 上传量/分享率/做种时间/注册天数/发帖/完成数
  │     ├→ 找到当前等级以上的UserClass
  │     ├→ 逐一检查是否满足所有升级条件
  │     ├→ 满足 → 升级 + PromotionLog + 发送PM通知
  │     └→ 不满足 → 不变
  │
  └→ check_user_demotion(user)
        │
        ├→ 查找当前等级对应的UserClass
        ├→ 检查降级条件(分享率是否低于keep_min_ratio)
        ├→ 触发降级 → 降级 + demotion_warning_count++ + PM通知
        └→ 未触发 → 不变
```

### 手动升降级
管理员在用户编辑页的"升降级"标签页可以手动调整用户等级，记录操作人和理由到`PromotionLog`。

---

## 积分经济系统

### 积分发放流程

```
调度器(每小时)
  │
  ▼
查询30分钟内活跃的所有做种Peer
  │
  ├→ 对每个Peer:
  │     ├→ 获取种子大小
  │     ├→ 匹配SeedBonusRate等级
  │     ├→ 计算积分 = points_per_hour × multiplier
  │     ├→ user.seed_bonus += points
  │     └→ SeedBonusLog记录
  │
  └→ 提交事务
```

### 商店购买流程

```
用户选择商品 → 检查: 积分够?库存够?角色满足?限购未达?
                           │
                    全部通过 → 扣积分 + 减库存 + 创建购买记录 + 发放效果
                    任一失败 → 返回错误提示
```

---

## 管理后台

### 侧边栏结构

```
管理面板
├── 控制面板 (仪表盘)
├── 用户管理
│   ├── 用户列表 (搜索/过滤/编辑/封禁/批量操作)
│   ├── 邀请管理 (生成/撤销/查看)
│   └── 等级管理 (UserClass定义/CRUD)
├── 种子管理
│   ├── 种子列表 (搜索/批量促销/编辑/禁用/删除)
│   ├── 分类管理 (CRUD)
│   ├── 标签管理 (CRUD)
│   └── 勋章管理 (CRUD/授予)
├── 内容审核
│   ├── 举报处理 (确认违规/驳回/通知举报人)
│   └── H&R违规 (查看/手动处理)
├── 公告与新闻
│   ├── 新闻管理 (发布/编辑/删除)
│   └── 系统公告 (发布/编辑/删除)
├── 论坛管理 (版块CRUD)
├── 积分与商店
│   ├── 商店管理 (商品CRUD)
│   └── 积分调整 (手动调整用户积分)
├── 安全管理
│   ├── IP封禁 (添加/删除/支持CIDR)
│   ├── IP白名单 (用户IP豁免)
│   └── 多账号检测 (同IP多用户)
├── 日志与统计
│   ├── 操作日志 (筛选/查看管理员操作)
│   ├── IP日志 (查看IP活动记录)
│   └── 数据统计 (日/周/月流量图表)
└── 系统设置
    ├── 站点设置 (基础/Tracker/分享率/H&R/积分)
    └── QB配置 (全局QB同步)
```

### 操作日志审计

每次管理操作都自动记录：
- **操作人**：哪个管理员执行的
- **操作类型**：具体动作(ban_user/edit_torrent/grant_medal等)
- **操作目标**：用户/种子/论坛等
- **详情**：操作描述
- **旧值/新值**：用于数据变更审计
- **严重程度**：info/warning/danger/success
- **IP地址**：操作来源
- **时间戳**：操作时间

---

## QBittorrent集成

### 工作原理

```
用户QB实例                        本站服务器
     │                                │
     ├─ 用户在设置页配置QB连接        │
     │  (host, port, username,        │
     │   password, use_ssl)           │
     │                                │
     ├─ 调度器每30分钟发起同步 ──────→│
     │                                │
     │  ←── QB API v2 请求 ──────────┤
     │  GET /api/v2/torrents/info     │
     │  GET /api/v2/transfer/info     │
     │                                │
     │  ─── 返回种子列表+统计 ──────→ │
     │                                │
     │                  系统计算增量   │
     │                  user.uploaded += delta_up
     │                  user.downloaded += delta_down
     │                  创建 QBittorrentSyncLog
```

### QB API端点

- `POST /api/v2/auth/login` — 登录获取SID
- `GET /api/v2/torrents/info` — 获取所有种子信息(哈希/名称/状态/上传量/下载量)
- `GET /api/v2/transfer/info` — 获取全局传输统计
- `POST /api/v2/auth/logout` — 登出

---

## IP管理与安全

### IP事件追踪

系统在以下时机记录IP：

| 事件 | 触发点 | 记录内容 |
|------|--------|---------|
| 登录 | `auth/routes.py` | IP + User-Agent |
| Tracker Announce | `tracker/routes.py` | IP + User-Agent + Port |
| 注册 | `auth/routes.py` | IP + User-Agent |
| API调用 | `api/routes.py` | IP |

### 多账号检测

```sql
SELECT ip, COUNT(DISTINCT user_id) as user_count
FROM ip_log
WHERE event_type = 'login'
GROUP BY ip
HAVING user_count > 1
ORDER BY user_count DESC
```

检测结果在管理面板 → 安全管理 → 多账号检测中展示。

### IP封禁

- 支持单个IP：`192.168.1.100`
- 支持CIDR网段：`192.168.1.0/24`
- 支持过期时间：临时封禁(按天)或永久封禁
- 封禁检查在登录和Tracker Announce时进行

### CIDR匹配原理

```python
import ipaddress

def is_ip_banned(ip):
    for ban in active_bans:
        if '/' in ban.ip_address:
            network = ipaddress.ip_network(ban.ip_address, strict=False)
            if ipaddress.ip_address(ip) in network:
                return True
        elif ban.ip_address == ip:
            return True
    return False
```

---

## 配置说明

### config.py 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `SECRET_KEY` | 环境变量或默认 | Flask密钥 |
| `SQLALCHEMY_DATABASE_URI` | sqlite:///app.db | 数据库连接 |
| `ANNOUNCE_INTERVAL` | 1800 | Tracker汇报间隔(秒) |
| `ANNOUNCE_MIN_INTERVAL` | 900 | 最小汇报间隔(秒) |
| `PEER_EXPIRE_SECONDS` | 1800 | Peer过期时间(秒) |
| `PEER_LIMIT` | 50 | 单次最大返回Peer数 |
| `HNR_MIN_SEED_HOURS` | 72 | H&R最低做种时间(小时) |
| `HNR_MIN_RATIO` | 1.0 | H&R最低分享率 |
| `HNR_GRACE_HOURS` | 168 | H&R豁免期(小时) |
| `MIN_RATIO_TO_DOWNLOAD` | 0.4 | 下载最低分享率要求 |
| `DEFAULT_BONUS_PER_HOUR` | 1.0 | 基础做种积分率 |
| `PERMANENT_SESSION_LIFETIME` | 30天 | 登录会话时长 |
| `MAX_CONTENT_LENGTH` | 16MB | 最大上传文件大小 |

### 动态配置 (SiteSetting表)

以下配置可在管理面板中在线修改：
- 站点名称/描述
- 邀请注册开关
- 开放注册开关
- 维护模式
- Tracker参数
- 分享率与H&R参数

### 环境变量 (.env)

```
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
DATABASE_URL=sqlite:///app.db
```

---

## 许可证

本项目仅供学习和技术研究使用。


**再次提醒：请遵守您所在地区的法律法规，不要使用本系统进行任何违法活动。**

---

## 效果展示    
<img width="1269" height="673" alt="屏幕截图 2026-06-27 093320" src="https://github.com/user-attachments/assets/ca891370-42d5-4425-9d69-f69e13326d24" />    
<img width="1277" height="672" alt="屏幕截图 2026-06-27 093248" src="https://github.com/user-attachments/assets/f95476b5-62dd-40d1-9229-2cb605db4877" />

