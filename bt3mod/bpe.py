"""Byte-pair encoding of the game's packed files (source/src/sys/bpe.c, Bpe_Decode; Philip Gage's "expand").

A packed file is {u32 raw size, u32 packed size} followed by blocks. A block is a pair table (runs of
"count, codes...", a code that is not itself followed by its pair), a 16-bit big-endian length and the data; every
block expands on its own. Packed() reads and changes a few bytes of a large file by expanding only the blocks that
hold them; a changed block is stored again as a plain block (identity pair table), the others are kept as they are.
"""
import bisect
import struct

PLAIN = bytes([0xFF, 0x80, 0xFE])  # identity pair table: 0xFF skips codes 0..127 and lists 128 as itself, 0xFE 129..255


def _table(src, pos):
    """Reads a block's pair table at pos: (left, right, position of its data length)."""
    left = list(range(256))
    right = [0] * 256
    count = src[pos]
    pos += 1
    c = 0
    while True:
        if count > 127:
            c += count - 127
            count = 0
        if c == 256:
            break
        for _ in range(count + 1):
            left[c] = src[pos]
            pos += 1
            if c != left[c]:
                right[c] = src[pos]
                pos += 1
            c += 1
        if c == 256:
            break
        count = src[pos]
        pos += 1
    return left, right, pos


def _expand(left, right, codes, out):
    stack = []
    for b in codes:
        stack.append(b)
        while stack:
            c = stack.pop()
            if c == left[c]:
                out.append(c)
            else:
                stack.append(right[c])
                stack.append(left[c])


def decode(data):
    size, pack_size = struct.unpack_from("<II", data, 0)
    src = memoryview(data)
    out = bytearray()
    pos, end = 8, 8 + pack_size
    while pos != end:
        left, right, pos = _table(src, pos)
        n = (src[pos] << 8) | src[pos + 1]
        pos += 2
        _expand(left, right, src[pos:pos + n], out)
        pos += n
    if len(out) != size:
        raise ValueError(f"BPE: {len(out)} bytes expanded, {size} expected")
    return bytes(out)


def blocks(data):
    """[(packed start, packed end, raw start, raw end)] of the blocks of a packed file (packed positions count
    from the start of the file, header included)."""
    size, pack_size = struct.unpack_from("<II", data, 0)
    src = memoryview(data)
    out = []
    pos, end, rpos = 8, 8 + pack_size, 0
    while pos != end:
        start = pos
        left, right, pos = _table(src, pos)
        n = (src[pos] << 8) | src[pos + 1]
        pos += 2
        lengths = {}

        def length(code):  # each code expands to a fixed length
            if code not in lengths:
                if code == left[code]:
                    lengths[code] = 1
                else:
                    lengths[code] = length(left[code]) + length(right[code])
            return lengths[code]
        rlen = sum(length(b) for b in src[pos:pos + n])
        pos += n
        out.append((start, pos, rpos, rpos + rlen))
        rpos += rlen
    return out


class Packed:
    """A packed file read and changed in place, block by block."""

    def __init__(self, data, block_table=None):
        self.data = bytes(data)
        self.blocks = [tuple(b) for b in block_table] if block_table else blocks(self.data)
        self.starts = [b[2] for b in self.blocks]
        self.cache = {}       # block index -> expanded bytes (bytearray when changed)
        self.changed = set()

    def _block(self, i):
        if i not in self.cache:
            ps, pe, rs, re_ = self.blocks[i]
            src = memoryview(self.data)
            left, right, pos = _table(src, ps)
            n = (src[pos] << 8) | src[pos + 1]
            out = bytearray()
            _expand(left, right, src[pos + 2:pos + 2 + n], out)
            self.cache[i] = out
        return self.cache[i]

    def _span(self, a, b):
        i = bisect.bisect_right(self.starts, a) - 1
        while i < len(self.blocks) and self.blocks[i][2] < b:
            yield i
            i += 1

    def read(self, a, n):
        out = bytearray()
        for i in self._span(a, a + n):
            rs = self.blocks[i][2]
            blk = self._block(i)
            out += blk[max(a, rs) - rs:min(a + n, rs + len(blk)) - rs]
        return bytes(out)

    def u32(self, a):
        return struct.unpack("<I", self.read(a, 4))[0]

    def write(self, a, buf):
        for i in self._span(a, a + len(buf)):
            rs = self.blocks[i][2]
            blk = self._block(i)
            lo, hi = max(a, rs), min(a + len(buf), rs + len(blk))
            if blk[lo - rs:hi - rs] != buf[lo - a:hi - a]:
                blk[lo - rs:hi - rs] = buf[lo - a:hi - a]
                self.changed.add(i)

    def bytes(self):
        if not self.changed:
            return self.data
        out = bytearray(self.data[:8])
        for i, (ps, pe, rs, re_) in enumerate(self.blocks):
            if i not in self.changed:
                out += self.data[ps:pe]
                continue
            blk = self.cache[i]
            for k in range(0, len(blk), 0xFFFF):
                chunk = blk[k:k + 0xFFFF]
                out += PLAIN + struct.pack(">H", len(chunk)) + chunk
        struct.pack_into("<I", out, 4, len(out) - 8)
        return bytes(out)


def patch(data, new_raw):
    """The packed file `data` changed to expand to `new_raw` (same length)."""
    p = Packed(data)
    old = decode(data)
    if len(new_raw) != len(old):
        raise ValueError("BPE patch: the expanded size must not change")
    for ps, pe, rs, re_ in p.blocks:
        if old[rs:re_] != new_raw[rs:re_]:
            p.write(rs, new_raw[rs:re_])
    return p.bytes()


def encode(raw):
    """The simplest valid packed form: plain blocks only. Larger than the game's own packing, but always correct."""
    out = bytearray(struct.pack("<II", len(raw), 0))
    pos = 0
    while pos < len(raw) or pos == 0:
        chunk = raw[pos:pos + 0xFFFF]
        out += PLAIN + struct.pack(">H", len(chunk)) + chunk
        pos += len(chunk)
        if not chunk:
            break
    struct.pack_into("<I", out, 4, len(out) - 8)
    return bytes(out)
