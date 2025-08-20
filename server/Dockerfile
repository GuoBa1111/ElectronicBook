FROM node:10.23-buster AS builder

# 在 builder 阶段安装 gitbook-cli
RUN npm install -g gitbook-cli

# 预先下载 GitBook 3.2.3
RUN gitbook fetch 3.2.3

# 修改 copyPluginAssets.js 文件，禁用确认提示
RUN sed -i.bak 's/confirm: true/confirm: false/g' \
    /root/.gitbook/versions/3.2.3/lib/output/website/copyPluginAssets.js

# 运行阶段：最终镜像
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/appuser
ENV GITBOOK_DIR=/home/appuser/.gitbook

# 添加一个非root用户来运行应用
RUN useradd -m -u 1000 appuser

# 安装 Python 和基础工具
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates curl wget git python3 python3-venv python3-pip \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# 将 Node.js 和 gitbook-cli 从 builder 阶段复制到最终镜像
COPY --from=builder /usr/local /usr/local

# 确保 Node.js 可执行文件权限正确
RUN chmod -R 755 /usr/local/lib/node_modules /usr/local/bin

# 设置工作目录
WORKDIR /app

# 复制应用代码并设置所有权
COPY --chown=appuser:appuser . .

# 创建数据目录并设置正确的权限
RUN mkdir -p /app/data/websites && \
    chown -R appuser:appuser /app/data && \
    chmod -R 755 /app/data

# 创建 GitBook 目录并设置权限
RUN mkdir -p $GITBOOK_DIR && \
    chown -R appuser:appuser $GITBOOK_DIR && \
    chmod -R 755 $GITBOOK_DIR

# 将 GitBook 相关文件从构建阶段复制到最终镜像
COPY --from=builder --chown=appuser:appuser /root/.gitbook /home/appuser/.gitbook

# 修复 GitBook 相关文件的权限
RUN chown -R appuser:appuser /home/appuser/.gitbook && \
    chmod -R 755 /home/appuser/.gitbook

# 创建一个符号链接，确保 GitBook 使用正确的目录
RUN ln -sf /home/appuser/.gitbook /root/.gitbook

# Python 虚拟环境
RUN python3 -m venv /venv
ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:$PATH"

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt || true

# 切换到非root用户
USER appuser

# 设置环境变量，确保 GitBook 使用正确的目录
ENV NODE_PATH=/usr/local/lib/node_modules

# 暴露端口
EXPOSE 5000

CMD ["python3", "server-docker.py"]