@echo off
echo Starting LifeOS API...
set PYTHONPATH=%~dp0
uvicorn main:app --reload --host 127.0.0.1 --port 8001