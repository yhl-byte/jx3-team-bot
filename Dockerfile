FROM python:3.13.2-alpine3.21

WORKDIR /app
COPY . .

EXPOSE 8080

# 安装必要的依赖
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    git \
    # 添加字体支持
    fontconfig \
    ttf-dejavu \
    # 添加wkhtmltox依赖
    libstdc++ \
    libx11 \
    libxrender \
    libxext \
    freetype \
    fontconfig

# 安装Python依赖
RUN pip install nb-cli
RUN pip install nonebot[fastapi]
RUN pip install -r requirements.txt

# 设置环境变量
ENV LD_LIBRARY_PATH=/usr/local/lib:/usr/lib

CMD ["nb", "run", "--host", "0.0.0.0"]