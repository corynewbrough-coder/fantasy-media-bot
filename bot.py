import os
import time
import requests
from datetime import datetime
import pytz

# ------------------------
# Config
# ------------------------
BOT_ID = os.getenv("GROUPME_BOT_ID", "TEST_MODE")

# Replace these with your league settings
LEAGUE_ID = os.getenv("ESPN_LEAGUE_ID", "123456")
ESPN_S2 = os.getenv("ESPN_S2", "")
SWID = os.getenv("ESPN_SWID", "")

# ------------------------
# GroupMe Posting
# ------------------------
def post_message(msg):
    """Send a message to GroupMe bot"""
    if BOT_ID == "TEST_MODE":
        print("[TEST MODE]", msg)
        return
    requests.post(
        "https://api.groupme.com/v3/bots/post",
        json={"bot_id": BOT_ID, "text": msg}
    )

# ------------------------
# ESPN Data Fetch
# ------------------------
def fetch_scores():
    """Fetch weekly scores from ESPN Fantasy API"""
    url = f"https://fantasy.espn.com/apis/v3/games/ffl/seasons/2025/segments/0/leagues/{LEAGUE_ID}?view=mMatchup"
    cookies = {"SWID": SWID, "espn_s2": ESPN_S2}
    r = requests.get(url, cookies=cookies)
    if r.status_code != 200:
        print("Failed to fetch ESPN data")
        return []

    data = r.json()
    scores = []
    teams = {}

    # Map teamId to teamName
    for team in data.get("teams", []):
        teams[team["id"]] = team["location"] + " " + team["nickname"]

    # Current week matchups
    for matchup in data.get("schedule", []):
        if "home" in matchup and "away" in matchup:
            home_id = matchup["home"]["teamId"]
            away_id = matchup["away"]["teamId"]
            home_score = matchup["home"].get("totalPoints", 0)
            away_score = matchup["away"].get("totalPoints", 0)

            scores.append((teams[home_id], home_score))
            scores.append((teams[away_id], away_score))

    return scores

def median(scores):
    """Compute median score"""
    s = sorted(scores)
    n = len(s)
    if n == 0:
        return 0
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2

# ------------------------
# Main Bot Logic
# ------------------------
def run_update():
    scores = fetch_scores()
    if not scores:  # No scores available
        post_message("Test 1 2 3 (no scores yet)")
        return

    score_values = [s for _, s in scores]
    med = median(score_values)

    msg_lines = ["🏈 Weekly Scores:"]
    for team, score in scores:
        status = "✅ Above Median" if score > med else "❌ Below Median"
        msg_lines.append(f"{team}: {score} ({status})")

    msg_lines.append(f"\nLeague Median: {med:.2f}")
    post_message("\n".join(msg_lines))

# ------------------------
# Scheduler
# ------------------------
def check_and_post():
    est = pytz.timezone("US/Eastern")
    now = datetime.now(est)

    # Sunday (6) 1PM–11:59PM
    if now.weekday() == 6 and 13 <= now.hour <= 23:
        run_update()
    # Monday (0) 9PM–11:59PM
    elif now.weekday() == 0 and 21 <= now.hour <= 23:
        run_update()
    else:
        print("Not in update window, skipping...")

if __name__ == "__main__":
    while True:
        check_and_post()
        time.sleep(60 * 60)  # sleep 1 hour
