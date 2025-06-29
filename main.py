import os
import json
import base64
import datetime
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/youtube.upload'
]

FOLDER_ID = '1S53xGR45LjWhbwcfTJgOK4zOWkSQFtUA'

def load_credentials():
    creds = None

    # Decode and save credentials.json
    cred_json_b64 = os.environ.get("CREDENTIALS_JSON")
    if cred_json_b64:
        cred_json = base64.b64decode(cred_json_b64).decode()
        with open("credentials.json", "w") as f:
            f.write(cred_json)

    # Decode and save token.json
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
            creds = flow.run_console()
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

def get_authenticated_services():
    creds = load_credentials()
    drive = build('drive', 'v3', credentials=creds)
    youtube = build('youtube', 'v3', credentials=creds)
    return drive, youtube

def upload_latest_video():
    print(f"[{datetime.datetime.now()}] Starting upload job...")

    drive, youtube = get_authenticated_services()

    # Get latest MP4 file in the specific folder
    results = drive.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType='video/mp4'",
        orderBy="createdTime desc",
        pageSize=1,
        fields="files(id, name)"
    ).execute()

    items = results.get('files', [])
    if not items:
        print("No video found.")
        return

    file = items[0]
    file_id = file['id']
    file_name = file['name']

    # Download video from Drive
    request = drive.files().get_media(fileId=file_id)
    response = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
        headers={"Authorization": f"Bearer {drive._http.credentials.token}"}
    )
    with open(file_name, "wb") as f:
        f.write(response.content)
    print(f"Downloaded {file_name} from Drive")

    # Generate title and tags from filename
    raw_name = os.path.splitext(file_name)[0]
    title = raw_name.replace('_', ' ').title()
    tags = raw_name.split('_')

    # Prepare upload request
    request_body = {
        'snippet': {
            'title': title,
            'description': 'Automated upload via Python bot',
            'tags': tags,
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(file_name, mimetype='video/mp4', resumable=True)
    response_upload = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    ).execute()

    print(f"✅ Uploaded: https://youtu.be/{response_upload['id']}")

    # Delete from Google Drive
    drive.files().delete(fileId=file_id).execute()
    print(f"🗑️ Deleted from Drive: {file_name}")

    # Delete from local
    os.remove(file_name)
    print(f"🧹 Deleted local file: {file_name}")

if __name__ == '__main__':
    upload_latest_video()
