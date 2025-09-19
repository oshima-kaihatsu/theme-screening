"""
リアルタイムモニタリングモジュール
Phase 2: リアルタイム監視と自動アラート
"""

import time
import threading
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Callable
from loguru import logger
import yfinance as yf
from queue import Queue, Empty
import json


class RealtimeMonitor:
    """リアルタイム監視クラス"""

    def __init__(self, config: Dict, notifier):
        """
        初期化

        Args:
            config: 設定辞書
            notifier: 通知オブジェクト
        """
        self.config = config
        self.notifier = notifier
        self.monitoring_stocks = {}
        self.alerts = Queue()
        self.is_running = False
        self.threads = []
        self.update_interval = 60  # 更新間隔（秒）
        self.alert_conditions = []
        self.price_cache = {}
        self.alert_history = {}

    def add_stock(self, symbol: str, entry_price: float,
                  stop_loss: float = None, take_profit: float = None,
                  alerts_config: Dict = None):
        """
        監視銘柄を追加

        Args:
            symbol: 銘柄コード
            entry_price: エントリー価格
            stop_loss: 損切り価格
            take_profit: 利確価格
            alerts_config: アラート設定
        """
        self.monitoring_stocks[symbol] = {
            'symbol': symbol,
            'entry_price': entry_price,
            'entry_time': datetime.now(),
            'stop_loss': stop_loss or entry_price * 0.97,
            'take_profit': take_profit or entry_price * 1.05,
            'current_price': entry_price,
            'high_since_entry': entry_price,
            'low_since_entry': entry_price,
            'status': 'monitoring',
            'pnl': 0,
            'pnl_percentage': 0,
            'alerts_config': alerts_config or self._default_alerts_config(),
            'triggered_alerts': [],
            'last_update': datetime.now()
        }

        logger.info(f"Added {symbol} to monitoring. Entry: {entry_price}, SL: {stop_loss}, TP: {take_profit}")

    def remove_stock(self, symbol: str):
        """監視銘柄を削除"""
        if symbol in self.monitoring_stocks:
            del self.monitoring_stocks[symbol]
            logger.info(f"Removed {symbol} from monitoring")

    def start_monitoring(self):
        """リアルタイム監視開始"""
        if self.is_running:
            logger.warning("Monitoring is already running")
            return

        self.is_running = True
        logger.info("Starting real-time monitoring")

        # 価格更新スレッド
        price_thread = threading.Thread(target=self._price_update_loop, daemon=True)
        price_thread.start()
        self.threads.append(price_thread)

        # アラート処理スレッド
        alert_thread = threading.Thread(target=self._alert_processing_loop, daemon=True)
        alert_thread.start()
        self.threads.append(alert_thread)

        # トレーリングストップ更新スレッド
        trailing_thread = threading.Thread(target=self._trailing_stop_loop, daemon=True)
        trailing_thread.start()
        self.threads.append(trailing_thread)

    def stop_monitoring(self):
        """リアルタイム監視停止"""
        logger.info("Stopping real-time monitoring")
        self.is_running = False

        # スレッド終了待機
        for thread in self.threads:
            thread.join(timeout=5)

        self.threads.clear()

    def get_monitoring_status(self) -> Dict:
        """
        監視状況を取得

        Returns:
            dict: 監視状況
        """
        total_pnl = sum(stock['pnl'] for stock in self.monitoring_stocks.values())
        winning_stocks = [s for s in self.monitoring_stocks.values() if s['pnl'] > 0]
        losing_stocks = [s for s in self.monitoring_stocks.values() if s['pnl'] < 0]

        return {
            'is_running': self.is_running,
            'monitoring_count': len(self.monitoring_stocks),
            'total_pnl': total_pnl,
            'winning_count': len(winning_stocks),
            'losing_count': len(losing_stocks),
            'win_rate': len(winning_stocks) / len(self.monitoring_stocks) if self.monitoring_stocks else 0,
            'stocks': list(self.monitoring_stocks.values()),
            'last_update': datetime.now()
        }

    def set_alert_condition(self, condition_func: Callable, name: str):
        """
        カスタムアラート条件を設定

        Args:
            condition_func: 条件判定関数
            name: 条件名
        """
        self.alert_conditions.append({
            'name': name,
            'func': condition_func
        })

    def _price_update_loop(self):
        """価格更新ループ"""
        while self.is_running:
            try:
                for symbol in list(self.monitoring_stocks.keys()):
                    if not self.is_running:
                        break

                    # 価格取得
                    current_price = self._fetch_current_price(symbol)
                    if current_price is None:
                        continue

                    stock = self.monitoring_stocks[symbol]
                    stock['current_price'] = current_price
                    stock['last_update'] = datetime.now()

                    # PnL計算
                    stock['pnl'] = current_price - stock['entry_price']
                    stock['pnl_percentage'] = (current_price - stock['entry_price']) / stock['entry_price'] * 100

                    # 高値・安値更新
                    stock['high_since_entry'] = max(stock['high_since_entry'], current_price)
                    stock['low_since_entry'] = min(stock['low_since_entry'], current_price)

                    # アラートチェック
                    self._check_alerts(symbol, stock)

                    logger.debug(f"{symbol}: {current_price:.2f} ({stock['pnl_percentage']:+.2f}%)")

                # 更新間隔待機
                time.sleep(self.update_interval)

            except Exception as e:
                logger.error(f"Error in price update loop: {e}")
                time.sleep(10)

    def _alert_processing_loop(self):
        """アラート処理ループ"""
        while self.is_running:
            try:
                # アラート取得（1秒タイムアウト）
                alert = self.alerts.get(timeout=1)

                # アラート処理
                self._process_alert(alert)

            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in alert processing: {e}")

    def _trailing_stop_loop(self):
        """トレーリングストップ更新ループ"""
        while self.is_running:
            try:
                for symbol, stock in self.monitoring_stocks.items():
                    if not self.is_running:
                        break

                    config = stock['alerts_config']
                    if not config.get('trailing_stop_enabled', False):
                        continue

                    trailing_percentage = config.get('trailing_stop_percentage', 0.02)
                    current_price = stock['current_price']
                    high_since_entry = stock['high_since_entry']

                    # トレーリングストップ価格計算
                    trailing_stop = high_since_entry * (1 - trailing_percentage)

                    # ストップロス更新
                    if trailing_stop > stock['stop_loss']:
                        old_stop = stock['stop_loss']
                        stock['stop_loss'] = trailing_stop

                        logger.info(f"{symbol}: Trailing stop updated: {old_stop:.2f} -> {trailing_stop:.2f}")

                        # アラート生成
                        self.alerts.put({
                            'type': 'trailing_stop_updated',
                            'symbol': symbol,
                            'old_stop': old_stop,
                            'new_stop': trailing_stop,
                            'current_price': current_price,
                            'timestamp': datetime.now()
                        })

                time.sleep(30)  # 30秒ごとに更新

            except Exception as e:
                logger.error(f"Error in trailing stop loop: {e}")
                time.sleep(10)

    def _check_alerts(self, symbol: str, stock: Dict):
        """アラート条件チェック"""
        current_price = stock['current_price']
        config = stock['alerts_config']

        # 損切りアラート
        if current_price <= stock['stop_loss']:
            self._trigger_alert(symbol, 'stop_loss', {
                'current_price': current_price,
                'stop_loss': stock['stop_loss'],
                'loss_percentage': stock['pnl_percentage']
            })

        # 利確アラート
        if current_price >= stock['take_profit']:
            self._trigger_alert(symbol, 'take_profit', {
                'current_price': current_price,
                'take_profit': stock['take_profit'],
                'profit_percentage': stock['pnl_percentage']
            })

        # 価格変動アラート
        change_threshold = config.get('price_change_threshold', 0.03)
        if abs(stock['pnl_percentage']) >= change_threshold * 100:
            self._trigger_alert(symbol, 'price_change', {
                'current_price': current_price,
                'change_percentage': stock['pnl_percentage']
            })

        # ボリューム急増アラート（実装には追加データ必要）
        # self._check_volume_alert(symbol, stock)

        # カスタムアラート条件
        for condition in self.alert_conditions:
            try:
                if condition['func'](stock):
                    self._trigger_alert(symbol, f"custom_{condition['name']}", {
                        'condition': condition['name'],
                        'stock_data': stock
                    })
            except Exception as e:
                logger.error(f"Error checking custom condition {condition['name']}: {e}")

    def _trigger_alert(self, symbol: str, alert_type: str, data: Dict):
        """アラートトリガー"""
        # 重複アラート防止
        alert_key = f"{symbol}_{alert_type}"
        if alert_key in self.alert_history:
            last_alert = self.alert_history[alert_key]
            if (datetime.now() - last_alert).seconds < 300:  # 5分以内は重複送信しない
                return

        alert = {
            'symbol': symbol,
            'type': alert_type,
            'data': data,
            'timestamp': datetime.now()
        }

        self.alerts.put(alert)
        self.alert_history[alert_key] = datetime.now()

        # triggered_alertsに追加
        if symbol in self.monitoring_stocks:
            self.monitoring_stocks[symbol]['triggered_alerts'].append(alert)

    def _process_alert(self, alert: Dict):
        """アラート処理"""
        try:
            symbol = alert['symbol']
            alert_type = alert['type']
            data = alert['data']

            # ログ出力
            logger.warning(f"ALERT [{symbol}] {alert_type}: {data}")

            # 通知メッセージ作成
            message = self._create_alert_message(alert)

            # 通知送信
            self.notifier.send_line_notify(message)

            # アラートタイプ別の追加処理
            if alert_type == 'stop_loss':
                self._handle_stop_loss(symbol, data)
            elif alert_type == 'take_profit':
                self._handle_take_profit(symbol, data)

        except Exception as e:
            logger.error(f"Error processing alert: {e}")

    def _create_alert_message(self, alert: Dict) -> str:
        """アラートメッセージ作成"""
        symbol = alert['symbol']
        alert_type = alert['type']
        data = alert['data']
        timestamp = alert['timestamp'].strftime('%H:%M:%S')

        if alert_type == 'stop_loss':
            return f"""
⚠️ 損切りアラート [{timestamp}]
銘柄: {symbol}
現在値: {data['current_price']:.0f}円
損失: {data['loss_percentage']:.1f}%
アクション: 売却検討
"""

        elif alert_type == 'take_profit':
            return f"""
✅ 利確アラート [{timestamp}]
銘柄: {symbol}
現在値: {data['current_price']:.0f}円
利益: {data['profit_percentage']:.1f}%
アクション: 利確検討
"""

        elif alert_type == 'price_change':
            emoji = "📈" if data['change_percentage'] > 0 else "📉"
            return f"""
{emoji} 価格変動アラート [{timestamp}]
銘柄: {symbol}
現在値: {data['current_price']:.0f}円
変動率: {data['change_percentage']:+.1f}%
"""

        elif alert_type == 'trailing_stop_updated':
            return f"""
🔄 トレーリングストップ更新 [{timestamp}]
銘柄: {symbol}
新しい損切り: {data['new_stop']:.0f}円
現在値: {data['current_price']:.0f}円
"""

        else:
            return f"""
📢 アラート [{timestamp}]
銘柄: {symbol}
タイプ: {alert_type}
詳細: {json.dumps(data, ensure_ascii=False)}
"""

    def _handle_stop_loss(self, symbol: str, data: Dict):
        """損切り処理"""
        if symbol in self.monitoring_stocks:
            self.monitoring_stocks[symbol]['status'] = 'stop_loss_triggered'
            logger.info(f"{symbol}: Stop loss triggered at {data['current_price']}")

    def _handle_take_profit(self, symbol: str, data: Dict):
        """利確処理"""
        if symbol in self.monitoring_stocks:
            self.monitoring_stocks[symbol]['status'] = 'take_profit_triggered'
            logger.info(f"{symbol}: Take profit triggered at {data['current_price']}")

    def _fetch_current_price(self, symbol: str) -> float:
        """現在価格取得"""
        try:
            # キャッシュチェック（10秒以内なら再利用）
            if symbol in self.price_cache:
                cache_time, cached_price = self.price_cache[symbol]
                if (datetime.now() - cache_time).seconds < 10:
                    return cached_price

            # Yahoo Financeから取得
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d', interval='1m')

            if not data.empty:
                current_price = float(data['Close'].iloc[-1])
                self.price_cache[symbol] = (datetime.now(), current_price)
                return current_price

        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")

        return None

    def _default_alerts_config(self) -> Dict:
        """デフォルトアラート設定"""
        return {
            'stop_loss_enabled': True,
            'take_profit_enabled': True,
            'trailing_stop_enabled': True,
            'trailing_stop_percentage': 0.02,
            'price_change_threshold': 0.03,
            'volume_alert_enabled': False,
            'volume_threshold': 2.0
        }

    def export_monitoring_data(self) -> pd.DataFrame:
        """
        監視データをDataFrameとしてエクスポート

        Returns:
            DataFrame: 監視データ
        """
        if not self.monitoring_stocks:
            return pd.DataFrame()

        data = []
        for symbol, stock in self.monitoring_stocks.items():
            data.append({
                'symbol': symbol,
                'entry_price': stock['entry_price'],
                'current_price': stock['current_price'],
                'stop_loss': stock['stop_loss'],
                'take_profit': stock['take_profit'],
                'pnl': stock['pnl'],
                'pnl_percentage': stock['pnl_percentage'],
                'high_since_entry': stock['high_since_entry'],
                'low_since_entry': stock['low_since_entry'],
                'status': stock['status'],
                'entry_time': stock['entry_time'],
                'last_update': stock['last_update']
            })

        return pd.DataFrame(data)


