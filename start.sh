#!/usr/bin/env bash
# Local development launcher for the Fund Investment Platform.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
BOLD="\033[1m"
RESET="\033[0m"

START_BACKEND=true
START_FRONTEND=true
START_WORKER=false
PYTHON_LOCALE="${FIP_PYTHON_LOCALE:-${LANG:-zh_CN.UTF-8}}"
if [[ "$PYTHON_LOCALE" == "C" || "$PYTHON_LOCALE" == "POSIX" || "$PYTHON_LOCALE" == *ASCII* ]]; then
  PYTHON_LOCALE="zh_CN.UTF-8"
fi

usage() {
  cat <<'EOF'
用法: ./start.sh [选项]

选项:
  (无参数)         启动后端 API 和前端 Vite
  --with-worker    同时启动 PostgreSQL 作业 Worker（需先应用数据库迁移）
  --api-only       仅启动后端 API 服务
  --backend-only   --api-only 的别名
  --frontend-only  仅启动前端 Web 界面
  --help, -h       查看帮助说明

默认不会启动 Worker。基金数据抓取、优化和回测任务需要 PostgreSQL、最新迁移及运行中的 Worker。
脚本不会自动执行数据库迁移，也不会终止已占用目标端口的进程。
EOF
}

for arg in "$@"; do
  case "$arg" in
    --backend-only|--api-only)
      START_FRONTEND=false
      ;;
    --frontend-only)
      START_BACKEND=false
      ;;
    --with-worker)
      START_WORKER=true
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf '%b未知参数: %s%b\n\n' "$RED" "$arg" "$RESET" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$START_BACKEND" == false && "$START_FRONTEND" == false ]]; then
  printf '%b错误: 至少选择一个服务启动。%b\n' "$RED" "$RESET" >&2
  exit 2
fi
if [[ "$START_WORKER" == true && "$START_BACKEND" == false ]]; then
  printf '%b错误: --with-worker 需要同时启动 API；不能与 --frontend-only 一起使用。%b\n' "$RED" "$RESET" >&2
  exit 2
fi

printf '%b%b\n' "$CYAN" "$BOLD"
printf '%s\n' '=================================================================='
printf '%s\n' '    🚀 Fund Investment Platform (基金投资平台) 本地启动程序'
printf '%s\n' '=================================================================='
printf '%b\n' "$RESET"
printf '%b🔍 正在检查运行环境依赖...%b\n' "$YELLOW" "$RESET"

if [[ "$START_BACKEND" == true ]]; then
  if [[ ! -x ".venv/bin/python" ]]; then
    printf '%b错误: 未检测到 Python 虚拟环境 (.venv/bin/python)。%b\n' "$RED" "$RESET" >&2
    printf '%s\n' '请先运行:' '  python3 -m venv .venv' '  .venv/bin/pip install -r requirements.lock' >&2
    exit 1
  fi
  if ! LC_ALL="$PYTHON_LOCALE" .venv/bin/python -c 'import uvicorn' >/dev/null 2>&1; then
    printf '%b错误: 当前 .venv 未安装 uvicorn，请按项目锁定依赖重新安装。%b\n' "$RED" "$RESET" >&2
    exit 1
  fi
  printf '%b  ✓ Python 环境正常 (.venv)%b\n' "$GREEN" "$RESET"
fi

if [[ "$START_FRONTEND" == true ]]; then
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    printf '%b错误: 启动前端需要 Node.js 和 npm。%b\n' "$RED" "$RESET" >&2
    exit 1
  fi
  if [[ ! -f frontend/package-lock.json ]]; then
    printf '%b错误: 缺少 frontend/package-lock.json，无法按锁文件安装依赖。%b\n' "$RED" "$RESET" >&2
    exit 1
  fi
  printf '%b  ✓ Node.js %s / npm %s%b\n' "$GREEN" "$(node -v)" "$(npm -v)" "$RESET"

  if [[ ! -x frontend/node_modules/.bin/vite ]]; then
    printf '%b  ⚡ 正在按 package-lock.json 安装前端依赖 (npm ci)...%b\n' "$YELLOW" "$RESET"
    (cd frontend && npm ci)
  fi
fi

check_port() {
  local port="$1"
  local service="$2"
  local listener=""

  if command -v lsof >/dev/null 2>&1; then
    listener="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$listener" ]]; then
      printf '%b错误: 端口 %s (%s) 已被监听，PID: %s。为避免连接到其他项目，请先确认并手动处理该进程。%b\n' \
        "$RED" "$port" "$service" "${listener//$'\n'/, }" "$RESET" >&2
      return 1
    fi
  fi
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") >/dev/null 2>&1; then
    printf '%b错误: 端口 %s (%s) 已有服务响应；请确认服务身份后再启动。%b\n' \
      "$RED" "$port" "$service" "$RESET" >&2
    return 1
  fi
}

if [[ "$START_BACKEND" == true ]]; then
  check_port 8000 "后端 API"
fi
if [[ "$START_FRONTEND" == true ]]; then
  check_port 5173 "前端 Vite"
fi

BACKEND_PID=""
FRONTEND_PID=""
WORKER_PID=""

stop_process() {
  local pid="$1"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill -TERM "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  fi
}

