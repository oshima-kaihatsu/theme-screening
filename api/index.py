from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import json
from datetime import datetime, timedelta
import os

# Simple Flask app for Vercel
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

@app.route('/')
def index():
    """メインページ - HTMLを返す"""
    return render_template('index.html')

@app.route('/api/screening/status', methods=['GET'])
def get_status():
    """ステータス取得"""
    return jsonify({
        'is_running': False,
        'auto_refresh': False,
        'last_update': None,
        'message': 'System is ready'
    })

@app.route('/api/screening/latest', methods=['GET'])
def get_latest_screening():
    """最新スクリーニング結果取得 - サンプルデータ付き"""
    # サンプルデータを返す（実際のYahoo Finance APIは複雑なため）
    sample_themes = [
        {
            'name': '🔥 半導体関連',
            'strength': 85,
            'stocks': [
                {'symbol': '6857 アドバンテスト', 'change': '+5.8'},
                {'symbol': '8035 東京エレクトロン', 'change': '+4.2'},
                {'symbol': '6502 東芝', 'change': '+3.9'},
                {'symbol': '6762 TDK', 'change': '+3.5'}
            ]
        },
        {
            'name': '⚡ AI・人工知能',
            'strength': 78,
            'stocks': [
                {'symbol': '3655 ブレインパッド', 'change': '+7.2'},
                {'symbol': '2158 FRONTEO', 'change': '+6.5'},
                {'symbol': '3993 PKSHA', 'change': '+4.8'},
                {'symbol': '4312 サイバー', 'change': '+3.2'}
            ]
        },
        {
            'name': '🌱 再生可能エネルギー',
            'strength': 72,
            'stocks': [
                {'symbol': '9519 レノバ', 'change': '+4.5'},
                {'symbol': '1407 ウエストHD', 'change': '+3.8'},
                {'symbol': '6255 エヌ・ピー・シー', 'change': '+3.2'},
                {'symbol': '9517 イーレックス', 'change': '+2.9'}
            ]
        }
    ]

    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_gainers': 12,
            'themes_detected': 3,
            'avg_change': 4.6
        },
        'message': 'スクリーニング完了',
        'themes': sample_themes,
        'watchlist': [
            {'symbol': '6857', 'name': 'アドバンテスト', 'reason': '半導体テスターのリーダー'},
            {'symbol': '3655', 'name': 'ブレインパッド', 'reason': 'AI関連の急騰'},
            {'symbol': '9519', 'name': 'レノバ', 'reason': '再エネ政策期待'}
        ]
    })

# Export the app for Vercel