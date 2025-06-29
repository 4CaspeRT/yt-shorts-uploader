import os
import io
import json
import logging
import base64
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from googleapiclient.errors import HttpError

FOLDER_ID = '1S53xGR45LjWhbwcfTJgOK4zOWkSQFtUA'
STATIC_DESCRIPTION = "🔥 Subscribe for more awesome content!\n📌 Follow us for daily shorts.\n#Shorts #Trending"
STATIC_TAGS = ["Shorts", "Trending", "DailyContent", "Viral"]
LOCAL_FOLDER = '.'

logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO)

def load_credentials():
    credentials_json = os.getenv("CREDENTIALS_JSON")
    token_json = os.getenv("TOKEN_JSON")

    if credentials_json and token_json:
        creds_data = json.loads(base64.b64decode(credentials_json))
        token_data = json.loads(base64.b64decode(token_json))
        creds = Credentials.from_authorized_user_info(token_data)
        return creds

    raise Exception("Environment variables for credentials or token are missing.")

def get_authenticated_services():
    creds = load_credentials()
    drive = build('drive', 'v3', credentials=creds)
    youtube = build('youtube', 'v3', credentials=creds)
    return drive, youtube

def get_latest_video_file(drive):
    results = drive.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType='video/mp4'",
        orderBy='createdTime desc',
        pageSize=1,
        fields="files(id, name)"
    ).execute()
    items = results.get('files', [])
    if not items:
        raise Exception("No video files found in the Drive folder.")
    return items[0]['id'], items[0]['name']

def download_file(drive, file_id, file_name):
    request = drive.files().get_media(fileId=file_id)
    fh = io.FileIO(file_name, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        logging.info("⬇️ Download progress: %d%%" % int(status.progress() * 100))

def upload_video(youtube, file_name, title):
    body = {
        'snippet': {
            'title': title,
            'description': STATIC_DESCRIPTION,
            'tags': STATIC_TAGS,
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        }
    }
    media = MediaFileUpload(file_name, resumable=True, chunksize=-1)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
        except HttpError as e:
            logging.error(f"❌ Upload failed: {e}")
            return None
    return response.get('id')

def delete_file_from_drive(drive, file_id):
    try:
        drive.files().delete(fileId=file_id).execute()
        logging.info("🗑️ Deleted video from Google Drive.")
    except HttpError as e:
        if e.resp.status == 403:
            logging.warning("⚠️ Failed to delete video from Drive: %s", e)
        else:
            raise

def delete_local_file(file_name):
    try:
        os.remove(file_name)
        logging.info("🗑️ Deleted local file.")
    except Exception as e:
        logging.warning("⚠️ Failed to delete local file: %s", e)

def upload_latest_video():
    logging.info("Upload job started...")
    drive, youtube = get_authenticated_services()
    file_id, file_name = get_latest_video_file(drive)

    logging.info(f"📥 Downloading {file_name} from Drive...")
    download_file(drive, file_id, file_name)

    title = os.path.splitext(file_name)[0]
    logging.info(f"📤 Uploading {file_name} to YouTube...")
    video_id = upload_video(youtube, file_name, title)
    if video_id:
        logging.info(f"✅ Uploaded: https://youtu.be/{video_id}")

    delete_file_from_drive(drive, file_id)
    delete_local_file(file_name)

if __name__ == "__main__":
    upload_latest_video()
