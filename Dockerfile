FROM python:3.10-slim
# コンテナ内の作業ディレクトリを設定
WORKDIR /app

# Dockerレイヤーのキャッシュを活かすため先にPython依存をインストール
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 残りのアプリケーションコードをコピー
COPY . ./

CMD ["python", "main.py"]
