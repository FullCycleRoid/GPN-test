@echo off
echo [1/3] Search Service (port 5010)...
start "SearchService" cmd /k "cd /d %~dp0 && python services\search_service.py"
timeout /t 2 /nobreak >nul

echo [2/3] LLM Service (port 5011)...
start "LLMService" cmd /k "cd /d %~dp0 && python services\llm_service.py"
timeout /t 2 /nobreak >nul

echo [3/3] Web Client (port 5012)...
start "WebClient" cmd /k "cd /d %~dp0 && python services\web_client.py"

echo All services started! Open: http://localhost:5012
pause