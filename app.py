"""マスキング評価システム - メインアプリケーション (FastAPI)"""
import json
import os
import csv
import io
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from models.database import init_db, get_db, row_to_dict, rows_to_list
from services.slm_manager import SLMManager
from services.masking_engine import MaskingEngine
from services.benchmark_engine import BenchmarkEngine
import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="マスキング評価システム", description="SLM ベンチマーク評価", lifespan=lifespan)

# 静的ファイル配信
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# テンプレート
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


# ---- ページルーティング ----

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---- SLMサービス API ----

@app.get("/api/slm-services")
async def get_services():
    services = SLMManager.get_all_services()
    return services


@app.post("/api/slm-services", status_code=201)
async def create_service(request: Request):
    data = await request.json()
    service = SLMManager.create_service(data)
    return service


@app.get("/api/slm-services/{sid}")
async def get_service(sid: int):
    service = SLMManager.get_service(sid)
    if not service:
        return JSONResponse(content={"error": "サービスが見つかりません"}, status_code=404)
    return service


@app.put("/api/slm-services/{sid}")
async def update_service(sid: int, request: Request):
    data = await request.json()
    service = SLMManager.update_service(sid, data)
    if not service:
        return JSONResponse(content={"error": "サービスが見つかりません"}, status_code=404)
    return service


@app.delete("/api/slm-services/{sid}")
async def delete_service(sid: int):
    SLMManager.delete_service(sid)
    return {"success": True}


@app.post("/api/slm-services/{sid}/start")
async def start_service(sid: int):
    result = SLMManager.start_service(sid)
    return result


@app.post("/api/slm-services/{sid}/stop")
async def stop_service(sid: int):
    result = SLMManager.stop_service(sid)
    return result


@app.get("/api/slm-services/{sid}/status")
async def service_status(sid: int):
    service = SLMManager.get_service(sid)
    if not service:
        return JSONResponse(content={"error": "サービスが見つかりません"}, status_code=404)
    return {"id": sid, "status": service["status"]}


# ---- マスキングルール API ----

@app.get("/api/masking-rules")
async def get_rules():
    conn = get_db()
    rows = conn.execute("SELECT * FROM masking_rules ORDER BY priority DESC, id").fetchall()
    conn.close()
    return rows_to_list(rows)


@app.post("/api/masking-rules", status_code=201)
async def create_rule(request: Request):
    data = await request.json()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO masking_rules (category, pattern, replacement, description, is_active, priority) VALUES (?, ?, ?, ?, ?, ?)",
        (
            data.get("category", ""),
            data.get("pattern", ""),
            data.get("replacement", "***"),
            data.get("description", ""),
            1 if data.get("is_active", True) else 0,
            data.get("priority", 0),
        ),
    )
    conn.commit()
    rule_id = cursor.lastrowid
    rule = row_to_dict(conn.execute("SELECT * FROM masking_rules WHERE id = ?", (rule_id,)).fetchone())
    conn.close()
    return rule


@app.put("/api/masking-rules/{rid}")
async def update_rule(rid: int, request: Request):
    data = await request.json()
    conn = get_db()
    conn.execute(
        "UPDATE masking_rules SET category=?, pattern=?, replacement=?, description=?, is_active=?, priority=? WHERE id=?",
        (
            data.get("category", ""),
            data.get("pattern", ""),
            data.get("replacement", "***"),
            data.get("description", ""),
            1 if data.get("is_active", True) else 0,
            data.get("priority", 0),
            rid,
        ),
    )
    conn.commit()
    rule = row_to_dict(conn.execute("SELECT * FROM masking_rules WHERE id = ?", (rid,)).fetchone())
    conn.close()
    return rule


@app.delete("/api/masking-rules/{rid}")
async def delete_rule(rid: int):
    conn = get_db()
    conn.execute("DELETE FROM masking_rules WHERE id = ?", (rid,))
    conn.commit()
    conn.close()
    return {"success": True}


# ---- テストデータ API ----

@app.get("/api/test-data")
async def get_test_data():
    conn = get_db()
    rows = conn.execute("SELECT * FROM test_data ORDER BY created_at DESC").fetchall()
    conn.close()
    return rows_to_list(rows)


@app.post("/api/test-data", status_code=201)
async def create_test_data(request: Request):
    data = await request.json()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO test_data (title, original_text, expected_masked_text, metadata_json) VALUES (?, ?, ?, ?)",
        (
            data.get("title", ""),
            data.get("original_text", ""),
            data.get("expected_masked_text", ""),
            json.dumps(data.get("metadata", {}), ensure_ascii=False),
        ),
    )
    conn.commit()
    td_id = cursor.lastrowid
    td = row_to_dict(conn.execute("SELECT * FROM test_data WHERE id = ?", (td_id,)).fetchone())
    conn.close()
    return td


