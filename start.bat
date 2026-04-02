@echo off
chcp 65001 >nul
echo ============================================================
echo   Справочная система по внутренним документам
echo   Запуск сервисов...
echo ============================================================

echo.
echo [1/3] Search Service (порт 5010)...
start "SearchService" cmd /k "cd /d %~dp0 && python services\search_service.py"
timeout /t 2 /nobreak >nul

echo [2/3] LLM Service (порт 5011)...
start "LLMService" cmd /k "cd /d %~dp0 && python services\llm_service.py"
timeout /t 2 /nobreak >nul

echo [3/3] Web Client (порт 5012)...
start "WebClient" cmd /k "cd /d %~dp0 && python services\web_client.py"

echo.
echo ============================================================
echo   Все сервисы запущены!
echo   Откройте в браузере: http://localhost:5012
echo   Для остановки закройте окна cmd
echo ============================================================
pause
