"""
分析・スコアリングモジュール

銘柄ごとにスコアを計算し、ランキングを作成
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from loguru import logger
from datetime import datetime


class StockAnalyzer:
    """株式分析・スコアリングクラス"""

    def __init__(self, config: Dict, data_fetcher):
        """
        初期化
        - スコアリング重みの設定
        - 閾値の設定
        """
        self.config = config
        self.data_fetcher = data_fetcher
        self.scoring_weights = config.get('screening', {}).get('scoring_weights', {})
        self.filters = config.get('screening', {}).get('filters', {})

    def calculate_score(self, stock_data: Dict) -> Dict:
        """
        個別銘柄のスコア計算

        Args:
            stock_data: DataFetcherから取得した銘柄データ

        Returns:
            dict: スコア詳細と分析結果
        """
        try:
            symbol = stock_data.get('symbol', '')
            logger.debug(f"Calculating score for {symbol}")

            # 各スコア要素を計算
            volume_score = self._calculate_volume_score(stock_data)
            gap_score = self._calculate_gap_score(stock_data)
            technical_score = self._calculate_technical_score(stock_data)
            news_score = self._calculate_news_score(stock_data)
            social_score = self._calculate_social_score(stock_data)
            sector_score = self._calculate_sector_score(stock_data)

            # 総合スコア計算
            total_score = (
                volume_score +
                gap_score +
                technical_score +
                news_score +
                social_score +
                sector_score
            )

            # 0-100の範囲に正規化
            total_score = max(0, min(100, total_score))

            # シグナル検出
            signals = self.detect_entry_signals(stock_data)

            # リスク警告
            warnings = self._detect_warnings(stock_data)

            result = {
                'symbol': symbol,
                'total_score': round(total_score, 2),
                'score_breakdown': {
                    'volume_score': round(volume_score, 2),
                    'gap_score': round(gap_score, 2),
                    'technical_score': round(technical_score, 2),
                    'news_score': round(news_score, 2),
                    'social_score': round(social_score, 2),
                    'sector_score': round(sector_score, 2)
                },
                'signals': signals,
                'warnings': warnings
            }

            return result

        except Exception as e:
            logger.error(f"Error calculating score for {stock_data.get('symbol', 'unknown')}: {e}")
            return {'symbol': stock_data.get('symbol', ''), 'total_score': 0, 'error': str(e)}

    def apply_filters(self, stocks: List[Dict]) -> List[Dict]:
        """
        基本フィルターを適用

        フィルター条件:
        - 売買代金 >= 5億円
        - 時価総額 100億〜1000億円
        - 貸借銘柄（信用取引可能）
        - ボラティリティ >= 2%

        Returns:
            list: フィルター通過銘柄のリスト
        """
        filtered_stocks = []

        for stock in stocks:
            try:
                # 売買代金チェック（価格 × 出来高）
                trading_value = stock.get('current_price', 0) * stock.get('volume', 0)
                if trading_value < self.filters.get('min_trading_value', 500000000):
                    continue

                # 時価総額チェック
                market_cap = stock.get('market_cap', 0)
                if (market_cap < self.filters.get('min_market_cap', 10000000000) or
                        market_cap > self.filters.get('max_market_cap', 100000000000)):
                    continue

                # 信用取引可能チェック
                if not stock.get('is_marginable', False):
                    continue

                # ボラティリティチェック（前日比変動率）
                volatility = abs(stock.get('gap_ratio', 0))
                if volatility < self.filters.get('min_volatility', 0.02):
                    continue

                filtered_stocks.append(stock)

            except Exception as e:
                logger.warning(f"Error applying filter to {stock.get('symbol', 'unknown')}: {e}")
                continue

        logger.info(f"Filtered {len(filtered_stocks)} stocks from {len(stocks)} total")
        return filtered_stocks

    def detect_entry_signals(self, stock_data: Dict) -> List[str]:
        """
        エントリーシグナルを検出

        検出シグナル:
        - 出来高急増（前日比200%以上）
        - 移動平均線ブレイクアウト
        - レジスタンス突破
        - 下ヒゲ陽線からの反発
        - ニュース材料（決算、業績修正）

        Returns:
            list: 検出されたシグナルのリスト
        """
        signals = []

        try:
            # 出来高急増シグナル
            volume_ratio = stock_data.get('volume_ratio', 1)
            if volume_ratio >= 2.0:
                signals.append(f"出来高急増 (前日比{volume_ratio:.1f}倍)")

            # ギャップアップシグナル
            gap_ratio = stock_data.get('gap_ratio', 0)
            if 0.02 <= gap_ratio <= 0.05:
                signals.append(f"適度なギャップアップ ({gap_ratio:.1%})")
            elif 0.05 < gap_ratio <= 0.10:
                signals.append(f"大幅ギャップアップ ({gap_ratio:.1%})")

            # テクニカル指標シグナル
            technical = stock_data.get('technical_indicators', {})
            if technical:
                # 5日移動平均線突破
                if technical.get('position_vs_sma5', 0) > 0.01:
                    signals.append("5日移動平均線突破")

                # 25日移動平均線突破
                if technical.get('position_vs_sma25', 0) > 0.01:
                    signals.append("25日移動平均線突破")

                # ローソク足パターン
                pattern = technical.get('candlestick_pattern', '')
                if pattern == 'lower_shadow':
                    signals.append("下ヒゲ陽線")
                elif pattern == 'high_close':
                    signals.append("高値引け")

                # レジスタンス突破
                current_price = stock_data.get('current_price', 0)
                resistance_levels = technical.get('resistance_levels', [])
                if resistance_levels and current_price > min(resistance_levels) * 1.005:
                    signals.append("レジスタンス突破")

            # ニュース材料シグナル
            news_list = stock_data.get('news', [])
            for news in news_list:
                if news.get('sentiment') == 'positive':
                    category = news.get('category', '')
                    if category in ['決算', '業績修正']:
                        signals.append(f"好材料ニュース ({category})")

        except Exception as e:
            logger.error(f"Error detecting signals: {e}")

        return signals

    def calculate_risk_metrics(self, stock_data: Dict) -> Dict:
        """
        リスク指標を計算

        Returns:
            dict: リスク情報
        """
        try:
            current_price = stock_data.get('current_price', 0)
            gap_ratio = stock_data.get('gap_ratio', 0)
            volume_ratio = stock_data.get('volume_ratio', 1)

            # リスクレベル判定
            risk_level = 'low'
            warnings = []

            # ギャップアップが大きすぎる場合
            if gap_ratio > 0.10:
                risk_level = 'high'
                warnings.append('極端なギャップアップ')
            elif gap_ratio > 0.05:
                risk_level = 'medium'
                warnings.append('大幅なギャップアップ')

            # 出来高が異常に多い場合
            if volume_ratio > 5.0:
                risk_level = 'high'
                warnings.append('異常な出来高急増')

            # ストップロス・利確価格計算
            stop_loss_ratio = 0.03  # 3%下
            take_profit_ratio = 0.05  # 5%上

            stop_loss_price = current_price * (1 - stop_loss_ratio)
            take_profit_price = current_price * (1 + take_profit_ratio)

            # リスクリワード比率
            risk_reward_ratio = take_profit_ratio / stop_loss_ratio

            return {
                'risk_level': risk_level,
                'stop_loss_price': round(stop_loss_price, 2),
                'take_profit_price': round(take_profit_price, 2),
                'risk_reward_ratio': round(risk_reward_ratio, 2),
                'warnings': warnings
            }

        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return {'risk_level': 'unknown', 'warnings': []}

    def rank_stocks(self, analyzed_stocks: List[Dict]) -> List[Dict]:
        """
        スコアに基づいてランキング作成

        Returns:
            list: スコア順にソートされた銘柄リスト（上位20銘柄）
        """
        try:
            # スコアでソート
            ranked_stocks = sorted(
                analyzed_stocks,
                key=lambda x: x.get('total_score', 0),
                reverse=True
            )

            # 上位20銘柄に限定
            top_stocks = ranked_stocks[:20]

            # ランキング番号を追加
            for i, stock in enumerate(top_stocks):
                stock['rank'] = i + 1

            logger.info(f"Ranked {len(top_stocks)} stocks")
            return top_stocks

        except Exception as e:
            logger.error(f"Error ranking stocks: {e}")
            return []

    def _calculate_volume_score(self, stock_data: Dict) -> float:
        """出来高スコア計算"""
        volume_ratio = stock_data.get('volume_ratio', 1)

        if volume_ratio >= 3.0:
            return self.scoring_weights.get('volume_surge', 30)
        elif volume_ratio >= 2.0:
            return self.scoring_weights.get('volume_surge', 30) * 0.8
        elif volume_ratio >= 1.5:
            return self.scoring_weights.get('volume_surge', 30) * 0.5
        else:
            return 0

    def _calculate_gap_score(self, stock_data: Dict) -> float:
        """ギャップスコア計算"""
        gap_ratio = stock_data.get('gap_ratio', 0)

        if gap_ratio > 0.10:
            return self.scoring_weights.get('gap_up_extreme', -10)
        elif gap_ratio > 0.05:
            return self.scoring_weights.get('gap_up_high', 10)
        elif gap_ratio >= 0.02:
            return self.scoring_weights.get('gap_up_moderate', 20)
        else:
            return 0

    def _calculate_technical_score(self, stock_data: Dict) -> float:
        """テクニカルスコア計算"""
        technical = stock_data.get('technical_indicators', {})
        score = 0

        # 移動平均線突破
        if technical.get('position_vs_sma5', 0) > 0:
            score += self.scoring_weights.get('ma5_breakout', 15)

        if technical.get('position_vs_sma25', 0) > 0:
            score += self.scoring_weights.get('ma25_breakout', 20)

        # ローソク足パターン
        pattern = technical.get('candlestick_pattern', '')
        if pattern == 'lower_shadow':
            score += self.scoring_weights.get('lower_shadow', 10)
        elif pattern == 'high_close':
            score += self.scoring_weights.get('high_close', 10)

        # レジスタンス突破
        current_price = stock_data.get('current_price', 0)
        resistance_levels = technical.get('resistance_levels', [])
        if resistance_levels and current_price > min(resistance_levels) * 1.005:
            score += self.scoring_weights.get('resistance_break', 15)

        return score

    def _calculate_news_score(self, stock_data: Dict) -> float:
        """ニューススコア計算"""
        news_list = stock_data.get('news', [])
        score = 0

        for news in news_list:
            if news.get('sentiment') == 'positive':
                score += self.scoring_weights.get('positive_news', 25)

        return min(score, self.scoring_weights.get('positive_news', 25))  # 上限設定

    def _calculate_social_score(self, stock_data: Dict) -> float:
        """ソーシャルメディアスコア計算"""
        # Twitter言及データがある場合の実装（現在はサンプル）
        return 0

    def _calculate_sector_score(self, stock_data: Dict) -> float:
        """セクタースコア計算"""
        sector_data = stock_data.get('sector_data', {})
        sector_performance = sector_data.get('sector_performance', 0)

        if sector_performance > 0.02:
            return self.scoring_weights.get('sector_momentum', 10)
        else:
            return 0

    def _detect_warnings(self, stock_data: Dict) -> List[str]:
        """警告を検出"""
        warnings = []

        # 極端なギャップアップ
        gap_ratio = stock_data.get('gap_ratio', 0)
        if gap_ratio > 0.10:
            warnings.append('極端なギャップアップ注意')

        # 異常な出来高
        volume_ratio = stock_data.get('volume_ratio', 1)
        if volume_ratio > 5.0:
            warnings.append('異常な出来高急増')

        return warnings