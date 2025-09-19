"""
データベース管理モジュール
SQLiteを使用した履歴データの永続化
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import json
from contextlib import contextmanager


class DatabaseManager:
    """データベース管理クラス"""

    def __init__(self, db_path: str = "data/trading_history.db"):
        """
        初期化

        Args:
            db_path: データベースファイルパス
        """
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """データベース接続のコンテキストマネージャー"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def init_database(self):
        """データベース初期化（テーブル作成）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # スクリーニング結果テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS screening_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    total_score REAL,
                    current_price REAL,
                    gap_ratio REAL,
                    volume_ratio REAL,
                    market_cap REAL,
                    signals TEXT,
                    warnings TEXT,
                    rank INTEGER,
                    screening_type TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 価格履歴テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            """)

            # テクニカル指標履歴テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS technical_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    rsi REAL,
                    macd REAL,
                    macd_signal REAL,
                    bb_upper REAL,
                    bb_middle REAL,
                    bb_lower REAL,
                    sma_5 REAL,
                    sma_25 REAL,
                    sma_75 REAL,
                    adx REAL,
                    atr REAL,
                    obv REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            """)

            # ポジション履歴テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    entry_time DATETIME NOT NULL,
                    exit_time DATETIME,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    shares INTEGER NOT NULL,
                    position_type TEXT DEFAULT 'long',
                    stop_loss REAL,
                    take_profit REAL,
                    pnl REAL,
                    pnl_percentage REAL,
                    exit_reason TEXT,
                    status TEXT DEFAULT 'open',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # アラート履歴テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT,
                    data TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ニュース履歴テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT,
                    title TEXT NOT NULL,
                    url TEXT,
                    category TEXT,
                    sentiment TEXT,
                    sentiment_score REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # バックテスト結果テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    initial_capital REAL NOT NULL,
                    final_capital REAL NOT NULL,
                    total_return REAL,
                    win_rate REAL,
                    sharpe_ratio REAL,
                    max_drawdown REAL,
                    total_trades INTEGER,
                    winning_trades INTEGER,
                    losing_trades INTEGER,
                    parameters TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # インデックス作成
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_screening_symbol ON screening_results(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_screening_timestamp ON screening_results(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_symbol_date ON price_history(symbol, date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_technical_symbol_date ON technical_indicators(symbol, date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol)")

            logger.info("Database initialized successfully")

    def save_screening_results(self, results: Dict):
        """
        スクリーニング結果を保存

        Args:
            results: スクリーニング結果
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            timestamp = results.get('timestamp', datetime.now())
            screening_type = results.get('screening_type', 'full')

            for stock in results.get('top_picks', []) + results.get('watch_list', []):
                cursor.execute("""
                    INSERT INTO screening_results
                    (timestamp, symbol, name, total_score, current_price, gap_ratio,
                     volume_ratio, market_cap, signals, warnings, rank, screening_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    stock.get('symbol'),
                    stock.get('name'),
                    stock.get('total_score'),
                    stock.get('current_price'),
                    stock.get('gap_ratio'),
                    stock.get('volume_ratio'),
                    stock.get('market_cap'),
                    json.dumps(stock.get('signals', [])),
                    json.dumps(stock.get('warnings', [])),
                    stock.get('rank'),
                    screening_type
                ))

            logger.info(f"Saved {len(results.get('top_picks', []) + results.get('watch_list', []))} screening results")

    def save_price_history(self, symbol: str, df: pd.DataFrame):
        """
        価格履歴を保存

        Args:
            symbol: 銘柄コード
            df: 価格データのDataFrame
        """
        with self.get_connection() as conn:
            for index, row in df.iterrows():
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO price_history
                        (symbol, date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol,
                        index.date() if hasattr(index, 'date') else index,
                        row['Open'],
                        row['High'],
                        row['Low'],
                        row['Close'],
                        row['Volume']
                    ))
                except Exception as e:
                    logger.warning(f"Error saving price for {symbol} on {index}: {e}")

            logger.debug(f"Saved {len(df)} price records for {symbol}")

    def save_technical_indicators(self, symbol: str, date: datetime, indicators: Dict):
        """
        テクニカル指標を保存

        Args:
            symbol: 銘柄コード
            date: 日付
            indicators: テクニカル指標の辞書
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO technical_indicators
                (symbol, date, rsi, macd, macd_signal, bb_upper, bb_middle, bb_lower,
                 sma_5, sma_25, sma_75, adx, atr, obv)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                date.date() if hasattr(date, 'date') else date,
                indicators.get('rsi', {}).get('value'),
                indicators.get('macd', {}).get('macd'),
                indicators.get('macd', {}).get('signal'),
                indicators.get('bollinger', {}).get('upper'),
                indicators.get('bollinger', {}).get('middle'),
                indicators.get('bollinger', {}).get('lower'),
                indicators.get('sma_5'),
                indicators.get('sma_25'),
                indicators.get('sma_75'),
                indicators.get('adx', {}).get('value'),
                indicators.get('atr', {}).get('value'),
                indicators.get('obv', {}).get('value')
            ))

    def save_position(self, position: Dict):
        """
        ポジション情報を保存

        Args:
            position: ポジション情報
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO positions
                (symbol, entry_time, exit_time, entry_price, exit_price, shares,
                 position_type, stop_loss, take_profit, pnl, pnl_percentage,
                 exit_reason, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.get('symbol'),
                position.get('entry_time'),
                position.get('exit_time'),
                position.get('entry_price'),
                position.get('exit_price'),
                position.get('shares'),
                position.get('position_type', 'long'),
                position.get('stop_loss'),
                position.get('take_profit'),
                position.get('pnl'),
                position.get('pnl_percentage'),
                position.get('exit_reason'),
                position.get('status', 'open')
            ))

            logger.info(f"Saved position for {position.get('symbol')}")

    def save_alert(self, alert: Dict):
        """
        アラート情報を保存

        Args:
            alert: アラート情報
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO alerts (timestamp, symbol, alert_type, message, data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                alert.get('timestamp', datetime.now()),
                alert.get('symbol'),
                alert.get('type'),
                alert.get('message'),
                json.dumps(alert.get('data', {}))
            ))

    def save_backtest_result(self, result: Dict):
        """
        バックテスト結果を保存

        Args:
            result: バックテスト結果
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO backtest_results
                (test_name, start_date, end_date, initial_capital, final_capital,
                 total_return, win_rate, sharpe_ratio, max_drawdown,
                 total_trades, winning_trades, losing_trades, parameters)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.get('test_name'),
                result.get('start_date'),
                result.get('end_date'),
                result.get('initial_capital'),
                result.get('final_capital'),
                result.get('total_return'),
                result.get('win_rate'),
                result.get('sharpe_ratio'),
                result.get('max_drawdown'),
                result.get('total_trades'),
                result.get('winning_trades'),
                result.get('losing_trades'),
                json.dumps(result.get('parameters', {}))
            ))

            logger.info(f"Saved backtest result: {result.get('test_name')}")

    def get_screening_history(self, symbol: str = None, days: int = 30) -> pd.DataFrame:
        """
        スクリーニング履歴を取得

        Args:
            symbol: 銘柄コード（Noneの場合全銘柄）
            days: 取得日数

        Returns:
            DataFrame: スクリーニング履歴
        """
        with self.get_connection() as conn:
            query = """
                SELECT * FROM screening_results
                WHERE timestamp > datetime('now', '-{} days')
            """.format(days)

            if symbol:
                query += f" AND symbol = '{symbol}'"

            query += " ORDER BY timestamp DESC, rank ASC"

            df = pd.read_sql_query(query, conn)

            # JSON文字列をリストに変換
            if not df.empty:
                df['signals'] = df['signals'].apply(lambda x: json.loads(x) if x else [])
                df['warnings'] = df['warnings'].apply(lambda x: json.loads(x) if x else [])

            return df

    def get_price_history(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        価格履歴を取得

        Args:
            symbol: 銘柄コード
            start_date: 開始日
            end_date: 終了日

        Returns:
            DataFrame: 価格履歴
        """
        with self.get_connection() as conn:
            query = f"SELECT * FROM price_history WHERE symbol = '{symbol}'"

            if start_date:
                query += f" AND date >= '{start_date}'"
            if end_date:
                query += f" AND date <= '{end_date}'"

            query += " ORDER BY date ASC"

            df = pd.read_sql_query(query, conn, parse_dates=['date'])

            if not df.empty:
                df.set_index('date', inplace=True)

            return df

    def get_position_history(self, status: str = None) -> pd.DataFrame:
        """
        ポジション履歴を取得

        Args:
            status: ステータス（'open', 'closed', None=全て）

        Returns:
            DataFrame: ポジション履歴
        """
        with self.get_connection() as conn:
            query = "SELECT * FROM positions"

            if status:
                query += f" WHERE status = '{status}'"

            query += " ORDER BY entry_time DESC"

            df = pd.read_sql_query(query, conn, parse_dates=['entry_time', 'exit_time'])

            return df

    def get_performance_stats(self, days: int = 30) -> Dict:
        """
        パフォーマンス統計を取得

        Args:
            days: 集計日数

        Returns:
            dict: パフォーマンス統計
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 期間内のポジション統計
            cursor.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(pnl) as total_pnl,
                    AVG(pnl_percentage) as avg_return,
                    MAX(pnl) as best_trade,
                    MIN(pnl) as worst_trade
                FROM positions
                WHERE exit_time > datetime('now', '-{} days')
                AND status = 'closed'
            """.format(days))

            stats = dict(cursor.fetchone())

            # 勝率計算
            if stats['total_trades'] > 0:
                stats['win_rate'] = stats['winning_trades'] / stats['total_trades']
            else:
                stats['win_rate'] = 0

            # スクリーニング精度（TOP5の翌日パフォーマンス）
            cursor.execute("""
                SELECT AVG(accuracy) as screening_accuracy
                FROM (
                    SELECT
                        s1.symbol,
                        s1.timestamp,
                        CASE
                            WHEN p2.close > p1.close THEN 1.0
                            ELSE 0.0
                        END as accuracy
                    FROM screening_results s1
                    JOIN price_history p1 ON s1.symbol = p1.symbol
                        AND DATE(s1.timestamp) = p1.date
                    JOIN price_history p2 ON s1.symbol = p2.symbol
                        AND p2.date = DATE(p1.date, '+1 day')
                    WHERE s1.rank <= 5
                    AND s1.timestamp > datetime('now', '-{} days')
                )
            """.format(days))

            result = cursor.fetchone()
            if result and result[0]:
                stats['screening_accuracy'] = result[0]
            else:
                stats['screening_accuracy'] = 0

            return stats

    def get_top_performers(self, days: int = 30, limit: int = 10) -> pd.DataFrame:
        """
        高パフォーマンス銘柄を取得

        Args:
            days: 集計日数
            limit: 取得数

        Returns:
            DataFrame: 高パフォーマンス銘柄
        """
        with self.get_connection() as conn:
            query = """
                SELECT
                    symbol,
                    COUNT(*) as appearance_count,
                    AVG(total_score) as avg_score,
                    AVG(gap_ratio) as avg_gap_ratio,
                    AVG(volume_ratio) as avg_volume_ratio
                FROM screening_results
                WHERE timestamp > datetime('now', '-{} days')
                AND rank <= 20
                GROUP BY symbol
                ORDER BY appearance_count DESC, avg_score DESC
                LIMIT {}
            """.format(days, limit)

            df = pd.read_sql_query(query, conn)

            return df

    def cleanup_old_data(self, days_to_keep: int = 90):
        """
        古いデータを削除

        Args:
            days_to_keep: 保持する日数
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            tables = [
                'screening_results',
                'price_history',
                'technical_indicators',
                'alerts',
                'news_history'
            ]

            for table in tables:
                cursor.execute(f"""
                    DELETE FROM {table}
                    WHERE created_at < datetime('now', '-{days_to_keep} days')
                """)

                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info(f"Deleted {deleted} old records from {table}")

    def export_to_excel(self, output_path: str = "data/trading_history.xlsx"):
        """
        データベース全体をExcelファイルにエクスポート

        Args:
            output_path: 出力ファイルパス
        """
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # 各テーブルを別シートとしてエクスポート
            tables = {
                'スクリーニング結果': 'screening_results',
                '価格履歴': 'price_history',
                'テクニカル指標': 'technical_indicators',
                'ポジション': 'positions',
                'アラート': 'alerts'
            }

            with self.get_connection() as conn:
                for sheet_name, table_name in tables.items():
                    query = f"SELECT * FROM {table_name} ORDER BY created_at DESC LIMIT 10000"
                    df = pd.read_sql_query(query, conn)

                    if not df.empty:
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        logger.info(f"Exported {len(df)} records from {table_name}")

        logger.info(f"Database exported to {output_path}")