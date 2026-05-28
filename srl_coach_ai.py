import streamlit as st
from openai import OpenAI
from datetime import datetime
import random
import json
import os
import requests

# ========== API Configuration ==========
DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]

deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# ========== Supabase 配置 ==========
SUPABASE_URL = "https://kgzotpkprrmuaxiqqeaz.supabase.co"
SUPABASE_KEY = "sb_publishable_r0YyELsdDWsVh8IcA80Nlw_eHpBe1lY"

STEPS = ("plan", "draft", "evaluating", "interaction")
STEP_LABELS = {
    "plan": "Plan",
    "draft": "Draft",
    "evaluating": "Evaluation",
    "interaction": "Interaction",
}
# Shorter labels on step buttons (one line, equal width)
STEP_BTN_LABEL = {
    "plan": "Plan",
    "draft": "Draft",
    "evaluating": "Evaluate",
    "interaction": "Interact",
}
ROUND_LABELS = {"round_1": "Round 1", "round_2": "Round 2"}


def save_to_supabase(student_id, student_name, test_round, plan_completed,
                     monitoring_count, conversation):
    try:
        url = f"{SUPABASE_URL}/rest/v1/writing_sessions"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        trimmed = conversation[-30:] if len(conversation) > 30 else conversation
        data = {
            "student_id": student_id,
            "student_name": student_name,
            "test_round": test_round,
            "plan_completed": plan_completed,
            "monitoring_count": monitoring_count,
            "conversation": trimmed,
            "created_at": datetime.now().isoformat()
        }
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        if resp.status_code not in (200, 201):
            print(f"❌ Supabase error {resp.status_code}: {resp.text}")
            return False
        return True
    except Exception as e:
        print(f"❌ Supabase error: {e}")
        return False

# ========== Local Storage ==========
DATA_DIR = "srl_writing_data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_user_data_file(user_id: str) -> str:
    safe_id = "".join(c for c in user_id if c.isalnum() or c in "._-")
    return os.path.join(DATA_DIR, f"{safe_id}.json")

def save_conversation(user_id: str, conversation_data: dict):
    file_path = get_user_data_file(user_id)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    else:
        all_data = {"user_id": user_id, "sessions": []}
    all_data["sessions"].append(conversation_data)
    all_data["last_updated"] = datetime.now().isoformat()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    return True

def save_current_session():
    if st.session_state.logged_in and len(st.session_state.messages) > 1:
        session_data = {
            "session_id": st.session_state.conversation_id,
            "start_time": st.session_state.session_start,
            "end_time": datetime.now().isoformat(),
            "plan_completed": st.session_state.plan_completed,
            "monitoring_count": st.session_state.monitoring_count,
            "current_step": st.session_state.current_step,
            "messages": st.session_state.messages
        }
        save_conversation(st.session_state.user_id, session_data)
        save_to_supabase(
            student_id=st.session_state.user_id,
            student_name=st.session_state.user_name,
            test_round=st.session_state.test_round,
            plan_completed=st.session_state.plan_completed,
            monitoring_count=st.session_state.monitoring_count,
            conversation=st.session_state.messages,
        )
        return True
    return False

# ========== System Prompts ==========
BASE_RULES = """## CRITICAL RULES
- RESPOND IN 100% ENGLISH. NO CHINESE.
- NEVER write full paragraphs for the student.
- End every response with ONE small actionable next step.
- If student copies your example word-for-word (80%+ match): "⚠️ I notice you copied my example. Now write YOUR OWN version — change at least 3 words."
"""

PLAN_PROMPT = BASE_RULES + """
## Your Role: PLAN Coach (Step 1)
Help the student set writing goals and create an outline using SRL theory.
Steps:
1. Ask for their topic and purpose
2. Help them define a clear thesis
3. Build a 3-part outline (Intro / Body / Conclusion)
4. Ask them to write ONE original opening sentence
Do NOT write the outline for them — guide with questions.
"""

DRAFT_PROMPT = BASE_RULES + """
## Your Role: DRAFT Coach (Step 2)
The student is actively drafting. Help them self-monitor their writing in progress.
Check these dimensions (do NOT score — give targeted feedback only):
1. LOGIC: Is the argument coherent? Do ideas connect?
2. EVIDENCE: Are there concrete examples or data?
3. LANGUAGE: Grammar, vocabulary, sentence variety
4. ORIGINALITY: Is this their own thinking, or copied/AI-generated?
Ask the student to self-assess first, then offer 1-2 specific suggestions.
"""

