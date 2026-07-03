"""Run the F009 API server and make sample API calls.

Quickstart:
    # Terminal 1 — start the server
    python src/run_api.py

    # Terminal 2 — call an API (opens $EDITOR to edit the JSON payload)
    python src/run_api.py --call

    # Or skip the editor and use the default sample payload
    python src/run_api.py --call --no-edit

    # Custom port (must match on both terminals)
    python src/run_api.py --port 9000
    python src/run_api.py --call --port 9000

Usage:
    python src/run_api.py                        # start server only
    python src/run_api.py --port 9000            # custom port
    python src/run_api.py --call                 # choose an API and call it
    python src/run_api.py --call --no-edit       # use default sample, skip editor

The --call flag lets you pick one of the three external APIs, opens a
default JSON payload in $EDITOR for editing, then sends the request.
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

SAMPLES = {
    "1": {
        "name": "POST /api/v1/session/start",
        "method": "POST",
        "path": "/api/v1/session/start",
        "body": {
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
        },
    },
    "2": {
        "name": "POST /api/v1/recommend",
        "method": "POST",
        "path": "/api/v1/recommend",
        "body": {
            "call_id": "2346430930132135291",
            "current_text": "我失业了，没钱还",
            "history_context": [],
        },
    },
    "3": {
        "name": "DELETE /api/v1/session/end",
        "method": "DELETE",
        "path": "/api/v1/session/end",
        "query": {"call_id": "2346430930132135291"},
        "body": None,
    },
}


def edit_json(default: dict | None) -> dict | None:
    if default is None:
        return None
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


def do_call(base_url: str, choice: str, edit: bool):
    spec = SAMPLES[choice]
    print(f"\n=== {spec['name']} ===")
    body = spec.get("body")
    if edit and body is not None:
        print("(editing JSON payload — save & quit to send)")
        body = edit_json(body)
    url = base_url + spec["path"]
    if spec.get("query"):
        qs = "&".join(f"{k}={v}" for k, v in spec["query"].items())
        url += f"?{qs}"
    cmd = ["curl", "-s", "-w", "\nHTTP %{http_code}", "-X", spec["method"],
           url, "-H", "Content-Type: application/json"]
    if body is not None:
        cmd += ["-d", json.dumps(body, ensure_ascii=False)]
    print(f"-> {spec['method']} {url}")
    if body is not None:
        print(f"   body: {json.dumps(body, ensure_ascii=False)}")
    subprocess.run(cmd)
    print()


def main():
    parser = argparse.ArgumentParser(description="Run the F009 API server and/or make sample API calls")
    parser.add_argument("--port", type=int, default=8114)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--call", action="store_true", help="Make an API call instead of starting the server")
    parser.add_argument("--no-edit", action="store_true", help="Use default sample payload, skip editor")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"

    if args.call:
        print("Available APIs:")
        for k, v in SAMPLES.items():
            print(f"  {k}) {v['name']}")
        choice = input("\nChoose [1-3]: ").strip()
        if choice not in SAMPLES:
            print("Invalid choice"); sys.exit(1)
        do_call(base_url, choice, edit=not args.no_edit)
    else:
        uvicorn.run("f009_api_server.server:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
