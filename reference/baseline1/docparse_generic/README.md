# docparse_generic

docparse_generic은 로컬 HWP/PDF를 요소로 파싱하고 청킹한 뒤 색인용 문맥 텍스트를 만드는 독립 패키지다. API 키, LLM, 임베딩, 벡터 DB가 필요 없다. 알고리즘은 docparse_b1과 같고, 문서군 차이는 ParserConfig 또는 프로필로 지정한다. 실무에서 가져갈 때는 이 범용판을 복사하고, docparse_b1은 기준 출력과 비교할 때 사용한다.

## 설치

저장소 안에서는 루트 디렉터리에서 의존성을 준비한다.

    uv sync

다른 프로젝트로 docparse_generic/ 폴더만 복사한다면 호스트 환경에 다음 라이브러리를 설치해야 한다: langchain-core, langchain-text-splitters, langchain-hwp-hwpx-loader[distribution], pdfplumber, pymupdf. HWP 파싱은 설치된 HWP loader와 pyhwp backend를 사용한다. PDF만 처리해도 패키지 import 시 HWP loader가 필요하므로 위 의존성을 함께 설치한다.

복사한 폴더가 새 프로젝트의 최상위 docparse_generic/라면 그 프로젝트 안에서 다음처럼 실행한다.

    python -m docparse_generic <파일·폴더·glob> --profile neutral --out <출력 폴더>

저장소 안에서는 전체 모듈 경로를 사용한다.

    uv run python -m reference.baseline1.docparse_generic data/dataset --profile gachon_2027 --out reference/baseline1/snapshots/generic_gachon_2027

## CLI

입력은 하나 이상의 로컬 파일·폴더·glob이다. 폴더 안에서 지원 확장자를 결정적으로 정렬하고 중복 경로는 한 번만 처리한다. 지원 형식은 .hwp와 .pdf다.

    # 설정된 도메인 프로필 없이 PDF/HWP 폴더 파싱
    uv run python -m reference.baseline1.docparse_generic data/sample_docs --profile neutral --out out/neutral

    # JSON 파일에 기록한 ParserConfig 값 사용
    uv run python -m reference.baseline1.docparse_generic data/sample_docs --profile parser_config.json --out out/custom

출력 폴더에는 단계별 JSONL과 manifest.json이 생성된다.

| 파일 | 내용 |
|---|---|
| raw_docs.jsonl | 파서가 돌려준 원문 요소의 page_content, metadata |
| chunks.jsonl | 출처 접두사와 청크 순번이 붙은 요소 |
| contextual_chunks.jsonl | 색인용 문맥 텍스트와 원문을 담은 metadata.raw |
| manifest.json | ParserConfig, 원문 SHA-256·크기·파서 버전, 패키지 버전, 단계별 수와 JSONL SHA-256 |

모든 문서 metadata에는 source, page, kind가 있다. 청크 metadata에는 part, chunk_id가 더해진다. 문맥 청크는 raw, title을 더한다. HWP 출력의 page는 동결판처럼 element index 기반이며 실제 쪽수가 아니다. 위치 의미는 추가된 locator에서 확인한다: HWP는 element_index, PDF는 page다.

## Python API

    from reference.baseline1.docparse_generic import (
        ParserConfig,
        build_contextual_chunks,
        chunk_documents,
        load_profile,
        parse_files,
        run_all,
    )

    config = ParserConfig()  # 중립 기본값
    raw_docs = parse_files(["data/sample_docs"], config)
    chunks = chunk_documents(raw_docs, config)
    contextual = build_contextual_chunks(chunks, config)

    all_stages = run_all(["data/sample_docs/*.pdf", "data/sample_docs/*.hwp"], config)

run_all(paths, config)는 raw_docs, chunks, contextual_chunks 키가 있는 dict를 돌려준다. load_sources(paths, config)는 처리할 Path 목록을, build_document_manifest(paths, config)는 입력 파일별 출처 manifest를 만든다. 저장소 밖에서 복사한 경우 import 경로는 패키지를 둔 위치에 맞춘다. 예를 들어 최상위 패키지로 복사했다면 from docparse_generic import ParserConfig, run_all을 사용한다.

## 설정과 프로필 만들기

기본 ParserConfig()는 파일을 고정하지 않고, 파일명 제목 매핑과 도메인 header/row 키워드, 일정 패턴을 비워 둔다. 숫자·기호의 표 값 판정과 청크·표 요약 튜닝값은 일반 파서 기본값으로 제공한다. 빈 header 키워드는 기존 start=1 경로를 사용하며, 빈 행 라벨 키워드는 기존 roster 요약 경로를 쓴다.

새 Python 프로필은 profiles/에 모듈을 추가하고 ParserConfig 인스턴스 CONFIG를 공개한다.

    from ..config import ParserConfig

    CONFIG = ParserConfig(
        required_files=(),
        title_map={},
        header_keywords=(),
        row_label_keywords=(),
        schedule_pattern="",
        schedule_caption="",
        generic_columns=(),
    )

그 다음 CLI에 --profile <모듈명>을 주거나 API에서 load_profile("<모듈명>")을 호출한다. ParserConfig 필드는 config.py를 참고한다. 별도의 .json 파일에 dataclass 필드값을 저장해 --profile <json 경로>로 넘길 수도 있다. 새 문서군에 맞는 값을 만드는 순서와 항목별 초기값은 HARDCODED.md를 참고한다.

중립 기본값으로 임의 문서를 처리할 때 문맥 제목은 파일명에서 앞 번호와 구분자 뒤의 stem을 사용한다. 특정 문서군에서 안정적인 제목이나 표 구조 규칙이 필요하면 해당 프로필에만 그 매핑과 키워드를 추가한다. 프로필별 출력에는 프로필명 디렉터리를 사용하면 비교 결과를 보존하기 쉽다.
