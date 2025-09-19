# デプロイメントガイド
# Deployment Guide for Theme Screening App

## Vercelデプロイメント

### 必要ファイル
- ✅ `package.json` - Node.js環境設定
- ✅ `vercel.json` - Vercel設定（Python用）
- ✅ `requirements.txt` - Python依存関係
- ✅ `wsgi.py` - WSGIエントリーポイント
- ✅ `.env.production` - 本番環境変数

### デプロイ手順

1. **GitHubリポジトリ準備**
   ```bash
   git init
   git add .
   git commit -m "Initial commit for theme screening app"
   git remote add origin https://github.com/yourusername/theme-screening.git
   git push -u origin main
   ```

2. **Vercelプロジェクト作成**
   - VercelダッシュボードでNew Project
   - GitHubリポジトリを選択
   - Framework Preset: Other
   - Build Command: `echo "Python app - no build required"`
   - Output Directory: (空白)
   - Install Command: `pip install -r requirements.txt`

3. **環境変数設定**
   Vercelダッシュボードで以下を設定:
   ```
   FLASK_ENV=production
   SECRET_KEY=your-production-secret-key
   LOG_LEVEL=INFO
   TIMEZONE=Asia/Tokyo
   ```

## Dockerデプロイメント

### ローカルテスト
```bash
# イメージビルド
docker build -t theme-screening .

# コンテナ実行
docker run -p 5001:5001 theme-screening
```

### 本番デプロイ（Docker Hub）
```bash
# タグ付け
docker tag theme-screening yourusername/theme-screening:latest

# プッシュ
docker push yourusername/theme-screening:latest
```

## アクセスURL
- 開発環境: http://localhost:5001
- 本番環境: https://your-vercel-app.vercel.app

## 動作確認項目
- [ ] メインページ表示
- [ ] スクリーニング実行
- [ ] レポート表示
- [ ] CSV エクスポート
- [ ] リアルタイムデータ取得
- [ ] 材料調査機能