# -*- coding: utf-8 -*-
"""가천대 2027 입학 안내 Agentic RAG - 로컬 모듈 생성기 (v24)."""
import json
import random
import string
import tomllib
from pathlib import Path

CELLS = []


def md(text):
    CELLS.append(("markdown", text.strip("\n")))


def code(text):
    if "%pip install" in text:
        root = Path(__file__).resolve().parent
        locked = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
        versions = {p["name"].lower().replace("_", "-"): p["version"] for p in locked["package"]}
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        pins = []
        for requirement in project["project"]["dependencies"]:
            name = requirement.split(">", 1)[0].split("=", 1)[0].split("<", 1)[0]
            base = name.split("[", 1)[0].lower().replace("_", "-")
            pins.append(f'"{name}=={versions[base]}"')
        text = "# uv.lock에 고정된 런타임 패키지 설치\n%pip install -q " + " ".join(pins)
        text += '\n\nprint("✅ 패키지 설치 완료")'
    CELLS.append(("code", text.strip("\n")))


# --------------------------------------------------------------------------- #
md(r"""
# 2027학년도 가천대학교 입학 안내 Agentic RAG 챗봇

**중간평가 · 생성형 AI 활용** · 202235052 박진성

- **대상 문서**: `dataset.zip` 내 5개 문서 (HWP 1개 + PDF 4개)
- **파이프라인**: HWP/PDF 파싱 → 청킹 → 문맥 헤더·표 행 요약 → 임베딩 + 벡터DB → 계층형 하이브리드 검색 → Agentic RAG 답변
- **원칙**: 답변 근거는 제공된 5개 문서로 한정 (웹 검색·외부 조회 없음), 평가 질문·정답을 코드에 등록하지 않음, 문항당 5초 이내 응답 목표

### 파이프라인

| 단계 | 구성 |
|---|---|
| 파싱 | HWP: `langchain-hwp-hwpx-loader`(elements) + 자체 표 렌더러 / PDF: PyMuPDF(텍스트) + pdfplumber(표) |
| 청킹 | 텍스트 800자(overlap 100), 표 1,400자(헤더 반복) |
| 색인용 문맥 | 모든 청크 앞에 `[문서] 제목 \| p.N \| 표/본문` 헤더, 표는 `라벨: 열=값` **행 요약**을 덧붙임 |
| 인덱스 | 임베딩 Voyage `voyage-4-large` · 청크 인덱스(Chroma cosine + BM25 kiwipiepy) + **페이지 인덱스**(계층 검색용) |
| 검색 | 질문 유형 라우팅 → 원문/키워드 다중 질의 RRF + 희귀어 BM25 + 페이지 prior → 상위 8개 + 이웃·같은 페이지 확장 |
| 답변 | 초안 → 근거 대조 검증 → **근거 부족 시 추가 검색** 후 재작성 / 누락 시 같은 근거로 교정 |

> 실행: 위에서부터 **모두 실행(Runtime → Run all)**. 최초 실행 시 패키지 설치·색인 생성에 2~4분이 걸리며,
> 이 시간은 평가의 응답시간 측정에서 제외되는 구간입니다. 질문은 맨 아래 `ask("질문")` 으로 실행합니다.
""")

md(r"""
---
## 0. 환경 설정

### 0-1. 패키지 설치
""")

code(r"""
# 필요 패키지 설치 (최초 1회, 약 1~2분)
%pip install -q langchain langchain-openai langchain-community langchain-chroma "langchain-hwp-hwpx-loader[distribution]" rank_bm25 kiwipiepy pymupdf pdfplumber voyageai langchain-voyageai python-dotenv

print("✅ 패키지 설치 완료")
""")

md(r"""
### 0-2. API 키

API 키는 **환경변수 → 선택적 `.env` → Colab Secrets(왼쪽 🔑)** 순서로 읽습니다. 환경변수가 `.env`보다 우선합니다.
""")

code(r'''
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path.cwd() / ".env", override=False)


def load_api_key(name: str = "OPENAI_API_KEY"):
    """환경변수(.env는 override=False로 로드) 또는 Colab Secrets에서 읽는다."""
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

# 임베딩은 Voyage AI 사용 (Secrets 이름: VOYAGEAI_API_KEY 또는 VOYAGE_API_KEY)
VOYAGE_API_KEY = load_api_key("VOYAGEAI_API_KEY") or load_api_key("VOYAGE_API_KEY")
if VOYAGE_API_KEY:
    os.environ["VOYAGE_API_KEY"] = VOYAGE_API_KEY

# Chroma 텔레메트리 로그 억제
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

print("OPENAI_API_KEY: 설정됨 ✅")
print("VOYAGE_API_KEY:", "설정됨 ✅" if VOYAGE_API_KEY else
      "없음 ⚠️  → 🔑(Secrets)에 VOYAGEAI_API_KEY 추가 권장 (없으면 OpenAI 임베딩으로 대체 실행)")
''')

md(r"""
---
## 1. 데이터 준비

`dataset.zip`(또는 이미 풀린 폴더)을 찾아 `/content/dataset` 에 5개 문서를 준비합니다.
없으면 Google Drive에서 찾고, 마지막으로 직접 업로드를 요청합니다.
""")

