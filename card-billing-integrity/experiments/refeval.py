import random, statistics as st
from ref import *
from run9 import make_case5
from m4 import attacks4, explainable4
# ---- 1. 단조성 (props와 동일한 300파일)
rng=random.Random(8); C=[]
for _ in range(300):
    led,F,_,_=make_case5(rng,0.1,0.1); C.append((led,F,attacks4(F,led,rng)))
BASE=['','D','Z','DZ','DB','DBZ']; XS=['','X','Y']
KS=[set('L'+b+x) for b in BASE for x in XS]
def leq(a,b):
    ab={k for k in a if k not in 'XY'}; bb={k for k in b if k not in 'XY'}
    xa=2 if 'Y' in a else (1 if 'X' in a else 0); xb=2 if 'Y' in b else (1 if 'X' in b else 0)
    return ab<=bb and xa<=xb
pairs=[(a,b) for a in KS for b in KS if a!=b and leq(a,b)]
for c in (1,2,3):
    Aa=(2,c,c); viol=0; tot=0
    for led,F,A in C:
        for G in [F]+[g for _,g in A]:
            res={''.join(sorted(k)):not ref_accept(G,led,k,Aa) for k in KS}
            for a,b in pairs:
                tot+=1
                if res[''.join(sorted(a))] and not res[''.join(sorted(b))]: viol+=1
    print(f'[통일 판정] CR=2, 이월 허용치 c={c}: 정보 단조성 위반 {viol}/{tot}')
# ---- 2. 이월 허용치 단조 (c 증가 시 수락 확대)
viol=0;tot=0
for led,F,A in C[:150]:
    for G in [F]+[g for _,g in A]:
        for k in (set('LDBZY'),set('LDB'),set('LDX')):
            prev=None
            for c in range(6):
                r=not ref_accept(G,led,k,(2,c,c))
                if prev is not None and r and not prev: viol+=1
                prev=r; tot+=1
print(f'[통일 판정] c 단조성 위반 {viol}/{tot}')
# ---- 3. 기존 고정 결과 재현 (final.py와 동일한 생성: seed 2024, 1000파일, p=0.1), A=(CR=2,cs=3,cc=3)
rng=random.Random(2024); CASES=[]
for _ in range(1000):
    led,F,ds,dc=make_case5(rng,0.1,0.1); CASES.append((led,F,attacks4(F,led,rng)))
SETS=[('V0 내부','') ,('V1 원장','L'),('원장+청구일자','LD'),('원장+D+반송+누계','LDBZ'),('+X1','LDBZX'),('+X2','LDBZY')]
OLD={'':13.8,'L':55.9,'LD':61.0,'LDBZ':69.6,'LDBZX':88.6,'LDBZY':88.6}
Aa=(2,3,3); print('\n[통일 판정으로 재계산] 유형균등 평균 차단% (기존값) / 정당 오차단%')
for nm,k in SETS:
    per={}; fr=0
    for l,F,A in CASES:
        fr+= not ref_accept(F,l,set(k),Aa)
        for kd,G in A:
            d=per.setdefault(kd,[0,0]); d[0]+= not ref_accept(G,l,set(k),Aa); d[1]+=1
    print(f'  {nm:16s} {st.mean(100*v[0]/v[1] for v in per.values()):5.1f} ({OLD[k]:4.1f})   오차단 {100*fr/1000:4.1f}%')
