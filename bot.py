import statistics
from datetime import datetime, time, timedelta
import pytz
import requests
from espn_api.football import League

# ----------------------------
# Config
# ----------------------------
LEAGUE_ID = 2075760555
YEAR = 2025
SWID = "{AFDF1C35-C3FF-4E8F-AD85-63D85CCE88ED}"
ESPN_S2 = "AECFFuqpnKkwgOlcCijqY71viRNLKIOsWVRu4cRQKbzfnIrJbf0jkAZ9x3csHAQz03U0D%2F9oCeXuchZVZa0M6Z4VQSYiFUwr7%2F5rrE1LZ6O6ySVeWsLC7xTsx%2FlDvw83DfRsffDlAaNdichxwCO2SY274IL0Cmlq68Ght9P8cekf4qid20hElhBWHC4KXdzVfPrh%2BX9tZIKqfxmtBtgC4Qf4m%2BueKsogUnTADTF672fbxy8G3LcurbepB1YLOehRokBXx9alTK3qS6b19hFlMOI5ch%2Bzaax2GIbYiitGkYDYXb%2B1Iatss9pwd1aSkt87XyI%3D"
GROUPME_BOT_ID = "b63cecb7e82d210797808b6f11"

# Control flags (prod)
TEST_MODE = False
FORCE_POST = False      # leave False so the time gate filters duplicate cron runs
FORCE_WEEK = None       # use the live/current week in-season

# ----------------------------
# Timezone & schedule
# ----------------------------
EASTERN = pytz.timezone("US/Eastern")
TOLERANCE_MINUTES = 2

SUNDAY_TIMES = [time(10, 0), time(16, 0), time(20, 0), time(23, 30)]
MONDAY_TIMES = [time(21, 30), time(22, 30), time(23, 59)]
THURSDAY_TIMES = [time(23, 59)]

# ----------------------------
# Helper functions
# ----------------------------
def within_post_window(now_eastern: datetime) -> bool:
    if TEST_MODE:
        return True

    # If you ever want "force means always post", uncomment the next line:
    # if FORCE_POST: return True

    weekday = now_eastern.weekday()  # Mon=0 ... Sun=6
    current_time = now_eastern.time()

    if weekday == 6:      # Sunday
        scheduled_times = SUNDAY_TIMES
    elif weekday == 0:    # Monday
        scheduled_times = MONDAY_TIMES
    elif weekday == 3:    # Thursday
        scheduled_times = THURSDAY_TIMES
    else:
        return False

    for sched in scheduled_times:
        lower_dt = datetime.combine(now_eastern.date(), sched) - timedelta(minutes=TOLERANCE_MINUTES)
        upper_dt = datetime.combine(now_eastern.date(), sched) + timedelta(minutes=TOLERANCE_MINUTES)
        if lower_dt.time() <= current_time <= upper_dt.time():
            return True
    return False

def post_to_groupme(text: str):
    url = "https://api.groupme.com/v3/bots/post"
    payload = {"bot_id": GROUPME_BOT_ID, "text": text}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()

def fetch_scores(league: League, projected: bool = False):
    """Get either current or projected scores using BoxScore objects (supports projections)."""
    week = FORCE_WEEK if FORCE_WEEK is not None else league.current_week
    if not week:
        return []

    team_scores = []
    for b in league.box_scores(week=week):
        if projected:
            h = float(b.home_projected or 0.0)
            a = float(b.away_projected or 0.0)
        else:
            h = float(b.home_score or 0.0)
            a = float(b.away_score or 0.0)

        team_scores.append((b.home_team.team_name, h))
        team_scores.append((b.away_team.team_name, a))

    return team_scores

def format_scores(team_scores):
    if not team_scores:
        return 0, "No matchups found."

    scores_only = [s for _, s in team_scores]
    median_score = statistics.median(scores_only)
    team_scores.sort(key=lambda x: x[1], reverse=True)

    lines = []
    for name, score in team_scores:
        mark = "✅" if score >= median_score else "❌"
        lines.append(f"{name}: {score:.1f} {mark}")
    return median_score, "\n".join(lines)

def build_message() -> str:
    league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)

    current_scores = fetch_scores(league, projected=False)
    current_median, current_text = format_scores(current_scores)

    projected_scores = fetch_scores(league, projected=True)
    projected_median, projected_text = format_scores(projected_scores)

    week = FORCE_WEEK if FORCE_WEEK is not None else league.current_week
    now_eastern_str = datetime.now(EASTERN).strftime("%a %I:%M %p %Z")

    return (
        f"📊 Fantasy Scores — Week {week} — {now_eastern_str}\n\n"
        f"🏈 Current Scores (Median: {current_median:.1f})\n"
        f"{current_text}\n\n"
        f"🔮 Projected Scores (Median: {projected_median:.1f})\n"
        f"{projected_text}"
    )

# ----------------------------
# Main bot
# ----------------------------
def main():
    now_eastern = datetime.now(EASTERN)
    if not within_post_window(now_eastern):
        print("Outside posting window. Exiting.")
        return

    try:
        msg = build_message()
        if TEST_MODE:
            print("=== Test Mode ===")
            print(msg)
        else:
            post_to_groupme(msg)
            print("Message posted successfully.")
    except Exception as e:
        print(f"Bot error: {e}")
        if not TEST_MODE:
            try:
                post_to_groupme(f"Bot error: {e}")
            except Exception:
                pass

if __name__ == "__main__":
    main()
