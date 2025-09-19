"""
Webダッシュボード
リアルタイムでスクリーニング結果を可視化
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import plotly.graph_objs as go
import plotly.utils
import pandas as pd
import json
from datetime import datetime, timedelta
import threading
import time
from loguru import logger
import sys
import os

# パスを追加
sys.path.append('src')

from database import DatabaseManager
from data_fetcher import DataFetcher
from analyzer import StockAnalyzer
from advanced_analyzer import AdvancedTechnicalAnalyzer
from realtime_monitor import RealtimeMonitor, PositionManager
from utils import load_config, setup_logging


# Flask アプリケーション設定
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# グローバル変数
db_manager = None
data_fetcher = None
analyzer = None
advanced_analyzer = None
monitor = None
position_manager = None
config = None


def init_app():
    """アプリケーション初期化"""
    global db_manager, data_fetcher, analyzer, advanced_analyzer, monitor, position_manager, config

    setup_logging()
    config = load_config('config/config.yaml')

    db_manager = DatabaseManager()
    data_fetcher = DataFetcher(config)
    analyzer = StockAnalyzer(config, data_fetcher)
    advanced_analyzer = AdvancedTechnicalAnalyzer()

    # ダミーのnotifierオブジェクト（Web通知用）
    class WebNotifier:
        def send_line_notify(self, message):
            socketio.emit('alert', {'message': message}, broadcast=True)

    monitor = RealtimeMonitor(config, WebNotifier())
    position_manager = PositionManager(initial_capital=1000000)

    logger.info("Web dashboard initialized")


@app.route('/')
def index():
    """メインダッシュボードページ"""
    return render_template('dashboard.html')


@app.route('/api/screening/latest')
def get_latest_screening():
    """最新のスクリーニング結果を取得（強化版）"""
    try:
        # 緊急修正版スクリーニングを使用（Yahoo Finance制限対応）
        import quick_fix_screening
        results = quick_fix_screening.run_quick_fix_screening()

        if results and 'error' not in results:
            return jsonify({
                'status': 'success',
                'timestamp': results['timestamp'].isoformat(),
                'under_3000': results.get('under_3000', {'count': 0, 'stocks': []}),
                'range_3000_10000': results.get('range_3000_10000', {'count': 0, 'stocks': []}),
                'top_picks': results.get('top_picks', []),
                'watch_list': results.get('watch_list', []),
                'statistics': results.get('statistics', {})
            })
        else:
            return jsonify({
                'status': 'error',
                'message': results.get('error', 'スクリーニング実行中にエラーが発生しました')
            }), 500

    except Exception as e:
        logger.error(f"Error getting latest screening: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/stock/<symbol>')
def get_stock_details(symbol):
    """個別銘柄の詳細情報を取得"""
    try:
        # 価格データ取得
        price_data = data_fetcher.fetch_price_data(symbol, period='30d')

        # テクニカル指標計算
        df = price_data.get('price_data')
        if df is not None and not df.empty:
            indicators = advanced_analyzer.calculate_all_indicators(df)
        else:
            indicators = {}

        # 履歴データ取得
        history_df = db_manager.get_price_history(symbol)

        # スクリーニング履歴
        screening_history = db_manager.get_screening_history(symbol, days=30)

        return jsonify({
            'status': 'success',
            'symbol': symbol,
            'current_price': price_data.get('current_price'),
            'indicators': indicators,
            'price_history': history_df.to_dict('records') if not history_df.empty else [],
            'screening_history': screening_history.to_dict('records') if not screening_history.empty else []
        })

    except Exception as e:
        logger.error(f"Error getting stock details for {symbol}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/chart/<symbol>')
def get_chart_data(symbol):
    """チャート用データを取得"""
    try:
        # 価格データ取得
        price_data = data_fetcher.fetch_price_data(symbol, period='60d')
        df = price_data.get('price_data')

        if df is None or df.empty:
            return jsonify({'status': 'no_data'})

        # テクニカル指標計算
        indicators = advanced_analyzer.calculate_all_indicators(df)

        # Plotlyチャート作成
        candlestick = go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='価格'
        )

        # ボリンジャーバンド
        bb = indicators.get('bollinger', {})
        bb_upper = go.Scatter(
            x=df.index,
            y=[bb.get('upper')] * len(df),
            name='BB Upper',
            line=dict(color='gray', width=1, dash='dash')
        )
        bb_lower = go.Scatter(
            x=df.index,
            y=[bb.get('lower')] * len(df),
            name='BB Lower',
            line=dict(color='gray', width=1, dash='dash')
        )

        # 出来高
        volume_trace = go.Bar(
            x=df.index,
            y=df['Volume'],
            name='出来高',
            yaxis='y2',
            marker=dict(color='lightblue')
        )

        # レイアウト
        layout = go.Layout(
            title=f'{symbol} チャート',
            xaxis=dict(title='日付'),
            yaxis=dict(title='価格', side='left'),
            yaxis2=dict(title='出来高', side='right', overlaying='y'),
            hovermode='x unified'
        )

        fig = go.Figure(data=[candlestick, bb_upper, bb_lower, volume_trace], layout=layout)

        return jsonify({
            'status': 'success',
            'chart': json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig))
        })

    except Exception as e:
        logger.error(f"Error getting chart data for {symbol}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/monitoring/status')
def get_monitoring_status():
    """リアルタイム監視状況を取得"""
    try:
        status = monitor.get_monitoring_status()

        # ポジション管理状況も追加
        portfolio_status = position_manager.get_portfolio_status()

        return jsonify({
            'status': 'success',
            'monitoring': status,
            'portfolio': portfolio_status
        })

    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/monitoring/add', methods=['POST'])
def add_monitoring_stock():
    """監視銘柄を追加"""
    try:
        data = request.json
        symbol = data.get('symbol')
        entry_price = data.get('entry_price')
        stop_loss = data.get('stop_loss')
        take_profit = data.get('take_profit')

        monitor.add_stock(symbol, entry_price, stop_loss, take_profit)

        return jsonify({
            'status': 'success',
            'message': f'{symbol} added to monitoring'
        })

    except Exception as e:
        logger.error(f"Error adding monitoring stock: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/monitoring/remove/<symbol>', methods=['DELETE'])
def remove_monitoring_stock(symbol):
    """監視銘柄を削除"""
    try:
        monitor.remove_stock(symbol)

        return jsonify({
            'status': 'success',
            'message': f'{symbol} removed from monitoring'
        })

    except Exception as e:
        logger.error(f"Error removing monitoring stock: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/performance')
def get_performance_stats():
    """パフォーマンス統計を取得"""
    try:
        # 30日間の統計
        stats_30d = db_manager.get_performance_stats(days=30)

        # 7日間の統計
        stats_7d = db_manager.get_performance_stats(days=7)

        # トップパフォーマー
        top_performers = db_manager.get_top_performers(days=30, limit=10)

        return jsonify({
            'status': 'success',
            'stats_30d': stats_30d,
            'stats_7d': stats_7d,
            'top_performers': top_performers.to_dict('records') if not top_performers.empty else []
        })

    except Exception as e:
        logger.error(f"Error getting performance stats: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/positions')
def get_positions():
    """ポジション一覧を取得"""
    try:
        # 現在のポジション
        open_positions = db_manager.get_position_history(status='open')

        # クローズドポジション（最新10件）
        closed_positions = db_manager.get_position_history(status='closed').head(10)

        return jsonify({
            'status': 'success',
            'open_positions': open_positions.to_dict('records') if not open_positions.empty else [],
            'closed_positions': closed_positions.to_dict('records') if not closed_positions.empty else []
        })

    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/screening/run', methods=['POST'])
def run_screening():
    """スクリーニング実行"""
    try:
        logger.info("Manual screening requested")

        # 緊急修正版スクリーニング実行（Yahoo Finance制限対応）
        import quick_fix_screening
        results = quick_fix_screening.run_quick_fix_screening()

        # データベースに保存
        if results and 'error' not in results:
            db_manager.save_screening_results(results)

            return jsonify({
                'status': 'success',
                'message': 'スクリーニング完了',
                'processed_count': results.get('total_processed', 0),
                'filtered_count': results.get('filtered_count', 0),
                'top_picks_count': len(results.get('top_picks', [])),
                'execution_time': results.get('execution_time', 0)
            })
        else:
            return jsonify({
                'status': 'error',
                'message': results.get('error', 'スクリーニング実行中にエラーが発生しました')
            }), 500

    except Exception as e:
        logger.error(f"Error running screening: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# WebSocket イベントハンドラー
@socketio.on('connect')
def handle_connect():
    """クライアント接続"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to server'})


