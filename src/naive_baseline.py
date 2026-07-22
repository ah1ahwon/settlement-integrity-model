"""RQ4 비교용 베이스라인: 파일 크기·수정시각(mtime) 비교 방식.

정산 파일 인터페이스 구간에서 종종 쓰이는, 가장 단순한 무결성 점검 방식을
재현한다. 파일 크기와 수정시각이 생성 시점과 동일하면 '정상'으로 판단하고,
둘 중 하나라도 다르면 '이상'으로 판단한다. 해시 체이닝 모델과 달리 파일의
내용을 직접 들여다보지 않는다는 점이 핵심 차이다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class FilePropertySnapshot:
    size_bytes: int
    mtime: float


def snapshot(file_path: str) -> FilePropertySnapshot:
    st = os.stat(file_path)
    return FilePropertySnapshot(size_bytes=st.st_size, mtime=st.st_mtime)


def naive_check(original: FilePropertySnapshot, file_path: str) -> bool:
    """크기·수정시각이 원본과 동일하면 정상으로 판단한다.

    반환값 True = 통과(정상으로 오인 → 전송 허용), False = 차단(이상 감지).
    """
    current = snapshot(file_path)
    return current.size_bytes == original.size_bytes and current.mtime == original.mtime
