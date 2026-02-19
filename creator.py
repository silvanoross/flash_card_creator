import streamlit as st
import json
import base64
import os
import random
from pathlib import Path

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="FlashCard Studio", page_icon="🃏", layout="wide")

DATA_FILE = "flashcard_data.json"
IMAGES_DIR = "flashcard_images"
os.makedirs(IMAGES_DIR, exist_ok=True)

# ── Persistence ───────────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def save_image(uploaded_file):
    """Save uploaded image and return its path."""
    img_path = os.path.join(IMAGES_DIR, uploaded_file.name)
    with open(img_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return img_path

def img_to_b64(path):
    """Convert image file to base64 string for embedding."""
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            ext = Path(path).suffix.lower().lstrip(".")
            mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
            return f"data:image/{mime};base64,{base64.b64encode(f.read()).decode()}"
    return None

# ── Session state init ────────────────────────────────────────────────────────
if "data" not in st.session_state:
    st.session_state.data = load_data()
if "mode" not in st.session_state:
    st.session_state.mode = "manage"   # "manage" | "study"
if "study_state" not in st.session_state:
    st.session_state.study_state = {}

data = st.session_state.data

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2.4rem; font-weight: 800; color: #4F46E5;
        margin-bottom: 0.2rem;
    }
    .card-front {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px; padding: 2rem; color: white;
        font-size: 1.3rem; font-weight: 600; text-align: center;
        min-height: 180px; display: flex; align-items: center;
        justify-content: center; box-shadow: 0 8px 32px rgba(79,70,229,0.3);
        margin-bottom: 1rem;
    }
    .card-back {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        border-radius: 16px; padding: 2rem; color: white;
        font-size: 1.1rem; text-align: center;
        min-height: 180px; display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        box-shadow: 0 8px 32px rgba(245,87,108,0.3);
        margin-bottom: 1rem;
    }
    .card-back img { max-width: 100%; max-height: 260px; border-radius: 10px; margin-top: 1rem; }
    .progress-bar { background: #E5E7EB; border-radius: 8px; height: 12px; }
    .progress-fill { background: #4F46E5; border-radius: 8px; height: 12px; }
    .badge {
        display: inline-block; background: #EEF2FF; color: #4F46E5;
        border-radius: 20px; padding: 2px 12px; font-size: 0.8rem;
        font-weight: 600; margin: 2px;
    }
    .section-header {
        font-size: 1.1rem; font-weight: 700; color: #374151;
        border-left: 4px solid #4F46E5; padding-left: 10px;
        margin: 1.2rem 0 0.6rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">🃏 FlashCard Studio</div>', unsafe_allow_html=True)
st.markdown("Create classes, topics, and flashcards — then study them with ease.")
st.divider()

# ── Mode toggle ───────────────────────────────────────────────────────────────
col_m1, col_m2, col_m3 = st.columns([1, 1, 4])
with col_m1:
    if st.button("📚 Manage Cards", use_container_width=True,
                 type="primary" if st.session_state.mode == "manage" else "secondary"):
        st.session_state.mode = "manage"
        st.rerun()
with col_m2:
    if st.button("🧠 Study Mode", use_container_width=True,
                 type="primary" if st.session_state.mode == "study" else "secondary"):
        st.session_state.mode = "study"
        st.rerun()

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# MANAGE MODE
# ═════════════════════════════════════════════════════════════════════════════
if st.session_state.mode == "manage":

    left, right = st.columns([1, 2], gap="large")

    # ── LEFT: Class + Topic tree ──────────────────────────────────────────────
    with left:
        st.markdown('<div class="section-header">Classes</div>', unsafe_allow_html=True)

        # Add new class
        with st.expander("➕ Add New Class"):
            new_class = st.text_input("Class name", key="new_class_input")
            if st.button("Create Class", key="create_class"):
                if new_class.strip():
                    if new_class.strip() not in data:
                        data[new_class.strip()] = {}
                        save_data(data)
                        st.success(f"Class '{new_class.strip()}' created!")
                        st.rerun()
                    else:
                        st.warning("Class already exists.")

        if not data:
            st.info("No classes yet. Add one above!")
        else:
            selected_class = st.selectbox("Select a class", list(data.keys()), key="sel_class")

            if selected_class:
                st.markdown(f"**Topics in {selected_class}**")

                # Add topic
                with st.expander("➕ Add Topic"):
                    new_topic = st.text_input("Topic name", key="new_topic_input")
                    if st.button("Create Topic", key="create_topic"):
                        if new_topic.strip():
                            if new_topic.strip() not in data[selected_class]:
                                data[selected_class][new_topic.strip()] = []
                                save_data(data)
                                st.success(f"Topic '{new_topic.strip()}' added!")
                                st.rerun()
                            else:
                                st.warning("Topic already exists.")

                if not data[selected_class]:
                    st.info("No topics yet.")
                else:
                    selected_topic = st.selectbox("Select a topic", list(data[selected_class].keys()), key="sel_topic")

                    if selected_topic:
                        cards = data[selected_class][selected_topic]
                        n = len(cards)
                        st.markdown(f'<span class="badge">{n} card{"s" if n != 1 else ""}</span>', unsafe_allow_html=True)

                # Danger zone
                with st.expander("🗑️ Delete"):
                    if st.button(f"Delete class '{selected_class}'", type="secondary"):
                        del data[selected_class]
                        save_data(data)
                        st.rerun()

    # ── RIGHT: Card editor ────────────────────────────────────────────────────
    with right:
        if not data:
            st.info("👈 Create a class to get started.")
        else:
            selected_class = st.session_state.get("sel_class")
            selected_topic = st.session_state.get("sel_topic")

            if selected_class and selected_topic and selected_topic in data.get(selected_class, {}):
                cards = data[selected_class][selected_topic]

                st.markdown(f'<div class="section-header">Cards — {selected_class} › {selected_topic}</div>', unsafe_allow_html=True)

                # ── Add new card form ─────────────────────────────────────────
                with st.expander("➕ Add New Flashcard", expanded=len(cards) == 0):
                    q = st.text_area("❓ Question (front)", key="new_q", height=100,
                                     placeholder="Type your question here...")

                    st.markdown("**✏️ Answer (back)**")
                    a_text = st.text_area("Answer text", key="new_a_text", height=100,
                                          placeholder="Type the answer here...")

                    st.markdown("**🖼️ Answer image** (optional — paste, drag-drop, or browse)")
                    a_img = st.file_uploader("Upload image for answer",
                                             type=["png", "jpg", "jpeg", "gif", "webp"],
                                             key="new_a_img",
                                             label_visibility="collapsed")

                    if a_img:
                        st.image(a_img, caption="Preview", width=300)

                    if st.button("💾 Save Card", type="primary", key="save_card"):
                        if q.strip():
                            img_path = save_image(a_img) if a_img else None
                            card = {
                                "question": q.strip(),
                                "answer_text": a_text.strip(),
                                "answer_image": img_path,
                            }
                            data[selected_class][selected_topic].append(card)
                            save_data(data)
                            st.success("Card saved!")
                            st.rerun()
                        else:
                            st.warning("Please enter a question.")

                # ── Existing cards ────────────────────────────────────────────
                if cards:
                    st.markdown(f"**{len(cards)} card(s) in this topic:**")
                    for i, card in enumerate(cards):
                        with st.expander(f"Card {i+1}: {card['question'][:60]}{'...' if len(card['question']) > 60 else ''}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("**Front (Question)**")
                                st.info(card["question"])
                            with col2:
                                st.markdown("**Back (Answer)**")
                                if card.get("answer_text"):
                                    st.success(card["answer_text"])
                                if card.get("answer_image"):
                                    b64 = img_to_b64(card["answer_image"])
                                    if b64:
                                        st.image(card["answer_image"], width=200)
                                    else:
                                        st.caption("_(image file not found)_")

                            # Edit card
                            with st.form(key=f"edit_form_{i}"):
                                st.markdown("**Edit this card:**")
                                eq = st.text_area("Question", value=card["question"], key=f"eq_{i}")
                                ea = st.text_area("Answer text", value=card.get("answer_text", ""), key=f"ea_{i}")
                                new_img = st.file_uploader("Replace image (optional)",
                                                           type=["png","jpg","jpeg","gif","webp"],
                                                           key=f"eimg_{i}")
                                col_save, col_del = st.columns(2)
                                with col_save:
                                    if st.form_submit_button("💾 Update"):
                                        data[selected_class][selected_topic][i]["question"] = eq.strip()
                                        data[selected_class][selected_topic][i]["answer_text"] = ea.strip()
                                        if new_img:
                                            data[selected_class][selected_topic][i]["answer_image"] = save_image(new_img)
                                        save_data(data)
                                        st.success("Updated!")
                                        st.rerun()
                                with col_del:
                                    if st.form_submit_button("🗑️ Delete Card"):
                                        data[selected_class][selected_topic].pop(i)
                                        save_data(data)
                                        st.rerun()
            else:
                st.info("👈 Select a class and topic, then add flashcards.")

# ═════════════════════════════════════════════════════════════════════════════
# STUDY MODE
# ═════════════════════════════════════════════════════════════════════════════
else:
    if not data:
        st.info("No classes yet. Switch to Manage Cards to create some!")
    else:
        ss = st.session_state.study_state

        # ── Study setup ───────────────────────────────────────────────────────
        st.markdown('<div class="section-header">Study Session Setup</div>', unsafe_allow_html=True)
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            study_class = st.selectbox("Class", list(data.keys()), key="study_class")
        with col_s2:
            topics_in_class = list(data.get(study_class, {}).keys())
            topic_options = ["All Topics"] + topics_in_class
            study_topic = st.selectbox("Topic", topic_options, key="study_topic")
        with col_s3:
            shuffle = st.checkbox("Shuffle cards", value=True)

        # Gather cards
        if study_topic == "All Topics":
            all_cards = []
            for t, cards in data[study_class].items():
                for c in cards:
                    all_cards.append({**c, "_topic": t})
        else:
            all_cards = [{**c, "_topic": study_topic} for c in data[study_class].get(study_topic, [])]

        if not all_cards:
            st.warning("No cards found for this selection.")
        else:
            if st.button("▶️ Start / Restart Session", type="primary"):
                deck = all_cards.copy()
                if shuffle:
                    random.shuffle(deck)
                ss["deck"] = deck
                ss["index"] = 0
                ss["show_answer"] = False
                ss["correct"] = 0
                ss["incorrect"] = 0
                st.rerun()

            # ── Active study session ──────────────────────────────────────────
            if ss.get("deck"):
                deck = ss["deck"]
                idx = ss["index"]
                total = len(deck)

                if idx >= total:
                    # Session complete
                    st.balloons()
                    st.markdown("## 🎉 Session Complete!")
                    c = ss.get("correct", 0)
                    w = ss.get("incorrect", 0)
                    pct = round(c / (c + w) * 100) if (c + w) > 0 else 0
                    st.markdown(f"**Score: {c}/{c+w} correct ({pct}%)**")
                    if pct >= 80:
                        st.success("Great job! You're mastering this material! 🌟")
                    elif pct >= 60:
                        st.info("Good effort! Keep practicing the ones you missed.")
                    else:
                        st.warning("Keep going! Repetition is key to learning.")
                    if st.button("🔄 Study Again"):
                        ss.clear()
                        st.rerun()
                else:
                    card = deck[idx]

                    # Progress
                    progress = idx / total
                    st.markdown(f"**Card {idx+1} of {total}** — Topic: *{card.get('_topic', '')}*")
                    st.markdown(f"""
                    <div class="progress-bar">
                        <div class="progress-fill" style="width:{progress*100:.1f}%"></div>
                    </div>
                    """, unsafe_allow_html=True)

                    score_col1, score_col2, _ = st.columns([1,1,4])
                    with score_col1:
                        st.markdown(f'✅ **{ss.get("correct",0)}** correct')
                    with score_col2:
                        st.markdown(f'❌ **{ss.get("incorrect",0)}** incorrect')

                    st.markdown("<br>", unsafe_allow_html=True)

                    # Card front
                    st.markdown(f'<div class="card-front">{card["question"]}</div>', unsafe_allow_html=True)

                    if not ss.get("show_answer"):
                        if st.button("👁️ Show Answer", type="primary", use_container_width=True):
                            ss["show_answer"] = True
                            st.rerun()
                    else:
                        # Card back
                        answer_text = card.get("answer_text", "")
                        img_html = ""
                        if card.get("answer_image"):
                            b64 = img_to_b64(card["answer_image"])
                            if b64:
                                img_html = f'<img src="{b64}" />'

                        st.markdown(f"""
                        <div class="card-back">
                            <div>{answer_text}</div>
                            {img_html}
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown("**How did you do?**")
                        col_y, col_n = st.columns(2)
                        with col_y:
                            if st.button("✅ Got it!", type="primary", use_container_width=True):
                                ss["correct"] = ss.get("correct", 0) + 1
                                ss["index"] = idx + 1
                                ss["show_answer"] = False
                                st.rerun()
                        with col_n:
                            if st.button("❌ Missed it", use_container_width=True):
                                ss["incorrect"] = ss.get("incorrect", 0) + 1
                                ss["index"] = idx + 1
                                ss["show_answer"] = False
                                st.rerun()

                        st.markdown("---")
                        if st.button("⏭️ Skip (don't count)"):
                            ss["index"] = idx + 1
                            ss["show_answer"] = False
                            st.rerun()