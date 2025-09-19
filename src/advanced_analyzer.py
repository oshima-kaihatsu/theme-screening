"""
拡張分析モジュール
Phase 2: 高度なテクニカル指標とニュース分析
"""

import pandas as pd
import numpy as np
import ta
from typing import Dict, List, Tuple
from loguru import logger
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta


class AdvancedTechnicalAnalyzer:
    """高度なテクニカル分析クラス"""

    def __init__(self):
        """初期化"""
        self.indicators = {}

    def calculate_all_indicators(self, df: pd.DataFrame) -> Dict:
        """
        全てのテクニカル指標を計算

        Args:
            df: OHLCV DataFrame

        Returns:
            dict: 計算された指標
        """
        if len(df) < 30:
            logger.warning("Insufficient data for advanced indicators")
            return {}

        try:
            indicators = {
                'rsi': self.calculate_rsi(df),
                'macd': self.calculate_macd(df),
                'bollinger': self.calculate_bollinger_bands(df),
                'stochastic': self.calculate_stochastic(df),
                'adx': self.calculate_adx(df),
                'obv': self.calculate_obv(df),
                'vwap': self.calculate_vwap(df),
                'atr': self.calculate_atr(df),
                'pivot_points': self.calculate_pivot_points(df),
                'fibonacci': self.calculate_fibonacci_levels(df),
                'volume_profile': self.calculate_volume_profile(df),
                'trend_strength': self.analyze_trend_strength(df)
            }

            # シグナルの統合評価
            indicators['signal_summary'] = self.evaluate_signals(indicators)

            return indicators

        except Exception as e:
            logger.error(f"Error calculating advanced indicators: {e}")
            return {}

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Dict:
        """
        RSI（相対力指数）計算

        Returns:
            dict: RSI値と状態
        """
        rsi = ta.momentum.RSIIndicator(df['Close'], window=period)
        rsi_value = rsi.rsi().iloc[-1]

        # RSI解釈
        if rsi_value > 70:
            status = 'overbought'
            signal = 'sell'
        elif rsi_value < 30:
            status = 'oversold'
            signal = 'buy'
        else:
            status = 'neutral'
            signal = 'hold'

        # ダイバージェンス検出
        divergence = self._detect_rsi_divergence(df, rsi.rsi())

        return {
            'value': float(rsi_value),
            'status': status,
            'signal': signal,
            'divergence': divergence
        }

    def calculate_macd(self, df: pd.DataFrame) -> Dict:
        """
        MACD計算

        Returns:
            dict: MACD、シグナル、ヒストグラム
        """
        macd = ta.trend.MACD(df['Close'])

        macd_line = macd.macd().iloc[-1]
        signal_line = macd.macd_signal().iloc[-1]
        histogram = macd.macd_diff().iloc[-1]

        # 前日のヒストグラム
        prev_histogram = macd.macd_diff().iloc[-2]

        # クロスオーバー検出
        crossover = None
        if prev_histogram < 0 and histogram > 0:
            crossover = 'bullish'
        elif prev_histogram > 0 and histogram < 0:
            crossover = 'bearish'

        return {
            'macd': float(macd_line),
            'signal': float(signal_line),
            'histogram': float(histogram),
            'crossover': crossover,
            'trend': 'bullish' if histogram > 0 else 'bearish'
        }

    def calculate_bollinger_bands(self, df: pd.DataFrame, window: int = 20) -> Dict:
        """
        ボリンジャーバンド計算

        Returns:
            dict: バンド情報と現在位置
        """
        bb = ta.volatility.BollingerBands(df['Close'], window=window)

        upper_band = bb.bollinger_hband().iloc[-1]
        middle_band = bb.bollinger_mavg().iloc[-1]
        lower_band = bb.bollinger_lband().iloc[-1]
        current_price = df['Close'].iloc[-1]

        # バンド幅
        band_width = upper_band - lower_band
        band_width_ratio = band_width / middle_band

        # 価格の位置（0=下限、1=上限）
        position_in_band = (current_price - lower_band) / band_width if band_width > 0 else 0.5

        # スクイーズ検出（バンドが狭まっている）
        recent_widths = (bb.bollinger_hband() - bb.bollinger_lband()).tail(10)
        is_squeeze = band_width < recent_widths.mean() * 0.8

        return {
            'upper': float(upper_band),
            'middle': float(middle_band),
            'lower': float(lower_band),
            'width': float(band_width),
            'width_ratio': float(band_width_ratio),
            'position': float(position_in_band),
            'is_squeeze': is_squeeze,
            'signal': self._get_bb_signal(position_in_band, is_squeeze)
        }

    def calculate_stochastic(self, df: pd.DataFrame, window: int = 14) -> Dict:
        """
        ストキャスティクス計算

        Returns:
            dict: %K、%D値とシグナル
        """
        stoch = ta.momentum.StochasticOscillator(
            df['High'], df['Low'], df['Close'], window=window
        )

        k_value = stoch.stoch().iloc[-1]
        d_value = stoch.stoch_signal().iloc[-1]

        # オーバーボート/オーバーソールド判定
        if k_value > 80:
            status = 'overbought'
        elif k_value < 20:
            status = 'oversold'
        else:
            status = 'neutral'

        # クロスオーバー検出
        prev_k = stoch.stoch().iloc[-2]
        prev_d = stoch.stoch_signal().iloc[-2]

        crossover = None
        if prev_k < prev_d and k_value > d_value:
            crossover = 'bullish'
        elif prev_k > prev_d and k_value < d_value:
            crossover = 'bearish'

        return {
            'k': float(k_value),
            'd': float(d_value),
            'status': status,
            'crossover': crossover
        }

    def calculate_adx(self, df: pd.DataFrame, window: int = 14) -> Dict:
        """
        ADX（平均方向性指数）計算

        Returns:
            dict: ADX値とトレンド強度
        """
        adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=window)

        adx_value = adx.adx().iloc[-1]
        plus_di = adx.adx_pos().iloc[-1]
        minus_di = adx.adx_neg().iloc[-1]

        # トレンド強度判定
        if adx_value < 25:
            trend_strength = 'weak'
        elif adx_value < 50:
            trend_strength = 'moderate'
        elif adx_value < 75:
            trend_strength = 'strong'
        else:
            trend_strength = 'very_strong'

        # トレンド方向
        trend_direction = 'bullish' if plus_di > minus_di else 'bearish'

        return {
            'value': float(adx_value),
            'plus_di': float(plus_di),
            'minus_di': float(minus_di),
            'trend_strength': trend_strength,
            'trend_direction': trend_direction
        }

    def calculate_obv(self, df: pd.DataFrame) -> Dict:
        """
        OBV（オンバランスボリューム）計算

        Returns:
            dict: OBV値とトレンド
        """
        obv = ta.volume.OnBalanceVolumeIndicator(df['Close'], df['Volume'])
        obv_values = obv.on_balance_volume()

        current_obv = obv_values.iloc[-1]
        obv_sma = obv_values.tail(20).mean()

        # OBVトレンド判定
        obv_trend = 'bullish' if current_obv > obv_sma else 'bearish'

        # 価格との乖離チェック
        price_trend = 'bullish' if df['Close'].iloc[-1] > df['Close'].tail(20).mean() else 'bearish'
        divergence = obv_trend != price_trend

        return {
            'value': float(current_obv),
            'sma': float(obv_sma),
            'trend': obv_trend,
            'divergence': divergence
        }

    def calculate_vwap(self, df: pd.DataFrame) -> Dict:
        """
        VWAP（出来高加重平均価格）計算

        Returns:
            dict: VWAP値と現在価格との関係
        """
        typical_price = (df['High'] + df['Low'] + df['Close']) / 3
        vwap = (typical_price * df['Volume']).cumsum() / df['Volume'].cumsum()

        current_vwap = vwap.iloc[-1]
        current_price = df['Close'].iloc[-1]

        # 価格位置
        deviation = (current_price - current_vwap) / current_vwap

        return {
            'value': float(current_vwap),
            'deviation': float(deviation),
            'signal': 'buy' if deviation < -0.01 else 'sell' if deviation > 0.01 else 'neutral'
        }

    def calculate_atr(self, df: pd.DataFrame, window: int = 14) -> Dict:
        """
        ATR（平均真幅）計算

        Returns:
            dict: ATR値とボラティリティ評価
        """
        atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=window)
        atr_value = atr.average_true_range().iloc[-1]

        # ボラティリティレベル
        atr_percentage = atr_value / df['Close'].iloc[-1]

        if atr_percentage < 0.01:
            volatility = 'very_low'
        elif atr_percentage < 0.02:
            volatility = 'low'
        elif atr_percentage < 0.03:
            volatility = 'medium'
        elif atr_percentage < 0.05:
            volatility = 'high'
        else:
            volatility = 'very_high'

        return {
            'value': float(atr_value),
            'percentage': float(atr_percentage),
            'volatility': volatility
        }

    def calculate_pivot_points(self, df: pd.DataFrame) -> Dict:
        """
        ピボットポイント計算

        Returns:
            dict: ピボット、サポート、レジスタンスレベル
        """
        high = df['High'].iloc[-1]
        low = df['Low'].iloc[-1]
        close = df['Close'].iloc[-1]

        # 標準ピボット
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)

        current_price = df['Close'].iloc[-1]

        # 最も近いレベルを特定
        levels = {
            'r3': r3, 'r2': r2, 'r1': r1,
            'pivot': pivot,
            's1': s1, 's2': s2, 's3': s3
        }

        closest_level = min(levels.items(), key=lambda x: abs(x[1] - current_price))

        return {
            'pivot': float(pivot),
            'resistance': {
                'r1': float(r1),
                'r2': float(r2),
                'r3': float(r3)
            },
            'support': {
                's1': float(s1),
                's2': float(s2),
                's3': float(s3)
            },
            'closest_level': closest_level[0],
            'distance_to_closest': float(current_price - closest_level[1])
        }

    def calculate_fibonacci_levels(self, df: pd.DataFrame, lookback: int = 20) -> Dict:
        """
        フィボナッチリトレースメントレベル計算

        Returns:
            dict: フィボナッチレベル
        """
        recent_high = df['High'].tail(lookback).max()
        recent_low = df['Low'].tail(lookback).min()
        diff = recent_high - recent_low

        levels = {
            '0%': recent_low,
            '23.6%': recent_low + diff * 0.236,
            '38.2%': recent_low + diff * 0.382,
            '50%': recent_low + diff * 0.5,
            '61.8%': recent_low + diff * 0.618,
            '100%': recent_high
        }

        current_price = df['Close'].iloc[-1]

        # 現在価格に最も近いレベル
        closest_level = min(levels.items(), key=lambda x: abs(x[1] - current_price))

        return {
            'levels': {k: float(v) for k, v in levels.items()},
            'current_position': float((current_price - recent_low) / diff) if diff > 0 else 0.5,
            'closest_level': closest_level[0],
            'distance_to_closest': float(current_price - closest_level[1])
        }

    def calculate_volume_profile(self, df: pd.DataFrame) -> Dict:
        """
        ボリュームプロファイル計算

        Returns:
            dict: 価格帯別出来高分析
        """
        # 価格帯を10分割
        price_min = df['Low'].min()
        price_max = df['High'].max()
        price_bins = np.linspace(price_min, price_max, 11)

        volume_profile = {}
        for i in range(len(price_bins) - 1):
            mask = (df['Close'] >= price_bins[i]) & (df['Close'] < price_bins[i + 1])
            volume_profile[f"{price_bins[i]:.0f}-{price_bins[i+1]:.0f}"] = float(df.loc[mask, 'Volume'].sum())

        # POC（Point of Control）- 最大出来高価格帯
        poc_range = max(volume_profile.items(), key=lambda x: x[1])

        # VAH/VAL（Value Area High/Low）- 出来高の70%が集中する価格帯
        total_volume = sum(volume_profile.values())
        sorted_profile = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)

        cumulative_volume = 0
        value_area = []
        for price_range, volume in sorted_profile:
            cumulative_volume += volume
            value_area.append(price_range)
            if cumulative_volume >= total_volume * 0.7:
                break

        return {
            'profile': volume_profile,
            'poc': poc_range[0],
            'value_area': value_area,
            'current_in_value_area': self._is_in_value_area(df['Close'].iloc[-1], value_area)
        }

    def analyze_trend_strength(self, df: pd.DataFrame) -> Dict:
        """
        トレンド強度の総合分析

        Returns:
            dict: トレンド評価
        """
        # 複数の移動平均線
        sma_5 = ta.trend.sma_indicator(df['Close'], 5).iloc[-1]
        sma_10 = ta.trend.sma_indicator(df['Close'], 10).iloc[-1]
        sma_20 = ta.trend.sma_indicator(df['Close'], 20).iloc[-1]
        current_price = df['Close'].iloc[-1]

        # トレンドスコア計算
        trend_score = 0

        # 価格が移動平均線の上にある
        if current_price > sma_5:
            trend_score += 1
        if current_price > sma_10:
            trend_score += 1
        if current_price > sma_20:
            trend_score += 1

        # 移動平均線の並び順
        if sma_5 > sma_10 > sma_20:
            trend_score += 2  # パーフェクトオーダー
        elif sma_5 > sma_10:
            trend_score += 1

        # 連続陽線/陰線カウント
        consecutive_ups = 0
        consecutive_downs = 0
        for i in range(-5, 0):
            if df['Close'].iloc[i] > df['Close'].iloc[i-1]:
                consecutive_ups += 1
                consecutive_downs = 0
            else:
                consecutive_downs += 1
                consecutive_ups = 0

        return {
            'score': trend_score,
            'strength': self._get_trend_strength(trend_score),
            'consecutive_ups': consecutive_ups,
            'consecutive_downs': consecutive_downs,
            'perfect_order': sma_5 > sma_10 > sma_20
        }

    def evaluate_signals(self, indicators: Dict) -> Dict:
        """
        全指標からの統合シグナル評価

        Returns:
            dict: 統合評価結果
        """
        buy_signals = 0
        sell_signals = 0
        neutral_signals = 0

        # RSI
        if indicators.get('rsi', {}).get('signal') == 'buy':
            buy_signals += 2
        elif indicators.get('rsi', {}).get('signal') == 'sell':
            sell_signals += 2

        # MACD
        if indicators.get('macd', {}).get('crossover') == 'bullish':
            buy_signals += 3
        elif indicators.get('macd', {}).get('crossover') == 'bearish':
            sell_signals += 3

        # ボリンジャーバンド
        bb_position = indicators.get('bollinger', {}).get('position', 0.5)
        if bb_position < 0.2:
            buy_signals += 1
        elif bb_position > 0.8:
            sell_signals += 1

        # ストキャスティクス
        if indicators.get('stochastic', {}).get('crossover') == 'bullish':
            buy_signals += 2
        elif indicators.get('stochastic', {}).get('crossover') == 'bearish':
            sell_signals += 2

        # ADX（トレンドの強さ）
        adx = indicators.get('adx', {})
        if adx.get('trend_strength') in ['strong', 'very_strong']:
            if adx.get('trend_direction') == 'bullish':
                buy_signals += 2
            else:
                sell_signals += 2

        # 総合判定
        total_signals = buy_signals + sell_signals + neutral_signals
        if total_signals == 0:
            recommendation = 'hold'
            confidence = 0
        else:
            if buy_signals > sell_signals * 1.5:
                recommendation = 'strong_buy'
                confidence = buy_signals / (buy_signals + sell_signals) if (buy_signals + sell_signals) > 0 else 0
            elif buy_signals > sell_signals:
                recommendation = 'buy'
                confidence = buy_signals / (buy_signals + sell_signals) if (buy_signals + sell_signals) > 0 else 0
            elif sell_signals > buy_signals * 1.5:
                recommendation = 'strong_sell'
                confidence = sell_signals / (buy_signals + sell_signals) if (buy_signals + sell_signals) > 0 else 0
            elif sell_signals > buy_signals:
                recommendation = 'sell'
                confidence = sell_signals / (buy_signals + sell_signals) if (buy_signals + sell_signals) > 0 else 0
            else:
                recommendation = 'hold'
                confidence = 0.5

        return {
            'recommendation': recommendation,
            'confidence': float(confidence),
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'signal_strength': self._get_signal_strength(max(buy_signals, sell_signals))
        }

    def _detect_rsi_divergence(self, df: pd.DataFrame, rsi: pd.Series) -> str:
        """RSIダイバージェンス検出"""
        if len(df) < 10 or len(rsi) < 10:
            return 'none'

        # 直近の高値/安値
        recent_highs = df['High'].tail(10)
        recent_lows = df['Low'].tail(10)
        recent_rsi = rsi.tail(10)

        # 価格が上昇しているがRSIが下降 = ベアリッシュダイバージェンス
        if recent_highs.iloc[-1] > recent_highs.iloc[0] and recent_rsi.iloc[-1] < recent_rsi.iloc[0]:
            return 'bearish_divergence'

        # 価格が下降しているがRSIが上昇 = ブリッシュダイバージェンス
        if recent_lows.iloc[-1] < recent_lows.iloc[0] and recent_rsi.iloc[-1] > recent_rsi.iloc[0]:
            return 'bullish_divergence'

        return 'none'

    def _get_bb_signal(self, position: float, is_squeeze: bool) -> str:
        """ボリンジャーバンドシグナル判定"""
        if is_squeeze:
            return 'prepare_breakout'
        elif position < 0.2:
            return 'oversold'
        elif position > 0.8:
            return 'overbought'
        else:
            return 'neutral'

    def _is_in_value_area(self, price: float, value_area: List[str]) -> bool:
        """価格がバリューエリア内かチェック"""
        for range_str in value_area:
            low, high = map(float, range_str.split('-'))
            if low <= price <= high:
                return True
        return False

    def _get_trend_strength(self, score: int) -> str:
        """トレンド強度評価"""
        if score >= 5:
            return 'very_strong'
        elif score >= 3:
            return 'strong'
        elif score >= 1:
            return 'moderate'
        else:
            return 'weak'

    def _get_signal_strength(self, signal_count: int) -> str:
        """シグナル強度評価"""
        if signal_count >= 7:
            return 'very_strong'
        elif signal_count >= 5:
            return 'strong'
        elif signal_count >= 3:
            return 'moderate'
        else:
            return 'weak'


