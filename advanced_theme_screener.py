"""
高度なテーマ関連銘柄連動手法スクリーニングシステム
Advanced Theme-Based Stock Movement Analysis System

真のテーマ連動分析：
1. セクター別連動分析
2. 材料ニュースによるテーマ抽出
3. 出来高急増での関連銘柄発見
4. 価格動向相関によるリーダー・フォロワー識別
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
from scipy.stats import pearsonr
from sklearn.cluster import DBSCAN
import warnings
warnings.filterwarnings('ignore')

class AdvancedThemeScreener:
    """高度なテーマ関連銘柄スクリーニングクラス"""

    def __init__(self):
        self.setup_logging()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 主要銘柄リスト（セクター別に整理）
        self.sector_stocks = {
            'AI・半導体': {
                'leaders': ['6501.T', '6861.T', '6981.T', '6762.T', '6753.T'],  # 日立、キーエンス、村田、TDK、シャープ
                'followers': ['6902.T', '6925.T', '6929.T', '6954.T', '6963.T']  # デンソー、ウシオ電機、日本セラミック、ファナック、ローム
            },
            'EV・自動車': {
                'leaders': ['7203.T', '7267.T', '7201.T', '7261.T'],  # トヨタ、ホンダ、日産、マツダ
                'followers': ['7211.T', '7269.T', '7270.T', '7259.T', '7245.T']  # 三菱自動車、スズキ、SUBARU、アイシン、大同メタル
            },
            'バイオ・医薬': {
                'leaders': ['4568.T', '4519.T', '4503.T', '4502.T'],  # 第一三共、中外製薬、アステラス、武田薬品
                'followers': ['4507.T', '4523.T', '4578.T', '4544.T', '4547.T']  # 塩野義、エーザイ、大塚HD、みらかHD、キッセイ薬品
            },
            '金融・フィンテック': {
                'leaders': ['8306.T', '8316.T', '8411.T', '8354.T'],  # 三菱UFJ、三井住友FG、みずほFG、ふくおかFG
                'followers': ['8628.T', '8750.T', '8697.T', '8604.T', '8766.T']  # 松井証券、第一生命、日本取引所、野村HD、東京海上
            },
            '不動産・REIT': {
                'leaders': ['8801.T', '8802.T', '8830.T'],  # 三井不動産、三菱地所、住友不動産
                'followers': ['3289.T', '3290.T', '3293.T', '3294.T', '8850.T']  # 東急不動産、アズビル、イー・ギャランティ、アジア開発、スターツ
            },
            'エネルギー・資源': {
                'leaders': ['1605.T', '1662.T', '5020.T', '5019.T'],  # INPEX、石油資源開発、ENEOS、出光興産
                'followers': ['1721.T', '1801.T', '1803.T', '1808.T', '1812.T']  # コスモエネルギー、大成建設、清水建設、長谷川工務店、鹿島建設
            },
            '通信・IT': {
                'leaders': ['9984.T', '9432.T', '4755.T', '4751.T'],  # ソフトバンクG、NTT、楽天G、サイバーエージェント
                'followers': ['4324.T', '4689.T', '4704.T', '9613.T', '4385.T']  # 電通G、ヤフー、トレンドマイクロ、NTTデータ、メルカリ
            },
            '小売・消費': {
                'leaders': ['9983.T', '3382.T', '8267.T', '7974.T'],  # ファーストリテイリング、セブン＆アイ、イオン、任天堂
                'followers': ['8268.T', '3086.T', '3099.T', '2914.T', '2801.T']  # 西友、J.フロント、三越伊勢丹、JT、キッコーマン
            }
        }

        # テーマキーワード強化版
        self.enhanced_theme_keywords = {
            'AI・人工知能': {
                'primary': ['AI', '人工知能', 'ChatGPT', '生成AI', '機械学習', 'ディープラーニング'],
                'secondary': ['自動運転', 'ロボット', 'IoT', 'ビッグデータ', 'クラウド']
            },
            '半導体': {
                'primary': ['半導体', 'チップ', 'TSMC', 'エヌビディア', 'ファウンドリ', 'メモリ'],
                'secondary': ['電子部品', '回路', 'プロセッサ', 'GPU', 'CPU']
            },
            'EV・電気自動車': {
                'primary': ['EV', '電気自動車', 'テスラ', 'バッテリー', '充電'],
                'secondary': ['モーター', 'リチウム', '蓄電池', '自動運転', 'モビリティ']
            },
            '量子・先端技術': {
                'primary': ['量子コンピュータ', '量子', 'キュービット', '量子計算'],
                'secondary': ['スーパーコンピュータ', '先端技術', '量子通信']
            },
            '防衛・安全保障': {
                'primary': ['防衛', '防衛費', '安全保障', '自衛隊', '軍事'],
                'secondary': ['宇宙', 'サイバーセキュリティ', 'ドローン', 'レーダー']
            },
            'バイオ・創薬': {
                'primary': ['創薬', 'バイオ', '治験', 'FDA', '承認', 'ワクチン'],
                'secondary': ['医療', '薬事', '臨床', '新薬', 'がん治療']
            },
            'インバウンド・観光': {
                'primary': ['インバウンド', '訪日客', '観光', 'ホテル', '免税'],
                'secondary': ['旅行', '航空', '空港', '鉄道', 'カジノ']
            },
            '金融・フィンテック': {
                'primary': ['フィンテック', 'デジタル通貨', 'ブロックチェーン', 'キャッシュレス'],
                'secondary': ['決済', '暗号資産', 'DX', 'ネット銀行', '保険テック']
            }
        }

    def setup_logging(self):
        """ロギング設定"""
        logger.add(
            "data/logs/advanced_theme_screener_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
        )

    def get_sector_gainers(self, min_change_pct: float = 5.0) -> Dict[str, List]:
        """
        セクター別値上がり銘柄取得

        Args:
            min_change_pct: 最小上昇率

        Returns:
            セクター別銘柄辞書
        """
        logger.info(f"Analyzing sector-based gainers (min change: {min_change_pct}%)")

        sector_gainers = {}

        for sector, stocks in self.sector_stocks.items():
            all_sector_stocks = stocks['leaders'] + stocks['followers']
            sector_results = []

            for symbol in all_sector_stocks:
                try:
                    ticker = yf.Ticker(symbol)
                    history = ticker.history(period='5d')

                    if len(history) < 2:
                        continue

                    # 最新2日の価格比較
                    current = history['Close'][-1]
                    prev_close = history['Close'][-2]
                    volume = history['Volume'][-1]
                    avg_volume = history['Volume'].mean()

                    change_pct = ((current - prev_close) / prev_close) * 100

                    if change_pct >= min_change_pct:
                        sector_results.append({
                            'symbol': symbol,
                            'change_pct': float(change_pct),
                            'current_price': float(current),
                            'volume': int(volume),
                            'volume_ratio': float(volume / avg_volume if avg_volume > 0 else 1),
                            'is_leader': symbol in stocks['leaders'],
                            'market_cap': self.get_market_cap(symbol)
                        })

                    time.sleep(0.1)  # レート制限対策

                except Exception as e:
                    logger.debug(f"Error processing {symbol}: {e}")
                    continue

            if sector_results:
                # セクター内でソート
                sector_results.sort(key=lambda x: x['change_pct'], reverse=True)
                sector_gainers[sector] = sector_results

        return sector_gainers

    def get_market_cap(self, symbol: str) -> int:
        """時価総額取得"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return int(info.get('marketCap', 0))
        except:
            return 0

    def fetch_comprehensive_news(self, symbols: List[str]) -> Dict[str, List]:
        """
        包括的ニュース取得

        Args:
            symbols: 銘柄コードリスト

        Returns:
            銘柄別ニュース辞書
        """
        logger.info(f"Fetching comprehensive news for {len(symbols)} symbols")

        all_news = {}

        for symbol in symbols:
            news_items = []

            try:
                # Yahoo Finance ニュース
                ticker = yf.Ticker(symbol)
                yahoo_news = ticker.news

                for item in yahoo_news[:5]:
                    news_items.append({
                        'title': item.get('title', ''),
                        'link': item.get('link', ''),
                        'publisher': item.get('publisher', ''),
                        'timestamp': datetime.fromtimestamp(item.get('providerPublishTime', 0)),
                        'source': 'yahoo'
                    })

                # 株探ニュース
                code = symbol.split('.')[0]
                kabutan_url = f"https://kabutan.jp/stock/news?code={code}"

                response = self.session.get(kabutan_url, timeout=5)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    news_elements = soup.find_all('div', class_='news_ttl')[:3]

                    for news in news_elements:
                        title_elem = news.find('a')
                        if title_elem:
                            news_items.append({
                                'title': title_elem.text.strip(),
                                'link': f"https://kabutan.jp{title_elem.get('href', '')}",
                                'publisher': '株探',
                                'timestamp': datetime.now(),
                                'source': 'kabutan'
                            })

                all_news[symbol] = news_items
                time.sleep(0.5)  # レート制限対策

            except Exception as e:
                logger.debug(f"News fetch error for {symbol}: {e}")
                all_news[symbol] = []

        return all_news

    def analyze_theme_correlation(self, sector_gainers: Dict) -> Dict:
        """
        テーマ相関分析

        Args:
            sector_gainers: セクター別上昇銘柄

        Returns:
            テーマ相関結果
        """
        logger.info("Analyzing theme correlations")

        theme_analysis = {}

        for sector, stocks in sector_gainers.items():
            if len(stocks) < 2:
                continue

            # セクター内での銘柄分析
            leaders = [s for s in stocks if s['is_leader']]
            followers = [s for s in stocks if not s['is_leader']]

            if leaders and followers:
                # リーダー・フォロワー関係の分析
                leader_avg_change = np.mean([s['change_pct'] for s in leaders])
                follower_avg_change = np.mean([s['change_pct'] for s in followers])

                # 出来高比率の分析
                leader_avg_volume = np.mean([s['volume_ratio'] for s in leaders])
                follower_avg_volume = np.mean([s['volume_ratio'] for s in followers])

                theme_analysis[sector] = {
                    'sector': sector,
                    'total_stocks': len(stocks),
                    'leader_count': len(leaders),
                    'follower_count': len(followers),
                    'leader_avg_change': float(leader_avg_change),
                    'follower_avg_change': float(follower_avg_change),
                    'volume_leadership': leader_avg_volume > follower_avg_volume,
                    'price_leadership': leader_avg_change > follower_avg_change,
                    'correlation_strength': self.calculate_sector_correlation(stocks),
                    'theme_strength': len(stocks) / (len(leaders) + len(followers)) * 100,
                    'leaders': leaders,
                    'followers': followers
                }

        return theme_analysis

    def calculate_sector_correlation(self, stocks: List[Dict]) -> float:
        """セクター内相関計算"""
        if len(stocks) < 2:
            return 0.0

        # 価格変動率の相関を簡易計算
        changes = [s['change_pct'] for s in stocks]
        volumes = [s['volume_ratio'] for s in stocks]

        try:
            correlation, _ = pearsonr(changes, volumes)
            return float(abs(correlation)) if not np.isnan(correlation) else 0.0
        except:
            return 0.0

    def identify_theme_leaders(self, theme_analysis: Dict) -> Dict:
        """
        テーマリーダー識別

        Args:
            theme_analysis: テーマ分析結果

        Returns:
            リーダー銘柄情報
        """
        logger.info("Identifying theme leaders and followers")

        ranked_themes = {}

        for sector, analysis in theme_analysis.items():
            if analysis['total_stocks'] < 2:
                continue

            # 全銘柄をリーダーシップスコアでランキング
            all_stocks = analysis['leaders'] + analysis['followers']

            for stock in all_stocks:
                # リーダーシップスコア算出
                stock['leadership_score'] = (
                    stock['change_pct'] * 0.4 +          # 上昇率 40%
                    stock['volume_ratio'] * 30 +         # 出来高比率 30%
                    (100 if stock['is_leader'] else 50) * 0.2 +  # セクター地位 20%
                    (1 / np.log10(stock['market_cap'] + 1)) * 10  # 時価総額逆数 10%
                )

            # スコア順にソート
            all_stocks.sort(key=lambda x: x['leadership_score'], reverse=True)

            # ランキング付与
            for i, stock in enumerate(all_stocks, 1):
                stock['rank'] = i
                stock['role'] = 'テーマリーダー' if i == 1 else f'{i}番手フォロワー'

            ranked_themes[sector] = {
                'theme_name': sector,
                'strength_score': analysis['correlation_strength'] * analysis['theme_strength'],
                'stock_count': len(all_stocks),
                'price_momentum': analysis['leader_avg_change'],
                'volume_surge': any(s['volume_ratio'] > 2.0 for s in all_stocks),
                'stocks': all_stocks
            }

        return ranked_themes

    def generate_advanced_report(self, ranked_themes: Dict, all_news: Dict) -> Dict:
        """
        高度レポート生成

        Args:
            ranked_themes: ランク付けテーマ
            all_news: ニュース情報

        Returns:
            詳細レポート
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'analysis_type': 'テーマ関連銘柄連動分析',
            'summary': {
                'detected_themes': len(ranked_themes),
                'total_gainers': sum(t['stock_count'] for t in ranked_themes.values()),
                'strong_themes': len([t for t in ranked_themes.values() if t['strength_score'] > 50]),
                'volume_surge_themes': len([t for t in ranked_themes.values() if t['volume_surge']])
            },
            'theme_rankings': [],
            'investment_signals': [],
            'watchlist': []
        }

        # テーマランキング
        sorted_themes = sorted(ranked_themes.items(),
                             key=lambda x: x[1]['strength_score'], reverse=True)

        for rank, (theme_name, theme_data) in enumerate(sorted_themes, 1):
            leader_stock = theme_data['stocks'][0] if theme_data['stocks'] else None

            theme_info = {
                'rank': rank,
                'theme_name': theme_name,
                'strength_score': round(theme_data['strength_score'], 2),
                'stock_count': theme_data['stock_count'],
                'price_momentum': round(theme_data['price_momentum'], 2),
                'volume_surge': theme_data['volume_surge'],
                'leader_stock': {
                    'symbol': leader_stock['symbol'],
                    'change_pct': round(leader_stock['change_pct'], 2),
                    'volume_ratio': round(leader_stock['volume_ratio'], 2),
                    'leadership_score': round(leader_stock['leadership_score'], 2)
                } if leader_stock else None,
                'follower_stocks': [
                    {
                        'symbol': stock['symbol'],
                        'rank': stock['rank'],
                        'change_pct': round(stock['change_pct'], 2),
                        'role': stock['role']
                    }
                    for stock in theme_data['stocks'][1:4]  # 上位3フォロワー
                ],
                'news_highlights': []
            }

            # ニュースハイライト追加
            if leader_stock and leader_stock['symbol'] in all_news:
                theme_info['news_highlights'] = [
                    {
                        'title': news['title'],
                        'source': news['source']
                    }
                    for news in all_news[leader_stock['symbol']][:2]
                ]

            report['theme_rankings'].append(theme_info)

        # 投資シグナル生成
        for theme_name, theme_data in sorted_themes[:3]:  # 上位3テーマ
            if theme_data['strength_score'] > 30:
                signal = {
                    'signal_type': 'テーマ連動エントリー',
                    'theme': theme_name,
                    'confidence': 'HIGH' if theme_data['strength_score'] > 70 else 'MEDIUM',
                    'strategy': '🎯 リーダー株確認後、フォロワー株へのエントリー検討',
                    'leader': theme_data['stocks'][0]['symbol'],
                    'targets': [s['symbol'] for s in theme_data['stocks'][1:3]],
                    'risk_note': '⚠️ テーマの持続性とニュースの信頼性を確認'
                }
                report['investment_signals'].append(signal)

        # 監視リスト
        for theme_data in ranked_themes.values():
            for stock in theme_data['stocks'][:2]:  # 各テーマの上位2銘柄
                report['watchlist'].append({
                    'symbol': stock['symbol'],
                    'theme': theme_data['theme_name'],
                    'role': stock['role'],
                    'change_pct': round(stock['change_pct'], 2),
                    'leadership_score': round(stock['leadership_score'], 2),
                    'priority': 'HIGH' if stock['rank'] == 1 else 'MEDIUM'
                })

        return report

    def run_advanced_screening(self, min_change_pct: float = 5.0) -> Dict:
        """
        高度スクリーニング実行

        Args:
            min_change_pct: 最小上昇率

        Returns:
            詳細分析結果
        """
        logger.info(f"Starting advanced theme screening (min change: {min_change_pct}%)")

        # 1. セクター別上昇銘柄取得
        sector_gainers = self.get_sector_gainers(min_change_pct)

        if not sector_gainers:
            logger.warning("No sector gainers found")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': 'No sector gainers found',
                'summary': {'detected_themes': 0}
            }

        # 2. ニュース収集
        all_symbols = []
        for stocks in sector_gainers.values():
            all_symbols.extend([s['symbol'] for s in stocks])

        all_news = self.fetch_comprehensive_news(all_symbols)

        # 3. テーマ相関分析
        theme_analysis = self.analyze_theme_correlation(sector_gainers)

        # 4. リーダー・フォロワー識別
        ranked_themes = self.identify_theme_leaders(theme_analysis)

        # 5. 詳細レポート生成
        report = self.generate_advanced_report(ranked_themes, all_news)

        # 6. 保存
        self.save_advanced_report(report)

        logger.info(f"Advanced screening completed: {len(ranked_themes)} themes detected")

        return report

    def save_advanced_report(self, report: Dict):
        """詳細レポート保存"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"data/reports/advanced_theme_report_{timestamp}.json"

        try:
            import os
            os.makedirs('data/reports', exist_ok=True)

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            logger.info(f"Advanced report saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save advanced report: {e}")


