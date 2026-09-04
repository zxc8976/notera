param(
  [string]$Container = "notegen-backend-enhanced",
  [int]$Lines = 200
)

# Build bash script via single-quoted here-string to avoid PowerShell parsing
$bashScript = @'
latest="$(ls -t /app/logs/traces/*.log 2>/dev/null | head -n1)"
if [ -n "$latest" ]; then
  echo "LATEST:${latest}"
  tail -n TAIL_LINES "$latest"
elif [ -f /app/logs/notegen.log ]; then
  echo "LATEST:/app/logs/notegen.log"
  tail -n TAIL_LINES /app/logs/notegen.log
else
  echo "no logs"
fi
'@

# Replace placeholder with desired line count
$bashScript = $bashScript -replace 'TAIL_LINES', [string]$Lines

# Normalize newlines to LF to avoid CRLF issues inside bash
$bashScript = $bashScript -replace "`r`n", "`n"

$bytes = [System.Text.Encoding]::UTF8.GetBytes($bashScript)
$b64 = [System.Convert]::ToBase64String($bytes)

# Execute inside container
docker exec $Container bash -lc "echo $b64 | base64 -d | bash" | Out-Host


