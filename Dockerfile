# 使用官方提供的包含 Playwright 环境的镜像，省去安装系统依赖的麻烦
FROM mcr.microsoft.com/playwright/python:v1.40.0-focal

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖 (在此处添加 api 相关的依赖)
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install fastapi uvicorn pymongo motor

# 复制项目代码
COPY . .

# 暴露 API 端口
EXPOSE 8000

# 启动命令 (启动你新建的 FastAPI 服务)
CMD ["uvicorn", "server_main:app", "--host", "0.0.0.0", "--port", "8000"]