import os
import time
import statistics
import traceback
from datetime import datetime
import pytz
import requests
from espn_api.football import League

# ----------------------------
# Config (kept as literals, per your request)
# ----------------------------
LEAGUE_ID = 2075760555
YEAR = 2025
SWID = "{AFDF1C35-C3FF-4E8F-AD85-63D85CCE88ED}"
ESPN_S2 = "AECFFuqpnKkwgOlcCijqY71viRNLKIOsWVRu4cRQKbzfnIrJbf0jkAZ9x3csHAQz03U0D%2F9oCeXuchZVZa0M6Z4VQSYiFUwr7%2F5rrE1LZ6O6ySVeWsLC7xTsx%2FlDvw83DfRsffDlAaNdichxwCO2SY274IL0Cmlq68Ght9P8cekf4qid20hElhBWHC4KXdzVfPrh%2BX9tZIKqfxmtBtgC4Qf4m%2BueKsogUnTADTF672fbxy8G3LcurbepB1YLOehRokBXx9alTK3qS6b19hFlMOI5ch%2Bzaax2GIbYiitGkYDYXb%2B1Iatss9pwd1aSkt87XyI%3D"
GROUPME_BOT_ID = "b63cecb7e82d210797808b6f11"

# Optional controls
TEST_MODE = False          # If True, just print the message instead of posting
FORCE_WEEK = None          # Set an int to override ESPN current_week (for testing)

# ----------------------------
# Timezone (for display only)
# ----------------------------
EASTERN = pytz.timezone("US/Eastern")

# ----------------------------
# Helpers
# ----------------------------
def _mask(s: str, show=6) -> str:
    """Mask long tokens in logs."""
    if not s:
        return "<empty>"
    return s[:show] + "…" if len(s) > show else s

def post_to_groupme(text: str, retries: int = 2, backoff: float = 1.5):
    """Post a message to GroupMe with logging and tiny retry."""
    url = "https://api.groupme.com/v3/bots/post"
    payload = {"bot_id": GROUPME_BOT_ID, "text": text}

    attempt = 0
    while True:
        attempt += 1
        try:
            r = requests.post(url, json=payload, timeout=10)
            body_preview = (r.text or "")[:500]
            print(f"[GroupMe] attempt={attempt} status={r.status_code} body={body_preview!r}")
            r.raise_for_status()
            return
        except Exception as e:
            print(f"[GroupMe] attempt={attempt} error: {type(e).__name__}: {e}")
            if attempt > retries:
                raise
            time.sleep(backoff * attempt)

def fetch_scores(league: League, projected: bool = False):
    """Get current or projected team scores using BoxScore objects."""
    week = FORCE_WEEK if FORCE_WEEK is not None else league.current_week
    if not week:
        return week, []

    team_scores = []
    for b in league.box_scores(week=week):
        if projected:
            h = float(b.home_projected or 0.0)
            a = float(b.away_projected or 0.0)
        else:
            h = float(b.home_score or 0.0)
            a = float(b.away_score or 0.0)

        # Team names
        home_name = getattr(b.home_team, "team_name", "Home")
        away_name = getattr(b.away_team, "team_name", "Away")

        team_scores.append((home_name, h))
        team_scores.append((away_name, a))

    return week, team_scores

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

    week_cur, current_scores = fetch_scores(league, projected=False)
    week_proj, projected_scores = fetch_scores(league, projected=True)

    # Prefer whichever week we got (both should match)
    week = week_cur or week_proj
    if not week:
        now_eastern_str = datetime.now(EASTERN).strftime("%a %I:%M %p %Z")
        return f"📊 Fantasy Scores — {now_eastern_str}\n\nNo active week yet."

    current_median, current_text = format_scores(current_scores)
    projected_median, projected_text = format_scores(projected_scores)

    now_eastern_str = datetime.now(EASTERN).strftime("%a %I:%M %p %Z")

    return (
        f"📊 Fantasy Scores — Week {week} — {now_eastern_str}\n\n"
        f"🏈 Current Scores (Median: {current_median:.1f})\n"
        f"{current_text}\n\n"
        f"🔮 Projected Scores (Median: {projected_median:.1f})\n"
        f"{projected_text}"
    )

# ----------------------------
# Main
# ----------------------------
def main():
    now_et = datetime.now(EASTERN)
    print(
        f"Start (ET)={now_et:%Y-%m-%d %I:%M:%S %p %Z}  "
        f"BotID={_mask(GROUPME_BOT_ID)}  "
        f"League={LEAGUE_ID}  Year={YEAR}  TEST_MODE={TEST_MODE}"
    )

    try:
        msg = build_message()
        if TEST_MODE:
            print("=== Test Mode ===\n" + msg)
        else:
            post_to_groupme(msg)
            print("Message posted successfully.")
    except Exception as e:
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        print(f"Bot error: {err}")
        if not TEST_MODE:
            try:
                post_to_groupme(f"Bot error: {e}")
            except Exception as e2:
                print(f"Also failed to notify GroupMe: {e2}")

if __name__ == "__main__":
    main()
