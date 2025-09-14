import statistics
from datetime import datetime, time
import pytz
import requests
from espn_api.football import League

# ----------------------------
# Configuration
# ----------------------------
LEAGUE_ID = 2075760555
YEAR = 2025
SWID = "{AFDF1C35-C3FF-4E8F-AD85-63D85CCE88ED}"
ESPN_S2 = "AECFFuqpnKkwgOlcCijqY71viRNLKIOsWVRu4cRQKbzfnIrJbf0jkAZ9x3csHAQz03U0D%2F9oCeXuchZVZa0M6Z4VQSYiFUwr7%2F5rrE1LZ6O6ySVeWsLC7xTsx%2FlDvw83DfRsffDlAaNdichxwCO2SY274IL0Cmlq68Ght9P8cekf4qid20hElhBWHC4KXdzVfPrh%2BX9tZIKqfxmtBtgC4Qf4m%2BueKsogUnTADTF672fbxy8G3LcurbepB1YLOehRokBXx9alTK3qS6b19hFlMOI5ch%2Bzaax2GIbYiitGkYDYXb%2B1Iatss9pwd1aSkt87XyI%3D"
GROUPME_BOT_ID = "b63cecb7e82d210797808b6f11"
TEST_MODE = False  # True for testing, False for production

EASTERN = pytz.timezone("US/Eastern")

# ----------------------------
# Posting windows
# ----------------------------
SUNDAY_TIMES = [time(10, 0), time(16, 0), time(20, 0), time(23, 30)]
MONDAY_TIMES = [time(21, 30), time(22, 30), time(23, 59)]
THURSDAY_TIMES = [time(23, 59)]

# ----------------------------
# Helper functions
# ----------------------------
def post_to_groupme(text: str):
    """Send a message to GroupMe via bot."""
    url = "https://api.groupme.com/v3/bots/post"
    payload = {"bot_id": GROUPME_BOT_ID, "text": text}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()

def build_scoreboard(league: League, projected: bool = False) -> str:
    """Build a scoreboard message for current or projected scores."""
    matchups = league.scoreboard()
    team_scores = []

    for m in matchups:
        if projected:
            team_scores.append((m.home_team.team_name, float(m.home_projected_score)))
            team_scores.append((m.away_team.team_name, float(m.away_projected_score)))
        else:
            team_scores.append((m.home_team.team_name, float(m.home_score)))
            team_scores.append((m.away_team.team_name, float(m.away_score)))

    if not team_scores:
        return "No matchups found right now."

    scores_only = [s for _, s in team_scores]
    median_score = statistics.median(scores_only)
    team_scores.sort(key=lambda x: x[1], reverse=True)

    lines = []
    for name, score in team_scores:
        mark = "✅" if score >= median_score else "❌"
        lines.append(f"{name}: {score:.1f} {mark}")

    type_label = "Projected Scores" if projected else "Current Scores"
    now_str = datetime.now(EASTERN).strftime("%a %I:%M %p %Z")
    header = f"📊 {type_label} — {now_str}\nLeague Median: {median_score:.1f}\n"
    return header + "\n" + "\n".join(lines)

def within_post_window(now_eastern: datetime) -> bool:
    """Check if current time matches a scheduled posting time."""
    if TEST_MODE:
        return True

    weekday = now_eastern.weekday()
    current_time = now_eastern.time()

    if weekday == 6:
        scheduled_times = SUNDAY_TIMES
    elif weekday == 0:
        scheduled_times = MONDAY_TIMES
    elif weekday == 3:
        scheduled_times = THURSDAY_TIMES
    else:
        return False

    # Exact match (cron handles timing), no ± tolerance needed
    return any(current_time.hour == t.hour and current_time.minute == t.minute for t in scheduled_times)

# ----------------------------
# Main bot function
# ----------------------------
def main():
    now_eastern = datetime.now(EASTERN)
    if not within_post_window(now_eastern):
        print(f"Outside posting window: {now_eastern}")
        return

    try:
        league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)
        # Current scores
        msg_current = build_scoreboard(league, projected=False)
        post_to_groupme(msg_current)
        # Projected scores
        msg_projected = build_scoreboard(league, projected=True)
        post_to_groupme(msg_projected)
    except Exception as e:
        try:
            post_to_groupme(f"Bot error: {e}")
        except Exception:
            print(f"Failed to report error: {e}")

if __name__ == "__main__":
    main()
