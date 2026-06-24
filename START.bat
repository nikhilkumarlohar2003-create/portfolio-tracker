@echo off
echo Starting Portfolio Tracker...
echo.

cd /d "%~dp0"

REM Check if .env exists
if not exist .env (
    echo Creating .env from template...
    copy .env.example .env
    echo.
    echo IMPORTANT: Open .env and add your Anthropic API key!
    echo            (Get one free at https://console.anthropic.com)
    echo.
    pause
)

REM Install dependencies if needed
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    echo.
)

echo Launching app...
python -m streamlit run app.py --server.port 8501

pause
