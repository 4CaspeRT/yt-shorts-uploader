import os
import json
import pickle
import base64
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from apscheduler.schedulers.blocking import BlockingScheduler

# Set scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/youtube.upload'
]

# Load creds/token from environment (base64 encoded)
def load_credentials():
    creds = None

    # Load and write credentials.json
    cred_json_b64 = os.environ.get("CREDENTIALS_JSON")
    if cred_json_b64:
        cred_json = base64.b64decode(cred_json_b64).decode()
        with open("credentials.json", "w") as f:
            f.write(cred_json)

    # Load token.json or get new one
    token_json_b64 = os.environ.get("TOKEN_JSON")
    if token_json_b64:
        token_json = base64.b64decode(token_json_b64).decode()
        with open("token.json", "w") as f:
            f.write(token_json)

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )
            creds = flow.run_console()  # Use `run_console()` in headless server
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

# Get services
def get_authenticated_services():
    creds = load_credentials()
    drive_service = build('drive', 'v3', credentials=creds)
    youtube_service = build('youtube', 'v3', credentials=creds)
    return drive_service, youtube_service

# Your uploading logic
def upload_latest_video():
    print(f"[{datetime.datetime.now()}] Upload job started...")

    drive, youtube = get_authenticated_services()

    # Example logic
    folder_id = 'your-drive-folder-id'  # optional
    results = drive.files().list(
        q="mimeType='video/mp4'",
        pageSize=1,
        orderBy="createdTime desc",
        fields="files(id, name)"
    ).execute()

    items = results.get('files', [])
    if not items:
        print("No video found.")
        return

    video_file = items[0]
    file_id = video_file['id']
    file_name = video_file['name']
    request = drive.files().get_media(fileId=file_id)
    fh = open(file_name, "wb")
    downloader = drive._http.request("GET", f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
    fh.write(downloader.data)
    fh.close()

    print(f"Uploading {file_name} to YouTube...")
    request_body = {
        'snippet': {
            'title': file_name,
            'description': 'Automated upload',
            'tags': ['shorts'],
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        }
    }

    media_file = MediaFileUpload(file_name, resumable=True, mimetype='video/mp4')
    response = youtube.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=media_file
    ).execute()

    print(f"Uploaded: https://youtu.be/{response['id']}")

# Schedule (optional, for local testing)
if __name__ == '__main__':
    upload_latest_video()
