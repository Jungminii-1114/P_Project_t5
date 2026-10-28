# -*- coding: utf-8 -*-
"""가천대 2027 입학 안내 Agentic RAG — 실험(v1~v7) 레거시 코드 아카이브.

최종 제출 노트북(202235052_박진성.ipynb)에는 채택된 v6 구성만 들어 있습니다.
이 파일은 Colab scratch 노트북에서 실험했던 변형들을 재현/비교할 때 쓰기 위한 발췌본입니다.

전제(공통):
    raw_docs  : 파싱 단위 Document 리스트 (source/page/kind 메타데이터)
    chunks    : 청킹된 Document 리스트 (source/page/kind/part/chunk_id)
    llm       : ChatOpenAI(model="gpt-6-luna")

실험 결과 요약(자동 생성 20문항, 정답 1건은 gold 오류):
    v2  OpenAI embedding + BM25 RRF + 이웃확장, 단일 호출(한국어 프롬프트)  16/20  2.82s
    v3  v2 + 영어 프롬프트                                                    15/20  2.67s
    v4  v3 + PyMuPDF 텍스트 / pdfplumber 표                                   16/20  3.35s
    v5  v4 + reasoning_effort="low"                                           15/20  1.89s
    v6  v4 + draft→verify 2단  ← 최종 채택                                    19/20  3.8s
    v7a voyage-4-large + rerank-3 + draft→verify                              19/20  4.1s
    v7b voyage-context-4 + rerank-3 + draft→verify                            17/20  3.7s
"""

# --------------------------------------------------------------------------- #
# A. v1: 단일 호출 + 자기점검(sufficient) 후 재검색
# --------------------------------------------------------------------------- #
from pydantic import BaseModel, Field


class AgentStep(BaseModel):
    sufficient: bool = Field(description="True if the evidence alone fully answers the question")
    missing: str = Field(default="", description="What is missing (when sufficient=False)")
    search_query: str = Field(default="", description="Short Korean keyword query for a second retrieval")
    answer: str = Field(default="", description="Final Korean answer (when sufficient=True)")


step_llm = llm.with_structured_output(AgentStep)

JUDGE_PROMPT_KO = """당신은 가천대학교 입학처 상담원입니다. [근거 문서]만 보고 [질문]에 답하세요.

먼저 스스로 점검하세요.
- 질문이 요구한 핵심 정보(수치·날짜·대상·조건)가 근거에 모두 있는가?
- 서로 다른 문서/표를 함께 봐야 하는 질문인데 한쪽만 있는가?

모두 있으면 sufficient=True 로 두고 answer 에 답변을 작성하세요.
부족하면 sufficient=False 로 두고, missing 에 무엇이 없는지, search_query 에 다시 검색할
핵심 키워드(문서에 나올 법한 명사 위주, 15자 내외)를 적으세요."""


def agent_answer_v1(question, k=6):
    import time
    t0 = time.perf_counter()
    pairs = rrf_retrieve(question, k=k)
    step = step_llm.invoke([("system", JUDGE_PROMPT_KO),
                            ("human", f"[근거 문서]\n{format_context(pairs)}\n\n[질문]\n{question}")])
    if step.sufficient and step.answer:
        return step.answer, 1, time.perf_counter() - t0

    pairs2 = rrf_retrieve(step.search_query or question, k=k)
    seen, merged = set(), []
    for d, s in pairs + pairs2:
        if d.page_content not in seen:
            seen.add(d.page_content)
            merged.append((d, s))

    resp = llm.invoke([("system", SYSTEM_PROMPT),
                       ("human", f"[Evidence]\n{format_context(merged)}\n\n[Question]\n{question}")])
    return resp.content, 2, time.perf_counter() - t0


# --------------------------------------------------------------------------- #
# B. v2/v4: RRF 융합 + 이웃 청크 확장
# --------------------------------------------------------------------------- #
def rrf_retrieve(query, k=8, rrf_k=60, span=1):
    """BM25 + Dense(RRF) → 상위 결과의 앞뒤 청크 확장."""
    ranked = [bm25_retriever.invoke(query), vector_retriever.invoke(query)]
    scores, docs = {}, {}
    for result in ranked:
        for rank, doc in enumerate(result, start=1):
            key = doc.page_content
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
            docs[key] = doc
    ordered = sorted(scores, key=scores.get, reverse=True)[:k]

    out, seen = [], set()
    for key in ordered:
        d = docs[key]
        i = CHUNK_INDEX.get(key)
        cand = [d]
        if i is not None:
            for j in range(max(0, i - span), min(len(chunks), i + span + 1)):
                if chunks[j].metadata["source"] == d.metadata["source"]:
                    cand.append(chunks[j])
        for c in cand:
            if c.page_content not in seen:
                seen.add(c.page_content)
                out.append((c, scores[key]))
    return out


