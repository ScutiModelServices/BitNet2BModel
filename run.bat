@echo off
REM Starts the BitNet service on port 9140 (syncs .venv with uv on each run). The first start downloads the weights (about 1.2 GB).
REM LABEL: BitNet Service
REM DESCRIPTION: Shared HTTP service that runs Microsoft BitNet b1.58 2B4T on the CPU for every project.

cd /d "%~dp0"

python -m uv sync
if errorlevel 1 (
    echo uv sync failed. Install uv: python -m pip install uv
    pause
    exit /b 1
)
call .venv\Scripts\activate

python src/app.py
pause
