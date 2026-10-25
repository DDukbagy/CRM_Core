"""주석 정리 공용 함수 (Python·TS 공통)"""
import re, pathlib

SEP_PY = re.compile(r"^(\s*)#\s*[─━-]{2,}\s*(.*?)\s*[─━-]*\s*$")
SEP_TS = re.compile(r"^(\s*)//\s*[─━-]{2,}\s*(.*?)\s*[─━-]*\s*$")

def clean_separators(text, ts=False):
    out = []
    for line in text.split("\n"):
        m = (SEP_TS if ts else SEP_PY).match(line)
        if m:
            label = m.group(2).strip()
            if not label:  # 구분선만 있는 줄은 지운다
                continue
            line = f"{m.group(1)}{'//' if ts else '#'} {label}"
        out.append(line)
    return "\n".join(out)

DATE_PATTERNS = [
    r"\s*\(사용자 결정 \d{4}-\d{2}-\d{2}\)",
    r"\s*\(사용자가 정한 [^)]*\d{4}-\d{2}-\d{2}\)",
    r",\s*\d{4}-\d{2}-\d{2}\)", r"\s*\(\d{4}-\d{2}(-\d{2})?\)", r"\s*\(\d{4}-\d{2}-\d{2}[^)]*\)",
]
def strip_dates(text):
    out = []
    for line in text.split("\n"):
        s = line.lstrip()
        if s.startswith(("#", "//", "*", "/*")) or " # " in line or " // " in line:
            for p in DATE_PATTERNS:
                line = re.sub(p, lambda m: ")" if m.group(0).lstrip().startswith(",") else "", line)
        out.append(line)
    return "\n".join(out)

def replace(text, old, new, path):
    if old not in text:
        if not new or new in text:  # 이미 적용됨 (삭제했거나 바꿈)
            return text
        raise SystemExit(f"[없음] {path}: {old[:60]!r}")
    return text.replace(old, new, 1)

def header(text, comment, ts=False):
    """파일 맨 위 설명 한 줄 (이미 있으면 그대로)"""
    mark = "//" if ts else "#"
    first = text.lstrip("﻿").split("\n", 1)[0]
    if first.startswith(('"""', mark)) and not first.startswith(f"{mark} `from"):
        return text
    if ts and first.startswith(('"use client"', "'use client'", '"use server"')):
        a, b = text.split("\n", 1)
        return f"{a}\n{mark} {comment}\n{b}"
    return f"{mark} {comment}\n{text}"

def above(text, anchor, comment, path, ts=False):
    """anchor 줄(데코레이터 포함 정의 시작) 바로 위에 같은 들여쓰기로 설명 한 줄"""
    lines = text.split("\n")
    idx = [i for i, l in enumerate(lines) if l.strip().startswith(anchor) or l.strip().startswith("async " + anchor) or l.strip().startswith("export " + anchor)]
    if len(idx) != 1:
        raise SystemExit(f"[anchor {len(idx)}개] {path}: {anchor!r}")
    i = idx[0]
    while i > 0 and lines[i-1].strip().startswith("@"):
        i -= 1
    ind = re.match(r"\s*", lines[i]).group(0)
    prev = lines[i-1].strip() if i else ""
    if prev.startswith("#" if not ts else "//"):
        return text
    lines.insert(i, f"{ind}{'//' if ts else '#'} {comment}")
    return "\n".join(lines)

def apply(root, spec, ts=False):
    changed = 0
    for rel, ops in spec.items():
        p = pathlib.Path(root, rel); t0 = t = p.read_text()
        t = clean_separators(t, ts); t = strip_dates(t)
        for op in ops:
            kind = op[0]
            if kind == "rep": t = replace(t, op[1], op[2], rel)
            elif kind == "head": t = header(t, op[1], ts)
            elif kind == "above": t = above(t, op[1], op[2], rel, ts)
        if t != t0:
            p.write_text(t); changed += 1
    return changed