code(r'''
import hashlib
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
PARSER_VERSIONS = {
    ".hwp": "hwp-elements-pyhwp-v1",
    ".pdf": "pymupdf-text-pdfplumber-v1",
}
DATA_DIR = Path(os.environ.get("GACHON_DATA_DIR", "/content/dataset"))


def required_files(directory: Path):
    """필수 원본 5개만 고정 순서로 반환하고 누락 시 파싱 전에 알린다."""
    directory = Path(directory)
    missing = [name for name in REQUIRED if not (directory / name).is_file()]
    if missing:
        raise FileNotFoundError("필수 문서가 없습니다: " + ", ".join(missing))
    return [directory / name for name in REQUIRED]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_document_manifest(directory: Path):
    """필수 원본별 SHA-256, 크기, 파서 구현 버전을 기록한다."""
    manifest = {}
    for path in required_files(directory):
        suffix = path.suffix.lower()
        if suffix not in PARSER_VERSIONS:
            raise ValueError(f"지원하지 않는 문서 확장자: {path.name}")
        manifest[path.name] = {
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
            "parser_version": PARSER_VERSIONS[suffix],
        }
    return manifest


def parse_required_files(directory: Path, parse_hwp, parse_pdf):
    """필수 원본 5개만 해당 파서로 전달한다. 다른 PDF/HWP는 무시한다."""
    parsed = []
    for path in required_files(directory):
        if path.suffix.lower() == ".hwp":
            parsed.extend(parse_hwp(path))
        elif path.suffix.lower() == ".pdf":
            parsed.extend(parse_pdf(path))
    return parsed


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
        print(f"✅ {DATA_DIR} 의 문서 5개를 사용합니다.")
        return DATA_DIR

    if os.environ.get("GACHON_DATA_DIR"):
        raise FileNotFoundError(f"GACHON_DATA_DIR에서 필수 문서 5개를 찾지 못했습니다: {DATA_DIR}")

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
manifest = build_document_manifest(DATA_DIR)
print("문서 manifest (filename → sha256, size_bytes, parser_version):")
for _name, _entry in manifest.items():
    print(f"  - {_name}: {_entry}")
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
    """중복 공백/탭 제거, 'YYYY . MM . DD .' → 'YYYY.MM.DD.'"""
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


raw_docs = parse_required_files(DATA_DIR, parse_hwp, parse_pdf)

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
## 4. 색인용 문맥 청크 (Contextual Retrieval + Table-aware)

청크 원문은 그대로 두고, **색인에 쓰는 텍스트**에만 다음을 덧붙입니다.

- 문맥 헤더: `[문서] 2027학년도 정시 모집요강 | p.7 | 표 | 표제: …`
- 표 행 요약: 다단 헤더를 전개한 뒤 `- ○○학과: 일반전형1=N명, 일반전형2=M명` 처럼 **행 단위 문장**으로 직렬화

임베딩/BM25가 표의 "행 라벨 + 열 이름 + 값" 조합을 직접 매칭할 수 있게 하기 위함입니다.
LLM에는 요약이 아니라 **원문 표**를 근거로 넘깁니다.
""")

code(r'''
DOC_TITLES = {
    "01": "2027학년도 재외국민 모집요강",
    "02": "2027학년도 지역의사선발전형 안내",
    "03": "2027학년도 수시 모집요강",
    "04": "2027학년도 정시 모집요강",
    "05": "2027학년도 수시 면접고사 일정",
}
NUMERIC = re.compile(r"^[\d,./~%()~\-–\s]+$")
SYMBOLS = {"O", "■", "□", "△", "○", "●", "X", "▲", "★", "◉"}
GENERIC_COLS = {"비고", "계열", "연번", "번호", "구분"}


def doc_title(source: str) -> str:
    return DOC_TITLES.get(source[:2], source)


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


def build_contextual_chunks(chunks):
    """색인용 텍스트 = 문맥 헤더 + (표 행 요약) + 원문. 원문은 metadata['raw']에 보관."""
    out, with_summary = [], 0
    for c in chunks:
        src, page, kind = c.metadata["source"], c.metadata["page"], c.metadata["kind"]
        title = doc_title(src)
        raw = c.page_content
        header = f"[문서] {title} | p.{page} | {'표' if kind == 'table' else '본문'}"
        summary = ""
        if kind == "table":
            caption, mode, cols, data = parse_table(raw)
            if caption:
                header += f" | 표제: {caption}"
            summary = row_summary(cols, data, mode)
            with_summary += bool(summary)
        body = header + (("\n[표 행 요약]\n" + summary) if summary else "") + "\n[원문]\n" + raw
        out.append(Document(page_content=body, metadata={**c.metadata, "raw": raw, "title": title}))
    n_table = sum(c.metadata["kind"] == "table" for c in chunks)
    print(f"색인용 청크 {len(out)}개 | 표 청크 {n_table}개 중 행 요약 {with_summary}개")
    return out


chunks_ctx = build_contextual_chunks(chunks)
''')

md(r"""
---
## 5. 벡터 DB + BM25 (청크 인덱스 + 페이지 인덱스)

- **청크 인덱스**: Voyage AI `voyage-4-large`(1024차원) + Chroma(cosine) / BM25(kiwipiepy 형태소: 명사·동사·영문·숫자)
  - Voyage 키가 없는 환경에서는 실행이 멈추지 않도록 OpenAI `text-embedding-3-small`로 대체합니다.
- **페이지 인덱스**(계층 검색): 같은 페이지의 청크를 묶은 페이지 문서를 따로 색인해, 질문과 관련된 페이지를 먼저 찾고
  그 페이지에 속한 청크에 가산점을 줍니다.
- **목차 페이지 자동 탐지**: "숫자 + 제목" 줄의 비율이 높은 본문 페이지를 목차로 판정 (수동 지정 없음)
""")

code(r'''
import time
from collections import defaultdict

from kiwipiepy import Kiwi
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_openai import OpenAIEmbeddings
from langchain_voyageai import VoyageAIEmbeddings

if os.environ.get("VOYAGE_API_KEY"):
    EMBED_MODEL = "voyage-4-large"
    embeddings = VoyageAIEmbeddings(model=EMBED_MODEL, voyage_api_key=os.environ["VOYAGE_API_KEY"])
else:
    EMBED_MODEL = "text-embedding-3-small"
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)

kiwi = Kiwi()
ALLOWED_TAGS = {"NNG", "NNP", "NNB", "VV", "VA", "XR", "SL", "SN"}


def korean_tokenizer(text: str):
    return [t.form for t in kiwi.tokenize(text) if t.tag in ALLOWED_TAGS]


t0 = time.perf_counter()
vectordb = Chroma.from_documents(
    documents=chunks_ctx,
    embedding=embeddings,
    collection_name=f"gachon_chunks_{int(time.time())}",
    collection_metadata={"hnsw:space": "cosine"},
)
dense_retriever = vectordb.as_retriever(search_kwargs={"k": 20})
bm25_retriever = BM25Retriever.from_documents(chunks_ctx, preprocess_func=korean_tokenizer, k=20)
CHUNK_INDEX = {c.page_content: i for i, c in enumerate(chunks_ctx)}

# ---- 페이지 인덱스 (계층 검색) ----
groups = defaultdict(list)
for c in chunks_ctx:
    groups[(c.metadata["source"], c.metadata["page"])].append(c)

page_docs = []
for (src, page), cs in sorted(groups.items()):
    body, used = [], 0
    for c in cs:
        t = c.metadata["raw"].strip()[: max(0, 3200 - used)]
        body.append(t)
        used += len(t)
        if used >= 3200:
            break
    page_docs.append(Document(page_content=f"[{doc_title(src)} p.{page}]\n" + "\n".join(body),
                              metadata={"source": src, "page": page}))

page_db = Chroma.from_documents(
    documents=page_docs,
    embedding=embeddings,
    collection_name=f"gachon_pages_{int(time.time())}",
    collection_metadata={"hnsw:space": "cosine"},
)
page_dense = page_db.as_retriever(search_kwargs={"k": 8})
page_bm25 = BM25Retriever.from_documents(page_docs, preprocess_func=korean_tokenizer, k=8)

# ---- 목차 페이지 자동 탐지 ----
TOC_PAGES = {}
for c in chunks_ctx:
    if c.metadata["kind"] != "text":
        continue
    lines = [l.strip() for l in c.metadata["raw"].splitlines() if l.strip()]
    n_num = sum(bool(re.match(r"^\d{1,3}\s+\S", l)) for l in lines)
    if n_num >= 5 and n_num / max(1, len(lines)) >= 0.3:
        TOC_PAGES.setdefault(c.metadata["source"][:2], set()).add(c.metadata["page"])

print(f"청크 인덱스 {vectordb._collection.count():,}개 | 페이지 인덱스 {len(page_docs)}개 | "
      f"임베딩 {EMBED_MODEL} | {time.perf_counter() - t0:.1f}s")
print("목차 페이지(자동 탐지):", {k: sorted(v) for k, v in TOC_PAGES.items()})
''')

md(r"""
---
## 6. 질의 분석 · 라우팅 (Adaptive RAG Routing)

질문을 형태소 분석해 **검색 키워드**(일반어 제거 + 구어체→문서 용어 치환)를 만들고,
질문 유형(`page / schedule / table / procedure / eligibility / list / general`)과 대상 문서를 규칙으로 판정합니다.
유형에 따라 검색 질의 접미어, 표/본문 가중치, 전용 도구(목차 조회·면접 일정표)가 달라집니다.
규칙에 걸리지 않으면 `general`로 처리합니다.
""")

code(r'''
GENERIC = {"무엇", "분", "얼마", "월", "사람", "이", "나", "경우", "저거", "년", "너", "학생들",
           "때문", "어디", "저", "친구", "거", "이거", "제", "등", "우리", "것", "언제", "학생",
           "때", "그", "정도", "뭐", "일", "사람들", "좀", "수", "애들", "그거"}

