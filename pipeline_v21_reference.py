"""
가천대 2027 입학안내 Agentic RAG — v21 파이프라인 레퍼런스 (Colab 커널에서 그대로 추출)

이 파일은 2026-10-25 Colab 커널의 실제 실행 코드를 inspect.getsource 로 뽑아 정리한 것입니다.
- 그대로 단독 실행되는 파일은 아닙니다(파싱/인덱싱 프리앰블은 build_notebook.py 참고).
- 목적: 커널이 사라져도 검증된 로직을 잃지 않기 위한 스냅샷.

전제 변수(프리앰블에서 생성):
    chunks_v15, CHUNK_INDEX_V15, vectordb_v15, dense_v15, bm25_v15,
    page_db, page_dense, page_bm25, kiwi, llm, embeddings
"""

import re
import time

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever

# ---------------------------------------------------------------------------
# 0. 패턴 / 상수
# ---------------------------------------------------------------------------
CITE_RE = re.compile(r"\(출처:\s*([^)]*?)\s*p\.\s*(\d+)\)")
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
NUMERIC = re.compile(r"^[\d,./~%()~\-–\s]+$")
DATE_RE = re.compile(r"\d{1,2}\s*월\s*\d{1,2}\s*일")
ENT_RE = re.compile(r"[가-힣A-Za-z0-9·]+(?:학과|학부|전공|전형|대학|고등학교|중학교)")
COND_MARK = re.compile(r"(경우|해야|충족|인정|간주|다만|반드시)")
LIST_INTENT = re.compile(r"((뭐|무엇|어떤).{0,12}(있|지원|혜택|항목|종류)|목록|종류|어디어디|무엇무엇)")
NEG_RE = re.compile(r"(불가|반환하지|제외|없음|않|미포함|불허)")
DATE_CELL = re.compile(r"^[\d.,~()\s월화수목금토일]+$")

NOT_FOUND = "확인할 수 없습니다"
SYMBOLS = {"O", "■", "□", "△", "○", "●", "X", "▲", "★", "◉"}
ALLOWED = {"NNG", "NNP", "NNB", "VV", "VA", "XR", "SL", "SN"}

GENERIC = {"무엇", "분", "얼마", "월", "사람", "이", "나", "경우", "저거", "년", "너", "학생들",
           "때문", "어디", "저", "친구", "거", "이거", "제", "등", "우리", "것", "언제", "학생",
           "때", "그", "정도", "뭐", "일", "사람들", "좀", "수", "애들", "그거"}
GENERIC_COLS = {"비고", "계열", "연번", "번호", "구분"}
GENERIC_DETAILS = {"경우에는", "모집", "사항", "전형", "절차", "가능", "대학", "2027학년도", "기간",
                   "본교", "서류", "입학", "경우", "결과", "방법", "학생", "내용", "지원", "정도",
                   "평가", "제출", "지원자", "이하", "신청", "모집요강", "안내", "관련", "이상",
                   "때문", "확인", "해당"}
DETAIL_STOP = {"경우에는", "확인", "숙지", "변경", "입력", "가능", "모집요강", "안내", "작성",
               "정확", "경우", "내용"}

SYNONYMS = {
    "뽑": "모집 선발", "선발": "모집", "몇명": "모집인원", "몇 명": "모집인원", "인원": "모집인원",
    "해외": "재외국민", "외국": "재외국민", "유학": "재외국민",
    "등록금": "등록 포기 환불", "환불": "등록포기 환불", "시험": "전형", "서류": "제출서류",
    "조건": "지원자격", "불편": "장애 지원", "도와": "지원", "도움": "지원", "장애인": "장애",
    "사진": "증명사진", "원서": "원서접수", "수시": "수시모집", "정시": "정시모집",
    "등록": "등록 포기 환불", "합격": "합격자 발표",
    "두 군데": "복수지원", "같이 넣": "복수지원", "중복 지원": "복수지원", "동시 지원": "복수지원",
    "여러 개 지원": "복수지원", "동시에": "복수지원",
    "일정표": "일정", "몇 쪽": "페이지", "몇쪽": "페이지",
    "새로 생": "신설", "새로 만": "신설", "신설된": "신설",
}

