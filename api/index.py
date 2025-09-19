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
    """最新スクリーニング結果取得"""
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_gainers': 0,
            'themes_detected': 0
        },
        'message': 'Demo mode - screening functionality available',
        'themes': [],
        'watchlist': []
    })

# Export the app for Vercel