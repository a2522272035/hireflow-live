FROM node:20-bookworm AS frontend

WORKDIR /app

COPY package*.json ./
RUN npm ci --registry=https://registry.npmmirror.com

COPY index.html vite.config.js ./
COPY src ./src
ENV VITE_BASE_PATH=/hireflow-live/
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-wqy-microhei fonts-noto-cjk fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

COPY doubao_asr_web.py doubao_asr_final.py ./
COPY --from=frontend /app/dist ./dist

RUN mkdir -p /app/reports

EXPOSE 8770 8771

CMD ["python", "-B", "-u", "doubao_asr_web.py", "--host", "0.0.0.0", "--http-port", "8770", "--ws-port", "8771"]
