"""阶段 3 后端业务流程 e2e 验证脚本。"""
import json
import sys

import urllib.request
import urllib.error
import http.cookiejar


BASE = "http://localhost:8000"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def req(method, path, body=None, headers=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with opener.open(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = {"raw": "<non-json>"}
        return e.code, payload


def assert_eq(label, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {label}: got={got} want={want}")
    if not ok:
        sys.exit(1)


def assert_in(label, got, container):
    ok = got in container
    print(f"{'PASS' if ok else 'FAIL'}  {label}: got={got} in {container}")
    if not ok:
        sys.exit(1)


# 第二套 cookie jar:模拟新访客(无 Admin session)
cj2 = http.cookiejar.CookieJar()
opener2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj2))


def req2(method, path, body=None, headers=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with opener2.open(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = {"raw": "<non-json>"}
        return e.code, payload


# ===== 1. Login =====
print("[1] login...")
code, body = req("POST", "/api/auth/admin", {"token": "demo"})
assert_eq("login", code, 200)
assert_eq("login.code", body.get("code"), "ok")

# ===== 2. Find leaf category =====
print("[2] list categories...")
code, body = req("GET", "/api/admin/categories")
print("category tree:", body["code"], "roots:", len(body["data"]))

# 如果还没有 3 级叶子,自动建立一套
def _flatten(node, acc):
    acc.append(node)
    for ch in node.get("children", []):
        _flatten(ch, acc)
    return acc


flat = []
for r in body["data"]:
    _flatten(r, flat)
leaf = next((n for n in flat if n["level"] == 3), None)
if leaf is None:
    print("[2.1] bootstrapping 3-level category chain ...")
    code, body = req("POST", "/api/admin/categories", {"name": "Root"})
    rid = body["data"]["id"]
    code, body = req("POST", "/api/admin/categories", {"name": "Mid", "parentId": rid})
    mid_id = body["data"]["id"]
    code, body = req("POST", "/api/admin/categories", {"name": "Leaf", "parentId": mid_id})
    LEAF_ID = body["data"]["id"]
else:
    LEAF_ID = leaf["id"]
print(f"leaf category id = {LEAF_ID}")
assert LEAF_ID is not None, "No leaf category found"

# ===== 3. Create access token =====
print("[3] create token...")
import time
_label = f"team-{int(time.time())}"
code, body = req("POST", "/api/admin/access-tokens", {"label": _label})
assert_eq("create_token", code, 201)
TOKEN_ID = int(body["data"]["id"])
TOKEN_VALUE = body["data"]["value"]
TOKEN_HASH = body["data"]["valueHash"]
print(f"token id={TOKEN_ID} value={TOKEN_VALUE}")

# ===== 4. List tokens =====
code, body = req("GET", "/api/admin/access-tokens")
assert_eq("list_tokens", code, 200)
assert_in("list_tokens.code", body["code"], ["ok"])

# ===== 5. Create RESTRICTED courseware =====
code, body = req(
    "POST",
    "/api/admin/coursewares",
    {
        "title": "Restricted Course",
        "categoryId": LEAF_ID,
        "accessMode": "RESTRICTED",
        "tokenIds": [TOKEN_ID],
    },
)
assert_eq("create_restricted_courseware", code, 201)
RESTRICTED_ID = body["data"]["id"]
assert_eq("restricted mode", body["data"]["accessMode"], "RESTRICTED")
print(f"restricted courseware id={RESTRICTED_ID}")

# ===== 6. Create OPEN courseware =====
code, body = req(
    "POST",
    "/api/admin/coursewares",
    {
        "title": "Open Course",
        "categoryId": LEAF_ID,
        "accessMode": "OPEN",
    },
)
assert_eq("create_open_courseware", code, 201)
OPEN_ID = body["data"]["id"]

# ===== 7. RESTRICTED requires token: POST without token should fail with courseware_token_required =====
code, body = req(
    "POST",
    "/api/admin/coursewares",
    {
        "title": "Bad Restricted",
        "categoryId": LEAF_ID,
        "accessMode": "RESTRICTED",
        "tokenIds": [],
    },
)
assert_eq("restricted_no_token_blocked", code, 400)
assert_eq("restricted_no_token_code", body.get("code"), "courseware_token_required")

# ===== 8. R-01 已放开:课件可挂接任意层级节点,不再要求 3 级叶子 =====
# 取根节点 id (Root),创建课件到 root,应返回 201
root_nodes = [n for n in flat if n["level"] == 1]
if root_nodes:
    code, body = req(
        "POST",
        "/api/admin/coursewares",
        {
            "title": "On Root",
            "categoryId": root_nodes[0]["id"],
            "accessMode": "OPEN",
        },
    )
    assert_eq("any_level_allowed", code, 201)
else:
    print("(skip) no root category to assert any-level-allowed")

# ===== 9. Public search =====
code, body = req("GET", "/api/public/coursewares/search?q=Course")
assert_eq("public_search", code, 200)
print(f"search hits: {len(body['data']['items'])}")

# ===== 10. Public GET restricted without token-hash → 403 =====
code, body = req("GET", f"/api/public/coursewares/{RESTRICTED_ID}")
assert_eq("restricted_no_unlock", code, 403)
assert_eq("restricted_no_unlock_code", body.get("code"), "courseware_acl_locked")

# ===== 11. Unlock with wrong token → 401 =====
code, body = req2("POST", f"/api/public/coursewares/{RESTRICTED_ID}/unlock", {"token": "wrong"})
assert_eq("unlock_wrong", code, 401)
assert_eq("unlock_wrong_code", body.get("code"), "invalid_token")

# ===== 12. Unlock with correct token → 200 + cookie =====
# (req2 使用专属 cookie jar,模拟新访客)


code, body = req2("POST", f"/api/public/coursewares/{RESTRICTED_ID}/unlock", {"token": TOKEN_VALUE})
assert_eq("unlock_ok", code, 200)
assert_eq("unlock_hash_match", body["data"]["tokenHash"], TOKEN_HASH)

# ===== 13. Public GET restricted WITH cookie → 200 =====
code, body = req2("GET", f"/api/public/coursewares/{RESTRICTED_ID}")
assert_eq("restricted_with_cookie", code, 200)
assert_eq("restricted_with_cookie_title", body["data"]["title"], "Restricted Course")

# ===== 14. Public GET OPEN without cookie → 200 =====
code, body = req("GET", f"/api/public/coursewares/{OPEN_ID}")
assert_eq("open_no_cookie", code, 200)

# ===== 15. Regenerate token → old plaintext invalid =====
code, body = req("POST", f"/api/admin/access-tokens/{TOKEN_ID}/regenerate")
assert_eq("regenerate", code, 200)
NEW_VALUE = body["data"]["value"]
NEW_HASH = body["data"]["valueHash"]
assert_eq("hash_changed", NEW_HASH != TOKEN_HASH, True)

# old token no longer unlocks
code, body = req("POST", f"/api/public/coursewares/{RESTRICTED_ID}/unlock", {"token": TOKEN_VALUE})
assert_eq("old_token_invalid", code, 401)

# ===== 16. R-12: downgrade RESTRICTED → OPEN should auto-clear tokens =====
code, body = req(
    "PUT",
    f"/api/admin/coursewares/{RESTRICTED_ID}",
    {"accessMode": "OPEN"},
)
assert_eq("downgrade_to_open", code, 200)
assert_eq("downgrade_to_open.mode", body["data"]["accessMode"], "OPEN")
assert_eq("downgrade_to_open.tokens_cleared", body["data"]["tokenIds"], [])

# ===== 17. R-10: cannot delete token referenced by courseware =====
# Create new token + courseware, then attempt delete
code, body = req("POST", "/api/admin/access-tokens", {"label": "team-B"})
TOKEN_B_ID = int(body["data"]["id"])
code, body = req(
    "POST",
    "/api/admin/coursewares",
    {
        "title": "Refs B",
        "categoryId": LEAF_ID,
        "accessMode": "RESTRICTED",
        "tokenIds": [TOKEN_B_ID],
    },
)
assert_eq("refs_b_create", code, 201)
code, body = req("DELETE", f"/api/admin/access-tokens/{TOKEN_B_ID}")
assert_eq("delete_referenced_blocked", code, 422)
assert_eq("delete_referenced_code", body.get("code"), "token_referenced")

# ===== 18. R-11: cannot delete last active token =====
# 先清空除目标外的所有 token,仅留一个,然后再试删除
print("[18] R-11 last-token-required ...")
# 第一步:把所有引用任何 token 的 RESTRICTED 课件全部降级为 OPEN
code, body = req("GET", "/api/admin/coursewares", {"accessMode": "RESTRICTED", "size": 200})
print(f"  restricted coursewares to downgrade: {len(body['data']['items'])}")
for cw in body["data"]["items"]:
    req("PUT", f"/api/admin/coursewares/{cw['id']}", {"accessMode": "OPEN"})

# 第二步:删除所有非 keep_id 的 token
code, body = req("GET", "/api/admin/access-tokens", {"page": 1, "size": 200})
keep_id = TOKEN_ID
print(f"  keep_id={keep_id} tokens before cleanup: {[t['id'] for t in body['data']['items']]}")
for t in body["data"]["items"]:
    if t["id"] != keep_id:
        c, b = req("DELETE", f"/api/admin/access-tokens/{t['id']}")
        if c != 200:
            print(f"  WARN: failed to delete token {t['id']}: {c} {b}")

# 第三步:验证现在只剩 1 个 token
code, body = req("GET", "/api/admin/access-tokens", {"page": 1, "size": 200})
print(f"  remaining tokens: {[t['id'] for t in body['data']['items']]}")
assert_eq("only_one_token_left", len(body["data"]["items"]), 1)
# 第四步:删除唯一的 token → 应该 422 last_token_required
code, body = req("DELETE", f"/api/admin/access-tokens/{keep_id}")
print(f"  final delete keep_id={keep_id}: c={code} body={body}")
assert_eq("last_token_blocked", code, 422)
assert_eq("last_token_code", body.get("code"), "last_token_required")

print("\n=== ALL STAGE-3 BACKEND BUSINESS RULES PASS ===")