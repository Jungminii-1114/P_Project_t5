"""v23 frozen parser vocabulary and fixed source order."""

from ..config import ParserConfig


CONFIG = ParserConfig(
    required_files=(
        "01_2027학년도_재외국민_모집요강.hwp",
        "02_2027학년도_지역의사선발전형_안내.pdf",
        "03_2027학년도_수시_모집요강.pdf",
        "04_2027학년도_정시_모집요강.pdf",
        "05_2027학년도_수시_면접고사_일정.pdf",
    ),
    title_map={
        "01": "2027학년도 재외국민 모집요강",
        "02": "2027학년도 지역의사선발전형 안내",
        "03": "2027학년도 수시 모집요강",
        "04": "2027학년도 정시 모집요강",
        "05": "2027학년도 수시 면접고사 일정",
    },
    title_prefix_length=2,
    title_fallback_source=True,
    header_keywords=("학과", "학부", "전공", "의예과", "지역"),
    row_label_keywords=("학과", "학부", "전공", "지역"),
    excluded_columns=("모집단위",),
    schedule_pattern=r"\d+월|\d+일|시간|일시|오전|오후",
    schedule_caption="면접/전형 일정",
    generic_columns=("비고", "계열", "연번", "번호", "구분"),
)
