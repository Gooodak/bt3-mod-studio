"""Pictures of the game's menus for the tool's window: the grid chips (64 x 64, one per character in the menu
archives) and the large pictures of the select screens (file id 0x2F9 + character, 256 x 512), turned into PNG.

A texture file (docs/systems/graphics.md; source/include/sys/gfxm_b_b.h, TexFile / TexEntry): u32 count, u32 entry
table offset in words, 0x40-byte entries {pixel packet offset in words, CLUT packet offset, ..., TEX0 @0x30}. A
packet is a DMA tag, a GIF tag with A+D registers (BITBLTBUF, TRXPOS, TRXREG, TRXDIR), an IMAGE GIF tag, the data.
The 8-bit pictures are sent to the GS as 32-bit pixels (half as wide, half as high): read back as 8-bit pixels they
come out in the GS's 8-bit order, which unswizzle8 undoes. Their 256-colour CLUT is in the GS's CSM1 order (entries
8..15 and 16..23 of every 32 swapped) and its alpha goes from 0 to 0x80 (opaque).
"""
import functools
import operator
import struct
import zlib

from . import bpe

FACE_FILE = 0x2F9 - 1   # pzs3us1 index + character: the large picture of the select screens
PSMCT32, PSMT8 = 0x00, 0x13


def _packet(r, ofs):
    """(registers {address: value}, offset of the data) of an upload packet."""
    nloop = struct.unpack_from("<Q", r, ofs + 16)[0] & 0x7FFF
    regs, p = {}, ofs + 32
    for _ in range(nloop):
        val, reg = struct.unpack_from("<QQ", r, p)
        regs[reg & 0xFF] = val
        p += 16
    return regs, p + 16  # (the IMAGE GIF tag)


@functools.lru_cache(maxsize=8)
def _unswizzle8(w, h):
    """For each 8-bit pixel of a w x h picture (row by row), its byte in data sent as w/2 x h/2 32-bit pixels."""
    out = []
    for y in range(h):
        block_y = (y & ~0xF) * w
        swap = (((y + 2) >> 2) & 1) * 4
        col_y = ((((y & ~3) >> 1) + (y & 1)) & 7) * w * 2
        byte_y = (y >> 1) & 1
        for x in range(w):
            out.append(block_y + (x & ~0xF) * 2 + col_y + ((x + swap) & 7) * 4 + byte_y + ((x >> 2) & 2))
    return operator.itemgetter(*out)


def _csm1(i):
    return (i & ~0x18) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)


