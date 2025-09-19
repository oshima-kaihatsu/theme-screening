"""
WSGI Entry Point for Production Deployment
本番環境用WSGIエントリーポイント
"""

import os
import sys

# プロジェクトパスを追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from theme_web_app import app, init_app
from deploy_config import get_config

# 環境設定
env = os.environ.get('FLASK_ENV', 'production')
config = get_config(env)

# アプリケーション設定
app.config.from_object(config)

# 初期化
init_app()

if __name__ == '__main__':
    # Gunicornで実行される場合
    app.run()