@app.put("/api/test-data/{tid}")
async def update_test_data(tid: int, request: Request):
    data = await request.json()
    conn = get_db()
    conn.execute(
        "UPDATE test_data SET title=?, original_text=?, expected_masked_text=?, metadata_json=? WHERE id=?",
        (
            data.get("title", ""),
            data.get("original_text", ""),
            data.get("expected_masked_text", ""),
            json.dumps(data.get("metadata", {}), ensure_ascii=False),
            tid,
        ),
    )
    conn.commit()
    td = row_to_dict(conn.execute("SELECT * FROM test_data WHERE id = ?", (tid,)).fetchone())
    conn.close()
    return td


@app.delete("/api/test-data/{tid}")
async def delete_test_data(tid: int):
    conn = get_db()
    conn.execute("DELETE FROM test_data WHERE id = ?", (tid,))
    conn.commit()
    conn.close()
    return {"success": True}


@app.post("/api/test-data/import")
async def import_test_data(request: Request):
    """テストデータの一括インポート（JSON配列）"""
    data = await request.json()
    items = data if isinstance(data, list) else data.get("items", [])
    conn = get_db()
    count = 0
    for item in items:
        conn.execute(
            "INSERT INTO test_data (title, original_text, expected_masked_text) VALUES (?, ?, ?)",
            (item.get("title", f"データ{count+1}"), item.get("original_text", ""), item.get("expected_masked_text", "")),
        )
        count += 1
    conn.commit()
    conn.close()
    return {"success": True, "imported": count}


@app.post("/api/test-data/upload")
async def upload_test_data(file: UploadFile = File(...)):
    """CSV/JSONファイルアップロードでテストデータをインポート"""
    filename = file.filename.lower()
    count = 0
    conn = get_db()

    try:
        raw = await file.read()
        content = raw.decode("utf-8-sig")

        if filename.endswith(".json"):
            items = json.loads(content)
            if isinstance(items, dict):
                items = items.get("items", items.get("data", [items]))
            if not isinstance(items, list):
                items = [items]
            for item in items:
                title = item.get("title", item.get("タイトル", f"データ{count+1}"))
                text = item.get("original_text", item.get("text", item.get("テキスト", "")))
                expected = item.get("expected_masked_text", item.get("expected", item.get("期待結果", "")))
                if text:
                    conn.execute(
                        "INSERT INTO test_data (title, original_text, expected_masked_text) VALUES (?, ?, ?)",
                        (title, text, expected),
                    )
                    count += 1

        elif filename.endswith(".csv"):
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                title = row.get("title", row.get("タイトル", f"データ{count+1}"))
                text = row.get("original_text", row.get("text", row.get("テキスト", "")))
                expected = row.get("expected_masked_text", row.get("expected", row.get("期待結果", "")))
                if text:
                    conn.execute(
                        "INSERT INTO test_data (title, original_text, expected_masked_text) VALUES (?, ?, ?)",
                        (title, text, expected),
                    )
                    count += 1

        elif filename.endswith(".txt"):
            title = os.path.splitext(file.filename)[0]
            if content.strip():
                conn.execute(
                    "INSERT INTO test_data (title, original_text) VALUES (?, ?)",
                    (title, content.strip()),
                )
                count = 1
        else:
            conn.close()
            return JSONResponse(content={"error": "対応形式: .json, .csv, .txt"}, status_code=400)

        conn.commit()
    except Exception as e:
        conn.close()
        return JSONResponse(content={"error": f"ファイル解析エラー: {str(e)}"}, status_code=400)

    conn.close()
    return {"success": True, "imported": count, "filename": file.filename}


