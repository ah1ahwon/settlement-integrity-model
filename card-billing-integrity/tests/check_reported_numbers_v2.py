"""2차 세트(baseline_v2) 로그가 논문에 보고할 수치와 일치하는지 대조한다. 결과는 results/reported_numbers_check_v2_<디렉터리>.txt 에 기록한다."""
import os, re, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
LOG = os.path.join(ROOT, 'results', sys.argv[1] if len(sys.argv) > 1 else 'baseline_v2')
NOMIS = r"'X1-ID 수락·X2-ID 거절': 0"
CHK = [  # (로그, 설명, 정규식, 최소 일치 횟수)
 ('indep_check_ref2', 'ref2 vs 독립 열거기 3,063,413건, 불일치 0', r'대조 3063413 건, 불일치 0\b', 1),
 ('indep_check_ref', '원 판정기 ref vs 독립 열거기 불일치 2,667', r'대조 3063413 건, 불일치 2667\b', 1),
 ('ref2_refval', '구 열거기 결함으로 인한 불일치 3,036 (85,624건)', r'85624 건, 불일치 3036\b', 1),
 ('ref2_thm2', '단일 거래 245,280건 해석식 불일치 0', r'245280 건 중 불일치 0\b', 1),
 ('ref2_thm2', '판정 갈림: 예산만 128, 포함관계 1,055', r"'비용\(예산\)만 차이': 128, '포함관계 차이': 1055", 1),
 ('ref2_thm2', '두 거래 공통 예산 의존 290건', r'공통 취소 예산에서만 갈린 경우 290건', 1),
 ('ref2_budget_only', '갈린 파일 1,183 및 직접 열거 불일치 0', r'판정이 갈린 파일: 1183[\s\S]*직접 열거와의 불일치: 0', 1),
 ('ref2_budget_only', '보고 수치 일치', r'보고 수치 일치: True', 1),
 ('ref2_casecmp', 'X1+Z vs X2 43,668건 불일치 0', r'총 비교 43668.*판정 불일치 0 건', 1),
 ('ref2_refeval', '정보 단조성 위반 0 (c=1,2,3)', r'정보 단조성 위반 0/1155690', 3),
 ('ref2_refeval', 'c 단조성 위반 0/114,426', r'c 단조성 위반 0/114426', 1),
 ('ref2_final_ref', '표1 원장+청구일자 62.1', r'원장\+청구일자\s+61\.0 /\s+62\.1', 1),
 ('ref2_final_ref', '표1 원장+D+B+Z 70.4', r'원장\+D\+B\+Z\s+69\.6 /\s+70\.4', 1),
 ('ref2_final_ref', '표1 D+B+Z+X1 = X2 = 89.2', r'D\+B\+Z\+X1\s+88\.6 /\s+89\.2.*\n.*D\+B\+Z\+X2\s+88\.6 /\s+89\.2', 1),
 ('ref2_final_ref', '표1 Z 없는 X1 81.3', r'D\+B \(Z 없음\)\+X1\s+80\.6 /\s+81\.3', 1),
 ('ref2_final_ref', '표5 미반영→반영 표시 5/10/20%: 26.1, 45.4, 68.5', r'미반영→반영 표시\s+5%: 24\.8/90\.6 → 26\.1/[\s\S]*10%: 43\.3/92\.9 → 45\.4/[\s\S]*20%: 66\.2/95\.7 → 68\.5/', 1),
 ('id_equivalence', '취소 ID 13,764건: X1-금액 vs X1-ID 0, X1-ID vs X2 355', r'13764 건\s*\n\s*X1-금액 vs X1-ID 불일치 0\s*\n\s*X1-ID vs X2 불일치 355', 1),
 ('id_chain', '취소 ID 포함관계 26,092건, 위반 0 (3종)', r'26092 건[\s\S]*위반 \(1\)[^\n]* 0\n[\s\S]*위반 \(2\)[^\n]* 0\n[\s\S]*위반 \(3\)[^\n]* 0\n', 1),
 ('prop33b', '(b-1) 26,352건 위반 0', r'\(b-1\) 전제 충족 금액 사례: 26352\s*\n\s*\(b-1\) 위반: 0\b', 1),
 ('prop33b', '(b-2) 3,372건 위반 0', r'\(b-2\) 전제 충족 ID 사례: 3372\s*\n\s*\(b-2\) 위반: 0\b', 1),
 ('prop33b', '(b-1) 전제 충족이나 ID 수준에서 갈림 1,824', r'ID 수준에서 갈림: 1824\b', 1),
 ('coupling_219', '290 = 한 거래 71 + 순수 결합 219', r'예산 의존 판정 차이 290, 한 거래만으로도 갈림 71, 공통 예산에서만 갈림\(순수 결합\) 219', 1),
 ('ref2id_consistency', 'ref2id vs 별도 ID 판정식 13,764건 불일치 0', r'13764 건, 불일치 0\b', 1),
 ('sensitivity', 'S1 c_c=1: X1+Z와 X2 모두 오차단 13.3 탐지 92.8 취소삭제 45.1', r'c_c=1 .*X1\+Z 오차단\s+13\.3 탐지\s+92\.8 취소삭제\s+45\.1 \| X2 오차단\s+13\.3 탐지\s+92\.8 취소삭제\s+45\.1', 1),
 ('sensitivity', 'S1 c_c=3: 오차단 0.3 탐지 89.2 취소삭제 3.2', r'c_c=3 .*X1\+Z 오차단\s+0\.3 탐지\s+89\.2 취소삭제\s+3\.2', 1),
 ('sensitivity', 'S3 동일 금액: 모호 881, 불일치 가능 0', r'동일 금액\s+파일 1000 이벤트 8434 모호 881 불일치가능 0 ', 1),
 ('sensitivity_s4', 'ID 추적 생성기와 원 생성기 1,000/1,000 일치, ID 유효성 위반 0', r'원장·파일 일치 1000/1000\s*\n\s*정상 파일 ID 유효성 위반 0/1000', 1),
 ('sensitivity_s4', 'A=(2,3,3) X1-금액·X2-금액: 오차단 0.3, 13유형 89.2, ID3유형 66.7, 16유형 85.0', r'\(2, 3, 3\)\n\s+X1-금액\s+오차단\s+0\.3 \| 탐지 13유형\s+89\.2 ID3유형\s+66\.7 16유형\s+85\.0[\s\S]*?X2-금액\s+오차단\s+0\.3 \| 탐지 13유형\s+89\.2 ID3유형\s+66\.7 16유형\s+85\.0', 1),
 ('sensitivity_s4', 'A=(2,3,3) X1-ID·X2-ID: ID3유형 100, 16유형 91.2', r'\(2, 3, 3\)\n[^\n]*\n\s+X1-ID\s+오차단\s+0\.3 \| 탐지 13유형\s+89\.2 ID3유형 100\.0 16유형\s+91\.2[\s\S]*?X2-ID\s+오차단\s+0\.3 \| 탐지 13유형\s+89\.2 ID3유형 100\.0 16유형\s+91\.2', 1),
 ('sensitivity_s4', 'X1-ID 수락·X2-ID 거절 0 (두 A × 13유형/ID/정상)', re.escape(NOMIS), 6),
 ('s4_breakdown', 'A=(2,3,3) 유령 ID 995, 중복 ID 3, 기반영 재전송 0', r'\(2, 3, 3\)\n\s+유령 ID[^\n]*X1-금액≠X1-ID 995,[^\n]*\n\s+중복 ID[^\n]*X1-금액≠X1-ID 3,[^\n]*\n\s+기반영[^\n]*X1-금액≠X1-ID 0,', 1),
 ('s4_breakdown', 'A=(2,3,1) 유령 ID 865, 중복 ID 3', r'\(2, 3, 1\)\n\s+유령 ID[^\n]*X1-금액≠X1-ID 865,[^\n]*\n\s+중복 ID[^\n]*X1-금액≠X1-ID 3,', 1),
]
fails = 0; lines = []
for log, desc, rx, n in CHK:
    p = os.path.join(LOG, log + '.log')
    txt = open(p, encoding='utf-8').read() if os.path.exists(p) else ''
    m = len(re.findall(rx, txt))
    ok = m >= n; fails += (not ok)
    lines.append(f"{'PASS' if ok else 'FAIL'}  [{log}] {desc} (일치 {m}/{n}회 이상)")
out = os.path.join(ROOT, 'results', 'reported_numbers_check_v2_' + os.path.basename(LOG) + '.txt')
open(out, 'w', encoding='utf-8').write('\n'.join(lines) + f'\n\nFAIL {fails}건\n')
print('\n'.join(lines)); print('FAIL', fails, '건 ->', os.path.relpath(out, ROOT))
sys.exit(1 if fails else 0)
