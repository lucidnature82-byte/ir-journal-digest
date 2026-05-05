@echo off
REM IR Journal Digest 월간 자동 실행 스크립트
REM 매월 1일 자동 실행됨

REM 작업 디렉토리로 이동
cd /d C:\project\ir-journal-digest

REM 로그 파일에 실행 시작 기록
echo. >> logs\scheduler.log
echo === Run started at %DATE% %TIME% === >> logs\scheduler.log

REM Python 파이프라인 실행 (출력 로그에 저장)
python -m src.main --debug >> logs\scheduler.log 2>&1

REM Git 자동 커밋/푸시
git add . >> logs\scheduler.log 2>&1
git commit -m "Auto-update %DATE%" >> logs\scheduler.log 2>&1
git push >> logs\scheduler.log 2>&1

echo === Run finished at %DATE% %TIME% === >> logs\scheduler.log