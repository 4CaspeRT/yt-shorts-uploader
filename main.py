import os
import base64
import json
import logging
import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io

# Setup logging
logging.basicConfig(
    format='[%(asctime)s] %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
)

FOLDER_ID = '1S53xGR45LjWhbwcfTJgOK4zOWkSQFtUA'  # Your Google Drive folder ID

def load_credentials():
    credentials_json = os.environ.get('CREDENTIALS_JSON')
    token_json = os.environ.get('TOKEN_JSON')

    if not credentials_json or not token_json:
        raise Exception("Environment variables for credentials or token are missing.")

    creds_data = json.loads(base64.b64decode(credentials_json))
    token_data = json.loads(base64.b64decode(token_json))

    creds = Credentials(
        token=token_data['token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri=creds_data['installed']['token_uri'],
        client_id=creds_data['installed']['client_id'],
        client_secret=creds_data['installed']['client_secret'],
        scopes=[
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube'
        ]
    )
    return creds

def get_authenticated_services():
    creds = load_credentials()
    drive = build('drive', 'v3', credentials=creds)
    youtube = build('youtube', 'v3', credentials=creds)
    return drive, youtube

def get_latest_video_file(drive):
    results = (
        drive.files()
        .list(
            q=f"'{FOLDER_ID}' in parents and mimeType='video/mp4'",
            orderBy='createdTime desc',
            pageSize=1,
            fields='files(id, name)',
        )
        .execute()
    )
    items = results.get('files', [])
    if not items:
        raise Exception("No video files found in the folder.")
    return items[0]['id'], items[0]['name']

def download_file(drive, file_id, file_name):
    logging.info(f"📥 Downloading {file_name} from Drive...")
    request = drive.files().get_media(fileId=file_id)
    fh = io.FileIO(file_name, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            logging.info(f"⬇️ Download progress: {int(status.progress() * 100)}%")
    return file_name

def upload_to_youtube(youtube, file_path):
    title = os.path.splitext(os.path.basename(file_path))[0]
    body = {
        'snippet': {
            'title': title,
            'description': 'Uploaded via automation.',
            'tags': ['shorts'],
            'categoryId': '22',
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        },
    }
    media = MediaFileUpload(file_path, mimetype='video/*', resumable=True)
    request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)

    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                logging.info(f"📤 Upload progress: {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in [403, 500, 503]:
                logging.warning("Retrying after error...")
                time.sleep(5)
            else:
                raise
    logging.info(f"✅ Uploaded: https://youtu.be/{response['id']}")
    return response['id']

def upload_latest_video():
    logging.info("Upload job started...")
    drive, youtube = get_authenticated_services()
    file_id, file_name = get_latest_video_file(drive)
    file_path = download_file(drive, file_id, file_name)
    try:
        upload_to_youtube(youtube, file_path)
    except Exception as e:
        logging.error(f"❌ Failed to upload: {e}")
    try:
        drive.files().delete(fileId=file_id).execute()
        logging.info("🗑️ Deleted video from Google Drive.")
    except Exception as e:
        logging.warning(f"⚠️ Failed to delete video from Drive: {e}")
    try:
        os.remove(file_path)
        logging.info("🗑️ Deleted local file.")
    except Exception as e:
        logging.warning(f"⚠️ Failed to delete local file: {e}")

if __name__ == '__main__':
    upload_latest_video()