ROUTE_PATTERNS = [
    ("page", r"(몇\s*쪽|페이지|쪽에|몇\s*장)"),
    ("table", r"(몇\s*명|몇명|인원|모집|선발|정원|명까지|명씩|비율|점수|등급|컷|몇\s*점|감점)"),
    ("procedure", r"(어떻게|신청|제출|절차|방법|해야\s*하|어디서)"),
    ("eligibility", r"(자격|조건|대상|가능|되나요|될까|수\s*있나|받을\s*수)"),
    ("list", r"(어디어디|무엇무엇|종류|예시|포함|목록|어떤\s*게)"),
]
ROUTE_SUFFIX = {"table": " 모집인원 표", "page": " 목차 페이지", "procedure": " 신청 방법 절차",
                "eligibility": " 지원자격 조건", "list": " 목록", "general": "", "schedule": " 면접 일정"}

DOC_KEYWORDS = [
    ("05", r"(면접.*(일정|일정표|날짜|시간)|(일정|일정표).*면접)"),
    ("04", r"정시"),
    ("03", r"수시"),
    ("02", r"지역\s*의사"),
    ("01", r"(재외국민|외국)"),
]

DOC_TITLES = {
    "01": "2027학년도 재외국민 모집요강",
    "02": "2027학년도 지역의사선발전형 안내",
    "03": "2027학년도 수시 모집요강",
    "04": "2027학년도 정시 모집요강",
    "05": "2027학년도 수시 면접고사 일정",
}

# 목차 페이지는 실행 시 자동 탐지한 값 (수동 하드코딩 아님)
TOC_PAGES = {"03": {3, 28, 38, 82, 96, 102}, "04": {2, 11, 31}}


# ---------------------------------------------------------------------------
# 1. 질의 분석 / 라우팅
# ---------------------------------------------------------------------------
def doc_title(source):
    return DOC_TITLES.get(source[:2], source)


def korean_tokenizer(text):
    return [t.form for t in kiwi.tokenize(text) if t.tag in ALLOWED]


def search_keywords(q, k=10):
    """질문 → 검색용 키워드(일반명사 제거 + 동의어 치환)."""
    out = []
    for t in kiwi.tokenize(q):
        if t.tag not in {"NNG", "NNP", "SL", "SN"} or len(t.form) < 2:
            continue
        w = t.form
        if w in GENERIC or any(key in w for key in SYNONYMS):
            continue
        if w not in out:
            out.append(w)
    for key, val in SYNONYMS.items():
        if key in q:
            for v in val.split():
                if v not in out:
                    out.append(v)
    return " ".join(out[:k])


def route_query(q):
    if re.search(r"(면접.*(일정|일정표|날짜|시간)|(일정|일정표).*면접)", q):
        return "schedule"
    for name, pat in ROUTE_PATTERNS:
        if re.search(pat, q):
            return name
    return "general"


def route_queries(q):
    kw = search_keywords(q)
    return route_query(q), kw, (kw + ROUTE_SUFFIX[route_query(q)]).strip()


def target_doc(q):
    for prefix, pat in DOC_KEYWORDS:
        if re.search(pat, q):
            return prefix
    return None


def dept_terms(q):
    return list(dict.fromkeys(re.findall(r"([가-힣A-Za-z0-9·]{2,})\s*(?:학과|학부|전공)", q)))


def overlap_score(doc, kw):
    toks = [t for t in kw.split() if len(t) > 1]
    text = doc.metadata.get("raw", doc.page_content)
    return sum(text.count(t) for t in toks)


# ---------------------------------------------------------------------------
# 2. 표 파싱 / 문맥 헤더 (Contextual Retrieval + Table-aware)
# ---------------------------------------------------------------------------
def dedup_cells(cells):
    out = []
    for c in cells:
        if not out or c != out[-1]:
            out.append(c)
    return out


def is_value(c):
    return bool(c) and (bool(NUMERIC.match(c)) or c in SYMBOLS)


def expand_header(header_rows, width):
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


def parse_table2(text):
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
        caption = (first[0][:30] if first else "")
    return caption, mode, cols, data


def row_summary2(cols, data, mode, max_rows=30, max_chars=2600):
    """표 → '라벨: 열=값' 직렬화. 임베딩/BM25가 표 구조를 이해하도록 만드는 핵심."""
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
            if len(ded) == H + 1 and len(ded) >= 3:
                ded = [ded[0], f"{ded[1]} {ded[2]}".strip()] + ded[3:]
            if len(ded) < H:
                ded = [""] * (H - len(ded)) + ded
            if len(ded) > H:
                ded = ded[-H:]
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


