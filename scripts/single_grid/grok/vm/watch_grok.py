import json, os, subprocess, time, urllib.request
G = "<vm>/grok"
env = dict(l.strip().split("=", 1) for l in open("<vm>/luna/.env.azure") if "=" in l and not l.startswith("#"))
ep = env["AZURE_LUNA_ENDPOINT"].strip().rstrip("/") + "/openai/v1/chat/completions"
key = env["AZURE_LUNA_API_KEY"].strip()
def probe():
    body = json.dumps({"model": "grok-4.6", "messages": [{"role": "user", "content": "Reply with the single word: ok"}], "max_completion_tokens": 200}).encode()
    t = time.time()
    try:
        r = urllib.request.urlopen(urllib.request.Request(ep, data=body, headers={"api-key": key, "Content-Type": "application/json"}), timeout=60)
        json.load(r); return f"200 {time.time()-t:.1f}s", time.time() - t < 30
    except Exception as e:
        return repr(e)[:120], False
ok = 0; start = time.time()
while time.time() - start < 24 * 3600:
    msg, healthy = probe(); ok = ok + 1 if healthy else 0
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, f"healthy-streak {ok}", flush=True)
    if ok >= 3:
        subprocess.run(["tmux", "new-session", "-d", "-s", "grokretry2", f"{G}/plan/run_retry2.sh"])
        time.sleep(3)
        subprocess.run(["tmux", "new-session", "-d", "-s", "grokretry2guard",
                        f"python3 {G}/paper/scripts/single_grid/grok/guard.py {G}/plan/retry2-configs/runs grokretry2 --cap 75 --max-mean 1.0 >> {G}/plan/logs/retry2-guard.log 2>&1"])
        print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "LAUNCHED retry2", flush=True)
        break
    time.sleep(300)
else:
    print("GAVE UP after 24 h", flush=True)
