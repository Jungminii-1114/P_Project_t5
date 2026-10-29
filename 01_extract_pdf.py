"""기존 실행 파일명은 유지하고 재사용 가능한 추출 모듈을 호출한다."""

from pdf_extract import main


if __name__ == "__main__":
    raise SystemExit(main())