# 구어체·일상어 → 모집요강 용어
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
    "전화": "Tel 연락처", "홈페이지": "www 누리집",
    "새로 생": "신설", "새로 만": "신설", "신설된": "신설",
}

SCHEDULE_RE = r"(면접.*(일정|일정표|날짜|시간)|(일정|일정표).*면접)"
ROUTE_PATTERNS = [
    # '홈페이지'는 페이지 번호 질문이 아니고, '몇 장'은 '사진 몇 장'처럼 수량 질문이므로 제외
    ("page", r"(몇\s*쪽|(?<!홈)페이지|쪽에)"),
    # '모집/선발'은 '정시모집', '지역의사선발전형'처럼 거의 모든 질문에 들어가므로 표 신호에서 제외
    ("table", r"(몇\s*명|인원|정원|명까지|명씩|비율|점수|등급|컷|몇\s*점|감점)"),
    ("procedure", r"(어떻게|신청|제출|절차|방법|해야\s*하|어디서)"),
    ("eligibility", r"(자격|조건|대상|가능|되나요|될까|수\s*있나|받을\s*수)"),
    ("list", r"(어디어디|무엇무엇|종류|예시|포함|목록|어떤\s*게)"),
]
ROUTE_SUFFIX = {"table": " 모집인원 표", "page": " 목차 페이지", "procedure": " 신청 방법 절차",
                "eligibility": " 지원자격 조건", "list": " 목록", "general": "", "schedule": " 면접 일정"}

DOC_KEYWORDS = [
    ("05", SCHEDULE_RE),
    ("04", r"정시"),
    ("03", r"수시"),
    ("02", r"지역\s*의사"),
    ("01", r"(재외국민|외국)"),
]


def search_keywords(q: str, k: int = 10) -> str:
    """질문 → 검색 키워드 (일반어 제거 + 동의어 치환)."""
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


def route_query(q: str) -> str:
    if re.search(SCHEDULE_RE, q):
        return "schedule"
    for name, pat in ROUTE_PATTERNS:
        if re.search(pat, q):
            return name
    return "general"


def target_doc(q: str):
    for prefix, pat in DOC_KEYWORDS:
        if re.search(pat, q):
            return prefix
    return None


def dept_terms(q: str):
    return list(dict.fromkeys(re.findall(r"([가-힣A-Za-z0-9·]{2,})\s*(?:학과|학부|전공)", q)))


def overlap_score(doc, kw: str) -> int:
    toks = [t for t in kw.split() if len(t) > 1]
    text = doc.metadata.get("raw", doc.page_content)
    return sum(text.count(t) for t in toks)


for _q in ["입학처 홈페이지 주소를 알려주세요.",
           "정시 원서접수는 몇 월 며칠부터 시작하나요?",
           "정시 모집요강에서 원서접수 안내는 몇 페이지에 있나요?",
           "정시로 간호학과는 몇 명 뽑나요?"]:
    print(f"[{route_query(_q):11s}| doc={target_doc(_q)}] {_q}  →  {search_keywords(_q)}")
''')

md(r"""
---
## 7. 검색 (Hierarchical + 다중 질의 RRF) 과 도구

1. 질의 4종을 RRF로 융합: 원문(BM25·Dense) + 키워드(BM25) + 키워드+유형 접미어(Dense)
2. **희귀어 BM25**: 키워드 중 코퍼스 빈도가 가장 낮은 단어로 한 번 더 검색 (RRF 희석 방지)
3. **페이지 prior**: 페이지 인덱스 상위 5페이지에 속한 청크 가산
4. 유형별 가중: 대상 문서 ×1.12, 표 질문→표 청크 ×1.15, 절차·자격 질문→본문 ×1.12, 학과명이 있으면 해당 표 주입
5. 상위 8개 + 상위 2개의 앞뒤 청크 + **같은 페이지의 다른 청크 1개** (청크 경계에서 잘린 문장 회수)

도구:
- `toc_lookup`: "몇 쪽/페이지" 질문은 자동 탐지한 목차를 파싱해 결정적으로 답함
- `retrieve_multi`: "A는 언제이며, B는 무엇인가요?"처럼 **여러 항목을 묻는 질문**은 절 단위 하위 질의(여러 문서를 함께 물으면 문서별 질의 포함)로 나눠 병렬 검색한 뒤 근거를 합침
- `retrieve_more`: 초안이 "근거를 찾지 못했다"고 판단하면 키워드 질의로 **추가 검색**해 근거를 보강
""")

code(r'''
from concurrent.futures import ThreadPoolExecutor, wait


def rrf_fuse(result_lists, weights, rrf_k: int = 60):
    scores, docs = {}, {}
    for w, result in zip(weights, result_lists):
        for rank, d in enumerate(result, 1):
            key = d.page_content
            scores[key] = scores.get(key, 0.0) + w / (rrf_k + rank)
            docs[key] = d
    return scores, docs


def page_prior(query: str, top_pages: int = 5):
    s, d = rrf_fuse([page_bm25.invoke(query), page_dense.invoke(query)], [1.0, 1.0], rrf_k=40)
    ordered = sorted(s, key=s.get, reverse=True)[:top_pages]
    return {(d[k].metadata["source"], d[k].metadata["page"]): i + 1 for i, k in enumerate(ordered)}


def rare_terms(kw: str, n: int = 1):
    toks = [t for t in kw.split() if len(t) >= 2 and not t.isdigit()]
    toks.sort(key=lambda t: sum(t in c.metadata["raw"] for c in chunks_ctx))
    return toks[:n]


def inject(scores, docs, kw, pool, top_score, factor=1.05, limit=2):
    """경로별 필수 근거(목차/일정표)를 후보에 주입."""
    ranked = sorted(pool, key=lambda d: overlap_score(d, kw), reverse=True)[:limit]
    for d in ranked:
        scores[d.page_content] = max(scores.get(d.page_content, 0.0), top_score * factor)
        docs[d.page_content] = d


def table_dept_boost(scores, docs, query, kw, tdoc, top_score):
    """질문에 학과명이 있으면 대상 문서의 해당 학과 표 청크를 상위로 올린다."""
    terms = dept_terms(query)
    if not terms:
        return
    cands = []
    for c in chunks_ctx:
        if c.metadata["kind"] != "table" or not c.metadata["source"].startswith(tdoc):
            continue
        if not any(t in c.metadata["raw"] for t in terms):
            continue
        summary_hit = sum(t in c.page_content.split("[원문]")[0] for t in terms)
        cands.append((overlap_score(c, kw) + 5 * summary_hit, c))
    cands.sort(key=lambda x: x[0], reverse=True)
    for _, c in cands[:2]:
        scores[c.page_content] = max(scores.get(c.page_content, 0.0), top_score * 1.18)
        docs[c.page_content] = c


