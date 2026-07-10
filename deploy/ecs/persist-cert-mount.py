#!/usr/bin/env python3
"""Persist new LE cert mounts into /root/nginx-smartmoves/docker-compose.yml.

Idempotent: detects if the cert mount for the given domain already exists.
"""
import sys, pathlib

DOMAIN = sys.argv[1]
COMPOSE = pathlib.Path('/root/nginx-smartmoves/docker-compose.yml')

needle = '- /etc/letsencrypt/live/mcp-en.smartmoves.com.cn/privkey.pem:/etc/nginx/certs/mcp-en.smartmoves.com.cn.key:ro\n'
add = f'''      # -- {DOMAIN} (added by publish.ps1) --------------------------
      - /etc/letsencrypt/live/{DOMAIN}/fullchain.pem:/etc/nginx/certs/{DOMAIN}.crt:ro
      - /etc/letsencrypt/live/{DOMAIN}/privkey.pem:/etc/nginx/certs/{DOMAIN}.key:ro

'''

text = COMPOSE.read_text()
if f'{DOMAIN}/fullchain.pem' in text:
    print('compose-file: already present, no change')
elif needle not in text:
    print('compose-file: anchor needle not found, skipping')
    sys.exit(2)
else:
    new = text.replace(needle, needle + add)
    COMPOSE.write_text(new)
    print('compose-file: mounts persisted')
