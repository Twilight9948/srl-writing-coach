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

# ========== CSS ==========
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');

    .stApp {
        background: linear-gradient(135deg, #c9d4c5 0%, #d4cfc4 20%, #e2dcd0 40%, #ede5d8 60%, #dcd0bd 80%, #c4b8a8 100%);
        font-family: 'Source Sans 3', sans-serif;
    }
    .monet-title {
        text-align: center;
        font-family: 'Playfair Display', serif;
        font-size: 2.4rem;
        font-weight: 600;
        color: #2c4a3e;
        margin-bottom: 0.1rem;
    }
    .monet-subtitle {
        text-align: center;
        color: #5a6e5a;
        font-size: 0.85rem;
        font-style: italic;
        margin-bottom: 0.5rem;
    }
    .intro-text {
        text-align: center;
        color: #4a5e4a;
        font-size: 0.9rem;
        max-width: 560px;
        margin: 0 auto;
        line-height: 1.5;
    }
    .intro-icon-row {
        display: flex;
        justify-content: center;
        gap: 1.2rem;
        margin: 1rem 0;
        flex-wrap: wrap;
    }
    .intro-icon-item {
        text-align: center;
        font-size: 0.78rem;
        color: #5a6e5a;
        min-width: 72px;
    }
    .intro-icon-item span { font-size: 1.4rem; display: block; margin-bottom: 0.2rem; }
    .login-area { max-width: 360px; margin: 0.5rem auto; }

    /* Step row buttons (marker div is sibling of stButton in Streamlit DOM) */
    .step-row [data-testid="column"] .stButton > button {
        width: 100% !important;
        min-height: 3.25rem !important;
        padding: 0.45rem 0.35rem !important;
        border-radius: 14px !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        line-height: 1.25 !important;
        white-space: normal !important;
        word-break: break-word !important;
        border: 2px solid transparent !important;
        transition: all 0.2s ease !important;
    }
    .step-row [data-testid="column"] .step-active ~ [data-testid="stButton"] > button {
        background: linear-gradient(145deg, #1f6b4f 0%, #2d8a66 100%) !important;
        color: #fff !important;
        border-color: #a8dcc4 !important;
        box-shadow: 0 4px 14px rgba(31, 107, 79, 0.35) !important;
        transform: translateY(-1px);
    }
    .step-row [data-testid="column"] .step-inactive ~ [data-testid="stButton"] > button {
        background: linear-gradient(145deg, #b8c4bb 0%, #c9c0b2 100%) !important;
        color: #3d4a40 !important;
        opacity: 0.88 !important;
        border-color: rgba(255,255,255,0.35) !important;
    }
    .step-row [data-testid="column"] .step-inactive ~ [data-testid="stButton"] > button:hover {
        opacity: 1 !important;
        border-color: #8daa9a !important;
    }

    /* Eval sub-options */
    .eval-sub-row .stButton > button {
        min-height: 2.6rem !important;
        font-size: 0.78rem !important;
        border-radius: 12px !important;
        background: linear-gradient(145deg, #5a8a72 0%, #6e9a82 100%) !important;
        color: #fff !important;
    }

    /* Utility row */
    .util-row .stButton > button {
        min-height: 2.2rem !important;
        font-size: 0.8rem !important;
        border-radius: 10px !important;
        padding: 0.35rem 0.75rem !important;
        background: linear-gradient(135deg, #8a9a8c 0%, #9a8e7e 100%) !important;
    }

    .step-flow-caption {
        text-align: center;
        color: #4a5e4a;
        font-size: 0.8rem;
        margin: 0.25rem 0 0.75rem 0;
    }
    .eval-pick-box {
        background: rgba(255, 252, 245, 0.55);
        border: 1px solid rgba(140, 170, 150, 0.35);
        border-radius: 14px;
        padding: 0.5rem 0.75rem 0.25rem;
        margin-bottom: 0.5rem;
    }
    .eval-pick-title {
        font-size: 0.82rem;
        color: #3d5248;
        font-weight: 600;
        margin-bottom: 0.35rem;
        text-align: center;
    }

    .stTextInput > div { margin-bottom: 0.35rem; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background: linear-gradient(135deg, #8daa9a 0%, #6b8a78 100%);
        color: white;
        border-radius: 20px 20px 6px 20px;
        padding: 8px 14px;
        margin: 4px 0;
        max-width: 78%;
        margin-left: auto;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        background: rgba(245, 240, 230, 0.9);
        border-radius: 20px 20px 20px 6px;
        padding: 8px 14px;
        margin: 4px 0;
        max-width: 88%;
        color: #3a4a3a;
        border: 1px solid rgba(200, 180, 140, 0.3);
    }
    hr { border: none; height: 1px; background: linear-gradient(90deg, transparent, #b8a99a, transparent); margin: 0.35rem 0; }

    /* Login primary button */
    .login-area .stButton > button {
        border-radius: 24px !important;
        font-weight: 600 !important;
        min-height: 2.5rem !important;
    }
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

# ========== Login Page ==========
def show_login_page():
    st.markdown('<div class="monet-title">✍️ SRL Writing Coach</div>', unsafe_allow_html=True)
    st.markdown('<div class="monet-subtitle">Self-Regulated Learning · English Writing</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown("""
    <div class="intro-text">
        Four stages: <strong>Plan → Draft → Evaluation → Interaction</strong>
    </div>
    <div class="intro-icon-row">
        <div class="intro-icon-item"><span>📋</span><strong>Plan</strong></div>
        <div class="intro-icon-item"><span>✍️</span><strong>Draft</strong></div>
        <div class="intro-icon-item"><span>📊</span><strong>Evaluation</strong></div>
        <div class="intro-icon-item"><span>💬</span><strong>Interaction</strong></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="login-area">', unsafe_allow_html=True)
    st.markdown("#### Sign in")
    email = st.text_input("Email", placeholder="you@university.edu", key="login_email")
    user_name = st.text_input("Your name", placeholder="e.g., Wei Yutong", key="login_name")
    round_option = st.selectbox("Round", ["Round 1", "Round 2"], key="test_round_select")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        login_clicked = st.button("Start", use_container_width=True, type="primary")
    if login_clicked:
        if email.strip() and user_name.strip():
            round_value = "round_1" if round_option == "Round 1" else "round_2"
            do_login(email.strip(), user_name.strip(), round_value)
            st.rerun()
        else:
            st.warning("Please enter your email and name.")
    st.caption("Your writing is saved automatically after each message.")
    st.markdown("</div>", unsafe_allow_html=True)

# ========== Main App ==========
def main_app():
    cur = st.session_state.current_step
    round_label = round_display(st.session_state.test_round)

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">
        <div>
            <div class="monet-title" style="text-align:left;font-size:1.85rem;margin:0;">✍️ SRL Writing Coach</div>
            <div class="monet-subtitle" style="text-align:left;margin:0;">Plan → Draft → Evaluation → Interaction</div>
        </div>
        <div style="background:rgba(255,248,235,0.45);border-radius:16px;padding:8px 16px;text-align:right;">
            <div style="font-size:0.9rem;font-weight:600;color:#2c4a3e;">{st.session_state.user_name}</div>
            <div style="font-size:0.72rem;color:#5a6e5a;">{st.session_state.user_id}</div>
            <div style="font-size:0.72rem;color:#5a6e5a;">{round_label}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    with st.sidebar:
        st.markdown("""
        <div style="background:rgba(255,248,235,0.35);border-radius:16px;padding:14px;text-align:center;margin-bottom:12px;">
            <span style="font-size:1.6rem;">🎨</span><br>
            <span style="font-weight:600;">Writing Studio</span>
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
        if st.button("Sign out", use_container_width=True):
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

    # ── Step buttons (4 main + util) ──
    st.markdown("#### The 4 steps")
    step_num = {s: i + 1 for i, s in enumerate(STEPS)}
    cur = st.session_state.current_step

    st.markdown('<div class="step-row">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="small")

    def render_step_button(step_key: str, icon: str, on_click):
        css = "step-active" if cur == step_key else "step-inactive"
        label = STEP_LABELS[step_key]
        n = step_num[step_key]
        st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
        st.button(
            f"{icon} Step {n}\n{label}",
            use_container_width=True,
            on_click=on_click,
            key=f"btn_{step_key}",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with c1:
        render_step_button("plan", "📋", action_plan)
    with c2:
        render_step_button("draft", "✍️", action_draft)
    with c3:
        render_step_button("evaluating", "📊", action_open_evaluation)
    with c4:
        render_step_button("interaction", "💬", action_interaction)

    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.show_eval_menu and cur == "evaluating":
        st.markdown('<div class="eval-pick-box">', unsafe_allow_html=True)
        st.markdown(
            '<div class="eval-pick-title">Official CET holistic scoring · pick a mode</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="eval-sub-row">', unsafe_allow_html=True)
        e1, e2 = st.columns(2, gap="small")
        with e1:
            st.button(
                "Feedback only\n(no score)",
                use_container_width=True,
                on_click=action_evaluating_no_score,
                key="btn_eval_feedback",
            )
        with e2:
            st.button(
                "CET score +\nfeedback",
                use_container_width=True,
                on_click=action_evaluating_with_score,
                key="btn_eval_score",
            )
        st.markdown("</div></div>", unsafe_allow_html=True)

    active_label = STEP_LABELS.get(cur, cur.title())
    st.markdown(
        f'<p class="step-flow-caption">You are on <strong>Step {step_num.get(cur, "?")}: {active_label}</strong> '
        f"· Flow: Plan → Draft → Evaluation → Interaction</p>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="util-row">', unsafe_allow_html=True)
    u1, u2, u3, u4, u5 = st.columns([1, 1, 2, 1, 1])
    with u1:
        st.button("Reset", use_container_width=True, on_click=action_reset, key="btn_reset")
    with u5:
        if st.button("Save", use_container_width=True, key="btn_save"):
            if save_current_session():
                st.toast("Saved!", icon="✅")
            else:
                st.toast("Nothing to save yet.", icon="💡")
    st.markdown("</div>", unsafe_allow_html=True)

    st.chat_input("Type your English writing here...", key="user_input", on_submit=handle_input)

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        st.caption("Powered by DeepSeek")
    with fc2:
        st.caption("SRL · CET official 15-pt rubric")
    with fc3:
        st.caption("Data saved securely")

# ========== Run ==========
init_session_state()
if st.session_state.logged_in:
    main_app()
else:
    show_login_page()