def _retrieve_impl(query: str, top_n: int = 8, expand_top: int = 2, rrf_k: int = 60):
    route = route_query(query)
    kw = search_keywords(query)
    kw_route = (kw + ROUTE_SUFFIX[route]).strip()
    lists = [bm25_retriever.invoke(query), dense_retriever.invoke(query),
             bm25_retriever.invoke(kw or query), dense_retriever.invoke(kw_route or query)]
    weights = [1.0, 1.0, 1.15, 1.15]

    rare = rare_terms(kw, 1)
    if rare and sum(rare[0] in c.metadata["raw"] for c in chunks_ctx) < 80:
        lists.append(bm25_retriever.invoke(rare[0]))
        weights.append(1.0)

    scores, docs = rrf_fuse(lists, weights, rrf_k)
    prior = page_prior(kw_route or query)
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
    if route == "page" and tdoc in TOC_PAGES:
        pool = [c for c in chunks_ctx
                if c.metadata["source"].startswith(tdoc) and c.metadata["page"] in TOC_PAGES[tdoc]]
        inject(scores, docs, kw, pool, top_score, factor=1.12, limit=2)
    if route == "schedule":
        pool = [c for c in chunks_ctx if c.metadata["source"].startswith("05")]
        inject(scores, docs, kw, pool, top_score, factor=1.15, limit=3)

    top = [docs[k] for k in sorted(scores, key=scores.get, reverse=True)[:top_n]]
    # 원문 질의의 Dense 1위는 BM25 목록 수에 밀려 탈락하지 않도록 항상 포함
    dense_top = lists[1][0] if lists[1] else None
    if dense_top is not None and all(d.page_content != dense_top.page_content for d in top):
        top[-1] = dense_top
    out, seen = [], set()
    for n, d in enumerate(top):
        if d.page_content not in seen:
            out.append(d)
            seen.add(d.page_content)
        if n >= expand_top:
            continue
        i = CHUNK_INDEX[d.page_content]
        for j in range(max(0, i - 1), min(len(chunks_ctx), i + 2)):
            c = chunks_ctx[j]
            if c.metadata["source"] == d.metadata["source"] and c.page_content not in seen:
                out.append(c)
                seen.add(c.page_content)

    # 같은 페이지의 다른 청크 중 질문과 가장 관련 있는 1개 (잘린 뒷문장 회수)
    for d in top[:2]:
        sibs = [c for c in chunks_ctx
                if c.metadata["source"] == d.metadata["source"]
                and c.metadata["page"] == d.metadata["page"] and c.page_content not in seen]
        if sibs:
            best = max(sibs, key=lambda c: overlap_score(c, kw))
            if overlap_score(best, kw) > 0:
                out.append(best)
                seen.add(best.page_content)
    return out, route


def remaining(deadline):
    return max(0.0, deadline - time.perf_counter())


def deadline_result(future, deadline):
    try:
        left = remaining(deadline)
        if left <= 0:
            raise TimeoutError("request deadline exhausted")
        return future.result(timeout=left)
    except BaseException:
        future.cancel()
        raise


def retrieve(query: str, top_n: int = 8, expand_top: int = 2, rrf_k: int = 60, deadline=None):
    if deadline is None:  # index warm-up / direct interactive retrieval
        deadline = time.perf_counter() + 18.0
    if remaining(deadline) <= 0:
        raise TimeoutError("search deadline exhausted")
    return deadline_result(_search_pool.submit(_retrieve_impl, query, top_n, expand_top, rrf_k), deadline)


def retrieve_more(question: str, docs, extra_n: int = 4, deadline=None):
    """추가 검색: 질문 대신 키워드 질의로 다시 찾아, 기존 근거에 없는 청크를 최대 extra_n개 덧붙인다."""
    if deadline is None:
        deadline = time.perf_counter() + 18.0
    if remaining(deadline) < MIN_STAGE_SECONDS:
        return docs, 0
    kw = search_keywords(question) or question
    seen = {d.page_content for d in docs}
    extra, _ = retrieve(kw, top_n=extra_n + 2, expand_top=0, deadline=deadline)
    new = [d for d in extra if d.page_content not in seen][:extra_n]
    return docs + new, len(new)


# ---- 복합 질문 분해 검색 (Query Decomposition) ----
CLAUSE_SPLIT = re.compile(r"\s*그리고\s+|(?<=[가-힣])(?:이며|이고|하며|되며|으며|며|고),\s*|\?\s+")
DOC_TERMS = {"01": "재외국민", "02": "지역의사", "03": "수시모집", "04": "정시모집", "05": "수시 면접 일정"}
_search_pool = ThreadPoolExecutor(max_workers=6)


def target_docs(q: str):
    return [p for p, pat in DOC_KEYWORDS if re.search(pat, q)]


def sub_queries(q: str, max_n: int = 5):
    """'A는 언제이며, B는 무엇인가요?'처럼 여러 항목을 묻는 질문을 절 단위 하위 질의로 나눈다.
    여러 문서(재외국민·수시·정시 등)를 함께 묻는 질문은 문서별 질의도 만든다."""
    parts = [p.strip(" ,") for p in CLAUSE_SPLIT.split(q) if p and len(p.strip(" ,")) >= 8]
    docs = target_docs(q)
    if len(parts) < 2 and len(docs) < 2:
        return []
    anchors = re.findall(r"'([^']+)'", q) + dept_terms(q)
    anchors += [m.group(0) for _, pat in DOC_KEYWORDS for m in [re.search(pat, q)] if m]
    subs = []
    for p in parts:
        extra = [a for a in dict.fromkeys(anchors) if a not in p]
        subs.append((p + " " + " ".join(extra)).strip())
    if len(docs) >= 2:
        kw = search_keywords(q)
        subs += [f"{DOC_TERMS[d]} {kw}" for d in docs]
    return subs[:max_n]


def retrieve_multi(question: str, docs, per_sub: int = 3, cap: int = 20, deadline=None):
    """하위 질의별로 병렬 검색해, 기존 근거에 없는 청크를 질의당 per_sub개씩 덧붙인다."""
    if deadline is None:
        deadline = time.perf_counter() + 18.0
    subs = sub_queries(question)
    if not subs:
        return docs, 0
    if remaining(deadline) < MIN_STAGE_SECONDS:
        return docs, 0
    seen = {d.page_content for d in docs}
    new = []
    futures = [_search_pool.submit(_retrieve_impl, s, top_n=per_sub + 2, expand_top=0) for s in subs]
    done, pending = wait(futures, timeout=remaining(deadline))
    for fut in pending:
        fut.cancel()
    # Preserve query order among completed results, without waiting for stragglers.
    for fut in futures:
        if fut not in done:
            continue
        try:
            res, _ = fut.result(timeout=0)
        except Exception:
            continue
        added = 0
        for d in res:
            if d.page_content in seen:
                continue
            new.append(d)
            seen.add(d.page_content)
            added += 1
            if added >= per_sub:
                break
    return (docs + new)[:cap], len(subs)


def toc_lookup(question: str, tdoc):
    """목차 페이지를 파싱해 '몇 쪽/페이지' 질문에 답한다 (LLM 미호출)."""
    if not tdoc or tdoc not in TOC_PAGES:
        return None
    kw = search_keywords(question)
    skip = {"페이지", "목차", "요강", "모집", "전형", "안내", "정시모집", "수시모집", "대학"}
    toks = [t for t in kw.split() if len(t) >= 2 and t not in skip]
    best = (0, None, None, None)
    for c in chunks_ctx:
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
            "source": best[3].metadata["source"], "doc": best[3]}


_q = "정시모집 실기고사 준비물은 무엇인가요?"
_docs, _route = retrieve(_q)
print(f"[{_route}] {_q}")
for d in _docs[:5]:
    print(f"   - {d.metadata['source'][:24]} p.{d.metadata['page']} ({d.metadata['kind']})")