def build_contextual_chunks(chunks):
    out, with_summary = [], 0
    for c in chunks:
        src, page, kind = c.metadata["source"], c.metadata["page"], c.metadata["kind"]
        title = doc_title(src)
        raw = c.page_content
        header = f"[문서] {title} | p.{page} | {'표' if kind == 'table' else '본문'}"
        summary, mode = "", ""
        if kind == "table":
            caption, mode, cols, data = parse_table2(raw)
            if caption:
                header += f" | 표제: {caption}"
            summary = row_summary2(cols, data, mode)
            if summary:
                with_summary += 1
        body = header + (("\n[표 행 요약]\n" + summary) if summary else "") + "\n[원문]\n" + raw
        md = dict(c.metadata)
        md.update(raw=raw, title=title, table_mode=mode, contextual=True)
        out.append(Document(page_content=body, metadata=md))
    print(f"표 청크 {sum(c.metadata['kind']=='table' for c in chunks)}개 중 행 요약 {with_summary}개")
    return out


# ---------------------------------------------------------------------------
# 3. 검색 (Hierarchical + Multi-query RRF + rare-term)
# ---------------------------------------------------------------------------
def rrf_fuse(result_lists, weights, rrf_k=60):
    scores, docs = {}, {}
    for w, result in zip(weights, result_lists):
        for rank, d in enumerate(result, 1):
            key = d.page_content
            scores[key] = scores.get(key, 0.0) + w / (rrf_k + rank)
            docs[key] = d
    return scores, docs


def page_prior(query, top_pages=5):
    """계층 검색: 페이지 단위로 먼저 찾고, 해당 페이지 청크에 가산점."""
    s, d = rrf_fuse([page_bm25.invoke(query), page_dense.invoke(query)], [1.0, 1.0], rrf_k=40)
    ordered = sorted(s, key=s.get, reverse=True)[:top_pages]
    return {(d[k].metadata["source"], d[k].metadata["page"]): i + 1 for i, k in enumerate(ordered)}


def rare_terms(kw, n=1):
    """질문 키워드 중 코퍼스 빈도가 가장 낮은 토큰 (RRF 희석 방지용)."""
    toks = [t for t in kw.split() if len(t) >= 2 and not t.isdigit()]
    toks.sort(key=lambda t: sum(t in c.metadata["raw"] for c in chunks_v15))
    return toks[:n]


def inject(scores, docs, kw, pool, top_score, factor=1.05, limit=2):
    ranked = sorted(pool, key=lambda d: overlap_score(d, kw), reverse=True)[:limit]
    for d in ranked:
        key = d.page_content
        scores[key] = max(scores.get(key, 0.0), top_score * factor)
        docs[key] = d
    return ranked


def table_dept_boost(scores, docs, query, kw, tdoc, top_score):
    terms = dept_terms(query)
    if not terms:
        return []
    cands = []
    for c in chunks_v15:
        if c.metadata["kind"] != "table" or not c.metadata["source"].startswith(tdoc):
            continue
        if not any(t in c.metadata["raw"] for t in terms):
            continue
        summary_hit = sum(t in c.page_content.split("[원문]")[0] for t in terms)
        cands.append((overlap_score(c, kw) + 5 * summary_hit, c))
    cands.sort(key=lambda x: x[0], reverse=True)
    picked = [c for _, c in cands[:2]]
    for c in picked:
        scores[c.page_content] = max(scores.get(c.page_content, 0.0), top_score * 1.18)
        docs[c.page_content] = c
    return picked


