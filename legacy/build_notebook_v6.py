# -*- coding: utf-8 -*-
"""가천대 2027 입학 안내 Agentic RAG - 최종 제출용 노트북 빌더."""
import json
import random
import string
from pathlib import Path

CELLS = []


def md(text):
    CELLS.append(("markdown", text.strip("\n")))


def code(text):
    CELLS.append(("code", text.strip("\n")))


# --------------------------------------------------------------------------- #
md(r"""
# 2027학년도 가천대학교 입학 안내 Agentic RAG 챗봇

**중간평가 · 생성형 AI 활용** · 202235052 박진성

- **대상 문서**: `dataset.zip` 내 5개 문서 (HWP 1개 + PDF 4개)
- **파이프라인**: HWP/PDF 파싱 → 청킹 → 임베딩 + 벡터DB → 하이브리드 검색 → Agentic RAG 답변
- **원칙**: 답변 근거는 제공된 5개 문서로 한정 (웹 검색·외부 조회 없음), 문항당 5초 이내 응답 목표

### 파이프라인

| 단계 | 구성 |
|---|---|
| 파싱 | HWP: `langchain-hwp-hwpx-loader`(elements) + 자체 표 렌더러 / PDF: PyMuPDF(텍스트) + pdfplumber(표) |
| 청킹 | 텍스트 800자(overlap 100), 표 1,400자(헤더 반복), 청크 앞에 `[파일명 p.N]` 접두 |
| 인덱스 | Chroma(cosine) + BM25(kiwipiepy 형태소) |
| 검색 | BM25 + Dense → RRF 융합 → 상위 6개 + 이웃 청크 확장 |
| 답변 | 초안 생성 → 근거 대조 검증 → (부족하면) 재검색 후 재작성 |

> 실행: 위에서부터 **모두 실행(Runtime → Run all)**. 최초 실행 시 패키지 설치·색인 생성에 2~3분이 걸리며,
> 이 시간은 평가의 응답시간 측정에서 제외되는 구간입니다.
""")

md(r"""
---
## 0. 환경 설정

### 0-1. 패키지 설치
""")

code(r"""
# 필요 패키지 설치 (최초 1회, 약 1~2분)
%pip install -q -U langchain langchain-openai langchain-community "langchain-chroma>=0.1.2" "langchain-hwp-hwpx-loader[distribution]" rank_bm25 kiwipiepy pymupdf pdfplumber

print("✅ 패키지 설치 완료")
""")

md(r"""
### 0-2. API 키

API 키는 **코드에 직접 기재하지 않고** Colab Secrets(왼쪽 🔑) 또는 런타임 환경변수에서 읽습니다.
""")

code(r'''
import os


def load_api_key(name: str = "OPENAI_API_KEY"):
    """Colab Secrets(🔑) 또는 환경변수에서 API 키를 읽는다."""
    key = os.environ.get(name)
    if key:
        return key.strip()
    try:
        from google.colab import userdata

        key = userdata.get(name)
    except Exception:
        key = None
    return key.strip() if key else None


OPENAI_API_KEY = load_api_key("OPENAI_API_KEY")
assert OPENAI_API_KEY, (
    "OPENAI_API_KEY 가 없습니다. Colab 왼쪽 🔑(Secrets)에서 OPENAI_API_KEY 를 추가하고 "
    "'노트북 액세스'를 허용한 뒤 다시 실행하세요."
)
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Chroma 텔레메트리 로그 억제
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

print("OPENAI_API_KEY: 설정됨 ✅")
''')

md(r"""
---
## 1. 데이터 준비

`dataset.zip`(또는 이미 풀린 폴더)을 찾아 `/content/dataset` 에 5개 문서를 준비합니다.
없으면 Google Drive에서 찾고, 마지막으로 직접 업로드를 요청합니다.
""")

