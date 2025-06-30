import os
import io
import json
import base64
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime

logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO)

# ✅ USE FULL DRIVE ACCESS TO ALLOW DELETING FILES
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]

# ✅ SET YOUR FOLDER ID HERE
FOLDER_ID = "1S53xGR45LjWhbwcfTJgOK4zOWkSQFtUA"

# ✅ STATIC INFO (Set these to your fixed description and tags)
YOUTUBE_DESCRIPTION = "Thanks for watching! 🔥 Subscribe for more Shorts."
YOUTUBE_TAGS = ["Shorts", "YouTube Shorts", "Trending", "Viral", "Daily Content"]

def load_credentials():
    credentials_json = os.environ.get("CREDENTIALS_JSON")
    token_json = os.environ.get("TOKEN_JSON")

    if credentials_json and token_json:
        creds_data = json.loads(base64.b64decode(credentials_json))
        token_data = json.loads(base64.b64decode(token_json))
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    else:
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        else:
            raise Exception("Environment variables for credentials or token are missing.")
    return creds

def get_authenticated_services():
    creds = load_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    youtube_service = build("youtube", "v3", credentials=creds)
    return drive_service, youtube_service

def get_latest_video_file(drive):
    response = drive.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType='video/mp4'",
        orderBy="createdTime desc",
        pageSize=1,
        fields="files(id, name)"
    ).execute()
    files = response.get("files", [])
    if not files:
        raise Exception("No video files found in Google Drive folder.")
    return files[0]["id"], files[0]["name"]

def download_file(drive, file_id, file_name):
    request = drive.files().get_media(fileId=file_id)
    fh = io.FileIO(file_name, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return file_name

def upload_to_youtube(youtube, video_file, title):
    request_body = {
        "snippet": {
            "title": title,
            "description": YOUTUBE_DESCRIPTION,
            "tags": YOUTUBE_TAGS,
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    media = MediaFileUpload(video_file, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
    return response["id"]

def delete_drive_file(drive, file_id):
    try:
        drive.files().delete(fileId=file_id).execute()
        logging.info("🗑️ Deleted video from Google Drive.")
    except HttpError as e:
        logging.warning(f"⚠️ Failed to delete video from Drive: {e}")

def delete_local_file(file_path):
    try:
        os.remove(file_path)
        logging.info("🗑️ Deleted local file.")
    except Exception as e:
        logging.warning(f"⚠️ Failed to delete local file: {e}")

def upload_latest_video():
    logging.info("Upload job started...")
    drive, youtube = get_authenticated_services()

    file_id, file_name = get_latest_video_file(drive)
    logging.info(f"📥 Downloading {file_name} from Drive...")
    download_file(drive, file_id, file_name)
    logging.info("⬇️ Download progress: 100%")

    title = os.path.splitext(file_name)[0]
    logging.info(f"📤 Uploading {file_name} to YouTube...")
    video_id = upload_to_youtube(youtube, file_name, title)
    logging.info(f"✅ Uploaded: https://youtu.be/{video_id}")

    delete_drive_file(drive, file_id)
    delete_local_file(file_name)

if __name__ == "__main__":
    upload_latest_video()
