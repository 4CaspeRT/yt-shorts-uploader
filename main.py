import os
import io
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# === SCOPES for YouTube + Drive ===
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/drive.readonly'
]

# === Your Real Google Drive Folder ID ===
DRIVE_FOLDER_ID = '1S53xGR45LjWhbwcfTJgOK4zOWkSQFtUA'

def get_authenticated_services():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    youtube = build('youtube', 'v3', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)
    return drive, youtube

def download_videos_from_drive(drive_service, destination_folder='videos'):
    print("🔍 Checking Google Drive for new videos...")
    query = f"'{DRIVE_FOLDER_ID}' in parents and mimeType='video/mp4'"
    results = drive_service.files().list(q=query, pageSize=10, fields="files(id, name)").execute()
    items = results.get('files', [])

    if not items:
        print("📭 No new videos found.")
        return

    os.makedirs(destination_folder, exist_ok=True)

    for item in items:
        file_id = item['id']
        file_name = item['name']
        request = drive_service.files().get_media(fileId=file_id)
        file_path = os.path.join(destination_folder, file_name)

        fh = io.FileIO(file_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        print(f"✅ Downloaded: {file_name}")

        # Optional: delete from Drive after download
        # drive_service.files().delete(fileId=file_id).execute()

if __name__ == "__main__":
    drive, youtube = get_authenticated_services()
    print("✅ Authenticated")
    download_videos_from_drive(drive)
