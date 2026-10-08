@echo off
setlocal
set "PROJECT_DIR=%~dp0.."
for %%I in ("%PROJECT_DIR%") do set "PROJECT_DIR=%%~fI"
set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "PYTHONPATH=%BACKEND_DIR%"

"%BACKEND_DIR%\.venv\Scripts\python.exe" -m app.agent.windows_capture --live --interface "\Device\NPF_{9B53D52B-435F-43A5-BABE-3232279FB0C8}" --capture-timeout 60 --packet-filter "ip or ip6" --api-base-url "http://localhost:8000" --agent-id "7f3c2b91-6d44-4a8e-9c27-51f0d8a63b12"
