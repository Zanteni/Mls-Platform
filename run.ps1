$Project = "D:\MLs-lab\grade-Labs"

# Start Flask
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Project'; .\.venv\Scripts\Activate.ps1; python -m webapp.app"
)

# Wait for Flask to start
Start-Sleep -Seconds 3

# Start ngrok
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Project'; ngrok http 5000"
)