''')

md(r"""
---
## 8. 근거 대조 검증 (Evidence-grounded Verification)

LLM 초안을 규칙으로 근거와 대조해 **교정이 필요한지** 판단합니다.

| 검사 | 내용 |
|---|---|
| grounding | 숫자·날짜·개체의 존재와 같은 문장/행 안의 개체·값 연결, 전체 파일명·페이지 인용 일치 검사 |
| 목록 충실성 | 목록을 묻는 질문에서 근거의 쉼표 항목이 답변에 빠졌는지 |
| 조건문 | 답변을 뒷받침하는 청크의 `~경우/다만/반드시` 조건 문장이 반영됐는지 |
| 주변 세부정보 | 답변에 쓴 날짜·숫자와 같은 표 행 / 같은 부정 문장(불가·제외)의 세부사항이 빠졌는지 |

`heuristic_score`는 교정 판단에 참고하는 규칙 기반 점수이며, 정답 가능성을 나타내지 않습니다.
""")

code(r'''
CITE_RE = re.compile(r"\(출처:\s*([^)]*?)\s*p\.\s*(\d+)\)")
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
DATE_RE = re.compile(r"\d{1,2}\s*월\s*\d{1,2}\s*일")
ENT_RE = re.compile(r"[가-힣A-Za-z0-9·]+(?:학과|학부|전공|전형|대학|고등학교|중학교)")
COND_MARK = re.compile(r"(경우|해야|충족|인정|간주|다만|반드시)")
LIST_INTENT = re.compile(r"((뭐|무엇|어떤).{0,12}(있|지원|혜택|항목|종류)|목록|종류|어디어디|무엇무엇)")
NEG_RE = re.compile(r"(불가|반환하지|제외|없음|않|미포함|불허)")
DATE_CELL = re.compile(r"^[\d.,~()\s월화수목금토일]+$")
NOT_FOUND_RE = re.compile(r"(확인할 수 없|규정이 없|안내되어 있지 않|나와 있지 않|제공된 (자료|문서|근거)에는.{0,20}없)")

GENERIC_DETAILS = {"경우에는", "모집", "사항", "전형", "절차", "가능", "대학", "2027학년도", "기간",
                   "본교", "서류", "입학", "경우", "결과", "방법", "학생", "내용", "지원", "정도",
                   "평가", "제출", "지원자", "이하", "신청", "모집요강", "안내", "관련", "이상",
                   "때문", "확인", "해당"}
DETAIL_STOP = {"경우에는", "확인", "숙지", "변경", "입력", "가능", "모집요강", "안내", "작성",
               "정확", "경우", "내용"}


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


def ground_answer(answer, docs):
    evidence = _norm("\n".join(d.metadata.get("raw", d.page_content) for d in docs))
    body = _strip_cite(answer)
    nums = NUM_RE.findall(body)
    dates = DATE_RE.findall(body)
    ents = [e for e in ENT_RE.findall(body) if len(e) >= 3]
    num_ok = sum(_norm(n) in evidence for n in nums) / len(nums) if nums else 1.0
    date_ok = sum(_norm(d) in evidence for d in dates) / len(dates) if dates else 1.0
    ent_ok = sum(_norm(e) in evidence for e in ents) / len(ents) if ents else 1.0
    cites = CITE_RE.findall(answer)
    valid = sum(any(_filename_norm(d.metadata["source"]) == _filename_norm(f) and str(d.metadata["page"]) == p
                    for d in docs) for f, p in cites)
    cite_ok = valid / len(cites) if cites else 0.0
    # A value and an entity must occur in one evidence sentence/line/table row.
    # Finding each independently elsewhere in a document does not establish the fact.
    units = [_norm(unit) for d in docs
             for unit in fact_units(d.metadata.get("raw", d.page_content))]
    pairs = [(entity, value) for unit in fact_units(body)
             for entity in ENT_RE.findall(unit)
             for value in NUM_RE.findall(unit)]
    unsupported = [(entity, value) for entity, value in pairs
                   if not any(_norm(entity) in unit and
                              _norm(value) in NUM_RE.findall(unit) for unit in units)]
    pair_ok = 1.0 - len(unsupported) / len(pairs) if pairs else 1.0
    score = 0.40 * num_ok + 0.20 * date_ok + 0.25 * ent_ok + 0.15 * cite_ok
    score *= 0.5 + 0.5 * pair_ok
    return {"score": round(score, 3), "num_ok": round(num_ok, 3), "date_ok": round(date_ok, 3),
            "ent_ok": round(ent_ok, 3), "cite_ok": round(cite_ok, 3),
            "pair_ok": round(pair_ok, 3), "unsupported_pairs": unsupported,
            "not_found": bool(NOT_FOUND_RE.search(body))}


def _filename_norm(name):
    return _norm(__import__("unicodedata").normalize("NFC", name)).casefold()


def fact_units(text):
    # Do not split at decimal/date dots or table cell delimiters.
    return [unit.strip() for unit in re.split(r"\n|(?<=[.!?。])\s+(?=[^\d])|;", text) if unit.strip()]


def make_heuristic_score(route, kw, docs, g):
    cov = lexical_coverage(kw, docs)
    route_bonus = {"table": 0.06, "page": 0.05, "schedule": 0.05}.get(route, 0.0)
    heuristic_score = 0.50 * g["score"] + 0.35 * cov + 0.15 * (1.0 if g["cite_ok"] >= 0.99 else 0.5) + route_bonus
    if g["not_found"]:
        heuristic_score -= 0.25
    return round(max(0.0, min(1.0, heuristic_score)), 3), round(cov, 3)


