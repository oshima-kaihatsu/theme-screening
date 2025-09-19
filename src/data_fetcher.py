"""
データ取得モジュール

主要機能:
1. 株価データ取得（Yahoo Finance API）
2. ニュース取得（株探RSS/スクレイピング）
3. Twitter情報取得
4. 板情報・気配値取得（可能な範囲で）
"""

import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import feedparser
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from loguru import logger
import numpy as np
import ta


class DataFetcher:
    """データ取得クラス"""

    def __init__(self, config: Dict):
        """
        初期化
        - API認証情報の設定
        - セッションの初期化
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # キャッシュ設定
        self.cache = {}
        self.cache_ttl = {
            'stock_list': 86400,      # 24時間
            'price_data': 300,        # 5分
            'news_data': 1800,        # 30分
            'sector_data': 3600       # 1時間
        }

    def fetch_stock_list(self) -> pd.DataFrame:
        """
        取引可能な全銘柄リストを取得

        Returns:
            DataFrame: columns=['symbol', 'name', 'market', 'market_cap', 'is_marginable']
        """
        cache_key = 'stock_list'

        # キャッシュチェック
        if self._is_cache_valid(cache_key):
            logger.info("Using cached stock list")
            return self.cache[cache_key]['data']

        try:
            logger.info("Fetching stock list from data source")

            # 東証の主要銘柄のサンプルリスト（実際の実装では、より包括的なデータソースを使用）
            sample_stocks = [
                {'symbol': '7203.T', 'name': 'トヨタ自動車', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '9984.T', 'name': 'ソフトバンクグループ', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '6098.T', 'name': 'リクルートホールディングス', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '8058.T', 'name': '三菱商事', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '9432.T', 'name': 'NTT', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '6981.T', 'name': '村田製作所', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '4568.T', 'name': '第一三共', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '8306.T', 'name': '三菱UFJフィナンシャル・グループ', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '6594.T', 'name': '日本電産', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '7974.T', 'name': '任天堂', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '4063.T', 'name': '信越化学工業', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '9983.T', 'name': 'ファーストリテイリング', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '8035.T', 'name': '東京エレクトロン', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '6857.T', 'name': 'アドバンテスト', 'market': 'Prime', 'is_marginable': True},
                {'symbol': '4519.T', 'name': '中外製薬', 'market': 'Prime', 'is_marginable': True},
            ]

            df = pd.DataFrame(sample_stocks)

            # 時価総額情報を追加取得
            for idx, row in df.iterrows():
                try:
                    ticker = yf.Ticker(row['symbol'])
                    info = ticker.info
                    df.at[idx, 'market_cap'] = info.get('marketCap', 0)
                    time.sleep(0.1)  # レート制限対策
                except Exception as e:
                    logger.warning(f"Failed to get market cap for {row['symbol']}: {e}")
                    df.at[idx, 'market_cap'] = 0

            # キャッシュに保存
            self._cache_data(cache_key, df)

            logger.info(f"Successfully fetched {len(df)} stocks")
            return df

        except Exception as e:
            logger.error(f"Error fetching stock list: {e}")
            return pd.DataFrame()

    def fetch_price_data(self, symbol: str, period: str = "5d") -> Dict:
        """
        個別銘柄の株価データ取得

        Args:
            symbol: 銘柄コード（例: "7203.T"）
            period: 取得期間

        Returns:
            dict: 価格データと計算された指標
        """
        cache_key = f'price_data_{symbol}_{period}'

        # キャッシュチェック
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]['data']

        try:
            logger.debug(f"Fetching price data for {symbol}")

            ticker = yf.Ticker(symbol)

            # 過去5日分のデータを取得
            hist = ticker.history(period=period)

            if hist.empty:
                logger.warning(f"No price data found for {symbol}")
                return {}

            # 現在の価格情報
            current_data = hist.iloc[-1]
            previous_data = hist.iloc[-2] if len(hist) > 1 else current_data

            # 平均出来高計算（過去5日間）
            average_volume = hist['Volume'].mean()

            # ギャップ率計算
            gap_ratio = (current_data['Open'] - previous_data['Close']) / previous_data['Close']

            # 出来高比率計算
            volume_ratio = current_data['Volume'] / average_volume if average_volume > 0 else 1

            result = {
                'current_price': float(current_data['Close']),
                'previous_close': float(previous_data['Close']),
                'open': float(current_data['Open']),
                'high': float(current_data['High']),
                'low': float(current_data['Low']),
                'volume': int(current_data['Volume']),
                'average_volume': float(average_volume),
                'gap_ratio': float(gap_ratio),
                'volume_ratio': float(volume_ratio),
                'price_data': hist
            }

            # キャッシュに保存
            self._cache_data(cache_key, result)

            return result

        except Exception as e:
            logger.error(f"Error fetching price data for {symbol}: {e}")
            return {}

    def fetch_technical_indicators(self, symbol: str) -> Dict:
        """
        テクニカル指標を計算

        Returns:
            dict: テクニカル指標の辞書
        """
        try:
            # 価格データを取得
            price_data = self.fetch_price_data(symbol, period="30d")

            if not price_data or 'price_data' not in price_data:
                return {}

            df = price_data['price_data']

            if len(df) < 25:  # 最低25日分のデータが必要
                logger.warning(f"Insufficient data for technical indicators: {symbol}")
                return {}

            # 移動平均線計算
            sma_5 = ta.trend.sma_indicator(df['Close'], window=5).iloc[-1]
            sma_25 = ta.trend.sma_indicator(df['Close'], window=25).iloc[-1]

            current_price = df['Close'].iloc[-1]

            # 移動平均線からの乖離率
            position_vs_sma5 = (current_price - sma_5) / sma_5 if sma_5 > 0 else 0
            position_vs_sma25 = (current_price - sma_25) / sma_25 if sma_25 > 0 else 0

            # レジスタンス・サポートレベル（過去20日間の高値・安値）
            recent_data = df.tail(20)
            resistance_levels = recent_data['High'].nlargest(3).tolist()
            support_levels = recent_data['Low'].nsmallest(3).tolist()

            # ローソク足パターン分析
            candlestick_pattern = self._analyze_candlestick_pattern(df.tail(5))

            result = {
                'sma_5': float(sma_5),
                'sma_25': float(sma_25),
                'position_vs_sma5': float(position_vs_sma5),
                'position_vs_sma25': float(position_vs_sma25),
                'resistance_levels': [float(x) for x in resistance_levels],
                'support_levels': [float(x) for x in support_levels],
                'candlestick_pattern': candlestick_pattern
            }

            return result

        except Exception as e:
            logger.error(f"Error calculating technical indicators for {symbol}: {e}")
            return {}

    def fetch_news(self, symbol: str = None) -> List[Dict]:
        """
        ニュース取得（株探）

        Args:
            symbol: 特定銘柄のニュースを取得する場合は銘柄コード

        Returns:
            list: ニュース記事のリスト
        """
        cache_key = f'news_{symbol or "general"}'

        # キャッシュチェック
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]['data']

        try:
            logger.debug(f"Fetching news for {symbol or 'general market'}")

            # 株探のRSSから取得
            rss_url = self.config.get('data_sources', {}).get('news_sources', {}).get('kabutan', {}).get('rss', '')

            if not rss_url:
                logger.warning("RSS URL not configured")
                return []

            feed = feedparser.parse(rss_url)
            news_list = []

            for entry in feed.entries[:10]:  # 最新10件
                # 簡単な感情分析（キーワードベース）
                sentiment = self._analyze_news_sentiment(entry.title + " " + entry.get('summary', ''))

                news_item = {
                    'title': entry.title,
                    'url': entry.link,
                    'datetime': datetime.now(),  # 実際の実装では entry.published をパース
                    'symbol': symbol or '',
                    'category': self._categorize_news(entry.title),
                    'sentiment': sentiment
                }

                news_list.append(news_item)

            # キャッシュに保存
            self._cache_data(cache_key, news_list)

            return news_list

        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []

    def fetch_sector_data(self, sector: str) -> Dict:
        """
        セクター全体の動向を取得

        Returns:
            dict: セクター情報
        """
        cache_key = f'sector_{sector}'

        # キャッシュチェック
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]['data']

        try:
            # サンプル実装（実際の実装では、より詳細なセクターデータを取得）
            result = {
                'sector_performance': 0.0,  # セクター平均騰落率
                'top_performers': [],       # 上位銘柄
                'sector_volume_ratio': 1.0  # セクター全体の出来高比率
            }

            # キャッシュに保存
            self._cache_data(cache_key, result)

            return result

        except Exception as e:
            logger.error(f"Error fetching sector data for {sector}: {e}")
            return {}

    def _analyze_candlestick_pattern(self, df: pd.DataFrame) -> str:
        """ローソク足パターンを分析"""
        if len(df) < 1:
            return "unknown"

        last_candle = df.iloc[-1]

        # 下ヒゲの長さを計算
        body_bottom = min(last_candle['Open'], last_candle['Close'])
        lower_shadow_ratio = (body_bottom - last_candle['Low']) / (last_candle['High'] - last_candle['Low'])

        # 高値引けかどうか
        close_position = (last_candle['Close'] - last_candle['Low']) / (last_candle['High'] - last_candle['Low'])

        if lower_shadow_ratio > 0.3 and last_candle['Close'] > last_candle['Open']:
            return "lower_shadow"
        elif close_position > 0.8:
            return "high_close"
        else:
            return "normal"

    def _analyze_news_sentiment(self, text: str) -> str:
        """ニュースの感情分析（簡易版）"""
        positive_keywords = ['増益', '上方修正', '好調', '拡大', '成長', '回復']
        negative_keywords = ['減益', '下方修正', '不調', '縮小', '悪化', '低迷']

        positive_count = sum(1 for keyword in positive_keywords if keyword in text)
        negative_count = sum(1 for keyword in negative_keywords if keyword in text)

        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'

    def _categorize_news(self, title: str) -> str:
        """ニュースをカテゴリ分類"""
        if '決算' in title:
            return '決算'
        elif '修正' in title:
            return '業績修正'
        else:
            return 'その他'

    def _is_cache_valid(self, key: str) -> bool:
        """キャッシュの有効性をチェック"""
        if key not in self.cache:
            return False

        cache_entry = self.cache[key]
        cache_time = cache_entry['timestamp']
        ttl = self.cache_ttl.get(key.split('_')[0], 300)  # デフォルト5分

        return (datetime.now() - cache_time).total_seconds() < ttl

    def _cache_data(self, key: str, data):
        """データをキャッシュに保存"""
        self.cache[key] = {
            'data': data,
            'timestamp': datetime.now()
        }