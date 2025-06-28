import os
import json
import time
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from apscheduler.schedulers.blocking import BlockingScheduler

# Scopes for Google APIs
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/drive"
]

# Step 1: Reconstruct credential files from environment variables
def write_credentials_from_env():
    creds_json = os.getenv("CREDENTIALS_JSON")
    token_json = os.getenv("TOKEN_JSON")

    if creds_json:
        with open("credentials.json", "w") as f:
            f.write(creds_json)
    else:
        raise Exception("CREDENTIALS_JSON environment variable is missing!")

    if token_json:
        with open("token.json", "w") as f:
            f.write(token_json)
    else:
        raise Exception("TOKEN_JSON environment variable is missing!")

# Step 2: Authenticate with YouTube and Drive
def get_authenticated_services():
    write_credentials_from_env()

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_console()

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)
    drive = build("drive", "v3", credentials=creds)
    return drive, youtube

# Dummy function to simulate upload (replace with your actual logic)
def upload_to_youtube(video_path, title, description, tags, publish_time):
    try:
        print(f"Uploading: {video_path}")
        # Your upload logic goes here...
        # ...
        print("✅ Upload successful!")
    except HttpError as e:
        print(f"❌ Upload failed: {e}")

# Scheduler logic
def job():
    now = datetime.now()
    publish_time = (now + timedelta(minutes=5)).isoformat("T") + "Z"
    upload_to_youtube(
        "videos/example.mp4",
        "My YouTube Short Title",
        "My video description",
        ["shorts", "example"],
        publish_time
    )

if __name__ == "__main__":
    try:
        drive, youtube = get_authenticated_services()
        scheduler = BlockingScheduler()
        scheduler.add_job(job, "interval", hours=1)
        scheduler.start()
    except Exception as e:
        print(f"⚠️ Error: {e}")
