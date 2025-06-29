import os
import json
import pickle
import base64
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from apscheduler.schedulers.blocking import BlockingScheduler

# Scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/youtube.upload'
]

# Load credentials from environment
def load_credentials():
    creds = None

    cred_json_b64 = os.environ.get("CREDENTIALS_JSON")
    if cred_json_b64:
        cred_json = base64.b64decode(cred_json_b64).decode()
        with open("credentials.json", "w") as f:
            f.write(cred_json)

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
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_console()
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

# Get services
def get_authenticated_services():
    creds = load_credentials()
    drive_service = build('drive', 'v3', credentials=creds)
    youtube_service = build('youtube', 'v3', credentials=creds)
    return drive_service, youtube_service

# Upload logic
def upload_latest_video():
    print(f"[{datetime.datetime.now()}] Upload job started...")

    drive, youtube = get_authenticated_services()

    folder_id = '1S53xGR45LjWhbwcfTJgOK4zOWkSQFtUA'
    query = f"'{folder_id}' in parents and mimeType='video/mp4'"
    results = drive.files().list(
        q=query,
        pageSize=1,
        orderBy="createdTime desc",
        fields="files(id, name)"
    ).execute()

    items = results.get('files', [])
    if not items:
        print("No videos found.")
        return

    video = items[0]
    file_id = video['id']
    file_name = video['name']

    # Download from Drive
    print(f"Downloading {file_name} from Google Drive...")
    request = drive.files().get_media(fileId=file_id)
    with open(file_name, "wb") as f:
        data = drive._http.request("GET", f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
        f.write(data.data)

    # Upload to YouTube
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
            'selfDeclaredMadeForKids': False
        }
    }

    media_file = MediaFileUpload(file_name, resumable=True, mimetype='video/mp4')
    response = youtube.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=media_file
    ).execute()

    print(f"Uploaded: https://youtu.be/{response['id']}")

    # Delete local video
    os.remove(file_name)
    print(f"Deleted local file: {file_name}")

    # Delete from Google Drive
    drive.files().delete(fileId=file_id).execute()
    print(f"Deleted from Google Drive: {file_name}")

# Run once when script starts
if __name__ == '__main__':
    upload_latest_video()
