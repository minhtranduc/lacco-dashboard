@echo off
rem Chay Streamlit cho LACCO Dashboard (production). Duoc Task Scheduler goi luc khoi dong may.
rem Log ra logs\streamlit.log (*.log da nam trong .gitignore).
rem Vong lap tu restart: Task Scheduler "restart on failure" KHONG kich hoat khi process bi kill/crash
rem (da test thuc te o buoc 7.2, xem HD-22), nen chinh script nay tu giam sat Streamlit.
cd /d "%~dp0..\.."
if not exist logs mkdir logs
:loop
echo [%date% %time%] starting streamlit >> logs\streamlit.log
".venv\Scripts\python.exe" -m streamlit run src/app/main.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --browser.gatherUsageStats false >> logs\streamlit.log 2>&1
echo [%date% %time%] streamlit exited code %ERRORLEVEL%, restart in 10s >> logs\streamlit.log
timeout /t 10 /nobreak >nul
goto loop
