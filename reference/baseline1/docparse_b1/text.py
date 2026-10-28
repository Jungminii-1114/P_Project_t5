# baseline-1 동결 레퍼런스 — v23(64ac263) build_notebook.py §2에서 이식. 수정 금지. 개선은 새 버전에서.

import re


def normalize(text: str) -> str:
    """중복 공백/탭 제거, 'YYYY . MM . DD .' → 'YYYY.MM.DD.'"""
    out = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        line = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", line)
        if line:
            out.append(line)
    return "\n".join(out)
