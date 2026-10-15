"""GF(256) 기반 체계적 Cauchy Reed-Solomon 소거 부호.

세 비교군(블록/CDC/레코드)이 동일한 구현을 공유하도록 복구 단위 길이만 다른
바이트 벡터를 입력으로 받는다. 스트라이프당 데이터 k개(k<=250), 패리티 m개(m<=5).
알려진 위치의 소거(erasure)만 복구한다. 오류 위치 탐지는 하지 않는다.
"""

from __future__ import annotations

import numpy as np

K_MAX = 250
M_MAX = 5
_X0 = 250  # 패리티 행 좌표. 데이터 열 좌표(0..K_MAX-1)와 겹치지 않는다.

_EXP = np.zeros(512, dtype=np.uint8)
_LOG = np.zeros(256, dtype=np.int32)
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]

# MUL[c][v] = c * v (GF(256)). 벡터 곱을 테이블 인덱싱 한 번으로 처리한다.
MUL = np.zeros((256, 256), dtype=np.uint8)
_a = np.arange(1, 256)
for _c in range(1, 256):
    MUL[_c, 1:] = _EXP[_LOG[_c] + _LOG[_a]]


def _mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return int(_EXP[_LOG[a] + _LOG[b]])


def _inv(a: int) -> int:
    if a == 0:
        raise ZeroDivisionError("GF(256)에서 0은 역원이 없다.")
    return int(_EXP[255 - _LOG[a]])


def coeff(i: int, j: int) -> int:
    """Cauchy 행렬 원소 C[i][j] = 1 / (x_i xor y_j)."""
    return _inv((_X0 + i) ^ j)


def encode(units: np.ndarray, m: int) -> np.ndarray:
    """units: (k, S) uint8 → 패리티 (m, S) uint8."""
    k, size = units.shape
    if not (1 <= k <= K_MAX and 1 <= m <= M_MAX):
        raise ValueError(f"지원 범위 밖: k={k}, m={m}")
    parity = np.zeros((m, size), dtype=np.uint8)
    for i in range(m):
        for j in range(k):
            parity[i] ^= MUL[coeff(i, j)][units[j]]
    return parity


def _invert(matrix: list[list[int]]) -> list[list[int]]:
    n = len(matrix)
    aug = [row[:] + [1 if r == c else 0 for c in range(n)] for r, row in enumerate(matrix)]
    for col in range(n):
        piv = next((r for r in range(col, n) if aug[r][col]), None)
        if piv is None:
            raise ValueError("특이행렬: 복구 불가")
        aug[col], aug[piv] = aug[piv], aug[col]
        inv_p = _inv(aug[col][col])
        aug[col] = [_mul(inv_p, v) for v in aug[col]]
        for r in range(n):
            if r != col and aug[r][col]:
                f = aug[r][col]
                aug[r] = [v ^ _mul(f, w) for v, w in zip(aug[r], aug[col])]
    return [row[n:] for row in aug]


def decode(
    survivors: dict[int, np.ndarray],
    erased: list[int],
    parity: np.ndarray,
    k: int,
    size: int,
) -> dict[int, np.ndarray]:
    """생존 데이터 단위와 패리티로 소거된 단위를 복원한다.

    survivors: {데이터 위치: (size,) uint8}, erased: 소거된 데이터 위치 목록.
    소거 수가 패리티 수를 넘으면 ValueError.
    """
    e = len(erased)
    if e == 0:
        return {}
    if e > parity.shape[0]:
        raise ValueError(f"소거 {e}개가 패리티 {parity.shape[0]}개를 초과")
    rhs = parity[:e].copy()
    for i in range(e):
        for j, data in survivors.items():
            rhs[i] ^= MUL[coeff(i, j)][data]
    inv = _invert([[coeff(i, j) for j in erased] for i in range(e)])
    out = {}
    for t, j in enumerate(erased):
        acc = np.zeros(size, dtype=np.uint8)
        for i in range(e):
            acc ^= MUL[inv[t][i]][rhs[i]]
        out[j] = acc
    return out
