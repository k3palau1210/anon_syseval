"""ベンチマーク実行・評価エンジン"""
import time
import json
import threading
from datetime import datetime
from models.database import get_db, row_to_dict, rows_to_list
from services.slm_manager import SLMManager
from services.masking_engine import MaskingEngine


class BenchmarkEngine:
    """ベンチマーク実行管理"""

    # 実行中のベンチマークスレッド
    _running = {}

    @staticmethod
    def create_run(name, description, slm_service_ids, test_data_ids):
        """ベンチマーク実行を作成"""
        conn = get_db()
        cursor = conn.execute(
            """INSERT INTO benchmark_runs (name, description, slm_service_ids, test_data_ids, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (
                name,
                description,
                json.dumps(slm_service_ids),
                json.dumps(test_data_ids),
            ),
        )
        conn.commit()
        run_id = cursor.lastrowid
        conn.close()
        return run_id

    @staticmethod
    def start_run(run_id):
        """ベンチマーク実行を開始（バックグラウンドスレッド）"""
        if run_id in BenchmarkEngine._running:
            return {"success": False, "message": "既に実行中です"}

        thread = threading.Thread(target=BenchmarkEngine._execute_run, args=(run_id,), daemon=True)
        BenchmarkEngine._running[run_id] = thread
        thread.start()

        return {"success": True, "message": "ベンチマークを開始しました", "run_id": run_id}

    @staticmethod
    def _execute_run(run_id):
        """ベンチマーク実行の本体"""
        conn = get_db()
        run = row_to_dict(conn.execute("SELECT * FROM benchmark_runs WHERE id = ?", (run_id,)).fetchone())
        conn.close()

        if not run:
            return

        slm_ids = json.loads(run["slm_service_ids"])
        test_ids = json.loads(run["test_data_ids"])

        # ステータス更新: running
        conn = get_db()
        conn.execute(
            "UPDATE benchmark_runs SET status='running', started_at=datetime('now','localtime') WHERE id=?",
            (run_id,),
        )
        conn.commit()
        conn.close()

        rules = MaskingEngine.get_active_rules()

        try:
            for slm_id in slm_ids:
                service = SLMManager.get_service(slm_id)
                if not service or service["type"] == "reference":
                    continue

                for test_id in test_ids:
                    conn = get_db()
                    test = row_to_dict(
                        conn.execute("SELECT * FROM test_data WHERE id = ?", (test_id,)).fetchone()
                    )
                    conn.close()

                    if not test:
                        continue

                    # マスキング実行・計測
                    start_time = time.time()
                    result = MaskingEngine.execute_masking(None, service, test["original_text"], rules)
                    elapsed_ms = (time.time() - start_time) * 1000

                    masked_text = result.get("masked_text", "") if result["success"] else ""

                    # リファレンス結果との比較
                    ref_text = test.get("expected_masked_text", "")
                    if not ref_text:
                        # reference_resultsテーブルから取得
                        conn = get_db()
                        ref_row = conn.execute(
                            "SELECT masked_text FROM reference_results WHERE test_data_id = ? ORDER BY created_at DESC LIMIT 1",
                            (test_id,),
                        ).fetchone()
                        conn.close()
                        if ref_row:
                            ref_text = ref_row["masked_text"]

                    comparison = MaskingEngine.compare_results(masked_text, ref_text)

                    # 結果保存
                    conn = get_db()
                    conn.execute(
                        """INSERT INTO benchmark_results
                           (run_id, slm_service_id, test_data_id, masked_text,
                            processing_time_ms, precision_score, recall_score, f1_score, match_rate, details_json)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            run_id,
                            slm_id,
                            test_id,
                            masked_text,
                            round(elapsed_ms, 2),
                            comparison["precision"],
                            comparison["recall"],
                            comparison["f1"],
                            comparison["match_rate"],
                            json.dumps(comparison["details"], ensure_ascii=False),
                        ),
                    )
                    conn.commit()
                    conn.close()

            # 完了
            conn = get_db()
            conn.execute(
                "UPDATE benchmark_runs SET status='completed', completed_at=datetime('now','localtime') WHERE id=?",
                (run_id,),
            )
            conn.commit()
            conn.close()

        except Exception as e:
            conn = get_db()
            conn.execute(
                "UPDATE benchmark_runs SET status='failed', completed_at=datetime('now','localtime') WHERE id=?",
                (run_id,),
            )
            conn.commit()
            conn.close()
            print(f"Benchmark error: {e}")

        finally:
            if run_id in BenchmarkEngine._running:
                del BenchmarkEngine._running[run_id]

    @staticmethod
    def get_run(run_id):
        """ベンチマーク実行情報を取得"""
        conn = get_db()
        run = row_to_dict(conn.execute("SELECT * FROM benchmark_runs WHERE id = ?", (run_id,)).fetchone())
        if run:
            results = rows_to_list(
                conn.execute(
                    """SELECT br.*, ss.name as slm_name, td.title as test_title
                       FROM benchmark_results br
                       JOIN slm_services ss ON br.slm_service_id = ss.id
                       JOIN test_data td ON br.test_data_id = td.id
                       WHERE br.run_id = ?
                       ORDER BY br.slm_service_id, br.test_data_id""",
                    (run_id,),
                ).fetchall()
            )
            run["results"] = results

            # 進捗計算
            total = len(json.loads(run.get("slm_service_ids", "[]"))) * len(
                json.loads(run.get("test_data_ids", "[]"))
            )
            run["progress"] = {
                "completed": len(results),
                "total": total if total > 0 else 1,
            }
        conn.close()
        return run

    @staticmethod
    def get_all_runs():
        """全ベンチマーク実行を取得"""
        conn = get_db()
        rows = conn.execute("SELECT * FROM benchmark_runs ORDER BY created_at DESC").fetchall()
        conn.close()
        return rows_to_list(rows)

    @staticmethod
    def get_comparison(run_ids):
        """複数ベンチマーク結果を比較"""
        conn = get_db()
        placeholders = ",".join("?" * len(run_ids))

        # SLMごとの集計
        rows = conn.execute(
            f"""SELECT
                    br.run_id,
                    br.slm_service_id,
                    ss.name as slm_name,
                    ss.type as slm_type,
                    brun.name as run_name,
                    COUNT(*) as test_count,
                    AVG(br.precision_score) as avg_precision,
                    AVG(br.recall_score) as avg_recall,
                    AVG(br.f1_score) as avg_f1,
                    AVG(br.match_rate) as avg_match_rate,
                    AVG(br.processing_time_ms) as avg_time_ms,
                    MIN(br.f1_score) as min_f1,
                    MAX(br.f1_score) as max_f1
                FROM benchmark_results br
                JOIN slm_services ss ON br.slm_service_id = ss.id
                JOIN benchmark_runs brun ON br.run_id = brun.id
                WHERE br.run_id IN ({placeholders})
                GROUP BY br.run_id, br.slm_service_id
                ORDER BY avg_f1 DESC""",
            run_ids,
        ).fetchall()
        conn.close()

        results = rows_to_list(rows)
        # 数値の丸め
        for r in results:
            for key in ["avg_precision", "avg_recall", "avg_f1", "avg_match_rate", "avg_time_ms", "min_f1", "max_f1"]:
                if r.get(key) is not None:
                    r[key] = round(r[key], 4)
        return results

    @staticmethod
    def delete_run(run_id):
        """ベンチマーク実行を削除"""
        conn = get_db()
        conn.execute("DELETE FROM benchmark_results WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM benchmark_runs WHERE id = ?", (run_id,))
        conn.commit()
        conn.close()
