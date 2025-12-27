from flask import Flask, render_template, redirect, url_for, request
import feedparser
import sqlite3
import json
import os

app = Flask(__name__)
DB_PATH = "curefeed.db"
CHANNELS_PATH = "channels.json"

# ---------------- LOAD CHANNELS (JSON) ----------------

with open(CHANNELS_PATH, "r", encoding="utf-8") as f:
    channels = json.load(f)

# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watched (
            video_id TEXT PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

def is_watched(video_id):
    conn = get_db()
    cur = conn.execute(
        "SELECT 1 FROM watched WHERE video_id = ?",
        (video_id,)
    )
    result = cur.fetchone()
    conn.close()
    return result is not None

def mark_watched(video_id):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO watched (video_id) VALUES (?)",
        (video_id,)
    )
    conn.commit()
    conn.close()

# ---------------- HELPERS ----------------

def get_channel(channel_id):
    return next((c for c in channels if c["id"] == channel_id), None)

def get_latest_video(channel_id):
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(rss_url)

    if not feed.entries:
        return None

    entry = feed.entries[0]

    thumbnail = (
        entry.media_thumbnail[0]["url"]
        if hasattr(entry, "media_thumbnail")
        else f"https://i.ytimg.com/vi/{entry.yt_videoid}/hqdefault.jpg"
    )

    return {
        "id": entry.yt_videoid,
        "title": entry.title,
        "url": entry.link,
        "thumbnail": thumbnail
    }

def get_general_feed():
    feed = []

    for ch in channels:
        video = get_latest_video(ch["channel_id"])
        if video and not is_watched(video["id"]):
            feed.append({
                "channel": ch,
                "video": video
            })

    return feed

# ---------------- ROUTES ----------------

@app.route("/")
def general_feed():
    feed = get_general_feed()
    return render_template("feed.html", feed=feed, channels=channels)

@app.route("/channel/<channel_id>")
def channel_view(channel_id):
    channel = get_channel(channel_id)
    if not channel:
        return redirect(url_for("general_feed"))

    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel['channel_id']}"
    feed = feedparser.parse(rss_url)

    videos = []
    for entry in feed.entries[:5]:  # 🔒 HARD LIMIT
        thumbnail = (
            entry.media_thumbnail[0]["url"]
            if hasattr(entry, "media_thumbnail")
            else f"https://i.ytimg.com/vi/{entry.yt_videoid}/hqdefault.jpg"
        )

        videos.append({
            "id": entry.yt_videoid,
            "title": entry.title,
            "thumbnail": thumbnail,
            "watched": is_watched(entry.yt_videoid)
        })

    return render_template(
        "channel.html",
        channel=channel,
        videos=videos,
        channels=channels
    )

@app.route("/watch", methods=["POST"])
def watch():
    video_id = request.form.get("video_id")
    if video_id:
        mark_watched(video_id)
        return redirect(f"https://www.youtube.com/watch?v={video_id}")
    return redirect(url_for("general_feed"))

@app.route("/player/<video_id>")
def player(video_id):
    return render_template(
        "player.html",
        video_id=video_id,
        channels=channels
    )

@app.route("/play/<video_id>", methods=["POST"])
def play(video_id):
    mark_watched(video_id)
    return redirect(url_for("player", video_id=video_id))


# ---------------- STARTUP ----------------

if __name__ == "__main__":
    init_db()
    app.run(
        debug=False,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 7777))
    )
