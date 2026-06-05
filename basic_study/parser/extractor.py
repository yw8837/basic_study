import re
import json
import hashlib
import random
from pathlib import Path

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


def clean_text(text: str) -> str:
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^>.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[^\S\n]+", " ", text)
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff\U0001F300-\U0001F9FF\U00002600-\U000027BF]",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub("", text)
    return text.strip()


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


def extract_concepts(body: str) -> list[str]:
    cleaned = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    cleaned = clean_text(cleaned)
    sentences = re.split(r"[.。\n]{1,2}", cleaned)
    concepts = []
    for s in sentences:
        s = s.strip()
        if 10 < len(s) < 200 and "`" in s or re.search(r"\*\*.+\*\*", s):
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
    for p in pool:
        if p != correct and p not in distractors:
            distractors.append(p)
        if len(distractors) >= n:
            break
    if len(distractors) < n and correct in TYPE_VARIANTS:
        for v in TYPE_VARIANTS[correct]:
            if v not in distractors and v != correct:
                distractors.append(v)
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
        if len(questions) >= 3:
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
    short_code = code.split("\n")[0] if "\n" in code else code
    distractors = [c.split("\n")[0] for c in other_codes if c != code][:3]
    if len(distractors) < 3:
        return []
    options = [short_code] + distractors[:3]
    random.shuffle(options)
    return [{
        "id": make_id(source_file, section, output),
        "type": "result_to_code",
        "question": f"다음 출력을 만드는 코드는?\n\n```\n{output}\n```",
        "answer": short_code,
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
        if len(answer) < 2:
            continue
        desc = re.sub(r"`[^`]+`", "____", concept, count=1)
        desc = re.sub(r"\*\*[^*]+\*\*", "____", desc, count=1)
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
        if len(answer) < 2:
            continue
        question_text = re.sub(r"`[^`]+`", "____", concept, count=1)
        question_text = re.sub(r"\*\*[^*]+\*\*", "____", question_text, count=1)
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

        for pair in pairs:
            questions.extend(gen_fill_blank(pair, sec["title"], source_file, all_tokens_in_file))
            questions.extend(gen_code_to_result(pair, sec["title"], source_file, other_outputs))
            questions.extend(gen_result_to_code(pair, sec["title"], source_file, other_codes))

        questions.extend(gen_concept_mc(concepts, sec["title"], source_file, other_concepts))
        questions.extend(gen_short_answer(concepts, sec["title"], source_file))

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