code(r'''
import glob
import os
import shutil
import zipfile
from pathlib import Path

REQUIRED = [
    "01_2027학년도_재외국민_모집요강.hwp",
    "02_2027학년도_지역의사선발전형_안내.pdf",
    "03_2027학년도_수시_모집요강.pdf",
    "04_2027학년도_정시_모집요강.pdf",
    "05_2027학년도_수시_면접고사_일정.pdf",
]
DATA_DIR = Path("/content/dataset")


def _all_present(directory: Path) -> bool:
    return all((directory / name).exists() for name in REQUIRED)


def _extract(zip_path: Path) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(DATA_DIR)
    # 압축 파일 안에 하위 폴더가 있거나 한글 파일명이 깨진 경우 → 이름/번호 기준으로 복구
    if not _all_present(DATA_DIR):
        for name in REQUIRED:
            hits = [p for p in DATA_DIR.rglob(name) if p.is_file()]
            if hits:
                shutil.move(str(hits[0]), str(DATA_DIR / name))
    if not _all_present(DATA_DIR):
        for i, name in enumerate(REQUIRED, start=1):
            if (DATA_DIR / name).exists():
                continue
            hits = [p for p in DATA_DIR.iterdir()
                    if p.is_file() and p.name.startswith(f"{i:02d}")]
            if hits:
                hits[0].rename(DATA_DIR / name)


def _bounded_find(root, filename: str, max_depth: int = 5):
    root = Path(root)
    if not root.exists():
        return None
    base = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        if len(Path(dirpath).parts) - base >= max_depth:
            dirnames[:] = []
            continue
        if filename in filenames:
            return Path(dirpath) / filename
    return None


def prepare_dataset() -> Path:
    if _all_present(DATA_DIR):
        print("✅ /content/dataset 의 문서 5개를 사용합니다.")
        return DATA_DIR

    for z in [Path("/content/dataset.zip")] + [Path(p) for p in glob.glob("/content/*/dataset.zip")]:
        if z.exists():
            _extract(z)
            if _all_present(DATA_DIR):
                print(f"✅ {z} 압축 해제 완료")
                return DATA_DIR

    try:  # Google Drive 에 dataset.zip 또는 원본 문서가 있는 경우
        from google.colab import drive

        if not Path("/content/drive/MyDrive").exists():
            print("Google Drive 마운트를 시도합니다... (실패해도 다음 단계로 진행)")
            drive.mount("/content/drive")
        z = _bounded_find("/content/drive/MyDrive", "dataset.zip")
        if z is not None:
            _extract(z)
            if _all_present(DATA_DIR):
                print(f"✅ Drive의 {z} 압축 해제 완료")
                return DATA_DIR
        for name in REQUIRED:
            hit = _bounded_find("/content/drive/MyDrive", name)
            if hit is not None:
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy(hit, DATA_DIR / name)
        if _all_present(DATA_DIR):
            print("✅ Drive의 원본 문서 5개를 복사했습니다.")
            return DATA_DIR
    except Exception as exc:
        print("Drive 탐색 생략:", type(exc).__name__)

    if not _all_present(DATA_DIR):  # 마지막 수단: 직접 업로드
        from google.colab import files

        print("dataset.zip 또는 문서 5개를 업로드하세요.")
        uploaded = files.upload()
        for name, data in uploaded.items():
            Path("/content", name).write_bytes(data)
        if Path("/content/dataset.zip").exists():
            _extract(Path("/content/dataset.zip"))
        for name in REQUIRED:
            src = Path("/content", name)
            if src.exists():
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, DATA_DIR / name)

    assert _all_present(DATA_DIR), f"문서 5개를 찾지 못했습니다: {DATA_DIR}"
    return DATA_DIR


DATA_DIR = prepare_dataset()
for _name in REQUIRED:
    print(f"  - {_name} ({(DATA_DIR / _name).stat().st_size:,} bytes)")
''')

