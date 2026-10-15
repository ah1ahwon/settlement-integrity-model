import random, itertools
from run9 import make_case5
from m4 import *
rng=random.Random(8); C=[]
for _ in range(300):
    led,F,_,_=make_case5(rng,0.1,0.1); C.append((led,F,attacks4(F,led,rng)))
BASE=['','D','Z','DZ','DB','DBZ']; XS=['','X','Y']
KS=[set('L'+b+x) for b in BASE for x in XS]
def leq(a,b):
    ab={k for k in a if k not in 'XY'}; bb={k for k in b if k not in 'XY'}
    xa=2 if 'Y' in a else (1 if 'X' in a else 0); xb=2 if 'Y' in b else (1 if 'X' in b else 0)
    return ab<=bb and xa<=xb
# 성질 A: K1<=K2 이면 K1이 거절한 것은 K2도 거절 (c 고정)
for c in (1,3):
    pairs=[(a,b) for a in KS for b in KS if a!=b and leq(a,b)]
    viol=0; tot=0; ex=None
    for led,F,A in C:
        files=[F]+[G for _,G in A]
        for G in files:
            res={ ''.join(sorted(k)):not explainable4(G,led,k,c) for k in KS}
            for a,b in pairs:
                ra=res[''.join(sorted(a))]; rb=res[''.join(sorted(b))]; tot+=1
                if ra and not rb:
                    viol+=1
                    if ex is None: ex=(sorted(a),sorted(b),G,{i:v for i,v in led.items() if v['m']==0})
    print(f'[성질 A] c={c}: 비교쌍 {len(pairs)}개 x 파일, 총 {tot}건 중 단조성 위반 {viol}건'); 
    if ex: print('  위반 예:',ex)
# 성질 B: c 증가시 거절 집합 축소(수락 집합 확대)
viol=0; tot=0
for led,F,A in C:
    for G in [F]+[g for _,g in A]:
        for k in (set('LDBZY'),set('LDBZX'),set('LDB')):
            prev=None
            for c in range(0,6):
                r=not explainable4(G,led,k,c)
                if prev is not None and r and not prev: viol+=1
                prev=r; tot+=1
print(f'[성질 B] c 단조성: {tot}건 중 위반 {viol}건')
