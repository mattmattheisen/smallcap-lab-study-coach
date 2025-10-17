import streamlit as st
import json, os, random, time
from pathlib import Path
from datetime import datetime

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

# ----- Helpers -----
def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def safe_load(path: Path):
    if not path.exists():
        # minimal placeholder to avoid crashes
        return {"title": path.stem, "questions": [
            {"type": "repeat",
             "question": "Placeholder day — review a concept you found tricky yesterday.",
             "answer_text": "Use this slot to articulate the concept in your own words."}
        ]}
    return load_json(path)

def save_scores(scores):
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2)

def load_scores():
    if SCORES_FILE.exists():
        return load_json(SCORES_FILE)
    return {"history": []}

def sample_repeats(current_day: int, k: int):
    if current_day <= 1 or k == 0:
        return []
    candidates = []
    for d in range(1, current_day):
        _, fname = DAYS[d]
        qset = safe_load(DATA_DIR / fname).get("questions", [])
        # prefer mcq/numeric for active recall
        pool = [q for q in qset if q.get("type") in ("mcq", "numeric")] or qset
        if pool:
            candidates.append(random.choice(pool))
    random.shuffle(candidates)
    return candidates[:k]

def reset_session(questions):
    st.session_state.started = True
    st.session_state.questions = questions
    st.session_state.idx = 0
    st.session_state.correct = 0
    st.session_state.answered = 0

def end_session(day):
    st.session_state.started = False
    scores = load_scores()
    scores["history"].append({
        "ts": datetime.utcnow().isoformat() + "Z",
        "day": day,
        "correct": st.session_state.correct,
        "total": st.session_state.answered
    })
    save_scores(scores)
    st.balloons()
    pct = (100 * st.session_state.correct / max(1, st.session_state.answered))
    st.success(f"Session complete — Score: {st.session_state.correct}/{st.session_state.answered} ({pct:.0f}%)")

# ----- UI -----
st.title("Small-Cap Lab Study Coach")
st.caption("Learn the logic and math behind your Small-Cap Lab with daily quizzes and spaced repetition.")

# Day selector
day = st.sidebar.selectbox("Choose Day", options=list(DAYS.keys()),
                           format_func=lambda d: f"Day {d}: {DAYS[d][0]}")

# Session controls
reps = st.sidebar.slider("Review questions (spaced repetition)", 0, 5, 2)
new_q = st.sidebar.slider("New questions today", 3, 10, 6)
if st.sidebar.button("Start / Restart Session", use_container_width=True):
    # load current day
    _, fname = DAYS[day]
    quiz = safe_load(DATA_DIR / fname)
    q_new = quiz.get("questions", [])[:]
    random.shuffle(q_new)
    q_new = q_new[:new_q]
    # sample repeats from earlier days
    q_rep = sample_repeats(day, reps)
    Q = q_rep + q_new
    random.shuffle(Q)
    reset_session(Q)

# initialize
if "started" not in st.session_state:
    st.session_state.started = False

# render
_, fname = DAYS[day]
quiz = safe_load(DATA_DIR / fname)

st.header(quiz.get("title", f"Day {day}"))
if not st.session_state.started:
    st.info("Click **Start / Restart Session** in the sidebar to begin today’s quiz.")
else:
    Q = st.session_state.questions
    i = st.session_state.idx
    total = len(Q)
    st.progress(i / max(1, total))
    st.caption(f"Question {i+1} of {total} • Score: {st.session_state.correct}/{st.session_state.answered}")

    if i < total:
        q = Q[i]
        st.subheader(q["question"])
        fb = st.empty()

        if q["type"] == "mcq":
            choice = st.radio("Select an answer:", q["options"], key=f"mcq_{i}")
            if st.button("Check", key=f"btn_{i}"):
                st.session_state.answered += 1
                correct_text = q["options"][q["answer"]]
                if choice == correct_text:
                    st.session_state.correct += 1
                    fb.success("✅ Correct! " + q.get("explanation",""))
                else:
                    fb.error("❌ Incorrect. " + q.get("explanation",""))
                time.sleep(0.4)
                st.session_state.idx += 1

        elif q["type"] == "numeric":
            val = st.number_input("Enter your answer (decimals ok):", key=f"num_{i}")
            tol = q.get("tolerance", 0.01)
            if st.button("Check", key=f"btn_{i}"):
                st.session_state.answered += 1
                if abs(val - q["answer"]) <= tol:
                    st.session_state.correct += 1
                    fb.success("✅ Correct! " + q.get("explanation",""))
                else:
                    fb.error(f"❌ Incorrect. Expected ≈ {q['answer']} (±{tol}). " + q.get("explanation",""))
                time.sleep(0.4)
                st.session_state.idx += 1

        elif q["type"] == "repeat":
            st.info(q.get("answer_text", "Review item"))
            if st.button("Next", key=f"btn_{i}"):
                st.session_state.idx += 1

    else:
        end_session(day)

# history
scores = load_scores()
if scores["history"]:
    st.divider()
    st.markdown("### Recent Sessions")
    for item in reversed(scores["history"][-5:]):
        st.write(f"- {item['ts']} — Day {item['day']} — {item['correct']}/{item['total']}")
