@echo off
chcp 65001 >nul
cd /d %~dp0frontend
if not exist dist (
  echo 首次运行，正在构建前端...
  call npm install
  call npm run build
)
cd /d %~dp0backend
python -c "import fastapi, uvicorn, fitz, docx, openpyxl, openai, multipart" 2>nul
if errorlevel 1 (
  echo 首次运行，正在安装后端依赖...
  python -m pip install -r requirements.txt
)
netstat -ano | findstr "LISTENING" | findstr ":8366" >nul
if not errorlevel 1 (
  echo.
  echo 端口 8366 已被占用，平台可能已经在运行。
  echo 请直接访问 http://127.0.0.1:8366 确认；若不是本平台，请关闭占用进程后再启动。
  pause
  exit /b 1
)
echo 后端启动中，3 秒后自动打开浏览器 http://127.0.0.1:8366
echo.
echo 本机访问:  http://127.0.0.1:8366
echo 局域网访问: http://192.168.0.162:8366  (同一 WiFi/内网下的其他电脑可用，已设固定IP)
start "" cmd /c "ping -n 4 127.0.0.1 >nul & start http://127.0.0.1:8366"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8366
if errorlevel 1 (
  echo.
  echo 后端启动失败，请把上面的报错信息发给我。
  pause
)
