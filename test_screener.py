#!/usr/bin/env python
"""
スクリーニングツールのテストスクリプト
基本機能の動作確認とサンプル実行
"""

import sys
import os
sys.path.append('src')

from datetime import datetime
from data_fetcher import DataFetcher
from analyzer import StockAnalyzer
from notifier import Notifier
from utils import setup_logging, load_config
from loguru import logger


def test_basic_screening():
    """基本的なスクリーニング機能をテスト"""

    print("=" * 60)
    print("デイトレードスクリーニングツール - テスト実行")
    print("=" * 60)

    # 1. セットアップ
    print("\n[1] セットアップ中...")
    setup_logging()
    config = load_config('config/config.yaml')

    # 2. モジュール初期化
    print("[2] モジュール初期化中...")
    data_fetcher = DataFetcher(config)
    analyzer = StockAnalyzer(config, data_fetcher)
    notifier = Notifier(config)

    # 3. テスト用銘柄リスト（少数でテスト）
    print("[3] テスト銘柄データ取得中...")
    test_symbols = ['7203.T', '9984.T', '6098.T']  # トヨタ、ソフトバンクG、リクルート

    analyzed_stocks = []
    for symbol in test_symbols:
        try:
            print(f"   - {symbol} を処理中...")

            # 価格データ取得
            price_data = data_fetcher.fetch_price_data(symbol)
            if not price_data:
                print(f"     ⚠ {symbol} のデータ取得失敗")
                continue

            # テクニカル指標計算
            technical = data_fetcher.fetch_technical_indicators(symbol)

            # データ統合
            stock_data = {
                'symbol': symbol,
                'name': symbol.split('.')[0],  # 簡易名前
                'market': 'Prime',
                'market_cap': 1000000000000,  # ダミー値
                'is_marginable': True,
                **price_data,
                'technical_indicators': technical,
                'news': [],
                'sector_data': {}
            }

            # スコア計算
            score_result = analyzer.calculate_score(stock_data)

            # リスク指標追加
            risk_metrics = analyzer.calculate_risk_metrics(stock_data)
            score_result.update(risk_metrics)
            score_result.update({
                'name': stock_data['name'],
                'current_price': stock_data.get('current_price', 0),
                'gap_ratio': stock_data.get('gap_ratio', 0),
                'volume_ratio': stock_data.get('volume_ratio', 1)
            })

            analyzed_stocks.append(score_result)

            print(f"     ✓ スコア: {score_result['total_score']:.1f}/100")

        except Exception as e:
            print(f"     ✗ エラー: {e}")

    # 4. ランキング作成
    print(f"\n[4] ランキング作成中...")
    ranked_stocks = analyzer.rank_stocks(analyzed_stocks)

    # 5. 結果表示
    print("\n[5] スクリーニング結果:")
    print("-" * 60)

    for stock in ranked_stocks:
        print(f"\n{stock['rank']}位: [{stock['symbol']}]")
        print(f"  スコア: {stock['total_score']}/100")
        print(f"  現在値: {stock.get('current_price', 0):,.0f}円")
        print(f"  前日比: {stock.get('gap_ratio', 0):.1%}")
        print(f"  出来高比: {stock.get('volume_ratio', 1):.1f}倍")

        if stock.get('signals'):
            print(f"  シグナル:")
            for signal in stock['signals']:
                print(f"    - {signal}")

        if stock.get('warnings'):
            print(f"  警告:")
            for warning in stock['warnings']:
                print(f"    - {warning}")

    # 6. レポート保存
    print(f"\n[6] レポート保存中...")

    results = {
        'timestamp': datetime.now(),
        'screening_type': 'test',
        'execution_time': 0,
        'total_processed': len(test_symbols),
        'filtered_count': len(analyzed_stocks),
        'scored_count': len(ranked_stocks),
        'top_picks': ranked_stocks[:5],
        'watch_list': [],
        'statistics': {
            'avg_score': sum(s.get('total_score', 0) for s in ranked_stocks) / len(ranked_stocks) if ranked_stocks else 0,
            'max_score': max(s.get('total_score', 0) for s in ranked_stocks) if ranked_stocks else 0,
            'min_score': min(s.get('total_score', 0) for s in ranked_stocks) if ranked_stocks else 0
        }
    }

    # CSV保存
    csv_path = 'data/test_screening_results.csv'
    notifier.save_to_csv(results, csv_path)
    print(f"  ✓ CSV保存: {csv_path}")

    # HTML保存
    html_report = notifier.create_html_report(results)
    html_path = 'data/test_screening_results.html'
    notifier.save_html_report(html_report, html_path)
    print(f"  ✓ HTML保存: {html_path}")

    print("\n" + "=" * 60)
    print("テスト完了！")
    print("=" * 60)

    return results


