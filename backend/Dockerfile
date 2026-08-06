FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src

# 系统依赖（PyMuPDF 需要 libmupdf）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖层（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
