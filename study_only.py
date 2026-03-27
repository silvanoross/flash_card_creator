"""
FlashCard Studio — Streamlit App
Image input methods for answers:
  1. Regular file uploader (browse)
  2. Drag-and-drop onto the paste zone
  3. Clipboard paste (Ctrl+V / Cmd+V) anywhere on the page

The paste/drop bridge:
  - An HTML component captures paste/drop events and converts the image to a
    base64 data-URL.
  - JS then finds the hidden Streamlit textarea (aria-label="__paste_relay__")
    in the parent document and sets its value, firing React synthetic events so
    Streamlit registers the change.
  - Python reads session_state for that key and saves the image to disk.
"""

import streamlit as st
import streamlit.components.v1 as components
import json, base64, os, random, uuid
import markdown as md_lib
from pathlib import Path
from PIL import Image
import io



st.set_page_config(page_title="FlashCard Studio", page_icon="🃏", layout="wide")

DATA_FILE  = "flashcard_data.json"
IMAGES_DIR = "flashcard_images"
os.makedirs(IMAGES_DIR, exist_ok=True)

# ─── persistence ──────────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}

def save_data(d):
    with open(DATA_FILE, "w") as f:
        json.dump(d, f, indent=2)

def img_to_b64(path):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            ext  = Path(path).suffix.lower().lstrip(".")
            mime = {"jpg":"jpeg","jpeg":"jpeg","png":"png","gif":"gif","webp":"webp"}.get(ext,"png")
            return f"data:image/{mime};base64,{base64.b64encode(f.read()).decode()}"
    return None


# ─── session state ───────────────────────────────────────────────────────────
for k, v in [("data", load_data()), ("study_state", {})]:
    if k not in st.session_state:
        st.session_state[k] = v