@app.post("/api/test-data/import-folder")
async def import_folder(request: Request):
    """サーバー上のフォルダパスからテストデータを一括インポート"""
    data = await request.json()
    folder_path = data.get("folder_path", "")

    if not folder_path or not os.path.isdir(folder_path):
        return JSONResponse(content={"error": "有効なフォルダパスを指定してください"}, status_code=400)

    conn = get_db()
    count = 0
    errors = []

    for fname in sorted(os.listdir(folder_path)):
        fpath = os.path.join(folder_path, fname)
        if not os.path.isfile(fpath):
            continue

        try:
            lower = fname.lower()
            if lower.endswith(".json"):
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    items = json.load(f)
                if isinstance(items, dict):
                    items = items.get("items", items.get("data", [items]))
                if not isinstance(items, list):
                    items = [items]
                for item in items:
                    title = item.get("title", item.get("タイトル", os.path.splitext(fname)[0]))
                    text = item.get("original_text", item.get("text", item.get("テキスト", "")))
                    expected = item.get("expected_masked_text", item.get("expected", item.get("期待結果", "")))
                    if text:
                        conn.execute(
                            "INSERT INTO test_data (title, original_text, expected_masked_text) VALUES (?, ?, ?)",
                            (title, text, expected),
                        )
                        count += 1

            elif lower.endswith(".csv"):
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        title = row.get("title", row.get("タイトル", os.path.splitext(fname)[0]))
                        text = row.get("original_text", row.get("text", row.get("テキスト", "")))
                        expected = row.get("expected_masked_text", row.get("expected", row.get("期待結果", "")))
                        if text:
                            conn.execute(
                                "INSERT INTO test_data (title, original_text, expected_masked_text) VALUES (?, ?, ?)",
                                (title, text, expected),
                            )
                            count += 1

            elif lower.endswith(".txt"):
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    file_content = f.read().strip()
                if file_content:
                    conn.execute(
                        "INSERT INTO test_data (title, original_text) VALUES (?, ?)",
                        (os.path.splitext(fname)[0], file_content),
                    )
                    count += 1
        except Exception as e:
            errors.append(f"{fname}: {str(e)}")

    conn.commit()
    conn.close()
    result = {"success": True, "imported": count, "folder": folder_path}
    if errors:
        result["errors"] = errors
    return result


