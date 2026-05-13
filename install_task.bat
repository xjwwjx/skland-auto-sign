@echo off
REM ============================================================
REM  森空岛自动签到 - Windows 定时任务安装脚本
REM  右键 -> 以管理员身份运行
REM ============================================================

set TASK_NAME=SklandAutoSign
set PY_EXE=D:\anaconda\pythonw.exe
set SCRIPT=C:\Users\Soyo\WorkBuddy\2026-05-09-task-2\skland_sign.py

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
    echo  日志文件: %SCRIPT:\skland_sign.py=\sign_log.txt%
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
    type "%SCRIPT:\skland_sign.py=\sign_log.txt%"
) else (
    echo.
    echo 创建失败，请确认以管理员身份运行此脚本！
    pause
)
