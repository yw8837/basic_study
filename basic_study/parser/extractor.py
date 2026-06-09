import re
import json
import hashlib
import random
from pathlib import Path

SECTION_CAP = 1  # 섹션·유형별 문제 생성 상한

LEARN_TOKENS = {
    "print", "len", "range", "type", "int", "str", "float", "list", "bool",
    "True", "False", "None", "if", "else", "elif", "for", "while", "def",
    "return", "import", "from", "class", "and", "or", "not", "in", "is",
    "append", "split", "join", "format", "input", "open", "sorted", "zip",
    "enumerate", "map", "filter", "dict", "set", "tuple", "pass", "break",
    "continue", "try", "except", "with", "as", "lambda", "yield", "global",
    "isinstance", "super", "self", "__init__", "index", "pop", "remove",
    "upper", "lower", "strip", "replace", "find", "count", "keys", "values",
    "items", "get", "update",
}

TYPE_VARIANTS = {
    "int": ["str", "float", "bool", "list"],
    "str": ["int", "float", "bool", "list"],
    "float": ["int", "str", "bool", "list"],
    "bool": ["int", "str", "float", "list"],
    "list": ["dict", "set", "tuple", "str"],
    "dict": ["list", "set", "tuple", "str"],
    "True": ["False", "None", "0", "[]"],
    "False": ["True", "None", "0", "[]"],
    "print": ["input", "len", "type", "str"],
    "append": ["extend", "insert", "add", "push"],
    "split": ["join", "strip", "replace", "find"],
}


def make_id(source_file: str, section: str, content: str) -> str:
    raw = f"{source_file}::{section}::{content[:60]}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].lstrip()
    return text


_EMOJI_RE = re.compile(
    "[\U00010000-\U0010ffff\U0001F300-\U0001F9FF\U00002600-\U000027BF]",
    flags=re.UNICODE,
)


def clean_text(text: str) -> str:
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^>.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[^\S\n]+", " ", text)
    return _EMOJI_RE.sub("", text).strip()


def extract_sections(text: str) -> list[dict]:
    text = strip_frontmatter(text)
    sections = []
    parts = re.split(r"^(#{1,3} .+)$", text, flags=re.MULTILINE)
    current_title = "intro"
    current_body = ""
    for part in parts:
        if re.match(r"^#{1,3} ", part):
            if current_body.strip():
                sections.append({"title": current_title, "body": current_body})
            current_title = re.sub(r"^#+\s*", "", part).strip()
            current_body = ""
        else:
            current_body += part
    if current_body.strip():
        sections.append({"title": current_title, "body": current_body})
    return sections


def extract_code_output_pairs(body: str) -> list[dict]:
    pairs = []
    pattern = re.compile(
        r"```python\n(.*?)```(?:\s*\n출력:\n```\n(.*?)```)?",
        re.DOTALL,
    )
    for m in pattern.finditer(body):
        code = m.group(1).strip()
        output = m.group(2).strip() if m.group(2) else None
        if code:
            pairs.append({"code": code, "output": output})
    return pairs


_DEICTIC_RE = re.compile(r"^(이를|이는|이게|이것|이건|그것|그게|위|아래|위의|아래의|여기|거기|해당|다음)\b")


def _is_complete_concept(s: str) -> bool:
    """맥락 없이 단독으로 이해되는 완결된 문장인지 검사."""
    # 앞에 지시어로 시작 → 앞 문장 없이는 의미 불명
    if _DEICTIC_RE.match(s):
        return False
    # 불완전 종결: 괄호 열림 / 콜론·쉼표·하이픈·예시 도입부로 끝남
    if re.search(r"[(\[:,\-]\s*$", s) or s.endswith("(ex") or s.endswith("예"):
        return False
    # 괄호 짝 안 맞음 → 문장 잘림
    if s.count("(") != s.count(")") or s.count("[") != s.count("]"):
        return False
    # 리스트 토막("- ____: ...")처럼 콜론으로 정의를 시작하다 만 형태
    if re.match(r"^[-*]\s", s) and ":" in s and s.rstrip().endswith(("(ex", "(예", ":")):
        return False
    # 표 잔재 / f-string·포맷 스펙 등 코드 조각이 섞인 문장 제외
    if "|" in s or re.search(r"[{}]|:>|:,|:\.\d|f['\"]", s):
        return False
    return True


_JOSA_PREFIX = re.compile(r"^(을|를|이|가|은|는|에|의|와|과|도|로|으로)\s")


def _extract_answer(concept: str) -> str | None:
    m = re.search(r"`([^`]{2,30})`", concept) or re.search(r"\*\*([^*]{2,30})\*\*", concept)
    return m.group(1) if m else None