md(r"""
---
## 2. 문서 파싱

- **HWP**: `langchain-hwp-hwpx-loader`의 `mode="elements"` + `distribution_backend="pyhwp"`(배포용 HWP).
  표는 셀 메타데이터(JSON)를 직접 받아 **rowspan/colspan을 전개한 markdown 표**로 복원합니다.
- **PDF 텍스트**: PyMuPDF — 날짜 표기가 정확하고 매우 빠릅니다(pypdf 대비 약 50배).
- **PDF 표**: pdfplumber `extract_tables()` — 2단 레이아웃에서도 행/열 정렬이 안정적입니다.
""")

code(r'''
import json
import re
from pathlib import Path

import pdfplumber

try:
    import pymupdf
except ImportError:  # 구버전 호환
    import fitz as pymupdf

from langchain_core.documents import Document
from langchain_hwp_hwpx import HwpHwpxLoader

# HWP 셀 텍스트에 섞여 들어오는 구조 마커 제거
_MARKER = re.compile(
    r"\[(?:rowspan=\d+,\s*colspan=\d+|colspan=\d+,\s*rowspan=\d+|merged:[^\]]+)\]"
)


def normalize(text: str) -> str:
    """중복 공백/탭 제거, '2027 . 01 . 04 .' → '2027.01.04.'"""
    out = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        line = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", line)
        if line:
            out.append(line)
    return "\n".join(out)


def render_hwp_table(cells_json: str) -> str:
    """HWP 표 cells(JSON)를 markdown 표로 복원한다 (병합 셀 전개)."""
    cells = json.loads(cells_json)
    nrows = max(c["row"] + max(c.get("rowspan", 1), 1) for c in cells)
    ncols = max(c["col"] + max(c.get("colspan", 1), 1) for c in cells)
    grid = [["" for _ in range(ncols)] for _ in range(nrows)]

    for c in cells:
        text = _MARKER.sub(" ", c.get("text") or "")
        text = " ".join(text.split()).replace("|", "/")
        if text == "[IMAGE]":
            text = ""
        rowspan, colspan = max(c.get("rowspan", 1), 1), max(c.get("colspan", 1), 1)
        span = rowspan * colspan
        for r in range(c["row"], min(c["row"] + rowspan, nrows)):
            for col in range(c["col"], min(c["col"] + colspan, ncols)):
                # 넓게 병합된 셀은 좌상단에만 값을 두어 같은 문장이 반복되지 않게 한다
                if span == 1 or len(text) <= 40 or (r, col) == (c["row"], c["col"]):
                    grid[r][col] = text

    lines, prev = [], None
    for row in grid:
        if row == prev or not any(row):
            continue
        prev = row
        lines.append("| " + " | ".join(row) + " |")
    if not lines:
        return ""
    return lines[0] + "\n|" + "---|" * ncols + "\n" + "\n".join(lines[1:])


def rows_to_markdown(rows) -> str:
    """pdfplumber 표(2차원 리스트)를 markdown 표로 변환한다 (빈 행/열 제거)."""
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    rows = [[(c or "").replace("\n", " ").strip() for c in r] + [""] * (ncols - len(r)) for r in rows]
    keep = [j for j in range(ncols) if any(r[j] for r in rows)]
    rows = [[r[j] for j in keep] for r in rows]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        return ""
    body = "\n".join("| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in rows[1:])
    return "| " + " | ".join(rows[0]) + " |\n|" + "---|" * len(keep) + "\n" + body


def parse_hwp(path: Path):
    elements = HwpHwpxLoader(str(path), mode="elements", distribution_backend="pyhwp").load()
    docs = []
    for e in elements:
        kind = e.metadata.get("element_type")
        if kind == "body" and e.page_content.strip():
            docs.append(Document(page_content=e.page_content.strip(),
                                 metadata={"source": path.name, "page": 1, "kind": "text"}))
        elif kind == "table":
            table_md = render_hwp_table(e.metadata.get("cells", "[]"))
            if table_md:
                docs.append(Document(page_content=table_md,
                                     metadata={"source": path.name,
                                               "page": int(e.metadata.get("element_index", 0)) + 1,
                                               "kind": "table"}))
    return docs


def parse_pdf(path: Path):
    docs = []
    with pymupdf.open(str(path)) as doc:
        for i, page in enumerate(doc, start=1):
            text = normalize(page.get_text("text"))
            if text:
                docs.append(Document(page_content=text,
                                     metadata={"source": path.name, "page": i, "kind": "text"}))
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                table_md = normalize(rows_to_markdown(table))
                if len(table_md) > 60:
                    docs.append(Document(page_content=table_md,
                                         metadata={"source": path.name, "page": i, "kind": "table"}))
    return docs


raw_docs = []
for p in sorted(DATA_DIR.iterdir()):
    if p.suffix.lower() == ".hwp":
        raw_docs.extend(parse_hwp(p))
    elif p.suffix.lower() == ".pdf":
        raw_docs.extend(parse_pdf(p))

print(f"파싱 단위: {len(raw_docs)}개")
for name in sorted({d.metadata['source'] for d in raw_docs}):
    part = [d for d in raw_docs if d.metadata["source"] == name]
    print(f"  - {name}: {len(part)}개 / {sum(len(d.page_content) for d in part):,}자")
''')

