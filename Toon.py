import os, time, random, subprocess, requests, traceback
from datetime import datetime, timedelta, timezone
from requests.auth import HTTPBasicAuth

# ================= CONFIG =================
TEST_MODE = False
MAX_RETRIES = 3
RETRY_DELAY = 60

UPLOAD_LOG = "uploaded.txt"
DAILY_LOG  = "daily_log.txt"

# ================= TIME =================
IST = timezone(timedelta(hours=5, minutes=30))

# ================= SECRETS =================
IG_TOKEN   = os.getenv("TOON4_TOON_IG_TOKEN")
IG_USER_ID = os.getenv("TOON4_TOON_IG_USER_ID")

CLOUD_NAME = os.getenv("TOON4_TOON_CLOUD_NAME")
API_KEY    = os.getenv("TOON4_TOON_API_KEY")
API_SECRET = os.getenv("TOON4_TOON_API_SECRET")

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID   = os.getenv("TG_CHAT_ID")
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "Instagram Channel")

if not all([IG_TOKEN, IG_USER_ID, CLOUD_NAME, API_KEY, API_SECRET]):
    print("❌ Missing secrets")
    exit(1)

print("✅ Secrets loaded")

# ================= TELEGRAM =================
def tg_send(msg):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    requests.post(
        f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
        data={"chat_id": TG_CHAT_ID, "text": msg},
        timeout=10
    )

def notify_success():
    time_now = datetime.now(IST).strftime("%d %b %Y | %H:%M IST")
    msg = (
        "✅ Instagram Reel Uploaded Successfully\n\n"
        f"📸 Page: {CHANNEL_NAME}\n"
        f"⏰ Time: {time_now}"
    )
    tg_send(msg)

def notify_failure(reason):
    time_now = datetime.now(IST).strftime("%d %b %Y | %H:%M IST")
    msg = (
        "❌ Instagram Reel Upload FAILED\n\n"
        f"📸 Page: {CHANNEL_NAME}\n"
        f"⏰ Time: {time_now}\n"
        f"⚠️ Reason: {reason}"
    )
    tg_send(msg)

# ================= CAPTION =================
CAPTIONS = [
    "This story doesn’t exist anywhere else",
    "Watch till the end! The twist is crazy",
    "AI wrote this… but it feels real",
    "One story. One twist. Pure AI"
]

HASHTAGS = ["#viral", "#trending", "#trendingreels", "#aistroytelling"]

def make_caption():
    return f"{random.choice(CAPTIONS)}\n\n{' '.join(HASHTAGS)}"

# ================= FILE HELPERS =================
def ensure_file(path):
    if not os.path.exists(path):
        open(path, "w", encoding="utf-8").close()

def read_file(path):
    ensure_file(path)
    with open(path, encoding="utf-8") as f:
        return set(f.read().splitlines())

def write_file(path, line):
    ensure_file(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def today():
    return datetime.now(IST).strftime("%Y-%m-%d")

# ================= CLOUDINARY =================
def get_videos():
    print("📦 Fetching videos from Cloudinary...")
    uploaded = read_file(UPLOAD_LOG)
    videos, cursor = [], None

    while True:
        params = {"type": "upload", "max_results": 100}
        if cursor:
            params["next_cursor"] = cursor

        r = requests.get(
            f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/resources/video",
            params=params,
            auth=HTTPBasicAuth(API_KEY, API_SECRET),
            timeout=30
        )
        r.raise_for_status()

        data = r.json()
        for v in data.get("resources", []):
            if v["secure_url"] not in uploaded:
                videos.append(v)

        cursor = data.get("next_cursor")
        if not cursor:
            break

    print(f"🎞️ New videos found: {len(videos)}")
    return videos

# ================= INSTAGRAM UPLOAD =================
def upload_instagram(video_url):
    caption = make_caption()

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"🚀 Upload attempt {attempt}/{MAX_RETRIES}")

        r = requests.post(
            f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": IG_TOKEN
            }
        ).json()

        if "id" not in r:
            time.sleep(RETRY_DELAY)
            continue

        creation_id = r["id"]
        print("⏳ Processing reel...")

        for _ in range(15):
            s = requests.get(
                f"https://graph.facebook.com/v19.0/{creation_id}",
                params={"fields": "status_code", "access_token": IG_TOKEN}
            ).json()

            if s.get("status_code") == "FINISHED":
                break
            time.sleep(20)
        else:
            return False

        pub = requests.post(
            f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
            data={"creation_id": creation_id, "access_token": IG_TOKEN}
        ).json()

        if "id" in pub:
            return True

        time.sleep(RETRY_DELAY)

    return False

# ================= GIT =================
def git_commit():
    subprocess.run(["git", "config", "user.name", "toon4_toon_bot"])
    subprocess.run(["git", "config", "user.email", "bot@toon4toon"])
    subprocess.run(["git", "add", UPLOAD_LOG, DAILY_LOG])
    subprocess.run(["git", "commit", "-m", "🎬 Reel uploaded"], check=False)
    subprocess.run(["git", "push"], check=False)

# ================= MAIN =================
print("🤖 Toon4_Toon IG Bot Started")

try:
    videos = get_videos()
    if not videos:
        notify_failure("No new videos in Cloudinary")
        exit()

    video = random.choice(videos)
    print("🎯 Video selected")

    if upload_instagram(video["secure_url"]):
        write_file(UPLOAD_LOG, video["secure_url"])
        write_file(DAILY_LOG, f"{today()}|posted")
        git_commit()
        notify_success()
        print("🎉 All done")
    else:
        notify_failure("Instagram API upload failed")
        print("❌ Upload failed")

except Exception as e:
    notify_failure(str(e))
    traceback.print_exc()
