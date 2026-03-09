"""SQLiteデータベースモデル定義"""
import sqlite3
import os
import json
from datetime import datetime

import config


def get_db():
    """データベース接続を取得"""
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """データベース初期化"""
    conn = get_db()
    cursor = conn.cursor()

    # SLMサービス定義
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS slm_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('local', 'api', 'remote', 'reference')),
            model_name TEXT,
            endpoint TEXT,
            api_key TEXT,
            config_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'stopped' CHECK(status IN ('running', 'stopped', 'error', 'unknown')),
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # マスキングルール
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS masking_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            pattern TEXT,
            replacement TEXT DEFAULT '***',
            description TEXT,
            is_active INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # テストデータ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            original_text TEXT NOT NULL,
            expected_masked_text TEXT,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # ベンチマーク実行記録
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed')),
            slm_service_ids TEXT,
            test_data_ids TEXT,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # ベンチマーク個別結果
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            slm_service_id INTEGER NOT NULL,
            test_data_id INTEGER NOT NULL,
            masked_text TEXT,
            processing_time_ms REAL,
            precision_score REAL,
            recall_score REAL,
            f1_score REAL,
            match_rate REAL,
            details_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (run_id) REFERENCES benchmark_runs(id),
            FOREIGN KEY (slm_service_id) REFERENCES slm_services(id),
            FOREIGN KEY (test_data_id) REFERENCES test_data(id)
        )
    """)

    # リファレンス結果（Gemini/Claude）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reference_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_data_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            masked_text TEXT NOT NULL,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (test_data_id) REFERENCES test_data(id)
        )
    """)

    conn.commit()

    # デフォルトマスキングルールの挿入
    cursor.execute("SELECT COUNT(*) as cnt FROM masking_rules")
    if cursor.fetchone()["cnt"] == 0:
        for cat in config.DEFAULT_MASKING_CATEGORIES:
            cursor.execute(
                "INSERT INTO masking_rules (category, description) VALUES (?, ?)",
                (cat["name"], cat["description"]),
            )
        conn.commit()

    conn.close()


# ---- ヘルパー関数 ----

def row_to_dict(row):
    """sqlite3.Rowを辞書に変換"""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    """sqlite3.Rowのリストを辞書リストに変換"""
    return [dict(r) for r in rows]
