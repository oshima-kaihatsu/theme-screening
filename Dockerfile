# Python Flask アプリケーション用Dockerfile
FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# システム依存関係をインストール
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 必要なファイルをコピー
COPY requirements.txt .

# Python依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# ポート5001を公開
EXPOSE 5001

# 環境変数を設定
ENV FLASK_APP=theme_web_app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# アプリケーションを実行
CMD ["python", "wsgi.py"]