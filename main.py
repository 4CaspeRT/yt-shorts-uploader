import os
import json
import base64
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 🔐 Updated SCOPES: Full Drive access (not read-only)
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/youtube.upload'
]

# 📦 Load credentials from environment (on server) or from file (locally)
def load_credentials():
    creds = None

    # Decode and save credentials.json from environment if available
    cred_b64 = os.environ.get("CREDENTIALS_JSON")
    if cred_b64:
        with open("credentials.json", "w") as f:
            f.write(base64.b64decode(cred_b64).decode())

    # Decode and save token.json from environment if available
    token_b64 = os.environ.get("TOKEN_JSON")
    if token_b64:
        with open("token.json", "w") as f:
            f.write(base64.b64decode(token_b64).decode())

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    if not creds or not creds.valid or not creds.refresh_token:
        raise Exception("Valid token.json with refresh_token is required on server.")

    return creds

# 🔑 Get Drive and YouTube service objects
def get_authenticated_services():
    creds = load_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    youtube_service = build("youtube", "v3", credentials=creds)
    return drive_service, youtube_service

# 🚀 Upload logic
def upload_latest_video():
    print(f"[{datetime.datetime.now()}] Upload job started...")

    drive, youtube = get_authenticated_services()

    # 🔍 Search in specific Google Drive folder
    folder_id = "1S53xGR45LjWhbwcfTJgOK4zOWkSQFtUA"
    query = f"'{folder_id}' in parents and mimeType='video/mp4'"
    results = drive.files().list(
        q=query,
        pageSize=1,
        orderBy="createdTime desc",
        fields="files(id, name)"
    ).execute()

    files = results.get("files", [])
    if not files:
        print("No video found in Drive.")
        return

    video = files[0]
    file_id = video["id"]
    file_name = video["name"]

    print(f"📥 Downloading {file_name} from Drive...")
    request = drive.files().get_media(fileId=file_id)
    with open(file_name, "wb") as f:
        downloader = drive._http.request("GET", f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
        f.write(downloader.data)
    print("⬇️ Download progress: 100%")

    print(f"📤 Uploading {file_name} to YouTube...")
    request_body = {
        "snippet": {
            "title": file_name,
            "description": "Automated upload",
            "tags": ["shorts"],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media_file = MediaFileUpload(file_name, mimetype="video/mp4", resumable=True)
    upload_request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media_file
    )
    response = upload_request.execute()
    print(f"✅ Uploaded: https://youtu.be/{response['id']}")

    # 🗑 Delete from Drive
    try:
        drive.files().delete(fileId=file_id).execute()
        print(f"🗑 Deleted {file_name} from Google Drive.")
    except Exception as e:
        print("⚠️ Failed to delete from Drive:", e)

    # 🧹 Delete locally
    try:
        os.remove(file_name)
        print(f"🧹 Deleted {file_name} from local storage.")
    except Exception as e:
        print("⚠️ Failed to delete local file:", e)

# 🕒 Trigger manually
if __name__ == "__main__":
    upload_latest_video()