def retrieve_v15(query, top_n=6, expand_top=2, rrf_k=60):
    route, kw, kw_route = route_queries(query)
    lists = [bm25_v15.invoke(query), dense_v15.invoke(query),
             bm25_v15.invoke(kw), dense_v15.invoke(kw_route)]
    weights = [1.0, 1.0, 1.15, 1.15]

    rare = rare_terms(kw, 1)
    if rare:
        tok = rare[0]
        if sum(tok in c.metadata["raw"] for c in chunks_v15) < 80:
            lists.append(bm25_v15.invoke(tok))
            weights.append(1.0)

    scores, docs = rrf_fuse(lists, weights, rrf_k)
    prior = page_prior(kw_route)
    tdoc = target_doc(query)
    for key, d in docs.items():
        r = prior.get((d.metadata["source"], d.metadata["page"]))
        if r:
            scores[key] += 0.45 / (40 + r)
        if tdoc and d.metadata["source"].startswith(tdoc):
            scores[key] *= 1.12
        if route == "table" and d.metadata["kind"] == "table":
            scores[key] *= 1.15
        if route in ("procedure", "eligibility", "page") and d.metadata["kind"] == "text":
            scores[key] *= 1.12

    top_score = max(scores.values()) if scores else 0.0
    if route == "table" and tdoc:
        table_dept_boost(scores, docs, query, kw, tdoc, top_score)
    if route == "page" and tdoc and tdoc in TOC_PAGES:
        pool = [c for c in chunks_v15
                if c.metadata["source"].startswith(tdoc) and c.metadata["page"] in TOC_PAGES[tdoc]]
        inject(scores, docs, kw, pool, top_score, factor=1.12, limit=2)
    if route == "schedule":
        pool = [c for c in chunks_v15 if c.metadata["source"].startswith("05")]
        inject(scores, docs, kw, pool, top_score, factor=1.15, limit=3)

    top = [docs[k] for k in sorted(scores, key=scores.get, reverse=True)[:top_n]]
    out, seen = [], set()
    for n, d in enumerate(top):
        if d.page_content not in seen:
            out.append(d)
            seen.add(d.page_content)
        if n >= expand_top:
            continue
        i = CHUNK_INDEX_V15[d.page_content]
        for j in range(max(0, i - 1), min(len(chunks_v15), i + 2)):
            c = chunks_v15[j]
            if c.metadata["source"] == d.metadata["source"] and c.page_content not in seen:
                out.append(c)
                seen.add(c.page_content)

    # 페이지 단위 형제 청크 확장 (같은 페이지의 다른 청크 중 질문과 가장 관련 있는 1개)
    for d in top[:2]:
        sibs = [c for c in chunks_v15
                if c.metadata["source"] == d.metadata["source"]
                and c.metadata["page"] == d.metadata["page"]
                and c.page_content not in seen]
        if sibs:
            best = max(sibs, key=lambda c: overlap_score(c, kw))
            if overlap_score(best, kw) > 0:
                out.append(best)
                seen.add(best.page_content)
    return out, route


def toc_lookup(question, tdoc):
    """목차 페이지를 파싱해 '몇 쪽' 질문에 결정적으로 답한다 (LLM 미호출)."""
    if not tdoc or tdoc not in TOC_PAGES:
        return None
    kw = search_keywords(question)
    skip = {"페이지", "목차", "요강", "모집", "전형", "안내", "정시모집", "수시모집", "대학"}
    toks = [t for t in kw.split() if len(t) >= 2 and t not in skip]
    best = (0, None, None, None)
    for c in chunks_v15:
        if not (c.metadata["source"].startswith(tdoc) and c.metadata["page"] in TOC_PAGES[tdoc]):
            continue
        for line in c.metadata["raw"].splitlines():
            m = re.match(r"^\s*(\d{1,3})\s+(.+)$", line.strip())
            if not m:
                continue
            num, title = m.group(1), m.group(2).strip()
            score = sum(len(t) for t in toks if t in title)
            if score > best[0]:
                best = (score, num, title, c)
    if best[0] < 2:
        return None
    return {"page": best[1], "title": best[2], "doc_page": best[3].metadata["page"],
            "source": best[3].metadata["source"]}


# ---------------------------------------------------------------------------
# 4. 근거 검증 (Evidence-grounded Verification)
# ---------------------------------------------------------------------------
def _norm(s):
    return re.sub(r"\s+", "", s)


def _strip_cite(s):
    return CITE_RE.sub("", s)


def _particle(word):
    last = word.strip()[-1]
    if not ("가" <= last <= "힣"):
        return "은"
    return "은" if (ord(last) - 0xAC00) % 28 else "는"


def lexical_coverage(kw, docs):
    toks = [t for t in kw.split() if len(t) > 1]
    if not toks:
        return 0.0
    ev = _norm(" ".join(d.metadata.get("raw", "") for d in docs[:5]))
    return sum(_norm(t) in ev for t in toks) / len(toks)


