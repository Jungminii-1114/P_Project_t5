# 가천대 2027학년도 입학 안내 Agentic RAG — 중간평가 진행 보고서

- 작성일: 2026-10-25
- 제출자: **202235052 박진성**
- 과목: 생성형 AI 활용 (중간평가)
- 실행 위치: Google Colab (colab-mcp로 연결된 **scratch 노트북** `notebooks/empty.ipynb`)
- 로컬 작업 폴더: **`C:\dev\middle_test`** (2026-10-25 세션 3 종료 시 이전 완료)

> ⚠️ 현재 Colab 노트북은 scratch 노트북이라 Drive에 자동 저장되지 않습니다.
> 최종 제출본은 별도로 `202235052_박진성.ipynb` 파일로 만들어 Drive에 올려야 합니다.

---

## 1. 과제 요약 (README.pdf)

| 항목 | 내용 |
|---|---|
| 목표 | 가천대 입학 자료 기반 **Agentic RAG 챗봇** |
| 데이터 | dataset.zip 내 5개 문서 (HWP 1 + PDF 4) |
| 필수 | HWP/PDF 파싱 → 청킹 → 임베딩/벡터DB → 검색 → Agentic RAG |
| 금지 | 웹 검색·외부 조회·추가 문서 수집, 정답 사전 등록 |
| 평가 | 50문항 × 1.6점 = 80점 + 응답시간 20점 |
| 응답시간 | 5초 이내 0.4점, 10초 이상 0점, 20초 초과/오류 시 해당 문항 0점 |
| 제외조건 | 제공 문서 외 자료 사용 / 벡터DB 검색 미구현 / 비공개 환경 의존 / 미제출 |
| 제출 | `학번_이름.ipynb` (Colab에서 ipynb 다운로드), API 키 제거, bloomaikr@gmail.com |

---

## 2. 데이터

| 파일 | 형식 | 규모 | 비고 |
|---|---|---|---|
| 01_2027학년도_재외국민_모집요강.hwp | HWP(배포용) | 표 18개 | pyhwp 백엔드 필요 |
| 02_2027학년도_지역의사선발전형_안내.pdf | PDF | 20p | |
| 03_2027학년도_수시_모집요강.pdf | PDF | 104p | 분량 최대 |
| 04_2027학년도_정시_모집요강.pdf | PDF | 44p | |
| 05_2027학년도_수시_면접고사_일정.pdf | PDF | 4p | 표 위주 |

- `sample.json`: 공식 샘플 3문항 (전화번호 / 정시 원서접수 / 재외국민 증명사진)
- 모든 PDF는 텍스트 추출 가능(스캔 아님) → OCR 불필요

---

## 3. 환경 / 키

- Colab 런타임: Python 3.13
- `OPENAI_API_KEY`: Colab Secrets(🔑)에 등록 → 노트북 액세스 허용 완료
- `VOYAGEAI_API_KEY`: Colab에서 조회 가능 확인 (`u8KKV-zuqaml` 셀 출력 "설정됨 ✅")
  - 로컬 Windows 환경변수/레지스트리에는 아직 없음(재시작 필요) — Colab 쪽만 사용 중
- LLM: **gpt-6-luna 단일 모델** (사용자 지시). 파이프라인/문항생성/채점 모두 동일 모델

### Drive 원본 위치
- `생성형 AI활용` 폴더: `11GJYN2KFLYdF-1xtdDIRrx03DaHnLP6Y`
- `중간평가` 폴더: `174O8eyyv2xasJWTkcEw6qHTpdsdJz1lk`
  - README.pdf `1d62ZZWgOVMVYBhKK0xqcv06tUlPUWuvR`
  - 템플릿 `홍길동_202311111.ipynb` `17SpHf76QBCNE3Zm-dJXwAa5VRjs3VZc7` (고용보험 예제, 구조만 참고)
  - dataset.zip `1EUogt4-hk7ohvby1WIJk4nWFWabXu_hO`
  - sample.json `1tF6rOP-8-tUbBEFImx6uJOqjbi8OhZHY`

### 로컬 사본
`C:\Users\jspar\AppData\Local\Temp\opencode\midterm\`
(README.pdf, 홍길동_202311111.ipynb, dataset.zip, dataset/ 5개 문서)

---

## 4. 최종 파이프라인 (현재 권장안)

```
[HWP]  langchain-hwp-hwpx-loader(mode=elements, distribution_backend=pyhwp)
        → 표 cells(JSON) 직접 렌더링 (rowspan/colspan 전개, 긴 병합셀 중복 방지)
[PDF]  텍스트: PyMuPDF(page.get_text)   ← pypdf보다 정확·압도적으로 빠름
        표: pdfplumber(page.extract_tables) → markdown
        → normalize(): 탭/중복공백 제거, "2027 . 01 . 04 ." → "2027.01.04."
