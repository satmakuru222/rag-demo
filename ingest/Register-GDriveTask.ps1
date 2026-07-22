# Run this ONCE as Administrator to register the scheduled task.
# After registration, it runs every 4 hours automatically.

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File D:\TheAIStackk\rag-demo\ingest\run_gdrive.ps1"

$trigger = New-ScheduledTaskTrigger `
    -RepetitionInterval (New-TimeSpan -Hours 4) `
    -Once `
    -At (Get-Date)

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName "RAG-GDrive-Ingest" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Force

Write-Host "Task registered. It will run every 4 hours."
Write-Host "To run immediately: Start-ScheduledTask -TaskName 'RAG-GDrive-Ingest'"
Write-Host "To check logs: Get-Content D:\TheAIStackk\rag-demo\logs\gdrive_ingest.log -Tail 20"