def ground_answer(answer, docs, question=""):
    """답변의 숫자·날짜·개체·인용을 근거와 대조해 grounding 점수를 계산."""
    evidence = _norm("\n".join(d.metadata.get("raw", d.page_content) for d in docs))
    body = _strip_cite(answer)

    nums = [n for n in NUM_RE.findall(body) if len(n.replace(",", "")) >= 1]
    dates = DATE_RE.findall(body)
    ents = [e for e in ENT_RE.findall(body) if len(e) >= 3]

    num_ok = sum(_norm(n) in evidence for n in nums) / len(nums) if nums else 1.0
    date_ok = sum(_norm(d) in evidence for d in dates) / len(dates) if dates else 1.0
    ent_ok = sum(_norm(e) in evidence for e in ents) / len(ents) if ents else 1.0

    cites = CITE_RE.findall(answer)
    valid = 0
    for fname, page in cites:
        key = fname.strip()[:2]
        if any(d.metadata["source"].startswith(key) and str(d.metadata["page"]) == page for d in docs):
            valid += 1
    cite_ok = valid / len(cites) if cites else 0.0

    score = 0.40 * num_ok + 0.20 * date_ok + 0.25 * ent_ok + 0.15 * cite_ok
    return {
        "score": round(score, 3), "num_ok": round(num_ok, 3), "date_ok": round(date_ok, 3),
        "ent_ok": round(ent_ok, 3), "cite_ok": round(cite_ok, 3),
        "n_num": len(nums), "n_date": len(dates), "n_ent": len(ents),
        "not_found": NOT_FOUND in body,
    }


def make_confidence(route, kw, docs, g):
    cov = lexical_coverage(kw, docs)
    route_bonus = {"table": 0.06, "page": 0.05, "schedule": 0.05}.get(route, 0.0)
    conf = 0.50 * g["score"] + 0.35 * cov + 0.15 * (1.0 if g["cite_ok"] >= 0.99 else 0.5) + route_bonus
    if g["not_found"]:
        conf -= 0.25
    return round(max(0.0, min(1.0, conf)), 3), round(cov, 3)


