"""マスキング処理エンジン"""
import json
import re
from models.database import get_db, rows_to_list


class MaskingEngine:
    """SLMを使ったマスキング処理"""

    @staticmethod
    def get_active_rules():
        """アクティブなマスキングルールを取得"""
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM masking_rules WHERE is_active = 1 ORDER BY priority DESC, id"
        ).fetchall()
        conn.close()
        return rows_to_list(rows)

    @staticmethod
    def build_prompt(text, rules=None):
        """マスキング用プロンプトを構築"""
        if rules is None:
            rules = MaskingEngine.get_active_rules()

        categories = []
        for r in rules:
            cat = r["category"]
            desc = r.get("description", "")
            pattern = r.get("pattern", "")
            if pattern:
                categories.append(f"- {cat}: {desc}（パターン例: {pattern}）")
            else:
                categories.append(f"- {cat}: {desc}")

        rules_text = "\n".join(categories)

        prompt = f"""あなたはコールセンターの通話記録から個人情報をマスキングする専門家です。
以下のテキストに含まれる個人情報やセンシティブな情報をマスキングしてください。

## マスキング対象カテゴリ
{rules_text}

## マスキングルール
1. マスキング対象の情報を「[カテゴリ名]」の形式で置換してください。
   例: 田中太郎 → [氏名]、090-1234-5678 → [電話番号]
2. 文脈を維持しつつ、個人を特定できる情報をすべてマスキングしてください。
3. マスキング後のテキストのみを出力してください。余計な説明は不要です。

## 入力テキスト
{text}

## マスキング後のテキスト"""

        return prompt

    @staticmethod
    def execute_masking(slm_manager_instance, service, text, rules=None):
        """マスキングを実行"""
        from services.slm_manager import SLMManager

        prompt = MaskingEngine.build_prompt(text, rules)
        result = SLMManager.send_request(service, prompt)

        if result["success"]:
            masked = result["response"].strip()
            # 余計なプレフィックスを除去
            for prefix in ["マスキング後のテキスト:", "マスキング後のテキスト：", "## マスキング後のテキスト"]:
                if masked.startswith(prefix):
                    masked = masked[len(prefix):].strip()
            return {"success": True, "masked_text": masked}
        else:
            return {"success": False, "message": result.get("message", "マスキング処理に失敗しました")}

    @staticmethod
    def compare_results(masked_text, reference_text):
        """マスキング結果をリファレンスと比較"""
        if not reference_text:
            return {"match_rate": None, "precision": None, "recall": None, "f1": None, "details": {}}

        # マスキングされた箇所を抽出 [カテゴリ名] パターン
        mask_pattern = r'\[([^\]]+)\]'

        masked_items = set(
            (m.start(), m.group()) for m in re.finditer(mask_pattern, masked_text)
        )
        ref_items = set(
            (m.start(), m.group()) for m in re.finditer(mask_pattern, reference_text)
        )

        # 位置に依存しない比較（テキスト全体でのマスク数ベース）
        masked_tags = [m.group() for m in re.finditer(mask_pattern, masked_text)]
        ref_tags = [m.group() for m in re.finditer(mask_pattern, reference_text)]

        if not ref_tags:
            return {
                "match_rate": 1.0 if not masked_tags else 0.0,
                "precision": 1.0 if not masked_tags else 0.0,
                "recall": 1.0,
                "f1": 1.0 if not masked_tags else 0.0,
                "details": {"masked_count": len(masked_tags), "ref_count": 0},
            }

        # 簡易的なマッチング: 同じカテゴリのタグ数で比較
        from collections import Counter
        masked_counter = Counter(masked_tags)
        ref_counter = Counter(ref_tags)

        # True Positives: 両方にある最小数
        tp = sum((masked_counter & ref_counter).values())
        # False Positives: マスキングしたが不要
        fp = sum(masked_counter.values()) - tp
        # False Negatives: マスキングすべきだったが漏れ
        fn = sum(ref_counter.values()) - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        # 完全一致率
        match_rate = 1.0 if masked_text.strip() == reference_text.strip() else 0.0

        return {
            "match_rate": round(match_rate, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "details": {
                "masked_count": len(masked_tags),
                "ref_count": len(ref_tags),
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
            },
        }