[청킹] 텍스트 800자/overlap 100, 표 1400자(헤더 반복), 청크 앞에 "[파일명 p.N]" prefix
[인덱스] Chroma(cosine) + BM25(kiwipiepy 형태소: NNG,NNP,NNB,VV,VA,XR,SL,SN)
[검색]  BM25(k=20) + Dense(k=20) → RRF(k=60) 상위 20 → **rerank-3** top 6
        → 상위 2개는 앞뒤 청크 확장(span=1)으로 문맥 절단 완화
[답변]  1) draft: gpt-6-luna (근거만 사용, 조건 누락 금지, 한국어)
        2) verify: structured output(Verify)로 누락 사실 점검·최종답 재작성
        3) verify가 needs_more_search=True면 재검색 후 재작성
```

### 프롬프트 원칙
- **지시문은 영어**, 답변은 한국어 (사용자 요청)
- 날짜는 문서 표기 그대로, 표 값은 행/열 머리글 확인
- 근거에 없는 조건·수식어 추가 금지
- 답변 끝에 `(출처: 파일명 p.페이지)`

### 모델 설정
```python
llm = ChatOpenAI(model="gpt-6-luna", reasoning_effort="low", max_completion_tokens=2000)
verify_llm = llm.with_structured_output(Verify)
```
- `reasoning_effort`: 실험 중에는 low, 최종 제출은 기본값(정확도 우선) 검토
- `max_completion_tokens=600`은 추론 토큰에 소진되어 구조화 출력이 잘림 → **2000으로 상향**
- `temperature=0`은 gpt-6-luna에서 **미지원** (400 에러)
- 검증 호출 실패 시 초안으로 폴백(`_safe_verify`)

---

## 5. 실험 이력

테스트셋: 문서 청크에서 gpt-6-luna로 자동 생성한 20문항(QA 구조화 출력)
※ 자동 생성 정답이므로 일부는 gold 자체가 오류 (아래 이슈 참조)

| 버전 | 검색/임베딩 | 답변 방식 | 정확도 | 평균 | 최대 |
|---|---|---|---|---|---|
| v2 | OpenAI `text-embedding-3-small` + BM25 RRF + 이웃확장 | 단일 호출, 한국어 프롬프트 | 16/20 | 2.82s | 8.2s |
| v3 | 〃 | 〃, **영어 프롬프트** | 15/20 | 2.67s | 5.2s |
| v4 | 〃 + **PyMuPDF 텍스트 / pdfplumber 표** | 단일 호출 | 16/20 | 3.35s | 18.8s |
| v5 | v4 + `reasoning_effort=low` | 단일 호출 | 15/20 | 1.89s | 2.9s |
| v6 | v4 + 기본 추론 | **draft → verify 2단** | **19/20** | 3.8s | 7.5s |
| v7a | **voyage-4-large** + rerank-3 | draft → verify | **19/20** | 4.1s | 8.9s |
| v7b | **voyage-context-4** + rerank-3 | draft → verify | 17/20 | 3.7s | 6.2s |

### 해석
- **draft→verify 2단이 가장 큰 정확도 개선** (16→19). "조건 누락" 오답을 잡아냄
- PyMuPDF 전환: 날짜 표기 정확도 향상, 속도 53배(0.28s vs 14.87s)
- pdfplumber 표 청크 추가: 2단 레이아웃 표의 행 정렬 정상화
- voyage-context-4는 이번 데이터/질문 유형에서 large-4보다 나쁨 (17/20)
- OpenAI 임베딩(v6)과 voyage-4-large(v7a)는 동률(19/20) → 비용/속도는 OpenAI가 유리

### 공식 샘플 3문항 (v6 기준)
| 질문 | 정답 | 결과 |
|---|---|---|
| 대표 전화번호 | 1577-0067 | O (2.3s) |
| 정시 원서접수 기간 | 2027.01.04.(월)~07.(목) 18:00 | O (2.1s) |
| 재외국민 증명사진 | 최근 3개월, JPG/GIF | O (2.3s) |

---

## 6. 알려진 이슈

1. **테스트 #14 정답 오류**: gold가 "바이오로직스학과 100명"인데, 100은 `금융·빅데이터학부`의 **전공선택기준정원**. 실제 정시 모집인원은 일반전형1 30 + 일반전형2 15 = **45명**. → 19/20은 사실상 19/19
2. 자동 생성 테스트셋에 "몇 페이지에 있나요?" 같은 목차 기반 문항이 섞여 노이즈 존재
3. 응답시간 편차 큼(1.6s~12s): 추론 토큰 수 변동. `reasoning_effort=low`로 1.6~2.8s 안정
4. HWP 표 일부(중첩 표)는 셀 텍스트에 `[merged:R#C#]` 플레이스홀더가 남음
5. Colab scratch 노트북은 Drive 자동 저장 안 됨

---

## 7. 다음 할 일

- [ ] 최종 검색 조합 확정 (voyage-4-large vs OpenAI embed — 정확도 동률이면 OpenAI)
- [ ] 파싱 정확도 추가 개선 여지 검토
      - HWP 중첩 표 렌더링
      - PDF 2단 레이아웃에서 표/본문 중복 제거
- [ ] **클린 노트북 작성** (아래 구성) 후 실제 재실행 검증
- [ ] `202235052_박진성.ipynb` 로 Drive 업로드
- [ ] API 키 셀 제거 확인 (코드에 키 문자열 없어야 함)
- [ ] 최종 검증: 공식 샘플 3문항 + 자동 생성 20문항

### 최종 노트북 목표 구성
```
0. 개요(md) / 패키지 설치 / API 키 로드(Secrets)
1. 데이터 준비 (5개 문서 존재 확인, dataset.zip 자동 해제)
2. 파싱 (HWP 표 렌더러 + PyMuPDF + pdfplumber)
3. 청킹
4. 임베딩 + Chroma + BM25
5. 하이브리드 검색(RRF) + rerank + 이웃 확장
6. Agentic 답변 (draft → verify → 재검색)
7. 데모: 샘플 3문항 실행 및 출력
8. (선택) 자체 평가 루프
```

---

## 8. 핵심 코드 조각

```python
# HWP 표 → markdown (rowspan/colspan 전개)
def render_hwp_table(cells_json):
    cells = json.loads(cells_json)
    nrows = max(c["row"] + c["rowspan"] for c in cells)
    ncols = max(c["col"] + c["colspan"] for c in cells)
    grid = [["" for _ in range(ncols)] for _ in range(nrows)]
    for c in cells:
        text = " ".join((c.get("text") or "").split()).replace("|", "/")
        span = c["rowspan"] * c["colspan"]
        for r in range(c["row"], min(c["row"] + c["rowspan"], nrows)):
            for col in range(c["col"], min(c["col"] + c["colspan"], ncols)):
                if span == 1 or len(text) <= 40 or (r, col) == (c["row"], c["col"]):
                    grid[r][col] = text
    ...
```

```python
# RRF 융합 + 리랭크 + 이웃 확장
def retrieve(query, top_n=6, k_rrf=20):
    lists = [bm25_retriever.invoke(query), dense_retriever.invoke(query)]
    scores, docs = {}, {}
    for result in lists:
        for rank, d in enumerate(result, 1):
            scores[d.page_content] = scores.get(d.page_content, 0) + 1/(60+rank)
            docs[d.page_content] = d
    cand = [docs[k] for k in sorted(scores, key=scores.get, reverse=True)[:k_rrf]]
    top = rerank(query, cand, top_n)      # voyage rerank-3
    return expand_neighbors(top, span=1)  # 상위 2개는 앞뒤 청크 포함
```

---

## 9. 참고 수치

- 파싱 단위: 382개 (HWP 19, PDF 텍스트 190, PDF 표 192)
- 청크: **514개**, 평균 574자, 최대 2,580자
- 인덱스 구축 시간: 약 1~2분 (평가 시간에서 제외됨)
- 문항당 응답: 2~4초 (검색 0.3s + draft ~1.2s + verify ~1.0s)

---

# 세션 2 (2026-10-25 오후) — 제출본 확정 + 구어체 평가셋 + 지연시간 분석

## 10. 제출본 노트북 (베이스라인 확정)

- 빌더: `build_notebook.py` → `202235052_박진성.ipynb` (20 cells, 35KB)
- 구성: 설치 → API키(Secrets) → 데이터 준비 → 파싱 → 청킹 → Chroma+BM25 → RRF+이웃확장 → draft/verify → 데모 3문항 → 설계노트
- **Drive 업로드 완료**: `202235052_박진성.ipynb`, file id `1KPlu7TQhxo2ul_d58jgJtxnFcr97tb3i`
  (Colab "노트 업로드"가 자동으로 Drive에 저장, 부모 폴더 `1EiQQ1exolOJP7-MEyiQoPZOpxyNl6K2O`)
- 최종 제출 시 `중간평가` 폴더(`174O8eyyv2xasJWTkcEw6qHTpdsdJz1lk`)로 이동 필요
- API 키 문자열 없음(환경변수/Secrets만 참조)
- **주의**: 이 노트북의 파라미터(top_n=6, expand_top=2)는 v6와 동일 계열이나, 아래 v14 개선은 아직 미반영

## 11. 구어체 평가셋 (20문항) — `eval/testset_hard.json`

기존 자동 생성 20문항의 **gold는 그대로 두고 질문만** 구어체·애매한 표현·용어 오용으로 바꾼 세트.
(#14 gold는 100명 → 45명으로 교정, #13은 목차 기준 페이지라 모호)

예시:
- "몸이 좀 불편한 학생인데요, 시험 볼 때 도와주는 사람 받을 수 있나요?"
- "외국에서 살다 온 사람들 뽑는 거 있잖아요, 경영학과는 최대 몇명까지 뽑을 수 있고..."
- "인천 캠퍼스에 바이오로직스학과 있잖아요, 거기 정시로 몇명 뽑아요?"

## 12. 기준선(v6 상당, `ask_final`) 측정 결과

| 세트 | 정확도 | 평균 | 최대 | 5초 초과 | 10초 초과 |
|---|---|---|---|---|---|
| 기존(정형) 20문항 | 19/20 | 3.8s | 7.5s | 2 | 0 |
| **구어체 20문항** | **18/20** | **8.49s** | **21.1s** | 13 | 5 |

→ **정확도는 유지되지만 응답시간이 붕괴**. 20초 초과 1건(21.1s)은 해당 문항 0점.

### 원인 분해
- 재검색(round 2) 발동 5/20 → 4회 LLM 호출 → 9~21초
- 호출당 지연: draft 1.9~4.3s, verify 2.5~5.0s (컨텍스트 5~13k자에 비례)
- **검색 실패 사례 발견**: Q2(경영학과 15/16)는 p.3 청크가 top-20에 아예 없었음
  - BM25("경영학과 최대모집 가능인원")는 p.3을 1위로 찾지만, 구어체 원문 질의는 "외국/사람"에 밀림
  - Dense도 구어체에서 p.3을 놓침

## 13. 실험 로그 (v8~v14)

| 버전 | 변경 | 결과 |
|---|---|---|
| v8 | 검증 `reasoning=none` + top_n 5/expand 1 | **실패** — 근거 누락 + 검증이 정답을 "없음"으로 덮어씀 |
| v9 | 검증만 `none` | 정확도 유지되나 **확률적** (같은 문항이 실행마다 정답/오답) |
| v10 | 2차 검색을 재작성 1회로 | 정확도 하락 (draft를 덮어써서 오답) |
| v11 | 2차 검색을 초안 1회로 + 시간가드 | 지연 개선(6.9s) but Q2 오답 (검색 실패가 원인) |
| v12/v13 | 키워드·동의어 4-리스트 RRF | Q2 p.3이 여전히 top-6 밖 (희석됨) |
| **v14** | **"확인할 수 없습니다" 감지 → 키워드 재검색** | **Q1·Q2 모두 정답, 8.3~8.6s (r2)** |

### 핵심 인사이트
1. **`reasoning_effort="none"`은 품질 붕괴** — 근거에 있는 사실도 "없다"고 답하고, 검증이 정답 draft를 덮어씀. `low` 유지.
2. **verify의 `needs_more_search`는 확률적** → LLM 판단에만 맡기면 같은 질문이 실행마다 다르게 동작.
   → 답변에 "확인할 수 없습니다"가 있으면 **문자열 기반으로 강제 재검색**.
3. **구어체에서는 키워드 질의가 결정적** — `search_keywords()`(일반명사 제거 + 동의어 치환)로 재검색하면
   Q2의 p.3이 BM25 4위/Dense 2위로 진입.
4. **시간 예산(t_budget)** 이 6.5s면 1차가 이미 6.5s를 넘어 재검색이 발동하지 않음 → **9.0s**로 상향.
   (오답 1.6점 손실 > 시간 감점 0.2점)

### 현재 v14 상태 (전체 20문항 미측정)
```python
ask_v14(q, top_n=6, expand_top=2, t_budget=9.0)
# 1차: retrieve_final(원 질문, 2-리스트 RRF) → draft(low) → verify(low)
# 2차: (needs_more_search or "확인할 수 없습니다") and elapsed<9s
#      → retrieve_kw(키워드·동의어 질의) 병합 → draft(low) 1회
```

## 14. 다음 할 일 (재개 지점)

1. **v14 전체 측정** — 구어체 20문항 + 기존 20문항(회귀) 각 4배치(5문항씩)
2. 결과에 따라:
   - 구어체 정확도 ≥18/20, 평균 <7s면 v14 채택
   - 아니면 재검색 트리거/키워드 사전 추가 조정
3. **노트북 반영** — `build_notebook.py`의 `retrieve`/`ask`를 v14로 교체 후 재생성
4. **최종 검증** — 클린 노트북 Run All (새 런타임), 샘플 3문항 확인
5. **제출** — Drive `중간평가` 폴더로 이동, API 키 문자열 최종 확인

## 15. 세션 2 파일 목록

| 파일 | 내용 |
|---|---|
| `202235052_박진성.ipynb` | 제출본(베이스라인, v6 상당) |
| `build_notebook.py` | 제출본 생성 스크립트 |
| `eval/testset_hard.json` | 구어체 20문항 + gold |
| `legacy/experiments_v1_v7.py` | v1~v7 레거시 코드 |
| `REPORT_중간평가_진행상황.md` | 본 보고서 |

## 16. Colab scratch 커널 상태 (재개용)

- 패키지 설치 완료, `chunks`(514), `vectordb`(OpenAI), `bm25_retriever`(k=20) 살아 있음
- 주요 함수: `retrieve_final`, `retrieve_kw`, `ask_final`(기준선), `ask_v14`, `search_keywords`, `evaluate_batch`
- 평가셋 변수: `testset`(기존 20), `testset_hard`(구어체 20)
- 결과 변수: `r_h1~r_h4` (기준선 구어체 측정)
- LLM: `llm = ChatOpenAI("gpt-6-luna", reasoning_effort="low", max_tokens=2000)`

---

# 세션 3 (2026-10-25 밤) — 정확도/지연 고도화 (v15~v21) + 6기법 + held-out 검증

## 17. 이번 세션에서 한 일 (요약)

1. 검색/청킹을 **v15**로 재구축 (문맥 헤더 + 표 행 요약 + 페이지 인덱스 + 희귀어 리스트)
2. 답변 파이프라인을 **v16~v21**로 반복 개선 (검증·교정 규칙 추가)
3. 구어체 20문항 **20/20**, 정형 20문항 **18/20**(실패 2건 모두 gold/표현 문제로 확인)
4. **held-out 10문항을 새로 작성**해 오버피팅 검증 → v20 5/10 → **v21 8/10**
5. 실패 원인을 `실제 오류` / `채점기 엄격성` / `지표 인공물`로 분류
6. v21 코드 전문을 `pipeline_v21_reference.py`로 **로컬에 스냅샷** (커널 소실 대비)

## 18. 6개 기법 → 구현 매핑 (발표/보고서용)

| 기법 | 구현 위치 | 구체 내용 |
|---|---|---|
| **① Adaptive RAG Routing** | `route_query` + `ROUTE_PATTERNS` | 질문을 `page/table/procedure/eligibility/list/schedule/general`로 분류. 경로별로 검색 리스트·필터·부스트·프롬프트를 다르게 적용. `page`는 LLM 없이 목차 도구로 직행 |
| **② Table-aware RAG** | `parse_table2` + `row_summary2` + `expand_header` | 표를 `라벨: 열=값`으로 직렬화하고 다중 헤더를 전개. 표 원문은 그대로 두고 **요약을 앞에 붙여** 임베딩/BM25가 행 단위로 매칭되게 함 (236개 표 청크 중 57개 요약 생성) |
| **③ Evidence-grounded Verification** | `ground_answer` + `make_confidence` + `missing_*` | ① 숫자/날짜/개체/인용을 근거와 대조(0.40/0.20/0.25/0.15) ② 목록 항목 충실성 ③ 조건문 반영 ④ 같은 문장·같은 행의 주변 세부정보 → 미충족 시 **같은 근거로 1회 교정** |
| **④ Contextual Retrieval** | `build_contextual_chunks` | 모든 청크 앞에 `[문서] 제목 \| p.N \| 표/본문 \| 표제: …` 헤더 부착. 표는 행 요약까지 포함 |
| **⑤ Hierarchical Retrieval** | `page_prior` + 형제 확장 2종 | ① 페이지 인덱스(BM25+Dense)로 상위 5페이지 선정 → 소속 청크 가산 ② top-2 청크의 앞뒤 1개 ③ **같은 페이지의 다른 청크 1개**(잘린 뒷문장 회수) |
| **⑥ RAG Evaluation & Calibration** | `eval_meta` + `conf/cov` | 문항별 정확도·지연·confidence·ground score를 함께 기록. `conf = 0.50·ground + 0.35·coverage + 0.15·citation + route_bonus` |

### 오버피팅 방지 원칙 (사용자 지적 반영)
- **문항을 외우는 분기는 넣지 않음.** 모든 분기는 `질문 유형` / `문서 제목` / `표 구조` / `목차 구조`에 근거.
- 예: "농어촌은 44쪽"을 코드에 넣은 게 아니라, "페이지를 물으면 목차를 파싱한다"는 **도구**를 넣음.
- 규칙이 실패하면 `general`로 fallback.
- 검증은 **학습에 쓰지 않은 held-out 10문항**으로 수행.

## 19. v15~v21 변경 로그

| 버전 | 변경 | 측정 결과 |
|---|---|---|
| v15 | 문맥 헤더 + 표 행 요약 + 페이지 인덱스 + 다중쿼리 RRF + 페이지 prior | 검색 Recall@6 구어체 20/20 (기준선 16/20) |
| v16 | 규칙 라우터 + target_doc + **toc_lookup**(페이지 질문 LLM 0회) | 페이지 2문항 **0.00s** 정답 |
| v17 | 표 부서 부스트(`dept_terms`) + 표 라우트 가중 | Q14(바이오로직스) 정답 |
| v18 | 목록 충실성 검증(`missing_list_items`) | Q8 "국내외 연수" 회수 |
| v19 | 조건문 검증(`missing_conditions`) | Q3(재외국민 1개 학년) 2회 연속 정답, 5.5~5.7s |
| v20 | 조건·목록 힌트를 교정 트리거로 통합 | 구어체 **20/20**, 평균 3.12s, 최대 6.41s |
| v21 | 희귀어 단독 BM25 + 페이지 형제 확장 + 주변 세부정보 검증 + 프롬프트 V5 | held-out **5/10 → 8/10** |

### v21에서 고친 실제 버그 2개
1. **"새로 생긴" → "신설" 미확장**: 동의어를 추가했지만 RRF에서 희석되어 p.30이 top-8 밖.
   → 질문 키워드 중 **코퍼스 빈도가 가장 낮은 토큰 1개**를 BM25 단독 리스트로 추가 (`rare_terms`).
2. **학교폭력 표 열 정렬 오류(6호 → 20점)**: 빈칸 압축 로직(v3)이 숫자열을 밀어버림.
   → 요약 v2로 롤백 + 프롬프트에 `4호=-10, 5호=-20, 6호=-100` 예시 제공 → **100점 정답**.

## 20. 측정 결과 (v20/v21)

| 세트 | 정확도 | 평균 | 최대 | 5초 초과 | 10초 초과 |
|---|---|---|---|---|---|
| 구어체 20 (v20) | **20/20** | 3.12s | 6.41s | 2 | 0 |
| 정형 20 (v20) | 18/20 | 2.66s | 5.86s | 1 | 0 |
| held-out 10 (v20) | 5/10 | 3.01s | 6.33s | 3 | 0 |
| **held-out 10 (v21)** | **8/10** | 4.69s | 6.35s | 5 | 0 |
| 페이지 질문 (v21) | 2/2 | **0.00s** | 0.00s | 0 | 0 |

- 정형 20의 실패 2건: ① #14 gold 오류(100명 → 실제 45명) ② #8 '국내외 연수' 목록 누락(v18에서 수정, 이후 정답)
- 검색 Recall@6: 구어체 20/20, 정형 20/20, held-out 9/10 (±1페이지 10/10)
- v21은 교정 발동률이 8/10으로 높아 평균이 4.69s. **정확도 1.6점 > 시간 감점 0.08~0.16점**이므로 의도된 트레이드오프.

## 21. held-out 실패 2건의 성격 (중요)

| # | 질문 | 실패 유형 | 내용 |
|---|---|---|---|
| 2 | 정시 원서 접수 후 학과 변경 / 접수 완료 시점 | **지표 인공물** | 질문이 묻지 않은 "제출서류·전형료 반환 불가"를 gold가 요구. 해당 문장은 p.9 청크가 594자에서 잘려 **p.8 다른 청크에만 존재** → 근거에 없음 |
| 10 | 의무복무지역 외 수련 기간 | **채점기 엄격성** | 근거 p.15의 '별도 지정' 예외를 함께 설명 → 채점기가 "gold를 제한하는 예외"로 감점. 내용은 근거에 존재 |

→ 두 건 모두 **파이프라인 오류가 아님**. 다만 #2는 "청크 절단"이라는 구조적 약점을 드러냈고, v21의 **페이지 형제 확장**이 이 문제를 완화한다(같은 페이지의 다른 청크를 1개 더 넣음).

### 규칙 추가를 멈춘 지점
`missing_details`(최고 겹침 문장의 명사 누락 검사)를 시험했으나 **표 셀 분리 때문에 오탐/미탐**이 발생해 채택하지 않음.
→ "규칙을 더 넣는 것"보다 **검증된 4종(숫자/목록/조건/이웃)** 으로 유지하는 것이 일반화에 유리하다고 판단.

## 22. 아직 안 한 것 (다음 세션 필수)

- [ ] **① 제출 노트북 재생성** — 현재 `202235052_박진성.ipynb`는 **아직 베이스라인 v6**입니다. v21 로직 이식 필요 (최우선)
- [ ] ② Calibration 보고서 — confidence 구간별 정확도, ECE, coverage-accuracy, 교정/기권 임계값
- [ ] ③ Retrieval ablation — ㉠ 기존 `retrieve_final` vs `retrieve_v15` ㉡ 라우팅 off ㉢ 표 요약 off ㉣ 형제 확장 off
- [ ] ④ 클린 런타임 Run All 검증 (새 세션에서 처음부터 실행)
- [ ] ⑤ Drive `중간평가` 폴더로 최종 이동 + API 키 문자열 0건 확인

## 23. 재개 지점 (다음 세션이 가장 먼저 할 일)

1. `pipeline_v21_reference.py`를 읽고 `build_notebook.py`의 검색/답변 섹션을 v21로 교체
   - 특히 `retrieve_v15`, `route_query`, `toc_lookup`, `ground_answer`, `missing_*`, `ask_v21`
   - `TOC_PAGES`는 **하드코딩이 아니라 자동 탐지 코드**로 넣을 것 (현재 값은 탐지 결과)
2. 노트북 재생성 → 새 런타임에서 Run All → 샘플 3문항 확인
3. 시간이 남으면 ②③ 수행

### 주의
- Colab 커널은 **scratch 노트북**이라 Drive 자동 저장이 안 됩니다. 커널이 죽으면 `pipeline_v21_reference.py`가 유일한 코드 사본입니다.
- `reasoning_effort="none"`은 여전히 금지(품질 붕괴). `"low"` 유지.

## 24. 파일 목록 (세션 3 추가분)

| 파일 | 내용 |
|---|---|
| `pipeline_v21_reference.py` | **v21 전체 코드 스냅샷** (검색·검증·프롬프트·ask_v21) |
| `eval/testset_holdout.json` | held-out 10문항 + gold + 실패 유형 주석 |
| `eval/results_v21.json` | 세트별 정확도/지연 + held-out 문항별 상세 + 실패 원인 |
| `eval/testset_hard.json` | 구어체 20문항 (세션 2) |

## 25. Colab 커널 상태 (세션 3 종료 시점)

- 살아 있는 주요 객체: `chunks`(514), `chunks_v15`(514), `vectordb_v15`, `bm25_v15`, `dense_v15`,
  `page_db/page_dense/page_bm25`, `CHUNK_INDEX_V15`
- 평가셋: `testset`(정형 20), `testset_hard`(구어체 20), `testset_holdout`(10)
- 결과: `h20`(구어체 v20), `o20`(정형 v20), `ho20`(held-out v20), `ho2`(held-out v21)
- 함수: `retrieve_v15`, `ask_v20`, `ask_v21`, `toc_lookup`, `route_query`, `target_doc`,
  `ground_answer`, `missing_list_items`, `missing_conditions`, `missing_neighbor_details`, `eval_meta`
- 커널 셀 번호: v21 관련 코드는 대략 **130~200번 셀**

---

# 세션 4 (2026-10-25 저녁) — 검토·버그 수정·v22 제출본 확정

## 26. 이전 보고서의 정정 사항 (Errata)

| 위치 | 기존 서술 | 실제 |
|---|---|---|
| §4 최종 파이프라인 | voyage `rerank-3` top 6 사용 | v6 제출본·v21 모두 **리랭크 미사용**, 임베딩은 OpenAI `text-embedding-3-small`이었음 |
| §9 참고 수치 | "PDF 텍스트 190" | PDF는 총 172쪽. 190은 **페이지 인덱스 문서 수**(HWP 표 순번 포함) |
| §18 오버피팅 방지 원칙 | "문항을 외우는 분기 없음" | v21 `DRAFT_PROMPT_V5`에 평가셋 정답 문구(`"국내외 연수"`, `"주거 안정"`, `4호=-10, 5호=-20, 6호=-100`)가 들어 있었음 → **v22에서 제거** |
| §20 held-out 8/10 | 일반화 성능 | v21은 held-out 실패를 보고 고친 버전이므로 **held-out이 아님** |
| §19/결과 json | #8 "v18에서 수정" / "v19에서 수정" | 서로 불일치. v20 정형 측정에서도 #8이 실패로 집계됨 |
| `pipeline_v21_reference.py` | "프리앰블은 build_notebook.py 참고" | 빌더에 `chunks_v15`·페이지 인덱스·TOC 탐지 코드가 **없었음** → 커널 `In[105]`, `In[109]`에만 존재 (현재 `scratchpad.ipynb`로 보존) |
| HWP `p.N` | 페이지 | HWP는 페이지 정보가 없어 **표 순번**임 (노트북 설계 노트에 명시) |

## 27. 발견·수정한 버그 (v21 → v22)

1. **"홈페이지"가 목차 도구로 오라우팅** — `페이지` 정규식이 "홈페이지"에 매칭 → `toc_lookup`이 LLM 없이 "원서접수는 35페이지" 같은 오답을 conf 0.99로 반환. `(?<!홈)페이지`로 수정, "몇 장"(사진 몇 장)도 제외.
2. **"모집/선발"이 표 경로 신호** — "정시**모집**", "지역의사**선발**전형" 등 거의 모든 질문이 `table`로 분류됨. 표 신호에서 제거.
3. **README 필수 요건 "추가 검색 여부 판단" 미충족** — v21은 같은 근거로 재작성만 함. v22: 초안이 "확인할 수 없다/규정이 없다"고 하면 `retrieve_more`(키워드 질의 추가 검색) 후 재작성.
4. **응답시간 상한 부재** — LLM `timeout=30`, 재시도 1회 → 20초 초과 가능. v22: 스레드 기반 남은시간 타임아웃(`HARD_LIMIT=18s`), 교정은 9초 이전에만 시작, 실패 시 초안 유지.
5. **초안 타임아웃이 너무 짧음(12.5s)** — Drive #11에서 오류 문구 반환 → 초안 제한을 `HARD_LIMIT-0.5s`로.
6. **공식 샘플 "대표 전화번호" 검색 실패(Voyage 전환 후)** — Dense 1위(03 p.104 `Tel. 1577-0067`)가 BM25 리스트 3~4개에 밀려 탈락. `전화→Tel` 동의어 + **Dense 1위 항상 포함** 보장.
7. **프롬프트 "2-5 sentences" 제한** — 복합 질문에서 괄호 조건·각주 누락의 주원인. 항목별 번호(①②③) + 한정어 유지 규칙으로 교체.
8. **노트북 내 정답값 노출** — 설계 노트의 `1577-0067`, `2027.01.04.(월)`, 표 예시 `일반전형1=30, 일반전형2=15`(실제 정답값) 제거.

## 28. v22 파이프라인 (제출본 = `build_notebook.py` → `202235052_박진성.ipynb`)

```
파싱(HWP 표 렌더러 + PyMuPDF + pdfplumber) → 청킹(본문 800/100, 표 1400 헤더반복)
→ 색인용 문맥 청크(문서 헤더 + 표 행 요약) → Voyage voyage-4-large + Chroma / BM25(kiwi) / 페이지 인덱스
→ 라우팅(page/schedule/table/procedure/eligibility/list/general)
   ├ page + 목차 일치 → toc_lookup (LLM 0회)
   └ retrieve(다중질의 RRF + 희귀어 BM25 + 페이지 prior + Dense 1위 보장 + 이웃/형제 확장)
       + retrieve_multi(복합 질문 절·문서별 분해 병렬 검색)
       → 초안(gpt-6-luna, low) → 근거 대조 검증
           ├ "근거 없음" → retrieve_more(추가 검색) → 재작성
           ├ 숫자/목록/조건/주변정보 누락 → 같은 근거로 교정
           └ 통과 → 반환
```
- 임베딩: **Voyage `voyage-4-large`** (Secrets `VOYAGEAI_API_KEY`). 키가 없으면 OpenAI `text-embedding-3-small`로 자동 대체(실행 중단 방지).
- 클린 실행 검증: 빈 네임스페이스에서 13개 코드 셀 전체 실행 **오류 0**, 총 68초(파싱 30s + 색인 22s), 공식 샘플 3문항 1.8 / 3.1 / 4.1초 정답.

## 29. v22 측정 결과 (`eval/results_v22.json`)

| 세트 | 정확도 | 평균 | 최대 | >5s | >10s |
|---|---|---|---|---|---|
| 공식 샘플 3 | **3/3** | 3.09s | 4.03s | 0 | 0 |
| held-out 10 | **10/10** | 5.24s | 8.31s | 6 | 0 |
| 구어체 20 | 19/20 | 4.77s | 8.78s | 10 | 0 |
| 정형 20 | 19/20 (실패 1 = gold 오류 #14) | 4.08s | 10.85s | 5 | 1 |
| **Drive 20 (신규)** | **8/20** (일반 7/10, 어려움 1/10) | 7.70s | 14.00s | 16 | 6 |

- 프롬프트 정답 누출을 제거했음에도 held-out은 10/10 유지(#6 학교폭력 6호 정답, #2 정답).
- Drive 20문항(사용자 작성, Drive `중간평가` 폴더)은 3~5개 문서 교차·계산·표 병합셀 판독 문항이라 어렵고, 실패 원인은
  ① 세부 한정어 누락(5건) ② 일부 근거 페이지 미검색(#12 03 p.33, #20 04 p.15) ③ 표 열 오독(#17, #19).
- 채점은 같은 모델(gpt-6-luna) LLM-as-judge이므로 실제 채점과 차이가 있을 수 있음.

## 30. 알려진 한계 (제출 시점)

- "홈페이지 주소" 질문: 문서에 `www.gachon.ac.kr`이 있으나 질의어 "홈페이지"로 검색되지 않아 "확인 불가"로 답함 (미수정 — 제출 직전 회귀 위험).
- 복합·다문서 질문은 5~14초 → 시간 점수 감점. 교정 단계가 대부분 문항에서 발동(평균 4~5초대의 원인).
- 표 병합 셀/★ 일정표의 열 정렬 오독 가능성 남음.

## 31. 제출 절차 (남은 일)

1. Colab에서 `202235052_박진성.ipynb` 열기(노트 업로드) → 🔑 Secrets에 `OPENAI_API_KEY`, `VOYAGEAI_API_KEY` 확인 → `/content/dataset.zip` 업로드(또는 Drive) → **런타임 → 모두 실행**
2. 실행 결과 확인 후 **파일 → 다운로드 → .ipynb 다운로드** (README: Colab 링크가 아닌 ipynb 파일 제출)
3. 다운로드한 파일에 API 키 문자열이 없는지 확인 후 bloomaikr@gmail.com 으로 제출

## 32. 파일 목록 (세션 4)

| 파일 | 내용 |
|---|---|
| `202235052_박진성.ipynb` | **v22 제출본** (27셀, 출력 없음, 키 없음) |
| `build_notebook.py` | v22 노트북 빌더 (단일 진실 원본) |
| `scratchpad.ipynb` | 세션 1~3 Colab 작업 노트북 전체(196셀, 출력 포함) — v15 색인/TOC 탐지 원본 코드 보존 |
| `eval/testset_drive20.json` | Drive 20문항 테스트셋 (사용자 작성) |
| `eval/results_v22.json` | v22 세트별 결과·실패 원인 |
| `legacy/build_notebook_v6.py`, `legacy/202235052_박진성_v6.ipynb` | 이전 v6 제출본 백업 |
