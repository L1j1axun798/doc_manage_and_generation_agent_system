@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish.ps1" %*
exit /b %ERRORLEVEL%
