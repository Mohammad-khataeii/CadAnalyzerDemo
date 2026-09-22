@echo off
setlocal
if not exist .venv (
  py -3.11 -m venv .venv
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest -q
if errorlevel 1 exit /b 1
.venv\Scripts\pyinstaller --clean ProductAnalyzer.spec
if errorlevel 1 exit /b 1
dist\ProductAnalyzer.exe --demo
if errorlevel 1 exit /b 1
echo.
echo Windows EXE created:
echo %CD%\dist\ProductAnalyzer.exe
endlocal
