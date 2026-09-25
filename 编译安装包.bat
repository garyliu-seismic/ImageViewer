@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ==============================================
echo   图片漫画浏览器 - 一键生成安装程序
echo ==============================================
echo.

set "ISCC="

if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo 未检测到 Inno Setup，正在尝试通过 winget 自动安装...
    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
)

if not defined ISCC (
    echo.
    echo 自动安装失败。请手动下载安装 Inno Setup 6：
    echo   https://jrsoftware.org/isdl.php
    echo 安装完成后再次运行本脚本。
    pause
    exit /b 1
)

echo 正在编译安装程序，请稍候...
"%ISCC%" "ImageViewer_setup.iss"
echo.
if errorlevel 1 (
    echo 编译失败，请检查上方错误信息。
) else (
    echo 完成！安装程序已生成到「发布」文件夹。
)
pause
