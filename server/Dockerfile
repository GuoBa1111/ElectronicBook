# 使用自定义基础镜像
FROM myapp-base:latest

# 先复制 requirements.txt 并安装依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# 复制应用代码并设置所有权
COPY --chown=appuser:appuser . .

# 创建数据目录并设置正确的权限
RUN mkdir -p /app/data/websites && \
    chown -R appuser:appuser /app/data && \
    chmod -R 755 /app/data

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 3000

CMD ["python3", "server-docker.py"]