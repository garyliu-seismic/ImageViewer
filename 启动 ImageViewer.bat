@echo off
setlocal

cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if defined PY goto check_pillow
where python >nul 2>nul && set "PY=python"
if defined PY goto check_pillow
echo Python 3 was not found. Install Python 3 and run this file again.
pause
exit /b 1

:check_pillow
%PY% -c "import PIL" >nul 2>nul
if not errorlevel 1 goto start
echo Installing Pillow...
%PY% -m pip install Pillow
if not errorlevel 1 goto start
echo Pillow installation failed.
pause
exit /b 1

:start
%PY% "%~dp0image_viewer.py"
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
