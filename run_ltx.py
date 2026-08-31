#!/usr/bin/env python3
"""Submit an LTX-2.5 i2v job to the RunPod serverless endpoint.

Usage:
  RUNPOD_API_KEY=... python3 run_ltx.py <endpoint_id> <start_image> [--prompt "..."] [--duration 15] [--seed N] [--out out.mp4]
"""
import argparse, base64, json, os, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKFLOW = HERE / "ltx25-i2v-api.json"


def api(url, key, body=None, timeout=120):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("endpoint_id")
    ap.add_argument("start_image")
    ap.add_argument("--prompt")
    ap.add_argument("--duration", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", default="ltx_out.mp4")
    args = ap.parse_args()
    key = os.environ["RUNPOD_API_KEY"]

    wf = json.loads(WORKFLOW.read_text())
    if args.prompt:
        wf["398:376"]["inputs"]["value"] = args.prompt
    if args.duration:
        wf["398:362"]["inputs"]["value"] = args.duration
    if args.seed is not None:
        wf["398:339"]["inputs"]["noise_seed"] = args.seed
        wf["398:338"]["inputs"]["noise_seed"] = args.seed + 1

    img_b64 = base64.b64encode(Path(args.start_image).read_bytes()).decode()
    payload = {
        "input": {
            "workflow": wf,
            "images": [{"name": "startframe.png", "image": img_b64}],
        }
    }

    base = f"https://api.runpod.ai/v2/{args.endpoint_id}"
    sub = api(f"{base}/run", key, payload)
    job_id = sub["id"]
    print(f"job {job_id} submitted", flush=True)

    t0 = time.time()
    delay_status = None
    while True:
        time.sleep(10)
        st = api(f"{base}/status/{job_id}", key)
        status = st.get("status")
        el = int(time.time() - t0)
        if status != delay_status:
            print(f"[{el}s] {status}", flush=True)
            delay_status = status
        if status in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
            break

    if status != "COMPLETED":
        print(json.dumps(st)[:3000])
        sys.exit(1)

    out = st.get("output") or {}
    imgs = out.get("images") or []
    saved = []
    for i, im in enumerate(imgs):
        name = im.get("filename", f"out_{i}")
        data = im.get("data") or im.get("image")
        if im.get("type") == "s3_url" or (isinstance(data, str) and data.startswith("http")):
            urllib.request.urlretrieve(data, args.out)
            saved.append(args.out)
        elif data:
            dest = args.out if name.endswith(".mp4") or len(imgs) == 1 else f"{args.out}.{i}.{name}"
            Path(dest).write_bytes(base64.b64decode(data))
            saved.append(dest)
    meta = {k: v for k, v in st.items() if k in ("delayTime", "executionTime", "workerId")}
    print("saved:", saved, "| meta:", meta)
    if not saved:
        print("NO OUTPUT FILES; raw output keys:", list(out.keys()), json.dumps(out)[:1500])


if __name__ == "__main__":
    main()