def norm_dates(text):
    out = set(re.findall(r"\d{4}\.\d{2}\.\d{2}", text))
    for y, m, d in re.findall(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", text):
        out.add(f"{y}.{int(m):02d}.{int(d):02d}")
    return out


def iter_sentences(raw):
    for sent in re.split(r"(?<=[.다])\s+|\n", raw.replace("|", "\n")):
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
    citations = {(_filename_norm(f), int(p)) for f, p in CITE_RE.findall(answer)}
    focus = [d for d in docs if (_filename_norm(d.metadata["source"]), int(d.metadata["page"])) in citations]
    return (focus or docs)[:4]


def missing_list_items(question, answer, docs, max_items=4):
    """목록을 묻는 질문: 근거 문장의 쉼표 항목 중 답변에 없는 것."""
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


def missing_conditions(answer, docs, max_sent=1):
    """답변을 뒷받침하는 청크 안의 조건 문장이 답변에 반영됐는지."""
    ans_toks = _content_tokens(answer)
    scored = []
    for d in docs[:6]:
        c_toks = _content_tokens(d.metadata.get("raw", ""))
        if c_toks:
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
            if len(s_toks) >= 3 and len(s_toks & ans_toks) / len(s_toks) < 0.5:
                missing.append(sent)
        if len(missing) >= max_sent:
            break
    return missing[:max_sent]


def missing_neighbor_details(answer, docs, max_items=2):
    """답변에 쓴 날짜·숫자와 같은 표 행, 또는 같은 부정 문장의 세부정보 중 빠진 것."""
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
            score = sum(len(t) for t in _content_tokens(s) & ans_toks)
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


print("검증 함수 준비 완료")
''')

md(r"""
---
## 9. Agentic RAG 답변

```
질문 ─▶ 라우팅 ─┬─ page + 목차 일치 ──▶ toc_lookup (LLM 0회)
                └─ retrieve (+ 복합 질문이면 retrieve_multi) ─▶ 초안(LLM) ─▶ 근거 대조 검증
                                    ├─ "근거에 없음" 판단 ─▶ retrieve_more(추가 검색) ─▶ 재작성(LLM)
                                    ├─ 누락·불일치 발견 ───▶ 같은 근거로 교정(LLM)
                                    └─ 통과 ──────────────▶ 초안 반환
```

- **추가 검색 판단**: 초안이 "확인할 수 없다/규정이 없다"고 답하면 근거가 부족하다고 보고 키워드 질의로 다시 검색합니다.
- **시간 가드**: 교정은 9초 이전에만 시작하고, 모든 LLM 호출에 남은 시간 기반 타임아웃을 걸어
  평가 최대 대기시간(20초)을 넘기지 않도록 합니다. 교정이 시간 안에 끝나지 않으면 초안을 반환합니다.
- LLM은 `gpt-6-luna` 단일 모델(`reasoning_effort="low"`), 지시문은 영어·답변은 한국어입니다.
""")

code(r'''
from concurrent.futures import ThreadPoolExecutor

from langchain_openai import ChatOpenAI

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-6-luna")
llm = ChatOpenAI(model=LLM_MODEL, reasoning_effort="low", max_completion_tokens=2000,
                 timeout=20, max_retries=0)

DRAFT_PROMPT = """You are an admissions counselor at Gachon University. Answer using ONLY the evidence documents.

Procedure:
1. Scan EVERY evidence passage for sentences containing the key terms of the question, including passages near the end.
2. Collect all facts that answer any part of the question.
3. Write the answer from those facts only.

Rules:
- Include EVERY key fact the question asks for (numbers, dates, targets, conditions, exceptions), and also closely related details stated in the same evidence sentence.
- If the evidence lists several conditions or exceptions, list ALL of them, including additional requirements stated in the same passage.
- Copy the exact wording of list items instead of shortening or paraphrasing them.
- For tables, align the row label and column headers by position. Never swap columns.
- For numbered or repeated column headers, count every cell from the left, including dashes, and match each value to its column.
  Example: header "A B C D" + row "- - 3 7" means C=3 and D=7.
- Keep the qualifiers attached to each fact you report: parenthetical notes, footnotes (※), scope conditions, units, and who is responsible or who decides.
- If the question has several parts, answer every part in order and number them (①, ②, ③ …); if one part is truly not in the evidence, say only that part cannot be confirmed in the documents.
- Never add facts or qualifiers that are not in the evidence.
- If only some parts are supported, answer those parts and mark only the unsupported parts exactly as "제공된 문서에서 확인할 수 없습니다".
- If the question asks which page, give the page number exactly as listed in the table of contents.
- Write in Korean, as long as needed to cover every part (usually 2-8 sentences), and end with (출처: 파일명 p.페이지)."""

REPAIR_PROMPT = """You are a strict fact-checker. Rewrite the draft using ONLY the evidence.

- Search every passage, including the last one, before deciding something is missing; never invent missing information.
- Remove any number, date, or name not present in the evidence.
- Add every key fact from the evidence that the question asks for but the draft omitted, including additional requirements in the same passage.
- Copy list items exactly as written in the evidence, and keep parenthetical notes and scope conditions attached to each fact.
- If a part of the question is truly not in the evidence, say only that part cannot be confirmed; do not invent it.
- Answer the supported parts and mark only unsupported parts exactly as "제공된 문서에서 확인할 수 없습니다".
- Keep it Korean, covering every part of the question, ending with (출처: 파일명 p.페이지)."""

HARD_LIMIT = 18.0          # 평가 최대 대기 20초보다 여유를 둔 상한
REPAIR_START_LIMIT = 9.0   # 이 시간 이후에는 교정·추가 검색을 시작하지 않음
MIN_STAGE_SECONDS = 1.0    # 새 검색/교정을 시작할 최소 잔여 시간
FALLBACK = "죄송합니다. 일시적인 오류로 답변을 생성하지 못했습니다. 다시 질문해 주세요."
_pool = ThreadPoolExecutor(max_workers=4)


def _call_llm(system: str, human: str, deadline: float) -> str:
    """남은 시간 안에 끝나지 않으면 TimeoutError를 낸다."""
    left = remaining(deadline)
    if left <= 0:
        raise TimeoutError("LLM deadline exhausted")
    fut = _pool.submit(llm.invoke, [("system", system), ("human", human)], timeout=left)
    answer = deadline_result(fut, deadline).content.strip()
    if not answer:
        raise ValueError("empty LLM response")
    return answer


def _context(docs) -> str:
    return "\n\n".join(f"[근거 {i}] {d.metadata['source']} p.{d.metadata['page']}\n{d.metadata['raw']}"
                       for i, d in enumerate(docs, 1))


def ask(question: str, return_meta: bool = False):
    """질문 → (목차 도구 | 검색 → 초안 → 검증 → 추가 검색/교정) → 한국어 답변."""
    t0 = time.perf_counter()
    deadline = t0 + HARD_LIMIT
    elapsed = lambda: time.perf_counter() - t0
    route, tdoc = route_query(question), target_doc(question)
    meta = {"route": route, "action": "none", "extra_docs": 0, "sub_queries": 0,
            "timings": {"search": 0.0, "draft": 0.0, "repair": 0.0}, "events": []}

    def finish(answer, docs, g=None, heuristic_score=None, cov=None):
        if not return_meta:
            return answer
        return {**meta, "answer": answer, "sec": elapsed(), "ground": g,
                "heuristic_score": heuristic_score, "cov": cov,
                "docs": [(d.metadata["source"], d.metadata["page"]) for d in docs],
                "evidence": [{"source": d.metadata["source"], "page": d.metadata["page"],
                              "kind": d.metadata.get("kind", "text"),
                              "chunk": d.metadata.get("raw", d.page_content)[:200]} for d in docs]}

    def may_refine():
        return elapsed() < REPAIR_START_LIMIT and remaining(deadline) >= MIN_STAGE_SECONDS

    # (1) 페이지 질문 → 목차 도구
    if route == "page" and tdoc:
        hit = toc_lookup(question, tdoc)
        if hit:
            topic = hit["title"]
            answer = (f"{topic}{_particle(topic)} {doc_title(hit['source'])} {hit['page']}페이지에 "
                      f"안내되어 있습니다. (출처: {hit['source']} p.{hit['doc_page']})")
            meta["route"] = "page_lookup"
            return finish(answer, [hit["doc"]], ground_answer(answer, [hit["doc"]]), 0.99, 1.0)

    # (2) 검색 (복합 질문이면 하위 질의별 검색을 합침) → 초안
    search_t0 = time.perf_counter()
    docs = []
    try:
        docs, route = retrieve(question, deadline=deadline)
        docs, n_sub = retrieve_multi(question, docs, deadline=deadline)
        meta["sub_queries"] = n_sub
    except Exception as exc:
        meta["events"].append({"stage": "search", "error": type(exc).__name__})
        if not docs:
            meta["action"] = "search_timeout" if isinstance(exc, TimeoutError) else "search_error"
            meta["timings"]["search"] = time.perf_counter() - search_t0
            return finish(FALLBACK, docs)
    meta["timings"]["search"] = time.perf_counter() - search_t0
    kw = search_keywords(question)
    ctx = _context(docs)
    draft_t0 = time.perf_counter()
    try:
        answer = _call_llm(DRAFT_PROMPT, f"[Evidence]\n{ctx}\n\n[Question]\n{question}",
                           deadline)
    except Exception as exc:
        meta["events"].append({"stage": "draft", "error": type(exc).__name__})
        meta["action"] = "draft_timeout" if isinstance(exc, TimeoutError) else "draft_error"
        meta["timings"]["draft"] = time.perf_counter() - draft_t0
        return finish(FALLBACK, docs)
    meta["timings"]["draft"] = time.perf_counter() - draft_t0
    g = ground_answer(answer, docs)

    # (3) 판단: 근거 부족 → 추가 검색 / 누락·불일치 → 같은 근거로 교정
    hints = []
    if g["not_found"]:
        meta["action"] = "research"
        if may_refine():
            extra_t0 = time.perf_counter()
            try:
                docs, n_new = retrieve_more(question, docs, deadline=deadline)
                meta["extra_docs"] = n_new
                ctx = _context(docs)
            except Exception as exc:
                meta["action"] = "research_timeout" if isinstance(exc, TimeoutError) else "research_error"
                meta["events"].append({"stage": "research", "error": type(exc).__name__})
            meta["timings"]["search"] += time.perf_counter() - extra_t0
        else:
            meta["action"] = "research_skipped"
    else:
        items = missing_list_items(question, answer, docs)
        conds = missing_conditions(answer, docs)
        neigh = missing_neighbor_details(answer, docs)
        if items:
            hints.append("[Exact items to include]\n" + ", ".join(items))
        if conds:
            hints.append("[Conditions that must be reflected]\n" + "\n".join(conds))
        if neigh:
            hints.append("[Related details from the same evidence row/sentence]\n" + ", ".join(neigh))
        if g.get("unsupported_pairs"):
            hints.append("[Entity/value pairs to check within one evidence sentence or row]\n"
                         + str(g["unsupported_pairs"]))
        if hints or g["score"] < 0.78 or g["cite_ok"] < 1.0 or g.get("pair_ok", 1.0) < 1.0:
            meta["action"] = "repair"

    if meta["action"] in ("research", "repair"):
        if may_refine():
            repair_t0 = time.perf_counter()
            meta["events"].append({"stage": "repair", "trigger": meta["action"],
                                   "unsupported_pairs": g.get("unsupported_pairs", [])})
            try:
                repaired = _call_llm(REPAIR_PROMPT,
                                   f"[Evidence]\n{ctx}\n\n[Question]\n{question}\n\n[Draft]\n{answer}\n\n"
                                   + "\n\n".join(hints), deadline)
                answer = repaired
                g = ground_answer(answer, docs)
            except Exception as exc:
                meta["action"] += "_timeout" if isinstance(exc, TimeoutError) else "_error"
                meta["events"].append({"stage": "repair", "error": type(exc).__name__})
            meta["timings"]["repair"] = time.perf_counter() - repair_t0
        else:
            meta["action"] += "_skipped"

    heuristic_score, cov = make_heuristic_score(route, kw, docs, g)
    return finish(answer, docs, g, heuristic_score, cov)


# 연결 예열 (색인 구축 구간에 포함, 첫 질문의 연결 지연 제거)
_ = llm.invoke("ping")
_ = retrieve("가천대학교 입학 안내")
print(f"LLM: {LLM_MODEL} | 준비 완료")
''')

md(r"""
---
## 10. 실행 예시

`ask("질문")` 은 답변 문자열을 돌려줍니다. (`ask(q, return_meta=True)` 는 경로·판단·시간·근거를 함께 반환)

아래는 공식 `sample.json` 의 **질문** 3개입니다. (정답은 코드에 넣지 않았습니다.)
""")

code(r'''
DEMO_QUESTIONS = [
    "가천대학교 대표 전화번호는 무엇인가요?",
    "정시 원서접수는 몇 월 며칠부터 시작하고, 마감일과 마감시각은 언제인가요?",
    "2027학년도 재외국민 전형의 인터넷 원서접수에 사용할 증명사진은 최근 몇 개월 이내 사진이어야 하며, 어떤 파일 형식으로 준비해야 하나요?",
]

for question in DEMO_QUESTIONS:
    r = ask(question, return_meta=True)
    print("Q.", question)
    print("A.", r["answer"])
    print(f"   ⏱ {r['sec']:.2f}s · 경로 {r['route']} · 판단 {r['action']}")
    print()
''')

code(r'''
# 직접 질문하기
query = "지역의사선발전형 학비 지원은 1학기와 2학기에 각각 언제까지 신청해야 하나요?"

start = time.perf_counter()
print(ask(query))
print(f"⏱ {time.perf_counter() - start:.2f}s")
''')

md(r"""
---
## 11. 설계 노트

**하이브리드 + 다중 질의** — 입학 요강 질문은 전화번호·날짜·학과명처럼 표기 그대로의 숫자·고유명사를 묻는 경우가 많아
BM25가 강하고, "외국에서 살다 온 사람 뽑는 거"처럼 구어체 질문은 Dense가 강합니다. 원문 질의와 키워드 질의를 모두 RRF로 합치고,
코퍼스에 드문 단어 하나는 단독 BM25로 한 번 더 찾아 희석을 막았습니다.

**표 처리** — 모집인원 표는 다단 헤더·병합 셀 때문에 원문 그대로 임베딩하면 행/열 대응이 사라집니다.
색인용 텍스트에만 `라벨: 열=값` 행 요약을 덧붙이고, LLM에는 원문 표를 근거로 줍니다.

**계층 검색** — 페이지 인덱스로 관련 페이지를 먼저 찾고, 같은 페이지의 다른 청크를 함께 넣어
800자 청크 경계에서 문장이 잘리는 문제를 줄였습니다.

**Agentic 판단** — 초안이 근거를 찾지 못했다고 답하면 추가 검색을, 숫자·목록·조건·주변 세부정보가 근거와 어긋나면
같은 근거로 교정을 수행합니다. 판단은 규칙(문자열·형태소 대조)으로 해서 LLM 호출 수와 지연을 늘리지 않습니다.

**일반화 원칙** — 분기와 프롬프트는 질문 유형·문서 제목·표 구조·목차 구조에만 근거하며, 특정 평가 문항의 정답이나 문구는 코드에 넣지 않았습니다.

**한계** — HWP는 페이지 정보가 없어 재외국민 요강의 `p.N`은 실제 쪽수가 아니라 **문서 내 표 순번**입니다.
스캔 이미지 문서는 대상이 아니며(모든 PDF에 텍스트 레이어 존재), 교정 단계가 발동하면 응답이 5초를 넘을 수 있습니다
(오답 1.6점 손실이 시간 감점 0.08점/초보다 크다고 판단).
""")

# --------------------------------------------------------------------------- #
def _replace_between(source: str, start: str, end: str, replacement: str = "") -> str:
    first = source.find(start)
    if first < 0:
        return source
    last = source.find(end, first + len(start))
    if last < 0:
        raise ValueError(f"builder section marker not found: {end}")
    return source[:first] + replacement + source[last:]


DOCPARSE_CELL = r'''from dataclasses import replace
from functools import partial
from pathlib import Path

import docparse
from docparse.context import doc_title as _docparse_title
from docparse.table import is_value as _docparse_is_value
from langchain_core.documents import Document

DOCPARSE_PROFILE = os.environ.get("DOCPARSE_PROFILE", "gachon_2027")
DOCPARSE_INDEX_RENDER = os.environ.get("DOCPARSE_INDEX_RENDER", "baseline1")
DOCPARSE_LLM_RENDER = os.environ.get("DOCPARSE_LLM_RENDER", "baseline1")
if DOCPARSE_INDEX_RENDER not in {"baseline1", "header_records"}:
    raise ValueError("DOCPARSE_INDEX_RENDER must be baseline1 or header_records")
if DOCPARSE_LLM_RENDER not in {"baseline1", "html_full", "header_records"}:
    raise ValueError("DOCPARSE_LLM_RENDER must be baseline1, html_full, or header_records")

docparse_config = replace(
    docparse.load_profile(DOCPARSE_PROFILE),
    index_render=DOCPARSE_INDEX_RENDER,
    llm_render=DOCPARSE_LLM_RENDER,
)
doc_title = partial(_docparse_title, config=docparse_config)
is_value = partial(_docparse_is_value, config=docparse_config)
DOCPARSE_SETTINGS = {
    "profile": DOCPARSE_PROFILE,
    "index_render": DOCPARSE_INDEX_RENDER,
    "llm_render": DOCPARSE_LLM_RENDER,
    "table_full_max_chars": docparse_config.table_full_max_chars,
}
manifest = docparse.build_document_manifest([DATA_DIR], docparse_config)
parser_result = docparse.run_all([DATA_DIR], docparse_config)
raw_docs = parser_result["raw_docs"]
chunks = parser_result["chunks"]
chunks_ctx = parser_result["contextual_chunks"]
tables = parser_result.get("tables", {})

print(f"파싱 단위: {len(raw_docs)}개")
for name in sorted({d.metadata['source'] for d in raw_docs}):
    part = [d for d in raw_docs if d.metadata["source"] == name]
    print(f"  - {name}: {len(part)}개 / {sum(len(d.page_content) for d in part):,}자")
lengths = [len(c.page_content) for c in chunks]
print(f"청크 {len(chunks):,}개 | 평균 {sum(lengths) / len(lengths):.0f}자 | 최대 {max(lengths):,}자")
print(f"색인용 청크 {len(chunks_ctx):,}개 | 표 전체 HTML {len(tables):,}개")
'''


code_cells = [source for cell_type, source in CELLS if cell_type == "code"]
pipeline_cells = []
for source in code_cells[:-2]:
    if any(line.lstrip().startswith("%pip") for line in source.splitlines()):
        continue
    if "import pdfplumber" in source and "def parse_hwp(path: Path)" in source:
        pipeline_cells.append(DOCPARSE_CELL)
        continue
    if "from langchain_text_splitters import RecursiveCharacterTextSplitter" in source:
        continue
    if "DOC_TITLES = {" in source and "def build_contextual_chunks(chunks)" in source:
        continue
    if "PARSER_VERSIONS = {" in source:
        source = source.replace("import hashlib\n", "")
        source = _replace_between(
            source,
            "PARSER_VERSIONS = {",
            "\n\n\ndef _all_present",
            "DATA_DIR = Path(os.environ.get(\"GACHON_DATA_DIR\", \"/content/dataset\"))\n",
        )
        manifest_start = source.find("\nmanifest = build_document_manifest(DATA_DIR)")
        if manifest_start >= 0:
            source = source[:manifest_start].rstrip()
    if "from langchain_openai import OpenAIEmbeddings" in source:
        source = source.replace(
            "from langchain_openai import OpenAIEmbeddings\nfrom langchain_voyageai import VoyageAIEmbeddings",
            "from langchain_openai import OpenAIEmbeddings\nfrom langchain_voyageai import VoyageAIEmbeddings",
        )
        source = source.replace(
            "kiwi = Kiwi()",
            r'''CACHE_DIR = Path(__file__).resolve().parent / "runs" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
try:
    from langchain_classic.embeddings import CacheBackedEmbeddings
    from langchain_classic.storage import LocalFileStore

    embeddings = CacheBackedEmbeddings.from_bytes_store(
        embeddings,
        LocalFileStore(str(CACHE_DIR)),
        namespace=EMBED_MODEL,
        key_encoder="sha256",
        query_embedding_cache=True,
    )
except (ImportError, AttributeError, TypeError):
    import hashlib
    import json
    import tempfile

    class _DiskCachedEmbeddings:
        """Embedding cache keyed by model name and SHA-256 of the input text."""

        def __init__(self, underlying, model_name, directory):
            self.underlying = underlying
            self.model_name = model_name
            self.directory = Path(directory) / hashlib.sha256(model_name.encode("utf-8")).hexdigest()
            self.directory.mkdir(parents=True, exist_ok=True)

        def _path(self, text, purpose):
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            directory = self.directory / purpose
            directory.mkdir(parents=True, exist_ok=True)
            return directory / f"{digest}.json"

        def _read(self, text, purpose):
            path = self._path(text, purpose)
            if not path.is_file():
                return None
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None

        def _write(self, text, vector, purpose):
            path = self._path(text, purpose)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                             delete=False, suffix=".tmp") as handle:
                json.dump(vector, handle)
                temp_path = Path(handle.name)
            temp_path.replace(path)

        def embed_documents(self, texts):
            vectors = [None] * len(texts)
            missing = {}
            for index, text in enumerate(texts):
                vector = self._read(text, "documents")
                if vector is not None:
                    vectors[index] = vector
                else:
                    missing.setdefault(self._path(text, "documents"), (text, []))[1].append(index)
            if missing:
                entries = list(missing.values())
                fresh = self.underlying.embed_documents([text for text, _ in entries])
                for (text, indices), vector in zip(entries, fresh):
                    self._write(text, vector, "documents")
                    for index in indices:
                        vectors[index] = vector
            return vectors

        def embed_query(self, text):
            cached = self._read(text, "queries")
            if cached is not None:
                return cached
            vector = self.underlying.embed_query(text)
            self._write(text, vector, "queries")
            return vector

    embeddings = _DiskCachedEmbeddings(embeddings, EMBED_MODEL, CACHE_DIR)

