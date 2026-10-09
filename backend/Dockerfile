# EvalFlow 后端:FastAPI + SQLite + ChromaDB 客户端(embedding 走宿主机 Ollama)
FROM python:3.12-slim

WORKDIR /app

# 依赖层单独一层:与 pyproject.toml 的 dependencies 保持一致,代码变更时不重装
RUN pip install --no-cache-dir \
    "chromadb>=1.5.9" \
    "fastapi>=0.142.4" \
    "numpy>=2.5.3" \
    "onnxruntime==1.23.2" \
    "openai>=3.26.0" \
    "pydantic-settings>=2.15.0" \
    "requests>=2.34.2" \
    "sqlalchemy>=2.1.4" \
    "uvicorn[standard]>=0.54.0"

COPY backend ./backend

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
