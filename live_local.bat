@echo off
rem Live results loop - run on a PC in Israel from 21:45 on election night and keep the window open.
rem Every 5 minutes: download the CEC results file, summarize to live/results.json, push to GitHub.
cd /d "%~dp0"
set UA=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36
:loop
echo.
echo [%date% %time:~0,8%] downloading...
curl -s -m 90 -A "%UA%" -o live\expc.csv https://media26.bechirot.gov.il/files/expc.csv
python scripts\fetch_results.py --file live\expc.csv --out live\results.json
git pull -q --rebase origin main || git rebase --abort
git add live\results.json live\turnout.json live\turnout26.json
git diff --cached --quiet && echo no change || (git commit -q -m "Live update %time:~0,5%" && git push -q origin main && echo pushed)
if "%1"=="once" goto end
echo next run in 5 minutes (Ctrl+C to stop)
timeout /t 300 /nobreak >nul
goto loop
:end
