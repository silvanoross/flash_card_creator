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
from pathlib import Path
from PIL import Image
import io
import markdown as md_lib



st.set_page_config(page_title="FlashCard Studio", page_icon="🧠", layout="wide")

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
for k, v in [("data", load_data()), ("study_state", {}), ("show_setup", True)]:
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
  box-shadow:0 8px 32px rgba(79,70,229,.3);margin-bottom:1rem}
.card-back img{max-width:100%;max-height:700px;border-radius:10px;margin-top:1rem}
.progress-bar{background:#E5E7EB;border-radius:8px;height:12px}
.progress-fill{background:#4F46E5;border-radius:8px;height:12px}
.badge{display:inline-block;background:#EEF2FF;color:#4F46E5;border-radius:20px;
  padding:2px 12px;font-size:.8rem;font-weight:600;margin:2px}
.section-header{font-size:1.1rem;font-weight:700;color:#374151;
  border-left:4px solid #4F46E5;padding-left:10px;margin:1.2rem 0 .6rem 0}

/* ── Topic grid: force every column cell to the same fixed height so rows
      stay perfectly aligned no matter how long the label text is.        ── */
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    height: 56px !important;
    overflow: visible !important;
    display: flex !important;
    flex-direction: column !important;   /* ← keep only this one */
    justify-content: flex-start !important;
    white-space: nowrap !important;
}
            
            
/* Keep the actual checkbox widget from inheriting the flex stretch */
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]
  > div[data-testid="stCheckbox"] {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

/* Prevent the checkbox label from pushing the row taller */
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]
  > div[data-testid="stCheckbox"] label {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    display: block !important;
}
</style>
""", unsafe_allow_html=True)

# ─── header ──────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">🦠 Micro and 🧬 Immuno Flashcard Study</div>', unsafe_allow_html=True)
st.markdown("Select your classes and topics, then start studying.")
st.divider()

if not data:
    st.info("No flashcard data found. Make sure flashcard_data.json is in the same folder as this app.")
else:
    ss = st.session_state.study_state

    # ── Pre-initialise all checkbox state before any widgets render ──────────
    all_classes = list(data.keys())

    if "select_all_classes" not in st.session_state:
        st.session_state["select_all_classes"] = True
    for cls in all_classes:
        if f"class_cb_{cls}" not in st.session_state:
            st.session_state[f"class_cb_{cls}"] = True
        if f"select_all_topics_{cls}" not in st.session_state:
            st.session_state[f"select_all_topics_{cls}"] = True
        for t in data[cls]:
            if f"topic_cb_{cls}_{t}" not in st.session_state:
                st.session_state[f"topic_cb_{cls}_{t}"] = True

    # ── Callbacks ─────────────────────────────────────────────────────────────
    def on_select_all_classes():
        val = st.session_state["select_all_classes"]
        for cls in all_classes:
            st.session_state[f"class_cb_{cls}"] = val
            st.session_state[f"select_all_topics_{cls}"] = val
            for t in data[cls]:
                st.session_state[f"topic_cb_{cls}_{t}"] = val

    def make_class_cb(cls):
        def on_class_cb():
            val = st.session_state[f"class_cb_{cls}"]
            # Cascade down to this class's topics only
            st.session_state[f"select_all_topics_{cls}"] = val
            for t in data[cls]:
                st.session_state[f"topic_cb_{cls}_{t}"] = val
            # Sync global select-all (True only if ALL classes are checked)
            st.session_state["select_all_classes"] = all(
                st.session_state.get(f"class_cb_{c}", True) for c in all_classes
            )
        return on_class_cb

    def make_select_all_topics_cb(cls):
        def on_select_all_topics():
            val = st.session_state[f"select_all_topics_{cls}"]
            # Cascade down to this class's topics only
            for t in data[cls]:
                st.session_state[f"topic_cb_{cls}_{t}"] = val
            # Sync class checkbox to match
            st.session_state[f"class_cb_{cls}"] = val
            # Sync global select-all
            st.session_state["select_all_classes"] = all(
                st.session_state.get(f"class_cb_{c}", True) for c in all_classes
            )
        return on_select_all_topics

    def make_topic_cb(cls):
        def on_topic_cb():
            topics = list(data[cls].keys())
            all_on = all(st.session_state.get(f"topic_cb_{cls}_{t}", True) for t in topics)
            # Sync this class's "select all topics" and class checkbox
            st.session_state[f"select_all_topics_{cls}"] = all_on
            st.session_state[f"class_cb_{cls}"] = all_on
            # Sync global select-all
            st.session_state["select_all_classes"] = all(
                st.session_state.get(f"class_cb_{c}", True) for c in all_classes
            )
        return on_topic_cb

    # ── Setup toggle (shown only when a session is active) ───────────────────
    if ss.get("deck"):
        toggle_label = "🔼 Hide Setup" if st.session_state.show_setup else "🔽 Change Setup"
        if st.button(toggle_label):
            st.session_state.show_setup = not st.session_state.show_setup
            st.rerun()
        st.divider()

    if st.session_state.show_setup:
        st.markdown('<div class="section-header">Study Session Setup</div>',
                    unsafe_allow_html=True)

        # ── Top controls ──────────────────────────────────────────────────────
        top1, top2 = st.columns([0.325, 1], gap='small')
        with top1:
            st.checkbox("📚 Select All Classes", key="select_all_classes",
                        on_change=on_select_all_classes)
        with top2:
            shuffle = st.checkbox("🔀 Shuffle cards", value=True)
    else:
        shuffle = st.session_state.get("_last_shuffle", True)

    if st.session_state.show_setup:
        st.divider()

    # ── Per-class sections ─────────────────────────────────────────────────────
    # FIX: Topics are ALWAYS rendered regardless of class checkbox state.
    # Previously they were hidden when the class was unchecked, which caused
    # Streamlit to destroy and recreate those widgets on every toggle,
    # resetting all their state values and producing the "deselects everything" bug.
    if st.session_state.show_setup:
        for cls in all_classes:
            topics = list(data[cls].keys())
            total_cls_cards = sum(len(data[cls][t]) for t in topics)

            # Class-level checkbox
            st.checkbox(
                f"**{cls}** — {len(topics)} topic(s), {total_cls_cards} card(s)",
                key=f"class_cb_{cls}",
                on_change=make_class_cb(cls),
            )

            # "Select all topics" toggle — always visible
            if topics:
                st.checkbox(
                    "Select all topics",
                    key=f"select_all_topics_{cls}",
                    on_change=make_select_all_topics_cb(cls),
                )

                # Individual topic checkboxes — always visible
                topic_cols = st.columns(min(4, len(topics)))
                for i, topic in enumerate(topics):
                    with topic_cols[i % len(topic_cols)]:
                        n = len(data[cls][topic])
                        label = topic if len(topic) <= 40 else topic[:38] + "…"
                        st.checkbox(
                            f"{label} ({n})",
                            key=f"topic_cb_{cls}_{topic}",
                            on_change=make_topic_cb(cls),
                        )

            st.divider()

    # ── Build card deck from current checkbox state ───────────────────────────
    all_cards = [
        {**card, "_class": cls, "_topic": topic}
        for cls in all_classes
        if st.session_state.get(f"class_cb_{cls}", True)
        for topic in data[cls]
        if st.session_state.get(f"topic_cb_{cls}_{topic}", True)
        for card in data[cls][topic]
    ]

    if st.session_state.show_setup:
        total_selected_topics = sum(
            1 for cls in all_classes
            if st.session_state.get(f"class_cb_{cls}", True)
            for t in data[cls]
            if st.session_state.get(f"topic_cb_{cls}_{t}", True)
        )
        selected_classes = [c for c in all_classes if st.session_state.get(f"class_cb_{c}", True)]
        st.caption(f"📌 {len(selected_classes)} class(es) · {total_selected_topics} topic(s) · {len(all_cards)} card(s) selected")

        if not all_cards:
            st.warning("No cards found for this selection.")
        else:
            if st.button("▶️ Start / Restart Session", type="primary"):
                st.session_state["_last_shuffle"] = shuffle
                deck = all_cards.copy()
                if shuffle: random.shuffle(deck)
                ss.update({"deck": deck, "index": 0, "show_answer": False,
                            "correct": 0, "incorrect": 0})
                st.session_state.show_setup = False
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
                    ss.clear()
                    st.session_state.show_setup = True
                    st.rerun()
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
