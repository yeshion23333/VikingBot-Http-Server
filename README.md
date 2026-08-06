# Vikingbot HTTP API Server

## 项目介绍
Vikingbot HTTP API 服务，提供对话接口和 OpenViking 内存管理接口，支持鉴权、限流和安全防护。

## 快速开始

### 1. 安装依赖
```bash
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
# 编辑 config.json，填写本地 OpenViking 和鉴权配置
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

### 4. 监控指标

服务通过无需鉴权的 `/metrics` 暴露 Prometheus 指标：

```bash
curl http://localhost:1933/metrics/
```

主要指标：

- `vikingbot_http_requests_total`：按请求方法、路由、HTTP 状态码、业务结果、`error_type` 和 `upstream_status_code` 统计请求量
- `vikingbot_http_request_duration_seconds`：请求耗时直方图
- `vikingbot_http_requests_in_progress`：当前正在处理的请求数

业务异常目前保持兼容，仍可能返回 HTTP 200，但会记录为
`outcome="business_error"`，可用于计算真实业务错误率。`error_type`
使用固定枚举（例如 `upstream_read_timeout`、`upstream_http_5xx`）展示可聚合的具体错误类别；完整错误正文不会写入 Prometheus，而是通过响应中的
`request_id` 到函数日志中查询。

## API 接口

### 认证
除 `/health` 和 `/metrics` 外，业务接口都需要在请求头中携带
`X-OpenViking-Bot-Key`。鉴权主密钥必须通过环境变量
`VIKINGBOT_ENCRYPT_KEY` 或本地 `config.json` 中的
`server.auth.encrypt_key` 配置，不要提交到 Git：

```bash
# 生成一个 32 字节的随机主密钥
export VIKINGBOT_ENCRYPT_KEY="$(python -c 'import secrets; print(secrets.token_hex(16))')"

# 使用同一个主密钥生成请求 Token
export VIKINGBOT_AUTH_TOKEN="$(python generate_token.py | cut -d ' ' -f 2-)"
```

### 1. 聊天接口
**POST /api/v1/bot/chat**

OpenViking Chat 的响应读取超时由
`openviking.chat_timeout_seconds` 配置，默认 600 秒。API Gateway、veFaaS
函数和调用方的超时时间也需要大于该值，否则外层会先取消请求。

每次 Chat 响应都会在响应体的 `request_id` 字段和 `X-Request-ID`
响应头中返回请求 ID。发生错误时，日志会记录同一个 request ID、异常类型、
OpenViking 状态码和最多 2048 个字符的响应正文；响应体的 `error_type`
可直接用于区分上游读取超时、连接失败、4xx、5xx 和非法响应。

```bash
curl -X POST http://localhost:1933/api/v1/bot/chat \
  -H "Content-Type: application/json" \
  -H "X-OpenViking-Bot-Key: ${VIKINGBOT_AUTH_TOKEN}" \
  -d '{
    "user_id": "test123",
    "query": "Openviking怎么使用"
  }'
```

### 2. 获取 Peer 内存列表
**POST /api/v1/ov/list/memory**
```bash
curl -X POST http://localhost:1933/api/v1/ov/list/memory \
  -H "Content-Type: application/json" \
  -H "X-OpenViking-Bot-Key: ${VIKINGBOT_AUTH_TOKEN}" \
  -d '{"user_id": "test123"}'
```

### 3. 获取内存详情
**POST /api/v1/ov/info/memory**
```bash
curl -X POST http://localhost:1933/api/v1/ov/info/memory \
  -H "Content-Type: application/json" \
  -H "X-OpenViking-Bot-Key: ${VIKINGBOT_AUTH_TOKEN}" \
  -d '{
    "user_id": "test123",
    "uri": "/entities/mem_00ee38e0-6393-4293-9fc9-e6dfd8e282c1.md",
    "level": "read"
  }'
```

### 4. 删除 Peer 内存
**POST /api/v1/ov/delete/user**
```bash
curl -X POST http://localhost:1933/api/v1/ov/delete/user \
  -H "Content-Type: application/json" \
  -H "X-OpenViking-Bot-Key: ${VIKINGBOT_AUTH_TOKEN}" \
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
1. `user_id` 会作为 OpenViking peer id 使用，不再注册或校验 OpenViking user。
2. 内存路径使用 `viking://user/peers/{user_id}/memories/`，并向 OpenViking 转发 `X-OpenViking-Actor-Peer: {user_id}`。
3. `/api/v1/ov/delete/user` 为兼容旧调用保留名称，实际删除的是该 peer 的 memory 目录。
