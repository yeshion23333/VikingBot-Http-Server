#!/bin/bash

# Vikingbot API 启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 配置
APP_MODULE="vikingbot_api.main:app"
HOST="0.0.0.0"
PORT="8000"
LOG_FILE="server.log"
PID_FILE="server.pid"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color




# 检查服务是否正在运行
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# 启动服务（前台模式）
start_foreground() {
    echo -e "${GREEN}启动 Vikingbot API 服务（前台模式）...${NC}"
    echo "访问地址: http://$HOST:$PORT"
    echo "健康检查: http://$HOST:$PORT/health"
    echo "按 Ctrl+C 停止服务"
    echo ""

    uvicorn "$APP_MODULE" \
        --host "$HOST" \
        --port "$PORT" \
        --reload
}

# 启动服务（后台模式）
start_background() {
    if is_running; then
        echo -e "${YELLOW}警告: 服务已在运行 (PID: $(cat $PID_FILE))${NC}"
        return 1
    fi

    echo -e "${GREEN}启动 Vikingbot API 服务（后台模式）...${NC}"

    nohup uvicorn "$APP_MODULE" \
        --host "$HOST" \
        --port "$PORT" \
        --reload \
        > "$LOG_FILE" 2>&1 &

    local pid=$!
    echo $pid > "$PID_FILE"

    sleep 2

    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${GREEN}服务启动成功!${NC}"
        echo "PID: $pid"
        echo "日志文件: $LOG_FILE"
        echo "访问地址: http://$HOST:$PORT"
        echo "健康检查: http://$HOST:$PORT/health"
        echo ""
        echo "查看日志: tail -f $LOG_FILE"
        echo "停止服务: $0 stop"
    else
        echo -e "${RED}服务启动失败，请查看日志: $LOG_FILE${NC}"
        rm -f "$PID_FILE"
        return 1
    fi
}

# 停止服务
stop_service() {
    if ! is_running; then
        echo -e "${YELLOW}服务未运行${NC}"
        return 0
    fi

    local pid=$(cat "$PID_FILE")
    echo -e "${GREEN}停止服务 (PID: $pid)...${NC}"

    kill "$pid" 2>/dev/null

    # 等待进程停止
    for i in {1..10}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo -e "${GREEN}服务已停止${NC}"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done

    # 强制停止
    echo -e "${YELLOW}强制停止服务...${NC}"
    kill -9 "$pid" 2>/dev/null
    rm -f "$PID_FILE"
    echo -e "${GREEN}服务已停止${NC}"
}

# 查看服务状态
status_service() {
    if is_running; then
        echo -e "${GREEN}服务正在运行 (PID: $(cat $PID_FILE))${NC}"
        echo "访问地址: http://$HOST:$PORT"
        echo "日志文件: $LOG_FILE"
    else
        echo -e "${RED}服务未运行${NC}"
    fi
}

# 查看日志
view_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo -e "${YELLOW}日志文件不存在: $LOG_FILE${NC}"
    fi
}

# 显示帮助
show_help() {
    echo "Vikingbot API 启动脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start        前台启动服务（默认）"
    echo "  start -d     后台启动服务"
    echo "  stop         停止服务"
    echo "  restart      重启服务"
    echo "  status       查看服务状态"
    echo "  logs         查看日志"
    echo "  help         显示帮助"
    echo ""
    echo "示例:"
    echo "  $0              # 前台启动"
    echo "  $0 start -d     # 后台启动"
    echo "  $0 stop         # 停止服务"
}

# 主逻辑
case "${1:-start}" in
    start)
        if [ "$2" = "-d" ] || [ "$2" = "--daemon" ]; then
            start_background
        else
            start_foreground
        fi
        ;;
    stop)
        stop_service
        ;;
    restart)
        stop_service
        sleep 1
        start_background
        ;;
    status)
        status_service
        ;;
    logs)
        view_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