@app.get("/api/test-data/stats")
async def test_data_stats():
    """テストデータの統計情報"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM test_data").fetchall()
    conn.close()

    data_list = rows_to_list(rows)
    total = len(data_list)
    if total == 0:
        return {"total": 0}

    lengths = [len(d["original_text"]) for d in data_list]
    with_expected = sum(1 for d in data_list if d.get("expected_masked_text"))

    # 文字数分布（ヒストグラム用）
    bins = [0, 50, 100, 200, 500, 1000, 2000, 5000, float("inf")]
    bin_labels = ["~50", "51-100", "101-200", "201-500", "501-1000", "1001-2000", "2001-5000", "5001~"]
    distribution = [0] * (len(bins) - 1)
    for l in lengths:
        for i in range(len(bins) - 1):
            if bins[i] <= l < bins[i + 1]:
                distribution[i] += 1
                break

    return {
        "total": total,
        "with_expected": with_expected,
        "without_expected": total - with_expected,
        "avg_length": round(sum(lengths) / total, 1),
        "min_length": min(lengths),
        "max_length": max(lengths),
        "total_chars": sum(lengths),
        "length_distribution": {"labels": bin_labels, "values": distribution},
    }


@app.post("/api/test-data/delete-all")
async def delete_all_test_data():
    """全テストデータを削除"""
    conn = get_db()
    conn.execute("DELETE FROM test_data")
    conn.commit()
    conn.close()
    return {"success": True}


# ---- ベンチマーク API ----

@app.get("/api/benchmark/runs")
async def get_benchmark_runs():
    runs = BenchmarkEngine.get_all_runs()
    return runs


@app.get("/api/benchmark/runs/{run_id}")
async def get_benchmark_run(run_id: int):
    run = BenchmarkEngine.get_run(run_id)
    if not run:
        return JSONResponse(content={"error": "ベンチマークが見つかりません"}, status_code=404)
    return run


@app.post("/api/benchmark/run")
async def start_benchmark(request: Request):
    data = await request.json()
    name = data.get("name", "ベンチマーク実行")
    description = data.get("description", "")
    slm_ids = data.get("slm_service_ids", [])
    test_ids = data.get("test_data_ids", [])

    if not slm_ids:
        return JSONResponse(content={"error": "SLMサービスを選択してください"}, status_code=400)
    if not test_ids:
        return JSONResponse(content={"error": "テストデータを選択してください"}, status_code=400)

    run_id = BenchmarkEngine.create_run(name, description, slm_ids, test_ids)
    result = BenchmarkEngine.start_run(run_id)
    return result


@app.post("/api/benchmark/compare")
async def compare_benchmarks(request: Request):
    data = await request.json()
    run_ids = data.get("run_ids", [])
    if not run_ids:
        return JSONResponse(content={"error": "比較するベンチマークを選択してください"}, status_code=400)
    results = BenchmarkEngine.get_comparison(run_ids)
    return results


@app.delete("/api/benchmark/runs/{run_id}")
async def delete_benchmark_run(run_id: int):
    BenchmarkEngine.delete_run(run_id)
    return {"success": True}


# ---- リファレンス結果 API ----

@app.post("/api/reference/upload")
async def upload_reference(request: Request):
    """リファレンス結果アップロード (Gemini/Claude)"""
    data = await request.json()
    model_name = data.get("model_name", "")
    results = data.get("results", [])

    conn = get_db()
    count = 0
    for item in results:
        test_data_id = item.get("test_data_id")
        masked_text = item.get("masked_text", "")
        if test_data_id and masked_text:
            conn.execute(
                "INSERT INTO reference_results (test_data_id, model_name, masked_text) VALUES (?, ?, ?)",
                (test_data_id, model_name, masked_text),
            )
            count += 1
    conn.commit()
    conn.close()
    return {"success": True, "uploaded": count}


@app.get("/api/reference")
async def get_references():
    conn = get_db()
    rows = conn.execute(
        """SELECT rr.*, td.title as test_title
           FROM reference_results rr
           JOIN test_data td ON rr.test_data_id = td.id
           ORDER BY rr.model_name, rr.test_data_id"""
    ).fetchall()
    conn.close()
    return rows_to_list(rows)


@app.delete("/api/reference/{rid}")
async def delete_reference(rid: int):
    conn = get_db()
    conn.execute("DELETE FROM reference_results WHERE id = ?", (rid,))
    conn.commit()
    conn.close()
    return {"success": True}


@app.post("/api/benchmark/detail-compare")
async def detail_compare(request: Request):
    """詳細比較: テストデータ毎に元テキスト・各SLMの結果・リファレンス結果を返す"""
    data = await request.json()
    run_ids = data.get("run_ids", [])
    if not run_ids:
        return JSONResponse(content={"error": "run_idsを指定してください"}, status_code=400)

    conn = get_db()
    placeholders = ",".join("?" * len(run_ids))

    # 対象のベンチマーク結果を全取得
    results = rows_to_list(conn.execute(
        f"""SELECT br.*, ss.name as slm_name, ss.type as slm_type,
                   td.title as test_title, td.original_text, td.expected_masked_text
            FROM benchmark_results br
            JOIN slm_services ss ON br.slm_service_id = ss.id
            JOIN test_data td ON br.test_data_id = td.id
            WHERE br.run_id IN ({placeholders})
            ORDER BY br.test_data_id, br.slm_service_id""",
        run_ids
    ).fetchall())

    # リファレンス結果を取得
    test_ids = list(set(r["test_data_id"] for r in results))
    refs = {}
    if test_ids:
        ref_placeholders = ",".join("?" * len(test_ids))
        ref_rows = rows_to_list(conn.execute(
            f"""SELECT * FROM reference_results
                WHERE test_data_id IN ({ref_placeholders})
                ORDER BY created_at DESC""",
            test_ids
        ).fetchall())
        for ref in ref_rows:
            tid = ref["test_data_id"]
            if tid not in refs:
                refs[tid] = []
            refs[tid].append({
                "model_name": ref["model_name"],
                "masked_text": ref["masked_text"],
                "created_at": ref["created_at"]
            })

    conn.close()

    # テストデータ毎にグルーピング
    grouped = {}
    for r in results:
        tid = r["test_data_id"]
        if tid not in grouped:
            grouped[tid] = {
                "test_data_id": tid,
                "title": r["test_title"],
                "original_text": r["original_text"],
                "expected_masked_text": r.get("expected_masked_text", ""),
                "slm_results": [],
                "reference_results": refs.get(tid, [])
            }
        grouped[tid]["slm_results"].append({
            "slm_name": r["slm_name"],
            "slm_type": r["slm_type"],
            "masked_text": r["masked_text"],
            "precision": r.get("precision_score"),
            "recall": r.get("recall_score"),
            "f1": r.get("f1_score"),
            "match_rate": r.get("match_rate"),
            "processing_time_ms": r.get("processing_time_ms"),
            "run_id": r["run_id"]
        })

    return list(grouped.values())


# ---- SLMタイプ定義 ----

@app.get("/api/slm-types")
async def get_slm_types():
    return config.SLM_TYPES


# ---- 単体マスキングテスト ----

@app.post("/api/masking/test")
async def test_masking(request: Request):
    """単体マスキングテスト"""
    data = await request.json()
    slm_id = data.get("slm_service_id")
    text = data.get("text", "")

    if not slm_id or not text:
        return JSONResponse(content={"error": "SLMサービスIDとテキストを指定してください"}, status_code=400)

    service = SLMManager.get_service(slm_id)
    if not service:
        return JSONResponse(content={"error": "サービスが見つかりません"}, status_code=404)

    start = time.time()
    result = MaskingEngine.execute_masking(None, service, text)
    elapsed = (time.time() - start) * 1000

    if result["success"]:
        return {
            "success": True,
            "masked_text": result["masked_text"],
            "processing_time_ms": round(elapsed, 2),
        }
    return JSONResponse(content=result, status_code=500)


if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run("app:app", host=config.HOST, port=config.PORT, reload=True)