kiwi = Kiwi()''',
        )
        source = source.replace(
            "t0 = time.perf_counter()\nvectordb = Chroma.from_documents(\n    documents=chunks_ctx,",
            "def _scalar_chroma_docs(documents):\n"
            "    return [Document(page_content=d.page_content, metadata={\n"
            "        key: value for key, value in d.metadata.items()\n"
            "        if isinstance(value, (str, int, float, bool))\n"
            "    }) for d in documents]\n\n"
            "t0 = time.perf_counter()\nvectordb = Chroma.from_documents(\n"
            "    documents=_scalar_chroma_docs(chunks_ctx),",
        )
        source = source.replace(
            "page_db = Chroma.from_documents(\n    documents=page_docs,",
            "page_db = Chroma.from_documents(\n    documents=_scalar_chroma_docs(page_docs),",
        )
    if "def _context(docs) -> str:" in source:
        source = _replace_between(
            source,
            "def _context(docs) -> str:",
            "\n\n\ndef ask(",
            '''def _context(docs) -> str:
    if DOCPARSE_LLM_RENDER != "html_full" or not tables:
        return "\\n\\n".join(f"[근거 {i}] {d.metadata['source']} p.{d.metadata['page']}\\n{d.metadata['raw']}"
                            for i, d in enumerate(docs, 1))
    if not any(d.metadata.get("kind") == "table" and d.metadata.get("table_id") in tables
               for d in docs):
        return "\\n\\n".join(f"[근거 {i}] {d.metadata['source']} p.{d.metadata['page']}\\n{d.metadata['raw']}"
                            for i, d in enumerate(docs, 1))
    parts, seen_tables = [], set()
    for d in docs:
        metadata = d.metadata
        table_id = metadata.get("table_id")
        if metadata.get("kind") == "table" and isinstance(table_id, str) and table_id in tables:
            if table_id in seen_tables:
                continue
            seen_tables.add(table_id)
            raw = tables[table_id]
        else:
            raw = metadata["raw"]
        index = len(parts) + 1
        parts.append(f"[근거 {index}] {metadata['source']} p.{metadata['page']}\\n{raw}")
    return "\\n\\n".join(parts)''',
        )
    pipeline_cells.append(source)

pipeline = "# 자동 생성 — 직접 수정 금지. source: build_pipeline_v24.py\n\n"
pipeline += "\n\n".join(pipeline_cells) + "\n"
pipeline_out = Path(__file__).with_name("pipeline_v24.py")
pipeline_out.write_text(pipeline, encoding="utf-8")
print("written:", pipeline_out, f"({pipeline_out.stat().st_size:,} bytes)")