md(r"""
---
## 3. 청킹

표는 행이 잘리면 의미가 깨지므로 **헤더를 반복**하면서 1,400자 단위로 나누고,
본문은 800자(overlap 100)로 나눕니다. 모든 청크 앞에는 `[파일명 p.페이지]`를 붙여 출처를 유지합니다.
""")

code(r'''
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", "다. ", " ", ""],
)


def _hard_split(text: str, limit: int):
    """공백 기준으로 limit 이하로 강제 분할."""
    out, cur = [], ""
    for word in text.split(" "):
        if len(cur) + len(word) + 1 > limit and cur:
            out.append(cur)
            cur = ""
        cur += (" " if cur else "") + word
    if cur:
        out.append(cur)
    return out


def split_table_markdown(table_md: str, max_chars: int = 1400):
    """표 markdown을 헤더 반복 단위로 분할."""
    lines = table_md.splitlines()
    header, body = lines[:2], lines[2:]
    parts, cur, size = [], [], 0
    for line in body:
        for piece in (_hard_split(line, max_chars) if len(line) > max_chars else [line]):
            if size + len(piece) > max_chars and cur:
                parts.append("\n".join(header + cur))
                cur, size = [], 0
            cur.append(piece)
            size += len(piece)
    if cur:
        parts.append("\n".join(header + cur))
    return parts


chunks = []
for d in raw_docs:
    prefix = f"[{d.metadata['source']} p.{d.metadata['page']}]\n"
    if d.metadata["kind"] == "table":
        pieces = split_table_markdown(d.page_content)
    else:
        pieces = [c.page_content for c in splitter.split_documents([d])]
    for i, piece in enumerate(pieces):
        chunks.append(Document(page_content=prefix + piece,
                               metadata={**d.metadata, "part": i, "chunk_id": len(chunks)}))

lengths = [len(c.page_content) for c in chunks]
print(f"청크 {len(chunks):,}개 | 평균 {sum(lengths) / len(lengths):.0f}자 | 최대 {max(lengths):,}자")
''')

md(r"""
---
## 4. 벡터 DB + BM25 하이브리드 검색기

- **Dense**: OpenAI `text-embedding-3-small` + Chroma(cosine)
- **Sparse**: BM25 (kiwipiepy 형태소 분석 — 명사/동사/영문/숫자만 사용)

문서에 등장하는 고유 명칭·숫자(예: `1577-0067`, `바이오로직스학과`)는 BM25가,  
의미가 유사한 표현은 Dense 임베딩이 강하므로 두 결과를 RRF로 융합합니다.
""")

