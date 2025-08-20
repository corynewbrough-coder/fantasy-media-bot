import os
import statistics
from datetime import datetime, time
import pytz
import requests
from espn_api.football import League
from dotenv import load_dotenv

# Load local env for testing; Render will inject env vars itself
load_dotenv()

LEAGUE_ID = int(os.getenv("LEAGUE_ID"))
YEAR = int(os.getenv("YEAR", "2025"))
SWID = os.getenv("SWID")
ESPN_S2 = os.getenv("ESPN_S2")
GROUPME_BOT_ID = os.getenv("GROUPME_BOT_ID")

EASTERN = pytz.timezone("US/Eastern")

# 👇 add this
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

def within_post_window(now_eastern: datetime) -> bool:
    if TEST_MODE:
        return True  # always allow during testing
    # Sundays 1:00 PM–11:59 PM ET
    if now_eastern.weekday() == 6:
        return time(13, 0) <= now_eastern.time() <= time(23, 59)
    # Mondays 9:00 PM–11:59 PM ET
    if now_eastern.weekday() == 0:
        return time(21, 0) <= now_eastern.time() <= time(23, 59)
    return False

def post_to_groupme(text: str):
    url = "https://api.groupme.com/v3/bots/post"
    payload = {"bot_id": GROUPME_BOT_ID, "text": text}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()

def build_message() -> str:
    if TEST_MODE:
        return "✅ Test 1 2 3 — bot is posting to GroupMe!"

    league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)
    matchups = league.scoreboard()
    team_scores = []
    for m in matchups:
        team_scores.append((m.home_team.team_name, float(m.home_score)))
        team_scores.append((m.away_team.team_name, float(m.away_score)))

    if not team_scores:
        return "No live matchups found right now."

    scores_only = [s for _, s in team_scores]
    median_score = statistics.median(scores_only)
    team_scores.sort(key=lambda x: x[1], reverse=True)

    lines = []
    for name, score in team_scores:
        mark = "✅" if score >= median_score else "❌"
        lines.append(f"{name}: {score:.1f} {mark}")

    now_eastern = datetime.now(EASTERN).strftime("%a %I:%M %p %Z")
    header = f"📊 Live Fantasy Scores — {now_eastern}\nLeague Median: {median_score:.1f}\n"
    return header + "\n" + "\n".join(lines)

def main():
    now_eastern = datetime.now(EASTERN)
    if not within_post_window(now_eastern):
        return
    try:
        msg = build_message()
        post_to_groupme(msg)
    except Exception as e:
        try:
            post_to_groupme(f"Bot error: {e}")
        except Exception:
            pass

if __name__ == "__main__":
    main()
