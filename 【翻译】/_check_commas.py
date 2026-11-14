# -*- coding: utf-8 -*-
from pathlib import Path
import sys
name = sys.argv[1]
lines = Path(name).read_text(encoding="utf-8").splitlines()
for i, l in enumerate(lines, 1):
    s = l.strip()
    if not s.startswith('"'):
        continue
    if s.endswith('",') or s.endswith('",\\'):
        continue
    if s.endswith('"'):
        print(f"NOCOMMA {i}: {s[-40:]}")