def texture(r, n=0):
    """Texture n of a texture file as (width, height, RGBA bytes)."""
    eo = struct.unpack_from("<I", r, 4)[0] * 4 + 0x40 * n
    pix_ofs, clut_ofs = struct.unpack_from("<II", r, eo)
    tex0 = struct.unpack_from("<Q", r, eo + 0x30)[0]
    psm = (tex0 >> 20) & 0x3F
    w, h = 1 << ((tex0 >> 26) & 0xF), 1 << ((tex0 >> 30) & 0xF)
    if psm != PSMT8:
        raise ValueError("unsupported texture format 0x%X" % psm)
    regs, at = _packet(r, pix_ofs * 4)
    rrw, rrh = regs.get(0x52, 0) & 0xFFF, (regs.get(0x52, 0) >> 32) & 0xFFF
    sent = r[at:at + w * h]
    if (rrw, rrh) == (w // 2, h // 2):          # sent as 32-bit pixels
        idx = bytes(_unswizzle8(w, h)(sent))
    elif (rrw, rrh) == (w, h):                  # sent as 8-bit pixels: in order
        idx = sent
    else:
        raise ValueError("unsupported texture upload %dx%d for %dx%d" % (rrw, rrh, w, h))
    _, at = _packet(r, clut_ofs * 4)
    clut = r[at:at + 1024]
    pal = [clut[4 * _csm1(i):4 * _csm1(i) + 4] for i in range(256)]
    out = bytearray(w * h * 4)
    for c in range(4):
        if c < 3:
            table = bytes(p[c] for p in pal)
        else:
            table = bytes(min(255, p[3] * 255 // 0x80) for p in pal)
        out[c::4] = idx.translate(table)
    return w, h, bytes(out)


def face(read, chara):
    """The large picture of a character (read(pzs3us1 index) gives a file's bytes): (width, height, RGBA)."""
    return texture(bpe.decode(read(FACE_FILE + chara)))


def crop(w, h, px):
    """The smallest box holding every pixel that is not fully transparent: (x0, y0, w, h, RGBA)."""
    alpha = px[3::4]
    rows = [y for y in range(h) if any(alpha[y * w:(y + 1) * w])]
    if not rows:
        return 0, 0, w, h, px
    y0, y1 = rows[0], rows[-1] + 1
    x0, x1 = w, 0
    for y in range(y0, y1):
        line = alpha[y * w:(y + 1) * w]
        nz = [x for x in range(w) if line[x]]
        if nz:
            x0, x1 = min(x0, nz[0]), max(x1, nz[-1] + 1)
    out = b"".join(px[(y * w + x0) * 4:(y * w + x1) * 4] for y in range(y0, y1))
    return x0, y0, x1 - x0, y1 - y0, out


def _weights(n, m):
    """Area-average weights from n samples to m: for each output, [(input index, weight)] (weights sum to 1)."""
    scale = n / m
    out = []
    for j in range(m):
        a, b = j * scale, (j + 1) * scale
        ws = []
        i = int(a)
        while i < b and i < n:
            cover = min(b, i + 1) - max(a, i)
            if cover > 1e-9:
                ws.append((i, cover / scale))
            i += 1
        out.append(ws)
    return out


def _resample(ch, w, h, wx, wy):
    rows = []
    for y in range(h):
        line = ch[y * w:(y + 1) * w]
        rows.append([sum([line[i] * f for i, f in ws]) for ws in wx])
    return [[sum([rows[i][x] * f for i, f in ws]) for x in range(len(wx))] for ws in wy]


@functools.lru_cache(maxsize=16)
def _matrix(n, m):
    """numpy weights from n samples to m: area average when shrinking, linear between neighbours when growing."""
    import numpy as np
    out = np.zeros((m, n), dtype=np.float32)
    if m <= n:
        for j, ws in enumerate(_weights(n, m)):
            for i, f in ws:
                out[j, i] = f
        return out
    for j in range(m):
        c = (j + 0.5) * n / m - 0.5
        i0 = int(np.floor(c))
        t = c - i0
        for i, f in ((i0, 1 - t), (i0 + 1, t)):
            out[j, min(n - 1, max(0, i))] += f
    return out


def _resize_np(w, h, px, nw, nh):
    import numpy as np
    img = np.frombuffer(px, dtype=np.uint8).reshape(h, w, 4).astype(np.float32)
    a = img[..., 3:4] / 255.0
    img[..., :3] *= a                                   # colours weighted by their alpha
    wy, wx = _matrix(h, nh), _matrix(w, nw)
    tmp = (wy @ img.reshape(h, w * 4)).reshape(nh, w, 4)
    out = (tmp.transpose(0, 2, 1) @ wx.T).transpose(0, 2, 1)  # (matrix products: numpy's fast path)
    al = out[..., 3:4]
    rgb = np.where(al > 0.5, out[..., :3] / np.maximum(al, 1e-6) * 255.0, 0)
    res = np.concatenate([rgb, al], axis=2)
    return np.clip(res + 0.5, 0, 255).astype(np.uint8).tobytes()


def resize(w, h, px, nw, nh):
    """RGBA resized to nw x nh (area average to shrink, linear to grow), colours weighted by their alpha (no dark
    fringes). Quick with numpy; without it, a slower area average in plain Python."""
    try:
        return _resize_np(w, h, px, nw, nh)
    except ImportError:
        pass
    a = px[3::4]
    wx, wy = _weights(w, nw), _weights(h, nh)
    out = bytearray(nw * nh * 4)
    if a.count(255) == len(a):  # opaque: no weighting
        for c in range(3):
            res = _resample(px[c::4], w, h, wx, wy)
            out[c::4] = bytes(min(255, int(v + 0.5)) for row in res for v in row)
        out[3::4] = b"\xff" * (nw * nh)
        return bytes(out)
    res = [_resample([v * al for v, al in zip(px[c::4], a)], w, h, wx, wy) for c in range(3)]
    res.append(_resample(a, w, h, wx, wy))
    k = 0
    for y in range(nh):
        ar, rr, gr, br = res[3][y], res[0][y], res[1][y], res[2][y]
        for x in range(nw):
            al = ar[x]
            if al > 0.5:
                out[k] = min(255, int(rr[x] / al + 0.5))
                out[k + 1] = min(255, int(gr[x] / al + 0.5))
                out[k + 2] = min(255, int(br[x] / al + 0.5))
                out[k + 3] = min(255, int(al + 0.5))
            k += 4
    return bytes(out)


def png(w, h, px, level=6):
    """RGBA bytes as a PNG file."""
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    stride = w * 4
    raw = b"".join(b"\0" + px[y * stride:(y + 1) * stride] for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, level)) + chunk(b"IEND", b""))
