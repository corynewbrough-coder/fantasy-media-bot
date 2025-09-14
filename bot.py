import statistics
from datetime import datetime, time, timedelta
import pytz
import requests
from espn_api.football import League

# ----------------------------
# Hard-coded config (safe in private repo)
# ----------------------------
LEAGUE_ID = 2075760555
YEAR = 2025
SWID = "{AFDF1C35-C3FF-4E8F-AD85-63D85CCE88ED}"
ESPN_S2 = "AECFFuqpnKkwgOlcCijqY71viRNLKIOsWVRu4cRQKbzfnIrJbf0jkAZ9x3csHAQz03U0D%2F9oCeXuchZVZa0M6Z4VQSYiFUwr7%2F5rrE1LZ6O6ySVeWsLC7xTsx%2FlDvw83DfRsffDlAaNdichxwCO2SY274IL0Cmlq68Ght9P8cekf4qid20hElhBWHC4KXdzVfPrh%2BX9tZIKqfxmtBtgC4Qf4m%2BueKsogUnTADTF672fbxy8G3LcurbepB1YLOehRokBXx9alTK3qS6b19hFlMOI5ch%2Bzaax2GIbYiitGkYDYXb%2B1Iatss9pwd1aSkt87XyI%3D"
GROUPME_BOT_ID = "b63cecb7e82d210797808b6f11"
TEST_MODE = False  # set True for test posts any time

# ----------------------------
# Timezone and schedule
# ----------------------------
EASTERN = pytz.timezone("US/Eastern")
TOLERANCE_MINUTES = 3  # ±3 minute buffer

SUNDAY_TIMES = [time(10, 0), time(16, 0), time(20, 0), time(23, 30)]
MONDAY_TIMES = [time(21, 30), time(22, 30), time(23, 59)]
THURSDAY_TIMES = [time(23, 59)]

# ----------------------------
# Helper functions
# ----------------------------
def within_post_window(now_eastern: datetime) -> bool:
    """Check if the current time is within TOLERANCE_MINUTES of a scheduled posting time."""
    if TEST_MODE:
        return True

    current_time = now_eastern.time()
    weekday = now_eastern.weekday()

    if weekday == 6:  # Sunday
        scheduled_times = SUNDAY_TIMES
    elif weekday == 0:  # Monday
        scheduled_times = MONDAY_TIMES
    elif weekday == 3:  # Thursday
        scheduled_times = THURSDAY_TIMES
    else:
        return False

    for sched in scheduled_times:
        lower = (datetime.combine(now_eastern.date(), sched) - timedelta(minutes=TOLERANCE_MINUTES)).time()
        upper = (datetime.combine(now_eastern.date(), sched) + timedelta(minutes=TOLERANCE_MINUTES)).time()
        if lower <= current_time <= upper:
            return True

    return False

def post_to_groupme(text: str):
    url = "https://api.groupme.com/v3/bots/post"
    payload = {"bot_id": GROUPME_BOT_ID, "text": text}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()

def format_scoreboard(title: str, scores: list[tuple[str, float]]) -> str:
    """Formats a scoreboard with median comparison."""
    if not scores:
        return f"{title}: No data available."

    median_score = statistics.median([s for _, s in scores])
    scores.sort(key=lambda x: x[1], reverse=True)

    lines = []
    for name, score in scores:
        mark = "✅" if score >= median_score else "❌"
        lines.append(f"{name}: {score:.1f} {mark}")

    return f"{title}\nMedian: {median_score:.1f}\n" + "\n".join(lines)

def build_message() -> str:
    if TEST_MODE:
        return """✅ Test mode active!
📅 Thursday: 11:59 PM EST
📅 Sunday: 10:00 AM, 4:00 PM, 8:00 PM, 11:30 PM EST
📅 Monday: 9:30 PM, 10:30 PM, 11:59 PM EST

Message will include BOTH live scores and projected scores with median checks."""

    league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)
    matchups = league.scoreboard()

    live_scores = []
    projected_scores = []

    for m in matchups:
        live_scores.append((m.home_team.team_name, float(m.home_score)))
        live_scores.append((m.away_team.team_name, float(m.away_score)))

        projected_scores.append((m.home_team.team_name, float(m.home_projected)))
        projected_scores.append((m.away_team.team_name, float(m.away_projected)))

    now_eastern_str = datetime.now(EASTERN).strftime("%a %I:%M %p %Z")
    header = f"📊 Fantasy Scores — {now_eastern_str}\n"

    live_block = format_scoreboard("🔥 Live Scores", live_scores)
    proj_block = format_scoreboard("🔮 Projected Scores", projected_scores)

    return header + "\n\n" + live_block + "\n\n" + proj_block

# ----------------------------
# Main bot loop
# ----------------------------
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
