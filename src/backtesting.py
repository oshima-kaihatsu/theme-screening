"""
バックテストフレームワーク
過去データを使用した戦略検証
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable
from loguru import logger
import yfinance as yf
from dataclasses import dataclass, field
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

from database import DatabaseManager
from data_fetcher import DataFetcher
from analyzer import StockAnalyzer
from advanced_analyzer import AdvancedTechnicalAnalyzer
from utils import load_config


@dataclass
class BacktestConfig:
    """バックテスト設定"""
    start_date: str
    end_date: str
    initial_capital: float = 1000000
    max_positions: int = 5
    position_size: float = 0.2  # 資金の20%
    commission: float = 0.001  # 手数料0.1%
    slippage: float = 0.001  # スリッページ0.1%
    stop_loss: float = 0.03  # 損切り3%
    take_profit: float = 0.05  # 利確5%
    holding_period_limit: int = 5  # 最大保有日数


@dataclass
class Trade:
    """取引記録"""
    symbol: str
    entry_date: datetime
    exit_date: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    shares: int = 0
    position_value: float = 0.0
    pnl: float = 0.0
    pnl_percentage: float = 0.0
    exit_reason: str = ""
    signals: List[str] = field(default_factory=list)
    score: float = 0.0
    commission_paid: float = 0.0
    slippage_cost: float = 0.0


@dataclass
class BacktestResult:
    """バックテスト結果"""
    config: BacktestConfig
    trades: List[Trade] = field(default_factory=list)
    daily_equity: pd.DataFrame = field(default_factory=pd.DataFrame)
    start_date: datetime = None
    end_date: datetime = None
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0


class BacktestEngine:
    """バックテストエンジン"""

    def __init__(self, config: BacktestConfig):
        """
        初期化

        Args:
            config: バックテスト設定
        """
        self.config = config
        self.trades = []
        self.open_positions = {}
        self.capital = config.initial_capital
        self.daily_equity = []
        self.data_fetcher = None
        self.analyzer = None
        self.advanced_analyzer = None

    def setup(self, app_config: Dict):
        """
        バックテスト環境セットアップ

        Args:
            app_config: アプリケーション設定
        """
        self.data_fetcher = DataFetcher(app_config)
        self.analyzer = StockAnalyzer(app_config, self.data_fetcher)
        self.advanced_analyzer = AdvancedTechnicalAnalyzer()

        logger.info(f"Backtest setup completed. Period: {self.config.start_date} to {self.config.end_date}")

    def get_universe(self) -> List[str]:
        """
        テスト対象銘柄リストを取得

        Returns:
            List[str]: 銘柄コードリスト
        """
        # 主要銘柄のサンプル（実際の実装では、より包括的なリストを使用）
        universe = [
            '7203.T', '9984.T', '6098.T', '8058.T', '9432.T',
            '6981.T', '4568.T', '8306.T', '6594.T', '7974.T',
            '4063.T', '9983.T', '8035.T', '6857.T', '4519.T',
            '6758.T', '6861.T', '6367.T', '7261.T', '8001.T'
        ]

        return universe

    def get_historical_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        履歴データ取得

        Args:
            symbol: 銘柄コード

        Returns:
            DataFrame: 価格データ
        """
        try:
            start_date = datetime.strptime(self.config.start_date, '%Y-%m-%d')
            end_date = datetime.strptime(self.config.end_date, '%Y-%m-%d')

            # バックテスト期間の前後にバッファを追加（テクニカル指標計算のため）
            buffer_start = start_date - timedelta(days=100)

            ticker = yf.Ticker(symbol)
            data = ticker.history(start=buffer_start, end=end_date)

            if data.empty:
                logger.warning(f"No data available for {symbol}")
                return None

            return data

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

    def screen_stocks(self, date: datetime, universe: List[str]) -> List[Dict]:
        """
        指定日付でのスクリーニング実行

        Args:
            date: スクリーニング日付
            universe: 対象銘柄リスト

        Returns:
            List[Dict]: スクリーニング結果
        """
        results = []

        for symbol in universe:
            try:
                # 指定日付までのデータを取得
                df = self.get_historical_data(symbol)
                if df is None or df.empty:
                    continue

                # 指定日付以前のデータのみ使用
                historical_df = df[df.index <= date]
                if len(historical_df) < 30:  # 最低30日分のデータが必要
                    continue

                # 最新の価格データ
                latest_data = historical_df.iloc[-1]
                prev_data = historical_df.iloc[-2] if len(historical_df) > 1 else latest_data

                # 株価データ準備
                stock_data = {
                    'symbol': symbol,
                    'name': symbol.split('.')[0],
                    'current_price': float(latest_data['Close']),
                    'previous_close': float(prev_data['Close']),
                    'open': float(latest_data['Open']),
                    'high': float(latest_data['High']),
                    'low': float(latest_data['Low']),
                    'volume': int(latest_data['Volume']),
                    'average_volume': float(historical_df['Volume'].tail(20).mean()),
                    'gap_ratio': (latest_data['Open'] - prev_data['Close']) / prev_data['Close'],
                    'volume_ratio': latest_data['Volume'] / historical_df['Volume'].tail(20).mean(),
                    'market_cap': 1000000000000,  # ダミー値
                    'is_marginable': True
                }

                # テクニカル指標計算
                indicators = self.advanced_analyzer.calculate_all_indicators(historical_df)
                stock_data['technical_indicators'] = indicators

                # スコアリング
                score_result = self.analyzer.calculate_score(stock_data)

                if score_result.get('total_score', 0) > 0:
                    result = {
                        'symbol': symbol,
                        'date': date,
                        'price': stock_data['current_price'],
                        'score': score_result['total_score'],
                        'signals': score_result.get('signals', []),
                        'stock_data': stock_data
                    }
                    results.append(result)

            except Exception as e:
                logger.warning(f"Error screening {symbol} on {date}: {e}")
                continue

        # スコア順にソート
        results.sort(key=lambda x: x['score'], reverse=True)

        return results[:self.config.max_positions * 2]  # 上位候補を返す

    def can_open_position(self) -> bool:
        """新規ポジション開設可能かチェック"""
        return len(self.open_positions) < self.config.max_positions

    def calculate_position_size(self, price: float) -> int:
        """
        ポジションサイズ計算

        Args:
            price: 株価

        Returns:
            int: 株数
        """
        max_investment = self.capital * self.config.position_size
        shares = int(max_investment / price / 100) * 100  # 100株単位

        return max(100, shares)

    def open_position(self, symbol: str, date: datetime, price: float,
                      signals: List[str], score: float) -> bool:
        """
        ポジションオープン

        Args:
            symbol: 銘柄コード
            date: エントリー日
            price: エントリー価格
            signals: シグナルリスト
            score: スコア

        Returns:
            bool: 成功/失敗
        """
        if not self.can_open_position():
            return False

        if symbol in self.open_positions:
            return False

        shares = self.calculate_position_size(price)
        if shares == 0:
            return False

        # スリッページとコミッション考慮
        adjusted_price = price * (1 + self.config.slippage)
        position_value = adjusted_price * shares
        commission = position_value * self.config.commission

        if position_value + commission > self.capital:
            return False

        trade = Trade(
            symbol=symbol,
            entry_date=date,
            entry_price=adjusted_price,
            shares=shares,
            position_value=position_value,
            signals=signals,
            score=score,
            commission_paid=commission,
            slippage_cost=price * shares * self.config.slippage
        )

        self.open_positions[symbol] = trade
        self.capital -= (position_value + commission)

        logger.debug(f"Opened position: {symbol} @ {adjusted_price} x {shares}")

        return True

    def close_position(self, symbol: str, date: datetime, price: float, reason: str):
        """
        ポジションクローズ

        Args:
            symbol: 銘柄コード
            date: エグジット日
            price: エグジット価格
            reason: クローズ理由
        """
        if symbol not in self.open_positions:
            return

        trade = self.open_positions[symbol]

        # スリッページとコミッション考慮
        adjusted_price = price * (1 - self.config.slippage)
        exit_value = adjusted_price * trade.shares
        commission = exit_value * self.config.commission

        trade.exit_date = date
        trade.exit_price = adjusted_price
        trade.pnl = exit_value - trade.position_value - commission - trade.commission_paid
        trade.pnl_percentage = trade.pnl / trade.position_value * 100
        trade.exit_reason = reason
        trade.commission_paid += commission
        trade.slippage_cost += price * trade.shares * self.config.slippage

        self.capital += (exit_value - commission)
        self.trades.append(trade)

        del self.open_positions[symbol]

        logger.debug(f"Closed position: {symbol} @ {adjusted_price}, PnL: {trade.pnl:.0f}")

    def process_day(self, date: datetime, universe: List[str]):
        """
        1日分の処理

        Args:
            date: 処理日
            universe: 対象銘柄リスト
        """
        try:
            # 既存ポジションの管理
            positions_to_close = []

            for symbol, trade in self.open_positions.items():
                df = self.get_historical_data(symbol)
                if df is None:
                    continue

                current_data = df[df.index <= date]
                if current_data.empty:
                    continue

                current_price = float(current_data.iloc[-1]['Close'])
                days_held = (date - trade.entry_date).days

                # 利確/損切りチェック
                if trade.entry_price > 0:
                    return_pct = (current_price - trade.entry_price) / trade.entry_price

                    if return_pct >= self.config.take_profit:
                        positions_to_close.append((symbol, current_price, 'take_profit'))
                    elif return_pct <= -self.config.stop_loss:
                        positions_to_close.append((symbol, current_price, 'stop_loss'))
                    elif days_held >= self.config.holding_period_limit:
                        positions_to_close.append((symbol, current_price, 'time_limit'))

            # ポジションクローズ
            for symbol, price, reason in positions_to_close:
                self.close_position(symbol, date, price, reason)

            # 新規エントリー検討
            if self.can_open_position():
                screening_results = self.screen_stocks(date, universe)

                for result in screening_results:
                    if not self.can_open_position():
                        break

                    symbol = result['symbol']
                    if symbol in self.open_positions:
                        continue

                    # エントリー条件チェック
                    if result['score'] >= 70:  # スコア閾値
                        self.open_position(
                            symbol, date, result['price'],
                            result['signals'], result['score']
                        )

            # 日次エクイティ記録
            total_value = self.capital
            for trade in self.open_positions.values():
                df = self.get_historical_data(trade.symbol)
                if df is not None:
                    current_data = df[df.index <= date]
                    if not current_data.empty:
                        current_price = float(current_data.iloc[-1]['Close'])
                        total_value += current_price * trade.shares

            self.daily_equity.append({
                'date': date,
                'cash': self.capital,
                'total_value': total_value,
                'open_positions': len(self.open_positions)
            })

        except Exception as e:
            logger.error(f"Error processing day {date}: {e}")

    def run(self, app_config: Dict) -> BacktestResult:
        """
        バックテスト実行

        Args:
            app_config: アプリケーション設定

        Returns:
            BacktestResult: バックテスト結果
        """
        logger.info("Starting backtest...")

        # セットアップ
        self.setup(app_config)

        # 日付範囲生成
        start_date = datetime.strptime(self.config.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(self.config.end_date, '%Y-%m-%d')

        universe = self.get_universe()

        # 営業日リストを生成
        business_days = pd.bdate_range(start=start_date, end=end_date)

        # 日次処理
        for i, date in enumerate(business_days):
            if i % 20 == 0:
                logger.info(f"Processing {date.strftime('%Y-%m-%d')} ({i+1}/{len(business_days)})")

            self.process_day(date.to_pydatetime(), universe)

        # 残りポジションをクローズ
        for symbol, trade in list(self.open_positions.items()):
            df = self.get_historical_data(symbol)
            if df is not None:
                final_data = df[df.index <= end_date]
                if not final_data.empty:
                    final_price = float(final_data.iloc[-1]['Close'])
                    self.close_position(symbol, end_date, final_price, 'backtest_end')

        # 結果計算
        result = self.calculate_results()

        logger.info(f"Backtest completed. Total return: {result.total_return:.2f}%")
        logger.info(f"Win rate: {result.win_rate:.2f}%, Sharpe ratio: {result.sharpe_ratio:.2f}")

        return result

    def calculate_results(self) -> BacktestResult:
        """
        バックテスト結果を計算

        Returns:
            BacktestResult: 計算結果
        """
        result = BacktestResult(config=self.config)

        # 基本統計
        result.trades = self.trades
        result.start_date = datetime.strptime(self.config.start_date, '%Y-%m-%d')
        result.end_date = datetime.strptime(self.config.end_date, '%Y-%m-%d')
        result.initial_capital = self.config.initial_capital
        result.final_capital = self.capital

        # Daily equity DataFrame
        result.daily_equity = pd.DataFrame(self.daily_equity)

        if result.daily_equity.empty:
            return result

        # リターン計算
        result.total_return = (result.final_capital - result.initial_capital) / result.initial_capital * 100

        # 年率リターン
        days = (result.end_date - result.start_date).days
        if days > 0:
            result.annualized_return = ((result.final_capital / result.initial_capital) ** (365.25 / days) - 1) * 100

        # ボラティリティとシャープレシオ
        if len(result.daily_equity) > 1:
            daily_returns = result.daily_equity['total_value'].pct_change().dropna()
            if len(daily_returns) > 1:
                result.volatility = daily_returns.std() * np.sqrt(252) * 100
                if result.volatility > 0:
                    result.sharpe_ratio = result.annualized_return / result.volatility

        # 最大ドローダウン
        if len(result.daily_equity) > 0:
            equity_curve = result.daily_equity['total_value']
            running_max = equity_curve.expanding().max()
            drawdown = (equity_curve - running_max) / running_max
            result.max_drawdown = drawdown.min() * 100

        # トレード統計
        if result.trades:
            result.total_trades = len(result.trades)
            winning_trades = [t for t in result.trades if t.pnl > 0]
            losing_trades = [t for t in result.trades if t.pnl < 0]

            result.winning_trades = len(winning_trades)
            result.losing_trades = len(losing_trades)
            result.win_rate = result.winning_trades / result.total_trades * 100

            if winning_trades:
                result.avg_win = np.mean([t.pnl for t in winning_trades])
                result.max_win = max([t.pnl for t in winning_trades])

            if losing_trades:
                result.avg_loss = np.mean([t.pnl for t in losing_trades])
                result.max_loss = min([t.pnl for t in losing_trades])

            # プロフィットファクター
            total_wins = sum([t.pnl for t in winning_trades])
            total_losses = abs(sum([t.pnl for t in losing_trades]))
            if total_losses > 0:
                result.profit_factor = total_wins / total_losses

        return result


class BacktestReporter:
    """バックテスト結果レポート生成"""

    def __init__(self, result: BacktestResult):
        """
        初期化

        Args:
            result: バックテスト結果
        """
        self.result = result

    def generate_summary_report(self) -> str:
        """
        サマリーレポート生成

        Returns:
            str: レポート文字列
        """
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("バックテスト結果サマリー")
        report_lines.append("=" * 60)
        report_lines.append("")

        # 基本情報
        report_lines.append("【基本情報】")
        report_lines.append(f"期間: {self.result.start_date.strftime('%Y-%m-%d')} ～ {self.result.end_date.strftime('%Y-%m-%d')}")
        report_lines.append(f"初期資金: ¥{self.result.initial_capital:,.0f}")
        report_lines.append(f"最終資金: ¥{self.result.final_capital:,.0f}")
        report_lines.append("")

        # パフォーマンス
        report_lines.append("【パフォーマンス】")
        report_lines.append(f"総リターン: {self.result.total_return:.2f}%")
        report_lines.append(f"年率リターン: {self.result.annualized_return:.2f}%")
        report_lines.append(f"ボラティリティ: {self.result.volatility:.2f}%")
        report_lines.append(f"シャープレシオ: {self.result.sharpe_ratio:.2f}")
        report_lines.append(f"最大ドローダウン: {self.result.max_drawdown:.2f}%")
        report_lines.append("")

        # トレード統計
        if self.result.trades:
            report_lines.append("【トレード統計】")
            report_lines.append(f"総トレード数: {self.result.total_trades}")
            report_lines.append(f"勝ちトレード: {self.result.winning_trades} ({self.result.win_rate:.1f}%)")
            report_lines.append(f"負けトレード: {self.result.losing_trades}")
            report_lines.append(f"平均利益: ¥{self.result.avg_win:,.0f}")
            report_lines.append(f"平均損失: ¥{self.result.avg_loss:,.0f}")
            report_lines.append(f"最大利益: ¥{self.result.max_win:,.0f}")
            report_lines.append(f"最大損失: ¥{self.result.max_loss:,.0f}")
            report_lines.append(f"プロフィットファクター: {self.result.profit_factor:.2f}")
            report_lines.append("")

        # 設定パラメータ
        report_lines.append("【設定パラメータ】")
        report_lines.append(f"最大ポジション数: {self.result.config.max_positions}")
        report_lines.append(f"ポジションサイズ: {self.result.config.position_size:.1%}")
        report_lines.append(f"損切り: {self.result.config.stop_loss:.1%}")
        report_lines.append(f"利確: {self.result.config.take_profit:.1%}")
        report_lines.append(f"最大保有日数: {self.result.config.holding_period_limit}日")
        report_lines.append("")

        report_lines.append("=" * 60)

        return "\n".join(report_lines)

    def save_detailed_report(self, output_dir: str = "backtest_results"):
        """
        詳細レポートを保存

        Args:
            output_dir: 出力ディレクトリ
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # トレードリスト
        if self.result.trades:
            trades_df = pd.DataFrame([
                {
                    'symbol': t.symbol,
                    'entry_date': t.entry_date,
                    'exit_date': t.exit_date,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'shares': t.shares,
                    'pnl': t.pnl,
                    'pnl_percentage': t.pnl_percentage,
                    'exit_reason': t.exit_reason,
                    'score': t.score,
                    'signals': ', '.join(t.signals)
                }
                for t in self.result.trades
            ])

            trades_file = output_path / f"trades_{timestamp}.csv"
            trades_df.to_csv(trades_file, index=False, encoding='utf-8-sig')
            logger.info(f"Trades saved to {trades_file}")

        # エクイティカーブ
        if not self.result.daily_equity.empty:
            equity_file = output_path / f"equity_curve_{timestamp}.csv"
            self.result.daily_equity.to_csv(equity_file, index=False, encoding='utf-8-sig')
            logger.info(f"Equity curve saved to {equity_file}")

            # エクイティカーブ図
            self.plot_equity_curve(output_path / f"equity_curve_{timestamp}.png")

        # サマリーレポート
        summary_file = output_path / f"summary_{timestamp}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_summary_report())
        logger.info(f"Summary saved to {summary_file}")

    def plot_equity_curve(self, output_file: str):
        """
        エクイティカーブを描画

        Args:
            output_file: 出力ファイルパス
        """
        if self.result.daily_equity.empty:
            return

        plt.figure(figsize=(12, 8))

        # エクイティカーブ
        plt.subplot(2, 1, 1)
        plt.plot(self.result.daily_equity['date'], self.result.daily_equity['total_value'])
        plt.title('Equity Curve')
        plt.ylabel('Portfolio Value (¥)')
        plt.grid(True)

        # ドローダウン
        plt.subplot(2, 1, 2)
        equity = self.result.daily_equity['total_value']
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max * 100

        plt.fill_between(self.result.daily_equity['date'], drawdown, 0, alpha=0.3, color='red')
        plt.title('Drawdown')
        plt.ylabel('Drawdown (%)')
        plt.grid(True)

        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Equity curve plot saved to {output_file}")


def run_backtest_example():
    """バックテスト実行例"""

    # バックテスト設定
    config = BacktestConfig(
        start_date='2023-01-01',
        end_date='2023-12-31',
        initial_capital=1000000,
        max_positions=3,
        position_size=0.25,
        stop_loss=0.05,
        take_profit=0.08
    )

    # アプリ設定読み込み
    try:
        app_config = load_config('config/config.yaml')
    except:
        # デフォルト設定
        app_config = {
            'screening': {
                'filters': {
                    'min_trading_value': 500000000,
                    'min_market_cap': 10000000000,
                    'max_market_cap': 100000000000,
                    'min_volatility': 0.02
                },
                'scoring_weights': {
                    'volume_surge': 30,
                    'gap_up_moderate': 20,
                    'ma5_breakout': 15,
                    'ma25_breakout': 20
                }
            }
        }

    # バックテスト実行
    engine = BacktestEngine(config)
    result = engine.run(app_config)

    # レポート生成
    reporter = BacktestReporter(result)
    print(reporter.generate_summary_report())

    # 詳細レポート保存
    reporter.save_detailed_report()

    # データベースに保存
    try:
        db = DatabaseManager()
        db_result = {
            'test_name': f'Backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'start_date': result.start_date,
            'end_date': result.end_date,
            'initial_capital': result.initial_capital,
            'final_capital': result.final_capital,
            'total_return': result.total_return,
            'win_rate': result.win_rate,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown,
            'total_trades': result.total_trades,
            'winning_trades': result.winning_trades,
            'losing_trades': result.losing_trades,
            'parameters': {
                'max_positions': config.max_positions,
                'position_size': config.position_size,
                'stop_loss': config.stop_loss,
                'take_profit': config.take_profit
            }
        }
        db.save_backtest_result(db_result)
        logger.info("Backtest result saved to database")

    except Exception as e:
        logger.warning(f"Could not save to database: {e}")

    return result


if __name__ == "__main__":
    run_backtest_example()