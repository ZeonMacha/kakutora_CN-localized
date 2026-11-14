# -*- coding: utf-8 -*-
from pathlib import Path
p = Path("_zh_14_010.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    '"呵呵，燕的话\\n我觉得会喜欢。"',
    '"呵呵，要是燕，\\n我觉得\\n会喜欢。",',
)
# add missing trailing commas on list items that are complete statements
lines = text.splitlines()
out = []
for i, l in enumerate(lines):
    s = l.rstrip()
    nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
    if s.endswith('"') and (nxt.startswith('"') or nxt.startswith("]")):
        s = s + ","
    out.append(s)
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("fixed")