cleanup() {
  local exit_status=$?
  trap - EXIT INT TERM
  printf '\n%b🛑 正在停止本脚本启动的服务...%b\n' "$YELLOW" "$RESET"
  stop_process "$WORKER_PID"
  stop_process "$FRONTEND_PID"
  stop_process "$BACKEND_PID"
  if [[ "$exit_status" -eq 0 ]]; then
    printf '%b✅ 服务已停止。%b\n' "$GREEN" "$RESET"
  else
    printf '%b服务以状态码 %s 退出。%b\n' "$YELLOW" "$exit_status" "$RESET"
  fi
  exit "$exit_status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

wait_for_http() {
  local url="$1"
  local expected="$2"
  local description="$3"
  local pid="$4"

  printf '  等待%s' "$description"
  for _ in {1..40}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      printf '\n%b错误: %s 进程已退出，请检查上方日志。%b\n' "$RED" "$description" "$RESET" >&2
      return 1
    fi
    if curl --fail --silent --max-time 1 "$url" 2>/dev/null | grep -q "$expected"; then
      printf ' %b✓ 就绪%b\n' "$GREEN" "$RESET"
      return 0
    fi
    printf '.'
    sleep 0.5
  done
  printf '\n%b错误: %s 等待超时。%b\n' "$RED" "$description" "$RESET" >&2
  return 1
}

if [[ "$START_BACKEND" == true ]]; then
  printf '\n%b▶ 正在启动后端 API (http://127.0.0.1:8000)...%b\n' "$CYAN" "$RESET"
  LC_ALL="$PYTHON_LOCALE" PYTHONPATH=src FIP_ENABLE_M2_REBALANCE="${FIP_ENABLE_M2_REBALANCE:-true}" \
    .venv/bin/python -m uvicorn fip.api.app:app \
    --host 127.0.0.1 --port 8000 --reload &
  BACKEND_PID=$!
  wait_for_http \
    "http://127.0.0.1:8000/health/live" \
    '"status":"ok"' \
    '后端 API' "$BACKEND_PID"
fi

if [[ "$START_WORKER" == true ]]; then
  printf '\n%b▶ 检查数据库与迁移状态...%b\n' "$CYAN" "$RESET"
  if ! curl --fail --silent --max-time 3 http://127.0.0.1:8000/health/ready >/dev/null; then
    printf '%b错误: 数据库未就绪或迁移未应用。请先启动 PostgreSQL 并运行 make migrate；本脚本不会自动迁移。%b\n' "$RED" "$RESET" >&2
    exit 1
  fi
  printf '%b▶ 正在启动后台作业 Worker...%b\n' "$CYAN" "$RESET"
  LC_ALL="$PYTHON_LOCALE" PYTHONPATH=src .venv/bin/python -m fip.platform.jobs.worker &
  WORKER_PID=$!
  sleep 1
  if ! kill -0 "$WORKER_PID" 2>/dev/null; then
    printf '%b错误: Worker 未能保持运行，请检查数据库连接及上方日志。%b\n' "$RED" "$RESET" >&2
    exit 1
  fi
  printf '%b  ✓ Worker 已启动 (PID: %s)%b\n' "$GREEN" "$WORKER_PID" "$RESET"
fi

if [[ "$START_FRONTEND" == true ]]; then
  printf '\n%b▶ 正在启动前端 Vite (http://127.0.0.1:5173)...%b\n' "$CYAN" "$RESET"
  frontend/node_modules/.bin/vite --host 127.0.0.1 --port 5173 &
  FRONTEND_PID=$!
  wait_for_http \
    "http://127.0.0.1:5173/funds" \
    '<div id="root">' \
    '前端 Vite' "$FRONTEND_PID"
fi

printf '\n%b%b==================================================================%b\n' "$GREEN" "$BOLD" "$RESET"
printf '%b%b🎉 已启动所选服务%b\n' "$GREEN" "$BOLD" "$RESET"
printf '%b%b==================================================================%b\n' "$GREEN" "$BOLD" "$RESET"
if [[ "$START_FRONTEND" == true ]]; then
  printf '  前端界面:   %bhttp://127.0.0.1:5173/funds%b\n' "$CYAN" "$RESET"
fi
if [[ "$START_BACKEND" == true ]]; then
  printf '  后端 API:   %bhttp://127.0.0.1:8000%b\n' "$CYAN" "$RESET"
  printf '  API 文档:   %bhttp://127.0.0.1:8000/docs%b\n' "$CYAN" "$RESET"
  printf '  健康检查:   %bhttp://127.0.0.1:8000/health/live%b\n' "$CYAN" "$RESET"
fi
if [[ "$START_WORKER" == true ]]; then
  printf '  后台 Worker: %b运行中%b\n' "$CYAN" "$RESET"
else
  printf '  后台 Worker: 未启动（抓取/优化/回测任务需要 ./start.sh --with-worker）\n'
fi
printf '\n%b按 Ctrl+C 停止本脚本启动的服务。%b\n' "$YELLOW" "$RESET"

monitor_process() {
  local pid="$1"
  local service="$2"
  local status=0
  if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
    if wait "$pid"; then
      status=1
    else
      status=$?
    fi
    printf '%b错误: %s 进程已退出 (状态码 %s)。%b\n' "$RED" "$service" "$status" "$RESET" >&2
    exit "$status"
  fi
}

while true; do
  monitor_process "$BACKEND_PID" "后端 API"
  monitor_process "$WORKER_PID" "后台 Worker"
  monitor_process "$FRONTEND_PID" "前端 Vite"
  sleep 1
done
