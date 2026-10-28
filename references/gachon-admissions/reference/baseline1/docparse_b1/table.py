# baseline-1 동결 레퍼런스 — v23(64ac263) build_notebook.py §4에서 이식. 수정 금지. 개선은 새 버전에서.

import re

from .constants import GENERIC_COLS, SYMBOLS

NUMERIC = re.compile(r"^[\d,./~%()~\-–\s]+$")


def dedup_cells(cells):
    """값이 나오기 전 반복 라벨만 줄이고, 값·후속 셀·빈 셀은 보존한다."""
    out = []
    label_side = True
    for c in cells:
        if is_value(c):
            out.append(c)
            label_side = False
        elif not c or not label_side or not out or c != out[-1]:
            out.append(c)
    return out


def is_value(c: str) -> bool:
    return bool(c) and (bool(NUMERIC.match(c)) or c in SYMBOLS)


def expand_header(header_rows, width: int):
    """다단 헤더: 행 내부의 빈칸(가로 병합)을 왼쪽 값으로 채운 뒤 열마다 위→아래로 결합."""
    rows = []
    for r in header_rows:
        r = list(r) + [""] * (width - len(r))
        last_nonempty = max((j for j, v in enumerate(r) if v), default=-1)
        for j in range(last_nonempty):
            if not r[j] and j > 0 and r[j - 1]:
                r[j] = r[j - 1]
        rows.append(r)
    cols = []
    for j in range(width):
        parts = []
        for r in rows:
            v = r[j]
            if v and (not parts or parts[-1] != v):
                parts.append(v)
        cols.append(" ".join(parts))
    return cols


def parse_table(text: str):
    """markdown 표 → (표제, 모드, 열 이름, 데이터 행). wide=열이 많은 표/일정표, roster=목록형 표."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    if not rows:
        return "", "roster", [], []
    start = None
    for i, r in enumerate(rows):
        if any(any(k in c for k in ("학과", "학부", "전공", "의예과", "지역")) for c in r):
            start = i
            break
    if start is None or start == 0:
        start = 1 if len(rows) > 1 else 0
    header_rows = rows[:start]
    data = [r for r in rows[start:] if r and not r[0].startswith("※")]
    width = max([len(r) for r in rows] + [1])
    sched = any(re.search(r"\d+월|\d+일|시간|일시|오전|오후", c) for r in header_rows for c in r)
    mode = "wide" if (width >= 7 or sched) else "roster"
    if mode == "wide":
        cols = expand_header(header_rows, width)
    else:
        base = header_rows[-1] if header_rows else []
        cols = dedup_cells([c for c in base if c]) or [c for c in base if c]
    if sched:
        caption = "면접/전형 일정"
    else:
        first = [c for c in (header_rows[0] if header_rows else []) if c and c not in GENERIC_COLS]
        caption = first[0][:30] if first else ""
    return caption, mode, cols, data


def row_summary(cols, data, mode, max_rows=30, max_chars=2600) -> str:
    """표 → '- 라벨: 열=값, …' 행 요약."""
    H = len(cols)
    if H == 0:
        return ""
    lines, used = [], 0
    for r in data:
        if not r:
            continue
        if mode == "wide":
            label = next((c for c in r if any(k in c for k in ("학과", "학부", "전공", "지역"))), "")
            pairs = []
            for j, v in enumerate(r):
                if not v or v == label or v in GENERIC_COLS:
                    continue
                col = cols[j] if j < len(cols) else ""
                if col and col != v and col != "모집단위":
                    pairs.append(f"{col}={v}")
            if not label or not pairs:
                continue
        else:
            ded = dedup_cells(r)
            # PDF 표에서 가장자리 빈 셀이 헤더 너비를 초과하게 만들 수 있다.
            # 빈 셀을 먼저 줄이고, 남는 초과 폭은 값 앞의 라벨 셀만 합친다.
            while len(ded) > H and ded and not ded[0]:
                ded = ded[1:]
            while len(ded) > H and ded and not ded[-1]:
                ded = ded[:-1]
            first_value = next((j for j, v in enumerate(ded) if is_value(v)), len(ded))
            while len(ded) > H and first_value > 1:
                ded = [f"{ded[0]} {ded[1]}".strip()] + ded[2:]
                first_value -= 1
            if len(ded) > H:
                continue
            if len(ded) < H:
                ded = [""] * (H - len(ded)) + ded
            vals = [(j, v) for j, v in enumerate(ded) if v]
            if len(vals) < 2:
                continue
            first_val = next((j for j, v in vals if is_value(v)), H)
            label = " ".join(v for j, v in vals if j < first_val and v not in GENERIC_COLS)
            if not label or is_value(label):
                continue
            pairs = [f"{cols[j]}={v}" for j, v in vals if j >= first_val and cols[j]]
            if not pairs:
                continue
        line = f"- {label}: " + ", ".join(pairs[:6])
        if used + len(line) > max_chars or len(lines) >= max_rows:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines)
