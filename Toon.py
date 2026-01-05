import os, time, random, subprocess, requests
from datetime import datetime, timedelta, timezone
from requests.auth import HTTPBasicAuth

# ================= CONFIG =================
TEST_MODE = False          # True = test only | False = LIVE
MAX_RETRIES = 3
RETRY_DELAY = 60

UPLOAD_LOG = "uploaded.txt"
DAILY_LOG = "daily_log.txt"

# ================= TIME =================
IST = timezone(timedelta(hours=5, minutes=30))

# ================= SECRETS (Toon4_Toon) =================
IG_TOKEN   = os.getenv("TOON4_TOON_IG_TOKEN")
IG_USER_ID = os.getenv("TOON4_TOON_IG_USER_ID")
CLOUD_NAME = os.getenv("TOON4_TOON_CLOUD_NAME")
API_KEY    = os.getenv("TOON4_TOON_API_KEY")
API_SECRET = os.getenv("TOON4_TOON_API_SECRET")

if not all([IG_TOKEN, IG_USER_ID, CLOUD_NAME, API_KEY, API_SECRET]):
    print("❌ Missing Toon4_Toon secrets")
    exit(1)

print("✅ Secrets loaded")

# ================= CAPTION =================
CAPTIONS = [
    "Parents vs Dreams",
    "Middle class life be like",
    "Reality hits different",
    "Relatable cartoon moment",
]
HASHTAGS = ["#reels", "#cartoon", "#animation"]

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

    if TEST_MODE:
        print("🧪 TEST MODE")
        print("🎬 Would upload:", video_url)
        print("📝 Caption:", caption)
        return True

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
            print("⚠️ Upload request failed, retrying...")
            time.sleep(RETRY_DELAY)
            continue

        creation_id = r["id"]
        print("⏳ Processing reel...")

        for _ in range(12):
            s = requests.get(
                f"https://graph.facebook.com/v19.0/{creation_id}",
                params={"fields": "status_code", "access_token": IG_TOKEN}
            ).json()

            if s.get("status_code") == "FINISHED":
                break
            time.sleep(20)
        else:
            print("❌ Processing timeout")
            return False

        pub = requests.post(
            f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
            data={"creation_id": creation_id, "access_token": IG_TOKEN}
        ).json()

        if "id" in pub:
            print("✅ Reel published 🎉")
            return True

        print("⚠️ Publish failed, retrying...")
        time.sleep(RETRY_DELAY)

    print("❌ Upload failed after retries")
    return False

# ================= GIT COMMIT =================
def git_commit():
    if TEST_MODE:
        print("🧪 Test mode → skipping git commit")
        return

    subprocess.run(["git", "config", "user.name", "toon4_toon_bot"])
    subprocess.run(["git", "config", "user.email", "bot@toon4toon"])
    subprocess.run(["git", "add", UPLOAD_LOG, DAILY_LOG])
    subprocess.run(["git", "commit", "-m", "🎬 Toon4_Toon reel uploaded"], check=False)
    subprocess.run(["git", "push"], check=False)
    print("📤 Logs pushed to GitHub")

# ================= MAIN =================
print("🤖 Toon4_Toon Bot Started")

videos = get_videos()
if not videos:
    print("😴 No new videos")
    exit()

video = random.choice(videos)
print("🎯 Video selected")

if upload_instagram(video["secure_url"]):
    write_file(UPLOAD_LOG, video["secure_url"])
    write_file(DAILY_LOG, f"{today()}|posted")
    git_commit()
    print("🎉 All done")
else:
    print("❌ Bot finished with error")
