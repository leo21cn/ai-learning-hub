import urllib.request
import urllib.error
import json

print("=== 5173 实例代理到哪个后端？===")
print("  /api/public/coursewares/search?q=")
req = urllib.request.Request("http://127.0.0.1:5173/api/public/coursewares/search?q=")
resp = urllib.request.urlopen(req, timeout=3)
data = json.loads(resp.read())
print("  status:", resp.status)
print("  total:", data["data"]["total"])
print("  source:", data["data"]["source"])
if data["data"]["items"]:
    item = data["data"]["items"][0]
    print("  first item:")
    print("    id:", item.get("id"))
    print("    title:", item.get("title"))
    print("    accessMode:", item.get("accessMode"))

print()
print("=== 5173 实例里 id=12 课件 ===")
try:
    req = urllib.request.Request("http://127.0.0.1:5173/api/public/coursewares/12")
    resp = urllib.request.urlopen(req, timeout=3)
    data = json.loads(resp.read())
    item = data["data"]
    print("  title:", item.get("title"))
    print("  accessMode:", item.get("accessMode"))
    print("  materials:")
    for m in item.get("materials", []):
        print("    id={} type={} name={} streamUrl={}".format(
            m["id"], m["type"], m["name"], m.get("streamUrl"), m.get("downloadUrl")
        ))
except urllib.error.HTTPError as e:
    body = json.loads(e.read())
    print("  status:", e.code, body.get("code"))
