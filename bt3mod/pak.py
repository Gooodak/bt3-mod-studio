"""Pack files of Budokai Tenkaichi 3 (the numbered .bin files of pzs3us1).

Layout: u32 entry count N, then N + 1 u32 offsets (the last one is the end of the data). The header and every
entry start on a 0x40 boundary; an empty entry has the same offset as the next one.
"""
import struct

ALIGN = 0x40


def _align(n, a=ALIGN):
    return (n + a - 1) // a * a


def is_pak(data, size=None):
    if len(data) < 8:
        return False
    n = struct.unpack_from("<I", data, 0)[0]
    if not 0 < n < 5000 or len(data) < 4 + 4 * (n + 1):
        return False
    offs = struct.unpack_from("<%dI" % (n + 1), data, 4)
    size = len(data) if size is None else size
    return all(offs[i] <= offs[i + 1] for i in range(n)) and offs[-1] <= size


def read(data):
    """Returns the list of entries (bytes, possibly empty)."""
    n = struct.unpack_from("<I", data, 0)[0]
    offs = struct.unpack_from("<%dI" % (n + 1), data, 4)
    return [data[offs[i]:offs[i + 1]] for i in range(n)]


def write(entries):
    """Builds a pack from a list of entries, with the game's 0x40 alignment."""
    n = len(entries)
    pos = _align(4 + 4 * (n + 1))
    offs, body = [], bytearray()
    for e in entries:
        offs.append(pos + len(body))
        body += e
        body += b"\0" * (_align(len(body)) - len(body))
    offs.append(pos + len(body))
    head = struct.pack("<I%dI" % (n + 1), n, *offs)
    head += b"\0" * (pos - len(head))
    return bytes(head) + bytes(body)
