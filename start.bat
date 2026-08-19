@echo off
cd /d %~dp0frontend
if not exist dist (
  echo 首次运行，正在构建前端...
  call npm install
  call npm run build
)
cd /d %~dp0backend
start "" http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
