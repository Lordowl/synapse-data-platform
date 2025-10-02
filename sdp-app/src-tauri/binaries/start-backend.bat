@echo off
cd /d "%~dp0"
echo Starting SDP Backend...
echo Working directory: %CD%
sdp-api-x86_64-pc-windows-msvc.exe --host 127.0.0.1 --port 8000
pause
