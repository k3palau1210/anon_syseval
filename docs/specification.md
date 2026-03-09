# マスキング評価システム 仕様書

| 項目 | 内容 |
|------|------|
| システム名 | マスキング評価システム |
| バージョン | 2.0 |
| 最終更新日 | 2026-03-09 |
| フレームワーク | FastAPI / Uvicorn |

---

## 1. システム概要

### 1.1 目的

コールセンター音声認識データに含まれる個人情報のマスキング処理において、最適な SLM（Small Language Model）を選定するためのベンチマーク評価プラットフォーム。

### 1.2 主要機能

- SLM サービスの登録・起動・停止・ステータス管理
- マスキングルール（個人情報カテゴリ）の管理
- テストデータの登録・インポート（JSON / CSV / TXT / フォルダ一括）
- 複数 SLM の一括ベンチマーク実行
- Precision / Recall / F1 / 一致率 / 処理時間の比較評価
- リファレンス結果（Gemini / Claude）との比較
- テストデータ毎の詳細並列比較
- 単体マスキングテスト
- Swagger UI による API ドキュメント自動生成

### 1.3 技術スタック

| レイヤー | 技術 |
|----------|------|
| バックエンド | Python 3.10+ / FastAPI 0.115 / Uvicorn 0.34 |
| フロントエンド | HTML / CSS / JavaScript（SPA 構成） |
| データベース | SQLite（WAL モード） |
| SLM 連携 | Ollama API / OpenAI 互換 API / リモート SSH |
| API ドキュメント | Swagger UI（`/docs`）/ ReDoc（`/redoc`） |

---

## 2. ディレクトリ構成

```
マスキング評価システム/
├── app.py                  # FastAPI メインアプリケーション
├── config.py               # 設定（ポート、DBパス、SLMタイプ、デフォルトカテゴリ）
├── requirements.txt        # Python 依存パッケージ
├── README.md               # プロジェクト説明
├── models/
│   ├── __init__.py
│   └── database.py         # SQLite スキーマ定義・初期化・ヘルパー関数
├── services/
│   ├── __init__.py
│   ├── slm_manager.py      # SLM サービス管理（起動/停止/リクエスト送信）
│   ├── masking_engine.py   # マスキングプロンプト構築・実行・結果比較
│   └── benchmark_engine.py # ベンチマーク実行・評価エンジン
├── templates/
│   └── index.html          # SPA テンプレート（全7画面）
├── static/
│   ├── css/style.css       # スタイルシート
│   └── js/app.js           # フロントエンド JavaScript
├── data/                   # SQLite DB ファイル（自動生成）
└── docs/                   # ドキュメント
    ├── specification.md    # 本仕様書
    └── 操作説明書.docx      # 操作説明書
```

---

## 3. データベース設計

データベースは SQLite を使用し、WAL モードで運用します。外部キー制約は有効化されています。

### 3.1 ER 図

```
slm_services ──┐
               ├──< benchmark_results >── benchmark_runs
test_data ─────┤
               └──< reference_results
masking_rules（独立テーブル）
```

### 3.2 テーブル定義

#### 3.2.1 slm_services（SLM サービス定義）

| カラム名 | 型 | 制約 | 説明 |
|----------|-----|------|------|
| id | INTEGER | PK, AUTOINCREMENT | サービスID |
| name | TEXT | NOT NULL | サービス名 |
| type | TEXT | NOT NULL, CHECK | タイプ（local/api/remote/reference） |
| model_name | TEXT | | モデル名 |
| endpoint | TEXT | | エンドポイントURL |
| api_key | TEXT | | APIキー |
| config_json | TEXT | DEFAULT '{}' | 追加設定（JSON） |
| status | TEXT | DEFAULT 'stopped', CHECK | ステータス（running/stopped/error/unknown） |
| created_at | TEXT | DEFAULT datetime | 作成日時 |
| updated_at | TEXT | DEFAULT datetime | 更新日時 |

#### 3.2.2 masking_rules（マスキングルール）

| カラム名 | 型 | 制約 | 説明 |
|----------|-----|------|------|
| id | INTEGER | PK, AUTOINCREMENT | ルールID |
| category | TEXT | NOT NULL | カテゴリ名（氏名、電話番号等） |
| pattern | TEXT | | 正規表現パターン |
| replacement | TEXT | DEFAULT '***' | 置換文字列 |
| description | TEXT | | 説明 |
| is_active | INTEGER | DEFAULT 1 | 有効フラグ（1=有効, 0=無効） |
| priority | INTEGER | DEFAULT 0 | 優先度（大きいほど優先） |
| created_at | TEXT | DEFAULT datetime | 作成日時 |

