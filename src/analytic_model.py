"""해석적 비용·복구 모델 (1차 근사)와 예비실험 대조.

모델: n개 단위를 ns = ceil(n/k)개 스트라이프에 배치. 파일 복구 성공 = 모든 스트라이프에서 소거 ≤ m,
스트라이프가 독립이라 보면 P ≈ P(X ≤ m)^ns. 스트라이프당 소거 수 X의 분포는 배치에 따라 다르다.

  인터리브(레코드·블록): 연속 삭제 한 덩어리(길이 B 레코드)는 u개의 연속 단위를 소거하고, 연속 단위는
      서로 다른 스트라이프로 가므로 한 덩어리는 스트라이프당 최대 1개 소거.  X ~ Bin(N_b, min(1, u/ns)),
      N_b = D/B 덩어리 수, u = B (레코드) 또는 B·μ/s + 1 (블록).
  길이순(record_sorted): 단위 위치가 무작위로 흩어짐.  X ~ Bin(D, 1/ns).

  평균 소거 수 λ:  λ_rec = d·k_rec,   λ_blk = d·(1 + s/(Bμ))·k_blk,   d = D/n_records

예산 Ω 안에서 가장 작은 k:  k ≈ m·(1+π)/(Ω − h/u)   (π=패딩비, h=단위당 메타 바이트, u=평균 단위 크기)
⇒ 레코드가 블록보다 낮은 λ를 가질 조건(손익분기):
    (1+π)·(Ω − h_blk/s)  <  (1 + s/(Bμ))·(Ω − h_rec/μ)
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pandas as pd

H_REC, H_BLK = 46.0, 36.0


def p_success(trials: float, p: float, ns: int, m: int) -> float:
    """X ~ Bin(trials, p) 일 때 P(X<=m)^ns. trials는 실수 가능(반올림)."""
    n = max(int(round(trials)), 0)
    p = min(p, 1.0)
    cdf = sum(math.comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(min(m, n) + 1))
    return cdf ** ns


def breakeven_margin(pi: float, omega: float, mu: float, s: float, burst: float) -> float:
    """> 0 이면 레코드 방식의 λ가 더 낮다(유리). π는 레코드 방식 패딩비."""
    return (1 + s / (burst * mu)) * (omega - H_REC / mu) - (1 + pi) * (omega - H_BLK / s)


def validate(path: str = "results/prelim_results.csv") -> pd.DataFrame:
    d = pd.read_csv(path)
    d = d[(d.feasible == 1) & d.scheme.isin(["record", "record_sorted", "block1024", "block512"])].copy()
    preds = []
    for r in d.itertuples():
        mu = r.file_bytes / r.records
        burst = 10 if r.pattern == "burst" else 1
        if r.scheme == "record_sorted":
            ns = math.ceil(r.records / r.k)
            preds.append(p_success(r.deleted, 1 / ns, ns, int(r.m)))
            continue
        if r.scheme == "record":
            n_units, u = r.records, burst
        else:
            s = int(r.scheme.removeprefix("block"))
            n_units, u = math.ceil(r.file_bytes / s), burst * mu / s + 1
        ns = math.ceil(n_units / r.k)
        preds.append(p_success(r.deleted / burst, u / ns, ns, int(r.m)))
    d["pred"] = preds
    return d


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "results/prelim_results.csv"
    d = validate(src)
    cell = d.groupby(["dataset", "budget", "m", "pattern", "rate", "scheme"]).agg(
        meas=("success", "mean"), pred=("pred", "mean")).reset_index()
    cell["err"] = (cell.pred - cell.meas).abs()
    print(f"셀 {len(cell)}개  MAE={cell.err.mean():.3f}  상관계수={cell[['meas','pred']].corr().iloc[0,1]:.3f}")
    print(cell.groupby("scheme").err.mean().round(3).to_string())
    # 승패 방향 일치율: 같은 조건에서 record_sorted vs block512 중 누가 높은가
    pv = cell.pivot_table(index=["dataset", "budget", "m", "pattern", "rate"], columns="scheme", values=["meas", "pred"])
    for blk in ["block1024", "block512"]:
        m_diff = pv[("meas", "record_sorted")] - pv[("meas", blk)]
        p_diff = pv[("pred", "record_sorted")] - pv[("pred", blk)]
        keep = m_diff.abs() > 0.1
        print(f"record_sorted vs {blk}: 실측 차이 >0.1인 {keep.sum()}개 조건 중 부호 일치 {(np.sign(m_diff[keep]) == np.sign(p_diff[keep])).mean():.2f}")
    cell.to_csv(os.path.join(os.path.dirname(src), "model_validation.csv"), index=False)
