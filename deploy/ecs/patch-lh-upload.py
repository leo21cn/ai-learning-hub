#!/usr/bin/env python3
"""Patch the existing learning-hub 443 server block in nginx-smartmoves/nginx.conf
to bump upload limits and timeouts.

Idempotent: replaces the existing block in place. Backup before edit.
"""
import re, pathlib, datetime, shutil, sys

CONF = pathlib.Path('/root/nginx-smartmoves/nginx.conf')

text = CONF.read_text()
lines = text.splitlines(keepends=False)

# Find indices of: upstream learning_hub_frontend and the next 'server {' containing 'listen 443 ssl'
up_idx = None
for i, L in enumerate(lines):
    if re.search(r'^\s*upstream\s+learning_hub_frontend\s*\{', L):
        up_idx = i
        break
if up_idx is None:
    print('ERROR: cannot find upstream learning_hub_frontend')
    sys.exit(1)

# Find the matching server { ... } block for 443. We assume it's the next 'server {'
# after the upstream that contains 'listen 443 ssl'.
srv_start = None
for j in range(up_idx + 1, len(lines)):
    if re.search(r'^\s*server\s*\{', lines[j]):
        # Check the first 30 lines for 'listen 443 ssl'
        for k in range(j, min(j + 30, len(lines))):
            if 'listen 443 ssl' in lines[k]:
                srv_start = j
                break
        if srv_start is not None:
            break

if srv_start is None:
    print('ERROR: cannot find server { ... listen 443 ssl } after upstream')
    sys.exit(1)

# Find matching closing '}' of server block
depth = 0
srv_end = None
for j in range(srv_start, len(lines)):
    depth += lines[j].count('{') - lines[j].count('}')
    if depth == 0 and j >= srv_start:
        srv_end = j
        break
if srv_end is None:
    print('ERROR: cannot find matching } for server block')
    sys.exit(1)

print(f'upstream: line {up_idx+1}')
print(f'server:   line {srv_start+1} to {srv_end+1}')

# Backup
ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
shutil.copy2(CONF, CONF.with_suffix(f'.conf.bak.{ts}_lh_upload'))
print('backup:', CONF.with_suffix(f'.conf.bak.{ts}_lh_upload'))

# New replacement: upstream block stays as is (we already kept it at up_idx position),
# but we'll print it fresh too to standardize.
new_block = '''upstream learning_hub_frontend { server learning-hub_frontend:80; }

server {
    listen 443 ssl;
    http2 on;
    server_name learning-hub.smartmoves.com.cn;

    ssl_certificate     /etc/nginx/certs/learning-hub.smartmoves.com.cn.crt;
    ssl_certificate_key /etc/nginx/certs/learning-hub.smartmoves.com.cn.key;

    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    charset utf-8;

    # 大文件上传超时：5–10Mbps 上传 500MB 需 400–800s。
    # 默认 proxy_send_timeout = 60s 会切断上传,必须拉高。client_body_timeout 同理。
    client_max_body_size 500m;
    client_body_timeout 600s;

    location / {
        proxy_pass http://learning_hub_frontend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        # 不要把请求体缓存到磁盘,边收边转发,适合上传大文件。
        proxy_request_buffering off;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
        proxy_connect_timeout 60s;
    }
}'''

# Replace from up_idx to srv_end inclusive
new_lines = lines[:up_idx] + [new_block + '\n'] + lines[srv_end + 1:]
new_text = '\n'.join(L.rstrip('\n') for L in new_lines) + '\n'
CONF.write_text(new_text)
print(f'replaced block ({srv_end - up_idx + 1} lines) with new block ({len(new_block.splitlines())} lines)')
