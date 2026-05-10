import argparse
import uuid

import websocket

from doubao_asr_final import URL, load_dotenv, make_headers


RESOURCE_IDS = [
    "volc.seedasr.sauc.duration",
    "volc.seedasr.sauc.concurrent",
]


def check(resource_id: str) -> bool:
    headers = make_headers(resource_id)
    connect_id = str(uuid.uuid4())
    headers["X-Api-Connect-Id"] = connect_id
    printable_headers = {
        "X-Api-App-Key": f"len={len(headers['X-Api-App-Key'])}",
        "X-Api-Access-Key": f"len={len(headers['X-Api-Access-Key'])}",
        "X-Api-Resource-Id": headers["X-Api-Resource-Id"],
        "X-Api-Connect-Id": connect_id,
    }
    print(f"\nchecking {resource_id}")
    print(printable_headers)

    try:
        ws = websocket.create_connection(
            URL,
            header=[f"{key}: {value}" for key, value in headers.items()],
            timeout=12,
        )
        print("handshake_ok")
        try:
            response_headers = getattr(ws, "headers", None)
            if response_headers:
                print(f"response_headers={response_headers}")
        finally:
            ws.close()
        return True
    except websocket.WebSocketBadStatusException as exc:
        print(f"handshake_failed status={getattr(exc, 'status_code', None) or exc}")
        response_headers = getattr(exc, "resp_headers", None) or getattr(exc, "headers", None)
        if response_headers:
            print(f"response_headers={response_headers}")
        response_body = getattr(exc, "resp_body", None) or getattr(exc, "response_body", None)
        if response_body:
            if isinstance(response_body, bytes):
                response_body = response_body.decode("utf-8", errors="replace")
            print(f"response_body={response_body}")
        return False
    except Exception as exc:
        print(f"handshake_failed error={type(exc).__name__}: {exc}")
        return False


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Check Doubao ASR WebSocket auth without printing secrets.")
    parser.add_argument("--resource-id", action="append", help="Resource id to check. Can be repeated.")
    args = parser.parse_args()

    resource_ids = args.resource_id or RESOURCE_IDS
    ok = False
    for resource_id in resource_ids:
        ok = check(resource_id) or ok
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
