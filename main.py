import streamlit as st
import json, os, random, time, io, csv
from pathlib import Path
from datetime import datetime, date

st.set_page_config(page_title="Small-Cap Lab Study Coach", layout="wide")

# ----- Paths -----
DATA_DIR = Path("data")
PROGRESS_DIR = Path("progress")
PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
SCORES_FILE = PROGRESS_DIR / "scores.json"

# ----- 3-Phase, 21-Day plan -----
DAYS = {
    1: ("Screening & Filtering", "day01_screening.json"),
    2: ("Candlestick Patterns", "day02_candlesticks.json"),
    3: ("Hidden Markov Models (HMM)", "day03_hmm.json"),
    4: ("Confidence & Combined Strength", "day04_confidence.json"),
    5: ("Regime Analysis Table", "day05_regime.json"),
    6: ("Kelly Position Sizing", "day06_kelly.json"),
    7: ("Integration & Case Study (Week 1)", "day07_integration.json"),
    8: ("Transition Matrices & Stationary Probs", "day08_markov_math.json"),
    9: ("Distributions & Kurtosis by Regime", "day09_kurtosis.json"),
    10: ("Volatility Clustering & Short Bull Runs", "day10_vol_clustering.json"),
    11: ("Signal Aggregation & Weights", "day11_signal_weights.json"),
    12: ("Fractional Kelly & Risk Constraints", "day12_fractional_kelly.json"),
    13: ("Expected Value & Compounding Efficiency", "day13_ev_compounding.json"),
    14: ("SOFI Deep Walkthrough", "day14_sofi_case.json"),
    15: ("Client-Friendly Explanations", "day15_client_language.json"),
    16: ("Interpreting Live Regime Shifts", "day16_live_shifts.json"),
    17: ("Failure Modes: Noise, Fat Tails, Outliers", "day17_failure_modes.json"),
    18: ("Multi-Ticker Sizing & Portfolio Context", "day18_multi_ticker.json"),
    19: ("Backtest Discipline & Overfitting", "day19_backtesting.json"),
    20: ("Storytelling with Data", "day20_storytelling.json"),
    21: ("Final Synthesis & Mastery Check", "day21_synthesis.json"),
}

# ---------- Persistence ----------
def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def safe_load(path: Path):
    if not path.exists():
        return {"title": path.stem, "questions": [
            {"type": "repeat",
             "question": "Placeholder day — review a concept you found tricky yesterday.",
             "answer_text": "Use this slot to articulate the concept in your own words."}
        ]}
    return load_json(path)

def load_scores():
    if SCORES_FILE.exists():
        return load_json(SCORES_FILE)
    # structure includes per-question events to compute mastery
    return {"history": [], "events": []}

def save_scores(data):
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ---------- Utility ----------
def sample_repeats(current_day: int, k: int):
    if current_day <= 1 or k == 0:
        return []
    candidates = []
    for d in range(1, current_day):
        _, fname = DAYS[d]
        qset = safe_load(DATA_DIR / fname).get("questions", [])
        pool = [q for q in qset if q.get("type") in ("mcq", "numeric")] or qset
        if pool:
            q = random.choice(pool)
            # tag with source day for analytics
            q = dict(q)
            q["_source_day"] = d
            candidates.append(q)
    random.shuffle(candidates)
    return candidates[:k]

def reset_session(questions):
    st.session_state.started = True
    st.session_state.questions = questions
    st.session_state.idx = 0
    st.session_state.correct = 0
    st.session_state.answered = 0

def badge_from_pct(p):
    if p >= 0.85:
        return "🏅 Gold"
    if p >= 0.70:
        return "🥈 Silver"
    if p >= 0.50:
        return "🥉 Bronze"
    return "📚 Keep going"

def export_csv(scores):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp","day","q_index","type","correct","user_answer","expected","title"])
    for e in scores.get("events", []):
        writer.writerow([
            e.get("ts",""),
            e.get("day",""),
            e.get("q_idx",""),
            e.get("type",""),
            e.get("correct",""),
            e.get("user",""),
            e.get("expected",""),
            e.get("title",""),
        ])
    return buf.getvalue().encode("utf-8")

# ---------- UI ----------
st.title("Small-Cap Lab Study Coach")
st.caption("Daily quizzes with spaced repetition, mastery tracking, and exportable results.")

scores = load_scores()

# Sidebar controls
day = st.sidebar.selectbox("Choose Day", options=list(DAYS.keys()),
                           format_func=lambda d: f"Day {d}: {DAYS[d][0]}")
reps = st.sidebar.slider("Review questions (spaced repetition)", 0, 5, 2)
new_q = st.sidebar.slider("New questions today", 3, 10, 6)
daily_goal = st.sidebar.number_input("Daily goal (questions)", min_value=3, max_value=20, value=8)
start_clicked = st.sidebar.button("Start / Restart Session", use_container_width=True)

