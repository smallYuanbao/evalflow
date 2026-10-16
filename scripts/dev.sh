#!/usr/bin/env bash
#
# 起后端 dev server（FastAPI,端口 8002）。
#
# ## 为什么是 8002,不是 8000
#
# 因为 8000 被 docker compose 里的 Chroma 占着（映射到宿主机 8000，
# curl 一下响应头带 chroma-trace-id）。后端只能让开。
#
# 而 README、本脚本、前端 client.ts 的默认值原先是**三处都写 8000** ——
# 也就是说三处都指向了 Chroma。真实在跑的是 8002，却只存在于
# "某次手动敲的命令"里。这类"只有当事人知道"的配置，代价是下一次调试时
# 花半小时从"接口 404"倒推到"连错服务"。
# 现在端口统一在 scripts/devguard.mjs 顶部的表里。
#
set -euo pipefail

cd "$(dirname "$0")/.."

# 启动前先确认端口没被别人占着。
#
# 这不是礼貌性检查：如果 8002 上坐着别的服务，uvicorn 会直接起不来，
# 而前端所有 /api 请求会**安静地**打到那个服务上 —— 症状是「接口 404 / 数据不对」，
# 和病因（端口）隔得很远。devguard 会在启动前把这件事挑明。
node scripts/devguard.mjs

mkdir -p data
uv run uvicorn backend.main:app --port "${BACKEND_PORT:-8002}" --reload