# Official CET-4/CET-6 writing rubric (2016 syllabus, holistic impression scoring / 总体印象评分法)
CET_OFFICIAL_RUBRIC = """
## Official CET-4/CET-6 Writing Rubric (reference)
Method: holistic impression scoring on a **15-point scale** (five descriptor tiers).
CET-4 and CET-6 use the same tier descriptions; only task difficulty differs.

Evaluate along these four dimensions (used by examiners holistically):
1. **Relevance (切题):** Addresses the prompt; ideas stay on topic.
2. **Clarity (表达思想清楚):** Ideas are expressed clearly enough for the reader.
3. **Coherence (文字通顺、连贯):** Smooth flow, logical progression, readable connections.
4. **Language accuracy (语言错误):** Frequency and severity of grammar, word-choice, and sentence errors.

### Five official score tiers (assign ONE tier, then a score within its range)
| Tier | Score range | Official descriptor |
|------|-------------|---------------------|
| 14-pt | **13–15** | On topic. Ideas expressed clearly. Writing smooth and coherent. Basically no language errors; only minor slips. |
| 11-pt | **10–12** | On topic. Ideas expressed clearly. Writing coherent, but a few language errors. |
| 8-pt  | **7–9**   | Basically on topic. Some places lack clarity. Barely coherent. Quite a few errors, some serious. |
| 5-pt  | **4–6**   | Basically on topic. Ideas unclear. Poor coherence. Many serious language errors. |
| 2-pt  | **1–3**   | Disorganized; confused thinking. Language fragmented, OR most sentences have errors (mostly serious). |
"""

EVALUATING_PROMPT_NO_SCORE = BASE_RULES + CET_OFFICIAL_RUBRIC + """
## Your Role: EVALUATION Coach — Feedback Only (Step 3, no score)
Apply the official CET holistic rubric above. Do **not** give a numeric score or tier label.

Comment on all four dimensions (Relevance, Clarity, Coherence, Language accuracy):
- For each: one strength + one specific improvement tied to the student's draft.
- Briefly note which official tier their draft *resembles* in plain language only (e.g., "closest to the 11-point description") — but do NOT state a number.

End with: "What will you revise first?"
"""

EVALUATING_PROMPT_WITH_SCORE = BASE_RULES + CET_OFFICIAL_RUBRIC + """
## Your Role: EVALUATION Coach — Official CET Score + Feedback (Step 3, scored)
Apply holistic impression scoring exactly as in the official table above.

Process:
1. Judge the draft on Relevance, Clarity, Coherence, and Language accuracy.
2. Select the **single best-matching tier** (14 / 11 / 8 / 5 / 2).
3. Assign a score **within that tier's range** (e.g., strong 11-pt draft → 12/15). You may use ±1 within the tier if warranted; do not jump more than one tier without explaining why.

Required response format:
**Relevance:** [brief comment]
**Clarity:** [brief comment]
**Coherence:** [brief comment]
**Language accuracy:** [brief comment]

**Official tier:** [14-pt / 11-pt / 8-pt / 5-pt / 2-pt] — [one-sentence paraphrase of that tier's descriptor]
**CET Writing Score:** [X/15] (range for this tier: …)
**Priority to improve:** [one concrete revision targeting the weakest dimension]
"""

INTERACTION_PROMPT = BASE_RULES + """
## Your Role: INTERACTION Coach (Step 4)
You have TWO responsibilities in this interaction:

### Part 1 — Diagnosis & Emotional Support
Analyze the student's writing journey so far and provide:
- Cognitive diagnosis: What writing skills have they demonstrated? What gaps remain?
- Emotional support: Acknowledge their effort, normalize struggles, build confidence
- Personalized encouragement based on their specific progress
If they seem stuck or frustrated, address that directly with warmth and a concrete small step.

### Part 2 — Critical Thinking Dialogue
After your diagnosis, invite the student to reflect critically:
- "Do you agree with my assessment? Is there anything you'd add or challenge?"
- If they disagree: validate their perspective, ask them to explain their reasoning, then update your view or explain yours more deeply
- Goal: model intellectual humility and help them develop their own critical voice
- Never dismiss their disagreement — treat it as valuable data

End with an open question that invites them to push back or go deeper.
"""