#### 3.2.3 test_data（テストデータ）

| カラム名 | 型 | 制約 | 説明 |
|----------|-----|------|------|
| id | INTEGER | PK, AUTOINCREMENT | データID |
| title | TEXT | NOT NULL | タイトル |
| original_text | TEXT | NOT NULL | 元テキスト |
| expected_masked_text | TEXT | | 期待されるマスキング結果 |
| metadata_json | TEXT | DEFAULT '{}' | メタデータ（JSON） |
| created_at | TEXT | DEFAULT datetime | 作成日時 |

#### 3.2.4 benchmark_runs（ベンチマーク実行記録）

| カラム名 | 型 | 制約 | 説明 |
|----------|-----|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 実行ID |
| name | TEXT | | ベンチマーク名 |
| description | TEXT | | 説明 |
| status | TEXT | DEFAULT 'pending', CHECK | ステータス（pending/running/completed/failed） |
| slm_service_ids | TEXT | | 対象SLM IDリスト（JSON） |
| test_data_ids | TEXT | | 対象テストデータIDリスト（JSON） |
| started_at | TEXT | | 開始日時 |
| completed_at | TEXT | | 完了日時 |
| created_at | TEXT | DEFAULT datetime | 作成日時 |

#### 3.2.5 benchmark_results（ベンチマーク個別結果）

| カラム名 | 型 | 制約 | 説明 |
|----------|-----|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 結果ID |
| run_id | INTEGER | NOT NULL, FK | ベンチマーク実行ID |
| slm_service_id | INTEGER | NOT NULL, FK | SLMサービスID |
| test_data_id | INTEGER | NOT NULL, FK | テストデータID |
| masked_text | TEXT | | マスキング結果テキスト |
| processing_time_ms | REAL | | 処理時間（ミリ秒） |
| precision_score | REAL | | Precision スコア |
| recall_score | REAL | | Recall スコア |
| f1_score | REAL | | F1 スコア |
| match_rate | REAL | | 完全一致率 |
| details_json | TEXT | DEFAULT '{}' | 詳細情報（JSON） |
| created_at | TEXT | DEFAULT datetime | 作成日時 |

#### 3.2.6 reference_results（リファレンス結果）

| カラム名 | 型 | 制約 | 説明 |
|----------|-----|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 結果ID |
| test_data_id | INTEGER | NOT NULL, FK | テストデータID |
| model_name | TEXT | NOT NULL | モデル名（Gemini/Claude等） |
| masked_text | TEXT | NOT NULL | マスキング結果テキスト |
| metadata_json | TEXT | DEFAULT '{}' | メタデータ（JSON） |
| created_at | TEXT | DEFAULT datetime | 作成日時 |

### 3.3 デフォルトマスキングカテゴリ

初回起動時に以下の 9 カテゴリが自動登録されます。

| カテゴリ | 説明 |
|----------|------|
| 氏名 | 個人の氏名（姓名） |
| 電話番号 | 固定電話・携帯電話番号 |
| 住所 | 都道府県・市区町村・番地等 |
| メールアドレス | メールアドレス |
| 生年月日 | 生年月日・年齢 |
| クレジットカード番号 | クレジットカード番号 |
| 口座番号 | 銀行口座番号 |
| マイナンバー | マイナンバー（個人番号） |
| カスタム | ユーザー定義のカスタムパターン |

---

## 4. API エンドポイント一覧

ベースURL: `http://localhost:5001`

