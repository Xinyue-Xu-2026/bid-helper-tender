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
echo 后端启动中，3 秒后自动打开浏览器 http://127.0.0.1:8000
start "" cmd /c "ping -n 4 127.0.0.1 >nul & start http://127.0.0.1:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if errorlevel 1 (
  echo.
  echo 后端启动失败，请把上面的报错信息发给我。
  pause
)
