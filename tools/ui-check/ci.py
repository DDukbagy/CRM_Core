import json, os, sys, time, urllib.request
H = {"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "Accept": "application/vnd.github+json"}
def get(u): return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H)))
sha = get("https://api.github.com/repos/DDukbagy/CRM_Core/pulls/" + os.environ.get("PR", "74"))["head"]["sha"]
for _ in range(int(sys.argv[1]) if len(sys.argv) > 1 else 60):
    runs = get(f"https://api.github.com/repos/DDukbagy/CRM_Core/actions/runs?head_sha={sha}&per_page=20")["workflow_runs"]
    if runs and all(r["status"] == "completed" for r in runs): break
    time.sleep(20)
for r in runs:
    print(f"{r['name']}: {r['status']} {r['conclusion']}  (run {r['id']})")
    jobs = get(r["jobs_url"])["jobs"]
    for j in jobs:
        print(f"   - {j['name']}: {j['status']} {j['conclusion']}")
        if j["conclusion"] == "failure":
            for st in j["steps"]:
                if st["conclusion"] == "failure": print(f"       실패 단계: {st['name']}")
