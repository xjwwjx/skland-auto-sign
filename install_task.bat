@echo off
REM ============================================================
REM  森空岛自动签到 - Windows 定时任务安装脚本
REM  右键 -> 以管理员身份运行
REM ============================================================

set TASK_NAME=SklandAutoSign

REM 自动检测脚本所在目录
set SCRIPT_DIR=%~dp0
set SCRIPT=%SCRIPT_DIR%skland_sign.py

REM 自动检测 Python 路径（优先 pythonw.exe 静默运行）
where pythonw.exe >nul 2>&1
if %errorlevel%==0 (
    for /f "delims=" %%i in ('where pythonw.exe') do set PY_EXE=%%i
) else (
    where python.exe >nul 2>&1
    if %errorlevel%==0 (
        for /f "delims=" %%i in ('where python.exe') do set PY_EXE=%%i
    ) else (
        echo.
        echo 未找到 Python，请先安装 Python 3 并添加到 PATH！
        pause
        exit /b 1
    )
)

echo 使用 Python: %PY_EXE%
echo 脚本路径: %SCRIPT%
echo.

REM 删除旧任务
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

REM 注册每日 15:00 定时任务
schtasks /Create ^
  /TN "%TASK_NAME%" ^
  /TR "\"%PY_EXE%\" \"%SCRIPT%\"" ^
  /SC DAILY ^
  /ST 15:00 ^
  /F ^
  /RL HIGHEST

if %errorlevel%==0 (
    echo.
    echo ==========
    echo  定时任务 "%TASK_NAME%" 创建成功！
    echo  执行时间: 每天 15:00
    echo  日志文件: %SCRIPT_DIR%sign_log.txt
    echo.
    echo  管理命令:
    echo    立即测试:  schtasks /Run /TN SklandAutoSign
    echo    查看任务:  schtasks /Query /TN SklandAutoSign
    echo    删除任务:  schtasks /Delete /TN SklandAutoSign /F
    echo ==========
    echo.
    echo  现在立即运行一次测试...
    schtasks /Run /TN SklandAutoSign
    timeout /t 5 >nul
    type "%SCRIPT_DIR%sign_log.txt"
) else (
    echo.
    echo 创建失败，请确认以管理员身份运行此脚本！
    pause
)
