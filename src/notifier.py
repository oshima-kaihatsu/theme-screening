"""
通知モジュール
"""

import os
import csv
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List
from loguru import logger
import json


class Notifier:
    """通知・出力クラス"""

    def __init__(self, config: Dict):
        """
        初期化

        Args:
            config: 設定辞書
        """
        self.config = config
        self.notification_config = config.get('notification', {})

        # LINE Notify設定
        self.line_token = os.getenv('LINE_NOTIFY_TOKEN')

        # Discord Webhook設定
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')

    def send_notification(self, report: str, results: Dict):
        """
        設定に基づいて通知を送信

        Args:
            report: テキストレポート
            results: スクリーニング結果データ
        """
        if not self.notification_config.get('enabled', False):
            logger.info("Notifications are disabled")
            return

        channels = self.notification_config.get('channels', [])

        for channel in channels:
            if not channel.get('enabled', False):
                continue

            channel_type = channel.get('type')

            try:
                if channel_type == 'line':
                    self.send_line_notify(report)
                elif channel_type == 'discord':
                    self.send_discord_webhook(report)
                elif channel_type == 'file':
                    file_path = channel.get('path', 'data/screening_results.csv')
                    self.save_to_csv(results, file_path)
                    # HTMLレポートも保存
                    html_path = file_path.replace('.csv', '.html')
                    html_report = self.create_html_report(results)
                    self.save_html_report(html_report, html_path)

            except Exception as e:
                logger.error(f"Error sending notification via {channel_type}: {e}")

    def send_line_notify(self, message: str):
        """
        LINE Notify送信

        Args:
            message: 送信メッセージ
        """
        if not self.line_token:
            logger.warning("LINE Notify token not configured")
            return

        try:
            url = "https://notify-api.line.me/api/notify"
            headers = {
                "Authorization": f"Bearer {self.line_token}"
            }

            # メッセージが長すぎる場合は分割
            max_length = 1000
            if len(message) > max_length:
                # 重要な部分（TOP5）のみ送信
                lines = message.split('\n')
                summary_lines = []
                in_top5 = False

                for line in lines:
                    if '【推奨銘柄TOP5】' in line:
                        in_top5 = True
                        summary_lines.append(line)
                    elif in_top5 and ('【' in line or '=' in line):
                        break
                    elif in_top5:
                        summary_lines.append(line)
                    elif 'スクリーニング結果' in line or '実行時刻:' in line:
                        summary_lines.append(line)

                message = '\n'.join(summary_lines[:50])  # 最初の50行

            data = {"message": message}

            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()

            logger.info("LINE notification sent successfully")

        except Exception as e:
            logger.error(f"Error sending LINE notification: {e}")

    def send_discord_webhook(self, message: str):
        """
        Discord Webhook送信

        Args:
            message: 送信メッセージ
        """
        if not self.discord_webhook:
            logger.warning("Discord webhook URL not configured")
            return

        try:
            # Discordの文字数制限（2000文字）
            if len(message) > 1900:
                message = message[:1900] + "..."

            data = {
                "content": f"```\n{message}\n```"
            }

            response = requests.post(self.discord_webhook, json=data)
            response.raise_for_status()

            logger.info("Discord notification sent successfully")

        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")

    def save_to_csv(self, results: Dict, filepath: str):
        """
        CSV出力

        Args:
            results: スクリーニング結果
            filepath: 出力ファイルパス
        """
        try:
            # ディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # 推奨銘柄とウォッチリストをまとめる
            all_stocks = results.get('top_picks', []) + results.get('watch_list', [])

            if not all_stocks:
                logger.warning("No stocks to save to CSV")
                return

            # CSV用データ準備
            csv_data = []
            for stock in all_stocks:
                row = {
                    'timestamp': results.get('timestamp', datetime.now()).strftime('%Y-%m-%d %H:%M:%S'),
                    'rank': stock.get('rank', 0),
                    'symbol': stock.get('symbol', ''),
                    'name': stock.get('name', ''),
                    'total_score': stock.get('total_score', 0),
                    'current_price': stock.get('current_price', 0),
                    'gap_ratio': stock.get('gap_ratio', 0),
                    'volume_ratio': stock.get('volume_ratio', 1),
                    'market_cap': stock.get('market_cap', 0),
                    'risk_level': stock.get('risk_level', 'unknown'),
                    'stop_loss_price': stock.get('stop_loss_price', 0),
                    'take_profit_price': stock.get('take_profit_price', 0),
                    'signals': '|'.join(stock.get('signals', [])),
                    'warnings': '|'.join(stock.get('warnings', [])),
                    'volume_score': stock.get('score_breakdown', {}).get('volume_score', 0),
                    'gap_score': stock.get('score_breakdown', {}).get('gap_score', 0),
                    'technical_score': stock.get('score_breakdown', {}).get('technical_score', 0),
                    'news_score': stock.get('score_breakdown', {}).get('news_score', 0)
                }
                csv_data.append(row)

            # DataFrameに変換してCSV保存
            df = pd.DataFrame(csv_data)

            # 既存ファイルに追記するかどうか
            file_exists = os.path.exists(filepath)
            mode = 'a' if file_exists else 'w'
            header = not file_exists

            df.to_csv(filepath, mode=mode, header=header, index=False, encoding='utf-8-sig')

            logger.info(f"Results saved to CSV: {filepath}")

        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")

    def create_html_report(self, results: Dict) -> str:
        """
        HTMLレポート生成

        Args:
            results: スクリーニング結果

        Returns:
            str: HTMLレポート
        """
        try:
            timestamp = results.get('timestamp', datetime.now())
            top_picks = results.get('top_picks', [])
            watch_list = results.get('watch_list', [])
            statistics = results.get('statistics', {})

            html = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>デイトレスクリーニング結果 - {timestamp.strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            border-bottom: 2px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #007bff;
            margin: 0;
        }}
        .stats {{
            display: flex;
            justify-content: space-around;
            margin-bottom: 30px;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 5px;
        }}
        .stat-item {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }}
        .stock-card {{
            border: 1px solid #ddd;
            border-radius: 5px;
            margin-bottom: 20px;
            padding: 20px;
            background-color: #fafafa;
        }}
        .stock-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .stock-title {{
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }}
        .score {{
            font-size: 20px;
            font-weight: bold;
            color: #28a745;
            background-color: #d4edda;
            padding: 5px 10px;
            border-radius: 3px;
        }}
        .stock-details {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }}
        .detail-item {{
            background-color: white;
            padding: 10px;
            border-radius: 3px;
            border-left: 3px solid #007bff;
        }}
        .detail-label {{
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
        }}
        .detail-value {{
            font-size: 14px;
            font-weight: bold;
            color: #333;
        }}
        .signals {{
            margin-top: 10px;
        }}
        .signal-tag {{
            display: inline-block;
            background-color: #007bff;
            color: white;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
            margin: 2px;
        }}
        .warning-tag {{
            display: inline-block;
            background-color: #dc3545;
            color: white;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
            margin: 2px;
        }}
        .section-title {{
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
            margin: 30px 0 20px 0;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>デイトレスクリーニング結果</h1>
            <p>実行時刻: {timestamp.strftime('%Y年%m月%d日 %H:%M:%S')}</p>
        </div>

        <div class="stats">
            <div class="stat-item">
                <div class="stat-value">{len(top_picks)}</div>
                <div>推奨銘柄</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{len(watch_list)}</div>
                <div>ウォッチ銘柄</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{statistics.get('max_score', 0):.1f}</div>
                <div>最高スコア</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{statistics.get('avg_score', 0):.1f}</div>
                <div>平均スコア</div>
            </div>
        </div>
"""

            # 推奨銘柄TOP5
            if top_picks:
                html += '<div class="section-title">推奨銘柄 TOP5</div>'

                for stock in top_picks:
                    html += self._generate_stock_card_html(stock)

            # ウォッチリスト
            if watch_list:
                html += '<div class="section-title">ウォッチリスト</div>'

                for stock in watch_list[:10]:  # 上位10銘柄のみ表示
                    html += self._generate_stock_card_html(stock)

            html += """
    </div>
</body>
</html>
"""

            return html

        except Exception as e:
            logger.error(f"Error creating HTML report: {e}")
            return f"<html><body><h1>レポート生成エラー</h1><p>{e}</p></body></html>"

    def _generate_stock_card_html(self, stock: Dict) -> str:
        """個別銘柄のHTMLカード生成"""
        signals = stock.get('signals', [])
        warnings = stock.get('warnings', [])

        signal_tags = ''.join([f'<span class="signal-tag">{signal}</span>' for signal in signals])
        warning_tags = ''.join([f'<span class="warning-tag">{warning}</span>' for warning in warnings])

        gap_ratio = stock.get('gap_ratio', 0)
        gap_display = f"+{gap_ratio:.1%}" if gap_ratio > 0 else f"{gap_ratio:.1%}"

        return f"""
        <div class="stock-card">
            <div class="stock-header">
                <div class="stock-title">{stock.get('rank', '')}. [{stock.get('symbol', '')}] {stock.get('name', '')}</div>
                <div class="score">{stock.get('total_score', 0):.1f}/100</div>
            </div>
            <div class="stock-details">
                <div class="detail-item">
                    <div class="detail-label">現在値</div>
                    <div class="detail-value">{stock.get('current_price', 0):,.0f}円</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">前日比</div>
                    <div class="detail-value">{gap_display}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">出来高比</div>
                    <div class="detail-value">{stock.get('volume_ratio', 1):.1f}倍</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">利確目標</div>
                    <div class="detail-value">{stock.get('take_profit_price', 0):,.0f}円</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">損切り</div>
                    <div class="detail-value">{stock.get('stop_loss_price', 0):,.0f}円</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">リスクレベル</div>
                    <div class="detail-value">{stock.get('risk_level', 'unknown').upper()}</div>
                </div>
            </div>
            <div class="signals">
                {signal_tags}
                {warning_tags}
            </div>
        </div>
        """

    def save_html_report(self, html: str, filepath: str):
        """
        HTMLレポートをファイルに保存

        Args:
            html: HTMLコンテンツ
            filepath: 保存先ファイルパス
        """
        try:
            # ディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)

            logger.info(f"HTML report saved: {filepath}")

        except Exception as e:
            logger.error(f"Error saving HTML report: {e}")

    def save_json_results(self, results: Dict, filepath: str):
        """
        結果をJSON形式で保存

        Args:
            results: スクリーニング結果
            filepath: 保存先ファイルパス
        """
        try:
            # ディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # datetimeオブジェクトを文字列に変換
            results_copy = dict(results)
            if 'timestamp' in results_copy:
                results_copy['timestamp'] = results_copy['timestamp'].isoformat()

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results_copy, f, ensure_ascii=False, indent=2)

            logger.info(f"JSON results saved: {filepath}")

        except Exception as e:
            logger.error(f"Error saving JSON results: {e}")