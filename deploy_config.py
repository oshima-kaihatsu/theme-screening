"""
デプロイメント設定ファイル
Deployment Configuration for Theme Screener

本番環境へのデプロイ用設定
"""

import os
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

class Config:
    """設定クラス"""

    # 基本設定
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

    # アプリケーション設定
    APP_NAME = 'Theme Stock Screener'
    APP_VERSION = '1.0.0'

    # サーバー設定
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5001))

    # データベース設定
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///data/screener.db')

    # キャッシュ設定
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300

    # レート制限設定
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_DEFAULT = "100 per hour"

    # CORS設定
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

    # ログ設定
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = 'data/logs/app.log'

    # スクリーニング設定
    DEFAULT_MIN_CHANGE_PCT = 10.0
    MAX_STOCKS_TO_SCAN = 500
    NEWS_FETCH_LIMIT = 10
    AUTO_REFRESH_INTERVAL = 1800  # 30分

    # セキュリティ設定
    SESSION_COOKIE_SECURE = not DEBUG
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    TESTING = False

    # 本番用データベース
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://user:pass@localhost/dbname')

    # キャッシュ設定（Redis）
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # セキュリティ強化
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'

class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    """テスト環境設定"""
    DEBUG = True
    TESTING = True
    DATABASE_URL = 'sqlite:///:memory:'

# 環境選択
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(env=None):
    """設定取得"""
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])