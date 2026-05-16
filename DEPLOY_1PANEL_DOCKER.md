# 1Panel Docker 部署

推荐部署方式：Docker Compose 跑应用，1Panel 网站反向代理到容器本机端口，再开启 HTTPS。

## 1. 拉取代码

```bash
cd /opt
git clone https://github.com/a2522272035/hireflow-live.git
cd hireflow-live
```

后续更新：

```bash
git pull
docker compose up -d --build
```

## 2. 配置环境变量

```bash
cp .env.example .env
vim .env
```

至少确认这些值：

```env
ASR_PROVIDER=tencent_speaker
ASR_MODE=fast
TENCENT_APP_ID=你的腾讯APPID
TENCENT_SECRET_ID=你的腾讯SecretId
TENCENT_SECRET_KEY=你的腾讯SecretKey
TENCENT_ASR_ENGINE=16k_zh_en_speaker
TENCENT_NEED_VAD=1
TENCENT_VAD_SILENCE_TIME=600
TENCENT_SPEAKER_DIARIZATION=1
TENCENT_ENABLE_SPEAKER_CONTEXT=1
TENCENT_FIRST_SPEAKER_ROLE=interviewer
DEEPSEEK_API_KEY=你的DeepSeekKey

# 一阶段数据持久化，连接同机 PostgreSQL/pgvector 容器。
ENABLE_DATABASE=1
ENABLE_PGVECTOR=1
DATABASE_URL=postgresql://hireflow:hireflow_dev_123@host.docker.internal:5432/hireflow
```

容器里报告目录由 `docker-compose.yml` 统一覆盖为：

```env
REPORT_OUTPUT_DIR=/app/reports
```

宿主机会落到项目目录下的：

```text
/opt/hireflow-live/reports
```

## 3. 启动容器

命令行启动：

```bash
docker compose up -d --build
docker logs -f hireflow-live
```

1Panel 启动：

1. 打开 `容器 -> 编排`
2. 新建编排
3. 选择 `/opt/hireflow-live/docker-compose.yml`
4. 启动

健康检查：

```bash
curl http://127.0.0.1:18770/debug-env
curl http://127.0.0.1:18770/api/db/status
```

应该看到：

```json
{
  "provider": "tencent_speaker",
  "app_id_loaded": true,
  "secret_id_loaded": true,
  "secret_key_loaded": true
}
```

数据库正常时，`/api/db/status` 应看到：

```json
{
  "enabled": true,
  "database_url_loaded": true,
  "pgvector_enabled": true,
  "schema_ready": true
}
```

## 4. 1Panel 网站反向代理

创建网站：

```text
网站类型：反向代理
主域名：你的域名，例如 interview.example.com
前端请求路径：/hireflow-live
代理地址：http://127.0.0.1:18770
```

开启 HTTPS。浏览器麦克风在公网环境下通常要求 HTTPS。

## 5. 配置 WebSocket

线上页面会连接：

```text
wss://你的域名/hireflow-live/ws
```

在 1Panel 网站的 Nginx 配置里增加：

```nginx
location ^~ /hireflow-live/ws {
    proxy_pass http://127.0.0.1:18771;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

## 6. 防火墙

公网只开放：

```text
80
443
```

不要开放：

```text
18770
18771
```

这两个端口已经通过 `127.0.0.1` 绑定，只给本机 1Panel/Nginx 访问。

## 7. 常用命令

```bash
docker compose ps
docker compose logs -f
docker compose restart
docker compose down
docker compose up -d --build
```
