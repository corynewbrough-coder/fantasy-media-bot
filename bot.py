import os
import time
import statistics
import traceback
from datetime import datetime
import pytz
import requests
from espn_api.football import League

# ----------------------------
# Config (use secrets for sensitive values)
# ----------------------------
LEAGUE_ID = 2075760555
YEAR = 2025

def require_secret(name: str) -> str:
    v = os.getenv(name)
    if not v or not v.strip():
        raise RuntimeError(
            f"Missing required secret: {name}. "
            f"Set it in GitHub → Settings → Secrets and variables → Actions, "
            f"and pass it into the workflow env."
        )
    return v.strip()

# Expect these **exact** env var names
SWID = require_secret("ESPN_SWID")           # keep the {...} braces
ESPN_S2 = require_secret("ESPN_S2")
GROUPME_BOT_ID = require_secret("GROUPME_BOT_ID")

TEST_MODE = False
FORCE_WEEK = None

EASTERN = pytz.timezone("US/Eastern")

# ----------------------------
# Helpers
# ----------------------------
def _mask(s: str, show=6) -> str:
    if not s:
        return "<empty>"
    return s[:show] + "…" if len(s) > show else s

def post_to_groupme(text: str, retries: int = 2, backoff: float = 1.5):
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
    week = FORCE_WEEK if FORCE_WEEK is not None else getattr(league, "current_week", None)
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

        home_name = getattr(b.home_team, "team_name", "Home")
        away_name = getattr(b.away_team, "team_name", "Away")

        team_scores.append((home_name, h))
        team_scores.append((away_name, a))

    return week, team_scores

def format_current_scores(team_scores):
    if not team_scores:
        return 0.0, "No matchups found."

    scores = [s for _, s in team_scores]
    zero_count = sum(1 for s in scores if s == 0)
    total = len(scores)
    zero_heavy = zero_count >= 6 or zero_count >= total / 2

    team_scores_sorted = sorted(team_scores, key=lambda x: x[1], reverse=True)

    if zero_heavy:
        median_score = 0.0
        lines = [f"{n}: {s:.1f} {'✅' if s > 0 else '❌'}" for n, s in team_scores_sorted]
        return median_score, "\n".join(lines)
    else:
        non_zero = [s for s in scores if s > 0]
        usable = non_zero if non_zero else scores
        median_score = statistics.median(usable)

        lines = []
        for name, score in team_scores_sorted:
            mark = "✅" if (score >= median_score and (median_score == 0 or score > 0)) else "❌"
            lines.append(f"{name}: {score:.1f} {mark}")
        return median_score, "\n".join(lines)

def format_projected_scores(team_scores):
    if not team_scores:
        return 0.0, "No matchups found."
    scores_only = [s for _, s in team_scores]
    median_score = statistics.median(scores_only)
    team_scores_sorted = sorted(team_scores, key=lambda x: x[1], reverse=True)
    lines = [f"{n}: {s:.1f} {'✅' if s >= median_score else '❌'}" for n, s in team_scores_sorted]
    return median_score, "\n".join(lines)

def build_message() -> str:
    try:
        league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)
        week_cur, current_scores = fetch_scores(league, projected=False)
        week_proj, projected_scores = fetch_scores(league, projected=True)
    except Exception as e:
        raise RuntimeError(
            "Failed to load ESPN league data. Likely causes: invalid/missing ESPN_S2/ESPN_SWID, "
            "expired cookies, wrong LEAGUE_ID/YEAR, or ESPN API change."
        ) from e

    week = week_cur or week_proj
    now_eastern_str = datetime.now(EASTERN).strftime("%a %I:%M %p %Z")
    if not week:
        return f"📊 Fantasy Scores — {now_eastern_str}\n\nNo active week yet."

    current_median, current_text = format_current_scores(current_scores)
    projected_median, projected_text = format_projected_scores(projected_scores)

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
        f"BotID={_mask(GROUPME_BOT_ID)}  League={LEAGUE_ID}  Year={YEAR}  TEST_MODE={TEST_MODE}  "
        f"Secrets: SWID={_mask(SWID)} ESPN_S2={_mask(ESPN_S2)}"
    )

    try:
        msg = build_message()
        if TEST_MODE:
            print("=== Test Mode ===\n" + msg)
        else:
            post_to_groupme(msg)
            print("Message posted successfully.")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"Bot error: {type(e).__name__}: {e}\n{tb}")
        if not TEST_MODE:
            try:
                post_to_groupme(f"Bot error: {e}\n(See GitHub Actions logs for details.)")
            except Exception as e2:
                print(f"Also failed to notify GroupMe: {e2}")

if __name__ == "__main__":
    main()
