@echo off
REM Run as Administrator: right-click -> Run as administrator
REM Sets static IP 192.168.0.162 so colleagues can always open http://192.168.0.162:8366
net session >nul 2>&1
if errorlevel 1 (
  echo ERROR: Please right-click this file and choose "Run as administrator".
  pause
  exit /b 1
)
echo Setting static IP 192.168.0.162 ...
netsh interface ip set address name="WLAN" static 192.168.0.162 255.255.0.0 192.168.0.1
netsh interface ip set dns name="WLAN" static 114.114.114.114
netsh interface ip add dns name="WLAN" 61.177.7.7 index=2
echo.
echo Done. Current config:
ipconfig | findstr /C:"IPv4" /C:"DNS"
echo.
echo To revert to DHCP later, run as administrator:
echo   netsh interface ip set address name="WLAN" dhcp
echo   netsh interface ip set dns name="WLAN" dhcp
pause