def _good_answer(ans: str, max_words: int, max_len: int) -> bool:
    """정답으로 쓸 만한 용어인지 검사 (서술구·코드 조각·깨진 추출 배제)."""
    a = ans.strip()
    if a != ans:           # 앞뒤 공백 = 깨진 추출
        return False
    if not (2 <= len(a) <= max_len):
        return False
    if len(a.split()) > max_words:
        return False
    if any(ch in a for ch in "{}|→"):
        return False
    if _JOSA_PREFIX.match(a):  # 조사로 시작 = 문장 중간이 잘림
        return False
    return True


def _normalize_table_row(s: str) -> str | None:
    """마크다운 표 행(| 용어 | 설명 |)을 자연 문장으로 변환."""
    if not (s.startswith("|") and s.count("|") >= 2):
        return None
    cells = [c.strip() for c in s.strip().strip("|").split("|")]
    cells = [c for c in cells if c and not re.fullmatch(r"[-:\s]+", c)]  # 구분선 셀 제외
    if len(cells) < 2:
        return None
    term = next((c for c in cells if "`" in c or re.search(r"\*\*.+\*\*", c)), None)
    if not term:
        return None
    desc = " / ".join(c for c in cells if c != term)
    if len(desc) < 5:
        return None
    if re.search(r"[{}]|:>|:,|:\.\d|f['\"]", desc + term):  # 코드 조각 든 행은 제외
        return None
    return f"{desc} — 이것을 가리키는 용어는 {term}"


def extract_concepts(body: str) -> list[str]:
    cleaned = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    cleaned = clean_text(cleaned)
    sentences = re.split(r"[.。\n]{1,2}", cleaned)
    concepts = []
    for s in sentences:
        s = s.strip()
        table = _normalize_table_row(s)
        if table:
            concepts.append(table)
            continue
        if 10 < len(s) < 200 and ("`" in s or re.search(r"\*\*.+\*\*", s)):
            if _is_complete_concept(s):
                concepts.append(s)
    return concepts[:5]


def pick_blank_token(code: str) -> tuple[str, str] | None:
    tokens_found = []
    for token in LEARN_TOKENS:
        pattern = rf"\b{re.escape(token)}\b"
        if re.search(pattern, code):
            tokens_found.append(token)
    if not tokens_found:
        return None
    token = random.choice(tokens_found)
    blanked = re.sub(rf"\b{re.escape(token)}\b", "____", code, count=1)
    return token, blanked


def make_distractors(correct: str, pool: list[str], n: int = 3) -> list[str]:
    distractors = []
    # 의미상 관련된 변형(같은 자료형·역할군)을 오답으로 우선 사용
    if correct in TYPE_VARIANTS:
        for v in TYPE_VARIANTS[correct]:
            if v not in distractors and v != correct:
                distractors.append(v)
            if len(distractors) >= n:
                break
    for p in pool:
        if p != correct and p not in distractors:
            distractors.append(p)
        if len(distractors) >= n:
            break
    if len(distractors) < n:
        fallbacks = [t for t in LEARN_TOKENS if t != correct and t not in distractors]
        random.shuffle(fallbacks)
        distractors.extend(fallbacks[: n - len(distractors)])
    return distractors[:n]


def _code_without_comments(code: str) -> str:
    """주석 부분을 제거한 코드 반환 (토큰 후보 탐색용)."""
    lines = []
    for line in code.splitlines():
        idx = line.find("#")
        lines.append(line[:idx] if idx != -1 else line)
    return "\n".join(lines)


def gen_fill_blank(pair: dict, section: str, source_file: str, all_tokens: list[str]) -> list[dict]:
    questions = []
    code = pair["code"]
    code_only = _code_without_comments(code)
    tokens_in_code = [t for t in LEARN_TOKENS if re.search(rf"\b{re.escape(t)}\b", code_only)]
    used_tokens = set()
    for token in tokens_in_code:
        if token in used_tokens:
            continue
        # 주석 제외한 코드 부분에서만 첫 번째 토큰을 blank 처리
        lines = code.splitlines()
        blanked_lines = []
        replaced = False
        for line in lines:
            comment_idx = line.find("#")
            code_part = line[:comment_idx] if comment_idx != -1 else line
            comment_part = line[comment_idx:] if comment_idx != -1 else ""
            if not replaced and re.search(rf"\b{re.escape(token)}\b", code_part):
                new_code_part = re.sub(rf"\b{re.escape(token)}\b", "____", code_part, count=1)
                blanked_lines.append(new_code_part + comment_part)
                replaced = True
            else:
                blanked_lines.append(line)
        if not replaced:
            continue
        blanked = "\n".join(blanked_lines)
        distractors = make_distractors(token, [t for t in all_tokens if t != token])
        if len(distractors) < 3:
            continue
        options = [token] + distractors[:3]
        random.shuffle(options)
        questions.append({
            "id": make_id(source_file, section, blanked),
            "type": "fill_blank",
            "question": f"빈칸에 들어갈 알맞은 코드는?\n\n```python\n{blanked}\n```",
            "answer": token,
            "options": options,
            "grading": "code_strict",
            "source_file": source_file,
            "section": section,
            "explanation": f"정답: `{token}`\n\n원본 코드:\n```python\n{code}\n```",
        })
        used_tokens.add(token)
        if len(questions) >= 1:
            break
    return questions