@socketio.on('disconnect')
def handle_disconnect():
    """クライアント切断"""
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on('start_monitoring')
def handle_start_monitoring():
    """リアルタイム監視開始"""
    try:
        if not monitor.is_running:
            monitor.start_monitoring()
            emit('monitoring_started', {'message': 'Monitoring started'})

            # 定期的に状態を配信するスレッド開始
            threading.Thread(target=broadcast_monitoring_status, daemon=True).start()
        else:
            emit('monitoring_already_running', {'message': 'Monitoring already running'})

    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        emit('error', {'message': str(e)})


@socketio.on('stop_monitoring')
def handle_stop_monitoring():
    """リアルタイム監視停止"""
    try:
        if monitor.is_running:
            monitor.stop_monitoring()
            emit('monitoring_stopped', {'message': 'Monitoring stopped'})
        else:
            emit('monitoring_not_running', {'message': 'Monitoring not running'})

    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        emit('error', {'message': str(e)})


def broadcast_monitoring_status():
    """監視状況を定期的にブロードキャスト"""
    while monitor.is_running:
        try:
            status = monitor.get_monitoring_status()
            socketio.emit('monitoring_update', status)
            time.sleep(5)  # 5秒ごとに更新

        except Exception as e:
            logger.error(f"Error broadcasting status: {e}")
            time.sleep(10)


