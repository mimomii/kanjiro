FROM python:3.10-slim
# コンテナ内の作業ディレクトリを設定
WORKDIR /app

# Dockerレイヤーのキャッシュを活かすため先にPython依存をインストール
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 残りのアプリケーションコードをコピー
COPY . ./

# デフォルトコマンド（実行時に引数が必要）
CMD ["python", "main.py"]