class PositionManager:
    """ポジション管理クラス"""

    def __init__(self, initial_capital: float = 1000000):
        """
        初期化

        Args:
            initial_capital: 初期資金
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {}
        self.closed_positions = []
        self.max_position_size = 0.2  # 最大ポジションサイズ（資金の20%）
        self.max_positions = 5  # 最大同時保有数

    def can_open_position(self) -> bool:
        """新規ポジション開設可能かチェック"""
        return len(self.positions) < self.max_positions

    def calculate_position_size(self, price: float, risk_percentage: float = 0.02) -> int:
        """
        ポジションサイズ計算（株数）

        Args:
            price: 株価
            risk_percentage: リスク率

        Returns:
            int: 購入株数
        """
        max_investment = self.current_capital * self.max_position_size
        risk_amount = self.current_capital * risk_percentage

        # 最小取引単位（100株）を考慮
        shares = int(min(max_investment, risk_amount) / price / 100) * 100

        return max(100, shares)

    def open_position(self, symbol: str, price: float, shares: int,
                      stop_loss: float = None, take_profit: float = None):
        """
        ポジションオープン

        Args:
            symbol: 銘柄コード
            price: エントリー価格
            shares: 株数
            stop_loss: 損切り価格
            take_profit: 利確価格
        """
        if symbol in self.positions:
            logger.warning(f"Position already exists for {symbol}")
            return False

        if not self.can_open_position():
            logger.warning("Maximum positions reached")
            return False

        investment = price * shares
        if investment > self.current_capital:
            logger.warning(f"Insufficient capital. Required: {investment}, Available: {self.current_capital}")
            return False

        self.positions[symbol] = {
            'symbol': symbol,
            'entry_price': price,
            'shares': shares,
            'stop_loss': stop_loss or price * 0.97,
            'take_profit': take_profit or price * 1.05,
            'entry_time': datetime.now(),
            'investment': investment,
            'current_value': investment,
            'pnl': 0,
            'status': 'open'
        }

        self.current_capital -= investment
        logger.info(f"Opened position: {symbol} @ {price} x {shares} shares")

        return True

    def close_position(self, symbol: str, exit_price: float, reason: str = 'manual'):
        """
        ポジションクローズ

        Args:
            symbol: 銘柄コード
            exit_price: 決済価格
            reason: 決済理由
        """
        if symbol not in self.positions:
            logger.warning(f"No position found for {symbol}")
            return False

        position = self.positions[symbol]
        exit_value = exit_price * position['shares']
        pnl = exit_value - position['investment']
        pnl_percentage = pnl / position['investment'] * 100

        # クローズドポジションに記録
        closed_position = {
            **position,
            'exit_price': exit_price,
            'exit_time': datetime.now(),
            'exit_value': exit_value,
            'pnl': pnl,
            'pnl_percentage': pnl_percentage,
            'reason': reason,
            'holding_period': (datetime.now() - position['entry_time']).total_seconds() / 3600
        }

        self.closed_positions.append(closed_position)

        # 資金を戻す
        self.current_capital += exit_value

        # ポジション削除
        del self.positions[symbol]

        logger.info(f"Closed position: {symbol} @ {exit_price}, PnL: {pnl:.0f} ({pnl_percentage:.1f}%)")

        return True

    def update_positions(self, price_dict: Dict[str, float]):
        """
        全ポジション更新

        Args:
            price_dict: 銘柄コード -> 現在価格の辞書
        """
        for symbol, position in self.positions.items():
            if symbol in price_dict:
                current_price = price_dict[symbol]
                position['current_value'] = current_price * position['shares']
                position['pnl'] = position['current_value'] - position['investment']

    def get_portfolio_status(self) -> Dict:
        """
        ポートフォリオ状況取得

        Returns:
            dict: ポートフォリオ統計
        """
        total_investment = sum(p['investment'] for p in self.positions.values())
        total_value = sum(p['current_value'] for p in self.positions.values())
        total_pnl = total_value - total_investment

        realized_pnl = sum(p['pnl'] for p in self.closed_positions)
        unrealized_pnl = total_pnl

        win_trades = [p for p in self.closed_positions if p['pnl'] > 0]
        lose_trades = [p for p in self.closed_positions if p['pnl'] < 0]

        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'invested_capital': total_investment,
            'total_value': self.current_capital + total_investment,
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_pnl': realized_pnl + unrealized_pnl,
            'return_percentage': ((self.current_capital + total_investment - self.initial_capital) /
                                 self.initial_capital * 100),
            'open_positions': len(self.positions),
            'closed_positions': len(self.closed_positions),
            'win_count': len(win_trades),
            'lose_count': len(lose_trades),
            'win_rate': len(win_trades) / len(self.closed_positions) if self.closed_positions else 0,
            'average_win': sum(p['pnl'] for p in win_trades) / len(win_trades) if win_trades else 0,
            'average_loss': sum(p['pnl'] for p in lose_trades) / len(lose_trades) if lose_trades else 0
        }