# --------------------------------------------------------------------------- #
# C. v6 (최종 채택): draft → verify → (부족 시) 재검색
# --------------------------------------------------------------------------- #
class Verify(BaseModel):
    missing_facts: list[str] = Field(default_factory=list,
                                     description="Key facts/conditions in the evidence that the draft omitted")
    needs_more_search: bool = Field(default=False,
                                    description="True if the evidence itself lacks information the question asks for")
    search_query: str = Field(default="", description="Korean keyword query for a second retrieval")
    final_answer: str = Field(default="", description="Corrected final answer in Korean")


verify_llm = llm.with_structured_output(Verify)

DRAFT_PROMPT = """You are an admissions counselor at Gachon University.
Answer using ONLY the evidence documents.

Rules:
1. Include every key fact the question asks for (numbers, dates, targets, conditions).
2. If the evidence lists several conditions or exceptions, list ALL of them.
3. Never add conditions or qualifiers that are not in the evidence.
4. Copy dates exactly as written (e.g., 2027.01.04.(월) ~ 07.(목) 18:00).
5. When reading a table, align the row and column headers correctly.
6. Write the answer in Korean, 2-5 sentences, and end with (출처: 파일명 p.페이지)."""

VERIFY_PROMPT = """You are a strict fact-checker for Gachon University admissions answers.

Given the question, the evidence, and a draft answer:
1. Check every key fact the question asks for (numbers, dates, targets, conditions) against the evidence.
2. If the draft omitted any key fact or condition that IS in the evidence, list it in `missing_facts`
   and produce a corrected `final_answer` that includes it.
3. Never introduce facts that are not in the evidence. Do not add invented qualifiers.
4. If the evidence itself does not contain the needed information, set needs_more_search=True and give a
   short Korean `search_query`; otherwise set it False.
5. `final_answer` must be in Korean and end with (출처: 파일명 p.페이지)."""


def _safe_verify(ctx, question, draft):
    try:
        return verify_llm.invoke([("system", VERIFY_PROMPT),
                                  ("human", f"[Evidence]\n{ctx}\n\n[Question]\n{question}\n\n[Draft]\n{draft}")])
    except Exception as e:  # LengthFinishReasonError 등 → 초안으로 폴백
        print("   (verify 폴백:", type(e).__name__, ")")
        return Verify(needs_more_search=False, final_answer=draft)


def agent_answer_v6(question, k=8):
    import time
    t0 = time.perf_counter()
    pairs = rrf_retrieve(question, k=k)
    ctx = format_context(pairs)

    draft = llm.invoke([("system", DRAFT_PROMPT),
                        ("human", f"[Evidence]\n{ctx}\n\n[Question]\n{question}")]).content
    v = _safe_verify(ctx, question, draft)
    if not v.needs_more_search:
        return v.final_answer, 1, time.perf_counter() - t0

    pairs2 = rrf_retrieve(v.search_query or question, k=k)
    seen, merged = set(), []
    for d, s in pairs + pairs2:
        if d.page_content not in seen:
            seen.add(d.page_content)
            merged.append((d, s))
    ctx2 = format_context(merged)

    draft2 = llm.invoke([("system", DRAFT_PROMPT),
                         ("human", f"[Evidence]\n{ctx2}\n\n[Question]\n{question}")]).content
    v2 = _safe_verify(ctx2, question, draft2)
    return v2.final_answer, 2, time.perf_counter() - t0


# --------------------------------------------------------------------------- #
# D. v7: VoyageAI (voyage-4-large / voyage-context-4 + rerank-3)
#    - VOYAGEAI_API_KEY 필요 (제출 환경에는 없을 수 있어 최종본에서는 제외)
# --------------------------------------------------------------------------- #
import voyageai

vo = voyageai.Client(api_key=VOYAGE_KEY)  # VOYAGE_KEY = Colab Secrets의 VOYAGEAI_API_KEY

# D-1) voyage-4-large
from langchain_voyageai import VoyageAIEmbeddings

