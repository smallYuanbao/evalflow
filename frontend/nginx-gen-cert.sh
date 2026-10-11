#!/bin/sh
# nginx entrypoint 钩子(Ch14):证书目录为空时自签一张本地证书,保证 HTTPS 开箱可用。
# 生产部署用真实证书挂载覆盖 /etc/nginx/certs/ 即可,本脚本不会覆盖已存在的证书。
set -e

CERT_DIR=/etc/nginx/certs
CRT=$CERT_DIR/server.crt
KEY=$CERT_DIR/server.key

if [ -f "$CRT" ] && [ -f "$KEY" ]; then
    echo "[gen-cert] 证书已存在,跳过自签"
    exit 0
fi

mkdir -p "$CERT_DIR"
echo "[gen-cert] 未发现证书,生成自签名证书(localhost,365 天)"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$KEY" -out "$CRT" \
    -subj "/CN=localhost" >/dev/null 2>&1
echo "[gen-cert] 完成:$CRT"
