"""복구 단위별(고정 블록 / CDC / 레코드) 소거복구 비교 구현.

세 방식은 단위 분할(split)과 손상 파일에서의 단위 위치 식별(locate)만 다르고,
스트라이프 배치·Reed-Solomon·해시·서명·재검증은 동일한 코드를 쓴다.

파일 모델: 개행(\\n)으로 구분된 레코드 파일. 레코드 id는 첫 번째 쉼표 앞 필드.
공격 모델: 승인 후 완전 레코드 삭제(이후 바이트가 앞으로 이동).
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass

import numpy as np
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from . import erasure

HASH_BYTES = 32
ID_BYTES = 10
WEAK_BYTES = 4
SIG_BYTES = 64
SCHEME_BYTES = 32
_MANIFEST_MAGIC = b"SIM-MNF2"
_HEADER = struct.Struct(">8sQIIIIQ32s32s32s")
_HEADER_BYTES = _HEADER.size


def sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


# ---------------------------------------------------------------------------
# 단위 분할 / 위치 식별
# ---------------------------------------------------------------------------

def _split_lines(data: bytes) -> list[bytes]:
    return [ln + b"\n" for ln in data.split(b"\n")[:-1]] if data.endswith(b"\n") else \
        [ln + b"\n" for ln in data.split(b"\n")]


def _record_id(rec: bytes) -> bytes:
    return rec.split(b",", 1)[0][:ID_BYTES].ljust(ID_BYTES, b"\0")


def _weak_windows(arr: np.ndarray, w: int) -> np.ndarray:
    """모든 길이 w 윈도우의 약한 체크섬(Adler 유사)을 벡터 연산으로 계산."""
    a = arr.astype(np.int64)
    s1 = np.concatenate(([0], np.cumsum(a)))
    wt = np.concatenate(([0], np.cumsum(a * np.arange(len(a), dtype=np.int64))))
    i = np.arange(len(a) - w + 1, dtype=np.int64)
    sa = s1[i + w] - s1[i]
    sb = (wt[i + w] - wt[i]) - i * sa
    return (sa & 0xFFFF) | ((sb & 0xFFFF) << 16)


def _weak(block: bytes) -> int:
    return int(_weak_windows(np.frombuffer(block, dtype=np.uint8), len(block))[0])


_GEAR = np.random.default_rng(0xC0FFEE).integers(0, 2**63, size=256, dtype=np.uint64)


def _cdc_cuts(data: bytes, avg: int) -> list[int]:
    """Gear 해시 기반 CDC. 청크 종료 오프셋 목록(마지막은 len(data))을 반환.

    해시는 직전 64바이트에만 의존하므로 삭제 이후 경계가 다시 동기화된다.
    min=avg/4, max=avg*4. 마스크 비트 수는 (avg - min)에 맞춘다.
    """
    n = len(data)
    if n == 0:
        return []
    arr = np.frombuffer(data, dtype=np.uint8)
    g = _GEAR[arr]
    h = np.zeros(n, dtype=np.uint64)
    for j in range(64):
        if j >= n:
            break
        h[j:] += g[: n - j] << np.uint64(j)
    mn, mx = max(avg // 4, 1), avg * 4
    bits = max(int(round(math.log2(max(avg - mn, 2)))), 1)
    # 상위 비트는 직전 64바이트 전체에 의존한다(하위 비트는 최근 몇 바이트만 반영).
    cand = np.flatnonzero((h >> np.uint64(64 - bits)) == 0) + 1  # 청크 끝 오프셋
    cuts, start = [], 0
    while start < n:
        lo = start + mn
        idx = int(np.searchsorted(cand, lo))
        end = int(cand[idx]) if idx < len(cand) else n
        end = min(end, start + mx, n)
        cuts.append(end)
        start = end
    return cuts


class Scheme:
    """복구 단위 분할 방식의 공통 인터페이스."""

    name = ""
    entry_bytes = 0
    param = 0
    has_ids = False          # 매니페스트에 레코드 식별자를 기록하는가
    has_weak = False         # 이동 블록 탐색용 약한 체크섬을 기록하는가
    sort_stripes = False     # 길이순으로 정렬해 비슷한 크기끼리 같은 스트라이프에 배치하는가

    def split(self, data: bytes) -> list[bytes]:
        raise NotImplementedError

    def entries(self, units: list[bytes]) -> bytes:
        raise NotImplementedError

    def locate(self, damaged: bytes, units_meta: list[tuple[bytes, int]], man: "Manifest") -> dict[int, bytes]:
        """손상 파일에서 해시가 일치하는 단위를 찾아 {단위 인덱스: 바이트}로 반환."""
        raise NotImplementedError


class RecordScheme(Scheme):
    """단위 = 완전한 레코드. 식별자로 누락 위치를 지정한다."""

    name = "record"
    entry_bytes = ID_BYTES + 4 + HASH_BYTES
    has_ids = True

    def split(self, data):
        return _split_lines(data)

    def entries(self, units):
        return b"".join(_record_id(u) + struct.pack(">I", len(u)) + sha(u) for u in units)

    def locate(self, damaged, units_meta, man):
        by_id = {_record_id(r): r for r in _split_lines(damaged)}
        found = {}
        for idx, (uid, _len, h) in enumerate(man.table):
            rec = by_id.get(uid)
            if rec is not None and sha(rec) == h:
                found[idx] = rec
        return found


class SortedRecordScheme(RecordScheme):
    """레코드 단위 + 길이 정렬 스트라이프(B4). 비슷한 크기끼리 묶어 패딩을 줄인다.

    스트라이프 구성은 매니페스트의 길이 표에서 결정적으로 재계산되므로 별도 매핑 비용이 없다.
    """

    name = "record_sorted"
    sort_stripes = True


class RecordGroupScheme(Scheme):
    """단위 = 연속한 완전 레코드 묶음(목표 크기 이상이 될 때까지). 경계가 레코드에 정렬된 블록.

    작은 레코드의 식별 메타데이터 비용을 묶음 단위로 분산한다. 묶음의 첫 레코드 id로 위치를 찾고,
    묶음 내 레코드가 하나라도 삭제되면 묶음 해시가 어긋나 묶음 전체가 소거로 처리된다.
    """

    has_ids = True

    def __init__(self, target: int):
        self.target = target
        self.param = target
        self.name = f"recgroup{target}"
        self.entry_bytes = ID_BYTES + 4 + HASH_BYTES

    def split(self, data):
        out, cur, size = [], [], 0
        for r in _split_lines(data):
            cur.append(r)
            size += len(r)
            if size >= self.target:
                out.append(b"".join(cur))
                cur, size = [], 0
        if cur:
            out.append(b"".join(cur))
        return out

    def entries(self, units):
        return b"".join(_record_id(u) + struct.pack(">I", len(u)) + sha(u) for u in units)

    def locate(self, damaged, units_meta, man):
        pos, off = {}, 0
        for r in _split_lines(damaged):
            pos[_record_id(r)] = off
            off += len(r)
        found = {}
        for idx, (uid, ln, h) in enumerate(man.table):
            o = pos.get(uid)
            if o is not None and sha(damaged[o:o + ln]) == h:
                found[idx] = damaged[o:o + ln]
        return found


class BlockScheme(Scheme):
    """단위 = 고정 크기 블록. 약한 체크섬 + SHA-256으로 이동된 블록을 재탐색(PAR2 방식)."""

    def __init__(self, size: int):
        self.size = size
        self.param = size
        self.name = f"block{size}"
        self.entry_bytes = HASH_BYTES + WEAK_BYTES
        self.has_weak = True

    def split(self, data):
        s = self.size
        return [data[i:i + s] for i in range(0, len(data), s)]

    def entries(self, units):
        return b"".join(sha(u) + struct.pack(">I", _weak(u)) for u in units)

    def locate(self, damaged, units_meta, man):
        arr = np.frombuffer(damaged, dtype=np.uint8)
        found = {}
        by_len: dict[int, dict[int, list[int]]] = {}
        for idx, (_uid, ln, _h) in enumerate(man.table):
            by_len.setdefault(ln, {}).setdefault(man.weak[idx], []).append(idx)
        for ln, weak_map in by_len.items():
            if ln > len(arr):
                continue
            ws = _weak_windows(arr, ln)
            keys = np.fromiter(weak_map.keys(), dtype=np.int64)
            for pos in np.flatnonzero(np.isin(ws, keys)):
                cand = damaged[pos:pos + ln]
                digest = sha(cand)
                for idx in weak_map[int(ws[pos])]:
                    if idx not in found and man.table[idx][2] == digest:
                        found[idx] = cand
        return found


class CDCScheme(Scheme):
    """단위 = 내용 정의 청크. 손상 파일을 다시 청킹해 해시로 대조(PAR3 방식)."""

    def __init__(self, avg: int, sort: bool = False):
        """sort=True: 비슷한 길이의 청크를 같은 스트라이프로 묶어 최대 청크 패딩을 피한다(record_sorted와 동일 규칙)."""
        self.avg = avg
        self.param = avg
        self.sort_stripes = sort
        self.name = f"cdcsorted{avg}" if sort else f"cdc{avg}"
        self.entry_bytes = 4 + HASH_BYTES

    def split(self, data):
        out, start = [], 0
        for end in _cdc_cuts(data, self.avg):
            out.append(data[start:end])
            start = end
        return out

    def entries(self, units):
        return b"".join(struct.pack(">I", len(u)) + sha(u) for u in units)

    def locate(self, damaged, units_meta, man):
        chunks = {sha(c): c for c in self.split(damaged)}
        return {i: chunks[h] for i, (_u, _l, h) in enumerate(man.table) if h in chunks}


# ---------------------------------------------------------------------------
# 스트라이프 배치 (인터리브)
# ---------------------------------------------------------------------------

def stripes(n: int, k: int, lens: list[int] | None = None) -> list[list[int]]:
    """단위 인덱스를 스트라이프로 분배.

    lens가 None이면 인터리브(연속 삭제가 여러 스트라이프로 흩어짐),
    주어지면 길이순 정렬 후 연속 k개씩 묶는다(패딩 최소화, 정렬은 안정 정렬이라 결정적).
    """
    ns = math.ceil(n / k)
    if lens is None:
        return [list(range(s, n, ns)) for s in range(ns)]
    order = sorted(range(n), key=lambda u: lens[u])
    size = math.ceil(n / ns)
    return [order[i:i + size] for i in range(0, n, size)]


def parity_bytes(lens: list[int], k: int, m: int, packed: bool = False) -> int:
    return sum(m * max(lens[u] for u in st) for st in stripes(len(lens), k, lens if packed else None))


def choose_k(lens: list[int], m: int, meta_bytes: int, orig: int, budget: float, packed: bool = False):
    """O_total <= budget 을 만족하는 가장 작은 k(=가장 큰 복구력). 불가능하면 None."""
    for k in range(2, erasure.K_MAX + 1):
        if (meta_bytes + parity_bytes(lens, k, m, packed)) / orig <= budget:
            return k
    return None


# ---------------------------------------------------------------------------
# 매니페스트 (서명 + 버전 + 패리티 해시)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Manifest:
    version: int
    k: int
    m: int
    n: int
    param: int
    orig: int
    scheme_id: str
    commit: bytes
    parity_hash: bytes
    table: tuple[tuple[bytes, int, bytes], ...]  # (id, length, hash)
    weak: tuple[int, ...]
    raw: bytes
    signature: bytes

    @property
    def total_bytes(self) -> int:
        return len(self.raw) + len(self.signature)


def _scheme_bytes(scheme: Scheme) -> bytes:
    encoded = scheme.name.encode("ascii")
    if not encoded or len(encoded) > SCHEME_BYTES:
        raise ValueError("매니페스트 방식 식별자는 1~32바이트 ASCII여야 한다.")
    return encoded.ljust(SCHEME_BYTES, b"\0")


def _parse_manifest(raw: bytes, signature: bytes, scheme: Scheme) -> Manifest:
    """서명 대상 raw에서 복구에 쓰는 모든 필드를 다시 구성한다.

    별도 Python 속성을 신뢰하지 않고, 방식 식별자·버전·원본 크기·단위표·커밋·
    패리티 해시를 서명된 바이트에서만 파싱한다. 형식이 맞지 않으면 fail-closed 한다.
    """
    if len(raw) < _HEADER_BYTES:
        raise ValueError("manifest_too_short")
    magic, version, k, m, n, param, orig, scheme_raw, commit, parity_hash = _HEADER.unpack_from(raw)
    if magic != _MANIFEST_MAGIC:
        raise ValueError("bad_manifest_magic")
    try:
        scheme_id = scheme_raw.rstrip(b"\0").decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("bad_scheme_id") from exc
    if scheme_id != scheme.name or param != scheme.param:
        raise ValueError("scheme_mismatch")
    if not (1 <= n and 1 <= k <= erasure.K_MAX and 1 <= m <= erasure.M_MAX and orig > 0):
        raise ValueError("bad_manifest_parameters")

    expected = _HEADER_BYTES + n * scheme.entry_bytes
    if len(raw) != expected:
        raise ValueError("bad_manifest_length")

    table: list[tuple[bytes, int, bytes]] = []
    weak: list[int] = []
    off = _HEADER_BYTES
    for i in range(n):
        entry = raw[off:off + scheme.entry_bytes]
        off += scheme.entry_bytes
        if scheme.has_ids:
            uid = entry[:ID_BYTES]
            ln = struct.unpack(">I", entry[ID_BYTES:ID_BYTES + 4])[0]
            digest = entry[ID_BYTES + 4:ID_BYTES + 4 + HASH_BYTES]
            w = 0
        elif scheme.has_weak:
            uid = b""
            digest = entry[:HASH_BYTES]
            w = struct.unpack(">I", entry[HASH_BYTES:HASH_BYTES + WEAK_BYTES])[0]
            ln = scheme.param if i < n - 1 else orig - scheme.param * (n - 1)
        else:
            uid = b""
            ln = struct.unpack(">I", entry[:4])[0]
            digest = entry[4:4 + HASH_BYTES]
            w = 0
        if ln <= 0 or len(digest) != HASH_BYTES:
            raise ValueError("bad_manifest_entry")
        if scheme.has_weak and ln > scheme.param:
            raise ValueError("bad_block_length")
        table.append((uid, ln, digest))
        weak.append(w)

    if sum(ln for _uid, ln, _digest in table) != orig:
        raise ValueError("original_size_mismatch")
    return Manifest(version, k, m, n, param, orig, scheme_id, commit, parity_hash,
                    tuple(table), tuple(weak), raw, signature)


def build_manifest(scheme: Scheme, units, data, k, m, parity_blob, version, sk) -> Manifest:
    ent = scheme.entries(units)
    raw = _HEADER.pack(
        _MANIFEST_MAGIC,
        version,
        k,
        m,
        len(units),
        scheme.param,
        len(data),
        _scheme_bytes(scheme),
        sha(data),
        sha(parity_blob),
    ) + ent
    signature = sk.sign(raw)
    return _parse_manifest(raw, signature, scheme)


def verify_manifest(
    man: Manifest,
    scheme: Scheme,
    pk: Ed25519PublicKey,
    latest_version: int,
    parity_blob: bytes,
) -> str | None:
    """실패 사유 문자열 또는 None. 서명 뒤 raw 재파싱과 객체 일치까지 확인한다."""
    try:
        pk.verify(man.signature, man.raw)
    except InvalidSignature:
        return "bad_signature"
    try:
        signed = _parse_manifest(man.raw, man.signature, scheme)
    except ValueError:
        return "bad_manifest"
    if man != signed:
        return "manifest_inconsistent"
    if signed.version != latest_version:
        return "stale_version"
    if sha(parity_blob) != signed.parity_hash:
        return "parity_tampered"
    return None


# ---------------------------------------------------------------------------
# 승인(encode) / 복구(repair)
# ---------------------------------------------------------------------------

@dataclass
class Protected:
    scheme: Scheme
    manifest: Manifest
    parity: list[np.ndarray]  # 생성 시 캐시. 복구에서는 검증된 parity_blob을 다시 파싱한다.
    parity_blob: bytes
    meta_bytes: int
    parity_total: int
    padded_bytes: int
    orig: int

    @property
    def o_total(self) -> float:
        return (self.meta_bytes + self.parity_total) / self.orig


def _pad(units: list[bytes], idxs: list[int], slot: int) -> np.ndarray:
    mat = np.zeros((len(idxs), slot), dtype=np.uint8)
    for r, u in enumerate(idxs):
        mat[r, :len(units[u])] = np.frombuffer(units[u], dtype=np.uint8)
    return mat


def protect(scheme: Scheme, data: bytes, m: int, budget: float, sk, version: int = 1) -> Protected | None:
    """예산 안에서 가장 작은 k를 골라 승인 상태(매니페스트+패리티)를 만든다. 불가능하면 None."""
    units = scheme.split(data)
    lens = [len(u) for u in units]
    meta = _HEADER_BYTES + len(units) * scheme.entry_bytes + SIG_BYTES
    k = choose_k(lens, m, meta, len(data), budget, scheme.sort_stripes)
    if k is None:
        return None
    parity, padded = [], 0
    for st in stripes(len(units), k, lens if scheme.sort_stripes else None):
        slot = max(lens[u] for u in st)
        padded += sum(slot - lens[u] for u in st)
        parity.append(erasure.encode(_pad(units, st, slot), m))
    blob = b"".join(p.tobytes() for p in parity)
    man = build_manifest(scheme, units, data, k, m, blob, version, sk)
    return Protected(scheme, man, parity, blob, man.total_bytes, len(blob), padded, len(data))


@dataclass
class RepairResult:
    success: bool
    reason: str
    erased_units: int
    erased_bytes: int
    repair_read_bytes: int
    coverage: float  # 검증된(발견+복구) 바이트 / 원본 바이트
    # 전체 I/O 정의(바이트). 실패한 시도도 기록한다.
    scan_bytes: int = 0         # 손상 파일 전체 스캔(위치 식별)
    manifest_bytes: int = 0     # 서명 매니페스트 읽기
    parity_verify_bytes: int = 0  # 패리티 전체 해시 검증을 위한 읽기
    reverify_bytes: int = 0     # 복구 결과 파일 재해시
    written_bytes: int = 0      # 복구된 파일 쓰기

    @property
    def total_read_bytes(self) -> int:
        return (self.scan_bytes + self.manifest_bytes + self.parity_verify_bytes
                + self.repair_read_bytes + self.reverify_bytes)


def repair(prot: Protected, damaged: bytes, pk, latest_version: int,
           parity_blob: bytes | None = None) -> tuple[bytes | None, RepairResult]:
    """검증 → 위치 식별 → 소거복구 → 단위 해시·파일 커밋 재검증. 하나라도 어긋나면 출력 없이 실패."""
    man, sch = prot.manifest, prot.scheme
    blob = prot.parity_blob if parity_blob is None else parity_blob
    why = verify_manifest(man, sch, pk, latest_version, blob)
    if why:
        return None, RepairResult(False, why, 0, 0, 0, 0.0, manifest_bytes=man.total_bytes,
                                  parity_verify_bytes=len(blob))

    try:
        verified_parity = _parse_parity_blob(man, sch, blob)
    except ValueError:
        return None, RepairResult(False, "bad_parity_layout", 0, 0, 0, 0.0,
                                  manifest_bytes=man.total_bytes, parity_verify_bytes=len(blob))

    found = sch.locate(damaged, None, man)
    lens = [t[1] for t in man.table]
    erased = [i for i in range(man.n) if i not in found]
    erased_bytes = sum(lens[i] for i in erased)
    ok_bytes = sum(lens[i] for i in found)
    recovered, read_bytes, reason = {}, 0, ""

    for st, par in zip(stripes(man.n, man.k, lens if sch.sort_stripes else None), verified_parity):
        er = [pos for pos, u in enumerate(st) if u not in found]
        if not er:
            continue
        if len(er) > man.m:
            reason = reason or "erasures_exceed_parity"
            continue
        slot = par.shape[1]
        surv = {pos: _pad_one(found[u], slot) for pos, u in enumerate(st) if u in found}
        dec = erasure.decode(surv, er, par, len(st), slot)
        read_bytes += len(st) * slot  # 생존 k-e개 + 패리티 e개를 slot 크기로 읽음
        for pos in er:
            u = st[pos]
            rec = dec[pos][:lens[u]].tobytes()
            if sha(rec) != man.table[u][2]:
                reason = reason or "unit_hash_mismatch"
                continue
            recovered[u] = rec
            ok_bytes += lens[u]

    cov = ok_bytes / man.orig
    io = dict(scan_bytes=len(damaged), manifest_bytes=man.total_bytes, parity_verify_bytes=len(blob))
    if len(recovered) + len(found) != man.n:
        return None, RepairResult(False, reason or "unrecovered", len(erased), erased_bytes, read_bytes, cov, **io)
    out = b"".join(found[i] if i in found else recovered[i] for i in range(man.n))
    io.update(reverify_bytes=len(out), written_bytes=len(out))
    if sha(out) != man.commit:
        return None, RepairResult(False, "commit_mismatch", len(erased), erased_bytes, read_bytes, cov, **io)
    return out, RepairResult(True, "ok", len(erased), erased_bytes, read_bytes, 1.0, **io)


def _parse_parity_blob(man: Manifest, scheme: Scheme, blob: bytes) -> list[np.ndarray]:
    """서명된 길이표와 배치 규칙으로 검증된 패리티 바이트열을 분해한다."""
    lens = [entry[1] for entry in man.table]
    out: list[np.ndarray] = []
    off = 0
    for st in stripes(man.n, man.k, lens if scheme.sort_stripes else None):
        slot = max(lens[u] for u in st)
        size = man.m * slot
        end = off + size
        if end > len(blob):
            raise ValueError("truncated_parity_blob")
        out.append(np.frombuffer(blob[off:end], dtype=np.uint8).reshape(man.m, slot).copy())
        off = end
    if off != len(blob):
        raise ValueError("trailing_parity_bytes")
    return out


def _pad_one(unit: bytes, slot: int) -> np.ndarray:
    v = np.zeros(slot, dtype=np.uint8)
    v[:len(unit)] = np.frombuffer(unit, dtype=np.uint8)
    return v


def new_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    sk = Ed25519PrivateKey.generate()
    return sk, sk.public_key()
