"""
メインエントリーポイント
"""

import yaml
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd
from loguru import logger
import schedule
import time
from dotenv import load_dotenv

# 相対インポート
from data_fetcher import DataFetcher
from analyzer import StockAnalyzer
from notifier import Notifier
from utils import setup_logging, load_config, format_currency


class DayTradeScreener:
    """デイトレードスクリーニングシステム"""

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        システム初期化
        - 設定ファイル読み込み
        - 各モジュールの初期化
        - ログ設定
        """
        # 環境変数読み込み
        load_dotenv()

        # ログ設定
        setup_logging()

        # 設定ファイル読み込み
        self.config = load_config(config_path)

        # モジュール初期化
        self.data_fetcher = DataFetcher(self.config)
        self.analyzer = StockAnalyzer(self.config, self.data_fetcher)
        self.notifier = Notifier(self.config)

        logger.info("DayTradeScreener initialized successfully")

    def run_screening(self, screening_type: str = "full") -> Dict:
        """
        スクリーニング実行

        Args:
            screening_type: "initial", "secondary", "final", "full"

        Returns:
            dict: スクリーニング結果
        """
        start_time = datetime.now()
        logger.info(f"Starting {screening_type} screening at {start_time}")

        try:
            # 1. 銘柄リスト取得
            logger.info("Fetching stock list...")
            stock_list = self.data_fetcher.fetch_stock_list()

            if stock_list.empty:
                logger.error("No stocks found")
                return {'error': 'No stocks found'}

            logger.info(f"Found {len(stock_list)} stocks")

            # 2. 各銘柄のデータ取得と分析
            analyzed_stocks = []

            for idx, stock_info in stock_list.iterrows():
                try:
                    symbol = stock_info['symbol']
                    logger.debug(f"Processing {symbol}")

                    # 株価データ取得
                    price_data = self.data_fetcher.fetch_price_data(symbol)
                    if not price_data:
                        continue

                    # テクニカル指標取得
                    technical_indicators = self.data_fetcher.fetch_technical_indicators(symbol)

                    # ニュース取得
                    news_data = self.data_fetcher.fetch_news(symbol)

                    # セクターデータ取得（簡易版）
                    sector_data = self.data_fetcher.fetch_sector_data('general')

                    # 銘柄データを統合
                    stock_data = {
                        'symbol': symbol,
                        'name': stock_info['name'],
                        'market': stock_info['market'],
                        'market_cap': stock_info.get('market_cap', 0),
                        'is_marginable': stock_info.get('is_marginable', False),
                        **price_data,
                        'technical_indicators': technical_indicators,
                        'news': news_data,
                        'sector_data': sector_data
                    }

                    analyzed_stocks.append(stock_data)

                    # 処理間隔（API制限対策）
                    time.sleep(0.1)

                except Exception as e:
                    logger.warning(f"Error processing {stock_info.get('symbol', 'unknown')}: {e}")
                    continue

            logger.info(f"Processed {len(analyzed_stocks)} stocks")

            # 3. フィルター適用
            logger.info("Applying filters...")
            filtered_stocks = self.analyzer.apply_filters(analyzed_stocks)

            # 4. スコア計算
            logger.info("Calculating scores...")
            scored_stocks = []
            for stock in filtered_stocks:
                try:
                    score_result = self.analyzer.calculate_score(stock)
                    if score_result.get('total_score', 0) > 0:
                        # リスク指標追加
                        risk_metrics = self.analyzer.calculate_risk_metrics(stock)
                        score_result.update(risk_metrics)

                        # 元の株式データもマージ
                        score_result.update({
                            'name': stock.get('name', ''),
                            'current_price': stock.get('current_price', 0),
                            'gap_ratio': stock.get('gap_ratio', 0),
                            'volume_ratio': stock.get('volume_ratio', 1),
                            'market_cap': stock.get('market_cap', 0)
                        })

                        scored_stocks.append(score_result)

                except Exception as e:
                    logger.warning(f"Error scoring {stock.get('symbol', 'unknown')}: {e}")
                    continue

            # 5. ランキング作成
            logger.info("Creating rankings...")
            ranked_stocks = self.analyzer.rank_stocks(scored_stocks)

            # 6. 結果まとめ
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            results = {
                'timestamp': start_time,
                'screening_type': screening_type,
                'execution_time': execution_time,
                'total_processed': len(analyzed_stocks),
                'filtered_count': len(filtered_stocks),
                'scored_count': len(scored_stocks),
                'top_picks': ranked_stocks[:5],  # 上位5銘柄
                'watch_list': ranked_stocks[5:20],  # 6-20位
                'statistics': {
                    'avg_score': sum(s.get('total_score', 0) for s in scored_stocks) / len(scored_stocks) if scored_stocks else 0,
                    'max_score': max(s.get('total_score', 0) for s in scored_stocks) if scored_stocks else 0,
                    'min_score': min(s.get('total_score', 0) for s in scored_stocks) if scored_stocks else 0
                }
            }

            logger.info(f"Screening completed in {execution_time:.2f} seconds")
            logger.info(f"Top 5 picks: {[s['symbol'] for s in results['top_picks']]}")

            return results

        except Exception as e:
            logger.error(f"Error during screening: {e}")
            return {'error': str(e), 'timestamp': datetime.now()}

    def generate_report(self, results: Dict) -> str:
        """
        レポート生成

        Args:
            results: run_screeningの結果

        Returns:
            str: フォーマットされたレポート
        """
        if 'error' in results:
            return f"スクリーニングエラー: {results['error']}"

        try:
            report_lines = []
            report_lines.append("=" * 60)
            report_lines.append("デイトレスクリーニング結果")
            report_lines.append(f"実行時刻: {results['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append(f"処理時間: {results['execution_time']:.2f}秒")
            report_lines.append(f"処理銘柄数: {results['total_processed']} → {results['scored_count']}銘柄")
            report_lines.append("=" * 60)
            report_lines.append("")

            # 推奨銘柄TOP5
            if results['top_picks']:
                report_lines.append("【推奨銘柄TOP5】")
                report_lines.append("")

                for i, stock in enumerate(results['top_picks'], 1):
                    report_lines.append(f"{i}. [{stock['symbol']}] {stock.get('name', '')}")
                    report_lines.append(f"   スコア: {stock['total_score']}/100")
                    report_lines.append(f"   現在値: {format_currency(stock.get('current_price', 0))}円")

                    gap_ratio = stock.get('gap_ratio', 0)
                    if gap_ratio > 0:
                        report_lines.append(f"   前日比: +{gap_ratio:.1%}")
                    else:
                        report_lines.append(f"   前日比: {gap_ratio:.1%}")

                    volume_ratio = stock.get('volume_ratio', 1)
                    report_lines.append(f"   出来高: 前日比 {volume_ratio:.1f}倍")
                    report_lines.append("")

                    # シグナル
                    if stock.get('signals'):
                        report_lines.append("   ▼ シグナル")
                        for signal in stock['signals']:
                            report_lines.append(f"   - {signal}")
                        report_lines.append("")

                    # 推奨アクション
                    current_price = stock.get('current_price', 0)
                    stop_loss = stock.get('stop_loss_price', 0)
                    take_profit = stock.get('take_profit_price', 0)

                    if current_price > 0:
                        entry_low = current_price * 1.002
                        entry_high = current_price * 1.008

                        report_lines.append("   ▼ 推奨アクション")
                        report_lines.append(f"   エントリー: {format_currency(entry_low)}-{format_currency(entry_high)}円")

                        if take_profit > 0:
                            profit_pct = (take_profit - current_price) / current_price * 100
                            report_lines.append(f"   利確目標: {format_currency(take_profit)}円 (+{profit_pct:.1f}%)")

                        if stop_loss > 0:
                            loss_pct = (current_price - stop_loss) / current_price * 100
                            report_lines.append(f"   損切り: {format_currency(stop_loss)}円 (-{loss_pct:.1f}%)")

                        report_lines.append("")

                    # 注意事項
                    if stock.get('warnings'):
                        report_lines.append("   ▼ 注意事項")
                        for warning in stock['warnings']:
                            report_lines.append(f"   - {warning}")
                        report_lines.append("")

                    report_lines.append("-" * 40)
                    report_lines.append("")

            # 統計情報
            stats = results.get('statistics', {})
            if stats:
                report_lines.append("【統計情報】")
                report_lines.append(f"平均スコア: {stats.get('avg_score', 0):.1f}")
                report_lines.append(f"最高スコア: {stats.get('max_score', 0):.1f}")
                report_lines.append(f"最低スコア: {stats.get('min_score', 0):.1f}")
                report_lines.append("")

            report_lines.append("=" * 60)

            return "\n".join(report_lines)

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"レポート生成エラー: {e}"

    def schedule_execution(self):
        """
        スケジュール実行設定

        実行タイミング:
        - 07:00: 初期スクリーニング（全銘柄対象）
        - 08:00: 二次スクリーニング（上位100銘柄対象）
        - 08:30: 最終スクリーニング（上位30銘柄対象）
        - 09:00: 寄り付き後モニタリング開始
        - 09:30: 結果レポート送信
        """
        logger.info("Setting up scheduled execution")

        # スケジュール設定
        schedule.every().monday.at("07:00").do(self._run_scheduled_screening, "initial")
        schedule.every().tuesday.at("07:00").do(self._run_scheduled_screening, "initial")
        schedule.every().wednesday.at("07:00").do(self._run_scheduled_screening, "initial")
        schedule.every().thursday.at("07:00").do(self._run_scheduled_screening, "initial")
        schedule.every().friday.at("07:00").do(self._run_scheduled_screening, "initial")

        schedule.every().monday.at("08:00").do(self._run_scheduled_screening, "secondary")
        schedule.every().tuesday.at("08:00").do(self._run_scheduled_screening, "secondary")
        schedule.every().wednesday.at("08:00").do(self._run_scheduled_screening, "secondary")
        schedule.every().thursday.at("08:00").do(self._run_scheduled_screening, "secondary")
        schedule.every().friday.at("08:00").do(self._run_scheduled_screening, "secondary")

        schedule.every().monday.at("08:30").do(self._run_scheduled_screening, "final")
        schedule.every().tuesday.at("08:30").do(self._run_scheduled_screening, "final")
        schedule.every().wednesday.at("08:30").do(self._run_scheduled_screening, "final")
        schedule.every().thursday.at("08:30").do(self._run_scheduled_screening, "final")
        schedule.every().friday.at("08:30").do(self._run_scheduled_screening, "final")

        logger.info("Scheduled tasks configured. Starting scheduler loop...")

        # スケジューラーループ
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1分間隔でチェック

    def _run_scheduled_screening(self, screening_type: str):
        """スケジュール実行用の内部メソッド"""
        try:
            logger.info(f"Running scheduled {screening_type} screening")

            # スクリーニング実行
            results = self.run_screening(screening_type)

            # レポート生成
            report = self.generate_report(results)

            # 通知送信
            self.notifier.send_notification(report, results)

        except Exception as e:
            logger.error(f"Error in scheduled screening: {e}")


def main():
    """メイン実行関数"""
    import argparse

    parser = argparse.ArgumentParser(description='日本株デイトレードスクリーニングツール')
    parser.add_argument('--mode', choices=['run', 'schedule'], default='run',
                        help='実行モード: run=単発実行, schedule=スケジュール実行')
    parser.add_argument('--type', choices=['initial', 'secondary', 'final', 'full'], default='full',
                        help='スクリーニングタイプ')
    parser.add_argument('--config', default='config/config.yaml',
                        help='設定ファイルパス')

    args = parser.parse_args()

    try:
        # スクリーナー初期化
        screener = DayTradeScreener(args.config)

        if args.mode == 'run':
            # 単発実行
            logger.info(f"Running {args.type} screening")
            results = screener.run_screening(args.type)

            # レポート生成・表示
            report = screener.generate_report(results)
            print(report)

            # 通知送信
            screener.notifier.send_notification(report, results)

        elif args.mode == 'schedule':
            # スケジュール実行
            screener.schedule_execution()

    except KeyboardInterrupt:
        logger.info("Execution interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()