def gen_code_to_result(pair: dict, section: str, source_file: str, other_outputs: list[str]) -> list[dict]:
    if not pair["output"]:
        return []
    code, output = pair["code"], pair["output"]
    if len(output) < 2:
        return []
    distractors = make_distractors(output, other_outputs)
    if len(distractors) < 3:
        return []
    options = [output] + distractors[:3]
    random.shuffle(options)
    return [{
        "id": make_id(source_file, section, code),
        "type": "code_to_result",
        "question": f"다음 코드를 실행하면 출력은?\n\n```python\n{code}\n```",
        "answer": output,
        "options": options,
        "grading": "code_strict",
        "source_file": source_file,
        "section": section,
        "explanation": f"출력 결과:\n```\n{output}\n```\n\n코드:\n```python\n{code}\n```",
    }]


def gen_result_to_code(pair: dict, section: str, source_file: str, other_codes: list[str]) -> list[dict]:
    if not pair["output"]:
        return []
    code, output = pair["code"], pair["output"]
    if len(code) < 5:
        return []
    distractors = [c for c in other_codes if c != code][:3]
    if len(distractors) < 3:
        return []
    options = [code] + distractors[:3]
    random.shuffle(options)
    return [{
        "id": make_id(source_file, section, output),
        "type": "result_to_code",
        "question": f"다음 출력을 만드는 코드는?\n\n```\n{output}\n```",
        "answer": code,
        "options": options,
        "grading": "code_strict",
        "source_file": source_file,
        "section": section,
        "explanation": f"정답 코드:\n```python\n{code}\n```",
    }]


def gen_concept_mc(concepts: list[str], section: str, source_file: str, other_concepts: list[str]) -> list[dict]:
    questions = []
    for concept in concepts[:3]:
        match = re.search(r"`([^`]{2,30})`", concept)
        if not match:
            match = re.search(r"\*\*([^*]{2,30})\*\*", concept)
        if not match:
            continue
        answer = match.group(1)
        if not _good_answer(answer, max_words=6, max_len=40):
            continue
        desc = re.sub(r"`[^`]+`", "____", concept, count=1)
        desc = re.sub(r"\*\*[^*]+\*\*", "____", desc, count=1)
        if clean_text(desc).lstrip("-*  ").startswith("____"):
            continue  # 빈칸이 맨 앞 → 맥락 없음
        other_answers = []
        for oc in other_concepts:
            m2 = re.search(r"`([^`]{2,30})`", oc) or re.search(r"\*\*([^*]{2,30})\*\*", oc)
            if m2 and m2.group(1) != answer:
                other_answers.append(m2.group(1))
        distractors = other_answers[:3]
        if len(distractors) < 2:
            continue
        while len(distractors) < 3:
            distractors.append(random.choice(list(LEARN_TOKENS)))
        options = [answer] + distractors[:3]
        random.shuffle(options)
        questions.append({
            "id": make_id(source_file, section, desc),
            "type": "concept_mc",
            "question": f"다음 설명에 해당하는 것은?\n\n{clean_text(desc)}",
            "answer": answer,
            "options": options,
            "grading": "lenient",
            "source_file": source_file,
            "section": section,
            "explanation": concept,
        })
    return questions


def gen_short_answer(concepts: list[str], section: str, source_file: str) -> list[dict]:
    questions = []
    for concept in concepts[:3]:
        match = re.search(r"`([^`]{2,30})`", concept) or re.search(r"\*\*([^*]{2,30})\*\*", concept)
        if not match:
            continue
        answer = match.group(1)
        if not _good_answer(answer, max_words=2, max_len=15):
            continue
        question_text = re.sub(r"`[^`]+`", "____", concept, count=1)
        question_text = re.sub(r"\*\*[^*]+\*\*", "____", question_text, count=1)
        if clean_text(question_text).lstrip("-*  ").startswith("____"):
            continue  # 빈칸이 맨 앞 → 맥락 없음
        questions.append({
            "id": make_id(source_file, section, f"sa::{concept[:40]}"),
            "type": "short_answer",
            "question": f"빈칸에 알맞은 용어/코드를 입력하세요:\n\n{clean_text(question_text)}",
            "answer": answer,
            "options": [],
            "grading": "lenient",
            "source_file": source_file,
            "section": section,
            "explanation": concept,
        })
    return questions


