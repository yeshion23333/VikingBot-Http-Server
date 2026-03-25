# Vikingbot HTTP API Server

## 项目介绍
Vikingbot HTTP API 服务，提供对话接口和 OpenViking 内存管理接口，支持鉴权、限流和安全防护。

## 快速开始

### 1. 安装依赖
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 启动服务
```bash
python -m vikingbot_api.main
# 或者
uvicorn vikingbot_api.main:app --host 0.0.0.0 --port 1933
```

服务将在 http://localhost:1933 启动

### 3. 测试接口
```bash
# 生成认证密钥
python generate_key.py

# 运行测试脚本
pip install requests
python test_api.py
```

## API 接口

### 认证
所有接口都需要在请求头中携带 `X-OpenViking-Bot-Key`，加密方式：
```javascript
const ENCRYPT_KEY = 'askecho-experience-ai9176#!';
const encrypt_key = aes.encrypt("ov-chat", ENCRYPT_KEY).toString();
```

### 1. 聊天接口
**POST /api/v1/bot/chat**
```bash
curl -X POST http://localhost:1933/api/v1/bot/chat \
  -H "Content-Type: application/json" \
  -H "X-OpenViking-Bot-Key: /0gSFvA==" \
  -d '{
    "user_id": "test123",
    "query": "Openviking怎么使用"
  }'
```

### 2. 获取内存列表
**POST /api/v1/ov/list/memory**
```bash
curl -X POST http://localhost:1933/api/v1/ov/list/memory \
  -H "Content-Type: application/json" \
  -H "X-OpenViking-Bot-Key: /0gSFvA==" \
  -d '{"user_id": "test123"}'
```

### 3. 获取内存详情
**POST /api/v1/ov/info/memory**
```bash
curl -X POST http://localhost:1933/api/v1/ov/info/memory \
  -H "Content-Type: application/json" \
  -H "X-OpenViking-Bot-Key: /0gSFvA==" \
  -d '{
    "user_id": "test123",
    "uri": "/entities/mem_00ee38e0-6393-4293-9fc9-e6dfd8e282c1.md",
    "level": "read"
  }'
```

### 4. 删除用户
**POST /api/v1/ov/delete/user**
```bash
curl -X POST http://localhost:1933/api/v1/ov/delete/user \
  -H "Content-Type: application/json" \
  -H "X-OpenViking-Bot-Key: /0gSFvA==" \
  -d '{"user_id": "test123"}'
```

## 限流规则
- 聊天接口：最多5个并发请求
- 其他接口：最多10个并发请求
- 同一IP：每分钟最多60次请求
- 同一用户：每分钟最多30次请求

## 项目结构
```
ov-bot-server/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 主入口
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── bot.py       # Bot 相关接口
│   │       └── ov.py        # OpenViking 相关接口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── auth.py          # 鉴权逻辑
│   │   └── limiter.py       # 限流逻辑
│   └── utils/
│       ├── __init__.py
│       └── response.py      # 统一返回格式
├── requirements.txt         # 依赖包
├── generate_key.py          # 生成测试密钥
├── test_api.py              # 接口测试脚本
└── README.md
```

## 后续开发
当前版本返回的是模拟数据，需要接入实际的 Vikingbot 和 OpenViking 实现：
1. 在 `app/api/v1/bot.py` 中实现真实的聊天逻辑
2. 在 `app/api/v1/ov.py` 中实现真实的内存管理逻辑
