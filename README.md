# HireFlow Live

HireFlow Live 是一个面试场景 AI 助手原型，支持简历解析、实时语音转写、说话人角色判断、分段 AI 分析、追问建议和面试报告归档。

## 功能

- 简历上传与 ResumeSDK 解析
- 简历解析视图与候选人画像视图
- 豆包实时 ASR 转写
- 面试官 / 候选人角色判断
- DeepSeek 分段分析、存疑点与追问建议
- 测试模式模拟无麦克风演示
- 面试结束后生成 TXT / PDF 报告
- 面试文件按时间戳归档到本地目录

## 环境变量

复制 `.env.example` 为 `.env`，并填写自己的服务密钥：

```powershell
copy .env.example .env
notepad .env
```

常用配置项：

```text
DOUBAO_APP_ID=your-doubao-app-id
DOUBAO_ACCESS_TOKEN=your-doubao-access-token
RESUMESDK_UID=your-resumesdk-uid
RESUMESDK_PWD=your-resumesdk-pwd
DEEPSEEK_API_KEY=your-deepseek-api-key
REPORT_OUTPUT_DIR=D:\FS
```

不要把 `.env` 提交到仓库。

## 安装

```powershell
npm install
python -m pip install -r requirements.txt
```

## 启动

后端：

```powershell
python .\doubao_asr_web.py
```

前端：

```powershell
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173/
```

## 构建检查

```powershell
npm run build
python -m py_compile .\doubao_asr_web.py
```

## 说明

当前项目处于可演示 MVP 阶段，适合内部演示和业务验证。生产部署前建议补充权限控制、任务队列、企业微信推送、端到端测试和数据保留策略。
