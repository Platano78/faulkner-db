@echo off
echo Stopping Faulkner DB...
cd /d "%~dp0"
docker-compose down
echo.
echo ✅ Faulkner DB stopped!
pause
