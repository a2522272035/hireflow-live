import argparse
import asyncio
import gzip
import json
import os
import sys
import uuid
import wave
from dataclasses import dataclass
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if not os.path.exists(env_path):
            env_path = ".env"
        if not os.path.exists(env_path):
            return False
        with open(env_path, "r", encoding="utf-8-sig") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip().lstrip("\ufeff")
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value
        return False


URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"

PROTOCOL_VERSION = 0x1
HEADER_SIZE = 0x1

MSG_FULL_CLIENT_REQUEST = 0x1
MSG_AUDIO_ONLY_REQUEST = 0x2
MSG_FULL_SERVER_RESPONSE = 0x9
MSG_ERROR_RESPONSE = 0xF

FLAG_NO_SEQUENCE = 0x0
FLAG_POS_SEQUENCE = 0x1
FLAG_LAST_PACKET = 0x2
FLAG_NEG_SEQUENCE = 0x3

SERIALIZATION_NONE = 0x0
SERIALIZATION_JSON = 0x1

COMPRESSION_NONE = 0x0
COMPRESSION_GZIP = 0x1


@dataclass
class ServerMessage:
    message_type: int
    flags: int
    sequence: int | None
    payload: Any
    error_code: int | None = None


def build_header(
    message_type: int,
    flags: int,
    serialization: int,
    compression: int,
) -> bytes:
    return bytes(
        [
            (PROTOCOL_VERSION << 4) | HEADER_SIZE,
            (message_type << 4) | flags,
            (serialization << 4) | compression,
            0x00,
        ]
    )


def build_full_client_request(end_window_size: int, language: str | None) -> bytes:
    payload: dict[str, Any] = {
        "user": {"uid": str(uuid.uuid4())},
        "audio": {
            "format": "pcm",
            "rate": 16000,
            "bits": 16,
            "channel": 1,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_nonstream": True,
            "show_utterances": True,
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": True,
            "force_to_speech_time": 800,
            "result_type": "full",
            "end_window_size": end_window_size,
        },
    }
    # Docs note that language is mainly for bigmodel_nostream; keep it optional.
    if language:
        payload["audio"]["language"] = language

    body = gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    header = build_header(
        MSG_FULL_CLIENT_REQUEST,
        FLAG_NO_SEQUENCE,
        SERIALIZATION_JSON,
        COMPRESSION_GZIP,
    )
    return header + len(body).to_bytes(4, "big") + body


def build_audio_request(audio: bytes, is_last: bool = False) -> bytes:
    body = gzip.compress(audio)
    header = build_header(
        MSG_AUDIO_ONLY_REQUEST,
        FLAG_LAST_PACKET if is_last else FLAG_NO_SEQUENCE,
        SERIALIZATION_NONE,
        COMPRESSION_GZIP,
    )
    return header + len(body).to_bytes(4, "big") + body


def parse_server_message(data: bytes) -> ServerMessage:
    if len(data) < 8:
        raise ValueError(f"server frame is too short: {len(data)} bytes")

    header_size = (data[0] & 0x0F) * 4
    message_type = data[1] >> 4
    flags = data[1] & 0x0F
    serialization = data[2] >> 4
    compression = data[2] & 0x0F
    offset = header_size
    sequence: int | None = None

    if message_type == MSG_FULL_SERVER_RESPONSE:
        if flags in (FLAG_POS_SEQUENCE, FLAG_NEG_SEQUENCE):
            sequence = int.from_bytes(data[offset : offset + 4], "big", signed=True)
            offset += 4
        payload_size = int.from_bytes(data[offset : offset + 4], "big")
        offset += 4
        payload = data[offset : offset + payload_size]
    elif message_type == MSG_ERROR_RESPONSE:
        error_code = int.from_bytes(data[offset : offset + 4], "big")
        offset += 4
        payload_size = int.from_bytes(data[offset : offset + 4], "big")
        offset += 4
        payload = data[offset : offset + payload_size]
        if compression == COMPRESSION_GZIP:
            payload = gzip.decompress(payload)
        text = payload.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text) if serialization == SERIALIZATION_JSON else text
        except json.JSONDecodeError:
            parsed = text
        return ServerMessage(message_type, flags, sequence, parsed, error_code)
    else:
        raise ValueError(f"unsupported server message type: {message_type}")

    if compression == COMPRESSION_GZIP:
        payload = gzip.decompress(payload)

    text = payload.decode("utf-8", errors="replace")
    parsed = json.loads(text) if serialization == SERIALIZATION_JSON and text else text
    return ServerMessage(message_type, flags, sequence, parsed)


def iter_utterances(payload: Any):
    if not isinstance(payload, dict):
        return

    result = payload.get("result")
    if isinstance(result, dict):
        for utterance in result.get("utterances") or []:
            if isinstance(utterance, dict):
                yield utterance
    elif isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                for utterance in item.get("utterances") or []:
                    if isinstance(utterance, dict):
                        yield utterance