# ========== CSS — Monet's Garden (Giverny) ==========
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,600;0,700;1,500&family=Cormorant+Garamond:wght@500;600&family=Source+Sans+3:wght@400;500;600&display=swap');

    :root {
        --giverny-sage: #5f8a72;
        --giverny-sage-light: #8fb39a;
        --giverny-pond: #9ebfcc;
        --giverny-lavender: #c8b8d8;
        --giverny-rose: #ddb8c8;
        --giverny-cream: #faf6ef;
        --giverny-paper: #f3ede4;
        --giverny-ink: #3a5248;
        --giverny-muted: #6a7f74;
        --step-h: 3.35rem;
    }

    .stApp {
        background:
            radial-gradient(ellipse 80% 50% at 15% 10%, rgba(200, 184, 216, 0.45), transparent 55%),
            radial-gradient(ellipse 70% 45% at 88% 15%, rgba(158, 191, 204, 0.4), transparent 50%),
            radial-gradient(ellipse 90% 60% at 50% 100%, rgba(143, 179, 154, 0.35), transparent 55%),
            radial-gradient(ellipse 50% 40% at 70% 60%, rgba(221, 184, 200, 0.25), transparent 50%),
            linear-gradient(165deg, #e9f2ec 0%, #f7f2ea 42%, #f0eaf5 78%, #e4efe9 100%);
        font-family: 'Source Sans 3', sans-serif;
        color: var(--giverny-ink);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(250, 246, 239, 0.97), rgba(232, 242, 236, 0.95)) !important;
        border-right: 1px solid rgba(95, 138, 114, 0.18) !important;
    }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label {
        color: var(--giverny-ink) !important;
    }

    .stButton > button[kind="primary"],
    button[data-testid="stBaseButton-primary"],
    [data-testid="stBaseButton-primary"] {
        background: linear-gradient(145deg, #4d7560, #6d9a7e) !important;
        background-color: #5f8a72 !important;
        border: 1px solid rgba(255,255,255,0.35) !important;
        color: #fff !important;
        box-shadow: 0 3px 12px rgba(77, 117, 96, 0.35) !important;
    }
    .stButton > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(145deg, #456a58, #5f8a72) !important;
        border-color: rgba(255,255,255,0.5) !important;
        color: #fff !important;
    }
    button[data-testid="stBaseButton-primary"] p,
    button[data-testid="stBaseButton-primary"] div {
        color: #fff !important;
    }

    .monet-title {
        font-family: 'Playfair Display', serif;
        font-size: 2.35rem;
        font-weight: 600;
        color: var(--giverny-ink);
        letter-spacing: 0.02em;
    }
    .monet-subtitle {
        font-family: 'Cormorant Garamond', serif;
        color: var(--giverny-muted);
        font-size: 1.05rem;
        font-style: italic;
    }
    .monet-badge {
        background: linear-gradient(135deg, rgba(255,252,248,0.85), rgba(232,245,238,0.75));
        border: 1px solid rgba(95, 138, 114, 0.22);
        border-radius: 18px;
        padding: 10px 18px;
        box-shadow: 0 4px 20px rgba(58, 82, 72, 0.08);
    }
    .login-shell {
        max-width: 400px;
        margin: 0 auto;
        padding: 1.5rem 1.75rem 1.25rem;
        background: linear-gradient(160deg, rgba(255,253,250,0.95), rgba(240,248,243,0.9));
        border: 1px solid rgba(143, 179, 154, 0.35);
        border-radius: 24px;
        box-shadow: 0 12px 40px rgba(58, 82, 72, 0.1);
    }
    .intro-text {
        text-align: center;
        color: var(--giverny-muted);
        font-size: 0.92rem;
        max-width: 520px;
        margin: 0 auto;
        line-height: 1.55;
    }
    .intro-icon-row {
        display: flex;
        justify-content: center;
        gap: 1rem;
        margin: 1.1rem 0;
        flex-wrap: wrap;
    }
    .intro-icon-item {
        text-align: center;
        font-size: 0.76rem;
        color: var(--giverny-muted);
        padding: 0.5rem 0.65rem;
        border-radius: 14px;
        background: rgba(255,255,255,0.45);
        border: 1px solid rgba(143, 179, 154, 0.2);
        min-width: 76px;
    }
    .intro-icon-item span { font-size: 1.35rem; display: block; margin-bottom: 0.15rem; }

    .monet-steps-header {
        font-family: 'Cormorant Garamond', serif;
        font-size: 1.15rem;
        font-weight: 600;
        color: var(--giverny-ink);
        margin: 0.75rem 0 0.5rem;
        text-align: center;
        letter-spacing: 0.04em;
    }
    .step-flow-caption {
        text-align: center;
        color: var(--giverny-muted);
        margin: 0.5rem 0 0.85rem;
        font-family: 'Cormorant Garamond', serif;
        font-size: 0.95rem;
    }
    .eval-pick-box {
        background: linear-gradient(135deg, rgba(255,252,248,0.9), rgba(232,245,238,0.75));
        border: 1px solid rgba(95, 138, 114, 0.28);
        border-radius: 16px;
        padding: 0.65rem 0.85rem 0.5rem;
        margin: 0.5rem 0 0.75rem;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
    }
    .eval-pick-title {
        font-family: 'Cormorant Garamond', serif;
        font-size: 1rem;
        color: var(--giverny-ink);
        font-weight: 600;
        text-align: center;
        margin-bottom: 0.4rem;
    }

    .stTextInput > div > div {
        background: rgba(255,253,250,0.85) !important;
        border-radius: 12px !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background: linear-gradient(135deg, #6d9480 0%, #5a7d6a 100%) !important;
        color: #fff !important;
        border-radius: 18px 18px 4px 18px !important;
        padding: 10px 16px !important;
        max-width: 78% !important;
        margin-left: auto !important;
        box-shadow: 0 2px 10px rgba(77, 117, 96, 0.2) !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        background: linear-gradient(135deg, rgba(255,252,247,0.98), rgba(243,237,228,0.95)) !important;
        border: 1px solid rgba(143, 179, 154, 0.25) !important;
        border-radius: 18px 18px 18px 4px !important;
        color: var(--giverny-ink) !important;
        max-width: 88% !important;
        box-shadow: 0 2px 12px rgba(58, 82, 72, 0.06) !important;
    }
    [data-testid="stChatInput"] {
        border-radius: 16px !important;
        border-color: rgba(95, 138, 114, 0.35) !important;
        background: rgba(255,253,250,0.9) !important;
    }
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(143,179,154,0.5), transparent);
        margin: 0.5rem 0;
    }
    #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ========== Session State ==========
