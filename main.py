import os
import json
import base64
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from apscheduler.schedulers.blocking import BlockingScheduler

# Scopes for Drive (read) and YouTube (upload)
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/youtube.upload'
]

# Load credentials from environment variables
def load_credentials():
    creds = None

    cred_json_b64 = os.environ.get("CREDENTIALS_JSON")
    if cred_json_b64:
        with open("credentials.json", "w") as f:
            f.write(base64.b64decode(cred_json_b64).decode())

    token_json_b64 = os.environ.get("TOKEN_JSON")
    if token_json_b64:
        with open("token.json", "w") as f:
            f.write(base64.b64decode(token_json_b64).decode())

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("Valid token.json with refresh_token is required on server.")

    return creds

# Build authenticated services
def get_authenticated_services():
    creds = load_credentials()
    drive = build('drive', 'v3', credentials=creds)
    youtube = build('youtube', 'v3', credentials=creds)
    return drive, youtube

# Main upload function
def upload_latest_video():
    print(f"[{datetime.datetime.now()}] Upload job started...")

    drive, youtube = get_authenticated_services()
    folder_id = "1S53xGR45LjWhbwcfTJgOK4zOWkSQFtUA"

    query = f"'{folder_id}' in parents and mimeType='video/mp4'"
    results = drive.files().list(
        q=query,
        pageSize=1,
        orderBy="createdTime desc",
        fields="files(id, name)"
    ).execute()

    items = results.get('files', [])
    if not items:
        print("No videos found in Drive folder.")
        return

    file = items[0]
    file_id = file['id']
    file_name = file['name']

    # Download file
    print(f"Downloading {file_name}...")
    request = drive.files().get_media(fileId=file_id)
    with open(file_name, "wb") as f:
        downloader = drive._http.request("GET", f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
        f.write(downloader.data)

    # Upload to YouTube
    print(f"Uploading {file_name} to YouTube...")
    request_body = {
        'snippet': {
            'title': os.path.splitext(file_name)[0],
            'description': 'Automated upload using Python cron job.',
            'tags': ['shorts'],
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(file_name, mimetype='video/mp4', resumable=True)
    video = youtube.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=media
    ).execute()

    print(f"Uploaded successfully: https://youtu.be/{video['id']}")

    # Delete local file
    os.remove(file_name)
    print(f"Deleted local file: {file_name}")

    # Delete from Drive
    drive.files().delete(fileId=file_id).execute()
    print(f"Deleted from Google Drive: {file_name}")

# Optional for local testing
if __name__ == "__main__":
    upload_latest_video()
