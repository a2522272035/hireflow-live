import argparse
import base64
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import websocket


WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference/"
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Paraformer Realtime ASR v2</title>
  <style>
    :root { color-scheme: light dark; font-family: Arial, "Microsoft YaHei", sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f5f7fb; color: #16181d; }
    main { width: min(760px, calc(100vw - 32px)); }
    h1 { font-size: 28px; margin: 0 0 12px; }
    .panel { background: #fff; border: 1px solid #dfe5ee; border-radius: 8px; padding: 20px; box-shadow: 0 8px 28px rgba(22,24,29,.08); }
    .controls { display: flex; gap: 12px; flex-wrap: wrap; margin: 18px 0; }
    button { border: 0; border-radius: 6px; padding: 10px 16px; font-size: 15px; cursor: pointer; background: #1769e0; color: #fff; }
    button.secondary { background: #eef2f7; color: #16181d; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    #status { min-height: 24px; color: #4d5968; }
    .log { background: #111827; color: #d8f7df; border-radius: 6px; min-height: 240px; max-height: 54vh; overflow: auto; padding: 14px; white-space: pre-wrap; font: 14px/1.5 Consolas, monospace; }
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>Paraformer Realtime ASR v2</h1>
      <div id="status">点击开始后允许浏览器使用麦克风。</div>
      <div class="controls">
        <button id="start">开始说话</button>
        <button class="secondary" id="stop" disabled>停止</button>
      </div>
      <div class="log" id="log"></div>
    </section>
  </main>

  <script>
    const startButton = document.getElementById('start');
    const stopButton = document.getElementById('stop');
    const statusEl = document.getElementById('status');
    const logEl = document.getElementById('log');
    let audioContext, source, processor, stream, pollTimer, lastEventId = 0;
    let sending = false;

    function log(line) {
      logEl.textContent += line + "\n";
      logEl.scrollTop = logEl.scrollHeight;
    }

    function downsampleTo16k(buffer, inputRate) {
      const outputRate = 16000;
      if (inputRate === outputRate) return buffer;
      const ratio = inputRate / outputRate;
      const length = Math.floor(buffer.length / ratio);
      const result = new Float32Array(length);
      for (let i = 0; i < length; i++) result[i] = buffer[Math.floor(i * ratio)] || 0;
      return result;
    }

    function floatTo16BitPCM(float32) {
      const pcm = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const sample = Math.max(-1, Math.min(1, float32[i]));
        pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      }
      return pcm.buffer;
    }

    async function postAudio(arrayBuffer) {
      if (!sending || !arrayBuffer.byteLength) return;
      await fetch('/audio', { method: 'POST', body: arrayBuffer });
    }

    async function pollEvents() {
      const res = await fetch('/events?after=' + lastEventId);
      const data = await res.json();
      for (const event of data.events) {
        lastEventId = Math.max(lastEventId, event.id);
        if (event.type === 'final') log('final: ' + event.text);
        if (event.type === 'asr_final') log('asr_final: ' + event.text);
        if (event.type === 'partial') statusEl.textContent = event.text;
        if (event.type === 'turn_wait') statusEl.textContent = '等待继续：' + (event.reason || '');
        if (event.type === 'llm') log('deepseek: ' + event.text);
        if (event.type === 'status') statusEl.textContent = event.message;
        if (event.type === 'error') log('error: ' + event.message);
      }
    }

    startButton.onclick = async () => {
      startButton.disabled = true;
      statusEl.textContent = '正在连接阿里 Paraformer...';
      const startRes = await fetch('/start', { method: 'POST' });
      if (!startRes.ok) {
        const text = await startRes.text();
        statusEl.textContent = '启动失败';
        log(text);
        startButton.disabled = false;
        return;
      }

      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      source = audioContext.createMediaStreamSource(stream);
      processor = audioContext.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);
        const pcm = floatTo16BitPCM(downsampleTo16k(input, audioContext.sampleRate));
        postAudio(pcm).catch((err) => log('audio send error: ' + err.message));
      };
      source.connect(processor);
      processor.connect(audioContext.destination);
      sending = true;
      pollTimer = setInterval(() => pollEvents().catch(() => {}), 300);
      statusEl.textContent = '已开始。Paraformer 判定句子结束时会输出 final。';
      stopButton.disabled = false;
    };

    stopButton.onclick = async () => {
      sending = false;
      stopButton.disabled = true;
      clearInterval(pollTimer);
      if (processor) processor.disconnect();
      if (source) source.disconnect();
      if (audioContext) await audioContext.close();
      if (stream) stream.getTracks().forEach((track) => track.stop());
      await fetch('/stop', { method: 'POST' });
      await pollEvents().catch(() => {});
      startButton.disabled = false;
      statusEl.textContent = '已停止。';
    };
  </script>
</body>
</html>
"""


def load_env() -> None:
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip().lstrip("\ufeff")] = value.strip().strip('"').strip("'")


def get_api_key() -> str:
    load_env()
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("missing DASHSCOPE_API_KEY in .env or environment")
    return api_key


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def deepseek_chat(messages: list[dict], max_tokens: int, temperature: float, timeout: int = 12) -> str:
    load_env()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("missing DEEPSEEK_API_KEY for semantic final detection")

    endpoint = os.getenv("DEEPSEEK_CHAT_URL")
    if not endpoint:
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        endpoint = f"{base_url}/chat/completions"

    body = {
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc

    return payload["choices"][0]["message"]["content"]


def extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def make_ws_frame(payload: bytes) -> bytes:
    header = bytearray([0x81])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.extend([126, (length >> 8) & 0xFF, length & 0xFF])
    else:
        header.extend(
            [
                127,
                (length >> 56) & 0xFF,
                (length >> 48) & 0xFF,
                (length >> 40) & 0xFF,
                (length >> 32) & 0xFF,
                (length >> 24) & 0xFF,
                (length >> 16) & 0xFF,
                (length >> 8) & 0xFF,
                length & 0xFF,
            ]
        )
    return bytes(header) + payload


def read_ws_frame(sock) -> int | None:
    first = sock.recv(2)
    if not first:
        return None
    opcode = first[0] & 0x0F
    masked = bool(first[1] & 0x80)
    length = first[1] & 0x7F
    if length == 126:
        length = int.from_bytes(sock.recv(2), "big")
    elif length == 127:
        length = int.from_bytes(sock.recv(8), "big")
    mask = sock.recv(4) if masked else b""
    payload = b""
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk:
            break
        payload += chunk
    if masked and payload:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode


def fallback_analysis(text: str) -> dict:
    cleaned = text.strip()
    if not cleaned:
        return {
            "analysis": "等待候选人给出更完整的回答。",
            "questions": ["可以再补充一个具体例子吗？", "这个结果你是如何衡量的？"],
        }
    topic = cleaned[:24]
    return {
        "analysis": "候选人已经给出回答，可以继续追问其背景、过程和结果，以验证真实经历与思考深度。",
        "questions": [
            f"你刚才提到“{topic}”，能展开讲一个具体案例吗？",
            "这个结果是如何衡量的？",
            "如果重新做一次，你会怎么调整？",
        ],
    }


def analyze_interview_answer(text: str) -> dict:
    load_env()
    if not os.getenv("DEEPSEEK_API_KEY"):
        return fallback_analysis(text)

    system_prompt = """
你是实时面试 AI 辅助系统。根据候选人的最新回答，给面试官一个简短分析，并生成 2 到 3 个建议追问问题。
只返回 JSON，不要 Markdown：
{"analysis":"...", "questions":["...","..."]}
分析要指出回答质量、证据充分性、可追问方向。问题要具体、短、适合面试官直接点击发送。
""".strip()
    content = deepseek_chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"候选人回答：{text}"},
        ],
        max_tokens=500,
        temperature=0.2,
        timeout=int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "12")),
    )
    result = extract_json_object(content)
    questions = result.get("questions") or []
    return {
        "analysis": str(result.get("analysis") or "已生成分析，但返回内容缺少 analysis 字段。"),
        "questions": [str(item) for item in questions[:3]],
    }


def semantic_turn_decision(transcript: str, include_reply: bool) -> dict:
    reply_instruction = (
        "如果 complete=true，同时在 reply 字段给出面试官/评估助手应该立刻返回给面试者的简短中文回复。"
        if include_reply
        else "reply 字段固定为空字符串。"
    )
    system_prompt = f"""
你是实时语音面试系统的语义端点检测器。
输入是 ASR 已经稳定的一段或多段中文转写，可能有错字。
你的任务不是回答内容，而是判断面试者这一轮是否已经表达完，可以把完整文本交给下游大模型。

判断规则：
- 如果只是短暂停顿，但语义明显没说完，complete=false。
- 如果末尾像“因为、然后、比如、首先、第二、我觉得、主要是、所以说、但是”等明显还要继续，complete=false。
- 如果只是一个完整回答、完整问题、完整陈述、完整选择或完整命令，complete=true。
- 不要因为句子短就判 false；“可以”“没有了”“我不知道”“是的”这类完整答复应为 true。
- 面试场景中，宁可稍等一个分句，也不要把明显半句话提前触发下游。

只返回一行 JSON，不要 Markdown：
{{"complete": true/false, "reason": "不超过20字", "reply": "..." }}
{reply_instruction}
""".strip()
    content = deepseek_chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"ASR稳定转写：{transcript}"},
        ],
        max_tokens=300 if include_reply else 120,
        temperature=0,
        timeout=int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "12")),
    )
    decision = extract_json_object(content)
    return {
        "complete": bool(decision.get("complete")),
        "reason": str(decision.get("reason") or ""),
        "reply": str(decision.get("reply") or ""),
    }


class ParaformerSession:
    def __init__(self, model: str, sample_rate: int, max_sentence_silence: int, language_hints: list[str]):
        self.model = model
        self.sample_rate = sample_rate
        self.max_sentence_silence = max_sentence_silence
        self.language_hints = language_hints
        self.lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.started = threading.Event()
        self.ws = None
        self.receiver = None
        self.task_id = ""
        self.running = False
        self.events: list[dict] = []
        self.event_clients = {}
        self.event_id = 0
        self.partial = ""
        self.seen_finals: set[tuple[int | None, int | None, str]] = set()
        self.turn_buffer: list[str] = []
        self.turn_version = 0
        self.semantic_final_enabled = env_bool("SEMANTIC_FINAL_ENABLED", True)
        self.deepseek_reply_enabled = env_bool("DEEPSEEK_REPLY_ENABLED", False)
        self.semantic_debounce_ms = int(os.getenv("SEMANTIC_FINAL_DEBOUNCE_MS", "250"))

    def add_event(self, event_type: str, **payload) -> None:
        with self.lock:
            self.event_id += 1
            event = {"id": self.event_id, "type": event_type, **payload}
            self.events.append(event)
            self.events = self.events[-200:]
            clients = list(self.event_clients.items())
        self.broadcast_event(event, clients)
        if event_type == "final":
            print(f"final: {payload.get('text', '')}", flush=True)
        elif event_type == "error":
            print(f"error: {payload.get('message', '')}", flush=True)

    def register_event_client(self, sock) -> None:
        with self.lock:
            self.event_clients[sock] = threading.Lock()

    def unregister_event_client(self, sock) -> None:
        with self.lock:
            self.event_clients.pop(sock, None)

    def broadcast_event(self, event: dict, clients=None) -> None:
        payload = json.dumps(event, ensure_ascii=False).encode("utf-8")
        frame = make_ws_frame(payload)
        dead = []
        for sock, lock in clients or []:
            try:
                with lock:
                    sock.sendall(frame)
            except Exception:
                dead.append(sock)
        if dead:
            with self.lock:
                for sock in dead:
                    self.event_clients.pop(sock, None)

    def run_task_message(self) -> str:
        parameters = {
            "format": "pcm",
            "sample_rate": self.sample_rate,
            "disfluency_removal_enabled": False,
            "semantic_punctuation_enabled": False,
            "max_sentence_silence": self.max_sentence_silence,
            "punctuation_prediction_enabled": True,
            "inverse_text_normalization_enabled": True,
        }
        if self.language_hints:
            parameters["language_hints"] = self.language_hints

        return json.dumps(
            {
                "header": {
                    "action": "run-task",
                    "task_id": self.task_id,
                    "streaming": "duplex",
                },
                "payload": {
                    "task_group": "audio",
                    "task": "asr",
                    "function": "recognition",
                    "model": self.model,
                    "parameters": parameters,
                    "input": {},
                },
            },
            ensure_ascii=False,
        )

    def finish_task_message(self) -> str:
        return json.dumps(
            {
                "header": {
                    "action": "finish-task",
                    "task_id": self.task_id,
                    "streaming": "duplex",
                },
                "payload": {"input": {}},
            },
            ensure_ascii=False,
        )

    def start(self) -> None:
        self.stop()
        self.started.clear()
        self.task_id = uuid.uuid4().hex
        self.partial = ""
        self.seen_finals.clear()
        self.turn_buffer.clear()
        self.turn_version += 1

        headers = [
            f"Authorization: Bearer {get_api_key()}",
            "user-agent: paraformer-realtime-validator",
        ]
        workspace = os.getenv("DASHSCOPE_WORKSPACE") or os.getenv("X_DASHSCOPE_WORKSPACE")
        if workspace:
            headers.append(f"X-DashScope-WorkSpace: {workspace}")

        ws = websocket.create_connection(WS_URL, header=headers, timeout=15)
        ws.settimeout(None)
        with self.lock:
            self.ws = ws
            self.running = True

        self.receiver = threading.Thread(target=self.receive_loop, daemon=True)
        self.receiver.start()
        with self.send_lock:
            ws.send(self.run_task_message(), opcode=websocket.ABNF.OPCODE_TEXT)

        if not self.started.wait(timeout=15):
            self.stop()
            raise RuntimeError("task-started timeout")

        with self.lock:
            if not self.running:
                raise RuntimeError("task failed before audio streaming started")

    def send_audio(self, audio: bytes) -> None:
        with self.lock:
            ws = self.ws
            running = self.running
        if ws and running and self.started.is_set() and audio:
            with self.send_lock:
                ws.send(audio, opcode=websocket.ABNF.OPCODE_BINARY)

    def stop(self) -> None:
        with self.lock:
            ws = self.ws
            task_id = self.task_id
            running = self.running
            self.running = False
            self.ws = None
        if ws:
            try:
                if running and task_id:
                    with self.send_lock:
                        ws.send(self.finish_task_message(), opcode=websocket.ABNF.OPCODE_TEXT)
            except Exception:
                pass
            try:
                ws.close()
            except Exception:
                pass

    def receive_loop(self) -> None:
        while True:
            with self.lock:
                ws = self.ws
                running = self.running
            if not ws or not running:
                return

            try:
                raw = ws.recv()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                message = json.loads(raw)
                header = message.get("header") or {}
                event = header.get("event")

                if event == "task-started":
                    self.add_event("status", message="任务已启动，可以说话。")
                    self.started.set()
                elif event == "result-generated":
                    sentence = (message.get("payload") or {}).get("output", {}).get("sentence", {})
                    if sentence.get("heartbeat") is True:
                        continue
                    text = (sentence.get("text") or "").strip()
                    if not text:
                        continue
                    if sentence.get("sentence_end") is True:
                        key = (sentence.get("begin_time"), sentence.get("end_time"), text)
                        if key not in self.seen_finals:
                            self.seen_finals.add(key)
                            self.handle_asr_final(text)
                    elif text != self.partial:
                        self.partial = text
                        self.add_event("partial", text=text)
                elif event == "task-failed":
                    code = header.get("error_code") or "TASK_FAILED"
                    detail = header.get("error_message") or json.dumps(message, ensure_ascii=False)
                    self.add_event("error", message=f"{code}: {detail}")
                    self.started.set()
                    with self.lock:
                        self.running = False
                    return
                elif event == "task-finished":
                    self.add_event("status", message="任务已结束。")
                    with self.lock:
                        self.running = False
                    return
            except Exception as exc:
                if exc.__class__.__name__ == "WebSocketTimeoutException":
                    continue
                with self.lock:
                    still_running = self.running
                    self.running = False
                self.started.set()
                if still_running:
                    self.add_event("error", message=f"{type(exc).__name__}: {exc}")
                return

    def events_after(self, after: int) -> list[dict]:
        with self.lock:
            return [event for event in self.events if event["id"] > after]

    def handle_asr_final(self, text: str) -> None:
        self.add_event("asr_final", text=text)
        with self.lock:
            self.turn_buffer.append(text)
            self.turn_version += 1
            version = self.turn_version
            transcript = "".join(self.turn_buffer).strip()

        if not self.semantic_final_enabled:
            with self.lock:
                self.turn_buffer.clear()
                self.turn_version += 1
            self.add_event("final", text=transcript)
            return

        self.add_event("status", message="正在判断语义是否完整...")
        threading.Thread(
            target=self.semantic_decision_worker,
            args=(version, transcript),
            daemon=True,
        ).start()

    def semantic_decision_worker(self, version: int, transcript: str) -> None:
        if self.semantic_debounce_ms > 0:
            time.sleep(self.semantic_debounce_ms / 1000)

        try:
            decision = semantic_turn_decision(transcript, self.deepseek_reply_enabled)
        except Exception as exc:
            self.add_event("error", message=f"semantic final failed: {exc}")
            return

        with self.lock:
            if version != self.turn_version:
                return
            if decision["complete"]:
                self.turn_buffer.clear()
                self.turn_version += 1

        if decision["complete"]:
            self.add_event("final", text=transcript)
            if decision.get("reply"):
                self.add_event("llm", text=decision["reply"])
        else:
            self.add_event("turn_wait", text=transcript, reason=decision.get("reason", "语义未完"))


def make_handler(session: ParaformerSession):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def send_text(self, status: int, text: str, content_type: str = "text/plain; charset=utf-8"):
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status: int, payload: dict):
            self.send_text(status, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")

        def do_GET(self):
            path = urlparse(self.path)
            if path.path == "/ws":
                self.handle_event_websocket()
            elif path.path == "/":
                self.send_text(HTTPStatus.OK, PAGE, "text/html; charset=utf-8")
            elif path.path == "/events":
                params = parse_qs(path.query)
                after = int((params.get("after") or ["0"])[0] or "0")
                self.send_json(HTTPStatus.OK, {"events": session.events_after(after)})
            elif path.path == "/debug-env":
                load_env()
                self.send_json(
                    HTTPStatus.OK,
                    {
                        "cwd": os.getcwd(),
                        "env_path": str(Path(__file__).with_name(".env")),
                        "env_exists": Path(__file__).with_name(".env").exists(),
                        "dashscope_key_loaded": bool(os.getenv("DASHSCOPE_API_KEY")),
                        "workspace_loaded": bool(os.getenv("DASHSCOPE_WORKSPACE")),
                        "model": session.model,
                        "semantic_final_enabled": session.semantic_final_enabled,
                        "deepseek_key_loaded": bool(os.getenv("DEEPSEEK_API_KEY")),
                        "deepseek_reply_enabled": session.deepseek_reply_enabled,
                    },
                )
            else:
                self.send_text(HTTPStatus.NOT_FOUND, "not found")

        def handle_event_websocket(self):
            key = self.headers.get("Sec-WebSocket-Key")
            if not key:
                self.send_text(HTTPStatus.BAD_REQUEST, "missing Sec-WebSocket-Key")
                return
            accept = base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()).decode("ascii")
            self.connection.sendall(
                (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept}\r\n"
                    "\r\n"
                ).encode("ascii")
            )
            self.close_connection = True
            session.register_event_client(self.connection)
            session.broadcast_event(
                {
                    "id": 0,
                    "type": "status",
                    "message": "实时事件通道已连接。",
                },
                [(self.connection, session.event_clients[self.connection])],
            )
            try:
                while True:
                    opcode = read_ws_frame(self.connection)
                    if opcode in (None, 0x8):
                        break
            except Exception:
                pass
            finally:
                session.unregister_event_client(self.connection)

        def do_POST(self):
            if self.path == "/start":
                try:
                    session.start()
                except Exception as exc:
                    self.send_text(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                    return
                self.send_json(HTTPStatus.OK, {"ok": True})
            elif self.path == "/audio":
                length = int(self.headers.get("Content-Length", "0") or "0")
                try:
                    session.send_audio(self.rfile.read(length))
                except Exception as exc:
                    session.add_event("error", message=f"audio send failed: {type(exc).__name__}: {exc}")
                    self.send_text(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                    return
                self.send_json(HTTPStatus.OK, {"ok": True})
            elif self.path == "/stop":
                session.stop()
                self.send_json(HTTPStatus.OK, {"ok": True})
            elif self.path == "/api/analyze":
                length = int(self.headers.get("Content-Length", "0") or "0")
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    result = analyze_interview_answer(str(payload.get("text") or ""))
                except Exception as exc:
                    self.send_text(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                    return
                self.send_json(HTTPStatus.OK, result)
            else:
                self.send_text(HTTPStatus.NOT_FOUND, "not found")

    return Handler


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Browser microphone validator for Alibaba Paraformer realtime ASR v2.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--model", default=os.getenv("PARAFORMER_MODEL", "paraformer-realtime-v2"))
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--max-sentence-silence", type=int, default=int(os.getenv("PARAFORMER_MAX_SENTENCE_SILENCE", "800")))
    parser.add_argument("--language-hints", default=os.getenv("PARAFORMER_LANGUAGE_HINTS", "zh"))
    parser.add_argument("--log-file")
    args = parser.parse_args()

    if args.log_file:
        log = open(args.log_file, "a", encoding="utf-8", buffering=1)
        sys.stdout = log
        sys.stderr = log

    language_hints = [item.strip() for item in args.language_hints.split(",") if item.strip()]
    session = ParaformerSession(args.model, args.sample_rate, args.max_sentence_silence, language_hints)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(session))
    print(f"open http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        session.stop()
        server.server_close()


if __name__ == "__main__":
    main()
