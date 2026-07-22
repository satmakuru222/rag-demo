"""
Google Drive auto-ingestion.

Run standalone:
  C:\\ragenv\\Scripts\\python.exe -m ingest.gdrive

Or scheduled every 4h via Windows Task Scheduler (see ingest/run_gdrive.ps1).

SETUP (one-time):
  1. console.cloud.google.com → New project → Enable Google Drive API
  2. IAM & Admin → Service Accounts → Create → download JSON key
  3. Save key as: keycloak/gdrive-service-account.json
  4. Share your Drive folder with the service account email (Viewer is enough)
  5. Copy folder ID from Drive URL → set GDRIVE_FOLDER_ID in .env
"""
import os
import io
import sys
from dotenv import load_dotenv

load_dotenv()

SA_FILE = os.environ.get("GDRIVE_SERVICE_ACCOUNT_FILE", "keycloak/gdrive-service-account.json")
FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def _get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(SA_FILE, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

def list_pdfs(folder_id: str) -> list[dict]:
    service = _get_drive_service()
    query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name, modifiedTime)").execute()
    return results.get("files", [])

def download_pdf(file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload
    service = _get_drive_service()
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()

def run_ingestion():
    from ingest.processor import extract_text, chunk_text
    from vectorstore import add_document
    from db import init_db, log_indexed_doc, get_indexed_docs

    init_db()

    if not FOLDER_ID:
        print("GDRIVE_FOLDER_ID not set in .env — skipping.")
        return

    if not os.path.exists(SA_FILE):
        print(f"Service account file not found: {SA_FILE}")
        print("See setup instructions at the top of this file.")
        return

    already_indexed = {d["filename"] for d in get_indexed_docs() if d["source_type"] == "gdrive"}

    files = list_pdfs(FOLDER_ID)
    print(f"Found {len(files)} PDFs in Drive folder.")

    for f in files:
        name = f["name"]
        if name in already_indexed:
            print(f"  Skipping {name} (already indexed)")
            continue
        print(f"  Ingesting {name}...")
        pdf_bytes = download_pdf(f["id"])
        text = extract_text(pdf_bytes)
        chunks = chunk_text(text)
        added = add_document(name, chunks)
        log_indexed_doc(name, "gdrive", "auto-ingest", added)
        print(f"  ✓ {name}: {added} chunks added")

    print("Done.")

if __name__ == "__main__":
    run_ingestion()