def init_session_state():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.user_name = None
        st.session_state.test_round = "round_1"
        st.session_state.messages = []
        st.session_state.plan_completed = False
        st.session_state.monitoring_count = 0
        st.session_state.conversation_id = ""
        st.session_state.session_start = ""
        st.session_state.current_step = "plan"
        st.session_state.plan_in_progress = False
        st.session_state.show_eval_menu = False
    elif st.session_state.get("current_step") == "monitoring":
        st.session_state.current_step = "draft"

def get_system_prompt(step: str, eval_mode: str = "no_score") -> str:
    mapping = {
        "plan":        PLAN_PROMPT,
        "draft":       DRAFT_PROMPT,
        "evaluating":  EVALUATING_PROMPT_WITH_SCORE if eval_mode == "score" else EVALUATING_PROMPT_NO_SCORE,
        "interaction": INTERACTION_PROMPT,
    }
    return mapping.get(step, PLAN_PROMPT)

def do_login(user_id: str, user_name: str, test_round: str = "round_1"):
    st.session_state.logged_in = True
    st.session_state.user_id = user_id
    st.session_state.user_name = user_name
    st.session_state.test_round = test_round
    st.session_state.messages = []
    st.session_state.plan_completed = False
    st.session_state.monitoring_count = 0
    st.session_state.current_step = "plan"
    st.session_state.plan_in_progress = False
    st.session_state.show_eval_menu = False
    st.session_state.conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.session_start = datetime.now().isoformat()
    st.session_state.messages.append({
        "role": "assistant",
        "content": (
            f"👋 **Welcome, {user_name}!**\n\n"
            "Writing can feel difficult — and that's completely normal. "
            "I'm here to help you **lower those barriers** and build confidence, step by step.\n\n"
            "**Tell me your English writing topic, and let's begin with Step 1: Plan.**\n\n"
            "---\n🎨 *Like painting with words — one brushstroke at a time.*"
        )
    })

