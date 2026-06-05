"""터미널 퀴즈 실행: python cli.py"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from basic_study.quiz.grader import grade_with_feedback
from basic_study.quiz.storage import LocalJSONStorage

DATA_PATH = Path(__file__).parent / "data" / "questions.json"
MAX_QUESTIONS = 20


def load_questions():
    if not DATA_PATH.exists():
        print("questions.json이 없습니다. python parse_questions.py 를 먼저 실행하세요.")
        sys.exit(1)
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def pick_scope(questions):
    sections = sorted({q["source_file"].replace(".md", "") for q in questions})
    print("\n[범위 선택]")
    print("0. 전체")
    for i, s in enumerate(sections, 1):
        print(f"{i}. {s}")
    choice = input("번호 입력 (기본 0): ").strip() or "0"
    if choice == "0":
        return questions
    try:
        idx = int(choice) - 1
        sec = sections[idx]
        return [q for q in questions if q["source_file"].replace(".md", "") == sec]
    except (ValueError, IndexError):
        print("잘못된 입력. 전체로 진행합니다.")
        return questions


def sample_questions(pool):
    by_type = {}
    for q in pool:
        by_type.setdefault(q["type"], []).append(q)
    selected, seen = [], set()
    types = list(by_type.keys())
    while len(selected) < MAX_QUESTIONS and types:
        for t in types[:]:
            if len(selected) >= MAX_QUESTIONS:
                break
            candidates = [q for q in by_type[t] if q["id"] not in seen]
            if not candidates:
                types.remove(t)
                continue
            q = random.choice(candidates)
            selected.append(q)
            seen.add(q["id"])
    random.shuffle(selected)
    return selected[:MAX_QUESTIONS]


TYPE_LABELS = {
    "fill_blank": "[코드 빈칸]",
    "code_to_result": "[코드→결과]",
    "result_to_code": "[결과→코드]",
    "concept_mc": "[개념/용어]",
    "short_answer": "[단답형]",
}


def ask_question(q, num, total):
    print(f"\n{'='*50}")
    print(f"Q{num}/{total}  {TYPE_LABELS.get(q['type'], '')}")
    print(q["question"])
    options = q.get("options", [])
    if options:
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        ans = input("번호 입력: ").strip()
        try:
            return options[int(ans) - 1]
        except (ValueError, IndexError):
            return ans
    else:
        return input("답 입력: ").strip()


def main():
    storage = LocalJSONStorage()
    questions = load_questions()
    pool = pick_scope(questions)
    selected = sample_questions(pool)
    total = len(selected)

    print(f"\n총 {total}문제 시작!\n")
    score = 0

    for i, q in enumerate(selected, 1):
        user_answer = ask_question(q, i, total)
        feedback = grade_with_feedback(q, user_answer)
        if feedback["correct"]:
            print("✅ 정답!")
            score += 1
        else:
            print(f"❌ 오답. 정답: {feedback['correct_answer']}")
        if feedback.get("explanation"):
            show = input("해설 보기? (y/n, 기본 n): ").strip().lower()
            if show == "y":
                print(feedback["explanation"])

    print(f"\n{'='*50}")
    print(f"최종 점수: {score} / {total}")
    storage.save_session({"score": score, "total": total})
    print("기록 저장 완료.")


if __name__ == "__main__":
    main()
