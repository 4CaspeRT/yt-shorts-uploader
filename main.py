import os
import io
import base64
import json
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO)

FOLDER_ID = '1S53xGR45LjWhbwcfTJgOK4zOWkSQFtUA'  # Replace with your actual folder ID

def load_credentials():
    credentials_json = os.environ.get("CREDENTIALS_JSON")
    token_json = os.environ.get("TOKEN_JSON")

    if not credentials_json or not token_json:
        raise Exception("Environment variables for credentials or token are missing.")

    creds_data = json.loads(base64.b64decode(credentials_json))
    token_data = json.loads(base64.b64decode(token_json))

    creds = Credentials.from_authorized_user_info(info=token_data)
    if creds.expired or not creds.valid:
        creds = Credentials(
            token=None,
            refresh_token=token_data.get("refresh_token"),
            token_uri=creds_data["installed"]["token_uri"],
            client_id=creds_data["installed"]["client_id"],
            client_secret=creds_data["installed"]["client_secret"],
            scopes=[
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube"
            ]
        )
        creds.refresh(Request())

    return creds

def get_authenticated_services():
    creds = load_credentials()
    drive = build("drive", "v3", credentials=creds)
    youtube = build("youtube", "v3", credentials=creds)
    return drive, youtube

def get_latest_video_file(drive):
    results = drive.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType='video/mp4'",
        orderBy="createdTime desc",
        pageSize=1,
        fields="files(id, name)"
    ).execute()
    files = results.get("files", [])
    if not files:
        raise Exception("No video files found in the Drive folder.")
    return files[0]["id"], files[0]["name"]

def download_file(drive, file_id, file_name):
    logging.info(f"📥 Downloading {file_name} from Drive...")
    request = drive.files().get_media(fileId=file_id)
    fh = io.FileIO(file_name, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        logging.info(f"⬇️ Download progress: {int(status.progress() * 100)}%")

def upload_to_youtube(youtube, file_name):
    logging.info(f"📤 Uploading {file_name} to YouTube...")
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": file_name,
                "description": "#shorts",
                "tags": ["shorts"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public"
            }
        },
        media_body=MediaFileUpload(file_name, resumable=True, mimetype="video/*")
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
    logging.info(f"✅ Uploaded: https://youtu.be/{response['id']}")
    return response["id"]

def delete_from_drive(drive, file_id):
    try:
        drive.files().delete(fileId=file_id).execute()
        logging.info("🗑️ Deleted video from Google Drive.")
    except HttpError as e:
        if e.resp.status == 403:
            logging.warning(f"⚠️ Failed to delete video from Drive: {e}")
        else:
            raise

def delete_local_file(file_name):
    try:
        os.remove(file_name)
        logging.info("🗑️ Deleted local file.")
    except Exception as e:
        logging.warning(f"⚠️ Failed to delete local file: {e}")

def upload_latest_video():
    logging.info("Upload job started...")
    drive, youtube = get_authenticated_services()
    file_id, file_name = get_latest_video_file(drive)
    download_file(drive, file_id, file_name)
    upload_to_youtube(youtube, file_name)
    delete_from_drive(drive, file_id)
    delete_local_file(file_name)

if __name__ == "__main__":
    upload_latest_video()
