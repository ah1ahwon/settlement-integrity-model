import random
from props import C, KS, leq
from m4 import *
import sys
for c in (1,2,3):
    pairs=[(a,b) for a in KS for b in KS if a!=b and leq(a,b)]
    v_leg=v_att=0; fr_low=0
    for led,F,A in C:
        for isleg,G in [(True,F)]+[(False,g) for _,g in A]:
            res={''.join(sorted(k)):not explainable4(G,led,k,c) for k in KS}
            for a,b in pairs:
                if res[''.join(sorted(a))] and not res[''.join(sorted(b))]:
                    if isleg: v_leg+=1
                    else: v_att+=1
    # 정당 파일 오차단(하위 정보 집합)
    fr={''.join(sorted(k)):sum(not explainable4(F,l,k,c) for l,F,_ in C) for k in [set('LD'),set('LDB'),set('LDBZY')]}
    print(f'c={c}: 위반 {v_leg+v_att}건 (정당 파일 {v_leg}, 변조 파일 {v_att}) | 정당 오차단 건수(300파일): LD {fr["DL"]} LDB {fr["BDL"]} LDBZY {fr["BDLYZ"]}')
