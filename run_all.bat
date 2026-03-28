@echo off
echo ==============================================
echo Starting IoT Services...
echo ==============================================

echo Starting CatalogAPI...
start "Catalog API" cmd /k "python CatalogAPI.py"
timeout /t 2 /nobreak > nul

echo Starting AlertSystem...
start "Alert System" cmd /k "python AlertSystem.py"
timeout /t 2 /nobreak > nul

echo Starting StaffBot...
start "Staff Bot" cmd /k "python StaffBot.py"
timeout /t 2 /nobreak > nul

echo Starting UserBot...
start "User Bot" cmd /k "python UserBot.py"
timeout /t 2 /nobreak > nul

echo Starting CartBot...
start "Cart Bot" cmd /k "python CartBot.py"

echo.
echo All services have been started in separate windows.
echo To stop a service, close its window (or press Ctrl+C in it).
pause
