#!/usr/bin/env bash
# =============================================================================
# Fund Investment Platform (基金投资平台) 本地一键启动脚本
# =============================================================================
set -e

# 获取当前脚本所在根目录
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# 输出带色彩提示
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
BOLD="\033[1m"
RESET="\033[0m"

echo -e "${CYAN}${BOLD}"
echo "=================================================================="
echo "    🚀 Fund Investment Platform (基金投资平台) 本地启动程序     "
echo "=================================================================="
echo -e "${RESET}"

START_BACKEND=true
START_FRONTEND=true
START_WORKER=false

# 解析入参选项
for arg in "$@"; do
  case $arg in
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
      echo "用法: ./start.sh [选项]"
      echo ""
      echo "选项:"
      echo "  (无参数)         默认同时启动后端 API (端口 8000) 与前端应用 (端口 5173)"
      echo "  --with-worker    同时启动后台异步作业 Worker 进程"
      echo "  --api-only       仅启动后端 API 服务"
      echo "  --frontend-only  仅启动前端 Web 界面"
      echo "  --help, -h       查看帮助说明"
      exit 0
      ;;
  esac
done

# 1. 环境依赖检查
echo -e "${YELLOW}🔍 正在检查运行环境依赖...${RESET}"

if [ "$START_BACKEND" = true ] || [ "$START_WORKER" = true ]; then
  if [ ! -f ".venv/bin/python" ]; then
    echo -e "${RED}❌ 错误: 未检测到 Python 虚拟环境 (.venv/bin/python)。${RESET}"
    echo "请先在根目录运行初始化命令安装环境:"
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/pip install -r requirements.lock"
    exit 1
  fi
  echo -e "${GREEN}  ✓ Python 虚拟环境正常 (.venv)${RESET}"
fi

if [ "$START_FRONTEND" = true ]; then
  if ! command -v node >/dev/null 2>&1; then
    echo -e "${RED}❌ 错误: 系统中未检测到 Node.js，请先安装 Node.js (推荐 v18+)。${RESET}"
    exit 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo -e "${RED}❌ 错误: 系统中未检测到 npm 命令。${RESET}"
    exit 1
  fi
  echo -e "${GREEN}  ✓ Node.js & npm 环境正常 ($(node -v))${RESET}"

  if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}  ⚡️ 检测到前端未安装依赖，正在自动执行 npm install...${RESET}"
    (cd frontend && npm install)
  fi
  echo -e "${GREEN}  ✓ 前端依赖包就绪 (frontend/node_modules)${RESET}"
fi

# 2. 检查端口占用
check_port() {
  local port=$1
  local name=$2
  if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️ 警告: 端口 $port ($name) 已被占用。如需重启，请先释放端口。${RESET}"
  fi
}

if [ "$START_BACKEND" = true ]; then
  check_port 8000 "后端 API"
fi
if [ "$START_FRONTEND" = true ]; then
  check_port 5173 "前端 Vite"
fi

# 清理进程 Hook
BACKEND_PID=""
FRONTEND_PID=""
WORKER_PID=""

cleanup() {
  echo ""
  echo -e "${YELLOW}🛑 正在安全停止所有服务进程...${RESET}"
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [ -n "$WORKER_PID" ] && kill -0 "$WORKER_PID" 2>/dev/null; then
    kill "$WORKER_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  echo -e "${GREEN}✅ 所有服务已安全退出。${RESET}"
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 3. 启动后端 API 服务
if [ "$START_BACKEND" = true ]; then
  echo -e "\n${CYAN}▶️ 正在启动后端 FastAPI 服务 (http://127.0.0.1:8000)...${RESET}"
  PYTHONPATH=src FIP_ENABLE_M2_REBALANCE=true .venv/bin/uvicorn fip.api.app:app \
    --host 127.0.0.1 \
    --port 8000 \
    --reload &
  BACKEND_PID=$!

  # 等待后端服务响应探针
  echo -n "  等待后端就绪"
  for _ in {1..20}; do
    if curl -s http://127.0.0.1:8000/health/live | grep -q "status"; then
      echo -e " ${GREEN}✓ 就绪!${RESET}"
      break
    fi
    echo -n "."
    sleep 0.5
  done
fi

# 4. 启动后台 Worker 进程 (若启用)
if [ "$START_WORKER" = true ]; then
  echo -e "\n${CYAN}▶️ 正在启动后台异步计算作业 Worker 进程...${RESET}"
  PYTHONPATH=src .venv/bin/python -m fip.platform.jobs.worker &
  WORKER_PID=$!
  echo -e "${GREEN}  ✓ Worker 进程已启动 (PID: $WORKER_PID)${RESET}"
fi

# 5. 启动前端 Vite 服务
if [ "$START_FRONTEND" = true ]; then
  echo -e "\n${CYAN}▶️ 正在启动前端 React + Vite 服务 (http://localhost:5173)...${RESET}"
  (cd frontend && npm run dev) &
  FRONTEND_PID=$!
  sleep 1.5
fi

# 6. 展示成功看板
echo ""
echo -e "${GREEN}${BOLD}==================================================================${RESET}"
echo -e "${GREEN}${BOLD}🎉 Fund Investment Platform 全部服务已启动完成！${RESET}"
echo -e "${GREEN}${BOLD}==================================================================${RESET}"
echo -e "  💻 ${BOLD}前端交互界面:${RESET}     ${CYAN}http://localhost:5173${RESET}"
echo -e "  🔌 ${BOLD}后端 API 服务:${RESET}    ${CYAN}http://127.0.0.1:8000${RESET}"
echo -e "  📖 ${BOLD}OpenAPI 文档:${RESET}     ${CYAN}http://127.0.0.1:8000/docs${RESET}"
echo -e "  📊 ${BOLD}Prometheus 指标:${RESET}  ${CYAN}http://127.0.0.1:8000/metrics${RESET}"
echo -e "  🩺 ${BOLD}健康状态检查:${RESET}     ${CYAN}http://127.0.0.1:8000/health/live${RESET}"
echo -e "------------------------------------------------------------------"
echo -e "  💡 ${BOLD}核心功能入口直达:${RESET}"
echo -e "     • 基金筛选与研究看板:  ${CYAN}http://localhost:5173/funds${RESET}"
echo -e "     • 候选池全时快照:      ${CYAN}http://localhost:5173/universes${RESET}"
echo -e "     • 组合决策与实盘调仓:  ${CYAN}http://localhost:5173/portfolios/P001${RESET}"
echo -e "     • 组合全闭环策略回测:  ${CYAN}http://localhost:5173/backtests${RESET}"
echo -e "=================================================================="
echo -e "${YELLOW}服务正在运行中，终端将实时展示访问日志。随时按下 [Ctrl + C] 即可安全停止全部服务。${RESET}\n"

# 挂起脚本持续监听退出信号并捕获后台日志
wait
