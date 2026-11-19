"""부하 테스트 결과 요약: .tmp/loadtest/*_stats.csv → 조건·사용자 수·엔드포인트별 p50/p95/p99·실패율 표(마크다운)

실행: cd backend && python loadtest/report.py   (표준 라이브러리만 쓴다)
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / ".tmp" / "loadtest"
NAME = re.compile(r"^(?P<net>\w+)-(?P<pool>\w+)-u(?P<users>\d+)_stats\.csv$")


def main() -> None:
    files = sorted(OUT.glob("*_stats.csv"))
    if not files:
        sys.exit(f"결과 없음: {OUT}")
    rows = []
    for f in files:
        m = NAME.match(f.name)
        if not m:
            continue
        with f.open() as fh:
            for r in csv.DictReader(fh):
                rows.append((m["net"], int(m["users"]), r["Name"], m["pool"], r))
    rows.sort(key=lambda x: (x[0], x[1], x[2] == "Aggregated", x[2], x[3] != "null"))

    print("| 네트워크 | 사용자 | 엔드포인트 | 연결 | 요청 수 | 초당 요청 | p50 | p95 | p99 | 실패율 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for net, users, name, pool, r in rows:
        n = int(r["Request Count"])
        fail = int(r["Failure Count"]) / n * 100 if n else 0.0
        print(
            f"| {net} | {users} | {name} | {pool} | {n} | {float(r['Requests/s']):.1f} "
            f"| {r['50%']} | {r['95%']} | {r['99%']} | {fail:.1f}% |"
        )


if __name__ == "__main__":
    main()