def main():
    """メイン実行"""
    screener = AdvancedThemeScreener()

    # 高度スクリーニング実行
    report = screener.run_advanced_screening(min_change_pct=3.0)

    # 結果表示
    print("\n" + "="*80)
    print("🚀 高度テーマ関連銘柄連動分析結果")
    print("="*80)

    print(f"\n📊 分析概要:")
    print(f"  実行時刻: {report['timestamp']}")
    print(f"  検出テーマ数: {report['summary']['detected_themes']}")
    print(f"  総銘柄数: {report['summary']['total_gainers']}")
    print(f"  強力テーマ数: {report['summary']['strong_themes']}")
    print(f"  出来高急増テーマ数: {report['summary']['volume_surge_themes']}")

    if report['summary']['detected_themes'] > 0:
        print(f"\n🎯 テーマランキング TOP5:")
        for i, theme in enumerate(report['theme_rankings'][:5], 1):
            surge_mark = "🔥" if theme['volume_surge'] else ""
            print(f"  {i}. {theme['theme_name']} {surge_mark}")
            print(f"     強度: {theme['strength_score']}, 銘柄数: {theme['stock_count']}")

            if theme['leader_stock']:
                leader = theme['leader_stock']
                print(f"     👑 リーダー: [{leader['symbol']}] +{leader['change_pct']}% "
                      f"(出来高比: {leader['volume_ratio']:.1f}倍)")

            if theme['follower_stocks']:
                print(f"     📈 フォロワー:")
                for follower in theme['follower_stocks'][:2]:
                    print(f"        {follower['rank']}位: [{follower['symbol']}] "
                          f"+{follower['change_pct']}% ({follower['role']})")
            print()

        print(f"\n💡 投資シグナル:")
        for signal in report['investment_signals']:
            confidence_mark = "🔴" if signal['confidence'] == 'HIGH' else "🟡"
            print(f"  {confidence_mark} {signal['signal_type']} - {signal['theme']}")
            print(f"     戦略: {signal['strategy']}")
            print(f"     リーダー: {signal['leader']}")
            print(f"     ターゲット: {', '.join(signal['targets'])}")
            print(f"     ⚠️ {signal['risk_note']}")
            print()

        print(f"\n👀 優先監視リスト:")
        high_priority = [w for w in report['watchlist'] if w['priority'] == 'HIGH']
        for item in high_priority[:10]:
            priority_mark = "🔴" if item['priority'] == 'HIGH' else "🟡"
            print(f"  {priority_mark} [{item['symbol']}] {item['theme']} - {item['role']}")
            print(f"      +{item['change_pct']}% (スコア: {item['leadership_score']:.1f})")

if __name__ == '__main__':
    main()