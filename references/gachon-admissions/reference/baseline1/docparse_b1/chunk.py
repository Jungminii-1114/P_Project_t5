# baseline-1 동결 레퍼런스 — v23(64ac263) build_notebook.py §3에서 이식. 수정 금지. 개선은 새 버전에서.

from langchain_core.documents import Document
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


def chunk_documents(raw_docs):
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
    return chunks
