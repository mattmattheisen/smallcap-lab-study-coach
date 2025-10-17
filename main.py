import streamlit as st
import json, os, random, time, io, csv, re
from pathlib import Path
from datetime import datetime, date

st.set_page_config(page_title="Small-Cap Lab Study Coach", layout="wide")

# ----- Paths -----
DATA_DIR = Path("data")
PROGRESS_DIR = Path("progress")
PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
SCORES_FILE = PROGRESS_DIR / "scores.json"
LEITNER_FILE = PROGRESS_DIR / "leitner.json"   # per-question proficiency

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
    return {"history": [], "events": []}

def save_scores(data):
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_leitner():
    if LEITNER_FILE.exists():
        return load_json(LEITNER_FILE)
    return {"boxes": {}}  # key -> box (1..5)

def save_leitner(data):
    with open(LEITNER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ---------- Helpers ----------
def q_key(day_num: int, q_text: str):
    """Stable key for a question, per day."""
    return f"d{day_num}::{abs(hash(q_text)) % 10_000_000}"

def box_of(leitner, key):
    return int(leitner["boxes"].get(key, 1))

def promote(leitner, key):
    leitner["boxes"][key] = min(box_of(leitner, key) + 1, 5)

def demote(leitner, key):
    leitner["boxes"][key] = 1

def simple_simplify(text: str):
    """Very simple 'presentation mode' simplifier: shorter, plain words, one sentence."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"\([^)]*\)", "", t)  # drop parentheticals
    t = re.sub(r"\bposterior probabilities\b", "model odds", t, flags=re.I)
    t = re.sub(r"\btransition\b", "shift", t, flags=re.I)
    t = re.sub(r"\bconfidence\b", "certainty", t, flags=re.I)
    t = re.sub(r"\bregime\b", "market mode", t, flags=re.I)
    t = re.sub(r"\bKelly\b", "sizing rule", t, flags=re.I)
    # keep only first sentence if too long
    parts = re.split(r"(?<=[.!?])\s+", t)
    return parts[0][:240]

def default_hint(q):
    """Generate a hint if JSON lacks 'hint'."""
    if q["type"] == "numeric":
        return "Hint: write the formula first; keep units consistent; consider rounding."
    if q["type"] == "mcq":
        return "Hint: eliminate clearly wrong choices; focus on what the model actually estimates."
    return "Think of how you’d explain this to a client in one sentence."

def sample_repeats(current_day: int, k: int, leitner):
    """Pick repeats across earlier days, weighted by Leitner box (harder items more likely)."""
    if current_day <= 1 or k == 0:
        return []
    pool = []
    for d in range(1, current_day):
        _, fname = DAYS[d]
        qset = safe_load(DATA_DIR / fname).get("questions", [])
        for q in qset:
            if q.get("type") in ("mcq", "numeric"):
                key = q_key(d, q["question"])
                b = box_of(leitner, key)  # 1..5
                weight = {1: 8, 2: 5, 3: 3, 4: 2, 5: 1}[b]
                q_copy = dict(q)
                q_copy["_source_day"] = d
                q_copy["_key"] = key
                pool.extend([q_copy] * weight)
    if not pool:
        return []
    random.shuffle(pool)
    chosen = []
    # avoid duplicates by question key
    seen = set()
    for q in pool:
        if q["_key"] not in seen:
            chosen.append(q)
            seen.add(q["_key"])
        if len(chosen) >= k:
            break
    return chosen

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
st.caption("Presentation Mode, Hints, and Adaptive Repeats now live.")

scores = load_scores()
leitner = load_leitner()

# Sidebar controls
day = st.sidebar.selectbox("Choose Day", options=list(DAYS.keys()),
                           format_func=lambda d: f"Day {d}: {DAYS[d][0]}")
reps = st.sidebar.slider("Review questions (spaced repetition)", 0, 6, 3)
new_q = st.sidebar.slider("New questions today", 3, 12, 6)
daily_goal = st.sidebar.number_input("Daily goal (questions)", min_value=3, max_value=30, value=8)
presentation_mode = st.sidebar.toggle("🎯 Presentation Mode (client-friendly)")
start_clicked = st.sidebar.button("Start / Restart Session", use_container_width=True)

# Mastery dashboard (top-right)
with st.sidebar.expander("📊 Mastery, Streak & Export", expanded=False):
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

    # streak
    dates = [h["ts"][:10] for h in scores.get("history", [])]
    streak = 0
    if dates:
        unique = sorted(set(dates), reverse=True)
        current = date.fromisoformat(unique[0])
        today = date.today()
        if current == today:
            streak = 1
            dptr = today
            sset = set(date.fromisoformat(x) for x in unique)
            while (dptr := dptr.fromordinal(dptr.toordinal()-1)) in sset:
                streak += 1
        else:
            streak = 1
            dptr = current
            sset = set(date.fromisoformat(x) for x in unique)
            while (dptr := dptr.fromordinal(dptr.toordinal()-1)) in sset:
                streak += 1
    st.write(f"🔥 Streak: {streak} day(s)")

    # export
    csv_bytes = export_csv(scores)
    st.download_button("⬇️ Export results (CSV)", data=csv_bytes, file_name="study_coach_results.csv", mime="text/csv")

# Load current day file (title)
_, fname = DAYS[day]
quiz = safe_load(DATA_DIR / fname)
st.header(quiz.get("title", f"Day {day}"))

# Start or reset session
if start_clicked:
    # assemble new + repeats with Leitner weighting
    q_new = quiz.get("questions", [])[:]
    # tag source for analytics & Leitner
    temp = []
    for q in q_new:
        qc = dict(q)
        qc["_source_day"] = day
        qc["_key"] = q_key(day, q["question"])
        temp.append(qc)
    q_new = temp
    random.shuffle(q_new)
    q_new = q_new[:new_q]
    q_rep = sample_repeats(day, reps, leitner)
    Q = q_rep + q_new
    random.shuffle(Q)
    st.session_state.started = True
    reset_session(Q)

if "started" not in st.session_state:
    st.session_state.started = False

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

if not st.session_state.started:
    st.info("Click **Start / Restart Session** in the sidebar to begin today’s quiz.")
else:
    Q = st.session_state.questions
    i = st.session_state.idx
    total = len(Q)
    st.progress(i / max(1, total))
    st.caption(f"Question {i+1} of {total} • Score: {st.session_state.correct}/{st.session_state.answered} • Goal: {daily_goal}")

    if i < total:
        q = Q[i]
        q_day = q.get("_source_day", day)
        q_title = quiz.get("title", f"Day {q_day}")
        key = q.get("_key", q_key(q_day, q["question"]))

        st.subheader(q["question"])
        # Hints
        hint_text = q.get("hint") or default_hint(q)
        with st.expander("💡 Need a hint?", expanded=False):
            st.write(hint_text)

        fb = st.empty()

        if q["type"] == "mcq":
            choice = st.radio("Select an answer:", q["options"], key=f"mcq_{i}")
            if st.button("Check", key=f"btn_{i}"):
                st.session_state.answered += 1
                expected = q["options"][q["answer"]]
                correct = (choice == expected)
                # Presentation Mode: simplify explanation text
                expl = q.get("explanation", "")
                if presentation_mode:
                    expl = simple_simplify(expl)
                if correct:
                    st.session_state.correct += 1
                    fb.success("✅ Correct! " + expl)
                    promote(leitner, key)
                else:
                    fb.error("❌ Incorrect. " + expl)
                    demote(leitner, key)
                save_leitner(leitner)
                log_event(q_day, i, "mcq", correct, choice, expected, q_title)
                time.sleep(0.4)
                st.session_state.idx += 1

        elif q["type"] == "numeric":
            val = st.number_input("Enter your answer (decimals ok):", key=f"num_{i}")
            tol = q.get("tolerance", 0.01)
            if st.button("Check", key=f"btn_{i}"):
                st.session_state.answered += 1
                correct = abs(val - q["answer"]) <= tol
                expl = q.get("explanation", "")
                if presentation_mode:
                    expl = simple_simplify(expl)
                if correct:
                    st.session_state.correct += 1
                    fb.success(f"✅ Correct! {expl}")
                    promote(leitner, key)
                else:
                    fb.error(f"❌ Incorrect. Expected ≈ {q['answer']} (±{tol}). {expl}")
                    demote(leitner, key)
                save_leitner(leitner)
                log_event(q_day, i, "numeric", correct, float(val), q["answer"], q_title)
                time.sleep(0.4)
                st.session_state.idx += 1

        elif q["type"] == "repeat":
            st.info(q.get("answer_text", "Review item"))
            if st.button("Next", key=f"btn_{i}"):
                # repeats don't affect Leitner boxes
                log_event(q_day, i, "repeat", True, "", "", q_title)
                st.session_state.idx += 1
    else:
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