data = st.session_state.data
# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.main-title{font-size:2.4rem;font-weight:800;color:#4F46E5;margin-bottom:.2rem}
.card-front{background:linear-gradient(135deg,#667eea,#764ba2);border-radius:16px;
  padding:2rem;color:#fff;font-size:1.3rem;font-weight:600;text-align:center;
  min-height:180px;display:flex;align-items:center;justify-content:center;
  flex-direction:column;
  box-shadow:0 8px 32px rgba(79,70,229,.3);margin-bottom:1rem}
.card-front p,.card-front li{margin:0;padding:0}
.card-front ul,.card-front ol{text-align:left;margin:.4rem 0 0 1.2rem;padding:0}
# .card-back{background:linear-gradient(135deg,#f093fb,#f5576c);border-radius:16px;
#   padding:2rem;color:#fff;font-size:1.1rem;text-align:left;min-height:180px;
#   box-shadow:0 8px 32px rgba(245,87,108,.3);margin-bottom:1rem}
.card-back img{max-width:100%;max-height:700px;border-radius:10px;margin-top:1rem}
.progress-bar{background:#E5E7EB;border-radius:8px;height:12px}
.progress-fill{background:#4F46E5;border-radius:8px;height:12px}
.badge{display:inline-block;background:#EEF2FF;color:#4F46E5;border-radius:20px;
  padding:2px 12px;font-size:.8rem;font-weight:600;margin:2px}
.section-header{font-size:1.1rem;font-weight:700;color:#374151;
  border-left:4px solid #4F46E5;padding-left:10px;margin:1.2rem 0 .6rem 0}
</style>
""", unsafe_allow_html=True)

# ─── header ──────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">🃏 FlashCard Studio — Study Mode</div>', unsafe_allow_html=True)
st.markdown("Select your classes and topics, then start studying.")
st.divider()

if not data:
    st.info("No classes yet. Switch to Manage Cards to create some!")
else:
    ss = st.session_state.study_state
    st.markdown('<div class="section-header">Study Session Setup</div>',
                unsafe_allow_html=True)

    # ── Top controls row ─────────────────────────────────────────────
    ctrl1, ctrl2 = st.columns([3, 1])
    with ctrl1:
        select_all_classes = st.checkbox("✅ Select All Classes", value=True, key="study_all_classes")
    with ctrl2:
        shuffle = st.checkbox("Shuffle cards", value=True)

    st.divider()

    # ── Per-class section with nested topic checkboxes ────────────────
    # collection: { class_name: [topic, ...] }
    selection = {}

    for cls_name, topics_dict in data.items():
        available_topics = list(topics_dict.keys())
        total_cls_cards  = sum(len(v) for v in topics_dict.values())

        cls_col, _ = st.columns([4, 1])
        with cls_col:
            cls_checked = st.checkbox(
                f"**{cls_name}** — {len(available_topics)} topic(s), {total_cls_cards} card(s)",
                value=select_all_classes,
                key=f"study_class_cb_{cls_name}"
            )

        if cls_checked and available_topics:
            # "Select All Topics" toggle for this class
            all_t_col, _ = st.columns([4, 1])
            with all_t_col:
                all_topics_checked = st.checkbox(
                    "Select all topics",
                    value=True,
                    key=f"study_all_topics_{cls_name}"
                )

            # Topic checkboxes in up to 4 columns
            topic_cols = st.columns(min(4, len(available_topics)))
            chosen_topics = []
            for i, topic in enumerate(available_topics):
                with topic_cols[i % len(topic_cols)]:
                    n = len(topics_dict.get(topic, []))
                    checked = st.checkbox(
                        f"{topic} ({n})",
                        value=all_topics_checked,
                        key=f"study_topic_cb_{cls_name}_{topic}"
                    )
                    if checked:
                        chosen_topics.append(topic)

            if chosen_topics:
                selection[cls_name] = chosen_topics

        st.divider()

    # ── Build the card deck from selection ────────────────────────────
    all_cards = [
        {**card, "_class": cls_name, "_topic": topic}
        for cls_name, topics in selection.items()
        for topic in topics
        for card in data[cls_name].get(topic, [])
    ]

    total_selected = sum(len(t) for t in selection.values())
    st.caption(f"📌 {len(selection)} class(es) · {total_selected} topic(s) · {len(all_cards)} card(s) selected")

    if not all_cards:
        st.warning("No cards found for this selection.")
    else:
        if st.button("▶️ Start / Restart Session", type="primary"):
            deck = all_cards.copy()
            if shuffle: random.shuffle(deck)
            ss.update({"deck": deck, "index": 0, "show_answer": False,
                        "correct": 0, "incorrect": 0})
            st.rerun()

        if ss.get("deck"):
            deck  = ss["deck"]
            idx   = ss["index"]
            total = len(deck)

            if idx >= total:
                st.balloons()
                st.markdown("## 🎉 Session Complete!")
                c   = ss.get("correct", 0)
                w   = ss.get("incorrect", 0)
                pct = round(c / (c+w) * 100) if (c+w) else 0
                st.markdown(f"**Score: {c}/{c+w} correct ({pct}%)**")
                if   pct >= 80: st.success("Great job! You're mastering this material! 🌟")
                elif pct >= 60: st.info("Good effort! Keep practicing the ones you missed.")
                else:           st.warning("Keep going! Repetition is key to learning.")
                if st.button("🔄 Study Again"):
                    ss.clear(); st.rerun()
            else:
                card = deck[idx]
                st.markdown(f"**Card {idx+1} of {total}** — {card.get('_class','')} › *{card.get('_topic','')}*")
                st.markdown(f"""
                <div class="progress-bar">
                    <div class="progress-fill" style="width:{idx/total*100:.1f}%"></div>
                </div>""", unsafe_allow_html=True)

                rc1, rc2, _ = st.columns([1, 1, 4])
                with rc1: st.markdown(f'✅ **{ss.get("correct",0)}** correct')
                with rc2: st.markdown(f'❌ **{ss.get("incorrect",0)}** incorrect')
                st.markdown("<br>", unsafe_allow_html=True)

                question_html = md_lib.markdown(card["question"])
                st.markdown(f'<div class="card-front">{question_html}</div>',
                            unsafe_allow_html=True)

                if not ss.get("show_answer"):
                    if st.button("👁️ Show Answer", type="primary", use_container_width=True):
                        ss["show_answer"] = True; st.rerun()
                else:
                    img_html = ""
                    if card.get("answer_image"):
                        b64 = img_to_b64(card["answer_image"])
                        if b64: img_html = f'<img src="{b64}" style="max-width:100%;max-height:600px;border-radius:10px;" />'

                    # st.markdown('<div class="card-back">', unsafe_allow_html=True)
                    with st.container(border=True):
                        st.markdown(
                            '<div style="background:linear-gradient(135deg,#f093fb,#f5576c);'
                            'border-radius:16px;padding:1rem;color:#fff;margin-bottom:1rem">',
                            unsafe_allow_html=True
                        )
                        if card.get("answer_text"):
                            st.markdown(card["answer_text"])
                        if img_html:
                            st.markdown(img_html, unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown("**How did you do?**")
                    cy, cn = st.columns(2)
                    with cy:
                        if st.button("✅ Got it!", type="primary", use_container_width=True):
                            ss["correct"] = ss.get("correct", 0) + 1
                            ss["index"] = idx + 1; ss["show_answer"] = False; st.rerun()
                    with cn:
                        if st.button("❌ Missed it", use_container_width=True):
                            ss["incorrect"] = ss.get("incorrect", 0) + 1
                            ss["index"] = idx + 1; ss["show_answer"] = False; st.rerun()

                    st.markdown("---")
                    if st.button("⏭️ Skip (don't count)"):
                        ss["index"] = idx + 1; ss["show_answer"] = False; st.rerun()