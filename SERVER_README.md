# MediaCrawler API Server

基于 MediaCrawler 项目的通用 API 服务，支持多平台、多轮次的关键词爬取，并将结果存储到 MongoDB。

## 功能特性

- ✅ **多平台支持**：小红书、抖音、快手、B站、微博、贴吧、知乎
- ✅ **多轮次调度**：支持多组关键词按轮次执行
- ✅ **动态配置注入**：运行时动态修改爬虫配置
- ✅ **MongoDB 分表存储**：按平台分表存储（`{platform}_media_crawler`）
- ✅ **全局任务锁**：防止任务冲突
- ✅ **后台任务执行**：异步执行，不阻塞 API 响应
- ✅ **任务状态查询**：实时查询任务执行状态

## 项目结构

```
MediaCrawler/
├── server/                     # API 服务模块
│   ├── __init__.py
│   ├── models.py              # Pydantic 数据模型
│   ├── db_handler.py          # MongoDB 异步处理器
│   └── task_runner.py         # 动态配置与调度器
├── server_main.py             # FastAPI 服务入口
└── SERVER_README.md           # 本文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install fastapi uvicorn motor
```

### 2. 配置 MongoDB

编辑 `config/db_config.py`，确保 MongoDB 配置正确：

```python
mongodb_config = {
    "host": "localhost",
    "port": 27017,
    "user": "",
    "password": "",
    "db_name": "media_crawler"
}
```

### 3. 启动 API 服务

```bash
python server_main.py
```

或使用 uvicorn：

```bash
uvicorn server_main:app --host 0.0.0.0 --port 8000 --reload
```

服务将在 `http://localhost:8000` 启动。

### 4. 访问 API 文档

浏览器打开：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API 端点

### POST /start_crawl - 启动爬虫任务

**请求体：**

```json
{
  "platforms": ["xhs", "dy"],
  "keyword_groups": [
    ["编程副业", "编程兼职"],
    ["Python教程", "Java学习"]
  ],
  "config": {
    "login_type": "qrcode",
    "crawler_type": "search",
    "sort_type": "general",
    "headless": false,
    "enable_cdp_mode": true,
    "enable_proxy": false,
    "max_notes_count": 20,
    "max_comments_per_note": 20,
    "enable_get_comments": true,
    "enable_get_sub_comments": false,
    "max_sleep_sec": 5
  }
}
```

**字段说明：**

- `platforms`: 目标平台列表，支持：`xhs`, `dy`, `ks`, `bili`, `wb`, `tieba`, `zhihu`
- `keyword_groups`: 多组关键词，每组关键词作为一个轮次
- `config`: 爬虫配置
  - `login_type`: 登录方式（`qrcode`/`phone`/`cookie`）
  - `crawler_type`: 爬取类型（`search`/`detail`/`creator`）
  - `sort_type`: 排序方式（不同平台支持不同值）
  - `headless`: 是否无头浏览器
  - `enable_cdp_mode`: 是否启用 CDP 模式（推荐）
  - `enable_proxy`: 是否启用代理
  - `max_notes_count`: 最大爬取帖子数
  - `max_comments_per_note`: 单个帖子最大评论数
  - `enable_get_comments`: 是否爬取评论
  - `enable_get_sub_comments`: 是否爬取二级评论
  - `max_sleep_sec`: 请求间隔（秒）

**响应：**

```json
{
  "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "started",
  "message": "Crawl task started successfully",
  "platforms": ["xhs", "dy"],
  "total_rounds": 2
}
```

### GET /task_status/{task_id} - 查询任务状态

**响应：**

```json
{
  "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "running",
  "current_round": 1,
  "current_platform": "xhs",
  "total_rounds": 2,
  "progress": 25.0,
  "error_message": null
}
```

**状态值：**
- `pending`: 等待中
- `running`: 运行中
- `completed`: 已完成
- `failed`: 失败

### GET /is_running - 检查是否有任务运行中

**响应：**

```json
{
  "is_running": true,
  "current_task": {
    "task_id": "...",
    "status": "running",
    "current_round": 1,
    "current_platform": "xhs",
    "total_rounds": 2,
    "progress": 25.0
  }
}
```

### GET /platforms - 获取支持的平台列表

**响应：**

```json
{
  "platforms": [
    {"code": "xhs", "name": "小红书 (Xiaohongshu)"},
    {"code": "dy", "name": "抖音 (Douyin)"},
    {"code": "ks", "name": "快手 (Kuaishou)"},
    {"code": "bili", "name": "哔哩哔哩 (Bilibili)"},
    {"code": "wb", "name": "微博 (Weibo)"},
    {"code": "tieba", "name": "百度贴吧 (Tieba)"},
    {"code": "zhihu", "name": "知乎 (Zhihu)"}
  ]
}
```

