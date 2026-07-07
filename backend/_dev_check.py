"""一次性最终验证脚本。"""
import urllib.request
import urllib.error
import json


def fmt(label: str, status: str, *extra) -> None:
    bits = " ".join(extra)
    print(f"[{label}] {status} {bits}".rstrip())


print("=" * 60)
print(" Learning Hub 本机启动验证总结")
print("=" * 60)

# 后端 health
req = urllib.request.Request("http://127.0.0.1:18765/api/public/health")
data = json.loads(urllib.request.urlopen(req).read())
uptime = data["data"]["uptimeSec"]
fmt("Backend", "UP", f"uptime={uptime}s")

# 前端代理
req = urllib.request.Request("http://127.0.0.1:15173/")
resp = urllib.request.urlopen(req)
html = resp.read().decode("utf-8", errors="ignore")
fmt("Frontend", str(resp.status), f"len={len(html)} lang={html.split('lang=')[1].split('\"')[1] if 'lang=' in html else '?'}")

# Vite 代理 + 课件搜索
req = urllib.request.Request("http://127.0.0.1:15173/api/public/coursewares/search?q=Vue")
data = json.loads(urllib.request.urlopen(req).read())
fmt("Vite Proxy", "200", f"q=Vue total={data['data']['total']} source={data['data']['source']}")

# 单素材
req = urllib.request.Request("http://127.0.0.1:18765/api/public/materials/1")
data = json.loads(urllib.request.urlopen(req).read())
m = data["data"]
fmt("Material", m["type"], f"name={m['name']} size={m['sizeBytes']}B previewReady={m['previewReady']}")

# 流式
req = urllib.request.Request("http://127.0.0.1:18765/api/public/materials/1/stream")
resp = urllib.request.urlopen(req)
fmt("Stream", str(resp.status),
    f"CT={resp.headers.get('Content-Type')}",
    f"CD={resp.headers.get('Content-Disposition')}")

# 受限课件素材(无 token)
req = urllib.request.Request("http://127.0.0.1:18765/api/public/materials/2/stream")
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    body = json.loads(e.read())
    fmt("ACL", str(e.code), f"code={body['code']}")

# 受限课件 unlock
import urllib.request
raw_token = "hl28oezy3myddfh2iezzm9uu"
req = urllib.request.Request(
    "http://127.0.0.1:18765/api/public/coursewares/2/unlock",
    data=json.dumps({"token": raw_token}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
resp = urllib.request.urlopen(req)
unlock = json.loads(resp.read())
th = unlock["data"]["tokenHash"]
fmt("Unlock", "200", f"tokenHash={th[:16]}... coursewareIds={unlock['data']['coursewareIds']}")

# 受限素材带 token
req = urllib.request.Request(
    "http://127.0.0.1:18765/api/public/materials/2/stream",
    headers={"X-Token-Hash": th},
)
resp = urllib.request.urlopen(req)
fmt("Stream (token)", str(resp.status),
    f"CT={resp.headers.get('Content-Type')}",
    f"CD={resp.headers.get('Content-Disposition')}")

print()
print("=" * 60)
print(" 服务监听端口")
print("=" * 60)
print("  Backend (FastAPI/uvicorn): http://127.0.0.1:18765")
print("  Backend admin docs:        http://127.0.0.1:18765/api/docs")
print("  Frontend (Vite dev):       http://127.0.0.1:15173")
print("  后台登录 token:            demo (POST /api/auth/admin {\"token\":\"demo\"})")
print("  种子 token 明文:           hl28oezy3myddfh2iezzm9uu")
print("=" * 60)
