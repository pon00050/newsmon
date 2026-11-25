"""Injection pre-filter (T-45; FR-14). Deterministic EN/KO/ZH patterns plus hidden-text checks. Runs in every mode,
including O1: a hit sets the item to `review` with a warning tag, discards any AI band, and keeps it out of automatic
actions. Pure: no I/O."""
from __future__ import annotations

import re
import unicodedata

PATTERNS = [
    # English: addressing the model, overriding instructions, exfiltration
    r"\bignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
    r"\b(note|message|instructions?) (to|for) (ai|the ai|llm|language model|automated|ai systems?)\b",
    r"\b(ai|llm) (systems?|models?|assistants?) (processing|reading) this",
    r"\bsystem (override|prompt)\b",
    r"\b(disregard|forget) (your|all|the) (instructions|rules|guidelines)",
    r"\bfor automated (news )?desks?\b",
    r"\b(assign|give|set) (it|this( story| article)?) (the )?(maximum|highest|top) (relevance|priority|score)",
    r"\bcopy (your|the) (complete |full )?(system )?prompt",
    r"\byou are now\b",
    # Korean
    r"(이전|위의|앞의)\s*(모든\s*)?(지시|지침|명령)(을|를)?\s*(무시|잊)",
    r"(AI|인공지능|언어\s*모델|자동화)\s*(시스템)?(에게|에|은|는)\s*(알림|지시|전달)",
    r"시스템\s*프롬프트",
    r"(관련성|우선순위)\s*(점수)?(를|을)?\s*(최고|최대)",
    # Chinese
    r"忽略(之前|以上|上述|先前)(的)?(所有)?(指令|指示|提示)",
    r"(给|致)\s*(AI|人工智能|模型|自动化)(系统)?",
    r"系统提示",
    r"(最高|最大)(的)?(相关性|优先级)",
]
_RX = [re.compile(p, re.I) for p in PATTERNS]
_HIDDEN = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")


def check(*texts: str | None) -> list[str]:
    """Return the matched pattern descriptions (empty = clean)."""
    hits = []
    joined = "\n".join(t for t in texts if t)
    if _HIDDEN.search(joined):
        hits.append("hidden characters")
    norm = unicodedata.normalize("NFKC", joined)
    for rx in _RX:
        m = rx.search(norm)
        if m:
            hits.append(m.group(0)[:60])
    return hits
