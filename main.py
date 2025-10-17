import streamlit as st
import json, random
from pathlib import Path

st.set_page_config(page_title="Small-Cap Lab Study Coach", layout="wide")

DATA_DIR = Path("data")

def load_quiz(day_file: str):
    with open(DATA_DIR / day_file, "r", encoding="utf-8") as f:
        return json.load(f)

st.title("Small-Cap Lab Study Coach")
st.caption("Daily quizzes with repetition to master your Small-Cap Lab.")

day_map = {
    "Day 1 — Screening & Filtering": "day1_screening.json"
}

day_label = st.sidebar.selectbox("Choose a Day", list(day_map.keys()))
quiz = load_quiz(day_map[day_label])

st.header(quiz["title"])
for i, q in enumerate(quiz["questions"], start=1):
    st.subheader(f"Q{i}. {q['question']}")
    if q["type"] == "mcq":
        choice = st.radio("Select an answer:", q["options"], key=f"q{i}")
        if st.button(f"Check Q{i}", key=f"btn{i}"):
            correct = q["options"][q["answer"]]
            if choice == correct:
                st.success(f"✅ Correct! {q.get('explanation','')}")
            else:
                st.error(f"❌ Incorrect. {q.get('explanation','')}")
    elif q["type"] == "numeric":
        val = st.number_input("Enter your answer (decimals allowed):", key=f"num{i}")
        if st.button(f"Check Q{i}", key=f"btn{i}"):
            tol = q.get("tolerance", 0.01)
            if abs(val - q["answer"]) <= tol:
                st.success(f"✅ Correct! {q.get('explanation','')}")
            else:
                st.error(f"❌ Incorrect. Expected ≈ {q['answer']} (±{tol}). {q.get('explanation','')}")
    elif q["type"] == "repeat":
        st.info(q.get("answer_text","Review item"))
        st.button("Next", key=f"next{i}")
