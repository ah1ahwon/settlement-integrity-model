"""baseline 로그가 대화에서 보고한 수치와 일치하는지 대조한다. 불일치는 덮어쓰지 않고 results/reported_numbers_check.txt 에 기록한다."""
import os, re, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
LOG = os.path.join(ROOT, 'results', sys.argv[1] if len(sys.argv) > 1 else 'baseline')
CHK = [  # (로그, 설명, 정규식, 최소 일치 횟수)
 ('refval', '독립 열거 대조 85,624건, 불일치 0', r'85624\s*건,\s*불일치\s*0', 1),
 ('val_x', '취소 규칙 열거 162,000건, 불일치 0', r'검증 건수 162000 불일치 0', 1),
 ('val', '구 규칙 열거 10,428건, 불일치 0', r'검증 건수 10428 불일치 0', 1),
 ('thm2', '단일 거래 245,280건 해석식 대조 불일치 0', r'245280 건 중 불일치 0', 1),
 ('thm2', '판정 갈림 원인: 예산만 128, 포함관계 1,055', r"'비용\(예산\)만 차이': 128.*'포함관계 차이': 1055|'포함관계 차이': 1055.*'비용\(예산\)만 차이': 128", 1),
 ('thm2', '두 거래 결합 290건', r'공통 취소 예산에서만 갈린 경우 290건', 1),
 ('thm', '반송 이력 없는 조합의 해석식 불일치 2,650건(원인: 숨은 반송 상태 R)', r'245280 건 중 불일치 2650', 1),
 ('budget_only', '예산만 차이 128건 및 전체 일치', r'보고 수치 일치: True', 1),
 ('props', '구 규칙 단조성 위반 5,352건(c=1)', r'c=1:.*단조성 위반 5352건', 1),
 ('props', 'c=3 구 규칙 단조성 위반 0', r'c=3:.*단조성 위반 0건', 1),
 ('props', 'c 단조성 위반 0/231,138', r'231138건 중 위반 0건', 1),
 ('cls', 'CR 고정 후 위반 10 / 5 / 0', r'c=1: 단조성 위반 10/1155690.*c=2: 단조성 위반 5/1155690.*c=3: 단조성 위반 0/1155690|c=1: 단조성 위반 10/1155690[\s\S]*c=2: 단조성 위반 5/1155690[\s\S]*c=3: 단조성 위반 0/1155690', 1),
 ('refeval', '통일 판정 정보 단조성 위반 0 (c=1,2,3)', r'정보 단조성 위반 0/1155690', 3),
 ('refeval', '통일 판정 c 단조성 위반 0/114,426', r'c 단조성 위반 0/114426', 1),
 ('casecmp', 'X1+Z vs X2 사례별 일치 43,668건 불일치 0', r'총 비교 43668.*판정 불일치 0 건', 1),
 ('final_ref', '공격 42,668건', r'42668 공격', 1),
 ('final_ref', '표1 원장+청구일자 61.0 -> 62.1', r'원장\+청구일자\s+61\.0 / +62\.1', 1),
 ('final_ref', '표1 원장+D+B+Z 69.6 -> 70.4', r'원장\+D\+B\+Z\s+69\.6 / +70\.4', 1),
 ('final_ref', '표1 D+B+Z+X1 = X2 = 88.6 -> 89.2', r'D\+B\+Z\+X1\s+88\.6 / +89\.2.*\n.*D\+B\+Z\+X2\s+88\.6 / +89\.2', 1),
 ('final_ref', '표1 D+B(Z 없음) X1 80.6->81.2, X2 88.6->89.2', r'D\+B \(Z 없음\)\+X1\s+80\.6 / +81\.2.*\n.*D\+B \(Z 없음\)\+X2\s+88\.6 / +89\.2', 1),
 ('run8', '본 실험 LDBZX vs LDBZY 불일치 1건/79,366', r'공격 79366건 중 불일치 1건', 1),
 ('cex', '누계 모호 세계 A: X1에서 수락, X2에서 거절', r'누계 모호\(세계 A: 2 반영\)\s+수락\s+수락\s+수락\s+수락\s+수락\s+거절', 1),
 ('sim_batch', '독립 생성기 p=0.1 취소삭제 c=0..5 탐지', r'p=0\.1.*\n.*\n\s+취소삭제\s+100\.0\s+32\.8\s+6\.6\s+0\.8\s+0\.0\s+0\.0', 1),
]
fails = 0; lines = []
for log, desc, rx, n in CHK:
    p = os.path.join(LOG, log + '.log')
    txt = open(p).read() if os.path.exists(p) else ''
    m = len(re.findall(rx, txt))
    ok = m >= n; fails += (not ok)
    lines.append(f"{'PASS' if ok else 'FAIL'}  [{log}] {desc} (일치 {m}/{n}회 이상)")
out = os.path.join(ROOT, 'results', 'reported_numbers_check_' + os.path.basename(LOG) + '.txt')
open(out, 'w').write('\n'.join(lines) + f'\n\nFAIL {fails}건\n')
print('\n'.join(lines)); print('FAIL', fails, '건 ->', os.path.relpath(out, ROOT))
sys.exit(1 if fails else 0)
