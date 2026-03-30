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
import re



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

def save_uploaded(uf):
    p = os.path.join(IMAGES_DIR, uf.name)
    with open(p, "wb") as f:
        f.write(uf.getbuffer())
    return p

def save_b64(data_url: str) -> str:
    header, b64data = data_url.split(",", 1)
    ext = "png"
    for x in ("jpeg", "jpg", "gif", "webp"):
        if x in header:
            ext = "jpg" if x == "jpeg" else x
            break
    path = os.path.join(IMAGES_DIR, f"paste_{uuid.uuid4().hex[:10]}.{ext}")
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64data))
    return path

def save_uploaded(uf):
    p = os.path.join(IMAGES_DIR, uf.name)
    # Save at full original quality using Pillow
    img = Image.open(uf)
    if p.lower().endswith((".jpg", ".jpeg")):
        img.save(p, quality=95, optimize=True)  # 95 = near-lossless
    else:
        img.save(p)  # PNG is lossless by default
    return p

def img_to_b64(path):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            ext  = Path(path).suffix.lower().lstrip(".")
            mime = {"jpg":"jpeg","jpeg":"jpeg","png":"png","gif":"gif","webp":"webp"}.get(ext,"png")
            return f"data:image/{mime};base64,{base64.b64encode(f.read()).decode()}"
    return None

def update_session_state():
    # This function runs when the widget value changes
    # st.session_state.new_q is already updated by Streamlit internally here
    st.session_state.other_variable = st.session_state.new_q

# ─── session state ────────────────────────────────────────────────────────────
for k, v in [("data", load_data()), ("mode", "manage"), ("study_state", {})]:
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


# ─── paste/drop zone ──────────────────────────────────────────────────────────
def image_paste_zone(relay_key: str, height: int = 220):
    """
    Renders a drag-drop / paste zone inside an iframe.
    When an image is pasted or dropped it:
      1. Shows a preview inside the iframe.
      2. Writes the base64 data-URL into the Streamlit textarea whose
         aria-label equals relay_key, then fires the events Streamlit needs.
    """
    html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
  body{{margin:0;padding:0;font-family:sans-serif;background:transparent}}
  #zone{{border:2px dashed #4F46E5;border-radius:12px;padding:14px;text-align:center;
    color:#6B7280;font-size:.88rem;background:#F5F3FF;cursor:pointer;
    min-height:70px;display:flex;align-items:center;justify-content:center;
    flex-direction:column;gap:4px;transition:background .2s}}
  #zone.over{{background:#EDE9FE;border-color:#7C3AED}}
  #zone.has-image{{border-color:#10B981;background:#ECFDF5}}
  #preview img{{max-width:100%;max-height:160px;border-radius:8px;
    margin-top:8px;border:1px solid #ddd}}
  #clrbtn{{margin-top:6px;background:#EF4444;color:#fff;border:none;
    border-radius:6px;padding:3px 12px;cursor:pointer;font-size:.8rem;display:none}}
</style>
</head>
<body>
<div id="zone" tabindex="0">
  📋 <strong>Ctrl+V / Cmd+V</strong> to paste &nbsp;|&nbsp; <strong>drag &amp; drop</strong> an image here
</div>
<div id="preview"></div>
<button id="clrbtn" onclick="clearImg()">✕ Remove image</button>

<script>
const RELAY_LABEL = "{relay_key}";
const zone    = document.getElementById('zone');
const preview = document.getElementById('preview');
const clrbtn  = document.getElementById('clrbtn');

function findRelay() {{
  // Search the top-level Streamlit document for our hidden textarea
  try {{
    return window.top.document.querySelector(
      `textarea[aria-label="${{RELAY_LABEL}}"]`
    );
  }} catch(e) {{
    return null;
  }}
}}

