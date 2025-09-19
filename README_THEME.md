# テーマ関連銘柄連動手法スクリーニングシステム
Theme-Based Stock Movement Screening System

## 🚀 概要

このシステムは、日本株市場において同一テーマで連動して動く銘柄群を自動検出し、リーダー銘柄とフォロワー銘柄を識別するスクリーニングツールです。

## ✨ 主要機能

### 1. 値上がり率ランキングチェック
- ストップ高銘柄の自動検出
- 前日比20%以上の急騰銘柄抽出
- 複数銘柄の同時急騰パターン認識

### 2. 材料調査（自動化）
- Yahoo!ファイナンスからのニュース取得
- 株探からの材料ニュース収集
- AIによるテーマ分類とクラスタリング

### 3. 銘柄の序列判定
- **リーダー銘柄**: 最も出来高が多く、材料の中心
- **フォロワー銘柄**: 同テーマで追随する銘柄
- 時価総額と出来高を考慮した序列スコアリング

### 4. リアルタイム監視
- Webダッシュボードでの可視化
- 自動更新機能（30分間隔）
- CSVエクスポート機能

## 📋 必要要件

- Python 3.8以上
- 必要パッケージは `requirements_theme.txt` 参照

## 🔧 インストール

```bash
# 依存パッケージインストール
pip install -r requirements_theme.txt

# データディレクトリ作成
mkdir -p data/logs data/reports
```

## 🎮 使用方法

### ローカル実行

```bash
# CLIモード（単発実行）
python theme_screener.py

# Webサーバー起動
python theme_web_app.py
```

ブラウザで `http://localhost:5001` にアクセス

### 本番環境デプロイ

```bash
# Gunicornで起動
gunicorn -w 4 -b 0.0.0.0:5001 wsgi:app

# または環境変数設定
export FLASK_ENV=production
python theme_web_app.py
```

## 🌐 API エンドポイント

| エンドポイント | メソッド | 説明 |
|-------------|---------|------|
| `/api/screening/run` | POST | スクリーニング実行 |
| `/api/screening/latest` | GET | 最新結果取得 |
| `/api/screening/status` | GET | 実行状態確認 |
| `/api/themes/<theme>` | GET | テーマ詳細取得 |
| `/api/stock/<symbol>` | GET | 銘柄詳細取得 |
| `/api/export` | GET | レポートエクスポート |
| `/api/history` | GET | 過去レポート一覧 |

## 📊 出力例

```json
{
  "timestamp": "2024-01-15T09:30:00",
  "summary": {
    "total_gainers": 45,
    "themes_detected": 5,
    "top_themes": ["AI・人工知能", "半導体", "防衛"],
    "limit_up_count": 3
  },
  "themes": [
    {
      "name": "AI・人工知能",
      "stock_count": 8,
      "stocks": [
        {
          "rank": 1,
          "symbol": "3655.T",
          "name": "ブレインパッド",
          "role": "リーダー",
          "change_pct": 23.5,
          "news": [...]
        }
      ]
    }
  ],
  "watchlist": [...]
}
```

## 🎯 活用戦略

### デイトレード戦略
1. 朝9時前にスクリーニング実行
2. リーダー銘柄の初動を確認
3. フォロワー銘柄へのエントリータイミング判断
4. テーマの持続性を監視

### リスク管理
- 複数テーマへの分散
- 出来高の確認
- ニュースの信頼性評価

## 📈 パフォーマンス

- 約400銘柄を3-5分でスクリーニング
- リアルタイムデータ取得
- 自動クラスタリングによるテーマ発見

## 🔐 セキュリティ

- APIレート制限実装
- CORS設定可能
- セッション管理

## 🛠 カスタマイズ

`deploy_config.py` で以下の設定が可能:
- 最小上昇率の調整
- スキャン銘柄数の変更
- 更新間隔の設定
- データベース接続設定

## 📝 ライセンス

MIT License

## 🤝 貢献

プルリクエスト歓迎です。大きな変更の場合は、まずissueを開いて変更内容を議論してください。

## 📧 サポート

問題が発生した場合は、GitHubのissueトラッカーで報告してください。

---

**注意事項**: 本システムは情報提供のみを目的としており、投資判断は自己責任で行ってください。