import json, glob, os
from typing import List, Tuple

REQUIRED_TOP_LEVEL = ["title", "questions"]

def _err(file, msg): return (file, msg)

def validate_file(path: str) -> List[Tuple[str,str]]:
    issues = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except Exception as e:
        return [_err(path, f"JSON parse error: {e}")]

    # top-level
    for k in REQUIRED_TOP_LEVEL:
        if k not in doc:
            issues.append(_err(path, f"Missing top-level key: {k}"))
    if "questions" not in doc or not isinstance(doc.get("questions"), list):
        issues.append(_err(path, "questions must be a list"))
        return issues

    seen_q = set()
    for i, q in enumerate(doc["questions"]):
        if not isinstance(q, dict):
            issues.append(_err(path, f"Q{i+1}: not an object"))
            continue
        qtype = q.get("type")
        text = q.get("question")
        if not qtype: issues.append(_err(path, f"Q{i+1}: missing 'type'"))
        if not text:  issues.append(_err(path, f"Q{i+1}: missing 'question'"))
        # duplicate question text within a file
        if text:
            if text in seen_q:
                issues.append(_err(path, f"Q{i+1}: duplicate question text"))
            seen_q.add(text)

        if qtype == "mcq":
            opts = q.get("options")
            ans  = q.get("answer")
            if not isinstance(opts, list) or len(opts) < 2:
                issues.append(_err(path, f"Q{i+1}: mcq needs >=2 options"))
            if not isinstance(ans, int):
                issues.append(_err(path, f"Q{i+1}: mcq 'answer' must be index (int)"))
            else:
                if isinstance(opts, list) and not (0 <= ans < len(opts)):
                    issues.append(_err(path, f"Q{i+1}: mcq 'answer' index out of range"))
            # explanation optional but recommended
        elif qtype == "numeric":
            if "answer" not in q:
                issues.append(_err(path, f"Q{i+1}: numeric needs 'answer'"))
            elif not isinstance(q["answer"], (int, float)):
                issues.append(_err(path, f"Q{i+1}: numeric 'answer' must be number"))
            tol = q.get("tolerance", 0.01)
            if not isinstance(tol, (int, float)) or tol < 0:
                issues.append(_err(path, f"Q{i+1}: numeric 'tolerance' must be non-negative number"))
        elif qtype == "repeat":
            if "answer_text" not in q:
                issues.append(_err(path, f"Q{i+1}: repeat needs 'answer_text'"))
        else:
            issues.append(_err(path, f"Q{i+1}: unknown type '{qtype}'"))
    return issues

def validate_all(data_dir: str = "data") -> List[Tuple[str,str]]:
    problems = []
    for path in sorted(glob.glob(os.path.join(data_dir, "day*.json"))):
        problems.extend(validate_file(path))
    return problems

if __name__ == "__main__":
    problems = validate_all()
    if not problems:
        print("OK: all quiz files valid.")
    else:
        for f, m in problems:
            print(f"[{f}] {m}")
        raise SystemExit(1)
