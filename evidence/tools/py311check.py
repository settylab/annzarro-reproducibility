"""Python 3.11 compatibility of the scripts the site build and the gate run.

The evidence host builds with Python 3.11 (evidence/HOSTING.md); the authors' machines run 3.12+,
where a string quote may be reused inside an f-string expression (PEP 701):

    f'{x.render([('a', 'b')])}'     # fine on 3.12+, SyntaxError on 3.11

check(paths) returns one message per problem:
  * on 3.12+, a tokenizer scan for a string or f-string nested in an f-string with the same quote
    character (the case that bit us), and a backslash inside an f-string replacement field's string;
  * if a Python 3.11 interpreter is found (python3.11 on PATH, or `uv python find 3.11`), every file is
    parsed with it, which catches everything else.
"""
from __future__ import annotations

import ast
import io
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path


def _nested_quotes(path: Path) -> list[str]:
    if sys.version_info < (3, 12):
        return []                            # this interpreter's own parse is the check
    out, stack = [], []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(path.read_text()).readline))
    except (tokenize.TokenError, SyntaxError):
        return []
    for t in toks:
        if t.type == tokenize.FSTRING_START:
            q = t.string.lstrip("fFrRbB")
            if stack and q == stack[-1][0]:
                out.append(f"{path}:{t.start[0]}: f-string nested in an f-string with the same quote {q} (needs Python 3.12)")
            stack.append((q, t.start[0]))
        elif t.type == tokenize.FSTRING_END and stack:
            stack.pop()
        elif t.type == tokenize.STRING and stack:
            q = t.string.lstrip("fFrRbB")
            q = q[:3] if q[:3] in ('"""', "'''") else q[:1]
            if q == stack[-1][0]:
                out.append(f"{path}:{t.start[0]}: string inside an f-string uses the f-string's own quote {q} (needs Python 3.12)")
    return out


def _py311() -> str | None:
    exe = shutil.which("python3.11")
    if exe:
        return exe
    uv = shutil.which("uv")
    if uv:
        r = subprocess.run([uv, "python", "find", "3.11"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return None


def check(paths) -> list[str]:
    paths = [Path(p) for p in paths]
    msgs = [m for p in paths for m in _nested_quotes(p)]
    exe = _py311()
    if exe and sys.version_info[:2] != (3, 11):
        code = "import ast,sys\nfor f in sys.argv[1:]:\n    try: ast.parse(open(f).read(), f)\n    except SyntaxError as e: print(f'{f}:{e.lineno}: {e.msg} (Python 3.11)')\n"
        r = subprocess.run([exe, "-c", code, *map(str, paths)], capture_output=True, text=True)
        msgs += [ln for ln in r.stdout.splitlines() if ln.strip()]
    elif not exe and sys.version_info[:2] != (3, 11):
        print("py311check: no Python 3.11 found; only the quote scan ran", file=sys.stderr)
    return sorted(set(msgs))


if __name__ == "__main__":
    bad = check(sys.argv[1:] or [str(p) for p in Path(__file__).resolve().parents[2].rglob("*.py") if ".venv" not in str(p)])
    print("\n".join(bad) or "ok")
    sys.exit(1 if bad else 0)