code(r'''
import time

from kiwipiepy import Kiwi
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_openai import OpenAIEmbeddings

EMBED_MODEL = "text-embedding-3-small"

t0 = time.perf_counter()
embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
vectordb = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    collection_name=f"gachon_admissions_{int(time.time())}",
    collection_metadata={"hnsw:space": "cosine"},
)
dense_retriever = vectordb.as_retriever(search_kwargs={"k": 20})

kiwi = Kiwi()
ALLOWED_TAGS = {"NNG", "NNP", "NNB", "VV", "VA", "XR", "SL", "SN"}


def korean_tokenizer(text: str):
    return [t.form for t in kiwi.tokenize(text) if t.tag in ALLOWED_TAGS]


bm25_retriever = BM25Retriever.from_documents(chunks, preprocess_func=korean_tokenizer)
bm25_retriever.k = 20

print(f"벡터DB {vectordb._collection.count():,}개 청크 | 임베딩 {EMBED_MODEL} | 색인 {time.perf_counter() - t0:.1f}s")
''')

md(r"""
---
## 5. 검색: RRF 융합 + 이웃 청크 확장

1. BM25 상위 20개 + Dense 상위 20개를 **RRF(Reciprocal Rank Fusion, k=60)** 로 융합
2. 상위 6개 선택
3. 상위 2개는 **앞뒤 청크까지 확장** — 표/문단이 청크 경계에서 잘려 문맥이 끊기는 문제를 완화
""")

code(r'''
def rrf_fuse(ranked_lists, top_n: int = 6, rrf_k: int = 60):
    """여러 검색 결과를 Reciprocal Rank Fusion으로 융합."""
    scores, docs = {}, {}
    for result in ranked_lists:
        for rank, doc in enumerate(result, start=1):
            cid = doc.metadata["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
            docs[cid] = doc
    return [docs[cid] for cid in sorted(scores, key=scores.get, reverse=True)[:top_n]]


def expand_neighbors(docs, span: int = 1, top: int = 2):
    """상위 문서의 앞뒤 청크를 같은 문서 내에서만 덧붙인다."""
    out, seen = [], set()
    for n, doc in enumerate(docs):
        cid = doc.metadata["chunk_id"]
        if cid not in seen:
            out.append(doc)
            seen.add(cid)
        if n >= top:
            continue
        for j in range(cid - span, cid + span + 1):
            nb = chunk_by_id.get(j)
            if nb is None or j in seen:
                continue
            if nb.metadata["source"] != doc.metadata["source"]:
                continue
            out.append(nb)
            seen.add(j)
    return out


chunk_by_id = {c.metadata["chunk_id"]: c for c in chunks}


def retrieve(query: str, top_n: int = 6, expand: bool = True):
    """BM25 + Dense → RRF → (선택) 이웃 확장."""
    fused = rrf_fuse([bm25_retriever.invoke(query), dense_retriever.invoke(query)], top_n=top_n)
    return expand_neighbors(fused) if expand else fused


def format_context(docs) -> str:
    return "\n\n".join(
        f"[근거 {i}] {d.metadata['source']} p.{d.metadata['page']}\n{d.page_content}"
        for i, d in enumerate(docs, start=1)
    )


q = "2027학년도 정시모집 원서접수 기간은 언제인가요?"
for d in retrieve(q, top_n=4):
    print(f"[{d.metadata['source'][:24]} p.{d.metadata['page']}] {d.page_content.splitlines()[1][:70]}")
''')

md(r"""
---
## 6. Agentic RAG

두 단계로 답변을 만듭니다.

1. **Draft** — 검색된 근거만 사용해 한국어 초안을 작성
2. **Verify** — 질문이 요구한 핵심 정보(수치·날짜·대상·예외 조건)가 초안에 모두 들어갔는지 근거와 대조
   - 누락/오류가 있으면 `final_answer`를 교정
   - **근거 자체에 답이 없으면** `needs_more_search=True` + 새 검색어를 만들어 **재검색 후 다시 작성** ← Agentic 판단 지점

LLM은 `gpt-6-luna` 단일 모델을 사용하며, 지시문은 영어·답변은 한국어로 생성합니다.
""")

