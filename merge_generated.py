"""data/generated/*.json (LLM 생성 문제) 병합 → data/questions.json.

각 문제에 id 부여(중복 제거), options/grading 기본값 보정.
"""
import json
import hashlib
from pathlib import Path

GEN_DIR = Path(__file__).parent / "data" / "generated"
OUTPUT = Path(__file__).parent / "data" / "questions.json"

CODE_TYPES = {"fill_blank", "code_to_result", "result_to_code"}


def make_id(source_file: str, section: str, content: str) -> str:
    raw = f"{source_file}::{section}::{content[:60]}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def main():
    all_q = []
    seen = set()
    per_file = {}
    for f in sorted(GEN_DIR.glob("*.json")):
        try:
            data = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print(f"[경고] {f.name} 로드 실패: {e}")
            continue
        cnt = 0
        for q in data:
            q["id"] = make_id(q.get("source_file", ""), q.get("section", ""), q.get("question", ""))
            if q["id"] in seen:
                continue
            seen.add(q["id"])
            q.setdefault("options", [])
            # grading 기본값: 코드 유형은 code_strict, 그 외 lenient
            if not q.get("grading"):
                q["grading"] = "code_strict" if q.get("type") in CODE_TYPES else "lenient"
            all_q.append(q)
            cnt += 1
        per_file[f.stem] = cnt

    OUTPUT.parent.mkdir(exist_ok=True)
    json.dump(all_q, open(OUTPUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"병합 완료: 총 {len(all_q)}문제 → {OUTPUT}")
    print("파일별:")
    for name, cnt in per_file.items():
        print(f"  {name}: {cnt}")
    from collections import Counter
    print("유형별:", dict(Counter(q["type"] for q in all_q)))


if __name__ == "__main__":
    main()
