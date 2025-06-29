import os
import json
import base64
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests

# Scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/youtube.upload"
]

# Google Drive folder ID (replace if needed)
DRIVE_FOLDER_ID = "1S53xGR45LjWhbwcfTJgOK4zOWkSQFtUA"

def load_credentials():
    # Decode and write credentials.json
    cred_json_b64 = os.environ.get("CREDENTIALS_JSON")
    token_json_b64 = os.environ.get("TOKEN_JSON")

    if not cred_json_b64 or not token_json_b64:
        raise Exception("Missing CREDENTIALS_JSON or TOKEN_JSON in environment variables.")

    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(cred_json_b64).decode())

    with open("token.json", "w") as f:
        f.write(base64.b64decode(token_json_b64).decode())

    creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # Refresh if needed
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds.refresh_token:
        raise Exception("Valid token.json with refresh_token is required on server.")

    return creds

def get_authenticated_services():
    creds = load_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    youtube_service = build("youtube", "v3", credentials=creds)
    return drive_service, youtube_service

def upload_latest_video():
    print(f"[{datetime.datetime.now()}] Upload job started...")

    drive, youtube = get_authenticated_services()

    # Find latest .mp4 file in the specified Drive folder
    query = f"'{DRIVE_FOLDER_ID}' in parents and mimeType='video/mp4'"
    results = drive.files().list(q=query, orderBy="createdTime desc", pageSize=1, fields="files(id, name)").execute()
    items = results.get("files", [])

    if not items:
        print("No video file found in Drive folder.")
        return

    file = items[0]
    file_id = file["id"]
    file_name = file["name"]

    print(f"Downloading file from Drive: {file_name}")
    request = drive.files().get_media(fileId=file_id)
    response = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media", headers={
        "Authorization": f"Bearer {drive._http.credentials.token}"
    })

    with open(file_name, "wb") as f:
        f.write(response.content)

    # Upload to YouTube
    print(f"Uploading to YouTube: {file_name}")
    body = {
        "snippet": {
            "title": os.path.splitext(file_name)[0],
            "description": "Automated YouTube Shorts upload",
            "tags": ["shorts"],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(file_name, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()

    print(f"✅ Uploaded: https://youtu.be/{response['id']}")

    # Cleanup
    os.remove(file_name)
    drive.files().delete(fileId=file_id).execute()
    print(f"🗑️ Deleted local file and Drive file: {file_name}")

if __name__ == "__main__":
    upload_latest_video()