code(r'''
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-6-luna")

llm = ChatOpenAI(
    model=LLM_MODEL,
    reasoning_effort="low",
    max_completion_tokens=2000,
    timeout=30,
    max_retries=1,
)

DRAFT_PROMPT = """You are an admissions counselor at Gachon University (가천대학교).
Answer the question using ONLY the evidence passages below.

Rules:
1. The answer must contain every key fact the question asks for: numbers, dates, eligibility, target groups, conditions and exceptions.
2. If the evidence lists several items or conditions, include ALL of them (a short list is fine).
3. Never add conditions, qualifications or background that is not in the evidence.
4. Copy dates and numbers exactly as written in the evidence (e.g., 2027. 01. 04.(월)).
5. When reading a table, check both the row and column headers before choosing a value.
6. If the evidence does not contain the answer, reply exactly: 제공된 문서에서 확인할 수 없습니다.
7. Write the answer in Korean (2-5 sentences) and end with (출처: 파일명 p.페이지)."""

VERIFY_PROMPT = """You are a strict fact-checker for Gachon University admissions answers.
You receive the question, the evidence passages, and a draft answer.

Tasks:
1. Verify every key fact in the draft against the evidence (numbers, dates, target groups, conditions, exceptions).
2. If the draft missed a key fact that IS in the evidence, list it in missing_facts and rewrite final_answer to include it.
3. If the draft states something the evidence does not support, remove or correct it.
4. Never add a fact that is not in the evidence.
5. If the evidence itself lacks information the question requires, set needs_more_search=True and put a short Korean search_query (wording that appears in the documents) for a second retrieval.
6. final_answer must be in Korean and end with (출처: 파일명 p.페이지)."""


class Verification(BaseModel):
    """검증 단계의 구조화 출력."""

    missing_facts: list[str] = Field(default_factory=list,
                                     description="Key facts/conditions present in the evidence but missing from the draft")
    needs_more_search: bool = Field(default=False,
                                    description="True if the evidence itself lacks information the question asks for")
    search_query: str = Field(default="", description="Short Korean keyword query for a second retrieval")
    final_answer: str = Field(default="", description="Corrected final answer in Korean")


verify_llm = llm.with_structured_output(Verification)


def _draft(question: str, context: str) -> str:
    return llm.invoke([
        ("system", DRAFT_PROMPT),
        ("human", f"[Evidence]\n{context}\n\n[Question]\n{question}"),
    ]).content.strip()


def _verify(question: str, context: str, draft: str) -> Verification:
    try:
        return verify_llm.invoke([
            ("system", VERIFY_PROMPT),
            ("human", f"[Evidence]\n{context}\n\n[Question]\n{question}\n\n[Draft]\n{draft}"),
        ])
    except Exception as exc:  # 구조화 출력 실패 시 초안을 그대로 사용
        print("  (검증 단계 생략:", type(exc).__name__, ")")
        return Verification(needs_more_search=False, final_answer=draft)


def _with_source(answer: str, docs) -> str:
    if "(출처" in answer or not docs:
        return answer
    d = docs[0]
    return f"{answer} (출처: {d.metadata['source']} p.{d.metadata['page']})"


def ask(question: str, top_n: int = 6, verbose: bool = False) -> dict:
    """질문 → 검색 → 초안 → 검증 → (필요 시) 재검색·재작성."""
    t0 = time.perf_counter()
    docs = retrieve(question, top_n=top_n)
    context = format_context(docs)

    draft = _draft(question, context)
    check = _verify(question, context, draft)

    rounds = 1
    answer = check.final_answer or draft

    if check.needs_more_search:
        rounds = 2
        extra = retrieve(check.search_query or question, top_n=top_n)
        merged, seen = [], set()
        for d in docs + extra:
            cid = d.metadata["chunk_id"]
            if cid not in seen:
                seen.add(cid)
                merged.append(d)
        context2 = format_context(merged)

        draft2 = _draft(question, context2)
        check2 = _verify(question, context2, draft2)
        answer = check2.final_answer or draft2
        docs = merged

    answer = _with_source(answer, docs)
    result = {
        "question": question,
        "answer": answer,
        "seconds": time.perf_counter() - t0,
        "rounds": rounds,
        "sources": sorted({f"{d.metadata['source']} p.{d.metadata['page']}" for d in docs}),
    }
    if verbose:
        print(f"[검색 {rounds}회 | {result['seconds']:.2f}s]")
        for s in result["sources"]:
            print("   -", s)
    return result


print(f"LLM: {LLM_MODEL} | 검증 스키마: {Verification.__name__}")
''')

