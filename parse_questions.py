"""md 원문 파싱 → data/questions.json 생성. 새 수업 추가 후 실행."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from basic_study.parser.extractor import parse_all

CONTENT_DIR = Path(r"C:\Users\최용우\yearstudy_6\content\posts")
OUTPUT = Path(__file__).parent / "data" / "questions.json"


if __name__ == "__main__":
    print(f"파싱 중: {CONTENT_DIR}")
    stats = parse_all(CONTENT_DIR, OUTPUT)
    print(f"\n완료! 총 {stats['total']}개 문제 → {OUTPUT}")
    print("유형별:")
    for t, n in stats["by_type"].items():
        print(f"  {t}: {n}개")
