@echo off
chcp 65001 >nul
title 哨兵 The Sentinel - 啟動中
cd /d "%~dp0"

echo.
echo ========================================
echo  哨兵 The Sentinel - 一鍵啟動
echo ========================================
echo.

REM 1. 確認 PG service
sc query postgresql-x64-16 | findstr "RUNNING" >nul
if errorlevel 1 (
    echo [1/4] PG service 沒跑、嘗試啟動...
    net start postgresql-x64-16
) else (
    echo [1/4] PG service: RUNNING
)

REM 2. 啟 backend (新視窗)
echo [2/4] 啟動 backend (port 8081)...
start "Sentinel Backend [關掉此視窗 = 停 backend]" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app --port 8081"

REM 3. 等 backend 起來
timeout /t 5 /nobreak >nul

REM 4. 啟 vite (新視窗)
echo [3/4] 啟動 frontend (port 5173)...
start "Sentinel Frontend [關掉此視窗 = 停 vite]" cmd /k "cd /d %~dp0frontend && npm run dev"

REM 5. 等 vite ready
timeout /t 5 /nobreak >nul

REM 6. 開 browser
echo [4/4] 開瀏覽器...
start http://127.0.0.1:5173/sentinel/patients

echo.
echo ========================================
echo  全部啟動完成！
echo ========================================
echo.
echo  Demo 主秀 ─ 王阿姨四幕劇:
echo    1. 病人列表搜尋 "W007" 找到「王慧明 (王阿姨)」
echo    2. 點開 detail page 看心臟層 (1 confirmed 紅旗「偶爾忘東西」)
echo    3. visit timeline 點幕 3 (2026-02-15) 「🅰️ Mode A 當時可獲得」
echo    4. 再點幕 4 (2026-06-26) 「🅱️ Mode B 事後諸葛」對比 AI 看到的差異
echo    5. Mode B 結果末「📌 加進我的 watchlist」-> 下次新就診頁頂部 banner
echo.
echo  關掉後面兩個 "Sentinel Backend" / "Sentinel Frontend" 視窗就停。
echo.
pause