function setRelayValue(val) {{
  const el = findRelay();
  if (!el) {{ console.warn('Paste relay not found for label:', RELAY_LABEL); return; }}
  // Use React's internal setter so Streamlit detects the change
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.top.HTMLTextAreaElement.prototype, 'value'
  ).set;
  nativeSetter.call(el, val);
  el.dispatchEvent(new Event('input',  {{bubbles:true}}));
  el.dispatchEvent(new Event('change', {{bubbles:true}}));
}}

function showPreview(dataUrl) {{
  preview.innerHTML = `<img src="${{dataUrl}}" />`;
  clrbtn.style.display = 'inline-block';
  zone.classList.add('has-image');
  zone.textContent = '✅ Image ready';
}}

function clearImg() {{
  preview.innerHTML = '';
  clrbtn.style.display = 'none';
  zone.classList.remove('has-image');
  zone.innerHTML = '📋 <strong>Ctrl+V / Cmd+V</strong> to paste &nbsp;|&nbsp; <strong>drag &amp; drop</strong> an image here';
  setRelayValue('CLEAR');
}}

function handleFile(file) {{
  if (!file || !file.type.startsWith('image/')) return;
  const reader = new FileReader();
  reader.onload = e => {{
    showPreview(e.target.result);
    setRelayValue(e.target.result);
  }};
  reader.readAsDataURL(file);
}}

// Listen for paste on the top-level document
try {{
  window.top.document.addEventListener('paste', function(e) {{
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (const item of items) {{
      if (item.type.startsWith('image/')) {{
        e.preventDefault();
        handleFile(item.getAsFile());
        return;
      }}
    }}
  }});
}} catch(crossOriginErr) {{
  // Fallback: listen inside iframe
  document.addEventListener('paste', function(e) {{
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (const item of items) {{
      if (item.type.startsWith('image/')) {{
        e.preventDefault();
        handleFile(item.getAsFile());
        return;
      }}
    }}
  }});
}}

