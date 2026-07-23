# RAG Platform — Start with SSL
# Run from D:\TheAIStackk\rag-demo\

$env:PATH = "C:\ragenv\Scripts;" + $env:PATH
Set-Location $PSScriptRoot

Write-Host "Starting RAG Platform with SSL..." -ForegroundColor Cyan
Write-Host "App:      http://localhost:8501" -ForegroundColor Green
Write-Host "Keycloak: https://localhost:8443" -ForegroundColor Green
Write-Host ""

streamlit run app.py --server.port 8501
