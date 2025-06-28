import os
import time
import shutil
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from apscheduler.schedulers.blocking import BlockingScheduler

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/drive.readonly"]
SCHEDULE = ["12:00", "14:00", "16:00", "18:15", "19:30"]
VIDEO_FOLDER = "videos"
UPLOADED_FOLDER = "uploaded"
DESCRIPTION = "🔥 Watch now! #shorts #viral"
TAGS = ["shorts", "viral", "funny"]

def get_authenticated_services():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError("❌ 'credentials.json' not found in project directory.")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_console()  # 👈 no browser needed

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    drive = build("drive", "v3", credentials=creds)
    youtube = build("youtube", "v3", credentials=creds)
    return drive, youtube

def get_next_video():
    if not os.path.exists(VIDEO_FOLDER):
        os.makedirs(VIDEO_FOLDER)
    videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith(".mp4")]
    return videos[0] if videos else None

def get_next_scheduled_time():
    now = datetime.now()
    for sched_time in SCHEDULE:
        target = datetime.strptime(sched_time, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
        if target > now:
            return target
    return datetime.strptime(SCHEDULE[0], "%H:%M").replace(
        year=now.year, month=now.month, day=now.day
    ) + timedelta(days=1)

def upload_to_youtube(youtube, filename):
    title = os.path.splitext(filename)[0]
    media = MediaFileUpload(os.path.join(VIDEO_FOLDER, filename), resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": DESCRIPTION,
                "tags": TAGS,
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public"
            },
        },
        media_body=media
    )

    print(f"⬆️ Uploading: {filename}...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"⏫ Uploaded {int(status.progress() * 100)}%")

    print(f"✅ Uploaded: {filename} (videoId: {response['id']})")

    # Safely move uploaded file
    uploaded_path = os.path.join(UPLOADED_FOLDER, filename)
    if not os.path.exists(UPLOADED_FOLDER):
        os.makedirs(UPLOADED_FOLDER)

    media._fd.close()  # Ensure file is closed
    for _ in range(3):
        try:
            shutil.move(os.path.join(VIDEO_FOLDER, filename), uploaded_path)
            break
        except PermissionError:
            print("⚠️ File is locked. Retrying...")
            time.sleep(1)

def scheduled_upload():
    drive, youtube = get_authenticated_services()
    filename = get_next_video()
    if not filename:
        print("📂 No videos found in 'videos/' folder.")
        return

    upload_to_youtube(youtube, filename)

if __name__ == "__main__":
    print("✅ Authenticated")
    next_time = get_next_scheduled_time()
    wait_sec = (next_time - datetime.now()).total_seconds()
    print(f"⏳ Waiting {int(wait_sec)} seconds until next scheduled upload at {next_time.strftime('%H:%M')}...")
    time.sleep(wait_sec)
    scheduled_upload()