// Drag & drop
zone.addEventListener('dragover',  e => {{ e.preventDefault(); zone.classList.add('over'); }});
zone.addEventListener('dragleave', ()  => zone.classList.remove('over'));
zone.addEventListener('drop', e => {{
  e.preventDefault();
  zone.classList.remove('over');
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
}});
</script>
</body>
</html>
"""
    components.html(html, height=height, scrolling=False)


# ─── header ───────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">🗂️ FlashCard Studio</div>', unsafe_allow_html=True)
st.markdown("Create classes, topics, and flashcards — then study them with ease.")
st.divider()

col_m1, col_m2, _ = st.columns([1, 1, 5])
with col_m1:
    if st.button("📚 Manage Cards", use_container_width=True,
                 type="primary" if st.session_state.mode == "manage" else "secondary"):
        st.session_state.mode = "manage"; st.rerun()
with col_m2:
    if st.button("🧠 Study Mode", use_container_width=True,
                 type="primary" if st.session_state.mode == "study" else "secondary"):
        st.session_state.mode = "study"; st.rerun()

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# MANAGE MODE
# ═════════════════════════════════════════════════════════════════════════════
if st.session_state.mode == "manage":

    left, right = st.columns([0.5, 2], gap="large")

    # ── LEFT ──────────────────────────────────────────────────────────────────
    with left:
        st.markdown('<div class="section-header">Classes</div>', unsafe_allow_html=True)

        with st.expander("➕ Add New Class"):
            nc = st.text_input("Class name", key="new_class_input")
            if st.button("Create Class"):
                nc = nc.strip()
                if nc:
                    if nc not in data:
                        data[nc] = {}; save_data(data)
                        st.success(f"Class '{nc}' created!"); st.rerun()
                    else:
                        st.warning("Class already exists.")

        if not data:
            st.info("No classes yet. Add one above!")
        else:
            selected_class = st.selectbox("Select a class", list(data.keys()), key="sel_class")

            if selected_class:
                st.markdown(f"**Topics in {selected_class}**")

                with st.expander("➕ Add Topic"):
                    nt = st.text_input("Topic name", key="new_topic_input")
                    if st.button("Create Topic"):
                        nt = nt.strip()
                        if nt:
                            if nt not in data[selected_class]:
                                data[selected_class][nt] = []; save_data(data)
                                st.success(f"Topic '{nt}' added!"); st.rerun()
                            else:
                                st.warning("Topic already exists.")

                if not data[selected_class]:
                    st.info("No topics yet.")
                else:
                    selected_topic = st.selectbox("Select a topic",
                                                  list(data[selected_class].keys()),
                                                  key="sel_topic")
                    if selected_topic:
                        n = len(data[selected_class][selected_topic])
                        st.markdown(
                            f'<span class="badge">{n} card{"s" if n!=1 else ""}</span>',
                            unsafe_allow_html=True)

                with st.expander("🗑️ Delete"):
                    # Delete selected topic
                    if data[selected_class]:
                        st.markdown("**Delete topic:**")
                        topic_to_delete = st.selectbox(
                            "Select topic to delete",
                            list(data[selected_class].keys()),
                            key="del_topic_select"
                        )
                        n_cards = len(data[selected_class].get(topic_to_delete, []))
                        st.caption(f"This will permanently delete '{topic_to_delete}' and its {n_cards} card(s).")
                        if st.button(f"🗑️ Delete Topic '{topic_to_delete}'", type="secondary", key="del_topic_btn"):
                            del data[selected_class][topic_to_delete]
                            save_data(data)
                            st.success(f"Topic '{topic_to_delete}' deleted.")
                            st.rerun()
                        st.divider()

                    # Delete entire class
                    st.markdown("**Delete entire class:**")
                    st.caption(f"This will permanently delete '{selected_class}' and ALL its topics and cards.")
                    if st.button(f"🗑️ Delete Class '{selected_class}'", type="secondary", key="del_class_btn"):
                        del data[selected_class]; save_data(data); st.rerun()

    # ── RIGHT ─────────────────────────────────────────────────────────────────
    with right:
        if not data:
            st.info("👈 Create a class to get started.")
        else:
            sel_class = st.session_state.get("sel_class")
            sel_topic = st.session_state.get("sel_topic")

            if sel_class and sel_topic and sel_topic in data.get(sel_class, {}):
                cards = data[sel_class][sel_topic]
                st.markdown(
                    f'<div class="section-header">Cards — {sel_class} › {sel_topic}</div>',
                    unsafe_allow_html=True)

                # ── Add new card ──────────────────────────────────────────────
                with st.expander("➕ Add New Flashcard", expanded=len(cards) == 0):

                    q = st.text_area("❓ Question (front)", key="new_q", height=100,
                                     placeholder="Type your question here…", on_change=update_session_state)
                    st.markdown("**✏️ Answer text**")
                    a_text = st.text_area("Answer text", key="new_a_text", height=100,
                                          placeholder="Type the answer here…")

                    st.markdown("**🖼️ Answer image**")

                    # Initialize a separate store key (not the widget key)
                    if "pasted_image_data" not in st.session_state:
                        st.session_state["pasted_image_data"] = ""

                    # Hidden relay textarea — JS writes the base64 here.
                    # We use a counter-based key so we can reset it by
                    # incrementing the counter (avoids the widget-key mutation error).
                    if "relay_counter" not in st.session_state:
                        st.session_state["relay_counter"] = 0

                    relay_widget_key = f"relay_new_{st.session_state['relay_counter']}"

                    relay_val = st.text_area(
                        "paste_image_relay_new",   # aria-label used by JS
                        key=relay_widget_key,
                        label_visibility="hidden",
                        height=1,
                        placeholder=""
                    )

                    # Mirror widget value into our safe store key
                    if relay_val and relay_val != "CLEAR" and relay_val.startswith("data:image"):
                        st.session_state["pasted_image_data"] = relay_val
                    elif relay_val == "CLEAR":
                        st.session_state["pasted_image_data"] = ""

                    # Paste / drop zone (references the aria-label above)
                    image_paste_zone("paste_image_relay_new")

                    # Regular file uploader as an alternative
                    a_img = st.file_uploader(
                        "…or browse / drag a file here",
                        type=["png","jpg","jpeg","gif","webp"],
                        key="new_a_img")
                    if a_img:
                        st.image(a_img, caption="Upload preview", width=280)

                    # Show a thumbnail if something was pasted
                    pasted = st.session_state.get("pasted_image_data", "")
                    if pasted and pasted.startswith("data:image"):
                        st.markdown("**Pasted image preview:**")
                        st.markdown(
                            f'<img src="{pasted}" style="max-width:280px;border-radius:8px;'
                            f'border:1px solid #ddd;margin-top:4px" />',
                            unsafe_allow_html=True)

                    if st.button("💾 Save Card", type="primary", key="save_card"):
                        if q.strip():
                            pasted = st.session_state.get("pasted_image_data", "")
                            if pasted and pasted.startswith("data:image"):
                                img_path = save_b64(pasted)
                            elif a_img:
                                img_path = save_uploaded(a_img)
                            else:
                                img_path = None

                            data[sel_class][sel_topic].append({
                                "question":     q.strip(),
                                "answer_text":  a_text.strip(),
                                "answer_image": img_path,
                            })
                            save_data(data)
                            # Reset by incrementing counter → new widget key next render
                            st.session_state["pasted_image_data"] = ""
                            st.session_state["relay_counter"] += 1

                            st.success("Card saved!"); st.rerun()
                        else:
                            st.warning("Please enter a question.")

                # ── Existing cards ────────────────────────────────────────────
                if cards:
                    st.markdown(f"**{len(cards)} card(s) in this topic:**", unsafe_allow_html=True)
                    for i, card in enumerate(cards):
                        if not card.get("question"): 
                            continue
                        
                        label = card["question"][:120] + ("…" if len(card["question"]) > 120 else "")
                        clean_label = re.sub(r'\*\*|__|`|#{1,6}\s*|<[^>]+>', '', card["question"])
                        label = clean_label[:120] + ("…" if len(clean_label) > 120 else "")

                        with st.expander(f"Card {i+1}: {label}"):
                            c1, c2 = st.columns([0.6, 2])
                            with c1:
                                st.markdown("**Front**", unsafe_allow_html=True)#; st.markdown(st.info(card["question"]), unsafe_allow_html=True)
                                st.markdown(card["question"], unsafe_allow_html=True)
                            with c2:
                                st.markdown("**Back**", unsafe_allow_html=True)
                                if card.get("answer_text"):
                                    st.markdown(card["answer_text"], unsafe_allow_html=True)
                                if card.get("answer_image") and os.path.exists(card["answer_image"]):
                                    st.image(card["answer_image"], width=200)

                            with st.form(key=f"edit_{i}"):
                                st.markdown("**Edit card:**")
                                eq = st.text_area("Question", value=card["question"], key=f"eq_{i}")
                                ea = st.text_area("Answer text", value=card.get("answer_text",""), key=f"ea_{i}")
                                ni = st.file_uploader("Replace image (browse)",
                                                      type=["png","jpg","jpeg","gif","webp"],
                                                      key=f"eimg_{i}")
                                cs2, cd = st.columns(2)
                                with cs2:
                                    if st.form_submit_button("💾 Update"):
                                        data[sel_class][sel_topic][i]["question"]    = eq.strip()
                                        data[sel_class][sel_topic][i]["answer_text"] = ea.strip()
                                        if ni:
                                            data[sel_class][sel_topic][i]["answer_image"] = save_uploaded(ni)
                                        save_data(data); st.success("Updated!"); st.rerun()
                                with cd:
                                    if st.form_submit_button("🗑️ Delete Card"):
                                        data[sel_class][sel_topic].pop(i)
                                        save_data(data); st.rerun()
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

                    st.markdown(f'<div class="card-front">{card["question"]}</div>',
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