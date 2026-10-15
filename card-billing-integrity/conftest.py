# 이 폴더의 스크립트는 pytest 테스트가 아니라 run_all.py로 실행하는 재현 스크립트다.
# 저장소 루트에서 pytest를 실행할 때 이 폴더를 수집하지 않도록 한다(import 시 실행되는 원본 스크립트 보호).
collect_ignore_glob = ["*"]
