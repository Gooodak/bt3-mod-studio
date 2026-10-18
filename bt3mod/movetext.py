"""The move list of a character (pause menu "command list"), UTF-16 text in 9 languages.

A line "!F*CCCname" (or "!F&NNN*CCCname") names a move; when the next line is a "!1#<PAD=...>" control line it is
one of the special moves (Blast 1, Blast 2, Ultimate). CCC is the cost shown next to it.
"""
import re

# 0-based costume pack entries of each language
LANGS = {
    "en": (44, "Anglais"),
    "en2": (46, "Anglais (2e copie)"),
    "fr": (49, "Français"),
    "es": (47, "Espagnol"),
    "de": (48, "Allemand"),
    "it": (50, "Italien"),
    "ja": (43, "Japonais"),
    "ko": (51, "Coréen"),
}

_NAME = re.compile(r"^(!F(?:&\d{3})?\*\d{3})(.*)$")
_PAD = re.compile(r"^!1(?:&\d{3})?#")


def decode(raw):
    t = raw.decode("utf-16-le", errors="replace")
    return t.split("\0", 1)[0]


def encode(text):
    return text.encode("utf-16-le") + b"\0\0"


def specials(text):
    """[(line index, name)] of the special moves, in order."""
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        m = _NAME.match(line)
        if m and i + 1 < len(lines) and _PAD.match(lines[i + 1]):
            out.append((i, m.group(2)))
    return out


def rename(text, index, new_name):
    """Renames the index-th special move."""
    lines = text.split("\n")
    line_no, _ = specials(text)[index]
    m = _NAME.match(lines[line_no])
    lines[line_no] = m.group(1) + new_name.replace("\n", " ")
    return "\n".join(lines)
