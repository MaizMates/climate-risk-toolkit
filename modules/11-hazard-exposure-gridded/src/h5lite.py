"""Minimal reader for the HDF5 files in the World Bank CCKP bucket.

The module may use only the standard library plus numpy, and netCDF4 and h5py are not allowed, so
this reads the one layout these files have: HDF5 superblock v2, a root group of link messages, and
chunked datasets compressed with shuffle then deflate. It refuses anything else. It is checked
against the CCKP country API in src/gridded.py (validation) and on a file it writes itself in
tests/test_h5lite.py.
"""
import struct
import zlib

import numpy as np


def unfilter(chunk, es):
    """Undo deflate, then the byte shuffle (all first bytes, then all second bytes, ...)."""
    raw = zlib.decompress(chunk)
    raw = np.frombuffer(raw, np.uint8).reshape(es, -1).T.tobytes()
    return np.frombuffer(raw, "<f%d" % es)


class H5:
    def __init__(self, data):
        if data[:8] != b"\x89HDF\r\n\x1a\n" or data[8] != 2:
            raise ValueError("not an HDF5 superblock v2 file")
        self.d = data
        self.root = struct.unpack("<Q", data[12 + 8 + 8 + 8:12 + 8 + 8 + 8 + 8])[0]

    def ohdr(self, off):
        d = self.d
        if d[off:off + 4] != b"OHDR":
            raise ValueError(f"no object header at {off}")
        flags = d[off + 5]
        p = off + 6
        if flags & 0x20:
            p += 16
        if flags & 0x10:
            p += 4
        w = {0: 1, 1: 2, 2: 4, 3: 8}[flags & 3]
        n0 = int.from_bytes(d[p:p + w], "little")
        p += w
        msgs = []

        def walk(p, end):
            while p + 4 <= end:
                t = d[p]
                s = int.from_bytes(d[p + 1:p + 3], "little")
                p += 4
                if flags & 4:
                    p += 2
                if t == 0 and s == 0:
                    break
                msgs.append((t, d[p:p + s]))
                if t == 0x10:       # continuation block
                    o = int.from_bytes(d[p:p + 8], "little")
                    n = int.from_bytes(d[p + 8:p + 16], "little")
                    walk(o + 4, o + n - 4)
                p += s

        walk(p, p + n0)
        return msgs

    def links(self):
        out = {}
        for t, b in self.ohdr(self.root):
            if t != 6:
                continue
            fl = b[1]
            p = 2
            if fl & 8:
                p += 1
            if fl & 4:
                p += 8
            if fl & 16:
                p += 1
            w = 1 << (fl & 3)
            n = int.from_bytes(b[p:p + w], "little")
            p += w
            out[b[p:p + n].decode()] = int.from_bytes(b[p + n:p + n + 8], "little")
        return out

    def _chunks(self, addr, nd):
        d = self.d
        if d[addr:addr + 4] != b"TREE":
            raise ValueError("chunk index is not a v1 B-tree")
        lvl = d[addr + 5]
        n = int.from_bytes(d[addr + 6:addr + 8], "little")
        p = addr + 24
        out = []
        for _ in range(n):
            size, _mask = struct.unpack("<II", d[p:p + 8])
            off = struct.unpack("<" + "Q" * nd, d[p + 8:p + 8 + 8 * nd])
            p += 8 + 8 * nd
            child = int.from_bytes(d[p:p + 8], "little")
            p += 8
            out += self._chunks(child, nd) if lvl else [(off, size, child)]
        return out

    def var(self, name):
        m = dict(self.ohdr(self.links()[name]))
        lay = m[8]
        if lay[0] != 3 or lay[1] != 2:
            raise ValueError("only chunked layout v3 is supported")
        nd = lay[2]
        addr = int.from_bytes(lay[3:11], "little")
        dims = struct.unpack("<" + "I" * nd, lay[11:11 + 4 * nd])
        es, cd = dims[-1], dims[:-1]
        rank = m[1][1]
        shape = struct.unpack("<" + "Q" * rank, m[1][4:4 + 8 * rank])
        arr = np.zeros(shape, dtype="<f%d" % es)
        for o, size, a in self._chunks(addr, nd):
            c = unfilter(self.d[a:a + size], es).reshape(cd)
            sl = tuple(slice(o[i], o[i] + cd[i]) for i in range(len(cd)))
            arr[sl] = c[tuple(slice(0, s) for s in arr[sl].shape)]
        return arr