def do_logout():
    if st.session_state.logged_in and len(st.session_state.messages) > 1:
        save_current_session()
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.test_round = "round_1"
    st.session_state.messages = []
    st.session_state.plan_completed = False
    st.session_state.monitoring_count = 0
    st.session_state.current_step = "plan"
    st.session_state.show_eval_menu = False
    st.rerun()

def round_display(value: str) -> str:
    legacy = {"pre": "Round 1", "post": "Round 2"}
    if value in legacy:
        return legacy[value]
    return ROUND_LABELS.get(value, value.replace("_", " ").title())


STEP_BUTTON_KEYS = {s: f"btn_{s}" for s in STEPS}


def _st_key(key: str) -> str:
    return f".st-key-{key}"


def inject_css_block(css: str) -> None:
    if hasattr(st, "html"):
        st.html(f"<style>{css}</style>")
    else:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def inject_step_button_styles(active_step: str) -> None:
    active_bg = "linear-gradient(155deg, #4a735f 0%, #6d9a7e 50%, #5f8a72 100%)"
    inactive_bg = "linear-gradient(155deg, #d8e4dc 0%, #e8e0d4 45%, #ddd4e8 100%)"
    btn_props = """
        width: 100% !important;
        height: var(--step-h) !important;
        min-height: var(--step-h) !important;
        max-height: var(--step-h) !important;
        padding: 0 0.5rem !important;
        margin: 0 !important;
        border-radius: 14px !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        line-height: 1.1 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-sizing: border-box !important;
        transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease !important;
    """
    rules = [
        """
        div:has(> #srl-step-grid-marker) + div [data-testid="stHorizontalBlock"] {
            align-items: stretch !important;
            gap: 0.5rem !important;
        }
        div:has(> #srl-step-grid-marker) + div [data-testid="column"] {
            display: flex !important;
            flex-direction: column !important;
        }
        div:has(> #srl-step-grid-marker) + div [data-testid="column"] > div {
            flex: 1 !important;
            display: flex !important;
            flex-direction: column !important;
        }
        """
    ]
    col_idx = {s: i + 1 for i, s in enumerate(STEPS)}

    for step, key in STEP_BUTTON_KEYS.items():
        on = step == active_step
        bg = active_bg if on else inactive_bg
        color = "#ffffff" if on else "#3a5248"
        border = "2px solid rgba(180, 220, 195, 0.9)" if on else "1px solid rgba(143, 179, 154, 0.35)"
        shadow = "0 6px 20px rgba(74, 115, 95, 0.38)" if on else "0 2px 8px rgba(58, 82, 72, 0.08)"
        transform = "translateY(-2px) scale(1.02)" if on else "none"
        opacity = "1" if on else "0.82"
        sk = _st_key(key)
        col_sel = (
            f'div:has(> #srl-step-grid-marker) + div '
            f'[data-testid="column"]:nth-child({col_idx[step]}) button'
        )
        block = f"{sk} button, {sk} [data-testid='stBaseButton-secondary'], {sk} [data-testid='stBaseButton-primary'], {col_sel}"
        rules.append(f"""
        {block} {{
            {btn_props}
            background: {bg} !important;
            background-color: transparent !important;
            background-image: {bg} !important;
            color: {color} !important;
            border: {border} !important;
            box-shadow: {shadow} !important;
            transform: {transform} !important;
            opacity: {opacity} !important;
        }}
        {sk} button p, {sk} button div, {sk} button span {{
            color: {color} !important;
            font-size: 0.8rem !important;
            white-space: nowrap !important;
        }}
        {block}:hover {{
            opacity: 1 !important;
            border-color: rgba(95, 138, 114, 0.65) !important;
        }}
        {block}:focus, {block}:focus-visible {{
            outline: none !important;
            box-shadow: {shadow} !important;
        }}
        """)

    eval_bg = "linear-gradient(155deg, #5a7d68 0%, #7a9f88 100%)"
    for key in ("btn_eval_feedback", "btn_eval_score"):
        sk = _st_key(key)
        rules.append(f"""
        {sk} button, {sk} [data-testid='stBaseButton-secondary'] {{
            height: 2.85rem !important;
            min-height: 2.85rem !important;
            max-height: 2.85rem !important;
            background: {eval_bg} !important;
            background-image: {eval_bg} !important;
            color: #fff !important;
            border-radius: 12px !important;
            border: 1px solid rgba(255,255,255,0.3) !important;
            font-size: 0.78rem !important;
            white-space: nowrap !important;
        }}
        {sk} button p {{ color: #fff !important; }}
        """)

    util_bg = "linear-gradient(135deg, #9aab9c 0%, #b5a898 100%)"
    for key in ("btn_reset", "btn_save", "btn_signout", "btn_login_start"):
        sk = _st_key(key)
        rules.append(f"""
        {sk} button, {sk} [data-testid='stBaseButton-primary'], {sk} [data-testid='stBaseButton-secondary'] {{
            min-height: 2.4rem !important;
            background: {util_bg if key != 'btn_login_start' else 'linear-gradient(145deg, #4d7560, #6d9a7e)'} !important;
            background-image: {util_bg if key != 'btn_login_start' else 'linear-gradient(145deg, #4d7560, #6d9a7e)'} !important;
            color: #fff !important;
            border: none !important;
            border-radius: 20px !important;
            font-size: 0.8rem !important;
        }}
        {sk} button p {{ color: #fff !important; }}
        """)

    inject_css_block("".join(rules))

