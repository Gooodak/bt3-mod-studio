"""Mod packs: a small JSON file listing changes, never game data, so it can be shared freely.

{
  "format": "bt3-mod-studio/1",
  "name": "...", "author": "...", "description": "...",
  "characters": {
    "0": {
      "nickname": "Goku (début)",
      "fields": {"super.damage.2": 20000},          # keys of fields.py, game units
      "texts": {"en": {"4": "Super Spirit Bomb"}},  # language -> special move number -> new name
      "base": 33,                                   # the slot becomes a copy of this character (game.py)
      "menuName": "...", "menuForm": "...",         # its names in the menus
      "transplants": [{"slot": 2, "from": 3, "fromSlot": 2},  # techniques taken from others (transplant.py)
                      {"kind": "skill", "slot": 0, "from": 31, "fromSlot": 0}],  # (a Blast 1)
      "transforms": [{"to": 2, "cost": 1}, null, null, null],  # R3 + left / up / right / down (forms.py)
      "forms": [0, 2]                               # the forms its cell of the grid offers (it heads one)
    }
  }
}
Friends who load the same pack get byte-identical files, which online play needs. A pack also travels as
a text code (to_code / from_code) and has a short fingerprint to compare before playing online.
"""
import json

FORMAT = "bt3-mod-studio/1"


def new(name="Mon pack", author="", description=""):
    return {"format": FORMAT, "name": name, "author": author, "description": description, "characters": {}}


def load(path):
    with open(path, encoding="utf-8") as f:
        pack = json.load(f)
    if pack.get("format") != FORMAT:
        raise ValueError("ce fichier n'est pas un pack BT3 Mod Studio")
    pack.setdefault("characters", {})
    return pack


def save(pack, path):
    clean(pack)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=1)


def chara(pack, n):
    return pack["characters"].setdefault(str(n), {"fields": {}, "texts": {}})


def clean(pack):
    """Drops characters without any change."""
    for k in list(pack["characters"]):
        c = pack["characters"][k]
        c["texts"] = {lang: r for lang, r in c.get("texts", {}).items() if r}
        if (not c.get("fields") and not c["texts"] and not c.get("nickname") and not c.get("transplants")
                and "base" not in c and not c.get("menuName") and "menuForm" not in c
                and c.get("transforms") is None and not c.get("forms")):
            del pack["characters"][k]
    return pack


# ---- sharing a pack as a text code -------------------------------------------------------------------------------
# A code carries the whole pack (compressed), so it needs no server: "BT3-" + version + "-" + base64url(zlib(JSON)).
CODE_PREFIX = "BT3-1-"


def _canonical(pack):
    return json.dumps(clean(json.loads(json.dumps(pack))), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def to_code(pack):
    """The pack as a text to paste in a message (a few hundred characters)."""
    import base64
    import zlib
    return CODE_PREFIX + base64.urlsafe_b64encode(zlib.compress(_canonical(pack), 9)).decode("ascii").rstrip("=")


def from_code(text):
    """The pack of a code made by to_code (spaces and line breaks of a message are ignored)."""
    import base64
    import binascii
    import zlib
    code = "".join(text.split())
    if not code.startswith(CODE_PREFIX):
        raise ValueError("ce n'est pas un code de pack BT3 Mod Studio (il commence par « BT3-1- »)")
    body = code[len(CODE_PREFIX):]
    try:
        pack = json.loads(zlib.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))).decode("utf-8"))
    except (binascii.Error, zlib.error, ValueError, UnicodeDecodeError):
        raise ValueError("ce code est incomplet ou abîmé : recopie-le en entier")
    if not isinstance(pack, dict) or pack.get("format") != FORMAT:
        raise ValueError("ce code ne contient pas un pack BT3 Mod Studio")
    pack.setdefault("characters", {})
    return pack


def fingerprint(pack):
    """A short mark of what the pack changes in the game (its name and author left out): two players with the
    same mark get the same game files, which online play needs."""
    import hashlib
    p = clean(json.loads(json.dumps(pack)))
    body = json.dumps(p.get("characters", {}), sort_keys=True, separators=(",", ":")).encode("utf-8")
    h = hashlib.sha256(body).hexdigest().upper()
    return h[:4] + "-" + h[4:8]
