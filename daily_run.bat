@echo off
cd /d C:\project\ir-journal-digest
python -m src.main --debug
git add .
git commit -m "Daily progress"
git push
pause