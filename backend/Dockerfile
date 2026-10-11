# EvalFlow 后端:FastAPI + SQLite + ChromaDB 客户端(embedding 走宿主机 Ollama)
FROM python:3.12-slim

WORKDIR /app

# 依赖层单独一层:与 pyproject.toml 的 dependencies 保持一致,代码变更时不重装
RUN pip install --no-cache-dir \
    "alembic>=1.14" \
    "celery[redis]>=5.4.0" \
    "chromadb>=1.5.9" \
    "fastapi>=0.142.4" \
    "numpy>=2.5.3" \
    "onnxruntime==1.23.2" \
    "openai>=3.26.0" \
    "psycopg[binary]>=3.2" \
    "pydantic-settings>=2.15.0" \
    "requests>=2.34.2" \
    "sqlalchemy>=2.1.4" \
    "uvicorn[standard]>=0.54.0"

COPY backend ./backend
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

# 非 root 运行(Ch14 交付加固):建独立用户,数据目录归它所有;命名卷首次挂载会继承这里的属主
RUN useradd --create-home --uid 1000 evalflow \
    && mkdir -p /app/data \
    && chown -R evalflow:evalflow /app/data
USER evalflow

EXPOSE 8000
# migrate-then-serve:先跑迁移再起服务(生产正确姿势;本地 dev 仍走 lifespan 的 init_db 自动迁移)
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
