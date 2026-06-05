import re


def _normalize_lenient(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[.,。،]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_code(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s*([+\-*/%=<>!&|^~])\s*", r" \1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace('"', "'")
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines)


def _edit_distance(a: str, b: str) -> int:
    """Damerau-Levenshtein: transposition(자리바꿈)도 1로 계산."""
    if abs(len(a) - len(b)) > 2:
        return 99
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                dp[i][j] = min(dp[i][j], dp[i - 2][j - 2] + 1)
    return dp[m][n]


def grade(question: dict, user_answer: str) -> bool:
    correct = str(question["answer"])
    grading = question.get("grading", "lenient")

    if grading == "code_strict":
        return _normalize_code(correct) == _normalize_code(user_answer)

    norm_correct = _normalize_lenient(correct)
    norm_user = _normalize_lenient(user_answer)

    if norm_correct == norm_user:
        return True

    if len(norm_correct) > 2 and _edit_distance(norm_correct, norm_user) <= 1:
        return True

    return False


def grade_with_feedback(question: dict, user_answer: str) -> dict:
    is_correct = grade(question, user_answer)
    return {
        "correct": is_correct,
        "user_answer": user_answer,
        "correct_answer": question["answer"],
        "explanation": question.get("explanation", ""),
    }