# ========== Login Page ==========
def show_login_page():
    st.markdown(
        '<div class="monet-title" style="text-align:center;margin-top:0.5rem;">'
        '🌸 Giverny Writing Garden</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="monet-subtitle" style="text-align:center;">'
        'Self-Regulated Learning · like painting with words</div>',
        unsafe_allow_html=True,
    )
    st.markdown("""
    <div class="intro-text">
        Walk through four soft brushstrokes of writing:<br>
        <strong>Plan → Draft → Evaluate → Interact</strong>
    </div>
    <div class="intro-icon-row">
        <div class="intro-icon-item"><span>🌿</span><strong>Plan</strong></div>
        <div class="intro-icon-item"><span>✏️</span><strong>Draft</strong></div>
        <div class="intro-icon-item"><span>🪷</span><strong>Evaluate</strong></div>
        <div class="intro-icon-item"><span>💭</span><strong>Interact</strong></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="login-shell">', unsafe_allow_html=True)
    st.markdown("##### 🎨 Enter the garden")
    email = st.text_input("Email", placeholder="you@university.edu", key="login_email")
    user_name = st.text_input("Your name", placeholder="e.g., Wei Yutong", key="login_name")
    round_option = st.selectbox("Round", ["Round 1", "Round 2"], key="test_round_select")
    login_clicked = st.button("Start", use_container_width=True, type="primary", key="btn_login_start")
    if login_clicked:
        if email.strip() and user_name.strip():
            round_value = "round_1" if round_option == "Round 1" else "round_2"
            do_login(email.strip(), user_name.strip(), round_value)
            st.rerun()
        else:
            st.warning("Please enter your email and name.")
    st.caption("Your writing is saved automatically after each message.")
    st.markdown("</div>", unsafe_allow_html=True)
    inject_step_button_styles("plan")

# ========== Main App ==========
def main_app():
    round_label = round_display(st.session_state.test_round)

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.75rem;margin-bottom:0.25rem;">
        <div>
            <div class="monet-title" style="text-align:left;font-size:1.75rem;margin:0;">
                🌸 Giverny Writing Garden
            </div>
            <div class="monet-subtitle" style="text-align:left;margin:0;">
                Plan → Draft → Evaluate → Interact
            </div>
        </div>
        <div class="monet-badge" style="text-align:right;">
            <div style="font-size:0.92rem;font-weight:600;">{st.session_state.user_name}</div>
            <div style="font-size:0.72rem;opacity:0.85;">{st.session_state.user_id}</div>
            <div style="font-size:0.72rem;opacity:0.85;">{round_label}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    with st.sidebar:
        st.markdown("""
        <div style="background:linear-gradient(145deg,rgba(255,252,248,0.9),rgba(232,245,238,0.85));
            border-radius:18px;padding:16px;text-align:center;margin-bottom:14px;
            border:1px solid rgba(143,179,154,0.25);">
            <span style="font-size:1.75rem;">🪷</span><br>
            <span style="font-family:'Cormorant Garamond',serif;font-size:1.15rem;font-weight:600;">
                Monet's Studio
            </span><br>
            <span style="font-size:0.72rem;opacity:0.8;">Your writing garden</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"👤 {st.session_state.user_name}")
        st.caption(f"📧 {st.session_state.user_id}")
        st.caption(f"🔄 {round_label}")
        st.divider()
        st.markdown("#### Progress")
        step = st.session_state.current_step
        plan_done = st.session_state.plan_completed
        draft_count = st.session_state.monitoring_count

        for i, key in enumerate(STEPS, start=1):
            label = STEP_LABELS[key]
            if step == key:
                st.info(f"**Step {i} · {label}** — active")
            elif key == "plan" and plan_done:
                st.success(f"Step {i} · {label} ✓")
            elif key == "draft" and draft_count > 0:
                st.success(f"Step {i} · {label} ({draft_count} checks)")
            else:
                st.caption(f"Step {i} · {label}")

        st.divider()
        st.metric("Draft checks", draft_count)
        st.caption(f"Session {st.session_state.conversation_id[-8:]}")
        st.divider()
        tips = [
            "Write one sentence at a time.",
            "Revision is where writing improves.",
            "Self-check before you ask for a score.",
        ]
        st.info(f"💡 {random.choice(tips)}")
        st.divider()
        if st.button("Sign out", use_container_width=True, key="btn_signout"):
            do_logout()

    for msg in st.session_state.messages:
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.markdown(msg["content"])

    def call_ai(user_input: str, eval_mode: str = "no_score") -> str:
        system = get_system_prompt(st.session_state.current_step, eval_mode)
        messages = [{"role": "system", "content": system}]
        for m in st.session_state.messages[-15:]:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_input})
        try:
            resp = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"❌ Error: {str(e)}"

    def handle_input(eval_mode: str = "no_score"):
        user_input = st.session_state.get("user_input", "")
        if not user_input or not user_input.strip():
            return
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.spinner("Thinking..."):
            response = call_ai(user_input, eval_mode)
        st.session_state.messages.append({"role": "assistant", "content": response})

        if st.session_state.get("plan_in_progress") and not st.session_state.plan_completed:
            st.session_state.plan_completed = True
            st.session_state.plan_in_progress = False

        if st.session_state.current_step == "draft":
            st.session_state.monitoring_count += 1

        try:
            save_current_session()
        except Exception as e:
            print(f"⚠️ Save failed: {e}")

        st.session_state.user_input = ""

    def last_user_writing() -> str:
        return next(
            (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"),
            "",
        )

    def set_step(step: str):
        st.session_state.current_step = step
        if step != "evaluating":
            st.session_state.show_eval_menu = False

    def action_plan():
        set_step("plan")
        st.session_state.plan_in_progress = True
        st.session_state.user_input = (
            "Step 1 — Plan. Please help me set goals and create an outline for my English essay."
        )
        handle_input()

    def action_draft():
        set_step("draft")
        if not st.session_state.plan_completed:
            st.session_state.user_input = (
                "I want to start Drafting, but I haven't finished Planning yet. "
                "Please remind me to complete Step 1 first."
            )
            handle_input()
            return
        text = last_user_writing()
        if text and len(text) > 30:
            st.session_state.user_input = f"Step 2 — Draft. Please help me self-check this writing:\n\n{text}"
        else:
            st.session_state.user_input = (
                "Step 2 — Draft. I'm ready to draft and self-check my writing. Please guide me."
            )
        handle_input()

    def action_open_evaluation():
        set_step("evaluating")
        st.session_state.show_eval_menu = True

    def action_evaluating_no_score():
        set_step("evaluating")
        if not st.session_state.plan_completed:
            st.session_state.user_input = (
                "I want Evaluation feedback, but I haven't finished Planning yet. Please remind me."
            )
            handle_input()
            return
        text = last_user_writing()
        prompt = (
            "Step 3 — Evaluation (official CET holistic rubric, feedback only, no score). "
            "Please evaluate my writing on Relevance, Clarity, Coherence, and Language accuracy."
        )
        if text and len(text) > 30:
            prompt += f"\n\nMy writing:\n{text}"
        st.session_state.user_input = prompt
        handle_input(eval_mode="no_score")

    def action_evaluating_with_score():
        set_step("evaluating")
        if not st.session_state.plan_completed:
            st.session_state.user_input = (
                "I want a CET scored evaluation, but I haven't finished Planning yet. Please remind me."
            )
            handle_input()
            return
        text = last_user_writing()
        prompt = (
            "Step 3 — Evaluation (official CET holistic scoring, 15-point scale). "
            "Please assign a tier and score (13–15 / 10–12 / 7–9 / 4–6 / 1–3) with feedback."
        )
        if text and len(text) > 30:
            prompt += f"\n\nMy writing:\n{text}"
        st.session_state.user_input = prompt
        handle_input(eval_mode="score")

    def action_interaction():
        set_step("interaction")
        if not st.session_state.plan_completed:
            st.session_state.user_input = (
                "I want Interaction, but I haven't finished Planning yet. Please remind me."
            )
            handle_input()
            return
        st.session_state.user_input = (
            "Step 4 — Interaction. Please diagnose my writing journey, offer emotional support, "
            "and invite me to critically reflect on your assessment."
        )
        handle_input()

    def action_reset():
        save_current_session()
        st.session_state.messages = []
        st.session_state.plan_completed = False
        st.session_state.monitoring_count = 0
        st.session_state.current_step = "plan"
        st.session_state.plan_in_progress = False
        st.session_state.show_eval_menu = False
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                f"✨ **Fresh start, {st.session_state.user_name}!**\n\n"
                "Tell me your topic and we'll begin with **Step 1: Plan**."
            )
        })
        st.rerun()

    step_num = {s: i + 1 for i, s in enumerate(STEPS)}
    cur = st.session_state.current_step

    st.markdown('<p class="monet-steps-header">🌿 The four steps in your garden</p>', unsafe_allow_html=True)
    st.markdown('<div id="srl-step-grid-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="small")

    def render_step_button(step_key: str, icon: str, on_click):
        n = step_num[step_key]
        short = STEP_BTN_LABEL[step_key]
        st.button(
            f"{icon}  {n} · {short}",
            use_container_width=True,
            on_click=on_click,
            key=STEP_BUTTON_KEYS[step_key],
            type="secondary",
        )

    with c1:
        render_step_button("plan", "📋", action_plan)
    with c2:
        render_step_button("draft", "✍️", action_draft)
    with c3:
        render_step_button("evaluating", "📊", action_open_evaluation)
    with c4:
        render_step_button("interaction", "💬", action_interaction)

    if st.session_state.show_eval_menu and cur == "evaluating":
        st.markdown('<div class="eval-pick-box">', unsafe_allow_html=True)
        st.markdown(
            '<div class="eval-pick-title">🪷 Choose your evaluation mode</div>',
            unsafe_allow_html=True,
        )
        e1, e2 = st.columns(2, gap="small")
        with e1:
            st.button(
                "Feedback only",
                use_container_width=True,
                on_click=action_evaluating_no_score,
                key="btn_eval_feedback",
                type="secondary",
            )
        with e2:
            st.button(
                "CET score + feedback",
                use_container_width=True,
                on_click=action_evaluating_with_score,
                key="btn_eval_score",
                type="secondary",
            )
        st.markdown("</div>", unsafe_allow_html=True)

    inject_step_button_styles(cur)

    active_label = STEP_LABELS.get(cur, cur.title())
    st.markdown(
        f'<p class="step-flow-caption">You are on <strong>Step {step_num.get(cur, "?")}: {active_label}</strong> '
        f"· Flow: Plan → Draft → Evaluation → Interaction</p>",
        unsafe_allow_html=True,
    )

    uc1, uc2, uc3 = st.columns([1, 1, 1])
    with uc1:
        st.button("🔄 Reset", use_container_width=True, on_click=action_reset, key="btn_reset", type="secondary")
    with uc2:
        if st.button("💾 Save", use_container_width=True, key="btn_save", type="secondary"):
            if save_current_session():
                st.toast("Saved to your garden 🌸", icon="✅")
            else:
                st.toast("Nothing to save yet.", icon="💡")
    st.chat_input("📝 Type your English writing here...", key="user_input", on_submit=handle_input)

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        st.caption("⚡ DeepSeek")
    with fc2:
        st.caption("🎓 SRL · CET rubric")
    with fc3:
        st.caption("🌸 Your garden, your words")

# ========== Run ==========
init_session_state()
if st.session_state.logged_in:
    main_app()
else:
    show_login_page()