def run_periodic_screening():
    """定期的にスクリーニングを実行"""
    while True:
        try:
            current_time = datetime.now()
            hour = current_time.hour
            minute = current_time.minute

            # 市場時間中は30分ごとにスクリーニング
            if 9 <= hour < 15 and minute in [0, 30]:
                logger.info("Running periodic screening")

                # スクリーニング実行（簡易版）
                stock_list = data_fetcher.fetch_stock_list()
                results = []

                for _, stock in stock_list.iterrows():
                    try:
                        symbol = stock['symbol']
                        price_data = data_fetcher.fetch_price_data(symbol)

                        if price_data:
                            stock_data = {
                                'symbol': symbol,
                                'name': stock['name'],
                                **price_data
                            }

                            score = analyzer.calculate_score(stock_data)
                            results.append(score)

                    except Exception as e:
                        logger.warning(f"Error processing {symbol}: {e}")

                # 結果をブロードキャスト
                if results:
                    top_stocks = sorted(results, key=lambda x: x.get('total_score', 0), reverse=True)[:10]
                    socketio.emit('screening_update', {
                        'timestamp': current_time.isoformat(),
                        'stocks': top_stocks
                    })

            time.sleep(60)  # 1分ごとにチェック

        except Exception as e:
            logger.error(f"Error in periodic screening: {e}")
            time.sleep(60)


if __name__ == '__main__':
    # アプリケーション初期化
    init_app()

    # 定期スクリーニングスレッド開始（オプション）
    # threading.Thread(target=run_periodic_screening, daemon=True).start()

    # サーバー起動
    logger.info("Starting web dashboard on http://localhost:5000")
    socketio.run(app, debug=True, port=5000)