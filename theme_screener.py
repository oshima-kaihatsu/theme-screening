"""
テーマ関連銘柄連動手法スクリーニングシステム
Theme-Based Stock Movement Screening System

主要機能:
1. 値上がり率ランキングによる急騰銘柄検出
2. ニュース材料の自動収集と分析
3. テーマ銘柄のグルーピングと序列判定
4. リアルタイム監視とアラート
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import feedparser
import json
import time
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import re
from loguru import logger
import asyncio
import aiohttp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
import warnings
warnings.filterwarnings('ignore')

class ThemeScreener:
    """テーマ関連銘柄スクリーニングクラス"""

    def __init__(self):
        self.setup_logging()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 全市場の主要銘柄リスト（東証全銘柄から主要なものを抽出）
        self.load_stock_universe()

        # テーマキーワード辞書
        self.theme_keywords = {
            'AI・人工知能': ['AI', '人工知能', '機械学習', 'ChatGPT', 'ディープラーニング', '生成AI'],
            '半導体': ['半導体', 'チップ', 'TSMC', 'エヌビディア', 'ファウンドリ'],
            'EV・電気自動車': ['EV', '電気自動車', 'テスラ', 'バッテリー', '充電'],
            '再生エネルギー': ['太陽光', '風力', '再生可能エネルギー', '脱炭素', 'カーボンニュートラル'],
            'メタバース': ['メタバース', 'VR', 'AR', '仮想空間', 'NFT'],
            '量子コンピュータ': ['量子コンピュータ', '量子計算', 'キュービット'],
            'バイオ・創薬': ['創薬', 'バイオ', '治験', 'FDA', '承認', 'ワクチン'],
            '５G・通信': ['5G', '6G', '基地局', '通信インフラ'],
            '宇宙': ['宇宙', 'ロケット', '衛星', 'JAXA', 'NASA'],
            'ロボット': ['ロボット', '自動化', 'FA', '協働ロボット'],
            '防衛': ['防衛', '防衛費', '安全保障', '自衛隊'],
            'インバウンド': ['インバウンド', '訪日客', '観光', 'ホテル', '免税'],
            '円安': ['円安', 'ドル高', '為替', '輸出'],
            '金利': ['金利', '利上げ', '日銀', 'FRB', '金融政策']
        }

    def setup_logging(self):
        """ロギング設定"""
        logger.add(
            "data/logs/theme_screener_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
        )

    def load_stock_universe(self):
        """全銘柄リストの読み込み"""
        # enhanced_screening.pyから銘柄リストを読み込み
        try:
            from enhanced_screening import EnhancedScreener
            screener = EnhancedScreener()
            self.stock_universe = screener.universe
            logger.info(f"Loaded {len(self.stock_universe)} stocks from universe")
        except Exception as e:
            logger.error(f"Failed to load stock universe: {e}")
            # フォールバック用の最小限のリスト
            self.stock_universe = ['7203.T', '9984.T', '6098.T']

    def get_top_gainers(self, min_change_pct: float = 10.0, limit: int = 100) -> pd.DataFrame:
        """
        値上がり率ランキング取得

        Args:
            min_change_pct: 最小上昇率（%）
            limit: 取得上限数

        Returns:
            値上がり銘柄のDataFrame
        """
        logger.info(f"Fetching top gainers (min change: {min_change_pct}%)")

        gainers = []
        batch_size = 50

        for i in range(0, len(self.stock_universe), batch_size):
            batch = self.stock_universe[i:i+batch_size]
            symbols_str = ' '.join(batch)

            try:
                tickers = yf.Tickers(symbols_str)

                for symbol in batch:
                    try:
                        ticker = tickers.tickers[symbol]
                        info = ticker.info
                        history = ticker.history(period='2d')

                        if len(history) < 2:
                            continue

                        prev_close = history['Close'][-2]
                        current = history['Close'][-1]
                        volume = history['Volume'][-1]

                        change_pct = ((current - prev_close) / prev_close) * 100

                        if change_pct >= min_change_pct:
                            gainers.append({
                                'symbol': symbol,
                                'name': info.get('longName', symbol),
                                'current_price': float(current),
                                'prev_close': float(prev_close),
                                'change_pct': float(change_pct),
                                'volume': int(volume),
                                'volume_ratio': float(volume / info.get('averageVolume', volume) if info.get('averageVolume', 0) > 0 else 1),
                                'market_cap': int(info.get('marketCap', 0)),
                                'limit_up': bool(change_pct >= 23.0),  # ストップ高判定（簡易）
                                'sector': info.get('sector', 'Unknown')
                            })

                    except Exception as e:
                        logger.debug(f"Error fetching {symbol}: {e}")
                        continue

                # レート制限対策
                time.sleep(1)

            except Exception as e:
                logger.error(f"Batch error: {e}")
                continue

        df = pd.DataFrame(gainers)
        if not df.empty:
            df = df.sort_values('change_pct', ascending=False).head(limit)
            logger.info(f"Found {len(df)} gainers above {min_change_pct}%")

        return df

    def fetch_news_for_symbol(self, symbol: str) -> List[Dict]:
        """
        個別銘柄のニュース取得

        Args:
            symbol: 銘柄コード

        Returns:
            ニュースリスト
        """
        news_items = []

        # Yahoo Finance API
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news

            for item in news[:10]:  # 最新10件
                news_items.append({
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'publisher': item.get('publisher', ''),
                    'timestamp': datetime.fromtimestamp(item.get('providerPublishTime', 0)),
                    'source': 'yahoo'
                })
        except Exception as e:
            logger.debug(f"Yahoo news error for {symbol}: {e}")

        # 株探のニュース取得
        try:
            code = symbol.split('.')[0]
            kabutan_url = f"https://kabutan.jp/stock/news?code={code}"
            response = self.session.get(kabutan_url, timeout=5)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                news_list = soup.find_all('div', class_='news_ttl')[:5]

                for news in news_list:
                    title_elem = news.find('a')
                    if title_elem:
                        news_items.append({
                            'title': title_elem.text.strip(),
                            'link': f"https://kabutan.jp{title_elem.get('href', '')}",
                            'publisher': '株探',
                            'timestamp': datetime.now(),
                            'source': 'kabutan'
                        })

        except Exception as e:
            logger.debug(f"Kabutan news error for {symbol}: {e}")

        return news_items

    def identify_themes(self, gainers_df: pd.DataFrame) -> Dict[str, List[str]]:
        """
        テーマ識別とグルーピング

        Args:
            gainers_df: 値上がり銘柄DataFrame

        Returns:
            テーマごとの銘柄リスト
        """
        logger.info("Identifying themes from news and clustering")

        # 各銘柄のニュース取得とテキスト結合
        symbol_texts = {}
        symbol_news = {}

        for _, row in gainers_df.iterrows():
            symbol = row['symbol']
            news_items = self.fetch_news_for_symbol(symbol)

            # ニュースタイトルを結合
            text = ' '.join([item['title'] for item in news_items])
            symbol_texts[symbol] = text
            symbol_news[symbol] = news_items

            time.sleep(0.5)  # レート制限対策

        # テーマキーワードマッチング
        theme_stocks = defaultdict(list)

        for symbol, text in symbol_texts.items():
            for theme, keywords in self.theme_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in text.lower():
                        theme_stocks[theme].append(symbol)
                        break

        # テキストクラスタリング（類似ニュースの銘柄をグループ化）
        if len(symbol_texts) >= 3:
            try:
                vectorizer = TfidfVectorizer(max_features=50)
                texts = list(symbol_texts.values())
                symbols = list(symbol_texts.keys())

                if texts and all(texts):  # 空でないテキストがある場合のみ
                    X = vectorizer.fit_transform(texts)

                    # DBSCAN clustering
                    clustering = DBSCAN(eps=0.3, min_samples=2, metric='cosine')
                    labels = clustering.fit_predict(X)

                    # クラスタごとにグループ化
                    for i, label in enumerate(labels):
                        if label != -1:  # ノイズでないクラスタ
                            cluster_theme = f"クラスタ_{label}"
                            if cluster_theme not in theme_stocks:
                                theme_stocks[cluster_theme] = []
                            theme_stocks[cluster_theme].append(symbols[i])

            except Exception as e:
                logger.error(f"Clustering error: {e}")

        # 銘柄ニュース情報を保存
        self.symbol_news = symbol_news

        return dict(theme_stocks)

    def identify_leader_follower(self, theme_stocks: Dict[str, List[str]],
                                gainers_df: pd.DataFrame) -> Dict[str, Dict]:
        """
        リーダー・フォロワー銘柄の識別

        Args:
            theme_stocks: テーマごとの銘柄リスト
            gainers_df: 値上がり銘柄DataFrame

        Returns:
            テーマごとの序列情報
        """
        logger.info("Identifying leader and follower stocks")

        theme_hierarchy = {}

        for theme, symbols in theme_stocks.items():
            if len(symbols) < 2:
                continue

            # テーマ内の銘柄情報取得
            theme_df = gainers_df[gainers_df['symbol'].isin(symbols)].copy()

            if theme_df.empty:
                continue

            # スコアリング（複合指標）
            theme_df['leader_score'] = (
                theme_df['change_pct'] * 0.3 +  # 上昇率
                theme_df['volume_ratio'] * 0.3 +  # 出来高比率
                (1 / np.log10(theme_df['market_cap'] + 1)) * 0.2 +  # 時価総額（小さい方が高スコア）
                theme_df['limit_up'].astype(int) * 0.2  # ストップ高ボーナス
            )

            # ソートして序列決定
            theme_df = theme_df.sort_values('leader_score', ascending=False)

            hierarchy = {
                'theme': theme,
                'stocks': [],
                'total_count': len(symbols)
            }

            for rank, (_, row) in enumerate(theme_df.iterrows(), 1):
                stock_info = {
                    'rank': int(rank),
                    'symbol': row['symbol'],
                    'name': row['name'],
                    'change_pct': float(row['change_pct']),
                    'volume_ratio': float(row['volume_ratio']),
                    'market_cap': int(row['market_cap']),
                    'role': 'リーダー' if rank == 1 else f'{rank}番手',
                    'score': float(row['leader_score'])
                }

                hierarchy['stocks'].append(stock_info)

            theme_hierarchy[theme] = hierarchy

        return theme_hierarchy

    def generate_report(self, gainers_df: pd.DataFrame,
                       theme_stocks: Dict[str, List[str]],
                       theme_hierarchy: Dict[str, Dict]) -> Dict:
        """
        スクリーニングレポート生成

        Returns:
            レポート辞書
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_gainers': int(len(gainers_df)),
                'themes_detected': int(len(theme_stocks)),
                'top_themes': [],
                'limit_up_count': int(gainers_df['limit_up'].sum() if not gainers_df.empty else 0)
            },
            'top_gainers': [],
            'themes': [],
            'watchlist': []
        }

        # トップゲイナー
        if not gainers_df.empty:
            for _, row in gainers_df.head(10).iterrows():
                report['top_gainers'].append({
                    'symbol': str(row['symbol']),
                    'name': str(row['name']),
                    'change_pct': float(round(row['change_pct'], 2)),
                    'volume_ratio': float(round(row['volume_ratio'], 2)),
                    'limit_up': bool(row['limit_up'])
                })

        # テーマ詳細
        for theme_name, hierarchy in theme_hierarchy.items():
            theme_info = {
                'name': str(theme_name),
                'stock_count': int(hierarchy['total_count']),
                'stocks': []
            }

            for stock in hierarchy['stocks']:
                stock_data = {
                    'rank': int(stock['rank']),
                    'symbol': str(stock['symbol']),
                    'name': str(stock['name']),
                    'role': str(stock['role']),
                    'change_pct': float(round(stock['change_pct'], 2)),
                    'news': []
                }

                # ニュース追加
                if stock['symbol'] in self.symbol_news:
                    for news in self.symbol_news[stock['symbol']][:3]:
                        stock_data['news'].append({
                            'title': news['title'],
                            'source': news['source']
                        })

                theme_info['stocks'].append(stock_data)

            report['themes'].append(theme_info)

        # 監視リスト（各テーマのトップ2銘柄）
        for hierarchy in theme_hierarchy.values():
            for stock in hierarchy['stocks'][:2]:
                report['watchlist'].append({
                    'theme': str(hierarchy['theme']),
                    'symbol': str(stock['symbol']),
                    'name': str(stock['name']),
                    'role': str(stock['role']),
                    'change_pct': float(round(stock['change_pct'], 2))
                })

        # サマリー更新
        if theme_hierarchy:
            top_themes = sorted(theme_hierarchy.items(),
                              key=lambda x: len(x[1]['stocks']),
                              reverse=True)[:3]
            report['summary']['top_themes'] = [t[0] for t in top_themes]

        return report

    def run_screening(self, min_change_pct: float = 10.0) -> Dict:
        """
        スクリーニング実行

        Args:
            min_change_pct: 最小上昇率

        Returns:
            スクリーニング結果
        """
        logger.info(f"Starting theme screening (min change: {min_change_pct}%)")

        # 1. 値上がり率ランキング取得
        gainers_df = self.get_top_gainers(min_change_pct=min_change_pct)

        if gainers_df.empty:
            logger.warning("No gainers found")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': 'No gainers found',
                'summary': {'total_gainers': 0}
            }

        # 2. テーマ識別
        theme_stocks = self.identify_themes(gainers_df)

        # 3. リーダー・フォロワー識別
        theme_hierarchy = self.identify_leader_follower(theme_stocks, gainers_df)

        # 4. レポート生成
        report = self.generate_report(gainers_df, theme_stocks, theme_hierarchy)

        # 5. 保存
        self.save_report(report)

        logger.info(f"Screening completed: {len(gainers_df)} gainers, {len(theme_stocks)} themes")

        return report

    def save_report(self, report: Dict):
        """レポート保存"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"data/reports/theme_report_{timestamp}.json"

        try:
            import os
            os.makedirs('data/reports', exist_ok=True)

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            logger.info(f"Report saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")


def main():
    """メイン実行"""
    screener = ThemeScreener()

    # スクリーニング実行
    report = screener.run_screening(min_change_pct=10.0)

    # 結果表示
    print("\n" + "="*60)
    print("テーマ関連銘柄スクリーニング結果")
    print("="*60)

    print(f"\n実行時刻: {report['timestamp']}")
    print(f"急騰銘柄数: {report['summary']['total_gainers']}")
    print(f"検出テーマ数: {report['summary']['themes_detected']}")
    print(f"ストップ高: {report['summary']['limit_up_count']}銘柄")

    if report['summary']['top_themes']:
        print(f"\n【主要テーマ】")
        for theme in report['summary']['top_themes']:
            print(f"  - {theme}")

    print(f"\n【値上がり率TOP5】")
    for i, stock in enumerate(report.get('top_gainers', [])[:5], 1):
        limit = "★ST高★" if stock['limit_up'] else ""
        print(f"  {i}. [{stock['symbol']}] {stock['name']} "
              f"+{stock['change_pct']}% {limit}")

    print(f"\n【テーマ別リーダー銘柄】")
    for theme in report.get('themes', []):
        if theme['stocks']:
            leader = theme['stocks'][0]
            print(f"\n  ◆ {theme['name']} ({theme['stock_count']}銘柄)")
            print(f"    リーダー: [{leader['symbol']}] {leader['name']} "
                  f"+{leader['change_pct']}%")

            if len(theme['stocks']) > 1:
                second = theme['stocks'][1]
                print(f"    2番手: [{second['symbol']}] {second['name']} "
                      f"+{second['change_pct']}%")

    print(f"\n【監視リスト】")
    for item in report.get('watchlist', [])[:10]:
        print(f"  [{item['symbol']}] {item['name']} ({item['theme']}) "
              f"役割:{item['role']} +{item['change_pct']}%")


if __name__ == '__main__':
    main()