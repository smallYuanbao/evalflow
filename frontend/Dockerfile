# EvalFlow 前端:node 构建 → nginx 托管静态产物 + 反代 /api
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
# HTTPS(Ch14):openssl 用于 entrypoint 在证书缺失时自签;生产可挂真实证书覆盖同一路径
RUN apk add --no-cache openssl
COPY frontend/nginx-gen-cert.sh /docker-entrypoint.d/40-gen-cert.sh
RUN chmod +x /docker-entrypoint.d/40-gen-cert.sh
EXPOSE 80 443