### 4.1 ページルーティング

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/` | メイン画面（SPA） |

### 4.2 SLM サービス API

| メソッド | パス | 説明 | ステータスコード |
|----------|------|------|----------------|
| GET | `/api/slm-services` | 全サービス一覧取得 | 200 |
| POST | `/api/slm-services` | サービス登録 | 201 |
| GET | `/api/slm-services/{sid}` | サービス取得 | 200 / 404 |
| PUT | `/api/slm-services/{sid}` | サービス更新 | 200 / 404 |
| DELETE | `/api/slm-services/{sid}` | サービス削除 | 200 |
| POST | `/api/slm-services/{sid}/start` | サービス起動 | 200 |
| POST | `/api/slm-services/{sid}/stop` | サービス停止 | 200 |
| GET | `/api/slm-services/{sid}/status` | ステータス取得 | 200 / 404 |

### 4.3 マスキングルール API

| メソッド | パス | 説明 | ステータスコード |
|----------|------|------|----------------|
| GET | `/api/masking-rules` | ルール一覧取得 | 200 |
| POST | `/api/masking-rules` | ルール作成 | 201 |
| PUT | `/api/masking-rules/{rid}` | ルール更新 | 200 |
| DELETE | `/api/masking-rules/{rid}` | ルール削除 | 200 |

### 4.4 テストデータ API

| メソッド | パス | 説明 | ステータスコード |
|----------|------|------|----------------|
| GET | `/api/test-data` | データ一覧取得 | 200 |
| POST | `/api/test-data` | データ作成 | 201 |
| PUT | `/api/test-data/{tid}` | データ更新 | 200 |
| DELETE | `/api/test-data/{tid}` | データ削除 | 200 |
| POST | `/api/test-data/import` | JSON 一括インポート | 200 |
| POST | `/api/test-data/upload` | ファイルアップロード（JSON/CSV/TXT） | 200 / 400 |
| POST | `/api/test-data/import-folder` | フォルダ一括インポート | 200 / 400 |
| GET | `/api/test-data/stats` | 統計情報取得 | 200 |
| POST | `/api/test-data/delete-all` | 全データ削除 | 200 |

### 4.5 ベンチマーク API

| メソッド | パス | 説明 | ステータスコード |
|----------|------|------|----------------|
| GET | `/api/benchmark/runs` | 全実行一覧取得 | 200 |
| GET | `/api/benchmark/runs/{run_id}` | 実行詳細取得 | 200 / 404 |
| POST | `/api/benchmark/run` | ベンチマーク実行 | 200 / 400 |
| POST | `/api/benchmark/compare` | 結果比較 | 200 / 400 |
| POST | `/api/benchmark/detail-compare` | 詳細比較 | 200 / 400 |
| DELETE | `/api/benchmark/runs/{run_id}` | 実行削除 | 200 |

### 4.6 リファレンス結果 API

| メソッド | パス | 説明 | ステータスコード |
|----------|------|------|----------------|
| POST | `/api/reference/upload` | リファレンス結果アップロード | 200 |
| GET | `/api/reference` | リファレンス結果一覧取得 | 200 |
| DELETE | `/api/reference/{rid}` | リファレンス結果削除 | 200 |

### 4.7 その他 API

| メソッド | パス | 説明 | ステータスコード |
|----------|------|------|----------------|
| GET | `/api/slm-types` | SLM タイプ定義取得 | 200 |
| POST | `/api/masking/test` | 単体マスキングテスト | 200 / 400 / 404 / 500 |

---

## 5. SLM サービス連携仕様

### 5.1 対応サービスタイプ

| タイプ | 識別子 | プロトコル | 対象 |
|--------|--------|-----------|------|
| ローカル | `local` | Ollama REST API | Ollama 等ローカル推論 |
| API | `api` | OpenAI 互換 API | 外部 API サービス |
| リモート | `remote` | Ollama REST API（リモート） | Mac mini M4Pro 等 |
| リファレンス | `reference` | なし（結果アップロード） | Gemini / Claude |

### 5.2 リクエストプロトコル

#### ローカル / リモート（Ollama）

```
POST {endpoint}/api/generate
Content-Type: application/json

{
  "model": "{model_name}",
  "prompt": "{マスキングプロンプト}",
  "stream": false,
  "options": {config_json.options}
}
```

#### API（OpenAI 互換）

```
POST {endpoint}/chat/completions
Content-Type: application/json
Authorization: Bearer {api_key}

{
  "model": "{model_name}",
  "messages": [{"role": "user", "content": "{マスキングプロンプト}"}],
  "temperature": 0.0,
  "max_tokens": 4096
}
```

### 5.3 ヘルスチェック

- ローカル: プロセス存在確認 + エンドポイントへの GET リクエスト
- API / リモート: エンドポイントベースURLへの GET リクエスト（タイムアウト 3 秒）
- リファレンス: 常に `stopped`（直接リクエスト不可）

---

## 6. マスキング処理仕様

### 6.1 プロンプト構成

マスキングエンジンは以下の構造のプロンプトを自動構築し SLM に送信します。

```
あなたはコールセンターの通話記録から個人情報をマスキングする専門家です。
以下のテキストに含まれる個人情報やセンシティブな情報をマスキングしてください。