### GET /data/{platform} - 获取平台数据

**参数：**
- `platform`: 平台代码（`xhs`, `dy` 等）
- `limit`: 返回数量（默认 100）
- `skip`: 跳过数量（默认 0）

**响应：**

```json
{
  "platform": "xhs",
  "count": 50,
  "data": [
    {
      "post_id": "64b95d01000000000c034587",
      "post_detail": {...},
      "comments": [...],
      "comment_count": 10,
      "crawl_metadata": {
        "task_id": "...",
        "round": 1,
        "keywords": ["编程副业"],
        "crawl_time": "2025-01-15T10:30:00"
      },
      "updated_at": "2025-01-15T10:30:00"
    }
  ]
}
```

### GET /stats/{platform} - 获取平台统计

**响应：**

```json
{
  "platform": "xhs",
  "total_posts": 150,
  "total_comments": 1500
}
```

## 执行逻辑

### 多轮次调度

```
Round 1
├── Platform 1 (xhs)
│   ├── Inject config
│   ├── Start crawler
│   ├── Collect data
│   ├── Save to MongoDB (xhs_media_crawler)
│   └── Sleep 60-120s
├── Platform 2 (dy)
│   └── ...
└── Sleep 300-600s

Round 2
├── Platform 1 (xhs)
│   └── ...
└── ...
```

### 平台间休眠：60-120 秒
### 轮次间休眠：300-600 秒

## MongoDB 数据结构

每个平台的数据存储在独立的集合中：

```
{platform}_media_crawler
├── post_id (唯一索引)
├── post_detail (帖子详细数据)
├── comments (评论列表)
├── comment_count (评论数量)
├── crawl_metadata (爬取元数据)
│   ├── task_id
│   ├── round
│   ├── keywords
│   └── crawl_time
└── updated_at (更新时间)
```

## 使用示例

### Python 示例

```python
import requests

# API 基础 URL
BASE_URL = "http://localhost:8000"

# 启动爬虫任务
response = requests.post(f"{BASE_URL}/start_crawl", json={
    "platforms": ["xhs", "dy"],
    "keyword_groups": [
        ["编程副业", "编程兼职"],
        ["Python教程", "Java学习"]
    ],
    "config": {
        "login_type": "cookie",
        "crawler_type": "search",
        "headless": False,
        "enable_cdp_mode": True,
        "max_notes_count": 20
    }
})

result = response.json()
task_id = result["task_id"]
print(f"Task started: {task_id}")

# 查询任务状态
status_response = requests.get(f"{BASE_URL}/task_status/{task_id}")
print(status_response.json())
```

### cURL 示例

```bash
# 启动爬虫任务
curl -X POST "http://localhost:8000/start_crawl" \
  -H "Content-Type: application/json" \
  -d '{
    "platforms": ["xhs"],
    "keyword_groups": [["编程副业"]],
    "config": {
      "login_type": "cookie",
      "crawler_type": "search"
    }
  }'

# 查询任务状态
curl "http://localhost:8000/task_status/{task_id}"

# 获取平台数据
curl "http://localhost:8000/data/xhs?limit=10"

# 获取平台统计
curl "http://localhost:8000/stats/xhs"
```

## 注意事项

1. **全局任务锁**：同一时间只能运行一个任务，新任务会返回 423 错误
2. **Cookie 登录**：推荐使用 `cookie` 登录方式，需要提前配置 cookies
3. **CDP 模式**：推荐启用 CDP 模式，反检测能力更强
4. **爬取频率**：默认配置了合理的休眠时间，避免被平台检测
5. **数据去重**：MongoDB 使用 `post_id` 作为唯一索引，自动去重

## 故障排查

### 任务启动失败

- 检查是否有其他任务正在运行：`GET /is_running`
- 检查平台代码是否正确
- 检查关键词列表是否为空

### 数据未保存

- 检查 MongoDB 连接配置
- 检查 MongoDB 是否正在运行
- 查看日志中的错误信息

### 浏览器启动失败

- 检查 Playwright 是否正确安装：`playwright install`
- 检查是否安装了浏览器驱动
- 如果使用 CDP 模式，检查 Chrome/Edge 是否正在运行

## 扩展开发

### 添加新平台

1. 在 `main.py` 的 `CrawlerFactory.CRAWLERS` 中添加新平台
2. 实现对应平台的爬虫类（继承 `AbstractCrawler`）
3. 在 API 请求中使用新平台代码

### 自定义配置

在 `server/models.py` 的 `CrawlerConfig` 中添加新字段：

```python
class CrawlerConfig(BaseModel):
    # 现有字段...
    custom_field: str = Field(default="value", description="Description")
```

## 许可证

本项目继承 MediaCrawler 的 NON-COMMERCIAL LEARNING LICENSE 1.1 许可证。
