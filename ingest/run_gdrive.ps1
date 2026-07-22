# RAG Platform — Google Drive Auto-Ingestion
# Runs every 4 hours via Windows Task Scheduler
# To register: run Register-GDriveTask.ps1

$env:PATH = "C:\ragenv\Scripts;" + $env:PATH
Set-Location "D:\TheAIStackk\rag-demo"

$logDir = "D:\TheAIStackk\rag-demo\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] Starting GDrive ingestion run" >> "$logDir\gdrive_ingest.log"

C:\ragenv\Scripts\python.exe -m ingest.gdrive >> "$logDir\gdrive_ingest.log" 2>&1

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] Done." >> "$logDir\gdrive_ingest.log"