def test_data_fetcher():
    """データ取得機能のテスト"""
    print("\n[データ取得テスト]")

    config = load_config('config/config.yaml')
    fetcher = DataFetcher(config)

    # 1. 銘柄リスト取得テスト
    print("1. 銘柄リスト取得...")
    stock_list = fetcher.fetch_stock_list()
    print(f"   ✓ {len(stock_list)}銘柄取得")

    # 2. 個別銘柄データ取得テスト
    print("2. 個別銘柄データ取得...")
    symbol = '7203.T'
    price_data = fetcher.fetch_price_data(symbol)
    if price_data:
        print(f"   ✓ {symbol}: 現在値 {price_data['current_price']:,.0f}円")
        print(f"     出来高比: {price_data['volume_ratio']:.2f}倍")

    # 3. テクニカル指標テスト
    print("3. テクニカル指標計算...")
    technical = fetcher.fetch_technical_indicators(symbol)
    if technical:
        print(f"   ✓ SMA5: {technical.get('sma_5', 0):,.0f}")
        print(f"   ✓ SMA25: {technical.get('sma_25', 0):,.0f}")


def test_analyzer():
    """分析機能のテスト"""
    print("\n[分析機能テスト]")

    config = load_config('config/config.yaml')
    fetcher = DataFetcher(config)
    analyzer = StockAnalyzer(config, fetcher)

    # サンプルデータ
    sample_stock = {
        'symbol': 'TEST',
        'name': 'テスト銘柄',
        'current_price': 1000,
        'previous_close': 950,
        'open': 980,
        'volume': 2000000,
        'average_volume': 1000000,
        'gap_ratio': 0.03,
        'volume_ratio': 2.0,
        'market_cap': 50000000000,
        'is_marginable': True,
        'technical_indicators': {
            'sma_5': 950,
            'sma_25': 900,
            'position_vs_sma5': 0.05,
            'position_vs_sma25': 0.11,
            'candlestick_pattern': 'high_close'
        },
        'news': [],
        'sector_data': {}
    }

    # スコア計算
    print("1. スコア計算...")
    score_result = analyzer.calculate_score(sample_stock)
    print(f"   ✓ 総合スコア: {score_result['total_score']}/100")
    print(f"   - 出来高スコア: {score_result['score_breakdown']['volume_score']}")
    print(f"   - ギャップスコア: {score_result['score_breakdown']['gap_score']}")
    print(f"   - テクニカルスコア: {score_result['score_breakdown']['technical_score']}")

    # シグナル検出
    print("2. シグナル検出...")
    signals = analyzer.detect_entry_signals(sample_stock)
    for signal in signals:
        print(f"   ✓ {signal}")

    # リスク計算
    print("3. リスク指標...")
    risk = analyzer.calculate_risk_metrics(sample_stock)
    print(f"   ✓ リスクレベル: {risk['risk_level']}")
    print(f"   ✓ 損切り価格: {risk['stop_loss_price']:,.0f}円")
    print(f"   ✓ 利確価格: {risk['take_profit_price']:,.0f}円")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='スクリーニングツールテスト')
    parser.add_argument('--test', choices=['all', 'basic', 'data', 'analyzer'],
                       default='basic', help='テストタイプ')

    args = parser.parse_args()

    try:
        if args.test == 'all':
            test_data_fetcher()
            test_analyzer()
            test_basic_screening()
        elif args.test == 'basic':
            test_basic_screening()
        elif args.test == 'data':
            test_data_fetcher()
        elif args.test == 'analyzer':
            test_analyzer()

    except Exception as e:
        print(f"\n✗ テストエラー: {e}")
        import traceback
        traceback.print_exc()