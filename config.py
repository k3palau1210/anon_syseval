"""設定管理モジュール"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# データベース
DATABASE_PATH = os.path.join(BASE_DIR, "data", "masking_eval.db")

# サーバー設定
HOST = "0.0.0.0"
PORT = 5001
DEBUG = True

# デフォルトSLMタイプ
SLM_TYPES = {
    "local": "ローカル (Ollama等)",
    "api": "API (OpenAI互換等)",
    "remote": "リモート (Mac mini M4Pro等)",
    "reference": "リファレンス (Gemini/Claude)",
}

# デフォルトマスキングカテゴリ
DEFAULT_MASKING_CATEGORIES = [
    {"name": "氏名", "description": "個人の氏名（姓名）"},
    {"name": "電話番号", "description": "固定電話・携帯電話番号"},
    {"name": "住所", "description": "都道府県・市区町村・番地等"},
    {"name": "メールアドレス", "description": "メールアドレス"},
    {"name": "生年月日", "description": "生年月日・年齢"},
    {"name": "クレジットカード番号", "description": "クレジットカード番号"},
    {"name": "口座番号", "description": "銀行口座番号"},
    {"name": "マイナンバー", "description": "マイナンバー（個人番号）"},
    {"name": "カスタム", "description": "ユーザー定義のカスタムパターン"},
]
