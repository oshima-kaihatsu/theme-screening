"""
テーマ関連銘柄スクリーニング Webアプリケーション
Theme-Based Stock Screening Web Application
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
from datetime import datetime, timedelta
import threading
import time
from theme_screener import ThemeScreener
from advanced_theme_screener import AdvancedThemeScreener
from practical_theme_screener import PracticalThemeScreener
import os
from loguru import logger

app = Flask(__name__)
CORS(app)

# グローバル変数
screener = None
advanced_screener = None
practical_screener = None
latest_report = None
is_running = False
auto_refresh = False
last_update = None

def init_app():
    """アプリケーション初期化"""
    global screener, advanced_screener, practical_screener
    screener = ThemeScreener()
    advanced_screener = AdvancedThemeScreener()
    practical_screener = PracticalThemeScreener()
    logger.info("Theme screening web app initialized")

@app.route('/')
def index():
    """メインページ"""
    return render_template('theme_dashboard.html')

@app.route('/api/screening/run', methods=['POST'])
def run_screening():
    """高度スクリーニング実行"""
    global latest_report, is_running, last_update

    if is_running:
        return jsonify({'error': 'Screening already running'}), 400

    is_running = True

    try:
        min_change = request.json.get('min_change_pct', 5.0)
        analysis_type = request.json.get('analysis_type', 'advanced')

        logger.info(f"Running {analysis_type} theme screening with min_change={min_change}%")

        if analysis_type == 'advanced':
            # 実用的テーマ分析実行（実際に銘柄が見つかる）
            report = practical_screener.run_practical_screening(min_change_pct=min_change)
        else:
            # 基本分析実行
            report = screener.run_screening(min_change_pct=min_change)

        latest_report = report
        last_update = datetime.now()

        # Convert any numpy types to Python native types
        import json
        try:
            json.dumps(report)  # Test serialization
        except TypeError as e:
            logger.error(f"JSON serialization issue in report: {e}")
            # Convert the report to handle numpy types
            report = json.loads(json.dumps(report, default=str))

        return jsonify({
            'status': 'success',
            'report': report
        })

    except Exception as e:
        logger.error(f"Screening error: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        is_running = False

@app.route('/api/screening/latest', methods=['GET'])
def get_latest_screening():
    """最新スクリーニング結果取得"""
    if latest_report:
        return jsonify(latest_report)
    else:
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'summary': {'total_gainers': 0, 'themes_detected': 0},
            'message': 'No screening data available'
        })

@app.route('/api/screening/status', methods=['GET'])
def get_status():
    """ステータス取得"""
    return jsonify({
        'is_running': is_running,
        'auto_refresh': auto_refresh,
        'last_update': last_update.isoformat() if last_update else None
    })

@app.route('/api/themes/<theme_name>', methods=['GET'])
def get_theme_details(theme_name):
    """テーマ詳細取得"""
    if not latest_report:
        return jsonify({'error': 'No data available'}), 404

    for theme in latest_report.get('themes', []):
        if theme['name'] == theme_name:
            return jsonify(theme)

    return jsonify({'error': 'Theme not found'}), 404

@app.route('/api/stock/<symbol>', methods=['GET'])
def get_stock_details(symbol):
    """銘柄詳細取得"""
    try:
        # リアルタイム情報取得
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        history = ticker.history(period='1d')

        return jsonify({
            'symbol': symbol,
            'name': info.get('longName', symbol),
            'current_price': float(history['Close'][-1]) if not history.empty else 0,
            'volume': int(history['Volume'][-1]) if not history.empty else 0,
            'market_cap': info.get('marketCap', 0),
            'sector': info.get('sector', 'Unknown'),
            'news': screener.fetch_news_for_symbol(symbol) if screener else []
        })

    except Exception as e:
        logger.error(f"Error fetching stock details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/auto-refresh', methods=['POST'])
def set_auto_refresh():
    """自動更新設定"""
    global auto_refresh
    auto_refresh = request.json.get('enabled', False)

    if auto_refresh:
        # 自動更新スレッド開始
        threading.Thread(target=auto_screening_worker, daemon=True).start()

    return jsonify({'auto_refresh': auto_refresh})

def auto_screening_worker():
    """自動スクリーニングワーカー"""
    global auto_refresh, latest_report, last_update

    while auto_refresh:
        try:
            # 市場時間チェック（9:00-15:00）
            now = datetime.now()
            if 9 <= now.hour < 15 and now.weekday() < 5:
                logger.info("Running auto screening")
                report = screener.run_screening(min_change_pct=10.0)
                latest_report = report
                last_update = now

            # 30分待機
            time.sleep(1800)

        except Exception as e:
            logger.error(f"Auto screening error: {e}")
            time.sleep(300)  # エラー時は5分待機

@app.route('/api/export', methods=['GET'])
def export_report():
    """レポートエクスポート"""
    if not latest_report:
        return jsonify({'error': 'No data available'}), 404

    format_type = request.args.get('format', 'json')

    if format_type == 'json':
        return jsonify(latest_report)

    elif format_type == 'csv':
        # CSV形式に変換
        import pandas as pd
        import io

        # 監視リストをDataFrameに変換
        watchlist_df = pd.DataFrame(latest_report.get('watchlist', []))

        # CSV文字列生成
        csv_buffer = io.StringIO()
        watchlist_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_data = csv_buffer.getvalue()

        return csv_data, 200, {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename=theme_screening_report.csv'
        }

    else:
        return jsonify({'error': 'Invalid format'}), 400

@app.route('/api/history', methods=['GET'])
def get_history():
    """過去のレポート履歴取得"""
    try:
        reports_dir = 'data/reports'
        history = []

        if os.path.exists(reports_dir):
            for filename in os.listdir(reports_dir):
                if filename.startswith('theme_report_') and filename.endswith('.json'):
                    filepath = os.path.join(reports_dir, filename)
                    mtime = os.path.getmtime(filepath)

                    history.append({
                        'filename': filename,
                        'timestamp': datetime.fromtimestamp(mtime).isoformat(),
                        'size': os.path.getsize(filepath)
                    })

        # 新しい順にソート
        history.sort(key=lambda x: x['timestamp'], reverse=True)

        return jsonify(history[:20])  # 最新20件

    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return jsonify([])

@app.route('/api/history/<filename>', methods=['GET'])
def get_historical_report(filename):
    """過去レポート取得"""
    try:
        filepath = os.path.join('data/reports', filename)

        if os.path.exists(filepath) and filename.startswith('theme_report_'):
            with open(filepath, 'r', encoding='utf-8') as f:
                report = json.load(f)
            return jsonify(report)
        else:
            return jsonify({'error': 'Report not found'}), 404

    except Exception as e:
        logger.error(f"Error loading report: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 初期化
    init_app()

    # 開発サーバー起動
    logger.info("Starting theme screening web server on http://localhost:5001")
    app.run(debug=True, port=5001, host='0.0.0.0')