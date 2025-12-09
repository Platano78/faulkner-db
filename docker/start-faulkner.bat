@echo off
echo Starting Faulkner DB...
cd /d "%~dp0"
docker-compose up -d
echo.
echo ✅ Faulkner DB started!
echo.
echo Access visualization at: http://localhost:8082
echo.
echo Services running:
docker-compose ps
pause
