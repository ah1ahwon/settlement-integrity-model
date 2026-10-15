"""최종 고정 모델(단일 버전). 정상: make_case5(p), 공격: attacks4, 검증: explainable4 (c = 검증기 허용치)."""
import random, statistics as st, collections, copy, sys
from run9 import make_case5
from m4 import *
P=0.10; CMAIN=3; N=1000; SEED=2024
def bal(per): return st.mean(100*v[0]/v[1] for v in per.values())
rng=random.Random(SEED); CASES=[]
for _ in range(N):
    led,F,ds,dc=make_case5(rng,P,P); CASES.append((led,F,attacks4(F,led,rng)))
print(f'[고정 조건] 정당 {N}파일, 실제 지연 확률 p={P}(판매·취소 각각), 검증기 허용치 c={CMAIN}, 공격 {sum(len(a) for _,_,a in CASES)}건 (13유형), 시드 {SEED}')
SETS=[('V0 내부 규칙만',''),('V1 승인 원장','L'),('원장+청구일자','LD'),('원장+D+반송+누계','LDBZ'),('+취소승인목록 X1','LDBZX'),('+X2(승인+반영상태)','LDBZY'),('Z 없이 D+B+X1','LDBX'),('Z 없이 D+B+X2','LDBY')]
KS=[k for _,k in SETS]
def fr(k,c=CMAIN): return 100*sum(not explainable4(F,l,set(k),c) for l,F,_ in CASES)/N
kinds=sorted({kd for _,_,A in CASES for kd,_ in A})
R={}
for nm,k in SETS:
    per={}
    for l,F,A in CASES:
        for kd,G in A:
            d=per.setdefault(kd,[0,0]); d[0]+= not explainable4(G,l,set(k),CMAIN); d[1]+=1
    R[k]=per
print(f'\n[표1] 신뢰정보 조합별 변조 유형 차단율% (단일 변경, c={CMAIN})')
print(f'{"유형":24s}'+''.join(f'{nm[:9]:>10s}' for nm,_ in SETS))
for kd in kinds: print(f'{kd:24s}'+''.join(f'{100*R[k][kd][0]/R[k][kd][1]:10.0f}' for k in KS))
print(f'{"유형균등 평균":22s}'+''.join(f'{bal({a:b for a,b in R[k].items()}):10.1f}' for k in KS))
print(f'{"정당 오차단%":22s}'+''.join(f'{fr(k):10.1f}' for k in KS))
# 적응형
print('\n[표2] 평균 차단 vs 적응형(사례당 20회 중 한 번이라도 미탐인 비율%)')
r2=random.Random(5); NC=200; ad={k:collections.defaultdict(lambda:[0,0]) for k in ('LDBZ','LDBZX','LDBZY')}; nc=collections.Counter()
for _ in range(NC):
    led,F,_,_=make_case5(r2,P,P); best={k:{} for k in ad}
    for t in range(20):
        for kd,G in attacks4(F,led,r2):
            for k in ad:
                b=best[k].setdefault(kd,0); best[k][kd]=b|int(explainable4(G,led,set(k),CMAIN))
    for k in ad:
        for kd,b in best[k].items(): ad[k][kd][0]+=b; ad[k][kd][1]+=1
for kd in kinds: print(f'{kd:24s}'+''.join(f'{100*(1-R[k][kd][0]/R[k][kd][1]) if False else 100-100*R[k][kd][0]/R[k][kd][1]:6.0f}→{100*ad[k][kd][0]/ad[k][kd][1]:<4.0f}' for k in ('LDBZ','LDBZX','LDBZY')))
print('  (각 열: 평균 미탐% → 적응형 미탐가능%)  유형균등 적응형 미탐가능 평균:',*[f'{k} {st.mean(100*v[0]/v[1] for kk,v in ad[k].items()):.1f}' for k in ad])
# c x p 격자
print('\n[표3] 실제 지연 p x 검증기 허용치 c (단일 c): 오차단% / 취소삭제 1건 탐지% / 거래삭제 1건 탐지%')
def grid(p,cs_list):
    r=random.Random(77); C=[make_case5(r,p,p) for _ in range(600)]
    out=[]
    for c in cs_list:
        f=0; d={'c':[0,0],'s':[0,0]}
        for led,F,_,_ in C:
            f+= not explainable4(F,led,K5,c); rs=F[1]
            for j,x in enumerate(rs):
                G=(0,rs[:j]+rs[j+1:]); t='c' if x[0]==20 else 's'
                d[t][1]+=1; d[t][0]+= not explainable4(G,led,K5,c)
        out.append((c,100*f/len(C),100*d['c'][0]/max(1,d['c'][1]),100*d['s'][0]/max(1,d['s'][1])))
    return out
K5=set('LDBZY')
print('  p     '+'  '.join(f'c={c}:오차단/취소/거래' for c in range(5)))
for p in (0.0,0.05,0.1,0.2):
    print(f'  {p:<5} '+' '.join(f'{o[1]:4.1f}/{o[2]:3.0f}/{o[3]:3.0f}' for o in grid(p,range(5))))
# 분리 예산
print('\n[표4] 판매·취소 허용치 분리 (p_판매, p_취소 | c_판매, c_취소 → 오차단% / 판매삭제 / 취소삭제 탐지%)')

def ex(F,led,cs,cc): return explainable(F,led,{k for k in K5 if k not in 'XY'},cs) and extra_ok(F,led,K5,cc)
def go(ps,pc,cs,cc,N=600,seed=17):
    r=random.Random(seed); f=0; n=dict(s=[0,0],c=[0,0])
    for _ in range(N):
        led,F,_,_=make_case5(r,ps,pc); rs=F[1]; f+= not ex(F,led,cs,cc)
        for typ,t in (('s',10),('c',20)):
            for j,x in enumerate(rs):
                if x[0]!=t: continue
                G=(0,rs[:j]+rs[j+1:]); n[typ][1]+=1; n[typ][0]+= not ex(G,led,cs,cc)
    return 100*f/N,100*n['s'][0]/max(1,n['s'][1]),100*n['c'][0]/max(1,n['c'][1])
for ps,pc in ((0.1,0.0),(0.1,0.1),(0.0,0.1)):
    for cs,cc in ((3,3),(3,0),(0,3)):
        a=go(ps,pc,cs,cc); print(f'  p_판매={ps} p_취소={pc} | c_판매={cs} c_취소={cc} → {a[0]:5.1f} / {a[1]:5.1f} / {a[2]:5.1f}')
# 이력 오류
print(f'\n[표5] X2 반영상태 오류 (c={CMAIN}): 정당 오차단% / 유형균등 차단%')
def lag(led,p,r,mode):
    l2=copy.deepcopy(led)
    for i in l2:
        l2[i]['ev']=[((a,(False if (cl and mode=='old') else (True if (not cl and mode=='early') else cl))) if r.random()<p else (a,cl)) for a,cl in l2[i]['ev']]
    return l2
for mode,lab in (('old','청구완료를 미반영으로 표시'),('early','미반영을 반영으로 표시')):
    for p in (0,.05,.1,.2):
        r=random.Random(3); f=0; per={}
        for led,F,A in CASES:
            l2=lag(led,p,r,mode); f+= not explainable4(F,l2,K5,CMAIN)
            for kd,G in A:
                if kd=='취소 재전송(청구완료)': continue
                d=per.setdefault(kd,[0,0]); d[0]+= not explainable4(G,l2,K5,CMAIN); d[1]+=1
        print(f'  {lab:18s} {int(p*100):2d}%  오차단 {100*f/N:5.1f}  차단 {bal(per):5.1f}')