v4emb = VoyageAIEmbeddings(model="voyage-4-large", voyage_api_key=VOYAGE_KEY)
v4db = Chroma.from_documents(documents=chunks, embedding=v4emb,
                             collection_name="gachon_v4",
                             collection_metadata={"hnsw:space": "cosine"})
v4ret = v4db.as_retriever(search_kwargs={"k": 20})

# D-2) voyage-context-4 (문서 문맥을 반영한 contextualized embedding)
ctx_col = chromadb.Client().create_collection("gachon_ctx4", metadata={"hnsw:space": "cosine"})


def build_context_index(batch=12):
    by_src = {}
    for i, c in enumerate(chunks):
        by_src.setdefault(c.metadata["source"], []).append(i)
    for src, idxs in by_src.items():
        for s in range(0, len(idxs), batch):
            group = idxs[s:s + batch]
            texts = [chunks[i].page_content for i in group]
            res = vo.contextualized_embed(inputs=[texts], model="voyage-context-4", input_type="document")
            ctx_col.add(ids=[str(i) for i in group],
                        embeddings=res.results[0].embeddings,
                        documents=texts,
                        metadatas=[chunks[i].metadata for i in group])


def ctx_query_embed(query):
    r = vo.contextualized_embed(inputs=[[query]], model="voyage-context-4", input_type="query")
    return r.results[0].embeddings[0]


# D-3) rerank-3
def _rerank(query, docs, top_n=6):
    r = vo.rerank(query, [d.page_content for d in docs], model="rerank-3", top_k=top_n)
    return [docs[x.index] for x in r.results]


# --------------------------------------------------------------------------- #
# E. 평가 하네스 (자동 문항 생성 + LLM 채점)
# --------------------------------------------------------------------------- #
import random
from pydantic import BaseModel, Field


class QA(BaseModel):
    question: str = Field(description="이 청크만으로 답할 수 있는 구체적 질문 (수치/날짜/조건 포함)")
    answer: str = Field(description="청크에 근거한 정답")


class Verdict(BaseModel):
    correct: bool = Field(description="핵심 정보(수치·날짜·대상·조건)를 모두 포함하면 True")
    reason: str = Field(default="", description="판정 이유")


qa_llm = llm.with_structured_output(QA)
judge = llm.with_structured_output(Verdict)

JUDGE = """정답과 예측 답변을 비교하세요. 표현이 달라도 핵심 정보(수치·날짜·대상·조건)가 모두 일치하면 정답입니다.
부분점수는 없습니다. 하나라도 빠지거나 틀리면 오답입니다."""


def build_testset(chunks, per_source=4, seed=42):
    random.seed(seed)
    by_src = {}
    for c in chunks:
        by_src.setdefault(c.metadata["source"], []).append(c)
    pool = []
    for src, lst in by_src.items():
        pool += random.sample(lst, min(per_source, len(lst)))

    testset = []
    for c in pool:
        qa = qa_llm.invoke([
            ("system", "주어진 문서 발췌만 근거로, 입학 상담에서 나올 법한 구체적 질문 1개와 정답을 만드세요. "
                       "질문은 수치·날짜·대상·조건 중 최소 하나를 묻도록 하세요."),
            ("human", c.page_content[:1500]),
        ])
        testset.append({"q": qa.question, "gold": qa.answer,
                        "src": f"{c.metadata['source']} p.{c.metadata['page']}"})
    return testset


def evaluate_batch(fn, dataset, start, end, tag=""):
    """MCP 타임아웃을 피하기 위해 10문항 단위로 나눠 실행."""
    rows = []
    for i in range(start, end):
        t = dataset[i]
        out, rounds, sec = fn(t["q"])
        v = judge.invoke([("system", JUDGE),
                          ("human", f"[질문]\n{t['q']}\n\n[정답]\n{t['gold']}\n\n[예측]\n{out}")])
        rows.append({"q": t["q"], "gold": t["gold"], "pred": out, "ok": v.correct,
                     "why": v.reason, "sec": sec, "rounds": rounds})
        print(f"{i+1:2d}. {'O' if v.correct else 'X'} {sec:4.1f}s | {t['q'][:50]}")
    ok = sum(r["ok"] for r in rows)
    print(f"[{tag} {start+1}-{end}] {ok}/{len(rows)} | "
          f"평균 {sum(r['sec'] for r in rows)/len(rows):.2f}s | 최대 {max(r['sec'] for r in rows):.2f}s")
    return rows
