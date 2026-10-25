# 설명(주석·docstring)이 없는 함수 찾기
import ast, sys, pathlib
for p in sys.argv[1:]:
    src = pathlib.Path(p).read_text(); lines = src.splitlines()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.name.startswith("__") : continue
            first = (n.decorator_list[0].lineno if n.decorator_list else n.lineno) - 1
            prev = lines[first-1].strip() if first > 0 else ""
            if ast.get_docstring(n) or prev.startswith("#"): continue
            print(f"{p}:{n.lineno} {n.name}")
