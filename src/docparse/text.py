"""Configurable copy of the frozen parsing algorithm."""

from .config import ParserConfig

import re


def normalize(text: str, config: ParserConfig = None) -> str:
    """중복 공백/탭 제거, 'YYYY . MM . DD .' → 'YYYY.MM.DD.'"""
    config = config or ParserConfig()
    out = []
    for line in text.split("\n"):
        line = re.sub(config.whitespace_pattern, " ", line).strip()
        if config.normalize_date_dots:
            line = re.sub(config.date_dot_pattern, ".", line)
        if line:
            out.append(line)
    return "\n".join(out)