## マスキング対象カテゴリ
- {カテゴリ名}: {説明}（パターン例: {pattern}）
  ...

## マスキングルール
1. マスキング対象の情報を「[カテゴリ名]」の形式で置換してください。
   例: 田中太郎 → [氏名]、090-1234-5678 → [電話番号]
2. 文脈を維持しつつ、個人を特定できる情報をすべてマスキングしてください。
3. マスキング後のテキストのみを出力してください。余計な説明は不要です。

## 入力テキスト
{テストテキスト}

## マスキング後のテキスト
```

### 6.2 マスキング形式

個人情報は `[カテゴリ名]` 形式で置換されます。

| 元テキスト | マスキング後 |
|-----------|-------------|
| 田中太郎 | [氏名] |
| 090-1234-5678 | [電話番号] |
| 東京都渋谷区... | [住所] |
| test@example.com | [メールアドレス] |

---

## 7. ベンチマーク評価仕様

### 7.1 実行フロー

1. ベンチマーク実行レコードを作成（ステータス: `pending`）
2. バックグラウンドスレッドで実行開始（ステータス: `running`）
3. 各 SLM × 各テストデータの組み合わせでマスキングを実行
4. 期待結果またはリファレンス結果がある場合、比較評価を実施
5. 結果を `benchmark_results` テーブルに保存
6. 完了時にステータスを `completed` に更新

### 7.2 評価指標の算出方法

マスキング結果とリファレンス結果から `[カテゴリ名]` パターンを抽出し、カテゴリごとの出現数で比較します。

| 指標 | 算出方法 |
|------|---------|
| **True Positives (TP)** | 両方に存在する同一カテゴリタグの最小出現数 |
| **False Positives (FP)** | マスキング結果にのみ存在するタグ数 |
| **False Negatives (FN)** | リファレンスにのみ存在するタグ数 |
| **Precision** | TP / (TP + FP) |
| **Recall** | TP / (TP + FN) |
| **F1** | 2 × Precision × Recall / (Precision + Recall) |
| **一致率** | マスキング結果とリファレンスの完全文字列一致（0.0 or 1.0） |

---

## 8. UI 画面構成

フロントエンドは SPA 構成で、サイドバーナビゲーションにより 7 画面を切り替えます。

| No. | 画面ID | 画面名 | 主要機能 |
|-----|--------|--------|----------|
| 1 | `page-dashboard` | ダッシュボード | サービス数・テストデータ数・ベンチマーク数の統計表示 |
| 2 | `page-services` | SLMサービス管理 | サービスの CRUD・起動/停止制御 |
| 3 | `page-rules` | マスキングルール | ルールの CRUD・有効/無効切替 |
| 4 | `page-data` | テストデータ | データの CRUD・インポート・統計・文字数分布 |
| 5 | `page-benchmark` | ベンチマーク実行 | SLM/データ選択・実行・進捗表示・単体テスト |
| 6 | `page-results` | 結果比較 | ベンチマーク結果の指標比較・リファレンス管理 |
| 7 | `page-detail` | 詳細比較 | テストデータ毎の元テキスト/結果の並列比較 |

---

## 9. 設定項目

設定ファイル: `config.py`

| 項目 | デフォルト値 | 説明 |
|------|-------------|------|
| `HOST` | `0.0.0.0` | サーバーバインドアドレス |
| `PORT` | `5001` | サーバーポート |
| `DEBUG` | `True` | デバッグモード |
| `DATABASE_PATH` | `data/masking_eval.db` | SQLite DB ファイルパス |

---

## 10. 依存パッケージ

`requirements.txt`:

| パッケージ | バージョン | 用途 |
|-----------|-----------|------|
| fastapi | 0.115.12 | Web フレームワーク |
| uvicorn[standard] | 0.34.0 | ASGI サーバー |
| python-multipart | 0.0.20 | ファイルアップロード対応 |
| jinja2 | 3.1.6 | HTML テンプレートエンジン |
| requests | 2.32.3 | SLM への HTTP リクエスト |
