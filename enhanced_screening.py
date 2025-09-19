"""
強化版スクリーニング - より多くの銘柄とリアルタイムデータ
"""

import sys
sys.path.append('src')

import pandas as pd
import yfinance as yf
from datetime import datetime
from typing import Dict, List
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from loguru import logger


class EnhancedScreener:
    """強化版スクリーナー"""

    def __init__(self):
        # 東証主要銘柄（大幅拡充）- 150銘柄
        self.universe = [
            # 大型株（日経225主要銘柄）
            '7203.T', '9984.T', '6098.T', '8058.T', '9432.T',
            '6981.T', '4568.T', '8306.T', '6594.T', '7974.T',
            '4063.T', '9983.T', '8035.T', '6857.T', '4519.T',
            '6758.T', '6861.T', '6367.T', '7261.T', '8001.T',

            # 中型株・成長株
            '4755.T', '3382.T', '9434.T', '2914.T', '4751.T',
            '6273.T', '7832.T', '9602.T', '9831.T', '2269.T',
            '4385.T', '3659.T', '4477.T', '2138.T', '4393.T',
            '3900.T', '4490.T', '4053.T', '4776.T', '3696.T',

            # 追加大型株
            '6502.T', '9020.T', '8031.T', '4543.T', '3405.T',
            '4578.T', '6178.T', '7751.T', '4901.T', '3401.T',

            # 金融セクター
            '8316.T', '8411.T', '8308.T', '8354.T', '8628.T',
            '8801.T', '8766.T', '8750.T', '8697.T', '8604.T',

            # 自動車・輸送機器
            '7267.T', '7269.T', '7270.T', '7201.T', '7202.T',
            '7211.T', '7259.T', '7245.T', '9104.T', '9107.T',

            # 電機・精密
            '6701.T', '6702.T', '6752.T', '6753.T', '6754.T',
            '6762.T', '6501.T', '6503.T', '6504.T', '6506.T',

            # 化学・素材
            '4005.T', '4021.T', '4041.T', '4042.T', '4061.T',
            '4188.T', '4183.T', '4208.T', '4272.T', '4901.T',

            # 医薬品・ヘルスケア
            '4502.T', '4503.T', '4506.T', '4507.T', '4523.T',
            '4528.T', '4541.T', '4544.T', '4547.T', '4550.T',

            # 食品・飲料
            '2001.T', '2002.T', '2121.T', '2201.T', '2282.T',
            '2501.T', '2502.T', '2503.T', '2801.T', '2802.T',

            # 小売・サービス
            '8267.T', '8268.T', '3086.T', '3087.T', '3088.T',
            '3099.T', '3101.T', '3103.T', '4680.T', '4681.T',

            # 不動産
            '8801.T', '8802.T', '8830.T', '8850.T', '3289.T',
            '3290.T', '3291.T', '3292.T', '3293.T', '3294.T',

            # エネルギー・資源
            '1605.T', '1662.T', '1721.T', '1801.T', '1802.T',
            '1803.T', '1808.T', '1812.T', '1820.T', '1824.T',

            # 通信・メディア
            '4324.T', '4689.T', '4704.T', '4307.T', '4739.T',
            '9613.T', '9766.T', '9601.T', '9635.T', '9684.T',

            # 新興・グロース
            '2427.T', '3760.T', '4071.T', '4575.T', '6030.T',
            '6619.T', '7779.T', '3624.T', '4293.T', '6079.T',

            # 追加300銘柄（高ボラティリティランキング）
            '8105.T', '6993.T', '6731.T', '6177.T', '5387.T', '5721.T', '4833.T', '7615.T',
            '3803.T', '7138.T', '6574.T', '6973.T', '2315.T', '3905.T', '9610.T', '2134.T',
            '4594.T', '2743.T', '4316.T', '7777.T', '9241.T', '2334.T', '5985.T', '9240.T',
            '3747.T', '8746.T', '7571.T', '3853.T', '7946.T', '8918.T', '3779.T', '2321.T',
            '9213.T', '8783.T', '7746.T', '7603.T', '3664.T', '4586.T', '8995.T', '3070.T',
            '3823.T', '6265.T', '6786.T', '5247.T', '5255.T', '8894.T', '7422.T', '9425.T',
            '6836.T', '7901.T', '6573.T', '3670.T', '7694.T', '6721.T', '7273.T', '3656.T',
            '3997.T', '3077.T', '9155.T', '8798.T', '4784.T', '3913.T', '7347.T', '4935.T',
            '2586.T', '4499.T', '3908.T', '3856.T', '4584.T', '4265.T', '2341.T', '3175.T',
            '5103.T', '5577.T', '3189.T', '5241.T', '7035.T', '2158.T', '3671.T', '7878.T',
            '6029.T', '5618.T', '2700.T', '6634.T', '9350.T', '2721.T', '5597.T', '2330.T',
            '5998.T', '2388.T', '3541.T', '7709.T', '4760.T', '3691.T', '4402.T', '2338.T',
            '2323.T', '7886.T', '3350.T', '4593.T', '3672.T', '6330.T', '4564.T', '7359.T',
            '3845.T', '4395.T', '5856.T', '9330.T', '3985.T', '9271.T', '5287.T', '3686.T',
            '4175.T', '7640.T', '4072.T', '8143.T', '2342.T', '2926.T', '6740.T', '5729.T',
            '6046.T', '4222.T', '7067.T', '6659.T', '3936.T', '5262.T', '6335.T', '3494.T',
            '4263.T', '5246.T', '6022.T', '6620.T', '5028.T', '1491.T', '6444.T', '8013.T',
            '5268.T', '7063.T', '7271.T', '9388.T', '7409.T', '2164.T', '4937.T', '9290.T',
            '7082.T', '9153.T', '9235.T', '9130.T', '6232.T', '3137.T', '9285.T', '4597.T',
            '3692.T', '7046.T', '6016.T', '5075.T', '6840.T', '4319.T', '5131.T', '9135.T',
            '3306.T', '3540.T', '4258.T', '7071.T', '9373.T', '9319.T', '3909.T', '7523.T',
            '9082.T', '9327.T', '6227.T', '5017.T', '9298.T', '4059.T', '4592.T', '6228.T',
            '4393.T', '7018.T', '5884.T', '7357.T', '3810.T', '3778.T', '9253.T', '7014.T',
            '9142.T', '2370.T', '4069.T', '3110.T', '9326.T', '9237.T', '6039.T', '7356.T',
            '3922.T', '6543.T', '6085.T', '7044.T', '6403.T', '4813.T', '4572.T', '5587.T',
            '9423.T', '2122.T', '3935.T', '6176.T', '4839.T', '6224.T', '9553.T', '9340.T',
            '3083.T', '2998.T', '3542.T', '2375.T', '7378.T', '4978.T', '3787.T', '4450.T',
            '9159.T', '6343.T', '4552.T', '5342.T', '6324.T', '7906.T', '7072.T', '9394.T',
            '2667.T', '3353.T', '4591.T', '9337.T', '9219.T', '9215.T', '9428.T', '7250.T',
            '9227.T', '7256.T', '9372.T', '3136.T', '5578.T', '1783.T', '7087.T', '7565.T',
            '6930.T', '7089.T', '3089.T', '3726.T', '9244.T', '9978.T', '7769.T', '5726.T',
            '9205.T', '3446.T', '5595.T', '5034.T', '9262.T', '3791.T', '6648.T', '4369.T',
            '7806.T', '3442.T', '3266.T', '9299.T', '7814.T', '9366.T', '4169.T'
        ]

        # 日本語会社名マッピング
        self.japanese_names = {
            '7203.T': 'トヨタ自動車',
            '9984.T': 'ソフトバンクグループ',
            '6098.T': 'リクルートホールディングス',
            '8058.T': '三菱商事',
            '9432.T': 'NTT',
            '6981.T': '村田製作所',
            '4568.T': '第一三共',
            '8306.T': '三菱UFJフィナンシャル・グループ',
            '6594.T': '日本電産',
            '7974.T': '任天堂',
            '4063.T': '信越化学工業',
            '9983.T': 'ファーストリテイリング',
            '8035.T': '東京エレクトロン',
            '6857.T': 'アドバンテスト',
            '4519.T': '中外製薬',
            '6758.T': 'ソニーグループ',
            '6861.T': 'キーエンス',
            '6367.T': 'ダイキン工業',
            '7261.T': 'マツダ',
            '8001.T': '伊藤忠商事',
            '4755.T': '楽天グループ',
            '3382.T': 'セブン&アイ・ホールディングス',
            '9434.T': 'ソフトバンク',
            '2914.T': '日本たばこ産業',
            '4751.T': 'サイバーエージェント',
            '6273.T': 'SMC',
            '7832.T': 'バンダイナムコホールディングス',
            '9602.T': '東宝',
            '9831.T': 'ヤマダホールディングス',
            '2269.T': '明治ホールディングス',
            '4385.T': 'メルカリ',
            '3659.T': 'ネクソン',
            '4477.T': 'BASE',
            '2138.T': 'クルーズ',
            '4393.T': 'バンク・オブ・イノベーション',
            '3900.T': 'クラウドワークス',
            '4490.T': 'ビザスク',
            '4053.T': 'Sun Asterisk',
            '4776.T': 'サイボウズ',
            '3696.T': 'セレス',
            '6502.T': '東芝',
            '9020.T': 'JR東日本',
            '8031.T': '三井物産',
            '4543.T': 'テルモ',
            '3405.T': 'クラレ',
            '4578.T': '大塚ホールディングス',
            '6178.T': '日本郵政',
            '7751.T': 'キヤノン',
            '4901.T': '富士フイルムホールディングス',
            '3401.T': '帝人'
        }

    def get_stock_info_batch(self, symbols: List[str]) -> Dict:
        """
        複数銘柄の基本情報を一括取得

        Args:
            symbols: 銘柄コードリスト

        Returns:
            Dict: 銘柄情報
        """
        stock_info = {}

        def get_single_stock_info(symbol):
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                return {
                    'symbol': symbol,
                    'stock_code': symbol.replace('.T', ''),
                    'exchange': 'T',
                    'name': self.japanese_names.get(symbol, info.get('longName', symbol.replace('.T', ''))),
                    'market_cap': info.get('marketCap', 0),
                    'sector': info.get('sector', 'Unknown'),
                    'industry': info.get('industry', 'Unknown'),
                    'employees': info.get('fullTimeEmployees', 0),
                    'website': info.get('website', ''),
                    'is_marginable': True  # 東証銘柄は基本的に信用取引可能
                }
            except Exception as e:
                logger.warning(f"Error getting info for {symbol}: {e}")
                return {
                    'symbol': symbol,
                    'stock_code': symbol.replace('.T', ''),
                    'exchange': 'T',
                    'name': self.japanese_names.get(symbol, symbol.replace('.T', '')),
                    'market_cap': 0,
                    'sector': 'Unknown',
                    'is_marginable': True
                }

        # 並行処理で高速化（レート制限対応）
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_symbol = {
                executor.submit(get_single_stock_info, symbol): symbol
                for symbol in symbols
            }

            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    stock_info[symbol] = result
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")

        return stock_info

    def get_market_data_batch(self, symbols: List[str]) -> Dict:
        """
        複数銘柄の価格データを一括取得

        Args:
            symbols: 銘柄コードリスト

        Returns:
            Dict: 価格データ
        """
        price_data = {}

        def get_single_price_data(symbol):
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='10d')  # 10日分

                if hist.empty:
                    return None

                current = hist.iloc[-1]
                previous = hist.iloc[-2] if len(hist) > 1 else current

                # ボラティリティ計算
                returns = hist['Close'].pct_change().dropna()
                volatility = returns.std() if len(returns) > 1 else 0

                return {
                    'symbol': symbol,
                    'current_price': float(current['Close']),
                    'previous_close': float(previous['Close']),
                    'open': float(current['Open']),
                    'high': float(current['High']),
                    'low': float(current['Low']),
                    'volume': int(current['Volume']),
                    'average_volume': float(hist['Volume'].mean()),
                    'gap_ratio': (current['Open'] - previous['Close']) / previous['Close'],
                    'volume_ratio': current['Volume'] / hist['Volume'].mean() if hist['Volume'].mean() > 0 else 1,
                    'volatility': volatility,
                    'price_change': (current['Close'] - previous['Close']) / previous['Close'],
                    'trading_value': float(current['Close'] * current['Volume']),
                    'high_52w': float(hist['High'].max()),
                    'low_52w': float(hist['Low'].min()),
                    'price_data': hist
                }

            except Exception as e:
                logger.warning(f"Error getting price data for {symbol}: {e}")
                return None

        # 並行処理（レート制限対応）
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_symbol = {
                executor.submit(get_single_price_data, symbol): symbol
                for symbol in symbols
            }

            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    if result:
                        price_data[symbol] = result
                except Exception as e:
                    logger.error(f"Error processing price data for {symbol}: {e}")

        return price_data

    def enhanced_screening(self, max_stocks: int = 20) -> Dict:
        """
        強化版スクリーニング実行

        Args:
            max_stocks: 最大処理銘柄数

        Returns:
            Dict: スクリーニング結果
        """
        start_time = datetime.now()
        logger.info(f"Starting enhanced screening for {max_stocks} stocks")

        try:
            # 対象銘柄を制限
            target_symbols = self.universe[:max_stocks]

            # Step 1: 基本情報取得
            logger.info("Getting stock information...")
            stock_info = self.get_stock_info_batch(target_symbols)

            # Step 2: 価格データ取得
            logger.info("Getting market data...")
            price_data = self.get_market_data_batch(target_symbols)

            # Step 3: フィルタリング
            logger.info("Applying filters...")
            filtered_symbols = []

            for symbol in target_symbols:
                if symbol not in price_data or symbol not in stock_info:
                    continue

                price = price_data[symbol]
                info = stock_info[symbol]

                # 基本フィルター（緩和版）
                if price['trading_value'] < 100_000_000:  # 1億円未満は除外
                    continue

                if info['market_cap'] < 5_000_000_000:  # 50億円未満は除外
                    continue

                if abs(price['price_change']) < 0.005:  # 変動率0.5%未満は除外
                    continue

                # 価格フィルター: 10,000円以下のみ
                if price['current_price'] > 10000:
                    continue

                filtered_symbols.append(symbol)

            # Step 4: スコアリング
            logger.info(f"Scoring {len(filtered_symbols)} stocks...")
            results = []

            for symbol in filtered_symbols:
                try:
                    price = price_data[symbol]
                    info = stock_info[symbol]

                    # 高度なスコア計算
                    score = self.calculate_advanced_score(price, info)

                    # シグナル検出
                    signals = self.detect_advanced_signals(price, info)

                    result = {
                        'symbol': symbol,
                        'stock_code': info['stock_code'],
                        'exchange': info['exchange'],
                        'name': info['name'],
                        'total_score': round(score, 1),
                        'current_price': price['current_price'],
                        'gap_ratio': price['gap_ratio'],
                        'volume_ratio': price['volume_ratio'],
                        'trading_value': price['trading_value'],
                        'market_cap': info['market_cap'],
                        'sector': info['sector'],
                        'volatility': price['volatility'],
                        'signals': signals,
                        'price_category': 'under_3000' if price['current_price'] < 3000 else 'range_3000_10000',
                        'rank': 0
                    }

                    results.append(result)

                except Exception as e:
                    logger.warning(f"Error scoring {symbol}: {e}")

            # Step 5: ランキング
            results.sort(key=lambda x: x['total_score'], reverse=True)

            for i, result in enumerate(results):
                result['rank'] = i + 1

            # 価格カテゴリー別に分類
            under_3000 = [r for r in results if r['price_category'] == 'under_3000']
            range_3000_10000 = [r for r in results if r['price_category'] == 'range_3000_10000']

            # カテゴリー別ランキング再設定
            for i, result in enumerate(under_3000):
                result['category_rank'] = i + 1

            for i, result in enumerate(range_3000_10000):
                result['category_rank'] = i + 1

            execution_time = (datetime.now() - start_time).total_seconds()

            screening_result = {
                'timestamp': start_time,
                'screening_type': 'enhanced',
                'execution_time': execution_time,
                'total_processed': len(target_symbols),
                'filtered_count': len(filtered_symbols),
                'scored_count': len(results),
                'under_3000': {
                    'count': len(under_3000),
                    'stocks': under_3000[:15]  # 15銘柄まで表示
                },
                'range_3000_10000': {
                    'count': len(range_3000_10000),
                    'stocks': range_3000_10000[:15]  # 15銘柄まで表示
                },
                'top_picks': results[:10],  # 全体のトップ10
                'watch_list': results[10:25],  # 全体の11-25位
                'statistics': {
                    'avg_score': sum(r['total_score'] for r in results) / len(results) if results else 0,
                    'max_score': max(r['total_score'] for r in results) if results else 0,
                    'min_score': min(r['total_score'] for r in results) if results else 0,
                    'sectors': list(set(r['sector'] for r in results)),
                    'under_3000_count': len(under_3000),
                    'range_3000_10000_count': len(range_3000_10000)
                }
            }

            logger.info(f"Enhanced screening completed in {execution_time:.2f}s: {len(results)} stocks")
            return screening_result

        except Exception as e:
            logger.error(f"Error in enhanced screening: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(),
                'screening_type': 'enhanced'
            }

    def calculate_advanced_score(self, price_data: Dict, info_data: Dict) -> float:
        """
        高度なスコア計算

        Args:
            price_data: 価格データ
            info_data: 基本情報

        Returns:
            float: スコア
        """
        score = 50  # ベーススコア

        # 出来高スコア (30点満点)
        volume_ratio = price_data['volume_ratio']
        if volume_ratio > 3.0:
            score += 30
        elif volume_ratio > 2.0:
            score += 25
        elif volume_ratio > 1.5:
            score += 15
        elif volume_ratio > 1.2:
            score += 5

        # 価格変動スコア (25点満点)
        price_change = abs(price_data['price_change'])
        gap_ratio = price_data['gap_ratio']

        if 0.02 <= gap_ratio <= 0.05:  # 2-5%のギャップアップ
            score += 20
        elif 0.05 < gap_ratio <= 0.08:  # 5-8%
            score += 10
        elif gap_ratio > 0.08:  # 8%超は減点
            score -= 5

        # 値上がり率
        if price_change > 0.03:
            score += 15
        elif price_change > 0.02:
            score += 10

        # 流動性スコア (15点満点)
        trading_value = price_data['trading_value']
        if trading_value > 10_000_000_000:  # 100億円超
            score += 15
        elif trading_value > 5_000_000_000:  # 50億円超
            score += 10
        elif trading_value > 1_000_000_000:  # 10億円超
            score += 5

        # セクタープレミアム (10点満点)
        hot_sectors = ['Technology', 'Healthcare', 'Consumer Cyclical']
        if info_data['sector'] in hot_sectors:
            score += 10

        # 時価総額による調整
        market_cap = info_data['market_cap']
        if 100_000_000_000 <= market_cap <= 1_000_000_000_000:  # 1000億-1兆円
            score += 5
        elif market_cap > 1_000_000_000_000:  # 1兆円超は安定株
            score += 3

        return max(0, min(100, score))

    def detect_advanced_signals(self, price_data: Dict, info_data: Dict) -> List[str]:
        """
        高度なシグナル検出

        Args:
            price_data: 価格データ
            info_data: 基本情報

        Returns:
            List[str]: シグナルリスト
        """
        signals = []

        # 出来高シグナル
        volume_ratio = price_data['volume_ratio']
        if volume_ratio > 3.0:
            signals.append(f"大量出来高({volume_ratio:.1f}倍)")
        elif volume_ratio > 2.0:
            signals.append(f"出来高急増({volume_ratio:.1f}倍)")

        # 価格シグナル
        gap_ratio = price_data['gap_ratio']
        price_change = price_data['price_change']

        if gap_ratio > 0.03:
            signals.append(f"ギャップアップ({gap_ratio:.1%})")

        if price_change > 0.05:
            signals.append(f"急騰({price_change:.1%})")

        # 流動性シグナル
        trading_value = price_data['trading_value']
        if trading_value > 10_000_000_000:
            signals.append("高流動性")

        # ボラティリティシグナル
        volatility = price_data['volatility']
        if volatility > 0.03:
            signals.append("高ボラティリティ")

        # 52週高値接近
        current_price = price_data['current_price']
        high_52w = price_data['high_52w']
        if current_price / high_52w > 0.95:
            signals.append("52週高値圏")

        # セクターモメンタム
        if info_data['sector'] in ['Technology', 'Healthcare']:
            signals.append(f"{info_data['sector']}注目")

        return signals


def run_enhanced_screening(max_stocks: int = 30):
    """強化版スクリーニング実行"""
    screener = EnhancedScreener()
    return screener.enhanced_screening(max_stocks)


if __name__ == "__main__":
    result = run_enhanced_screening(10)

    if 'error' in result:
        print(f"エラー: {result['error']}")
    else:
        print("=" * 60)
        print("強化版スクリーニング結果")
        print("=" * 60)
        print(f"実行時間: {result['execution_time']:.2f}秒")
        print(f"処理銘柄: {result['total_processed']} → {result['scored_count']}")
        print(f"セクター: {', '.join(result['statistics']['sectors'][:5])}")
        print()

        print("【推奨銘柄 TOP5】")
        for stock in result['top_picks']:
            print(f"{stock['rank']}位: {stock['symbol']} - {stock['name']}")
            print(f"  スコア: {stock['total_score']}/100")
            print(f"  現在値: {stock['current_price']:,.0f}円")
            print(f"  セクター: {stock['sector']}")
            print(f"  売買代金: {stock['trading_value']/100_000_000:.0f}億円")
            if stock['signals']:
                print(f"  シグナル: {', '.join(stock['signals'])}")
            print()