def extract_inline_output_pairs(body: str) -> list[dict]:
    """print(...)  # 결과 형태의 단일 라인 코드→결과 쌍 추출."""
    pairs = []
    for line in body.splitlines():
        line = line.strip()
        m = re.match(r"^(print\(.+?\))\s+#\s+(.+)$", line)
        if m:
            code = m.group(1)
            output = m.group(2).strip()
            if len(output) >= 3 and output not in ("소수점 없는 숫자", "소수점 있는 숫자"):
                pairs.append({"code": code, "output": output, "inline": True})
    return pairs


def parse_file(md_path: Path) -> list[dict]:
    text = md_path.read_text(encoding="utf-8")
    sections = extract_sections(text)
    source_file = md_path.name

    all_pairs: list[dict] = []
    all_concepts: list[str] = []
    for sec in sections:
        all_pairs.extend(extract_code_output_pairs(sec["body"]))
        all_pairs.extend(extract_inline_output_pairs(sec["body"]))
        all_concepts.extend(extract_concepts(sec["body"]))

    all_outputs = [p["output"] for p in all_pairs if p["output"]]
    all_codes = [p["code"] for p in all_pairs]
    all_tokens_in_file = [t for t in LEARN_TOKENS
                          if any(re.search(rf"\b{re.escape(t)}\b", p["code"]) for p in all_pairs)]

    questions = []
    seen_ids = set()

    for sec in sections:
        pairs = extract_code_output_pairs(sec["body"]) + extract_inline_output_pairs(sec["body"])
        concepts = extract_concepts(sec["body"])
        other_outputs = [o for o in all_outputs if o not in [p["output"] for p in pairs]]
        other_codes = [c for c in all_codes if c not in [p["code"] for p in pairs]]
        other_concepts = [c for c in all_concepts if c not in concepts]

        # 섹션·유형별 상한. 같은 원본 한 조각에서 문제가 과잉 생성되는 것을 막는다.
        fb = ct = rt = 0
        for pair in pairs:
            if fb < SECTION_CAP:
                qs = gen_fill_blank(pair, sec["title"], source_file, all_tokens_in_file)
                questions.extend(qs); fb += len(qs)
            if ct < SECTION_CAP:
                qs = gen_code_to_result(pair, sec["title"], source_file, other_outputs)
                questions.extend(qs); ct += len(qs)
            if rt < SECTION_CAP:
                qs = gen_result_to_code(pair, sec["title"], source_file, other_codes)
                questions.extend(qs); rt += len(qs)

        # 답이 짧고 명확하면 단답(입력형), 길거나 서술형이면 객관식(보기 선택)으로 배분.
        sa_concepts, mc_concepts = [], []
        for c in concepts:
            a = _extract_answer(c)
            if not a:
                continue
            if _good_answer(a, max_words=2, max_len=15):
                sa_concepts.append(c)   # 짧은 답 → 단답
            else:
                mc_concepts.append(c)   # 긴 답 → 객관식
        sa_use = sa_concepts[:SECTION_CAP]
        mc_use = mc_concepts[:SECTION_CAP]
        # 객관식 정원이 남으면 단답에 안 쓴 짧은-답 개념도 객관식으로 활용
        if len(mc_use) < SECTION_CAP:
            mc_use += [c for c in sa_concepts if c not in sa_use][: SECTION_CAP - len(mc_use)]
        questions.extend(gen_concept_mc(mc_use, sec["title"], source_file, other_concepts))
        questions.extend(gen_short_answer(sa_use, sec["title"], source_file))

    deduped = []
    for q in questions:
        if q["id"] not in seen_ids:
            seen_ids.add(q["id"])
            deduped.append(q)

    return deduped


def parse_all(content_dir: Path, output_path: Path) -> dict:
    all_questions = []
    seen_ids = set()

    for md_file in sorted(content_dir.rglob("*.md")):
        if "미션" in str(md_file):
            continue
        try:
            qs = parse_file(md_file)
            for q in qs:
                if q["id"] not in seen_ids:
                    seen_ids.add(q["id"])
                    all_questions.append(q)
        except Exception as e:
            print(f"[경고] {md_file.name} 파싱 실패: {e}")

    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)

    stats = {}
    for q in all_questions:
        stats[q["type"]] = stats.get(q["type"], 0) + 1

    return {"total": len(all_questions), "by_type": stats}
