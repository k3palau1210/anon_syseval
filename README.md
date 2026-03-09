# マスキング評価システム

コールセンター音声認識データの個人情報マスキングに最適な SLM（Small Language Model）を選定するためのベンチマーク評価システムです。

## 機能概要

| 機能 | 説明 |
|---|---|
| **SLMサービス管理** | ローカル（Ollama等）・API・リモート（Mac mini M4Pro等）・リファレンス（Gemini/Claude）の各種SLMを登録・起動・停止 |
| **マスキングルール** | 氏名・電話番号・住所・メールアドレス等のマスキング対象カテゴリを管理 |
| **テストデータ管理** | テストテキストの登録・インポート（JSON/CSV/TXT/フォルダ一括） |
| **ベンチマーク実行** | 複数SLM × 複数テストデータのバッチ評価 |
| **結果比較** | Precision / Recall / F1 / 一致率 / 処理時間の比較・可視化 |
| **詳細比較** | 元テキスト・各SLM結果・リファレンスの並列比較 |
| **単体テスト** | 任意テキストでのマスキング即時テスト |
| **Swagger UI** | `/docs` で全APIの対話的ドキュメント |

## 技術スタック

- **バックエンド**: Python / FastAPI / Uvicorn
- **フロントエンド**: HTML / CSS / JavaScript（SPA構成）
- **データベース**: SQLite
- **SLM連携**: Ollama / OpenAI互換API / リモートSSH

## ディレクトリ構成

```
├── app.py                 # FastAPI メインアプリケーション
├── config.py              # 設定（ポート、DB パス、SLM タイプ等）
├── requirements.txt       # Python 依存パッケージ
├── models/
│   └── database.py        # SQLite スキーマ定義・ヘルパー関数
├── services/
│   ├── slm_manager.py     # SLM サービス起動/停止/リクエスト送信
│   ├── masking_engine.py  # マスキングプロンプト構築・実行・比較
│   └── benchmark_engine.py# ベンチマーク実行・評価エンジン
├── templates/
│   └── index.html         # SPA テンプレート
├── static/
│   ├── css/style.css      # スタイルシート
│   └── js/app.js          # フロントエンド JavaScript
├── data/                  # SQLite DB（自動生成）
└── docs/                  # 操作説明書
```

## セットアップ

```bash
# リポジトリのクローン
git clone https://github.com/k3palau1210/anon_syseval.git
cd anon_syseval

# 仮想環境の作成
python -m venv venv
source venv/bin/activate

# 依存パッケージのインストール
pip install -r requirements.txt

# 起動
python app.py
```

サーバーが `http://localhost:5001` で起動します。

## API ドキュメント

起動後、ブラウザで以下にアクセスすると Swagger UI が利用できます：

- **Swagger UI**: http://localhost:5001/docs
- **ReDoc**: http://localhost:5001/redoc

## 主要 API エンドポイント

| メソッド | パス | 説明 |
|---|---|---|
| `GET` | `/api/slm-services` | SLMサービス一覧 |
| `POST` | `/api/slm-services` | SLMサービス登録 |
| `POST` | `/api/slm-services/{id}/start` | SLMサービス起動 |
| `GET` | `/api/masking-rules` | マスキングルール一覧 |
| `GET` | `/api/test-data` | テストデータ一覧 |
| `POST` | `/api/test-data/upload` | テストデータアップロード |
| `POST` | `/api/benchmark/run` | ベンチマーク実行 |
| `POST` | `/api/benchmark/compare` | ベンチマーク比較 |
| `POST` | `/api/benchmark/detail-compare` | 詳細比較 |
| `POST` | `/api/masking/test` | 単体マスキングテスト |
