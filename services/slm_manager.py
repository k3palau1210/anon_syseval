"""SLMサービス管理モジュール - 起動/停止/ステータス管理"""
import subprocess
import requests
import time
import json
from models.database import get_db, row_to_dict, rows_to_list


class SLMManager:
    """SLMサービスの管理クラス"""

    # 実行中のローカルプロセスを管理
    _processes = {}

    @staticmethod
    def get_all_services():
        """全サービス取得"""
        conn = get_db()
        rows = conn.execute("SELECT * FROM slm_services ORDER BY created_at DESC").fetchall()
        conn.close()
        services = rows_to_list(rows)
        # リアルタイムステータスを更新
        for svc in services:
            svc["status"] = SLMManager.check_status(svc)
        return services

    @staticmethod
    def get_service(service_id):
        """サービス取得"""
        conn = get_db()
        row = conn.execute("SELECT * FROM slm_services WHERE id = ?", (service_id,)).fetchone()
        conn.close()
        if row:
            svc = row_to_dict(row)
            svc["status"] = SLMManager.check_status(svc)
            return svc
        return None

    @staticmethod
    def create_service(data):
        """サービス作成"""
        conn = get_db()
        cursor = conn.execute(
            """INSERT INTO slm_services (name, type, model_name, endpoint, api_key, config_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                data.get("name", ""),
                data.get("type", "local"),
                data.get("model_name", ""),
                data.get("endpoint", ""),
                data.get("api_key", ""),
                json.dumps(data.get("config", {}), ensure_ascii=False),
            ),
        )
        conn.commit()
        service_id = cursor.lastrowid
        conn.close()
        return SLMManager.get_service(service_id)

    @staticmethod
    def update_service(service_id, data):
        """サービス更新"""
        conn = get_db()
        conn.execute(
            """UPDATE slm_services
               SET name=?, type=?, model_name=?, endpoint=?, api_key=?, config_json=?,
                   updated_at=datetime('now','localtime')
               WHERE id=?""",
            (
                data.get("name", ""),
                data.get("type", "local"),
                data.get("model_name", ""),
                data.get("endpoint", ""),
                data.get("api_key", ""),
                json.dumps(data.get("config", {}), ensure_ascii=False),
                service_id,
            ),
        )
        conn.commit()
        conn.close()
        return SLMManager.get_service(service_id)

    @staticmethod
    def delete_service(service_id):
        """サービス削除"""
        SLMManager.stop_service(service_id)
        conn = get_db()
        conn.execute("DELETE FROM slm_services WHERE id = ?", (service_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def check_status(service):
        """サービスのステータスをリアルタイムで確認"""
        svc_type = service.get("type", "")
        endpoint = service.get("endpoint", "")
        service_id = service.get("id")

        if svc_type == "reference":
            return "stopped"

        # ローカルプロセスの確認
        if svc_type == "local" and service_id in SLMManager._processes:
            proc = SLMManager._processes[service_id]
            if proc.poll() is None:
                # プロセスはまだ実行中、エンドポイントも確認
                if endpoint:
                    try:
                        resp = requests.get(endpoint, timeout=2)
                        if resp.status_code == 200:
                            return "running"
                    except Exception:
                        return "running"  # プロセスは生きているがAPIはまだ準備中かも
                return "running"
            else:
                del SLMManager._processes[service_id]
                return "stopped"

        # API/リモートのヘルスチェック
        if endpoint and svc_type in ("api", "remote", "local"):
            try:
                # Ollamaの場合
                health_url = endpoint.rstrip("/")
                if "/api" in health_url:
                    health_url = health_url.rsplit("/api", 1)[0]
                resp = requests.get(health_url, timeout=3)
                if resp.status_code == 200:
                    return "running"
                return "error"
            except requests.exceptions.ConnectionError:
                return "stopped"
            except Exception:
                return "unknown"

        return "stopped"

    @staticmethod
    def start_service(service_id):
        """サービス起動"""
        service = SLMManager.get_service(service_id)
        if not service:
            return {"success": False, "message": "サービスが見つかりません"}

        svc_type = service["type"]

        if svc_type == "local":
            return SLMManager._start_local(service)
        elif svc_type == "api":
            # APIは常時接続可能前提、ヘルスチェックのみ
            status = SLMManager.check_status(service)
            if status == "running":
                return {"success": True, "message": "API接続確認済み"}
            return {"success": False, "message": "APIに接続できません。エンドポイントを確認してください。"}
        elif svc_type == "remote":
            return SLMManager._start_remote(service)
        elif svc_type == "reference":
            return {"success": True, "message": "リファレンスモデルは起動不要です"}

        return {"success": False, "message": "不明なサービスタイプ"}

    @staticmethod
    def stop_service(service_id):
        """サービス停止"""
        service = SLMManager.get_service(service_id)
        if not service:
            return {"success": False, "message": "サービスが見つかりません"}

        svc_type = service["type"]

        if svc_type == "local":
            return SLMManager._stop_local(service)
        elif svc_type == "remote":
            return SLMManager._stop_remote(service)

        return {"success": True, "message": "停止しました"}

    @staticmethod
    def _start_local(service):
        """ローカルSLM起動（Ollama等）"""
        config_data = json.loads(service.get("config_json", "{}"))
        cmd = config_data.get("start_command", "ollama serve")

        try:
            proc = subprocess.Popen(
                cmd.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            SLMManager._processes[service["id"]] = proc
            time.sleep(2)  # 起動待ち

            if proc.poll() is not None:
                stderr = proc.stderr.read().decode("utf-8", errors="replace")
                # "address already in use" は既に起動中
                if "address already in use" in stderr.lower() or "bind" in stderr.lower():
                    return {"success": True, "message": "既に起動中です"}
                return {"success": False, "message": f"起動失敗: {stderr[:200]}"}

            # DB更新
            conn = get_db()
            conn.execute(
                "UPDATE slm_services SET status='running', updated_at=datetime('now','localtime') WHERE id=?",
                (service["id"],),
            )
            conn.commit()
            conn.close()

            return {"success": True, "message": "起動しました"}
        except FileNotFoundError:
            return {"success": False, "message": f"コマンドが見つかりません: {cmd}"}
        except Exception as e:
            return {"success": False, "message": f"起動エラー: {str(e)}"}

    @staticmethod
    def _stop_local(service):
        """ローカルSLM停止"""
        service_id = service["id"]
        if service_id in SLMManager._processes:
            proc = SLMManager._processes[service_id]
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            del SLMManager._processes[service_id]

        conn = get_db()
        conn.execute(
            "UPDATE slm_services SET status='stopped', updated_at=datetime('now','localtime') WHERE id=?",
            (service_id,),
        )
        conn.commit()
        conn.close()
        return {"success": True, "message": "停止しました"}

    @staticmethod
    def _start_remote(service):
        """リモートSLM起動（Mac mini等）"""
        config_data = json.loads(service.get("config_json", "{}"))
        start_url = config_data.get("start_url", "")

        if start_url:
            try:
                resp = requests.post(start_url, timeout=10)
                if resp.status_code == 200:
                    return {"success": True, "message": "リモートサービスを起動しました"}
                return {"success": False, "message": f"起動失敗: HTTP {resp.status_code}"}
            except Exception as e:
                return {"success": False, "message": f"接続エラー: {str(e)}"}

        # start_urlがない場合はヘルスチェックのみ
        status = SLMManager.check_status(service)
        if status == "running":
            return {"success": True, "message": "リモートサービスは稼働中です"}
        return {"success": False, "message": "リモートサービスに接続できません"}

    @staticmethod
    def _stop_remote(service):
        """リモートSLM停止"""
        config_data = json.loads(service.get("config_json", "{}"))
        stop_url = config_data.get("stop_url", "")

        if stop_url:
            try:
                resp = requests.post(stop_url, timeout=10)
                if resp.status_code == 200:
                    return {"success": True, "message": "リモートサービスを停止しました"}
            except Exception:
                pass

        return {"success": True, "message": "停止リクエストを送信しました"}

    @staticmethod
    def send_request(service, prompt, timeout=120):
        """SLMにリクエストを送信"""
        svc_type = service["type"]
        endpoint = service.get("endpoint", "").rstrip("/")
        model_name = service.get("model_name", "")
        api_key = service.get("api_key", "")
        config_data = json.loads(service.get("config_json", "{}"))

        if svc_type == "reference":
            return {"success": False, "message": "リファレンスモデルには直接リクエストできません"}

        if svc_type == "local":
            # Ollama API
            url = f"{endpoint}/api/generate" if "/api" not in endpoint else endpoint
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": config_data.get("options", {}),
            }
            try:
                resp = requests.post(url, json=payload, timeout=timeout)
                data = resp.json()
                return {"success": True, "response": data.get("response", ""), "raw": data}
            except Exception as e:
                return {"success": False, "message": str(e)}

        elif svc_type == "api":
            # OpenAI互換 API
            url = f"{endpoint}/chat/completions" if "/chat" not in endpoint else endpoint
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": config_data.get("temperature", 0.0),
                "max_tokens": config_data.get("max_tokens", 4096),
            }
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {"success": True, "response": content, "raw": data}
            except Exception as e:
                return {"success": False, "message": str(e)}

        elif svc_type == "remote":
            # リモート - Ollama互換想定
            url = f"{endpoint}/api/generate" if "/api" not in endpoint else endpoint
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": config_data.get("options", {}),
            }
            try:
                resp = requests.post(url, json=payload, timeout=timeout)
                data = resp.json()
                return {"success": True, "response": data.get("response", ""), "raw": data}
            except Exception as e:
                return {"success": False, "message": str(e)}

        return {"success": False, "message": "不明なサービスタイプ"}
