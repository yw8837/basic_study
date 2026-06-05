import json
import random
from pathlib import Path

import streamlit as st

from basic_study.quiz.grader import grade_with_feedback
from basic_study.quiz.storage import LocalJSONStorage

DATA_PATH = Path(__file__).parent / "data" / "questions.json"
STORAGE = LocalJSONStorage()
MAX_QUESTIONS = 20

st.set_page_config(page_title="Basic Study 퀴즈", page_icon="📚", layout="centered")

TYPE_LABELS = {
    "fill_blank": "코드 빈칸",
    "code_to_result": "코드→결과",
    "result_to_code": "결과→코드",
    "concept_mc": "개념 OX/MC",
    "short_answer": "단답형",
}


@st.cache_data
def load_questions():
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_sections(questions):
    sections = sorted({q["source_file"].replace(".md", "") for q in questions})
    return sections


def sample_questions(questions, scope, section=None):
    pool = questions if scope == "전체" else [q for q in questions if q["source_file"].replace(".md", "") == section]
    if not pool:
        return []
    by_type = {}
    for q in pool:
        by_type.setdefault(q["type"], []).append(q)
    types = list(by_type.keys())
    selected = []
    seen_ids = set()
    while len(selected) < MAX_QUESTIONS and types:
        for t in types[:]:
            if len(selected) >= MAX_QUESTIONS:
                break
            candidates = [q for q in by_type[t] if q["id"] not in seen_ids]
            if not candidates:
                types.remove(t)
                continue
            q = random.choice(candidates)
            selected.append(q)
            seen_ids.add(q["id"])
    random.shuffle(selected)
    return selected[:MAX_QUESTIONS]


def init_state(questions):
    st.session_state.questions = questions
    st.session_state.idx = 0
    st.session_state.score = 0
    st.session_state.answers = []
    st.session_state.phase = "quiz"
    st.session_state.feedback = None
    st.session_state.input_key = 0


def render_progress(idx, total):
    st.progress(idx / total, text=f"{idx} / {total} 문제")


def render_question(q, idx, instant_feedback, input_key):
    label = TYPE_LABELS.get(q["type"], q["type"])
    st.markdown(f"`{label}`")
    st.markdown(q["question"])

    user_answer = None
    submitted = False

    if q["type"] in ("fill_blank", "code_to_result", "result_to_code", "concept_mc"):
        options = q.get("options", [])
        if options:
            choice = st.radio("보기", options, key=f"radio_{input_key}_{idx}", index=None)
            if st.button("제출", key=f"btn_{input_key}_{idx}"):
                user_answer = choice
                submitted = True
    else:
        user_input = st.text_input("답 입력:", key=f"text_{input_key}_{idx}")
        if st.button("제출", key=f"btn_{input_key}_{idx}"):
            user_answer = user_input
            submitted = True

    return user_answer, submitted


def render_feedback(feedback, instant_feedback):
    if not instant_feedback:
        return
    if feedback["correct"]:
        st.success("✅ 정답!")
    else:
        st.error(f"❌ 오답. 정답: `{feedback['correct_answer']}`")
    if feedback.get("explanation"):
        with st.expander("해설 보기"):
            st.markdown(feedback["explanation"])


def render_result(questions, answers, score):
    st.title("🎉 퀴즈 완료!")
    st.metric("점수", f"{score} / {len(questions)}")
    st.divider()
    wrong = [(q, a) for (q, a) in zip(questions, answers) if not a["correct"]]
    if wrong:
        st.subheader(f"틀린 문제 ({len(wrong)}개)")
        for q, a in wrong:
            with st.expander(q["question"][:60] + "..."):
                st.markdown(f"**내 답:** `{a['user_answer']}`")
                st.markdown(f"**정답:** `{a['correct_answer']}`")
                if a.get("explanation"):
                    st.markdown(a["explanation"])
    if st.button("다시 하기"):
        for key in ["questions", "idx", "score", "answers", "phase", "feedback", "input_key"]:
            st.session_state.pop(key, None)
        st.rerun()


def main():
    all_questions = load_questions()
    sections = get_sections(all_questions)

    with st.sidebar:
        st.title("📚 Basic Study")
        st.divider()
        scope = st.radio("범위", ["전체", "섹션 선택"])
        section = None
        if scope == "섹션 선택":
            section = st.selectbox("수업/파일 선택", sections)
        instant_feedback = st.toggle("즉시 해설", value=True)
        st.divider()
        if st.button("🚀 퀴즈 시작", use_container_width=True):
            qs = sample_questions(all_questions, scope, section)
            if not qs:
                st.error("선택 범위에 문제가 없습니다.")
            else:
                init_state(qs)
                st.rerun()

    if "phase" not in st.session_state:
        st.title("📚 Basic Study 복습 퀴즈")
        st.write("왼쪽 사이드바에서 범위를 선택하고 퀴즈를 시작하세요.")
        if all_questions:
            st.info(f"문제은행: 총 {len(all_questions)}개 문제")
        else:
            st.warning("questions.json이 없습니다. `python parse_questions.py`를 먼저 실행하세요.")
        return

    if st.session_state.phase == "result":
        render_result(
            st.session_state.questions,
            st.session_state.answers,
            st.session_state.score,
        )
        return

    questions = st.session_state.questions
    idx = st.session_state.idx
    total = len(questions)

    if idx >= total:
        STORAGE.save_session({"score": st.session_state.score, "total": total})
        st.session_state.phase = "result"
        st.rerun()

    render_progress(idx, total)
    q = questions[idx]

    if st.session_state.feedback is None:
        user_answer, submitted = render_question(
            q, idx, instant_feedback, st.session_state.get("input_key", 0)
        )
        if submitted and user_answer is None:
            st.warning("보기를 선택해주세요.")
        elif submitted:
            feedback = grade_with_feedback(q, user_answer)
            st.session_state.feedback = feedback
            st.rerun()
    else:
        feedback = st.session_state.feedback
        st.markdown(q["question"])
        render_feedback(feedback, instant_feedback)

        if feedback["correct"]:
            st.session_state.score += 1
        else:
            STORAGE.save_wrong(q["id"], q)

        if instant_feedback:
            if st.button("다음 →"):
                st.session_state.answers.append(feedback)
                st.session_state.idx += 1
                st.session_state.feedback = None
                st.session_state.input_key = st.session_state.get("input_key", 0) + 1
                st.rerun()
        else:
            st.session_state.answers.append(feedback)
            st.session_state.idx += 1
            st.session_state.feedback = None
            st.session_state.input_key = st.session_state.get("input_key", 0) + 1
            st.rerun()


if __name__ == "__main__":
    main()