def norm_dates(text):
    out = set(re.findall(r"\d{4}\.\d{2}\.\d{2}", text))
    for y, m, d in re.findall(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", text):
        out.add(f"{y}.{int(m):02d}.{int(d):02d}")
    return out


def iter_sentences(raw):
    text = raw.replace("|", "\n")
    for sent in re.split(r"(?<=[.다])\s+|\n", text):
        sent = sent.strip(" -•\t")
        if len(sent) >= 25:
            yield sent


def _content_tokens(text):
    return {t.form for t in kiwi.tokenize(text)
            if t.tag in {"NNG", "NNP", "VV", "VA", "XR", "SL", "SN"} and len(t.form) >= 2}


def _noun_tokens(text):
    return {t.form for t in kiwi.tokenize(text)
            if t.tag in {"NNG", "NNP"} and len(t.form) >= 2 and t.form not in GENERIC_DETAILS}


def focus_docs(answer, docs):
    prefixes = {f.strip()[:2] for f, _ in CITE_RE.findall(answer)}
    focus = [d for d in docs if d.metadata["source"][:2] in prefixes]
    return (focus or docs)[:4]


def missing_list_items(question, answer, docs, max_items=4):
    """질문이 목록을 요구할 때, 근거의 쉼표 항목이 답변에 그대로 있는지 확인."""
    if not LIST_INTENT.search(question):
        return []
    kws = [t for t in search_keywords(question).split() if len(t) >= 2][:4]
    missing = []
    for d in docs[:3]:
        for sent in re.split(r"[.\n]", d.metadata.get("raw", "")):
            if ("," not in sent and "·" not in sent) or len(sent) < 15:
                continue
            if kws and not any(t in sent for t in kws):
                continue
            items = [x.strip(" ①②③④⑤⑥⑦⑧⑨⑩") for x in re.split(r"[,·]", sent)]
            items = [x for x in items if 2 <= len(x) <= 14]
            if len(items) < 3:
                continue
            for it in items:
                if it not in answer and it not in missing:
                    missing.append(it)
            if missing:
                return missing[:max_items]
    return []


def missing_conditions(answer, docs, max_sent=2):
    """답변을 실질적으로 뒷받침하는 청크 안의 조건문이 답변에 반영됐는지 확인."""
    ans_toks = _content_tokens(answer)
    scored = []
    for d in docs[:6]:
        c_toks = _content_tokens(d.metadata.get("raw", ""))
        if not c_toks:
            continue
        scored.append((len(c_toks & ans_toks) / len(c_toks), d))
    scored.sort(key=lambda x: x[0], reverse=True)

    missing = []
    for cov, d in scored[:2]:
        if cov < 0.30:
            continue
        for sent in iter_sentences(d.metadata.get("raw", "")):
            if not COND_MARK.search(sent):
                continue
            s_toks = _content_tokens(sent)
            if len(s_toks) < 3:
                continue
            overlap = len(s_toks & ans_toks) / len(s_toks)
            if overlap < 0.5:
                missing.append((round(overlap, 2), sent))
        if len(missing) >= max_sent:
            break
    return [s for _, s in missing[:max_sent]]


def missing_neighbor_details(answer, docs, max_items=2):
    ans_toks = _content_tokens(answer)
    body = _strip_cite(answer)
    focus = focus_docs(answer, docs)

    facts = norm_dates(body) | {n for n in NUM_RE.findall(body) if len(n.replace(",", "")) >= 5}
    if facts:
        for d in focus:
            if d.metadata["kind"] != "table":
                continue
            for line in d.metadata.get("raw", "").splitlines():
                if line.count("|") < 2 or not any(f in line for f in facts):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                missing = [c for c in cells
                           if len(c) >= 3 and c not in answer and not is_value(c)
                           and not DATE_CELL.match(c) and c not in GENERIC_DETAILS]
                if missing:
                    return missing[:max_items]

    best_neg = (0, [])
    for d in focus:
        for s in iter_sentences(d.metadata.get("raw", "")):
            if not NEG_RE.search(s):
                continue
            shared = _content_tokens(s) & ans_toks
            score = sum(len(t) for t in shared)
            missing = [t for t in _noun_tokens(s)
                       if t not in answer and t not in DETAIL_STOP and not t.isdigit()]
            if missing and score > best_neg[0]:
                best_neg = (score, missing)
    if best_neg[0] >= 2:
        return best_neg[1][:max_items]

    best = (0.0, [], 0)
    for d in focus:
        sents = [s for s in iter_sentences(d.metadata.get("raw", "")) if not s.startswith("[")]
        for i, s in enumerate(sents):
            st = _content_tokens(s)
            if len(st) < 4:
                continue
            ov = len(st & ans_toks) / len(st)
            if ov > best[0]:
                best = (ov, sents, i)
    if best[0] >= 0.8:
        for nxt in best[1][best[2] + 1: best[2] + 3]:
            missing = [t for t in _noun_tokens(nxt)
                       if t not in answer and t not in DETAIL_STOP and not t.isdigit()]
            if missing:
                return missing[:max_items]
    return []


# ---------------------------------------------------------------------------
# 5. 프롬프트
# ---------------------------------------------------------------------------
DRAFT_PROMPT_V5 = """You are an admissions counselor at Gachon University. Answer using ONLY the evidence documents.

Procedure:
1. Scan EVERY evidence passage for sentences containing the key terms of the question, including passages near the end.
2. Collect all facts that answer any part of the question.
3. Write the answer from those facts only.

Rules:
- Include EVERY key fact the question asks for (numbers, dates, targets, conditions, exceptions), and also closely related details stated in the same evidence sentence (e.g., venue, refund policy, issuing authority).
- If the evidence lists several conditions or exceptions, list ALL of them, including additional requirements stated in the same passage.
- Copy the exact wording of list items (e.g., "국내외 연수", "주거 안정") instead of shortening them.
- For tables, align the row label and column headers by position. Never swap columns.
- For numbered columns (1호, 2호, ...), count every cell from the left, including dashes; match each value to its column.
  Example: header "1호 2호 3호 4호 5호 6호" + row "- - - -10 -20 -100" means 4호=-10, 5호=-20, 6호=-100.
- Never add facts or qualifiers that are not in the evidence.
- NEVER say a rule or information is absent when any evidence passage mentions the question's key terms.
- If the question asks which page, give the page number exactly as listed in the table of contents.
- Write in Korean, 2-5 sentences, and end with (출처: 파일명 p.페이지)."""

REPAIR_PROMPT_V2 = """You are a strict fact-checker. Rewrite the draft using ONLY the evidence.

- The evidence DOES contain sentences relevant to the question. Search every passage, including the last one, before deciding something is missing.
- Remove any number, date, or name not present in the evidence.
- Add every key fact from the evidence that the question asks for but the draft omitted, including additional requirements in the same passage.
- Copy list items exactly (e.g., "국내외 연수").
- Keep it Korean, 2-5 sentences, ending with (출처: 파일명 p.페이지)."""


# ---------------------------------------------------------------------------
# 6. Agentic 루프
# ---------------------------------------------------------------------------
def ask_v21(question, top_n=8, t_budget=10.0, return_meta=False):
    t0 = time.perf_counter()
    route = route_query(question)
    tdoc = target_doc(question)

    # (A) 페이지 질문은 목차 도구로 결정적 처리 → LLM 0회, 0.0s
    if route == "page" and tdoc:
        hit = toc_lookup(question, tdoc)
        if hit:
            topic = hit["title"]
            answer = (f"{topic}{_particle(topic)} {doc_title(hit['source'])} "
                      f"{hit['page']}페이지에 안내되어 있습니다. "
                      f"(출처: {hit['source']} p.{hit['doc_page']})")
            toc_doc = next(c for c in chunks_v15
                           if c.metadata["source"] == hit["source"] and c.metadata["page"] == hit["doc_page"])
            g = ground_answer(answer, [toc_doc], question)
            sec = time.perf_counter() - t0
            if return_meta:
                return {"answer": answer, "route": "page_lookup", "sec": sec, "conf": 0.99,
                        "cov": 1.0, "ground": g, "retried": False,
                        "docs": [(hit["source"][:2], hit["doc_page"])]}
            return answer, 1, sec

    docs, route = retrieve_v15(question, top_n=top_n)
    kw = search_keywords(question)
    ctx = "\n\n".join(f"[근거 {i}] {d.metadata['source']} p.{d.metadata['page']}\n{d.metadata['raw']}"
                      for i, d in enumerate(docs, 1))
    answer = llm.invoke([("system", DRAFT_PROMPT_V5),
                         ("human", f"[Evidence]\n{ctx}\n\n[Question]\n{question}")]).content
    g = ground_answer(answer, docs, question)
    conf, cov = make_confidence(route, kw, docs, g)
    retried = False

    # (B) 근거 기반 검증 → 조건부 교정 (재검색이 아니라 "같은 근거로 다시 쓰기")
    missing_items = missing_list_items(question, answer, docs)
    missing_conds = missing_conditions(answer, docs, max_sent=1)
    missing_neigh = missing_neighbor_details(answer, docs)
    weak = (g["score"] < 0.78 or g["not_found"] or bool(missing_items) or bool(missing_conds)
            or bool(missing_neigh) or re.search(
                r"(규정이 없|안내되어 있지 않|나와 있지 않|확인할 수 없|제공된 자료에는.{0,20}없)", answer))
    if weak and time.perf_counter() - t0 < t_budget:
        retried = True
        hints = []
        if missing_items:
            hints.append("[Exact items to include]\n" + ", ".join(missing_items))
        if missing_conds:
            hints.append("[Conditions that must be reflected]\n" + "\n".join(missing_conds))
        if missing_neigh:
            hints.append("[Related details from the same evidence row/sentence]\n" + ", ".join(missing_neigh))
        answer = llm.invoke([("system", REPAIR_PROMPT_V2),
                             ("human", f"[Evidence]\n{ctx}\n\n[Question]\n{question}\n\n[Draft]\n{answer}\n\n"
                                       + "\n\n".join(hints))]).content
        g = ground_answer(answer, docs, question)
        conf, cov = make_confidence(route, kw, docs, g)

    sec = time.perf_counter() - t0
    if return_meta:
        return {"answer": answer, "route": route, "sec": sec, "conf": conf, "cov": cov,
                "ground": g, "retried": retried,
                "docs": [(d.metadata["source"][:2], d.metadata["page"]) for d in docs]}
    return answer, 1 + int(retried), sec