def make_headers(resource_id: str) -> dict[str, str]:
    load_dotenv()
    app_key = (
        os.getenv("DOUBAO_APP_ID")
        or os.getenv("DOUBAO_APP_KEY")
        or os.getenv("VOLC_APP_ID")
        or os.getenv("VOLC_APP_KEY")
    )
    access_key = (
        os.getenv("DOUBAO_ACCESS_TOKEN")
        or os.getenv("DOUBAO_ACCESS_KEY")
        or os.getenv("VOLC_ACCESS_TOKEN")
        or os.getenv("VOLC_ACCESS_KEY")
    )

    missing = []
    if not app_key:
        missing.append("DOUBAO_APP_ID")
    if not access_key:
        missing.append("DOUBAO_ACCESS_TOKEN")
    if missing:
        raise RuntimeError(f"missing environment variables: {', '.join(missing)}")

    return {
        "X-Api-App-Key": app_key,
        "X-Api-Access-Key": access_key,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }


def websocket_connect(headers: dict[str, str]):
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("websocket mode needs websockets: pip install -r requirements.txt") from exc

    return websockets.connect(URL, extra_headers=headers, max_size=None)


async def receive_loop(ws, show_partial: bool) -> None:
    seen_finals: set[tuple[int | None, int | None, str]] = set()
    last_partial = ""

    async for raw in ws:
        if not isinstance(raw, bytes):
            print(f"server text message: {raw}", file=sys.stderr)
            continue

        message = parse_server_message(raw)
        if message.message_type == MSG_ERROR_RESPONSE:
            raise RuntimeError(f"API error {message.error_code}: {message.payload}")

        for utterance in iter_utterances(message.payload):
            text = (utterance.get("text") or "").strip()
            if not text:
                continue

            if utterance.get("definite") is True:
                key = (utterance.get("start_time"), utterance.get("end_time"), text)
                if key not in seen_finals:
                    seen_finals.add(key)
                    print(f"final: {text}", flush=True)
            elif show_partial and text != last_partial:
                last_partial = text
                print(f"partial: {text}", flush=True)


async def stream_microphone(args: argparse.Namespace) -> None:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("microphone mode needs sounddevice: pip install -r requirements.txt") from exc

    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=20)
    loop = asyncio.get_running_loop()
    chunk_frames = int(16000 * args.chunk_ms / 1000)

    def on_audio(indata, frames, time, status) -> None:
        if status:
            print(f"audio status: {status}", file=sys.stderr)
        chunk = bytes(indata)

        def enqueue() -> None:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(chunk)
            except asyncio.QueueFull:
                pass

        loop.call_soon_threadsafe(enqueue)

    headers = make_headers(args.resource_id)
    async with websocket_connect(headers) as ws:
        print("connected. Speak into the microphone. Press Ctrl+C to stop.", flush=True)
        await ws.send(build_full_client_request(args.end_window_size, args.language))
        receiver = asyncio.create_task(receive_loop(ws, args.show_partial))

        try:
            with sd.RawInputStream(
                samplerate=16000,
                channels=1,
                dtype="int16",
                blocksize=chunk_frames,
                callback=on_audio,
            ):
                while True:
                    if receiver.done():
                        receiver.result()
                    chunk_task = asyncio.create_task(queue.get())
                    done, _ = await asyncio.wait(
                        {chunk_task, receiver},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if receiver in done:
                        chunk_task.cancel()
                        receiver.result()
                    chunk = chunk_task.result()
                    await ws.send(build_audio_request(chunk))
        finally:
            await ws.send(build_audio_request(b"", is_last=True))
            await asyncio.sleep(0.2)
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)


async def stream_wav_file(args: argparse.Namespace) -> None:
    headers = make_headers(args.resource_id)
    async with websocket_connect(headers) as ws:
        print(f"connected. Streaming WAV file: {args.wav}", flush=True)
        await ws.send(build_full_client_request(args.end_window_size, args.language))
        receiver = asyncio.create_task(receive_loop(ws, args.show_partial))

        with wave.open(args.wav, "rb") as wav:
            if wav.getframerate() != 16000 or wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise RuntimeError("WAV must be 16kHz, mono, 16-bit PCM")

            frames_per_chunk = int(16000 * args.chunk_ms / 1000)
            while True:
                chunk = wav.readframes(frames_per_chunk)
                if not chunk:
                    break
                await ws.send(build_audio_request(chunk))
                await asyncio.sleep(args.chunk_ms / 1000)

        await ws.send(build_audio_request(b"", is_last=True))
        try:
            await asyncio.wait_for(receiver, timeout=args.file_wait_seconds)
        except asyncio.TimeoutError:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal Doubao streaming ASR 2.0 validator. Prints 'final:' when API marks an utterance definite."
    )
    parser.add_argument("--wav", help="Optional 16kHz mono 16-bit PCM WAV file. If omitted, microphone is used.")
    parser.add_argument("--resource-id", default=os.getenv("DOUBAO_RESOURCE_ID", "volc.seedasr.sauc.duration"))
    parser.add_argument("--language", default="", help="Optional language hint. Empty means omit this field.")
    parser.add_argument("--chunk-ms", type=int, default=200, help="Audio packet size, 100-200ms is recommended.")
    parser.add_argument("--end-window-size", type=int, default=800, help="Silence ms before API returns definite=true.")
    parser.add_argument("--file-wait-seconds", type=float, default=10.0)
    parser.add_argument("--show-partial", action="store_true", help="Also print non-final partial text.")
    return parser


async def amain() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    if args.language == "":
        args.language = None

    if args.wav:
        await stream_wav_file(args)
    else:
        await stream_microphone(args)


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("\nstopped.", flush=True)


if __name__ == "__main__":
    main()