# Mastery dashboard (top-right)
with st.sidebar.expander("📊 Mastery & History", expanded=False):
    # per-day mastery
    per_day = {}
    for e in scores.get("events", []):
        d = e.get("day")
        per_day.setdefault(d, {"c":0,"t":0})
        per_day[d]["t"] += 1
        if e.get("correct"):
            per_day[d]["c"] += 1
    if per_day:
        for d in sorted(per_day):
            c,t = per_day[d]["c"], per_day[d]["t"]
            pct = c / t if t>0 else 0
            st.write(f"Day {d:02d}: {c}/{t}  →  {pct*100:0.0f}%  {badge_from_pct(pct)}")
    else:
        st.caption("No history yet — complete a session to see mastery.")

    # session streak (by calendar date)
    dates = [h["ts"][:10] for h in scores.get("history", [])]
    streak = 0
    if dates:
        unique = sorted(set(dates), reverse=True)
        current = date.fromisoformat(unique[0])
        today = date.today()
        # if you studied today, good; else streak counts until last day
        if current == today:
            streak = 1
            # walk backwards
            dptr = today
            sset = set(date.fromisoformat(x) for x in unique)
            while (dptr := dptr.fromordinal(dptr.toordinal()-1)) in sset:
                streak += 1
        else:
            # streak up to last study day
            streak = 1
            dptr = current
            sset = set(date.fromisoformat(x) for x in unique)
            while (dptr := dptr.fromordinal(dptr.toordinal()-1)) in sset:
                streak += 1
    st.write(f"🔥 Streak: {streak} day(s)")

    # export
    csv_bytes = export_csv(scores)
    st.download_button("⬇️ Export results (CSV)", data=csv_bytes, file_name="study_coach_results.csv", mime="text/csv")

# load current day quiz file (for title display)
_, fname = DAYS[day]
quiz = safe_load(DATA_DIR / fname)
st.header(quiz.get("title", f"Day {day}"))

# Start or reset session
if start_clicked:
    q_new = quiz.get("questions", [])[:]
    random.shuffle(q_new)
    q_new = q_new[:new_q]
    q_rep = sample_repeats(day, reps)
    Q = q_rep + q_new
    # tag current day on new questions for analytics
    for q in Q:
        q.setdefault("_source_day", day)
    random.shuffle(Q)
    reset_session(Q)

if "started" not in st.session_state:
    st.session_state.started = False

if not st.session_state.started:
    st.info("Click **Start / Restart Session** in the sidebar to begin today’s quiz.")
else:
    Q = st.session_state.questions
    i = st.session_state.idx
    total = len(Q)
    st.progress(i / max(1, total))
    st.caption(f"Question {i+1} of {total} • Score: {st.session_state.correct}/{st.session_state.answered} • Daily goal: {daily_goal}")

    def log_event(day_num, q_idx, qtype, correct, user, expected, title):
        evt = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "day": day_num,
            "q_idx": q_idx,
            "type": qtype,
            "correct": bool(correct),
            "user": user,
            "expected": expected,
            "title": title,
        }
        scores["events"].append(evt)
        save_scores(scores)

    if i < total:
        q = Q[i]
        st.subheader(q["question"])
        fb = st.empty()
        q_day = q.get("_source_day", day)
        q_title = quiz.get("title", f"Day {q_day}")

        if q["type"] == "mcq":
            choice = st.radio("Select an answer:", q["options"], key=f"mcq_{i}")
            if st.button("Check", key=f"btn_{i}"):
                st.session_state.answered += 1
                expected = q["options"][q["answer"]]
                correct = (choice == expected)
                if correct:
                    st.session_state.correct += 1
                    fb.success("✅ Correct! " + q.get("explanation",""))
                else:
                    fb.error("❌ Incorrect. " + q.get("explanation",""))
                log_event(q_day, i, "mcq", correct, choice, expected, q_title)
                time.sleep(0.4)
                st.session_state.idx += 1

        elif q["type"] == "numeric":
            val = st.number_input("Enter your answer (decimals ok):", key=f"num_{i}")
            tol = q.get("tolerance", 0.01)
            if st.button("Check", key=f"btn_{i}"):
                st.session_state.answered += 1
                correct = abs(val - q["answer"]) <= tol
                if correct:
                    st.session_state.correct += 1
                    fb.success("✅ Correct! " + q.get("explanation",""))
                else:
                    fb.error(f"❌ Incorrect. Expected ≈ {q['answer']} (±{tol}). " + q.get("explanation",""))
                log_event(q_day, i, "numeric", correct, float(val), q["answer"], q_title)
                time.sleep(0.4)
                st.session_state.idx += 1

        elif q["type"] == "repeat":
            st.info(q.get("answer_text", "Review item"))
            if st.button("Next", key=f"btn_{i}"):
                # log as neutral event (no score)
                log_event(q_day, i, "repeat", True, "", "", q_title)
                st.session_state.idx += 1
    else:
        # end of session
        st.session_state.started = False
        pct = (st.session_state.correct / max(1, st.session_state.answered))
        scores["history"].append({
            "ts": datetime.utcnow().isoformat() + "Z",
            "day": day,
            "correct": st.session_state.correct,
            "total": st.session_state.answered,
            "pct": pct
        })
        save_scores(scores)
        st.balloons()
        st.success(f"Session complete — Score: {st.session_state.correct}/{st.session_state.answered} "
                   f"({pct*100:.0f}%)  •  {badge_from_pct(pct)}")
        # Daily goal nudge
        if st.session_state.answered < daily_goal:
            remaining = daily_goal - st.session_state.answered
            st.warning(f"Daily goal not met: answer {remaining} more question(s) to hit your target today.")
        else:
            st.info("🎯 Daily goal achieved — nice work!")
