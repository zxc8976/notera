@echo off
echo 重启Docker系统...
docker-compose down --remove-orphans
timeout /t 3 /nobreak > nul
docker system prune -f
echo 请等待5-10秒后自动启动...
timeout /t 10 /nobreak > nul
docker-compose up -d --build --force-recreate
echo 系统重启完成
pause
