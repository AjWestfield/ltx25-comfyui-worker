#!/usr/bin/env python3
"""Submit a batch of LTX-2.5 i2v jobs to the RunPod endpoint in one shot.

All jobs queue immediately and run back-to-back on the same warm worker,
so only the first clip pays the cold start.

Usage:
  RUNPOD_API_KEY=... python3 batch_ltx.py <endpoint_id> <batch.json> [--outdir DIR]

batch.json: [{"image": "path.png", "prompt": "...", "duration": 15, "seed": 1}, ...]
Fields other than "image" are optional; omitted ones keep workflow defaults.
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
    ap.add_argument("batch_file")
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()
    key = os.environ["RUNPOD_API_KEY"]
    base = f"https://api.runpod.ai/v2/{args.endpoint_id}"
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    jobs = []
    for i, spec in enumerate(json.loads(Path(args.batch_file).read_text())):
        wf = json.loads(WORKFLOW.read_text())
        if spec.get("prompt"):
            wf["398:376"]["inputs"]["value"] = spec["prompt"]
        if spec.get("duration"):
            wf["398:362"]["inputs"]["value"] = spec["duration"]
        if spec.get("seed") is not None:
            wf["398:339"]["inputs"]["noise_seed"] = spec["seed"]
            wf["398:338"]["inputs"]["noise_seed"] = spec["seed"] + 1
        img_b64 = base64.b64encode(Path(spec["image"]).read_bytes()).decode()
        payload = {"input": {"workflow": wf, "images": [{"name": "startframe.png", "image": img_b64}]}}
        sub = api(f"{base}/run", key, payload)
        jobs.append({"i": i, "id": sub["id"], "done": False})
        print(f"clip {i}: job {sub['id']} queued", flush=True)

    t0 = time.time()
    while any(not j["done"] for j in jobs):
        time.sleep(15)
        for j in jobs:
            if j["done"]:
                continue
            st = api(f"{base}/status/{j['id']}", key)
            status = st.get("status")
            if status in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
                j["done"] = True
                if status == "COMPLETED":
                    out = (st.get("output") or {}).get("images") or []
                    for im in out:
                        data = im.get("data") or im.get("image")
                        if data and not str(data).startswith("http"):
                            dest = outdir / f"clip_{j['i']}.mp4"
                            dest.write_bytes(base64.b64decode(data))
                            print(f"clip {j['i']}: saved {dest} (exec {st.get('executionTime')}ms)", flush=True)
                        elif data:
                            urllib.request.urlretrieve(data, outdir / f"clip_{j['i']}.mp4")
                            print(f"clip {j['i']}: saved from URL", flush=True)
                else:
                    print(f"clip {j['i']}: {status} {json.dumps(st)[:400]}", flush=True)
    print(f"batch done in {int(time.time()-t0)}s")


if __name__ == "__main__":
    main()
