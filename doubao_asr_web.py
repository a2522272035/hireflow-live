import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
import math
import mimetypes
import os
import re
import select
import shutil
import socket
import struct
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse
from xml.sax.saxutils import escape

from doubao_asr_final import (
    URL,
    MSG_ERROR_RESPONSE,
    build_audio_request,
    build_full_client_request,
    iter_utterances,
    load_dotenv,
    make_headers,
    parse_server_message,
)

load_dotenv()

WS_PORT = int(os.getenv("WS_PORT", "8771"))

PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HireFlow AI Interview Assistant</title>
  <style>
    :root { color-scheme: light dark; font-family: Arial, "Microsoft YaHei", sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f6f7f9; color: #16181d; }
    main { width: min(760px, calc(100vw - 32px)); }
    h1 { font-size: 28px; margin: 0 0 12px; }
    .panel { background: #fff; border: 1px solid #dfe3ea; border-radius: 8px; padding: 20px; box-shadow: 0 8px 28px rgba(22,24,29,.08); }
    .controls { display: flex; gap: 12px; flex-wrap: wrap; margin: 18px 0; }
    button { border: 0; border-radius: 6px; padding: 10px 16px; font-size: 15px; cursor: pointer; background: #1d6fdc; color: #fff; }
    button.secondary { background: #eef1f5; color: #16181d; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    #status { min-height: 24px; color: #4d5968; }
    .log { background: #111827; color: #d8f7df; border-radius: 6px; min-height: 220px; max-height: 52vh; overflow: auto; padding: 14px; white-space: pre-wrap; font: 14px/1.5 Consolas, monospace; }
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>HireFlow AI Interview Assistant</h1>
      <div id="status">Click Start and allow browser to use microphone.</div>
      <div class="controls">
        <button id="start">Start Recording</button>
        <button class="secondary" id="stop" disabled>Stop</button>
      </div>
      <div class="log" id="log"></div>
    </section>
  </main>

  <script>
    const startButton = document.getElementById('start');
    const stopButton = document.getElementById('stop');
    const statusEl = document.getElementById('status');
    const logEl = document.getElementById('log');
    let ws, audioContext, source, processor, stream, sending = false;

    function log(line) {
      logEl.textContent += line + "\n";
      logEl.scrollTop = logEl.scrollHeight;
    }

    function floatTo16BitPCM(float32) {
      const pcm = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      return pcm.buffer;
    }

    function downsample(buffer, inputRate) {
      if (inputRate === 16000) return buffer;
      const ratio = inputRate / 16000;
      const length = Math.floor(buffer.length / ratio);
      const result = new Float32Array(length);
      for (let i = 0; i < length; i++) {
        result[i] = buffer[Math.floor(i * ratio)] || 0;
      }
      return result;
    }

    function sendAudio(arrayBuffer) {
      if (!ws || ws.readyState !== WebSocket.OPEN || !sending) return;
      if (!arrayBuffer || arrayBuffer.byteLength === 0) return;
      ws.send(arrayBuffer);
    }

    startButton.onclick = async () => {
      startButton.disabled = true;
      statusEl.textContent = 'Connecting to ASR...';
      ws = new WebSocket('ws://127.0.0.1:${WS_PORT}/');
      ws.onopen = () => log('WS connected');
      ws.onmessage = (e) => {
        const event = JSON.parse(e.data);
        if (event.type === 'final') log('final: ' + event.text);
        if (event.type === 'partial') statusEl.textContent = event.text;
        if (event.type === 'error') log('error: ' + event.message);
        if (event.type === 'status') log(event.message);
      };
      ws.onclose = () => log('WS closed');

      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      source = audioContext.createMediaStreamSource(stream);
      processor = audioContext.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        const pcm = floatTo16BitPCM(downsample(input, audioContext.sampleRate));
        sendAudio(pcm);
      };
      source.connect(processor);
      processor.connect(audioContext.destination);
      sending = true;
      statusEl.textContent = 'Recording... Speak now.';
      stopButton.disabled = false;
    };

    stopButton.onclick = async () => {
      sending = false;
      stopButton.disabled = true;
      if (processor) processor.disconnect();
      if (source) source.disconnect();
      if (audioContext) await audioContext.close();
      if (stream) stream.getTracks().forEach((t) => t.stop());
      if (ws) ws.close();
      startButton.disabled = false;
      statusEl.textContent = 'Stopped.';
    };
  </script>
</body>
</html>
""".replace("${WS_PORT}", str(WS_PORT))


def deepseek_chat(messages: list[dict], max_tokens: int, temperature: float, timeout: int = 12) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("missing DEEPSEEK_API_KEY")

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


def deepseek_chat_stream(messages: list[dict], max_tokens: int, temperature: float, timeout: int = 12, callback=None):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("missing DEEPSEEK_API_KEY")

    endpoint = os.getenv("DEEPSEEK_CHAT_URL")
    if not endpoint:
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        endpoint = f"{base_url}/chat/completions"

    body = {
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
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
            full_content = []
            for line in response:
                line = line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        full_content.append(content)
                        if callback:
                            callback(content)
                except json.JSONDecodeError:
                    continue
            return "".join(full_content)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc


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
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试修复常见的 JSON 格式问题
        text = text.replace("\n", "").replace("\r", "")
        text = text.replace("'", '"')
        while ",," in text:
            text = text.replace(",,", ",")
        return json.loads(text)


def fallback_analysis(text: str) -> dict:
    cleaned = text.strip()
    if not cleaned:
        return {
            "analysis": "当前面试片段内容不足，暂时无法形成有效判断。",
            "is_correct": None,
            "doubts": ["面试片段内容不完整，需要更多上下文。"],
            "questions": ["请补充一个具体案例。", "这个结果是如何衡量的？"],
        }
    topic = cleaned[:24]
    return {
        "analysis": "已收到新的面试片段。建议继续围绕背景、过程、结果和可验证数据追问；若该片段主要是面试官发问，则暂不作为候选人评分依据。",
        "is_correct": None,
        "doubts": [f"提到了“{topic}”，仍需要更多上下文核验真实性和完整性。"],
        "questions": [
            f"你刚才提到“{topic}”，能展开讲一个具体案例吗？",
            "这个结果是用哪些指标衡量的？",
            "如果重新做一次，你会调整哪些地方？",
        ],
    }


# Global variable to store parsed resume info
_parsed_resume = {}


def compact_resume_text(value: Any, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def normalize_resumesdk_result(result: dict, filename: str, raw_response: dict) -> dict:
    def first_value(*keys: str) -> Any:
        for key in keys:
            value = result.get(key)
            if value not in (None, "", []):
                return value
        return ""

    def date_range(item: dict) -> str:
        start = str(item.get("start_date") or "").strip()
        end = str(item.get("end_date") or "").strip()
        return " - ".join(part for part in (start, end) if part)

    education = []
    for item in result.get("education_objs") or []:
        if not isinstance(item, dict):
            continue
        education.append({
            "school": item.get("edu_college") or "",
            "major": item.get("edu_major") or "",
            "degree": item.get("edu_degree_norm") or item.get("edu_degree") or "",
            "start_date": item.get("start_date") or "",
            "end_date": item.get("end_date") or "",
            "duration": date_range(item),
            "description": compact_resume_text(item.get("edu_content"), 300),
        })

    work_experience = []
    for item in result.get("job_exp_objs") or []:
        if not isinstance(item, dict):
            continue
        work_experience.append({
            "company": item.get("job_cpy") or "",
            "title": item.get("job_position") or "",
            "position": item.get("job_position") or "",
            "positionType": item.get("job_position_type") or item.get("job_pos_type") or item.get("job_pos_type_p") or "",
            "department": item.get("job_dept") or "",
            "industry": item.get("job_industry") or "",
            "start_date": item.get("start_date") or "",
            "end_date": item.get("end_date") or "",
            "duration": item.get("job_duration") or date_range(item),
            "nature": item.get("job_nature") or "",
            "description": compact_resume_text(item.get("job_content"), 800),
        })

    projects = []
    for item in result.get("proj_exp_objs") or []:
        if not isinstance(item, dict):
            continue
        projects.append({
            "name": item.get("proj_name") or "",
            "company": item.get("proj_cpy") or "",
            "position": item.get("proj_position") or "",
            "duration": date_range(item),
            "description": compact_resume_text(item.get("proj_content"), 600),
            "responsibility": compact_resume_text(item.get("proj_resp"), 600),
        })

    skills = []
    for item in result.get("skills_objs") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("skills_name") or "").strip()
        if not name:
            continue
        level = str(item.get("skills_level") or "").strip()
        skills.append(f"{name}（{level}）" if level else name)

    certificates = []
    for item in result.get("all_cert_objs") or []:
        if isinstance(item, dict) and item.get("cert_name"):
            certificates.append(str(item.get("cert_name")))

    languages = []
    for item in result.get("lang_objs") or []:
        if not isinstance(item, dict):
            continue
        language = str(item.get("language_name") or "").strip()
        level = str(item.get("language_level") or "").strip()
        if language:
            languages.append(f"{language}（{level}）" if level else language)

    work_year_norm = first_value("work_year_norm", "work_year", "work_year_inf")
    work_company = first_value("work_company")
    work_position = first_value("work_position")
    expect_location = first_value("expect_jlocation_norm", "expect_jlocation", "desired_location")
    avatar_data = first_value("avatar_data", "avatar", "photo_data", "head_img", "portrait")
    avatar_url = first_value("avatar_url", "photo_url", "head_img_url")

    return {
        "source": "ResumeSDK",
        "filename": filename,
        "name": first_value("name"),
        "gender": first_value("gender", "gender_inf"),
        "age": first_value("age", "age_inf"),
        "phone": first_value("phone"),
        "email": first_value("email"),
        "location": first_value("city_norm", "city", "location"),
        "city": first_value("city_norm", "city", "location"),
        "avatar_url": avatar_url,
        "avatar_data": avatar_data,
        "degree": first_value("degree", "degree_norm"),
        "college": first_value("college"),
        "major": first_value("major"),
        "graduation_time": first_value("graduation_time", "graduate_time", "edu_end_date"),
        "college_type": first_value("college_type", "school_type", "college_level"),
        "work_year": work_year_norm,
        "work_year_norm": work_year_norm,
        "work_start_time": first_value("work_start_time", "work_begin_time"),
        "work_start_time_inferred": first_value("work_start_time_inferred", "work_begin_time_inf"),
        "work_position": work_position,
        "work_pos_type_p": first_value("work_pos_type_p", "work_position_type", "job_pos_type_p"),
        "work_company": work_company,
        "current_company": work_company,
        "current_position": work_position,
        "expect_job": first_value("expect_job"),
        "expected_job": first_value("expect_job"),
        "expect_salary": first_value("expect_salary"),
        "expect_salary_min": first_value("expect_salary_min", "expect_salary_low"),
        "expect_salary_max": first_value("expect_salary_max", "expect_salary_high"),
        "desired_location": expect_location,
        "expect_jlocation": first_value("expect_jlocation"),
        "expect_jlocation_norm": first_value("expect_jlocation_norm"),
        "expected_location": expect_location,
        "summary": compact_resume_text(result.get("cont_my_desc"), 800),
        "raw_text": compact_resume_text(result.get("raw_text"), 2000),
        "education": education,
        "experiences": work_experience,
        "work_experience": work_experience,
        "projects": projects,
        "skills": skills[:40],
        "skills_objs": result.get("skills_objs") or [],
        "certificates": certificates[:20],
        "certificate_text": compact_resume_text(first_value("certificate_text", "cert_text"), 1000),
        "languages": languages[:10],
        "resume_integrity": result.get("resume_integrity") or "",
        "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "eval": raw_response.get("eval") or result.get("eval") or {},
        "tags": raw_response.get("tags") or result.get("tags") or {},
        "raw_result": result,
        "raw": result,
        "raw_resumesdk_response": raw_response,
        "provider_response_status": raw_response.get("status") or {},
    }


def parse_resume_with_resumesdk(file_bytes: bytes, filename: str) -> dict:
    """Use ResumeSDK to parse resume into structured fields."""
    api_url = os.getenv("RESUMESDK_URL", "https://www.resumesdk.com/api/parse")
    uid = os.getenv("RESUMESDK_UID", "")
    pwd = os.getenv("RESUMESDK_PWD", "")
    appcode = os.getenv("RESUMESDK_APPCODE", "")
    auth_mode = os.getenv("RESUMESDK_AUTH_MODE", "").lower()
    timeout = int(os.getenv("RESUMESDK_TIMEOUT_SECONDS", "30"))

    payload = {
        "file_name": filename,
        "file_cont": base64.b64encode(file_bytes).decode("utf-8"),
        "need_avatar": int(os.getenv("RESUMESDK_NEED_AVATAR", "0")),
        "version": int(os.getenv("RESUMESDK_VERSION", "1")),
    }
    if os.getenv("RESUMESDK_OCR_TYPE"):
        payload["ocr_type"] = int(os.getenv("RESUMESDK_OCR_TYPE", "0"))

    headers = {"Content-Type": "application/json; charset=UTF-8"}
    if appcode:
        headers["Authorization"] = f"APPCODE {appcode}"
    elif uid and pwd:
        headers["uid"] = str(uid)
        headers["pwd"] = pwd
    elif auth_mode != "none":
        raise RuntimeError("ResumeSDK not configured: set RESUMESDK_UID/RESUMESDK_PWD or RESUMESDK_APPCODE")

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            response = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ResumeSDK HTTP {exc.code}: {detail}") from exc

    status = response.get("status") if isinstance(response, dict) else {}
    if not isinstance(status, dict) or int(status.get("code") or 0) != 200:
        raise RuntimeError(f"ResumeSDK parse failed: {json.dumps(status or response, ensure_ascii=False)}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("ResumeSDK response missing result")
    return normalize_resumesdk_result(result, filename, response)


def parse_resume_with_resumesdk_hard_timeout(file_bytes: bytes, filename: str) -> dict:
    timeout = int(os.getenv("RESUMESDK_HARD_TIMEOUT_SECONDS", "65"))
    result_holder: dict[str, Any] = {}
    error_holder: dict[str, BaseException] = {}

    def worker():
        try:
            result_holder["result"] = parse_resume_with_resumesdk(file_bytes, filename)
        except BaseException as exc:
            error_holder["error"] = exc

    thread = threading.Thread(target=worker, name="resumesdk-parse", daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    if thread.is_alive():
        raise TimeoutError(f"ResumeSDK 解析超过 {timeout} 秒未返回，请稍后重试或换一个更小/文本型简历文件")
    if "error" in error_holder:
        raise error_holder["error"]
    return result_holder["result"]


def get_resume_context() -> str:
    """Get formatted resume context for AI"""
    if not _parsed_resume:
        return ""
    
    parts = []
    resume = _parsed_resume
    
    if resume.get("name"):
        parts.append(f"候选人姓名：{resume['name']}")
    if resume.get("phone"):
        parts.append(f"电话：{resume['phone']}")
    if resume.get("email"):
        parts.append(f"邮箱：{resume['email']}")
    
    if resume.get("education"):
        edu_list = resume["education"]
        if isinstance(edu_list, list):
            edu_str = "；".join([f"{e.get('school', '')} {e.get('major', '')} {e.get('degree', '')}" for e in edu_list[:3]])
            parts.append(f"教育背景：{edu_str}")
    
    if resume.get("work_experience"):
        work_list = resume["work_experience"]
        if isinstance(work_list, list):
            parts.append("\n工作经历：")
            for w in work_list[:3]:
                parts.append(f"- {w.get('company', '')} | {w.get('position', '')} | {w.get('duration', '')}")
    
    if resume.get("skills"):
        skills = resume["skills"]
        if isinstance(skills, list):
            parts.append(f"技能：{', '.join(skills[:10])}")

    if resume.get("certificates"):
        certificates = resume["certificates"]
        if isinstance(certificates, list):
            parts.append(f"证书：{', '.join(certificates[:8])}")

    if resume.get("summary"):
        parts.append(f"个人总结：{compact_resume_text(resume.get('summary'), 500)}")
    
    if resume.get("projects"):
        proj_list = resume["projects"]
        if isinstance(proj_list, list):
            parts.append("\n项目经历：")
            for p in proj_list[:2]:
                parts.append(f"- {p.get('name', '')}: {p.get('description', '')}")

    if resume.get("raw_text") and len(parts) < 4:
        parts.append(f"简历原文摘要：{compact_resume_text(resume.get('raw_text'), 1000)}")
    
    return "\n".join(parts)


def analyze_interview_answer(text: str, callback=None) -> dict:
    if not os.getenv("DEEPSEEK_API_KEY"):
        return fallback_analysis(text)

    system_prompt = """
你是实时面试AI辅助系统。你会收到最新面试片段，片段可能包含面试官提问、候选人回答，或两者混杂。请完成以下任务：

1. 判断片段中是否存在可评估的候选人回答
2. 如存在候选人回答，分析回答质量、专业相关性和逻辑性
3. 如片段主要是面试官提问、寒暄、噪声或无法确认角色，不要强行当作候选人回答评分
3. 列出需要进一步验证的存疑点
4. 生成2-3个追问问题

只返回JSON，格式如下：
{
  "analysis": "简短的中文分析；如果无法确认候选人回答，请说明暂不评分",
  "is_correct": true/false/null（候选人回答专业且正确返回true，明显错误或态度不端正返回false，角色不明/信息不足/主要是面试官发问返回null）,
  "doubts": ["需要验证的具体说法或疑点，最多5条"],
  "questions": ["2-3个针对性追问，用于验证疑点或深入了解"]
}

判定规则：
- is_correct=true：回答展示扎实的专业知识，逻辑清晰，内容相关
- is_correct=false：回答明显错误、答非所问、态度不端正、胡言乱语
- is_correct=null：回答过于笼统、信息不足、角色不明，或片段主要是面试官发问

所有字段必须使用中文回答。
""".strip()

    resume_context = get_resume_context()
    user_content = f"面试片段：{text}"
    if resume_context:
        user_content = f"候选人简历信息：\n{resume_context}\n\n{user_content}\n\n请结合简历信息进行分析；只有当片段中出现可识别的候选人经历陈述、技能描述或时间线信息时，才判断是否与简历一致，并指出不一致或存疑的地方。"

    def on_chunk(chunk: str):
        if callback:
            callback(chunk)

    content = deepseek_chat_stream(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        max_tokens=500,
        temperature=0.2,
        timeout=int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "12")),
        callback=on_chunk,
    )
    result = extract_json_object(content)
    questions = result.get("questions") or []
    doubts = result.get("doubts") or []
    is_correct = result.get("is_correct")
    
    return {
        "analysis": str(result.get("analysis") or "分析已生成。"),
        "is_correct": is_correct if is_correct is not None else None,
        "doubts": [str(item) for item in doubts[:5]],
        "questions": [str(item) for item in questions[:3]],
    }


def semantic_turn_decision(transcript: str, include_reply: bool) -> dict:
    reply_instruction = (
        "If complete=true, also provide a brief reply in the reply field."
        if include_reply
        else "The reply field should be empty."
    )
    system_prompt = f"""
Determine if the ASR transcript is semantically complete. Return only JSON:
{{"complete": true/false, "reason": "brief reason in 10 chars"}}
Rules: ends with "because, then, but, I think" -> false; short phrases like "yes, okay" -> true.
{reply_instruction}
""".strip()
    try:
        content = deepseek_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            max_tokens=50,
            temperature=0,
            timeout=8,
        )
        decision = extract_json_object(content)
        return {
            "complete": bool(decision.get("complete")),
            "reason": str(decision.get("reason") or ""),
            "reply": str(decision.get("reply") or ""),
        }
    except Exception as e:
        print(f"[Semantic] decision failed: {e}", flush=True)
        return {
            "complete": True,
            "reason": "Fallback: assumed complete",
            "reply": "",
        }


REPORT_DIMENSIONS = [
    "岗位匹配度",
    "表达清晰度",
    "逻辑结构",
    "经验真实性",
    "数据意识",
    "风险控制",
]


def clamp_score(value: Any, default: int = 70) -> int:
    try:
        score = int(round(float(value)))
    except Exception:
        score = default
    return max(0, min(100, score))


def format_star_rating(score: int) -> float:
    return round(max(0, min(5, score / 20)), 1)


def compact_text(value: Any, limit: int = 5000) -> str:
    text = str(value or "").strip()
    return text[:limit]


def fallback_speaker_role(text: str) -> dict:
    cleaned = re.sub(r"\s+", "", str(text or ""))
    if not cleaned:
        return {
            "role": "unknown",
            "speakerLabel": "待识别",
            "confidence": 0,
            "reason": "文本为空",
            "source": "heuristic",
        }

    question_mark = cleaned.endswith(("?", "？", "吗", "呢"))
    interviewer_cues = [
        "请你", "请问", "能不能", "可以介绍", "介绍一下", "说一下", "讲一下",
        "为什么", "怎么看", "如何", "什么原因", "你觉得", "你认为",
        "方便说", "下一个问题", "我们来看", "你的职责", "你在", "你之前",
    ]
    candidate_cues = [
        "我", "我的", "我们团队", "我们当时", "负责", "参与", "主导",
        "做过", "经历", "项目", "岗位", "当时", "后来", "主要是",
        "我认为", "我觉得", "我的理解",
    ]
    interviewer_score = int(question_mark) + sum(1 for cue in interviewer_cues if cue in cleaned)
    candidate_score = sum(1 for cue in candidate_cues if cue in cleaned)

    if len(cleaned) < 4:
        return {
            "role": "unknown",
            "speakerLabel": "待识别",
            "confidence": 0.35,
            "reason": "文本过短，暂不判断",
            "source": "heuristic",
        }
    if interviewer_score > candidate_score and interviewer_score >= 1:
        return {
            "role": "interviewer",
            "speakerLabel": "面试官",
            "confidence": min(0.85, 0.55 + interviewer_score * 0.12),
            "reason": "文本更像提问或引导语",
            "source": "heuristic",
        }
    if candidate_score >= max(1, interviewer_score + 1):
        return {
            "role": "candidate",
            "speakerLabel": "候选人",
            "confidence": min(0.85, 0.5 + candidate_score * 0.08),
            "reason": "文本更像候选人自述或回答",
            "source": "heuristic",
        }
    return {
        "role": "unknown",
        "speakerLabel": "待识别",
        "confidence": 0.4,
        "reason": "线索不足或角色混杂",
        "source": "heuristic",
    }


def classify_realtime_speaker_role(text: str, history: list | None = None) -> dict:
    text = str(text or "").strip()
    if not os.getenv("DEEPSEEK_API_KEY"):
        return fallback_speaker_role(text)

    system_prompt = """
你是实时面试转写的说话人角色分类器。场景是一对一面试，当前片段可能来自面试官、候选人，也可能因为收音混杂而无法判断。

请只返回 JSON：
{
  "role": "interviewer/candidate/unknown",
  "confidence": 0.0-1.0,
  "reason": "一句中文理由"
}

判断规则：
- 面试官：提出问题、追问、引导候选人说明、确认简历或流程。
- 候选人：回答问题、自我介绍、描述个人经历、项目、能力、结果或观点。
- unknown：文本太短、寒暄/噪声、歌词/无关测试内容、面试官和候选人混杂，或仅凭当前片段无法可靠判断。
- 不要根据回答质量判断角色，不要把所有问句都当候选人，也不要强行二选一。
""".strip()
    payload = {
        "current_text": compact_text(text, 1200),
        "recent_context": history[-8:] if isinstance(history, list) else [],
    }
    try:
        content = deepseek_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            max_tokens=180,
            temperature=0,
            timeout=int(os.getenv("ROLE_CLASSIFY_TIMEOUT_SECONDS", "6")),
        )
        result = extract_json_object(content)
        role = str(result.get("role") or "unknown").lower()
        if role not in ("interviewer", "candidate", "unknown"):
            role = "unknown"
        try:
            confidence = float(result.get("confidence"))
        except Exception:
            confidence = 0
        confidence = max(0, min(1, confidence))
        min_confidence = float(os.getenv("ROLE_CLASSIFY_MIN_CONFIDENCE", "0.45"))
        if confidence < min_confidence:
            role = "unknown"
        return {
            "role": role,
            "speakerLabel": "面试官" if role == "interviewer" else "候选人" if role == "candidate" else "待识别",
            "confidence": confidence,
            "reason": str(result.get("reason") or "AI 已完成角色判断"),
            "source": "deepseek",
        }
    except Exception as exc:
        fallback = fallback_speaker_role(text)
        fallback["reason"] = f"AI角色判断异常，已使用规则兜底：{exc}"
        fallback["source"] = "heuristic_after_error"
        return fallback


def fallback_final_assessment(snapshot: dict) -> dict:
    finals = snapshot.get("finals") or []
    analyses = snapshot.get("analyses") or []
    resume = snapshot.get("resume") if isinstance(snapshot.get("resume"), dict) else {}
    experiences = resume.get("experiences") if isinstance(resume.get("experiences"), list) else []
    skills = resume.get("skills") if isinstance(resume.get("skills"), list) else []
    candidate_name = str(resume.get("name") or "候选人").strip()
    target_role = str(
        resume.get("expect_job")
        or resume.get("work_position")
        or resume.get("current_position")
        or snapshot.get("jobTitle")
        or "目标岗位"
    ).strip()
    work_year = str(resume.get("work_year_norm") or resume.get("work_year") or "").strip()
    degree = str(resume.get("degree") or "").strip()
    college = str(resume.get("college") or "").strip()
    major = str(resume.get("major") or "").strip()
    current_company = str(resume.get("work_company") or resume.get("current_company") or "").strip()
    transcript_text = "\n".join(
        str(item.get("text") or "")
        for item in finals
        if isinstance(item, dict) and item.get("speaker") != "interviewer"
    )
    correct_count = sum(1 for item in analyses if isinstance(item, dict) and item.get("is_correct") is True)
    risk_count = sum(1 for item in analyses if isinstance(item, dict) and item.get("is_correct") is False)
    doubt_count = sum(len(item.get("doubts") or []) for item in analyses if isinstance(item, dict))
    is_demo_mode = bool(snapshot.get("demoMode"))
    work_year_number = 0.0
    work_year_match = re.search(r"\d+(?:\.\d+)?", work_year)
    if work_year_match:
        try:
            work_year_number = float(work_year_match.group(0))
        except Exception:
            work_year_number = 0.0

    base = 68
    base += min(correct_count * 4, 12)
    base -= min(risk_count * 9, 24)
    base -= min(doubt_count * 2, 18)
    if len(transcript_text) >= 220:
        base += 5
    if resume:
        base += 3
    if skills:
        base += min(len(skills), 10) // 3
    if experiences:
        base += min(len(experiences), 3)
    if not transcript_text:
        base = 45
    if is_demo_mode and transcript_text:
        demo_base = 82
        demo_base += min(correct_count, 5)
        demo_base += 2 if resume else 0
        demo_base += 2 if work_year_number >= 5 else 0
        demo_base += 1 if len(skills) >= 5 else 0
        demo_base += 1 if experiences else 0
        demo_base -= min(risk_count * 3 + max(doubt_count - 8, 0), 6)
        total_score = max(80, min(89, clamp_score(demo_base)))
    else:
        total_score = clamp_score(base)

    dimension_seed = {
        "岗位匹配度": total_score + (4 if correct_count else -3),
        "表达清晰度": total_score + (5 if len(transcript_text) >= 160 else -6),
        "逻辑结构": total_score - min(doubt_count, 10),
        "经验真实性": total_score - min(doubt_count * 2, 18),
        "数据意识": total_score + (4 if re.search(r"\d|%|百分|数据|指标|转化|留存|增长", transcript_text) else -8),
        "风险控制": total_score - min(risk_count * 10 + doubt_count, 24),
    }
    if resume:
        dimension_seed["岗位匹配度"] += 5
        dimension_seed["经验真实性"] += 3 if experiences else 0
    if is_demo_mode and transcript_text:
        has_data_signal = bool(re.search(r"\d|%|百分|数据|指标|复核|准确|流程|交付", transcript_text))
        dimension_seed = {
            "岗位匹配度": total_score + (4 if resume else 1),
            "表达清晰度": total_score + (2 if len(transcript_text) >= 220 else -2),
            "逻辑结构": total_score - 2,
            "经验真实性": total_score - (4 if doubt_count else 1),
            "数据意识": total_score + (2 if has_data_signal else -3),
            "风险控制": total_score - min(6 + risk_count * 4, 10),
        }
    dimensions = [
        {
            "name": name,
            "score": clamp_score(dimension_seed.get(name), total_score),
            "comment": "基于实时转写和阶段性 AI 分析记录自动汇总。",
        }
        for name in REPORT_DIMENSIONS
    ]

    strengths = []
    risks = []
    resume_strengths = []
    if work_year:
        resume_strengths.append(f"简历显示有{work_year}相关工作经验。")
    if target_role:
        resume_strengths.append(f"候选人经历与{target_role}方向存在直接关联。")
    if current_company:
        resume_strengths.append(f"最近工作经历来自{current_company}，可围绕职责边界继续核验。")
    if college or degree or major:
        edu_text = "、".join(item for item in [college, degree, major] if item)
        resume_strengths.append(f"教育背景：{edu_text}。")
    if skills:
        resume_strengths.append(f"技能标签较丰富，包含{'、'.join(str(item) for item in skills[:8])}。")
    for item in analyses:
        if not isinstance(item, dict):
            continue
        analysis = str(item.get("analysis") or "").strip()
        if item.get("is_correct") is True and analysis:
            strengths.append(analysis[:80])
        for doubt in item.get("doubts") or []:
            risks.append(str(doubt)[:100])

    if not transcript_text:
        risks.append("面试转写内容不足，报告仅能作为演示或初筛参考。")

    return {
        "summary": f"{candidate_name}围绕{target_role}完成了面试演示，系统已结合简历与转写生成综合评价。",
        "detailed_evaluation": (
            f"{candidate_name}的简历背景显示其目标/当前方向为{target_role}。"
            f"{'工作年限约为' + work_year + '，' if work_year else ''}"
            f"{'最近经历与' + current_company + '有关。' if current_company else ''}"
            "当前评价主要依据简历结构、模拟问答中的回答完整度、实时分析记录和存疑点数量自动汇总。"
            "正式使用时仍建议结合真实面试录音、候选人项目细节和背调结果复核。"
        ),
        "recommendation": "建议进入下一轮人工复核，重点核验简历中关键项目、数据口径和个人贡献边界。",
        "total_score": total_score,
        "star_rating": format_star_rating(total_score),
        "dimensions": dimensions,
        "strengths": (resume_strengths + strengths)[:6] or ["已完成基础回答，可继续结合岗位要求复核。"],
        "risks": risks[:8] or ["暂无明确高风险点。"],
        "follow_ups": [q for item in analyses for q in (item.get("questions") or [])][:8],
    }


def normalize_final_assessment(raw: dict, fallback: dict) -> dict:
    result = dict(fallback)
    if not isinstance(raw, dict):
        return result
    for key in ("summary", "detailed_evaluation", "recommendation"):
        if raw.get(key):
            result[key] = str(raw.get(key))
    result["total_score"] = clamp_score(raw.get("total_score"), result["total_score"])
    result["star_rating"] = float(raw.get("star_rating") or format_star_rating(result["total_score"]))

    raw_dimensions = raw.get("dimensions") or []
    dimension_map = {}
    if isinstance(raw_dimensions, list):
        for item in raw_dimensions:
            if isinstance(item, dict) and item.get("name"):
                dimension_map[str(item.get("name"))] = item
    normalized_dimensions = []
    for fallback_item in fallback["dimensions"]:
        name = fallback_item["name"]
        item = dimension_map.get(name, {})
        normalized_dimensions.append({
            "name": name,
            "score": clamp_score(item.get("score"), fallback_item["score"]),
            "comment": str(item.get("comment") or fallback_item.get("comment") or ""),
        })
    result["dimensions"] = normalized_dimensions

    for key in ("strengths", "risks", "follow_ups"):
        value = raw.get(key)
        if isinstance(value, list):
            result[key] = [str(item) for item in value if str(item).strip()][:8]
    return result


def explain_resume_term(payload: dict) -> str:
    term = str(payload.get("term") or "").strip()
    category = str(payload.get("category") or "").strip()
    context = str(payload.get("context") or "").strip()
    resume = payload.get("resume") if isinstance(payload.get("resume"), dict) else {}
    if not term:
        return "未提供需要解释的术语。"
    if not os.getenv("DEEPSEEK_API_KEY"):
        return (
            f"“{term}”是简历中的{category or '术语'}。它可用于辅助判断候选人的背景、能力或风险点。"
            "建议追问其最近一次实际应用场景、个人负责程度、结果数据和可核验材料。"
        )

    system_prompt = """
你是面试助手里的简历术语解释器。请用中文解释一个简历中的技术名词/职业标签。
要求：
- 80 到 160 字，通俗易懂；
- 结合候选人简历上下文；
- 说明它代表什么能力或风险；
- 给出 1 个适合面试官继续追问的问题；
- 不要 Markdown，不要列表编号。
""".strip()
    user_content = {
        "term": term,
        "category": category,
        "context": context,
        "resume": resume,
    }
    try:
        return deepseek_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
            ],
            max_tokens=260,
            temperature=0.2,
            timeout=int(os.getenv("TERM_EXPLAIN_TIMEOUT_SECONDS", "8")),
        ).strip()
    except Exception as exc:
        print(f"[AI] term explanation fallback: {exc}", flush=True)
        return (
            f"“{term}”通常表示候选人在该方向具备相关经历或能力。"
            "建议进一步追问其实际负责范围、使用频率、产出结果以及是否能提供具体案例。"
        )


def generate_final_assessment(snapshot: dict) -> dict:
    fallback = fallback_final_assessment(snapshot)
    if snapshot.get("demoMode"):
        return fallback
    if not os.getenv("DEEPSEEK_API_KEY"):
        return fallback

    finals = snapshot.get("finals") or []
    analyses = snapshot.get("analyses") or []
    resume = snapshot.get("resume") or {}
    transcript = "\n".join(
        f"{item.get('time', '')} {item.get('speakerLabel') or ('面试官' if item.get('speaker') == 'interviewer' else '候选人')}：{item.get('text', '')}"
        for item in finals
        if isinstance(item, dict)
    )
    analysis_lines = []
    for item in analyses:
        if not isinstance(item, dict):
            continue
        analysis_lines.append(
            json.dumps(
                {
                    "time": item.get("time"),
                    "transcript": item.get("transcript"),
                    "analysis": item.get("analysis"),
                    "is_correct": item.get("is_correct"),
                    "doubts": item.get("doubts"),
                    "questions": item.get("questions"),
                },
                ensure_ascii=False,
            )
        )

    has_analysis_records = bool(analysis_lines)
    if has_analysis_records:
        system_prompt = f"""
你是面试报告汇总专家。当前项目在面试过程中已经持续调用 AI 做了片段分析，你的任务是把这些既有 AI 分析记录汇总成最终报告，不要从全程转写重新逐句评价。
优先依据 analysis_records 中的阶段性评价、存疑点和追问建议；简历用于判断岗位匹配和经历背景；transcript 只用于补充上下文和校验角色，不作为重新分析全文的主材料。
如果既有分析记录证据不足，请写“待核验”，不要臆造结论。面试官发言只作为问题背景，不计入候选人能力评分。
必须只返回 JSON，不要 Markdown。评分维度必须正好包含以下 6 项：{", ".join(REPORT_DIMENSIONS)}。
JSON 格式：
{{
  "summary": "一句话简要评价",
  "detailed_evaluation": "面向面试官的个人详细说明，包含能力、经历可信度、表达与岗位匹配",
  "recommendation": "录用/复试/淘汰建议及理由",
  "total_score": 0-100,
  "star_rating": 0-5,
  "dimensions": [
    {{"name": "岗位匹配度", "score": 0-100, "comment": "简短说明"}}
  ],
  "strengths": ["优势"],
  "risks": ["风险或待核验点"],
  "follow_ups": ["后续追问或背调建议"]
}}
""".strip()
    else:
        system_prompt = f"""
你是严谨的面试评估专家。请根据候选人简历和全程转写，生成最终面试报告评分。
必须只返回 JSON，不要 Markdown。评分维度必须正好包含以下 6 项：{", ".join(REPORT_DIMENSIONS)}。
JSON 格式：
{{
  "summary": "一句话简要评价",
  "detailed_evaluation": "面向面试官的个人详细说明，包含能力、经历可信度、表达与岗位匹配",
  "recommendation": "录用/复试/淘汰建议及理由",
  "total_score": 0-100,
  "star_rating": 0-5,
  "dimensions": [
    {{"name": "岗位匹配度", "score": 0-100, "comment": "简短说明"}}
  ],
  "strengths": ["优势"],
  "risks": ["风险或待核验点"],
  "follow_ups": ["后续追问或背调建议"]
}}
""".strip()
    user_content = {
        "jobTitle": snapshot.get("jobTitle"),
        "interviewer": snapshot.get("interviewer"),
        "resume": resume,
        "summary_mode": "aggregate_existing_ai_analysis" if has_analysis_records else "assess_from_transcript",
        "transcript": compact_text(transcript, 2500 if has_analysis_records else 7000),
        "instruction": (
            "请汇总既有 AI 片段评价生成最终评分；只在必要时参考转写上下文。"
            if has_analysis_records
            else "请重点评估候选人的发言；面试官发言只作为问题和上下文，不计入候选人能力评分。"
        ),
        "analysis_records": compact_text("\n".join(analysis_lines), 10000),
    }
    try:
        content = deepseek_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
            ],
            max_tokens=1200,
            temperature=0.1,
            timeout=int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "12")),
        )
        return normalize_final_assessment(extract_json_object(content), fallback)
    except Exception as exc:
        print(f"[Report] final assessment fallback: {exc}", flush=True)
        return fallback


def safe_report_filename(snapshot: dict) -> str:
    resume = snapshot.get("resume") if isinstance(snapshot.get("resume"), dict) else {}
    candidate = str((resume or {}).get("name") or "candidate")
    candidate = re.sub(r'[<>:"/\\|?*\s]+', "_", candidate).strip("_") or "candidate"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"HireFlow_Report_{candidate}_{timestamp}.pdf"


def timestamp_name() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def report_root_dir() -> Path:
    directory = Path(os.getenv("REPORT_OUTPUT_DIR", r"D:\FS"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def create_interview_output_dir(timestamp: str | None = None) -> Path:
    root = report_root_dir()
    base_name = timestamp or timestamp_name()
    directory = root / base_name
    counter = 1
    while directory.exists():
        counter += 1
        directory = root / f"{base_name}_{counter:02d}"
    directory.mkdir(parents=True, exist_ok=False)
    return directory


def resolve_interview_output_dir(snapshot: dict) -> Path:
    for key in ("interview_dir", "folder_path", "output_folder"):
        value = snapshot.get(key)
        if value:
            directory = Path(str(value))
            directory.mkdir(parents=True, exist_ok=True)
            return directory

    audio_path = snapshot.get("audio_path") or ""
    if audio_path:
        parent = Path(audio_path).expanduser().resolve().parent
        root = report_root_dir().resolve()
        if parent != root:
            parent.mkdir(parents=True, exist_ok=True)
            return parent

    return create_interview_output_dir()


def move_audio_into_directory(audio_path: str, directory: Path) -> str:
    if not audio_path:
        return ""
    source = Path(audio_path)
    if not source.exists():
        return audio_path
    directory.mkdir(parents=True, exist_ok=True)
    try:
        if source.resolve().parent == directory.resolve():
            return str(source)
    except Exception:
        pass

    target = directory / source.name
    if target.exists():
        target = directory / f"{source.stem}_{timestamp_name()}{source.suffix}"
    try:
        shutil.move(str(source), str(target))
        return str(target)
    except Exception as exc:
        print(f"[AUDIO] move into interview folder failed: {exc}", flush=True)
        return str(source)


def safe_file_stem(filename: str, default: str = "resume") -> str:
    stem = Path(filename or default).stem or default
    return re.sub(r'[<>:"/\\|?*\s]+', "_", stem).strip("_") or default


def safe_file_suffix(filename: str, default: str = ".pdf") -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in (".pdf", ".doc", ".docx", ".txt", ".html", ".htm", ".rtf"):
        return suffix
    return default


def unique_path(directory: Path, filename: str) -> Path:
    path = directory / filename
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def paragraph(text: Any, style):
    from reportlab.platypus import Paragraph

    return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), style)


def star_text(rating: float) -> str:
    filled = max(0, min(5, int(round(float(rating)))))
    return "★" * filled + "☆" * (5 - filled)


def ensure_pdf_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "HireFlowCN" in pdfmetrics.getRegisteredFontNames():
        return "HireFlowCN"
    font_candidates = [
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("HireFlowCN", font_path))
            return "HireFlowCN"
    return "Helvetica"


def build_pdf_report(snapshot: dict, assessment: dict, pdf_path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Flowable, PageBreak, SimpleDocTemplate, Spacer, Table, TableStyle

    font_name = ensure_pdf_fonts()

    class RadarChart(Flowable):
        def __init__(self, dimensions: list[dict], width: int = 145 * mm, height: int = 112 * mm):
            super().__init__()
            self.dimensions = dimensions
            self.width = width
            self.height = height

        def draw(self):
            canvas = self.canv
            cx = self.width / 2
            cy = self.height / 2
            radius = min(self.width, self.height) * 0.34
            count = max(1, len(self.dimensions))
            angles = [math.pi / 2 + 2 * math.pi * index / count for index in range(count)]
            canvas.setFont(font_name, 8)
            canvas.setStrokeColor(colors.HexColor("#d7deeb"))
            for level in range(1, 6):
                points = []
                level_radius = radius * level / 5
                for angle in angles:
                    points.append((cx + math.cos(angle) * level_radius, cy + math.sin(angle) * level_radius))
                path = canvas.beginPath()
                path.moveTo(points[0][0], points[0][1])
                for x, y in points[1:]:
                    path.lineTo(x, y)
                path.close()
                canvas.drawPath(path)
            canvas.setStrokeColor(colors.HexColor("#94a3b8"))
            for angle, item in zip(angles, self.dimensions):
                x = cx + math.cos(angle) * radius
                y = cy + math.sin(angle) * radius
                canvas.line(cx, cy, x, y)
                label_x = cx + math.cos(angle) * (radius + 22)
                label_y = cy + math.sin(angle) * (radius + 18)
                canvas.drawCentredString(label_x, label_y, str(item.get("name") or ""))

            score_points = []
            for angle, item in zip(angles, self.dimensions):
                score_radius = radius * clamp_score(item.get("score")) / 100
                score_points.append((cx + math.cos(angle) * score_radius, cy + math.sin(angle) * score_radius))
            path = canvas.beginPath()
            path.moveTo(score_points[0][0], score_points[0][1])
            for x, y in score_points[1:]:
                path.lineTo(x, y)
            path.close()
            canvas.setFillColor(colors.HexColor("#dbeafe"))
            canvas.setStrokeColor(colors.HexColor("#2563eb"))
            canvas.drawPath(path, stroke=1, fill=1)
            canvas.setFillColor(colors.HexColor("#1d4ed8"))
            for x, y in score_points:
                canvas.circle(x, y, 2.4, stroke=0, fill=1)

    normal = ParagraphStyle("NormalCN", fontName=font_name, fontSize=10.5, leading=16, textColor=colors.HexColor("#172033"))
    small = ParagraphStyle("SmallCN", parent=normal, fontSize=9, leading=13, textColor=colors.HexColor("#647086"))
    title = ParagraphStyle("TitleCN", parent=normal, fontSize=22, leading=28, spaceAfter=8, textColor=colors.HexColor("#111827"))
    heading = ParagraphStyle("HeadingCN", parent=normal, fontSize=15, leading=20, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#1f2937"))
    subheading = ParagraphStyle("SubheadingCN", parent=normal, fontSize=12, leading=16, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#334155"))

    def list_block(items: list[str]):
        if not items:
            return [paragraph("暂无", small)]
        return [paragraph(f"{index + 1}. {item}", normal) for index, item in enumerate(items)]

    def add_resume_section():
        story.append(paragraph("候选人简历摘要", heading))
        if not resume:
            story.append(paragraph("未上传简历。", small))
            return

        basic_items = [
            ("姓名", resume.get("name")),
            ("电话", resume.get("phone")),
            ("邮箱", resume.get("email")),
            ("城市", resume.get("city")),
            ("学历", resume.get("degree")),
            ("学校", resume.get("college")),
            ("专业", resume.get("major")),
            ("工作年限", resume.get("work_year")),
            ("当前公司", resume.get("current_company")),
            ("当前职位", resume.get("current_position")),
            ("期望岗位", resume.get("expected_job")),
        ]
        basic_rows = [[label, str(value)] for label, value in basic_items if value]
        if basic_rows:
            basic_table = Table(basic_rows, colWidths=[28 * mm, 144 * mm])
            basic_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#647086")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(basic_table)

        if resume.get("summary"):
            story.append(paragraph("个人总结", subheading))
            story.append(paragraph(compact_resume_text(resume.get("summary"), 800), normal))

        education = resume.get("education") if isinstance(resume.get("education"), list) else []
        if education:
            story.append(paragraph("教育经历", subheading))
            for item in education[:3]:
                title_text = " / ".join(str(part) for part in [item.get("school"), item.get("major"), item.get("degree")] if part)
                story.append(paragraph(f"{title_text}  {item.get('duration') or ''}", normal))

        works = resume.get("work_experience") if isinstance(resume.get("work_experience"), list) else []
        if works:
            story.append(paragraph("工作经历", subheading))
            for item in works[:5]:
                title_text = " / ".join(str(part) for part in [item.get("company"), item.get("position"), item.get("duration")] if part)
                story.append(paragraph(title_text, normal))
                if item.get("description"):
                    story.append(paragraph(compact_resume_text(item.get("description"), 500), small))

        projects = resume.get("projects") if isinstance(resume.get("projects"), list) else []
        if projects:
            story.append(paragraph("项目经历", subheading))
            for item in projects[:4]:
                story.append(paragraph(f"{item.get('name') or '未命名项目'}  {item.get('duration') or ''}", normal))
                desc = item.get("responsibility") or item.get("description")
                if desc:
                    story.append(paragraph(compact_resume_text(desc, 450), small))

        skills = resume.get("skills") if isinstance(resume.get("skills"), list) else []
        if skills:
            story.append(paragraph("技能", subheading))
            story.append(paragraph("、".join(str(item) for item in skills[:30]), normal))

        certificates = resume.get("certificates") if isinstance(resume.get("certificates"), list) else []
        if certificates:
            story.append(paragraph("证书", subheading))
            story.append(paragraph("、".join(str(item) for item in certificates[:20]), normal))

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="HireFlow AI 面试报告",
    )
    story = []
    resume = snapshot.get("resume") if isinstance(snapshot.get("resume"), dict) else {}
    finals = snapshot.get("finals") or []
    analyses = snapshot.get("analyses") or []

    story.append(paragraph("HireFlow AI 面试报告", title))
    summary_rows = [
        ["报告类型", "演示模式" if snapshot.get("demoMode") else "正式面试", "生成方式", "真实简历 + 模拟问答" if snapshot.get("demoMode") else "实时面试记录"],
        ["岗位", snapshot.get("jobTitle") or "运营专员（平台运营方向）", "面试官", snapshot.get("interviewer") or "李明"],
        ["候选人", (resume or {}).get("name") or "未填写", "面试时长", snapshot.get("elapsedTime") or ""],
        ["开始时间", snapshot.get("startedAtText") or "", "结束时间", snapshot.get("endedAtText") or ""],
    ]
    table = Table(summary_rows, colWidths=[22 * mm, 68 * mm, 24 * mm, 58 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#647086")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#647086")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 9))
    add_resume_section()
    story.append(Spacer(1, 8))

    score_table = Table(
        [[
            paragraph(f"{assessment['total_score']} 分", ParagraphStyle("ScoreCN", parent=title, fontSize=24, textColor=colors.HexColor("#2563eb"))),
            paragraph(f"{star_text(assessment['star_rating'])}  {assessment['star_rating']}/5", ParagraphStyle("StarCN", parent=title, fontSize=16, textColor=colors.HexColor("#f59e0b"))),
            paragraph(assessment.get("recommendation") or "", normal),
        ]],
        colWidths=[34 * mm, 46 * mm, 92 * mm],
    )
    score_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#bfdbfe")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(score_table)
    story.append(paragraph(assessment.get("summary") or "", normal))
    story.append(paragraph("六维评分", heading))
    dimension_rows = [["维度", "评分", "说明"]]
    for item in assessment.get("dimensions") or []:
        dimension_rows.append([
            paragraph(item.get("name"), normal),
            paragraph(str(clamp_score(item.get("score"))), normal),
            paragraph(item.get("comment"), small),
        ])
    dimension_table = Table(dimension_rows, colWidths=[34 * mm, 20 * mm, 118 * mm])
    dimension_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(RadarChart(assessment.get("dimensions") or []))
    story.append(dimension_table)

    story.append(paragraph("个人详细说明", heading))
    story.append(paragraph(assessment.get("detailed_evaluation") or "", normal))
    story.append(paragraph("主要优势", subheading))
    story.extend(list_block(assessment.get("strengths") or []))
    story.append(paragraph("风险与待核验点", subheading))
    story.extend(list_block(assessment.get("risks") or []))
    story.append(paragraph("后续追问/背调建议", subheading))
    story.extend(list_block(assessment.get("follow_ups") or []))

    story.append(PageBreak())
    story.append(paragraph("AI 分析记录", heading))
    if analyses:
        for index, item in enumerate(analyses):
            verdict = "回答合理" if item.get("is_correct") is True else "存在风险" if item.get("is_correct") is False else "无法判定"
            story.append(paragraph(f"#{index + 1}  {item.get('time', '')}  {verdict}", small))
            story.append(paragraph(item.get("analysis") or "", normal))
            doubts = item.get("doubts") or []
            questions = item.get("questions") or []
            if doubts:
                story.append(paragraph("存疑点：" + "；".join(str(doubt) for doubt in doubts), small))
            if questions:
                story.append(paragraph("建议追问：" + "；".join(str(question) for question in questions), small))
            story.append(Spacer(1, 7))
    else:
        story.append(paragraph("暂无 AI 分析记录。", small))

    def on_page(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, f"第 {doc_obj.page} 页")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def create_final_report(snapshot: dict, calibrated: dict | None = None) -> dict:
    output_dir = resolve_interview_output_dir(snapshot)
    audio_path = "" if snapshot.get("demoMode") else move_audio_into_directory(snapshot.get("audio_path") or "", output_dir)
    snapshot = {**snapshot, "audio_path": audio_path, "interview_dir": str(output_dir)}
    if snapshot.get("demoMode"):
        calibrated = None
    if calibrated is None:
        calibrated = create_calibrated_transcript(snapshot, output_dir)
    if calibrated.get("finals"):
        snapshot = {**snapshot, "finals": calibrated["finals"], "calibration": calibrated}
    assessment = generate_final_assessment(snapshot)
    pdf_path = output_dir / safe_report_filename(snapshot)
    build_pdf_report(snapshot, assessment, pdf_path)
    return {
        "folder_path": str(output_dir),
        "pdf_path": str(pdf_path),
        "audio_path": audio_path or "",
        "transcript_path": calibrated.get("transcript_path", ""),
        "realtime_transcript_path": calibrated.get("realtime_transcript_path", ""),
        "diarization_path": calibrated.get("diarization_path", ""),
        "diarization_error_path": calibrated.get("diarization_error_path", ""),
        "calibration_reason": calibrated.get("reason", ""),
        "diarization_status": calibrated.get("status") or (
            "done" if calibrated.get("speaker_calibrated") else "failed"
        ),
        "speaker_calibrated": bool(calibrated.get("speaker_calibrated")),
        "assessment": assessment,
    }


def output_dir() -> Path:
    return report_root_dir()


def speaker_label_from_value(value: Any) -> str:
    text = str(value or "").lower()
    if text in ("interviewer", "hr", "面试官"):
        return "面试官"
    if text in ("candidate", "面试者", "候选人"):
        return "候选人"
    if text.startswith("speaker"):
        return text.replace("speaker", "说话人 ")
    return str(value or "候选人")


def normalize_speaker_role(value: Any) -> str:
    text = str(value or "").lower()
    if text in ("interviewer", "hr", "面试官"):
        return "interviewer"
    return "candidate"


def collect_utterances(payload: Any) -> list[dict]:
    utterances: list[dict] = []
    if isinstance(payload, dict):
        for item in payload.get("utterances") or []:
            if isinstance(item, dict):
                utterances.append(item)
        result = payload.get("result")
        if isinstance(result, dict):
            for item in result.get("utterances") or []:
                if isinstance(item, dict):
                    utterances.append(item)
        elif isinstance(result, list):
            for result_item in result:
                if isinstance(result_item, dict):
                    for item in result_item.get("utterances") or []:
                        if isinstance(item, dict):
                            utterances.append(item)
    return utterances


def result_text_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    result = payload.get("result")
    if isinstance(result, dict):
        return str(result.get("text") or "")
    if isinstance(result, list):
        return "".join(str(item.get("text") or "") for item in result if isinstance(item, dict))
    return str(payload.get("text") or "")


def diarization_empty_reason(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "diarization returned no utterances"
    result = payload.get("result")
    text = ""
    if isinstance(result, dict):
        text = str(result.get("text") or "").strip()
    elif isinstance(payload.get("text"), str):
        text = str(payload.get("text") or "").strip()
    if not text:
        duration = ""
        audio_info = payload.get("audio_info")
        if isinstance(audio_info, dict) and audio_info.get("duration") is not None:
            duration = f"，音频时长 {audio_info.get('duration')}ms"
            if audio_info.get("segment_count"):
                duration += f"，已分为 {audio_info.get('segment_count')} 段并发识别"
        errors = payload.get("segment_errors")
        if isinstance(errors, list) and errors:
            return f"豆包分段识别未返回有效文本，失败片段数 {len(errors)}，首个错误：{errors[0].get('error')}"
        return f"豆包文件识别未识别到有效文本{duration}，通常是录音过短、音量过低、静音或测试内容太少"
    return "diarization returned text but no utterance segments"


def extract_speaker_value(utterance: dict) -> Any:
    for key in ("speaker", "speaker_id", "speakerId", "speaker_id_str"):
        if key in utterance:
            return utterance.get(key)
    additions = utterance.get("additions")
    if isinstance(additions, dict):
        for key in ("speaker", "speaker_id", "speakerId", "speaker_id_str"):
            if key in additions:
                return additions.get(key)
    speaker_info = utterance.get("speaker_info") or utterance.get("speakerInfo")
    if isinstance(speaker_info, dict):
        for key in ("speaker", "speaker_id", "speakerId", "id"):
            if key in speaker_info:
                return speaker_info.get(key)
    return ""


def classify_speaker_roles(utterances: list[dict]) -> dict[str, str]:
    speaker_totals: dict[str, int] = {}
    for item in utterances:
        speaker = str(extract_speaker_value(item) or "speaker_0")
        text = str(item.get("text") or "")
        speaker_totals[speaker] = speaker_totals.get(speaker, 0) + len(text)
    if not speaker_totals:
        return {}
    # In interviews the candidate usually talks more. Keep this as a transparent heuristic.
    candidate_speaker = max(speaker_totals.items(), key=lambda pair: pair[1])[0]
    return {
        speaker: "candidate" if speaker == candidate_speaker else "interviewer"
        for speaker in speaker_totals
    }


def make_file_headers(resource_id: str) -> dict[str, str]:
    load_dotenv()
    app_key = (
        os.getenv("DOUBAO_FILE_APP_ID")
        or os.getenv("DOUBAO_FILE_APP_KEY")
        or os.getenv("DOUBAO_APP_ID")
        or os.getenv("DOUBAO_APP_KEY")
        or os.getenv("VOLC_APP_ID")
        or os.getenv("VOLC_APP_KEY")
    )
    access_key = (
        os.getenv("DOUBAO_FILE_ACCESS_TOKEN")
        or os.getenv("DOUBAO_FILE_ACCESS_KEY")
        or os.getenv("DOUBAO_ACCESS_TOKEN")
        or os.getenv("DOUBAO_ACCESS_KEY")
        or os.getenv("VOLC_ACCESS_TOKEN")
        or os.getenv("VOLC_ACCESS_KEY")
    )
    missing = []
    if not app_key:
        missing.append("DOUBAO_FILE_APP_ID or DOUBAO_APP_ID")
    if not access_key:
        missing.append("DOUBAO_FILE_ACCESS_TOKEN or DOUBAO_ACCESS_TOKEN")
    if missing:
        raise RuntimeError(f"missing environment variables: {', '.join(missing)}")
    return {
        "X-Api-App-Key": app_key,
        "X-Api-Access-Key": access_key,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }


def call_doubao_file_diarization(audio_path: str) -> dict:
    api_key_headers = make_file_headers(os.getenv("DOUBAO_FILE_RESOURCE_ID", "volc.bigasr.auc_turbo"))
    endpoint = os.getenv(
        "DOUBAO_FILE_RECOGNIZE_URL",
        "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash",
    )
    with open(audio_path, "rb") as audio_file:
        audio_b64 = base64.b64encode(audio_file.read()).decode("ascii")
    request_id = str(uuid.uuid4())
    payload = {
        "user": {"uid": request_id},
        "audio": {
            "data": audio_b64,
            "format": Path(audio_path).suffix.lstrip(".") or "wav",
            "rate": 16000,
            "bits": 16,
            "channel": 1,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "show_utterances": True,
            "enable_speaker_info": True,
        },
    }
    headers = {
        **api_key_headers,
        "X-Api-Request-Id": request_id,
        "X-Api-Sequence": "-1",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=int(os.getenv("DOUBAO_FILE_TIMEOUT_SECONDS", "300"))) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Doubao file diarization HTTP {exc.code}: {detail or exc.reason}"
        ) from exc


def wav_duration_ms(audio_path: str) -> int:
    with wave.open(str(audio_path), "rb") as reader:
        frame_rate = reader.getframerate() or 16000
        return int(reader.getnframes() * 1000 / frame_rate)


def split_wav_for_diarization(audio_path: str, directory: Path, timestamp: str, segment_seconds: int) -> list[dict]:
    chunks_dir = directory / f"HireFlow_Diarization_Chunks_{timestamp}"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    with wave.open(str(audio_path), "rb") as reader:
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        frame_rate = reader.getframerate()
        total_frames = reader.getnframes()
        frames_per_segment = max(frame_rate, int(frame_rate * segment_seconds))
        offset_frames = 0
        index = 0
        while offset_frames < total_frames:
            frames_to_read = min(frames_per_segment, total_frames - offset_frames)
            frames = reader.readframes(frames_to_read)
            if not frames:
                break
            chunk_path = chunks_dir / f"segment_{index + 1:03d}.wav"
            with wave.open(str(chunk_path), "wb") as writer:
                writer.setnchannels(channels)
                writer.setsampwidth(sample_width)
                writer.setframerate(frame_rate)
                writer.writeframes(frames)
            chunks.append({
                "index": index,
                "path": str(chunk_path),
                "offset_ms": int(offset_frames * 1000 / frame_rate),
                "duration_ms": int(frames_to_read * 1000 / frame_rate),
            })
            offset_frames += frames_to_read
            index += 1
    return chunks


def offset_time_value(value: Any, offset_ms: int) -> Any:
    if value is None:
        return value
    try:
        return int(float(value)) + offset_ms
    except Exception:
        return value


def offset_utterance_times(utterance: dict, offset_ms: int, segment_index: int) -> dict:
    item = dict(utterance)
    for key in ("start_time", "startTime", "start"):
        if key in item:
            item[key] = offset_time_value(item.get(key), offset_ms)
    for key in ("end_time", "endTime", "end"):
        if key in item:
            item[key] = offset_time_value(item.get(key), offset_ms)
    words = item.get("words")
    if isinstance(words, list):
        shifted_words = []
        for word in words:
            if not isinstance(word, dict):
                shifted_words.append(word)
                continue
            shifted = dict(word)
            for key in ("start_time", "startTime", "start"):
                if key in shifted:
                    shifted[key] = offset_time_value(shifted.get(key), offset_ms)
            for key in ("end_time", "endTime", "end"):
                if key in shifted:
                    shifted[key] = offset_time_value(shifted.get(key), offset_ms)
            shifted_words.append(shifted)
        item["words"] = shifted_words
    item["segment_index"] = segment_index
    item["segment_offset_ms"] = offset_ms
    return item


def diarization_plan(duration_ms: int) -> tuple[int, int]:
    minutes = max(1, math.ceil(duration_ms / 60000))
    min_segment = max(60, int(os.getenv("DOUBAO_FILE_MIN_SEGMENT_SECONDS", "180")))
    max_segment = max(min_segment, int(os.getenv("DOUBAO_FILE_MAX_SEGMENT_SECONDS", "600")))
    max_workers_cap = max(1, int(os.getenv("DOUBAO_FILE_MAX_WORKERS", "6")))

    if duration_ms <= 10 * 60 * 1000:
        return min(max_segment, 600), 1
    if duration_ms <= 30 * 60 * 1000:
        return 300, min(2, max_workers_cap)
    if duration_ms <= 60 * 60 * 1000:
        return 240, min(4, max_workers_cap)
    return min_segment, min(max(4, math.ceil(minutes / 15)), max_workers_cap)


def call_doubao_file_diarization_segmented(audio_path: str, directory: Path, timestamp: str) -> dict:
    duration_ms = wav_duration_ms(audio_path)
    configured_segment = int(os.getenv("DOUBAO_FILE_SEGMENT_SECONDS", "0"))
    configured_workers = int(os.getenv("DOUBAO_FILE_WORKERS", "0"))
    auto_segment, auto_workers = diarization_plan(duration_ms)
    segment_seconds = configured_segment if configured_segment > 0 else auto_segment
    max_workers = configured_workers if configured_workers > 0 else auto_workers
    if segment_seconds <= 0 or duration_ms <= segment_seconds * 1000:
        result = call_doubao_file_diarization(audio_path)
        result.setdefault("segmented", False)
        result.setdefault("diarization_plan", {
            "duration_ms": duration_ms,
            "segment_seconds": segment_seconds,
            "max_workers": 1,
            "mode": "single",
        })
        return result

    chunks = split_wav_for_diarization(audio_path, directory, timestamp, segment_seconds)
    keep_segments = os.getenv("DOUBAO_FILE_KEEP_SEGMENTS", "false").lower() in ("1", "true", "yes")
    segment_results = []
    segment_errors = []

    def run_chunk(chunk: dict) -> dict:
        payload = call_doubao_file_diarization(chunk["path"])
        utterances = [
            offset_utterance_times(item, int(chunk["offset_ms"]), int(chunk["index"]))
            for item in collect_utterances(payload)
        ]
        return {
            "index": chunk["index"],
            "offset_ms": chunk["offset_ms"],
            "duration_ms": chunk["duration_ms"],
            "text": result_text_from_payload(payload),
            "utterances": utterances,
            "payload": payload,
        }

    try:
        with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(chunks)))) as executor:
            future_map = {executor.submit(run_chunk, chunk): chunk for chunk in chunks}
            for future in as_completed(future_map):
                chunk = future_map[future]
                try:
                    segment_results.append(future.result())
                except Exception as exc:
                    segment_errors.append({
                        "index": chunk["index"],
                        "offset_ms": chunk["offset_ms"],
                        "duration_ms": chunk["duration_ms"],
                        "error": str(exc),
                    })
    finally:
        if not keep_segments:
            for chunk in chunks:
                try:
                    Path(chunk["path"]).unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                chunk_dir = directory / f"HireFlow_Diarization_Chunks_{timestamp}"
                chunk_dir.rmdir()
            except Exception:
                pass

    segment_results.sort(key=lambda item: item["index"])
    merged_utterances = []
    merged_text = []
    for item in segment_results:
        if item.get("text"):
            merged_text.append(str(item.get("text") or ""))
        merged_utterances.extend(item.get("utterances") or [])

    return {
        "segmented": True,
        "diarization_plan": {
            "duration_ms": duration_ms,
            "segment_seconds": segment_seconds,
            "max_workers": max_workers,
            "mode": "segmented",
        },
        "segment_seconds": segment_seconds,
        "max_workers": max_workers,
        "audio_info": {
            "duration": duration_ms,
            "segment_count": len(chunks),
        },
        "result": {
            "text": "".join(merged_text),
            "utterances": merged_utterances,
            "additions": {"duration": str(duration_ms)},
        },
        "segments": [
            {
                "index": item["index"],
                "offset_ms": item["offset_ms"],
                "duration_ms": item["duration_ms"],
                "text": item.get("text", ""),
                "utterance_count": len(item.get("utterances") or []),
                "payload": item.get("payload"),
            }
            for item in segment_results
        ],
        "segment_errors": segment_errors,
    }


def write_transcript_file(finals: list[dict], path: Path) -> None:
    lines = []
    for index, item in enumerate(finals):
        role = item.get("speakerLabel") or ("面试官" if item.get("speaker") == "interviewer" else "候选人")
        timestamp = item.get("time") or ""
        lines.append(f"{index + 1}. [{timestamp}] {role}：{item.get('text') or ''}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_realtime_transcript_file(finals: list[dict], path: Path) -> None:
    lines = []
    for index, item in enumerate(finals):
        timestamp = item.get("time") or ""
        lines.append(f"{index + 1}. [{timestamp}] {item.get('text') or ''}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_diarization_error_file(path: Path, reason: str, audio_path: str) -> None:
    content = [
        "豆包说话人分离未完成。",
        f"原因：{reason}",
        f"音频文件：{audio_path or '未找到'}",
        "",
        "说明：未生成 HireFlow_Transcript_*.txt，避免把实时转写误标为已区分说话人的文本。",
        "请检查豆包文件识别接口配置、音频文件大小和接口返回错误后重新生成报告。",
    ]
    path.write_text("\n".join(content) + "\n", encoding="utf-8")


def diarization_failure_result(
    realtime_finals: list[dict],
    raw_transcript_path: Path,
    error_path: Path,
    reason: str,
    audio_path: str,
    diarization_path: Path | None = None,
) -> dict:
    write_realtime_transcript_file(realtime_finals, raw_transcript_path)
    write_diarization_error_file(error_path, reason, audio_path)
    return {
        "speaker_calibrated": False,
        "finals": realtime_finals,
        "transcript_path": "",
        "realtime_transcript_path": str(raw_transcript_path),
        "diarization_path": str(diarization_path) if diarization_path and diarization_path.exists() else "",
        "diarization_error_path": str(error_path),
        "reason": reason,
    }


def create_calibrated_transcript(snapshot: dict, directory: Path) -> dict:
    audio_path = snapshot.get("audio_path") or ""
    realtime_finals = snapshot.get("finals") if isinstance(snapshot.get("finals"), list) else []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    transcript_path = directory / f"HireFlow_Transcript_{timestamp}.txt"
    raw_transcript_path = Path(
        snapshot.get("realtime_transcript_path") or directory / f"HireFlow_RealtimeTranscript_{timestamp}.txt"
    )
    diarization_path = directory / f"HireFlow_Diarization_{timestamp}.json"
    error_path = directory / f"HireFlow_Diarization_Error_{timestamp}.txt"

    if snapshot.get("demoMode"):
        write_realtime_transcript_file(realtime_finals, raw_transcript_path)
        write_transcript_file(realtime_finals, transcript_path)
        return {
            "speaker_calibrated": True,
            "finals": realtime_finals,
            "transcript_path": str(transcript_path),
            "realtime_transcript_path": str(raw_transcript_path),
            "diarization_path": "",
            "diarization_error_path": "",
            "reason": "demo mode uses preset speaker roles",
            "status": "done",
        }

    if not audio_path or not Path(audio_path).exists():
        return diarization_failure_result(
            realtime_finals,
            raw_transcript_path,
            error_path,
            "audio file unavailable; saved realtime transcript",
            audio_path,
        )

    try:
        diarization = call_doubao_file_diarization_segmented(audio_path, directory, timestamp)
        diarization_path.write_text(json.dumps(diarization, ensure_ascii=False, indent=2), encoding="utf-8")
        utterances = collect_utterances(diarization)
        role_map = classify_speaker_roles(utterances)
        calibrated_finals = []
        for index, utterance in enumerate(utterances):
            text = str(utterance.get("text") or "").strip()
            if not text:
                continue
            speaker_value = str(extract_speaker_value(utterance) or f"speaker_{index}")
            role = role_map.get(speaker_value, "candidate")
            start_ms = utterance.get("start_time") or utterance.get("startTime") or utterance.get("start")
            seconds = 0
            try:
                seconds = int(float(start_ms) / 1000)
            except Exception:
                pass
            calibrated_finals.append({
                "id": f"calibrated-{index}",
                "text": text,
                "speaker": role,
                "speakerLabel": "候选人" if role == "candidate" else "面试官",
                "rawSpeaker": speaker_value,
                "time": f"{seconds // 60:02d}:{seconds % 60:02d}",
                "pending": False,
            })
        if calibrated_finals:
            write_transcript_file(calibrated_finals, transcript_path)
            return {
                "speaker_calibrated": True,
                "finals": calibrated_finals,
                "transcript_path": str(transcript_path),
                "diarization_path": str(diarization_path),
                "role_map": role_map,
            }
        return diarization_failure_result(
            realtime_finals,
            raw_transcript_path,
            error_path,
            diarization_empty_reason(diarization),
            audio_path,
            diarization_path,
        )
    except Exception as exc:
        print(f"[Report] diarization failed, using realtime transcript: {exc}", flush=True)
        return diarization_failure_result(
            realtime_finals,
            raw_transcript_path,
            error_path,
            str(exc),
            audio_path,
        )


def dist_file_for(path: str) -> Path | None:
    dist_dir = Path(__file__).with_name("dist").resolve()
    if not dist_dir.exists():
        return None
    rel_path = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
    target = (dist_dir / rel_path).resolve()
    if target != dist_dir and dist_dir not in target.parents:
        return None
    if target.is_file():
        return target
    return None


class WsServer:
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA

    def __init__(self, host: str, port: int, session: "DoubaoSession"):
        self.host = host
        self.port = port
        self.session = session
        self.server_socket: socket.socket | None = None
        self.running = False

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(128)
        self.running = True
        threading.Thread(target=self.accept_loop, daemon=True).start()
        print(f"[WS] listening on ws://{self.host}:{self.port}", flush=True)

    def stop(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

    def accept_loop(self):
        while self.running:
            try:
                ready = select.select([self.server_socket], [], [], 1.0)
                if not ready[0]:
                    continue
                client, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client, addr), daemon=True).start()
            except Exception as exc:
                if self.running:
                    print(f"[WS] accept error: {exc}", flush=True)

    def handle_client(self, client: socket.socket, addr):
        try:
            self.do_handshake(client)
            self.session.register_ws_client(client)
            self.session.broadcast_event(
                {"type": "status", "message": "WebSocket connected."},
            )
            buffer = bytearray()
            audio_count = 0

            def recv_fn(size: int) -> bytes:
                while len(buffer) < size:
                    chunk = client.recv(max(size, 4096))
                    if not chunk:
                        raise ConnectionError("closed")
                    buffer.extend(chunk)
                result = bytes(buffer[:size])
                del buffer[:size]
                return result

            while self.running:
                opcode, payload = self.read_frame(recv_fn)
                if opcode is None:
                    break
                if opcode == self.TEXT:
                    print(f"[WS] text: {payload.decode('utf-8', errors='replace')[:200]}", flush=True)
                elif opcode == self.BINARY:
                    audio_count += 1
                    if audio_count % 50 == 0:
                        print(f"[WS] audio #{audio_count}, {len(payload)} bytes", flush=True)
                    if payload:
                        self.session.send_audio(payload)
                elif opcode == self.CLOSE:
                    break
                elif opcode == self.PING:
                    self.send_frame(client, self.PONG, payload)

        except Exception as exc:
            if "missing Sec-WebSocket-Key" not in str(exc):
                print(f"[WS] client error: {type(exc).__name__}: {exc}", flush=True)
        finally:
            self.session.unregister_ws_client(client)
            try:
                client.close()
            except Exception:
                pass

    def do_handshake(self, client: socket.socket):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = client.recv(4096)
            if not chunk:
                raise ConnectionError("closed during handshake")
            data += chunk
        request_line, *header_lines = data.decode("utf-8", errors="replace").split("\r\n")
        headers = {}
        for line in header_lines:
            if ": " in line:
                key, value = line.split(": ", 1)
                headers[key.lower()] = value
        key = headers.get("sec-websocket-key")
        if not key:
            raise ValueError("missing Sec-WebSocket-Key")
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        client.sendall(response.encode("ascii"))

    def read_frame(self, recv_fn: Callable[[int], bytes]) -> tuple[int | None, bytes]:
        first = recv_fn(2)
        if len(first) < 2:
            return None, b""
        fin = (first[0] >> 7) & 1
        opcode = first[0] & 0x0F
        masked = (first[1] >> 7) & 1
        length = first[1] & 0x7F
        if length == 126:
            length = int.from_bytes(recv_fn(2), "big")
        elif length == 127:
            length = int.from_bytes(recv_fn(8), "big")
        mask = recv_fn(4) if masked else b""
        payload = recv_fn(length) if length else b""
        if masked and payload:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def send_frame(self, client: socket.socket, opcode: int, payload: bytes):
        header = bytearray()
        header.append(0x80 | (opcode & 0x0F))
        length = len(payload)
        if length < 126:
            header.append(length)
        elif length < 65536:
            header.extend([126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            header.extend([127])
            header.extend(struct.pack("!Q", length))
        client.sendall(header + payload)

    def broadcast_frame(self, opcode: int, payload: bytes):
        frame = bytearray()
        frame.append(0x80 | (opcode & 0x0F))
        length = len(payload)
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.extend([126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            frame.extend([127])
            frame.extend(struct.pack("!Q", length))
        frame.extend(payload)
        frame = bytes(frame)
        for client in list(self.session.ws_clients):
            try:
                client.sendall(frame)
            except Exception:
                self.session.unregister_ws_client(client)

    def broadcast_event(self, event: dict):
        payload = json.dumps(event, ensure_ascii=False).encode("utf-8")
        self.broadcast_frame(WsServer.TEXT, payload)


WS_OPCODE_BINARY = 0x2


class DoubaoSession:
    def __init__(self, resource_id: str, end_window_size: int, ws_server_instance: WsServer):
        self.resource_id = resource_id
        self.end_window_size = end_window_size
        self.ws_server = ws_server_instance
        self.ws = None
        self.lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.running = False
        self.receiver = None
        self.events: list[dict] = []
        self.event_lock = threading.Lock()
        self.event_id = 0
        self.partial = ""
        self.seen_finals: set[tuple[int | None, int | None, str]] = set()
        self.turn_buffer: list[str] = []
        self.turn_version = 0
        self.semantic_final_enabled = True
        self.fast_mode = os.getenv("ASR_MODE", "fast").lower() == "fast"
        self.ws_clients: set[socket.socket] = set()
        self.ws_client_lock = threading.Lock()
        self.audio_lock = threading.Lock()
        self.wav_writer = None
        self.audio_path = ""
        self.interview_dir = ""
        self.realtime_transcript_path = ""
        self.pending_resume_file: dict[str, Any] | None = None
        self.resume_file_path = ""
        self.resume_parsed_path = ""
        self.resume_lock = threading.Lock()
        self.realtime_transcript_lock = threading.Lock()
        self.realtime_finals: list[dict] = []
        self.realtime_index = 0
        self.diarization_lock = threading.Lock()
        self.diarization_thread = None
        self.diarization_running = False
        self.diarization_result = None
        print(f"[ASR] Mode: {'FAST (no semantic check)' if self.fast_mode else 'SMART (with semantic check)'}", flush=True)

    def register_ws_client(self, client: socket.socket):
        with self.ws_client_lock:
            self.ws_clients.add(client)

    def unregister_ws_client(self, client: socket.socket):
        with self.ws_client_lock:
            self.ws_clients.discard(client)

    def add_event(self, event_type: str, **payload):
        with self.event_lock:
            self.event_id += 1
            event = {"id": self.event_id, "type": event_type, **payload}
            self.events.append(event)
            self.events = self.events[-200:]

        self.ws_server.broadcast_event(event)
        if event_type == "final":
            print(f"final: {payload.get('text', '')}", flush=True)
        elif event_type == "error":
            print(f"error: {payload.get('message', '')}", flush=True)

    def broadcast_event(self, event: dict):
        payload = json.dumps(event, ensure_ascii=False).encode("utf-8")
        self.ws_server.broadcast_frame(WsServer.TEXT, payload)

    def start(self):
        self.stop(close_audio=True)
        self.start_audio_recording()
        self.connect_upstream(reset_state=True)

    def start_audio_recording(self):
        directory = create_interview_output_dir()
        path = directory / f"HireFlow_Audio_{directory.name}.wav"
        realtime_path = directory / f"HireFlow_RealtimeTranscript_{directory.name}.txt"
        writer = wave.open(str(path), "wb")
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16000)
        realtime_path.write_text("", encoding="utf-8")
        with self.audio_lock:
            self.wav_writer = writer
            self.audio_path = str(path)
            self.interview_dir = str(directory)
            self.realtime_transcript_path = str(realtime_path)
        with self.realtime_transcript_lock:
            self.realtime_finals = []
            self.realtime_index = 0
        with self.diarization_lock:
            self.diarization_thread = None
            self.diarization_running = False
            self.diarization_result = None
        self.flush_pending_resume_file(directory)
        print(f"[AUDIO] recording to {path}", flush=True)
        self.add_event("status", message=f"Recording audio to {path}")

    def write_audio(self, audio: bytes):
        with self.audio_lock:
            writer = self.wav_writer
        if not writer:
            return
        try:
            writer.writeframes(audio)
        except Exception as exc:
            print(f"[AUDIO] local write failed: {exc}", flush=True)

    def close_audio_recording(self):
        with self.audio_lock:
            writer = self.wav_writer
            self.wav_writer = None
        if writer:
            try:
                writer.close()
                print(f"[AUDIO] saved {self.audio_path}", flush=True)
            except Exception as exc:
                print(f"[AUDIO] close failed: {exc}", flush=True)
            self.start_background_diarization()

    def record_realtime_sentence(self, text: str):
        cleaned = str(text or "").strip()
        if not cleaned:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self.realtime_transcript_lock:
            self.realtime_index += 1
            entry = {
                "id": f"realtime-{self.realtime_index}",
                "text": cleaned,
                "speaker": "unknown",
                "speakerLabel": "待识别",
                "time": timestamp,
                "pending": False,
            }
            self.realtime_finals.append(entry)
            path = self.realtime_transcript_path
            index = self.realtime_index
        if path:
            try:
                with open(path, "a", encoding="utf-8") as file:
                    file.write(f"{index}. [{timestamp}] {cleaned}\n")
            except Exception as exc:
                print(f"[TRANSCRIPT] realtime write failed: {exc}", flush=True)

    def realtime_finals_snapshot(self) -> list[dict]:
        with self.realtime_transcript_lock:
            return [dict(item) for item in self.realtime_finals]

    def store_resume_file(self, filename: str, file_data: bytes, parsed_resume: dict | None = None) -> dict:
        with self.resume_lock:
            if self.interview_dir:
                return self._write_resume_file(Path(self.interview_dir), filename, file_data, parsed_resume)
            self.pending_resume_file = {
                "filename": filename,
                "file_data": file_data,
                "parsed_resume": parsed_resume or {},
            }
            self.resume_file_path = ""
            self.resume_parsed_path = ""
            return {"resume_file_path": "", "resume_parsed_path": "", "pending": True}

    def flush_pending_resume_file(self, directory: Path):
        with self.resume_lock:
            pending = self.pending_resume_file
            self.pending_resume_file = None
        if pending:
            self._write_resume_file(
                directory,
                str(pending.get("filename") or "resume.pdf"),
                pending.get("file_data") or b"",
                pending.get("parsed_resume") or {},
            )

    def _write_resume_file(self, directory: Path, filename: str, file_data: bytes, parsed_resume: dict | None = None) -> dict:
        directory.mkdir(parents=True, exist_ok=True)
        suffix = safe_file_suffix(filename)
        stem = safe_file_stem(filename, "resume")
        resume_path = unique_path(directory, f"HireFlow_Resume_{stem}{suffix}")
        resume_path.write_bytes(file_data)
        parsed_path = unique_path(directory, f"HireFlow_Resume_Parsed_{stem}.json")
        parsed_path.write_text(json.dumps(parsed_resume or {}, ensure_ascii=False, indent=2), encoding="utf-8")
        with self.resume_lock:
            self.resume_file_path = str(resume_path)
            self.resume_parsed_path = str(parsed_path)
        return {
            "resume_file_path": str(resume_path),
            "resume_parsed_path": str(parsed_path),
            "pending": False,
        }

    def clear_resume_file_state(self):
        with self.resume_lock:
            self.pending_resume_file = None
            self.resume_file_path = ""
            self.resume_parsed_path = ""

    def speaker_diarization_placeholder(self, reason: str = "speaker diarization is running in background") -> dict:
        return {
            "speaker_calibrated": False,
            "finals": self.realtime_finals_snapshot(),
            "transcript_path": "",
            "realtime_transcript_path": self.realtime_transcript_path,
            "diarization_path": "",
            "diarization_error_path": "",
            "reason": reason,
            "status": "running",
        }

    def start_background_diarization(self):
        with self.diarization_lock:
            if self.diarization_running or self.diarization_result:
                return
            audio_path = self.audio_path
            interview_dir = self.interview_dir
            realtime_transcript_path = self.realtime_transcript_path
            finals = self.realtime_finals_snapshot()
            if not audio_path or not interview_dir:
                return
            self.diarization_running = True

        def worker():
            try:
                result = create_calibrated_transcript(
                    {
                        "audio_path": audio_path,
                        "finals": finals,
                        "realtime_transcript_path": realtime_transcript_path,
                    },
                    Path(interview_dir),
                )
            except Exception as exc:
                print(f"[Report] background diarization crashed: {exc}", flush=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                result = diarization_failure_result(
                    finals,
                    Path(realtime_transcript_path) if realtime_transcript_path else Path(interview_dir) / f"HireFlow_RealtimeTranscript_{timestamp}.txt",
                    Path(interview_dir) / f"HireFlow_Diarization_Error_{timestamp}.txt",
                    str(exc),
                    audio_path,
                )
            with self.diarization_lock:
                self.diarization_result = result
                self.diarization_running = False
            if result.get("speaker_calibrated"):
                self.add_event("status", message=f"Speaker diarization completed: {result.get('transcript_path')}")
            else:
                self.add_event("status", message=f"Speaker diarization failed: {result.get('reason')}")

        thread = threading.Thread(target=worker, daemon=True)
        with self.diarization_lock:
            self.diarization_thread = thread
        thread.start()

    def get_background_diarization_result(self, wait_seconds: float = 0) -> dict | None:
        thread = None
        with self.diarization_lock:
            result = self.diarization_result
            running = self.diarization_running
            thread = self.diarization_thread
        if result:
            return result
        if thread and running and wait_seconds > 0:
            thread.join(wait_seconds)
            with self.diarization_lock:
                if self.diarization_result:
                    return self.diarization_result
                running = self.diarization_running
        if running:
            return self.speaker_diarization_placeholder()
        return None

    def connect_upstream(self, reset_state: bool):
        headers = [f"{key}: {value}" for key, value in make_headers(self.resource_id).items()]
        import websocket as ws_module
        ws = ws_module.create_connection(URL, header=headers, timeout=15)
        ws.settimeout(None)
        with self.send_lock:
            ws.send(build_full_client_request(self.end_window_size, None), opcode=WS_OPCODE_BINARY)
        with self.lock:
            self.ws = ws
            self.running = True
            if reset_state:
                self.partial = ""
                self.seen_finals.clear()
                self.turn_buffer.clear()
            self.turn_version += 1
        self.add_event("status", message="Doubao ASR connected, ready to speak.")
        self.receiver = threading.Thread(target=self.receive_loop, daemon=True)
        self.receiver.start()

    def send_audio(self, audio: bytes):
        if not audio:
            return
        self.write_audio(audio)
        with self.lock:
            ws = self.ws
            running = self.running
        if not ws or not running:
            try:
                print("[ASR] upstream inactive, reconnecting before audio send", flush=True)
                self.connect_upstream(reset_state=False)
            except Exception as exc:
                self.add_event("error", message=f"ASR reconnect failed: {exc}")
                return
            with self.lock:
                ws = self.ws
                running = self.running
        if not ws or not running:
            return
        try:
            with self.send_lock:
                ws.send(build_audio_request(audio), opcode=WS_OPCODE_BINARY)
        except Exception as exc:
            with self.lock:
                if self.ws is ws:
                    self.running = False
                    self.ws = None
            try:
                ws.close()
            except Exception:
                pass
            print(f"[AUDIO] upstream send closed, will reconnect on next audio: {type(exc).__name__}: {exc}", flush=True)

    def stop(self, close_audio: bool = True):
        with self.lock:
            ws = self.ws
            self.running = False
            self.ws = None
        if ws:
            try:
                with self.send_lock:
                    ws.send(build_audio_request(b"", is_last=True), opcode=WS_OPCODE_BINARY)
            except Exception:
                pass
            try:
                ws.close()
            except Exception:
                pass
        if close_audio:
            self.close_audio_recording()

    def receive_loop(self):
        import websocket as ws_module
        while True:
            with self.lock:
                ws = self.ws
                running = self.running
            if not ws or not running:
                return
            try:
                raw = ws.recv()
                if isinstance(raw, str):
                    continue
                message = parse_server_message(raw)
                if message.message_type == MSG_ERROR_RESPONSE:
                    if message.error_code != 45000081 or "Timeout waiting next packet" not in str(message.payload):
                        self.add_event("error", message=f"API error {message.error_code}: {message.payload}")
                    with self.lock:
                        self.running = False
                    return
                for utterance in iter_utterances(message.payload):
                    text = (utterance.get("text") or "").strip()
                    if not text:
                        continue
                    if utterance.get("definite") is True:
                        key = (utterance.get("start_time"), utterance.get("end_time"), text)
                        if key not in self.seen_finals:
                            self.seen_finals.add(key)
                            self.handle_asr_final(text)
                    elif text != self.partial:
                        self.partial = text
                        self.add_event("partial", text=text)
            except Exception as exc:
                with self.lock:
                    self.running = False
                    self.ws = None
                message = str(exc)
                if type(exc).__name__ == "SSLEOFError" or "EOF occurred in violation of protocol" in message:
                    print("[ASR] upstream SSL connection closed; waiting for next audio packet to reconnect.", flush=True)
                else:
                    self.add_event("error", message=f"{type(exc).__name__}: {exc}")
                return

    def handle_asr_final(self, text: str):
        self.add_event("utterance", text=text)

        if self.fast_mode:
            with self.lock:
                self.turn_buffer.append(text)
                transcript = "".join(self.turn_buffer).strip()
                self.turn_buffer.clear()
                self.turn_version += 1
            self.emit_sentence_done(transcript)
            return

        with self.lock:
            self.turn_buffer.append(text)
            self.turn_version += 1
            version = self.turn_version
            transcript = "".join(self.turn_buffer).strip()

        if not self.semantic_final_enabled:
            with self.lock:
                self.turn_buffer.clear()
                self.turn_version += 1
            self.emit_sentence_done(transcript)
            return

        self.add_event("status", message="Checking semantic completeness...")
        threading.Thread(
            target=self.semantic_decision_worker,
            args=(version, transcript),
            daemon=True,
        ).start()

    def semantic_decision_worker(self, version: int, transcript: str):
        time.sleep(0.1)
        try:
            decision = semantic_turn_decision(transcript, False)
        except Exception as exc:
            self.add_event("error", message=f"Semantic decision failed: {exc}")
            self.emit_sentence_done(transcript)
            return

        with self.lock:
            if version != self.turn_version:
                return
            if decision["complete"]:
                self.turn_buffer.clear()
                self.turn_version += 1

        if decision["complete"]:
            self.emit_sentence_done(transcript)
        else:
            self.add_event("merge_continue", reason=decision.get("reason", "Semantic incomplete"))

    def emit_sentence_done(self, transcript: str):
        self.record_realtime_sentence(transcript)
        self.add_event("sentence_done", text=transcript)

    def events_after(self, after: int):
        with self.event_lock:
            return [e for e in self.events if e["id"] > after]


def make_http_handler(session: DoubaoSession):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_GET(self):
            path = urlparse(self.path)
            if path.path == "/events":
                params = parse_qs(path.query)
                after = int((params.get("after") or ["0"])[0] or "0")
                self.send_json(HTTPStatus.OK, {"events": session.events_after(after)})
            elif path.path == "/":
                self.send_text(HTTPStatus.OK, PAGE, "text/html; charset=utf-8")
            elif path.path == "/debug-env":
                self.send_json(
                    HTTPStatus.OK,
                    {
                        "provider": "doubao",
                        "app_key_loaded": bool(os.getenv("DOUBAO_APP_ID")),
                        "access_key_loaded": bool(os.getenv("DOUBAO_ACCESS_TOKEN")),
                        "resource_id": os.getenv("DOUBAO_RESOURCE_ID"),
                    },
                )
            else:
                if self.serve_dist(path.path):
                    return
                self.send_text(HTTPStatus.NOT_FOUND, "not found")

        def do_DELETE(self):
            if self.path == "/api/resume":
                _parsed_resume.clear()
                session.clear_resume_file_state()
                self.send_json(HTTPStatus.OK, {"status": "success", "resume": None})
            else:
                self.send_text(HTTPStatus.NOT_FOUND, "not found")

        def do_POST(self):
            if self.path == "/start":
                try:
                    session.start()
                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    self.send_text(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                    return
                self.send_json(HTTPStatus.OK, {"ok": True})
            elif self.path == "/stop":
                session.stop()
                self.send_json(HTTPStatus.OK, {"ok": True})
            elif self.path == "/api/classify-speaker-role":
                length = int(self.headers.get("Content-Length", "0") or "0")
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    text = str(payload.get("text") or "")
                    history = payload.get("history") or []
                    if not isinstance(history, list):
                        history = []
                    result = classify_realtime_speaker_role(text, history)
                    self.send_json(HTTPStatus.OK, {"status": "success", **result})
                except Exception as exc:
                    self.send_json(
                        HTTPStatus.OK,
                        {
                            "status": "fallback",
                            "role": "unknown",
                            "speakerLabel": "待识别",
                            "confidence": 0,
                            "reason": f"角色判断失败：{exc}",
                            "source": "error",
                        },
                    )
            elif self.path == "/api/analyze":
                length = int(self.headers.get("Content-Length", "0") or "0")
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    text = str(payload.get("text") or "")
                except Exception as exc:
                    self.send_text(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                    return

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True

                buffer = []
                analysis_done = threading.Event()
                response_closed = threading.Event()
                write_lock = threading.Lock()

                def write_sse(payload):
                    if response_closed.is_set():
                        return False
                    try:
                        with write_lock:
                            if response_closed.is_set():
                                return False
                            self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                            self.wfile.flush()
                        return True
                    except Exception as e:
                        response_closed.set()
                        print(f"[SSE] write failed: {e}", flush=True)
                        return False

                def on_chunk(chunk: str):
                    buffer.append(chunk)
                    data = json.dumps({"text": chunk}, ensure_ascii=False)
                    write_sse(data)

                def done_callback(result: dict):
                    if response_closed.is_set():
                        analysis_done.set()
                        return
                    data = json.dumps({
                        "done": True,
                        "analysis": result.get("analysis", ""),
                        "is_correct": result.get("is_correct"),
                        "doubts": result.get("doubts", []),
                        "questions": result.get("questions", [])
                    }, ensure_ascii=False)
                    write_sse(data)
                    write_sse("[DONE]")
                    response_closed.set()
                    analysis_done.set()

                threading.Thread(
                    target=self._stream_analyze,
                    args=(text, on_chunk, done_callback),
                    daemon=True,
                ).start()

                timeout_seconds = int(os.getenv("AI_ANALYSIS_TIMEOUT_SECONDS", "18"))
                if not analysis_done.wait(timeout=timeout_seconds):
                    print(f"[AI] analyze timeout after {timeout_seconds}s, returning fallback.", flush=True)
                    done_callback(fallback_analysis(text))
            elif self.path == "/api/upload-resume":
                self._upload_resume()
            elif self.path == "/api/explain-term":
                length = int(self.headers.get("Content-Length", "0") or "0")
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    explanation = explain_resume_term(payload)
                    self.send_json(HTTPStatus.OK, {"status": "success", "explanation": explanation})
                except Exception as exc:
                    self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            elif self.path == "/api/final-report":
                length = int(self.headers.get("Content-Length", "0") or "0")
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    if payload.get("demoMode"):
                        calibrated = None
                    else:
                        if session.audio_path and not payload.get("audio_path"):
                            payload["audio_path"] = session.audio_path
                        if session.interview_dir and not payload.get("interview_dir"):
                            payload["interview_dir"] = session.interview_dir
                        if session.realtime_transcript_path and not payload.get("realtime_transcript_path"):
                            payload["realtime_transcript_path"] = session.realtime_transcript_path
                        session.start_background_diarization()
                        calibrated = session.get_background_diarization_result(
                            float(os.getenv("DIARIZATION_REPORT_WAIT_SECONDS", "0.5"))
                        )
                        if calibrated is None and session.audio_path:
                            calibrated = session.speaker_diarization_placeholder("speaker diarization queued in background")
                    result = create_final_report(payload, calibrated=calibrated)
                    self.send_json(HTTPStatus.OK, {"status": "success", **result})
                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            elif self.path == "/api/mode":
                length = int(self.headers.get("Content-Length", "0") or "0")
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    mode = str(payload.get("mode", "") or "").lower()
                    if mode in ("fast", "smart"):
                        session.fast_mode = (mode == "fast")
                        self.send_json(HTTPStatus.OK, {"mode": mode, "fast_mode": session.fast_mode})
                    else:
                        self.send_text(HTTPStatus.BAD_REQUEST, "mode must be 'fast' or 'smart'")
                except Exception as exc:
                    self.send_text(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            else:
                self.send_text(HTTPStatus.NOT_FOUND, "not found")

        def serve_dist(self, path: str) -> bool:
            target = dist_file_for(path)
            if not target:
                return False
            content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if target.suffix == ".js":
                content_type = "text/javascript; charset=utf-8"
            elif target.suffix in (".html", ".css"):
                content_type = f"{content_type}; charset=utf-8"
            self.send_bytes(HTTPStatus.OK, target.read_bytes(), content_type)
            return True

        def send_text(self, status: int, text: str, content_type: str = "text/plain; charset=utf-8"):
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status: int, payload: dict):
            self.send_text(status, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")

        def send_bytes(self, status: int, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _stream_analyze(self, text: str, on_chunk, done_callback):
            try:
                result = analyze_interview_answer(text, callback=on_chunk)
                done_callback(result)
            except Exception as exc:
                print(f"[AI] analysis failed, returning fallback: {exc}", flush=True)
                result = fallback_analysis(text)
                result["doubts"] = (result.get("doubts") or []) + [f"AI 分析接口异常：{exc}"]
                done_callback(result)

        def _upload_resume(self):
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_text(HTTPStatus.BAD_REQUEST, "Content-Type must be multipart/form-data")
                return
            
            content_length = int(self.headers.get('Content-Length', 0))
            max_bytes = int(os.getenv("RESUMESDK_MAX_FILE_MB", "30")) * 1024 * 1024
            if content_length > max_bytes:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "简历文件不能超过 30MB"})
                return
            body = self.rfile.read(content_length)
            
            # Parse multipart data manually
            boundary = content_type.split('boundary=')[1].encode()
            parts = body.split(b'--' + boundary)
            
            file_data = None
            filename = 'unknown.pdf'
            
            for part in parts:
                if not part or part == b'--\r\n':
                    continue
                
                # Find headers and content
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue
                
                headers = part[:header_end].decode('utf-8', errors='replace')
                content = part[header_end + 4:]
                
                # Extract filename
                if 'filename=' in headers:
                    filename_start = headers.index('filename="') + 10
                    filename_end = headers.index('"', filename_start)
                    filename = headers[filename_start:filename_end]
                    file_data = content.rstrip(b'\r\n')
            
            if not file_data:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "No file uploaded"})
                return
            if len(file_data) > max_bytes:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "简历文件不能超过 30MB"})
                return
            if safe_file_suffix(filename, "") == "":
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "仅支持 PDF / DOC / DOCX / TXT / HTML / RTF"})
                return
            
            try:
                start_at = time.time()
                print(f"[ResumeSDK] parsing {filename} ({len(file_data)} bytes)", flush=True)
                result = parse_resume_with_resumesdk_hard_timeout(file_data, filename)
                _parsed_resume.clear()
                _parsed_resume.update(result)
                saved = session.store_resume_file(filename, file_data, result)
                if saved.get("resume_file_path"):
                    result["resume_file_path"] = saved.get("resume_file_path")
                if saved.get("resume_parsed_path"):
                    result["resume_parsed_path"] = saved.get("resume_parsed_path")
                if saved.get("pending"):
                    result["resume_file_pending"] = True
                
                self.send_json(HTTPStatus.OK, {
                    "status": "success",
                    "resume": result,
                    **saved,
                })
                print(f"[ResumeSDK] parsed {filename} in {time.time() - start_at:.1f}s", flush=True)
            except Exception as exc:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    return Handler


session = None
ws_server = None


def main():
    global session, ws_server

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=8770)
    parser.add_argument("--ws-port", type=int, default=8771)
    parser.add_argument("--resource-id", default=os.getenv("DOUBAO_RESOURCE_ID", "volc.seedasr.sauc.duration"))
    parser.add_argument("--end-window-size", type=int, default=int(os.getenv("DOUBAO_END_WINDOW_SIZE", "300")))
    args = parser.parse_args()

    ws_server = WsServer(args.host, args.ws_port, None)
    session = DoubaoSession(args.resource_id, args.end_window_size, ws_server)
    ws_server.session = session
    ws_server.start()

    server = ThreadingHTTPServer((args.host, args.http_port), make_http_handler(session))
    print(f"[HTTP] open http://{args.host}:{args.http_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        session.stop()
        ws_server.stop()
        server.server_close()


if __name__ == "__main__":
    main()