md(r"""
---
## 7. 실행 예시

`ask("질문")` 을 호출하면 답변·응답시간·검색 횟수·출처를 함께 돌려줍니다.
""")

code(r'''
DEMO_QUESTIONS = [
    "2027학년도 수시모집 원서접수 기간은 언제인가요?",
    "가천대학교 입학처 대표 전화번호와 홈페이지 주소를 알려주세요.",
    "2027학년도 정시모집에서 바이오로직스학과의 모집인원은 몇 명인가요?",
]

for question in DEMO_QUESTIONS:
    result = ask(question)
    print("Q.", question)
    print("A.", result["answer"])
    print(f"   ⏱ {result['seconds']:.2f}s · 검색 {result['rounds']}회")
    print()
''')

md(r"""
---
## 8. 설계 노트

**왜 하이브리드 검색인가** — 입학 요강 질문은 “1577-0067”, “2027. 01. 04.(월)”, “농어촌(종합)”처럼
표기 그대로의 숫자·고유명사를 묻는 경우가 많습니다. BM25는 이런 정확 문자열에 강하고,
Dense 임베딩은 “원서 언제부터 받아요?” 같은 구어체 질의에 강합니다. 두 결과를 RRF로 합치면
서로의 약점을 보완할 수 있습니다.

**왜 초안→검증 2단계인가** — 단일 호출에서는 “복수 지원 가능 여부”처럼 조건이 여러 개인 질문에서
일부 조건을 빠뜨리는 오류가 반복되었습니다. 검증 단계에서 근거와 초안을 항목별로 대조하면
누락을 잡아낼 수 있고, 근거에 답이 없을 때만 재검색하므로 불필요한 지연을 만들지 않습니다.

**표 처리** — HWP 표는 병합 셀을 전개해 markdown으로, PDF 표는 pdfplumber로 추출했습니다.
표는 행이 잘리면 의미가 사라지므로 일반 본문과 다른 청킹(헤더 반복, 1,400자)을 적용했습니다.

**한계** — HWP는 페이지 정보가 없어 `p.N`이 문서 내 요소 순서를 뜻하는 근사값입니다.
또한 스캔 이미지 문서는 대상이 아니며(모든 PDF에 텍스트 레이어 존재), 근거에 없는 질문에는
`제공된 문서에서 확인할 수 없습니다.`라고 답하도록 제한했습니다.
""")

# --------------------------------------------------------------------------- #
def make_id():
    return "".join(random.choices(string.ascii_letters + string.digits, k=8))


cells = []
for cell_type, source in CELLS:
    cell = {
        "cell_type": cell_type,
        "metadata": {"id": make_id()},
        "source": [line + "\n" for line in source.split("\n")[:-1]] + [source.split("\n")[-1]],
    }
    if cell_type == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
    cells.append(cell)

notebook = {
    "cells": cells,
    "metadata": {
        "colab": {"provenance": [], "toc_visible": True},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

out = Path(__file__).with_name("202235052_박진성.ipynb")
out.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print("written:", out, f"({out.stat().st_size:,} bytes, {len(cells)} cells)")
