"""
クイックスクリーニング - 軽量版
Webダッシュボードからの呼び出し用
"""

import sys
sys.path.append('src')

import pandas as pd
import yfinance as yf
from datetime import datetime
from typing import Dict, List
import json
from loguru import logger
from utils import load_config


def quick_screening(max_stocks: int = 5) -> Dict:
    """
    クイックスクリーニング実行

    Args:
        max_stocks: 最大処理銘柄数

    Returns:
        Dict: スクリーニング結果
    """
    try:
        logger.info("Starting quick screening")

        # サンプル銘柄（軽量化のため少数）
        symbols = ['7203.T', '9984.T', '6098.T', '8058.T', '9432.T'][:max_stocks]

        results = []

        for symbol in symbols:
            try:
                logger.debug(f"Processing {symbol}")

                # Yahoo Financeから直接取得
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='5d')

                if hist.empty:
                    continue

                # 基本データ計算
                current = hist.iloc[-1]
                previous = hist.iloc[-2] if len(hist) > 1 else current

                current_price = float(current['Close'])
                gap_ratio = (current['Open'] - previous['Close']) / previous['Close']
                volume_ratio = current['Volume'] / hist['Volume'].mean()

                # シンプルスコア計算
                score = 50  # ベーススコア

                # 出来高急増
                if volume_ratio > 2.0:
                    score += 20
                elif volume_ratio > 1.5:
                    score += 10

                # ギャップアップ
                if 0.02 <= gap_ratio <= 0.05:
                    score += 15
                elif gap_ratio > 0.05:
                    score += 5  # あまり大きすぎるのは減点

                # 価格上昇トレンド
                if current_price > previous['Close']:
                    score += 10

                # シグナル検出
                signals = []
                if volume_ratio > 2.0:
                    signals.append(f"出来高急増({volume_ratio:.1f}倍)")
                if gap_ratio > 0.02:
                    signals.append(f"ギャップアップ({gap_ratio:.1%})")
                if current_price > hist['Close'].tail(5).mean():
                    signals.append("5日平均上回る")

                result = {
                    'symbol': symbol,
                    'name': symbol.replace('.T', ''),
                    'total_score': round(score, 1),
                    'current_price': current_price,
                    'gap_ratio': gap_ratio,
                    'volume_ratio': volume_ratio,
                    'signals': signals,
                    'rank': 0  # 後でソート時に設定
                }

                results.append(result)

                logger.debug(f"{symbol}: Score={score:.1f}, Price={current_price:.0f}")

            except Exception as e:
                logger.warning(f"Error processing {symbol}: {e}")
                continue

        # スコア順にソート
        results.sort(key=lambda x: x['total_score'], reverse=True)

        # ランキング設定
        for i, result in enumerate(results):
            result['rank'] = i + 1

        # 結果まとめ
        screening_result = {
            'timestamp': datetime.now(),
            'screening_type': 'quick',
            'execution_time': 10,  # 概算
            'total_processed': len(symbols),
            'filtered_count': len(results),
            'scored_count': len(results),
            'top_picks': results[:3],
            'watch_list': results[3:],
            'statistics': {
                'avg_score': sum(r['total_score'] for r in results) / len(results) if results else 0,
                'max_score': max(r['total_score'] for r in results) if results else 0,
                'min_score': min(r['total_score'] for r in results) if results else 0
            }
        }

        logger.info(f"Quick screening completed: {len(results)} stocks processed")
        return screening_result

    except Exception as e:
        logger.error(f"Error in quick screening: {e}")
        return {
            'error': str(e),
            'timestamp': datetime.now(),
            'screening_type': 'quick'
        }


def test_quick_screening():
    """テスト実行"""
    result = quick_screening()

    if 'error' in result:
        print(f"エラー: {result['error']}")
        return

    print("=" * 50)
    print("クイックスクリーニング結果")
    print("=" * 50)
    print(f"実行時刻: {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"処理銘柄数: {result['total_processed']}")
    print(f"平均スコア: {result['statistics']['avg_score']:.1f}")
    print()

    print("【推奨銘柄】")
    for stock in result['top_picks']:
        print(f"{stock['rank']}位: {stock['symbol']} - {stock['name']}")
        print(f"  スコア: {stock['total_score']}/100")
        print(f"  現在値: {stock['current_price']:,.0f}円")
        print(f"  前日比: {stock['gap_ratio']:+.1%}")
        print(f"  出来高比: {stock['volume_ratio']:.1f}倍")
        if stock['signals']:
            print(f"  シグナル: {', '.join(stock['signals'])}")
        print()


if __name__ == "__main__":
    test_quick_screening()