class NewsAnalyzer:
    """ニュース分析クラス（感情分析強化版）"""

    def __init__(self):
        """初期化"""
        self.positive_keywords = {
            '強い': ['増益', '上方修正', '最高益', '過去最高', '好調', '堅調', '拡大', '成長', '回復', '改善', '黒字転換', '増配'],
            '中程度': ['増収', '計画通り', '順調', '達成', '伸長', '上昇', 'プラス', '堅調', '安定'],
            '弱い': ['微増', '横ばい', '維持', '継続', '予想通り']
        }

        self.negative_keywords = {
            '強い': ['減益', '下方修正', '赤字', '損失', '悪化', '低迷', '不振', '減配', '無配'],
            '中程度': ['減収', '未達', '下落', '減少', 'マイナス', '苦戦', '弱含み'],
            '弱い': ['微減', '伸び悩み', '鈍化', '頭打ち']
        }

        self.sector_keywords = {
            'テクノロジー': ['AI', 'DX', 'クラウド', 'SaaS', '半導体', '5G', 'IoT'],
            'ヘルスケア': ['新薬', '承認', '臨床試験', 'FDA', '治験', 'バイオ'],
            'エネルギー': ['原油', '天然ガス', '再生可能', '脱炭素', 'EV', '電池'],
            '金融': ['金利', '利上げ', '融資', '与信', '資金調達'],
            '消費': ['売上高', '既存店', '客数', '客単価', 'EC']
        }

    def analyze_news_sentiment(self, news_text: str, title: str = None) -> Dict:
        """
        ニュースの感情分析（強化版）

        Args:
            news_text: ニュース本文
            title: ニュースタイトル

        Returns:
            dict: 感情分析結果
        """
        combined_text = f"{title} {news_text}" if title else news_text

        # スコア計算
        positive_score = 0
        negative_score = 0
        detected_keywords = []

        # ポジティブキーワード検出
        for strength, keywords in self.positive_keywords.items():
            for keyword in keywords:
                if keyword in combined_text:
                    weight = 3 if strength == '強い' else 2 if strength == '中程度' else 1
                    positive_score += weight
                    detected_keywords.append(('positive', keyword, strength))

        # ネガティブキーワード検出
        for strength, keywords in self.negative_keywords.items():
            for keyword in keywords:
                if keyword in combined_text:
                    weight = 3 if strength == '強い' else 2 if strength == '中程度' else 1
                    negative_score += weight
                    detected_keywords.append(('negative', keyword, strength))

        # セクター関連キーワード
        detected_sectors = []
        for sector, keywords in self.sector_keywords.items():
            for keyword in keywords:
                if keyword in combined_text:
                    detected_sectors.append(sector)
                    break

        # 数値抽出（パーセンテージ）
        percentage_matches = re.findall(r'([+-]?\d+(?:\.\d+)?)[%％]', combined_text)
        numeric_sentiment = 0
        for match in percentage_matches:
            value = float(match)
            if value > 10:
                numeric_sentiment += 2
            elif value > 0:
                numeric_sentiment += 1
            elif value < -10:
                numeric_sentiment -= 2
            elif value < 0:
                numeric_sentiment -= 1

        # 総合スコア
        total_score = positive_score - negative_score + numeric_sentiment

        # 感情判定
        if total_score >= 5:
            sentiment = 'very_positive'
            confidence = min(0.9, 0.5 + total_score * 0.05)
        elif total_score >= 2:
            sentiment = 'positive'
            confidence = min(0.7, 0.4 + total_score * 0.05)
        elif total_score <= -5:
            sentiment = 'very_negative'
            confidence = min(0.9, 0.5 + abs(total_score) * 0.05)
        elif total_score <= -2:
            sentiment = 'negative'
            confidence = min(0.7, 0.4 + abs(total_score) * 0.05)
        else:
            sentiment = 'neutral'
            confidence = 0.5

        return {
            'sentiment': sentiment,
            'confidence': float(confidence),
            'positive_score': positive_score,
            'negative_score': negative_score,
            'total_score': total_score,
            'detected_keywords': detected_keywords,
            'detected_sectors': list(set(detected_sectors)),
            'numeric_values': percentage_matches
        }

    def categorize_news(self, title: str, content: str = None) -> Dict:
        """
        ニュースのカテゴリ分類

        Returns:
            dict: カテゴリ情報
        """
        combined_text = f"{title} {content}" if content else title

        categories = {
            '決算': ['決算', '四半期', '通期', '業績', '売上高', '営業利益', '純利益'],
            '業績修正': ['修正', '上方修正', '下方修正', '見直し', '変更'],
            'M&A': ['買収', '合併', 'M&A', 'TOB', '統合', '子会社化'],
            '新製品': ['新製品', '新サービス', '発売', 'リリース', '開発', '投入'],
            '提携': ['提携', '協業', '連携', 'パートナーシップ', '共同'],
            '規制': ['規制', '承認', '認可', '法令', 'コンプライアンス'],
            '市況': ['市況', '相場', '為替', '原材料', 'コモディティ'],
            'その他': []
        }

        detected_categories = []
        for category, keywords in categories.items():
            if category == 'その他':
                continue
            for keyword in keywords:
                if keyword in combined_text:
                    detected_categories.append(category)
                    break

        if not detected_categories:
            detected_categories = ['その他']

        # 重要度判定
        importance = 'high' if detected_categories[0] in ['決算', '業績修正', 'M&A'] else 'medium'

        return {
            'primary_category': detected_categories[0],
            'all_categories': detected_categories,
            'importance': importance
        }