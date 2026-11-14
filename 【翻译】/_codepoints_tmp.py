import unicodedata
chars = "啵噻哽啦咯啰喔哦呀喃"
for c in chars:
    print(f"U+{ord(c):04X} {c} {unicodedata.name(c, '?')}")
print("---given---")
for u in [0x5575, 0x567B, 0x54FD, 0x5566, 0x54AF, 0x54E6]:
    c = chr(u)
    print(f"U+{u:04X} {c} {unicodedata.name(c, '?')}")
