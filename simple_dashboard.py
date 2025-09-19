"""
シンプルなWebダッシュボード（問題解決用）
"""

from flask import Flask, render_template_string, jsonify
import sys
sys.path.append('src')

app = Flask(__name__)

# シンプルなHTMLテンプレート
TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>デイトレスクリーニング - シンプルダッシュボード</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background-color: #f8f9fa; }
        .card { border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .status-card { text-align: center; padding: 20px; }
        .display-4 { font-size: 2.5rem; font-weight: bold; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="fas fa-chart-line"></i> デイトレスクリーニング
            </a>
        </div>
    </nav>

    <div class="container-fluid mt-3">
        <div class="row">
            <div class="col-md-3">
                <div class="card text-white bg-primary">
                    <div class="card-body status-card">
                        <h5>システム状態</h5>
                        <h2 class="display-4">
                            <i class="fas fa-check-circle"></i>
                        </h2>
                        <p>正常稼働中</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-success">
                    <div class="card-body status-card">
                        <h5>今日のスクリーニング</h5>
                        <h2 class="display-4">0</h2>
                        <p>推奨銘柄</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-info">
                    <div class="card-body status-card">
                        <h5>監視中銘柄</h5>
                        <h2 class="display-4">0</h2>
                        <p>リアルタイム監視</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-warning">
                    <div class="card-body status-card">
                        <h5>稼働時間</h5>
                        <h2 class="display-4" id="uptime">0</h2>
                        <p>分</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-cogs"></i> 機能テスト</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-4">
                                <button class="btn btn-primary w-100 mb-2" onclick="testDataFetcher()">
                                    <i class="fas fa-download"></i> データ取得テスト
                                </button>
                            </div>
                            <div class="col-md-4">
                                <button class="btn btn-success w-100 mb-2" onclick="testScreening()">
                                    <i class="fas fa-filter"></i> スクリーニングテスト
                                </button>
                            </div>
                            <div class="col-md-4">
                                <button class="btn btn-info w-100 mb-2" onclick="testDatabase()">
                                    <i class="fas fa-database"></i> データベーステスト
                                </button>
                            </div>
                        </div>
                        <div id="test-results" class="mt-3"></div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-info-circle"></i> システム情報</h5>
                    </div>
                    <div class="card-body">
                        <ul class="list-group list-group-flush">
                            <li class="list-group-item">サーバー起動時刻: <span id="start-time">{{ start_time }}</span></li>
                            <li class="list-group-item">Python バージョン: <span>{{ python_version }}</span></li>
                            <li class="list-group-item">プロジェクトバージョン: <span>v2.0.0 (Phase 3完了)</span></li>
                            <li class="list-group-item">データベース: <span class="text-success">接続済み</span></li>
                            <li class="list-group-item">アクセスURL: <span>http://localhost:5000</span></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>

    <script>
        let startTime = new Date();

        function updateUptime() {
            let now = new Date();
            let minutes = Math.floor((now - startTime) / 60000);
            $('#uptime').text(minutes);
        }

        function testDataFetcher() {
            $('#test-results').html('<div class="alert alert-info">データ取得テスト実行中...</div>');

            $.get('/api/test/data', function(response) {
                if (response.status === 'success') {
                    $('#test-results').html('<div class="alert alert-success">✓ データ取得: 成功</div>');
                } else {
                    $('#test-results').html('<div class="alert alert-danger">✗ データ取得: 失敗 - ' + response.message + '</div>');
                }
            }).fail(function() {
                $('#test-results').html('<div class="alert alert-danger">✗ データ取得: API接続エラー</div>');
            });
        }

        function testScreening() {
            $('#test-results').html('<div class="alert alert-info">スクリーニングテスト実行中...</div>');

            $.get('/api/test/screening', function(response) {
                if (response.status === 'success') {
                    $('#test-results').html('<div class="alert alert-success">✓ スクリーニング: 成功（' + response.count + '銘柄処理）</div>');
                } else {
                    $('#test-results').html('<div class="alert alert-danger">✗ スクリーニング: 失敗 - ' + response.message + '</div>');
                }
            }).fail(function() {
                $('#test-results').html('<div class="alert alert-danger">✗ スクリーニング: API接続エラー</div>');
            });
        }

        function testDatabase() {
            $('#test-results').html('<div class="alert alert-info">データベーステスト実行中...</div>');

            $.get('/api/test/database', function(response) {
                if (response.status === 'success') {
                    $('#test-results').html('<div class="alert alert-success">✓ データベース: 接続成功</div>');
                } else {
                    $('#test-results').html('<div class="alert alert-danger">✗ データベース: 接続失敗 - ' + response.message + '</div>');
                }
            }).fail(function() {
                $('#test-results').html('<div class="alert alert-danger">✗ データベース: API接続エラー</div>');
            });
        }

        // 1分ごとに稼働時間を更新
        setInterval(updateUptime, 60000);
        updateUptime();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """メインページ"""
    import sys
    from datetime import datetime

    return render_template_string(TEMPLATE,
                                start_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

@app.route('/api/test/data')
def test_data():
    """データ取得テスト"""
    try:
        from data_fetcher import DataFetcher
        from utils import load_config

        config = load_config('config/config.yaml')
        fetcher = DataFetcher(config)

        # 簡単なデータ取得テスト
        price_data = fetcher.fetch_price_data('7203.T')

        if price_data and 'current_price' in price_data:
            return jsonify({
                'status': 'success',
                'message': f'トヨタ現在値: {price_data["current_price"]:.0f}円'
            })
        else:
            return jsonify({'status': 'error', 'message': 'データ取得失敗'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/test/screening')
def test_screening():
    """スクリーニングテスト"""
    try:
        from data_fetcher import DataFetcher
        from analyzer import StockAnalyzer
        from utils import load_config

        config = load_config('config/config.yaml')
        fetcher = DataFetcher(config)
        analyzer = StockAnalyzer(config, fetcher)

        # サンプル銘柄でテスト
        test_symbols = ['7203.T', '9984.T']
        results = []

        for symbol in test_symbols:
            price_data = fetcher.fetch_price_data(symbol)
            if price_data:
                stock_data = {
                    'symbol': symbol,
                    'name': symbol.split('.')[0],
                    'market_cap': 1000000000000,
                    'is_marginable': True,
                    **price_data
                }
                score = analyzer.calculate_score(stock_data)
                if score.get('total_score', 0) > 0:
                    results.append(score)

        return jsonify({
            'status': 'success',
            'count': len(results),
            'message': f'{len(results)}銘柄のスコア計算完了'
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/test/database')
def test_database():
    """データベーステスト"""
    try:
        from database import DatabaseManager

        db = DatabaseManager()

        # 簡単な接続テスト
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]

        return jsonify({
            'status': 'success',
            'message': f'データベース接続成功（テーブル数: {table_count}）'
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    print("=" * 60)
    print("デイトレスクリーニング - シンプルダッシュボード")
    print("=" * 60)
    print("アクセスURL: http://localhost:5001")
    print("Ctrl+C で停止")
    print("=" * 60)

    app.run(debug=True, port=5001)