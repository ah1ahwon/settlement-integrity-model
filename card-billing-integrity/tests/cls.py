import random
import m2, m2b, m4
from m2 import atoms as atoms_old
from run9 import make_case5
from m4 import *
rng=random.Random(8); C=[]
for _ in range(300):
    led,F,_,_=make_case5(rng,0.1,0.1); C.append((led,F,attacks4(F,led,rng)))
# --- 1. 위반 사례 분해 (c=1): LD 거절 / LDB 수락
def why(F,led,K,c):
    a=atoms_old(F,led,{k for k in K if k not in 'XY'},c); return [n for n,v in a.items() if not v]
c=1; shown={'legit':0,'attack':0}
for led,F,A in C:
    for kind,G in [('legit',F)]+[('attack',g) for _,g in A]:
        if shown[kind]>=1: continue
        if (not explainable(G,led,set('LD'),c)) and explainable(G,led,set('LDB'),c):
            shown[kind]+=1
            print(f'[{kind}] c={c}: LD 위반 규칙 {why(G,led,set("LD"),c)} → LDB 위반 규칙 {why(G,led,set("LDB"),c)}')
            sent=[(i,led[i]["st"]) for t,i,a in G[1] if t==10]; print('   파일 10 레코드의 원장 상태:',sent)
# --- 2. 재청구 규칙을 기준 판정(반송 건수 상한 CR=2 고정)에 맞춰 단조성 재검증
m4.explainable=m2b.explainable
m2b.CR=2
from props import KS, leq
for c in (1,2,3):
    pairs=[(a,b) for a in KS for b in KS if a!=b and leq(a,b)]
    viol=0; tot=0; fr=0
    for led,F,A in C:
        for isleg,G in [(1,F)]+[(0,g) for _,g in A]:
            res={''.join(sorted(k)):not explainable4(G,led,k,c) for k in KS}
            for a,b in pairs:
                tot+=1
                if res[''.join(sorted(a))] and not res[''.join(sorted(b))]: viol+=1
    print(f'재청구 상한 CR=2 고정, 판매·취소 이월 허용치 c={c}: 단조성 위반 {viol}/{tot}')
