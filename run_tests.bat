@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo 正在執行測試，請稍候...
.venv\Scripts\python.exe -m unittest -v test_dashboard > outputs\test_result.txt 2>&1
type outputs\test_result.txt | findstr /R "^Ran ^OK ^FAILED ^FAIL: ^ERROR:"
echo.
echo 完整結果已存到 outputs\test_result.txt。看完後按任意鍵關閉。
pause > nul
