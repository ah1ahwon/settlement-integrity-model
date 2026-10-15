"""독립 정당 생성기: 일별 배치 시뮬레이터. 승인 시각 -> 청구 배치 결정(마감 놓치면 다음 배치). c를 쓰지 않는다."""
import random, statistics as st, sys
from m4 import *
K=set('LDBZY'); TARGET=2
def lag(rng,p):
    l=0
    while rng.random()<p and l<4: l+=1
    return l
def make_batch(rng,p):
    led={}; rs=[]; ndef_s=ndef_c=0; nid=1
    for _ in range(rng.randint(6,10)):
        i=nid; nid+=1; amt=rng.randint(10,200); a=rng.randint(0,TARGET)   # 승인일
        bs=a+lag(rng,p)
        led[i]=dict(m=0,amt=amt,st='U',cum=0,ev=[])
        if bs<TARGET: led[i]['st']='C'
        elif bs==TARGET: rs.append((10,i,amt))
        else: ndef_s+=1; led[i]['st']='U'      # 승인됐으나 아직 청구 안 됨(이월)
        # 취소: 판매 청구 배치 이후에 청구 가능
        rem=amt; ev=[]
        for _k in range(rng.choice([0,0,1,1,2])):
            if rem<1: break
            x=rng.randint(1,rem); rem-=x
            ca=rng.randint(a,TARGET)            # 취소 승인일(판매 승인 이후)
            bc=max(ca+lag(rng,p),bs)            # 취소는 판매 청구 이후/같은 파일
            ev.append((x,bc))
        for x,bc in ev:
            if bs>TARGET: continue              # 판매 미청구면 취소 이벤트는 수신측에 아직 청구 대상 아님(거래 이월)
            if bc<TARGET: led[i]['ev'].append((x,True)); led[i]['cum']+=x
            elif bc==TARGET: led[i]['ev'].append((x,False)); rs.append((20,i,x))
            else: led[i]['ev'].append((x,False)); ndef_c+=1
    for _ in range(2):
        i=nid; nid+=1; led[i]=dict(m=1,amt=rng.randint(10,200),st='C',cum=0,ev=[])
    rng.shuffle(rs); return led,(0,rs),ndef_s,ndef_c
def ex(F,led,cs,cc): return explainable(F,led,{k for k in K if k not in 'XY'},cs) and extra_ok(F,led,K,cc)
def run(p,N=800,seed=3):
    rng=random.Random(seed); rows=[]
    for _ in range(N):
        led,F,ds,dc=make_batch(rng,p); rs=F[1]; r=dict(ds=ds,dc=dc)
        att={'s':[(0,rs[:j]+rs[j+1:]) for j,x in enumerate(rs) if x[0]==10],'c':[(0,rs[:j]+rs[j+1:]) for j,x in enumerate(rs) if x[0]==20]}
        for c in range(6):
            r[('fr',c)]=not ex(F,led,c,c)
            for t,L in att.items(): r[(t,c)]=[not ex(G,led,c,c) for G in L]
        r[('fr','sep')]=None
        rows.append(r)
    return rows
print('독립 생성기(일별 배치, 지연=마감 놓침 확률 p). 단일 c. 오차단% | 거래삭제 탐지% | 취소삭제 탐지%')
print('p      c: '+'      '.join(f'{c}' for c in range(6)))
for p in (0.0,0.05,0.1,0.2):
    R=run(p)
    fr=[100*sum(r[('fr',c)] for r in R)/len(R) for c in range(6)]
    def det(t): 
        o=[]
        for c in range(6):
            tot=sum(len(r[(t,c)]) for r in R); d=sum(sum(r[(t,c)]) for r in R); o.append(100*d/tot if tot else float('nan'))
        return o
    print(f'p={p:<4} 오차단 '+' '.join(f'{x:5.1f}' for x in fr))
    print(f'       거래삭제 '+' '.join(f'{x:5.1f}' for x in det('s')))
    print(f'       취소삭제 '+' '.join(f'{x:5.1f}' for x in det('c')))
    print(f'       실제 이월 평균: 판매 {st.mean(r["ds"] for r in R):.2f} 취소 {st.mean(r["dc"] for r in R):.2f}')
