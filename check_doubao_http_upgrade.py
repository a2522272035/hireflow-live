import base64
import os
import socket
import ssl
import urllib.parse
import uuid
from pathlib import Path

from doubao_asr_final import load_dotenv, make_headers


URLS = [
    "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async",
    "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel",
]
RESOURCES = [
    "volc.seedasr.sauc.duration",
    "volc.seedasr.sauc.concurrent",
]


def read_response(sock):
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    head, _, rest = data.partition(b"\r\n\r\n")
    headers = {}
    lines = head.decode("iso-8859-1", errors="replace").split("\r\n")
    status = lines[0] if lines else ""
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.lower()] = value.strip()
    content_length = int(headers.get("content-length", "0") or "0")
    body = rest
    while len(body) < content_length:
        chunk = sock.recv(4096)
        if not chunk:
            break
        body += chunk
    return status, headers, body[:content_length]


def check(url, resource_id):
    parsed = urllib.parse.urlparse(url)
    headers = make_headers(resource_id)
    headers["X-Api-Connect-Id"] = str(uuid.uuid4())
    sec_key = base64.b64encode(os.urandom(16)).decode("ascii")
    request_lines = [
        f"GET {parsed.path} HTTP/1.1",
        f"Host: {parsed.netloc}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {sec_key}",
        "Sec-WebSocket-Version: 13",
        "User-Agent: doubao-auth-check",
    ]
    request_lines += [f"{key}: {value}" for key, value in headers.items()]
    request = "\r\n".join(request_lines) + "\r\n\r\n"

    context = ssl.create_default_context()
    with socket.create_connection((parsed.hostname, parsed.port or 443), timeout=12) as raw:
        with context.wrap_socket(raw, server_hostname=parsed.hostname) as sock:
            sock.sendall(request.encode("utf-8"))
            status, resp_headers, body = read_response(sock)

    print(f"\nchecking {parsed.path.rsplit('/', 1)[-1]} {resource_id}")
    print(status)
    interesting = {
        key: value
        for key, value in resp_headers.items()
        if key in ("content-type", "x-api-status-code", "x-api-message", "x-tt-logid")
    }
    print(interesting)
    if body:
        print(body.decode("utf-8", errors="replace"))


def main():
    env_keys = []
    if Path(".env").exists():
        for raw_line in Path(".env").read_text(encoding="utf-8-sig").splitlines():
            if "=" in raw_line and not raw_line.strip().startswith("#"):
                key, value = raw_line.split("=", 1)
                key = key.strip().lstrip("\ufeff")
                env_keys.append(key)
                os.environ[key] = value.strip().strip('"').strip("'")
    print(f"env_file_keys={env_keys}")
    load_dotenv()
    print(
        "env_loaded",
        f"app_key={bool(os.getenv('DOUBAO_APP_KEY'))}",
        f"access_key={bool(os.getenv('DOUBAO_ACCESS_KEY'))}",
    )
    for url in URLS:
        for resource_id in RESOURCES:
            check(url, resource_id)


if __name__ == "__main__":
    main()
