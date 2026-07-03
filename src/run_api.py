"""Run the F009 API server and make sample API calls.

Quickstart:
    # Terminal 1 — start the server
    python src/run_api.py

    # Terminal 2 — interactive API caller
    python src/run_api.py --call

    # Custom port (must match on both terminals)
    python src/run_api.py --port 9000
    python src/run_api.py --call --port 9000

The --call flag starts an interactive loop:
  1. Show menu of APIs (session/start, recommend, session/end)
  2. Open default JSON in $EDITOR for editing
  3. Send request, show response + HTTP status
  4. If session/start succeeded, remember call_id for subsequent calls
  5. Loop back to menu (Ctrl-C to exit)

Usage:
    python src/run_api.py                        # start server only
    python src/run_api.py --port 9000            # custom port
    python src/run_api.py --call                 # interactive API caller
    python src/run_api.py --call --no-edit       # use defaults, skip editor
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

src_dir = str(Path(__file__).resolve().parent)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

os.environ["PG_DSN"] = "postgresql://jiani@localhost/icbc"

import uvicorn


def default_session_start():
    return {
        "call_id": "2346430930132135291",
        "call_info": {
            "dial_date": "20260608183813",
            "connect_date": "20260608183852",
            "dial_type": "1",
            "ring_time": "37",
            "channel": "X",
            "mob_type": "M1",
        },
        "agent": {
            "coll_user_id": "AA11100",
            "coll_id": "A0BW9",
            "coll_area": "2",
            "coll_group_id": "CK002",
        },
        "customer": {
            "cust_no": "0000000221241219",
            "ac_no": "0221241219001001",
            "called_no": "13383023270",
        },
        "cust_tags": [
            {"tag": "经营贷款余额", "value": "0.0"},
            {"tag": "理财时点值", "value": "0.0"},
            {"tag": "其他贷款余额", "value": "0.0"},
            {"tag": "学历", "value": "大专"},
            {"tag": "商业房贷余额", "value": "0.0"},
            {"tag": "持卡用户是否疑似高风险代理投诉", "value": "否"},
            {"tag": "持卡用户是否疑似代理中介投诉", "value": "否"},
            {"tag": "持卡人当前是否缴纳社保", "value": ""},
            {"tag": "目前余额", "value": "7129.18"},
            {"tag": "ct标签", "value": ",667,040,"},
            {"tag": "（掌生APP操作）近7天-还款操作", "value": "N"},
            {"tag": "持卡用户名下历史车辆数", "value": "0"},
            {"tag": "近7日接通次数", "value": "19"},
            {"tag": "客户风险标识等级", "value": "3级"},
        ],
    }


def default_recommend(call_id: str, history: list[str]):
    return {
        "call_id": call_id,
        "current_text": "我失业了，没钱还",
        "history_context": list(history),
    }


def default_session_end(call_id: str):
    return {"call_id": call_id}


def edit_json(default: dict) -> dict:
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(default, f, indent=2, ensure_ascii=False)
        tmp = f.name
    try:
        subprocess.run([editor, tmp], check=True)
        with open(tmp, encoding="utf-8") as f:
            return json.load(f)
    finally:
        os.unlink(tmp)


def send(method: str, url: str, body: dict | None = None) -> tuple[int, dict | str | None]:
    cmd = ["curl", "-s", "-w", "\n%{http_code}", "-X", method, url,
           "-H", "Content-Type: application/json"]
    if body is not None:
        cmd += ["-d", json.dumps(body, ensure_ascii=False)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = result.stdout.rsplit("\n", 1)
    code = int(lines[-1]) if lines[-1].isdigit() else 0
    raw = lines[0] if len(lines) > 1 else ""
    try:
        parsed = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = raw
    return code, parsed


def interactive_loop(base_url: str, edit: bool):
    call_id = None
    history = []

    while True:
        print(f"\n{'='*50}")
        if call_id:
            print(f"  Active session: {call_id}  ({len(history)} turns)")
        else:
            print("  No active session")
        print(f"{'='*50}")
        print("  1) session/start")
        print("  2) recommend")
        print("  3) session/end")
        print("  q) quit")

        choice = input("\n> ").strip().lower()
        if choice == "q":
            break
        if choice not in ("1", "2", "3"):
            print("Invalid choice")
            continue

        try:
            if choice == "1":
                body = default_session_start()
                if edit:
                    body = edit_json(body)
                print(f"\n-> POST {base_url}/api/v1/session/start")
                code, resp = send("POST", f"{base_url}/api/v1/session/start", body)
                print(f"   HTTP {code}")
                print(f"   {json.dumps(resp, ensure_ascii=False, indent=2)}" if resp else "")
                if code == 200 and resp and "call_id" in resp:
                    call_id = resp["call_id"]
                    history = []
                    print(f"\n✓ Session started: {call_id}")

            elif choice == "2":
                if not call_id:
                    print("\n  No active session. Start a session first (option 1).")
                    continue
                body = default_recommend(call_id, history)
                if edit:
                    body = edit_json(body)
                print(f"\n-> POST {base_url}/api/v1/recommend")
                code, resp = send("POST", f"{base_url}/api/v1/recommend", body)
                print(f"   HTTP {code}")
                print(f"   {json.dumps(resp, ensure_ascii=False, indent=2)}" if resp else "")
                if code == 200 and resp:
                    history.append(body.get("current_text", ""))
                    rec_id = resp.get("rec_id", "")
                    print(f"\n✓ Turn {len(history)} | rec_id: {rec_id}")

            elif choice == "3":
                if not call_id:
                    print("\n  No active session.")
                    continue
                body = default_session_end(call_id)
                if edit:
                    body = edit_json(body)
                cid = body.get("call_id", call_id)
                print(f"\n-> DELETE {base_url}/api/v1/session/end?call_id={cid}")
                code, resp = send("DELETE", f"{base_url}/api/v1/session/end?call_id={cid}")
                print(f"   HTTP {code}")
                print(f"   {json.dumps(resp, ensure_ascii=False, indent=2)}" if resp else "")
                if code == 200:
                    call_id = None
                    history = []
                    print("\n✓ Session closed")

        except KeyboardInterrupt:
            print()
            continue
        except Exception as e:
            print(f"\n  Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Run the F009 API server and/or make sample API calls")
    parser.add_argument("--port", type=int, default=8114)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--call", action="store_true", help="Interactive API caller (instead of starting server)")
    parser.add_argument("--no-edit", action="store_true", help="Use default payloads, skip editor")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"

    if args.call:
        interactive_loop(base_url, edit=not args.no_edit)
    else:
        uvicorn.run("f009_api_server.server:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
