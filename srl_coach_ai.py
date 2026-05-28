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
## Your Role: PLAN Coach
Help the student set writing goals and create an outline using SRL theory.
Steps:
1. Ask for their topic and purpose
2. Help them define a clear thesis
3. Build a 3-part outline (Intro / Body / Conclusion)
4. Ask them to write ONE original opening sentence
Do NOT write the outline for them — guide with questions.
"""

MONITORING_PROMPT = BASE_RULES + """
## Your Role: MONITORING Coach
The student is actively writing. Your job is to help them self-monitor their progress.
Check these dimensions (do NOT score — give targeted feedback only):
1. LOGIC: Is the argument coherent? Do ideas connect?
2. EVIDENCE: Are there concrete examples or data?
3. LANGUAGE: Grammar, vocabulary, sentence variety
4. ORIGINALITY: Is this their own thinking, or copied/AI-generated?
Ask the student to self-assess first, then offer 1-2 specific suggestions.
"""

EVALUATING_PROMPT_NO_SCORE = BASE_RULES + """
## Your Role: EVALUATING Coach (Feedback Only — No Score)
Evaluate the student's writing based on CET-4/6 criteria across 3 dimensions:
1. CONTENT (20%): On-topic, clear argument, sufficient evidence
2. LANGUAGE (35%): Grammar accuracy, fluency, vocabulary range
3. STRUCTURE (40%): Clear framework, paragraph logic, cohesive devices

For each dimension: give specific praise + one concrete improvement suggestion.
Do NOT assign a score. Focus on actionable feedback.
End with: "What will you revise first?"
"""

EVALUATING_PROMPT_WITH_SCORE = BASE_RULES + """
## Your Role: EVALUATING Coach (Score + Feedback)
Evaluate the student's writing using the official CET-4/6 Global Scoring Method.
Scoring bands: 2 / 5 / 8 / 11 / 14 (out of 15), adjustable by ±1.

Score and comment on each dimension:
1. CONTENT (20% weight): Topic relevance, argument clarity, evidence quality
   → Score this dimension out of 3 points
2. LANGUAGE (35% weight): Grammar, vocabulary, fluency, sentence variety
   → Score this dimension out of 5 points  
3. STRUCTURE (40% weight): Framework completeness, paragraph logic, cohesion
   → Score this dimension out of 7 points

Format your response as:
**Content (X/3):** [feedback]
**Language (X/5):** [feedback]
**Structure (X/7):** [feedback]
**Estimated CET Band:** [X/15] — [band name: Excellent/Good/Adequate/Weak/Poor]
**Priority to improve:** [one specific action]
"""

INTERACTION_PROMPT = BASE_RULES + """
## Your Role: INTERACTION Coach
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
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&display=swap');

    .stApp {
        background: linear-gradient(135deg, #c9d4c5 0%, #d4cfc4 20%, #e2dcd0 40%, #ede5d8 60%, #dcd0bd 80%, #c4b8a8 100%);
    }
    .monet-title {
        text-align: center;
        font-family: 'Playfair Display', serif;
        font-size: 2.8rem;
        font-weight: 600;
        color: #2c4a3e;
        margin-bottom: 0.1rem;
    }
    .monet-subtitle {
        text-align: center;
        color: #5a6e5a;
        font-size: 0.8rem;
        font-style: italic;
        margin-bottom: 0.5rem;
    }
    .intro-text {
        text-align: center;
        color: #4a5e4a;
        font-size: 0.9rem;
        max-width: 600px;
        margin: 0 auto;
        line-height: 1.5;
    }
    .intro-icon-row {
        display: flex;
        justify-content: center;
        gap: 1.5rem;
        margin: 1rem 0;
    }
    .intro-icon-item {
        text-align: center;
        font-size: 0.8rem;
        color: #5a6e5a;
    }
    .intro-icon-item span { font-size: 1.5rem; display: block; }
    .login-area { max-width: 300px; margin: 0.5rem auto; text-align: center; }

    /* Default button style */
    .stButton > button {
        background: linear-gradient(135deg, #7c9c8c 0%, #9b8b7a 100%);
        color: white;
        border: none;
        border-radius: 40px;
        padding: 10px 24px;
        font-weight: 500;
        transition: all 0.3s ease;
        white-space: nowrap;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        background: linear-gradient(135deg, #6c8c7c 0%, #8b7b6a 100%);
    }
    /* Active step button — bright highlight */
    .step-active > button {
        background: linear-gradient(135deg, #2c7a5c 0%, #1a5c42 100%) !important;
        box-shadow: 0 0 0 3px #a8d5c2, 0 4px 12px rgba(44,122,92,0.4) !important;
        transform: translateY(-2px) !important;
        font-weight: 700 !important;
    }
    /* Locked button */
    .step-locked > button {
        background: linear-gradient(135deg, #b0b0a8 0%, #c8c0b4 100%) !important;
        color: #f0ebe4 !important;
        opacity: 0.6 !important;
        cursor: not-allowed !important;
    }
    .stTextInput > div { margin-bottom: 0.5rem; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background: linear-gradient(135deg, #8daa9a 0%, #6b8a78 100%);
        color: white;
        border-radius: 24px 24px 8px 24px;
        padding: 8px 16px;
        margin: 4px 0;
        max-width: 75%;
        margin-left: auto;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        background: rgba(245, 240, 230, 0.85);
        backdrop-filter: blur(4px);
        border-radius: 24px 24px 24px 8px;
        padding: 8px 16px;
        margin: 4px 0;
        max-width: 85%;
        color: #3a4a3a;
        border: 1px solid rgba(200,180,140,0.3);
    }
    hr { border: none; height: 1px; background: linear-gradient(90deg, transparent, #b8a99a, transparent); margin: 0.3rem 0; }
</style>
""", unsafe_allow_html=True)

# ========== Session State ==========
def init_session_state():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.user_name = None
        st.session_state.test_round = "pre"
        st.session_state.messages = []
        st.session_state.plan_completed = False
        st.session_state.monitoring_count = 0
        st.session_state.conversation_id = ""
        st.session_state.session_start = ""
        st.session_state.current_step = "plan"   # plan / monitoring / evaluating / interaction
        st.session_state.plan_in_progress = False

def get_system_prompt(step: str, eval_mode: str = "no_score") -> str:
    mapping = {
        "plan":        PLAN_PROMPT,
        "monitoring":  MONITORING_PROMPT,
        "evaluating":  EVALUATING_PROMPT_WITH_SCORE if eval_mode == "score" else EVALUATING_PROMPT_NO_SCORE,
        "interaction": INTERACTION_PROMPT,
    }
    return mapping.get(step, PLAN_PROMPT)

def do_login(user_id: str, user_name: str, test_round: str = "pre"):
    st.session_state.logged_in = True
    st.session_state.user_id = user_id
    st.session_state.user_name = user_name
    st.session_state.test_round = test_round
    st.session_state.messages = []
    st.session_state.plan_completed = False
    st.session_state.monitoring_count = 0
    st.session_state.current_step = "plan"
    st.session_state.plan_in_progress = False
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
    st.session_state.test_round = "pre"
    st.session_state.messages = []
    st.session_state.plan_completed = False
    st.session_state.monitoring_count = 0
    st.session_state.current_step = "plan"
    st.rerun()

# ========== Login Page ==========
def show_login_page():
    st.markdown('<div class="monet-title">✍️ SRL Writing Coach</div>', unsafe_allow_html=True)
    st.markdown('<div class="monet-subtitle">🎨 Self-Regulated Learning · Like painting with words</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown("""
    <div class="intro-text">
        <strong>SRL Writing Coach</strong> guides you through four evidence-based stages:
        <strong>Plan → Monitor → Evaluate → Interact</strong>
    </div>
    <div class="intro-icon-row">
        <div class="intro-icon-item"><span>📋</span><strong>Plan</strong><br>Goals & outline</div>
        <div class="intro-icon-item"><span>✍️</span><strong>Monitor</strong><br>Self-check writing</div>
        <div class="intro-icon-item"><span>📊</span><strong>Evaluate</strong><br>CET feedback</div>
        <div class="intro-icon-item"><span>💬</span><strong>Interact</strong><br>Reflect & debate</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="login-area">', unsafe_allow_html=True)
    st.markdown('<h4 style="text-align:center;margin:0.5rem 0;color:#4a5e4a;">🌸 Sign In</h4>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.75rem;color:#5a6e5a;margin-bottom:0.2rem;">Student ID / Email</p>', unsafe_allow_html=True)
    user_id = st.text_input("", placeholder="e.g., 20240001", key="login_id", label_visibility="collapsed")
    st.markdown('<p style="font-size:0.75rem;color:#5a6e5a;margin-bottom:0.2rem;">Your Name</p>', unsafe_allow_html=True)
    user_name = st.text_input("", placeholder="e.g., Zhang Wei", key="login_name", label_visibility="collapsed")
    st.markdown('<p style="font-size:0.75rem;color:#5a6e5a;margin-bottom:0.2rem;">Test Round</p>', unsafe_allow_html=True)
    test_round_option = st.selectbox("", ["Pre-test", "Post-test"], key="test_round_select", label_visibility="collapsed")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        login_clicked = st.button("🎨 Enter the Garden", use_container_width=True, type="primary")
    if login_clicked:
        if user_id and user_name:
            round_value = "pre" if test_round_option == "Pre-test" else "post"
            do_login(user_id.strip(), user_name.strip(), round_value)
            st.rerun()
        else:
            st.warning("Please enter both Student ID and Name.")
    st.caption("💡 Your writing data is saved automatically.")
    st.markdown('</div>', unsafe_allow_html=True)

# ========== Main App ==========
def main_app():
    # ── Header ──
    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0;">
        <div>
            <div class="monet-title" style="text-align:left;font-size:2rem;">✍️ SRL Writing Coach</div>
            <div class="monet-subtitle" style="text-align:left;">🎨 Self-Regulated Learning · Like painting with words</div>
        </div>
        <div style="background:rgba(255,248,235,0.3);border-radius:40px;padding:6px 18px;text-align:right;">
            <div style="font-size:0.85rem;font-weight:500;color:#2c4a3e;">🎨 {st.session_state.user_name}</div>
            <div style="font-size:0.65rem;color:#6b8a78;">{st.session_state.user_id}</div>
            <div style="font-size:0.65rem;color:#6b8a78;">Round: {st.session_state.test_round}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("""
        <div style="background:rgba(255,248,235,0.25);border-radius:28px;padding:18px;text-align:center;margin-bottom:20px;">
            <span style="font-size:2rem;">🎨🌿</span><br>
            <span style="font-size:1rem;font-weight:500;">Giverny Garden</span><br>
            <span style="font-size:0.75rem;">Your Writing Studio</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"👤 {st.session_state.user_name}")
        st.caption(f"📧 {st.session_state.user_id}")
        st.caption(f"🔄 Round: {st.session_state.test_round}")
        st.divider()
        st.markdown("#### 🌱 Growth Path")
        step = st.session_state.current_step
        plan_done = st.session_state.plan_completed
        mon_count = st.session_state.monitoring_count

        if step == "plan":
            st.info("📍 **Plan** — In progress")
        elif plan_done:
            st.success("✅ **Plan** — Done")
        else:
            st.info("📍 **Plan** — Ready to begin")

        if step == "monitoring":
            st.info(f"✍️ **Monitoring** — Active ({mon_count} checks)")
        elif plan_done and mon_count > 0:
            st.success(f"✅ **Monitoring** — {mon_count} checks")
        elif plan_done:
            st.warning("⏳ **Monitoring** — Write something first")
        else:
            st.caption("🔒 **Monitoring** — Complete Plan first")

        if step == "evaluating":
            st.info("📊 **Evaluating** — In progress")
        elif plan_done and mon_count > 0:
            st.success("🎯 **Evaluating** — Ready")
        else:
            st.caption("🔒 **Evaluating** — Complete Monitoring first")

        if step == "interaction":
            st.info("💬 **Interaction** — In progress")
        elif plan_done:
            st.success("💬 **Interaction** — Available")
        else:
            st.caption("🔒 **Interaction** — Complete Plan first")

        st.divider()
        st.metric("🔄 Monitoring checks", mon_count)
        st.caption(f"📅 Session: {st.session_state.conversation_id[-8:]}")
        st.divider()
        notes = [
            "🌻 Write like planting seeds — one sentence at a time.",
            "🎨 Every great painting starts with a single brushstroke.",
            "📝 Revision is where writing blooms.",
            "🌸 Patience grows beautiful gardens and good writing.",
            "💡 Hemingway wrote 500 words a day.",
            "🖌️ Monet painted water lilies again and again."
        ]
        st.info(f"✨ {random.choice(notes)}")
        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            do_logout()
            st.rerun()

    # ── Chat History ──
    for msg in st.session_state.messages:
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.markdown(msg["content"])

    # ── Core Functions ──
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
        with st.spinner("🎨 Thinking..."):
            response = call_ai(user_input, eval_mode)
        st.session_state.messages.append({"role": "assistant", "content": response})

        # Mark plan done after PLAN button flow
        if st.session_state.get("plan_in_progress") and not st.session_state.plan_completed:
            st.session_state.plan_completed = True
            st.session_state.plan_in_progress = False

        # Count monitoring checks
        if st.session_state.current_step == "monitoring":
            st.session_state.monitoring_count += 1

        try:
            save_current_session()
        except Exception as e:
            print(f"⚠️ Save failed: {e}")

        st.session_state.user_input = ""

    # ── Step Button Actions ──
    def action_plan():
        st.session_state.current_step = "plan"
        st.session_state.plan_in_progress = True
        st.session_state.user_input = "Let's start Step 1: Planning. Please help me set goals and create an outline for my English essay."
        handle_input()

    def action_monitoring():
        if not st.session_state.plan_completed:
            st.session_state.user_input = "I want to go to Monitoring, but I haven't finished Planning yet. Please remind me to complete Step 1 first."
            handle_input()
            return
        st.session_state.current_step = "monitoring"
        last_msg = next((m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"), "")
        if last_msg and len(last_msg) > 30:
            st.session_state.user_input = f"Step 2 — Monitoring. Please help me self-check this writing:\n\n{last_msg}"
        else:
            st.session_state.user_input = "Step 2 — Monitoring. I'm ready to self-check my writing. Please guide me."
        handle_input()

    def action_evaluating_no_score():
        if not st.session_state.plan_completed:
            st.session_state.user_input = "I want Evaluating feedback, but I haven't finished Planning yet. Please remind me."
            handle_input()
            return
        st.session_state.current_step = "evaluating"
        last_msg = next((m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"), "")
        prompt = "Step 3 — Evaluating (feedback only, no score). Please evaluate my writing based on CET criteria."
        if last_msg and len(last_msg) > 30:
            prompt += f"\n\nMy writing:\n{last_msg}"
        st.session_state.user_input = prompt
        handle_input(eval_mode="no_score")

    def action_evaluating_with_score():
        if not st.session_state.plan_completed:
            st.session_state.user_input = "I want a scored evaluation, but I haven't finished Planning yet. Please remind me."
            handle_input()
            return
        st.session_state.current_step = "evaluating"
        last_msg = next((m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"), "")
        prompt = "Step 3 — Evaluating (with CET score). Please score and evaluate my writing."
        if last_msg and len(last_msg) > 30:
            prompt += f"\n\nMy writing:\n{last_msg}"
        st.session_state.user_input = prompt
        handle_input(eval_mode="score")

    def action_interaction():
        if not st.session_state.plan_completed:
            st.session_state.user_input = "I want to go to Interaction, but I haven't finished Planning yet. Please remind me."
            handle_input()
            return
        st.session_state.current_step = "interaction"
        st.session_state.user_input = "Step 4 — Interaction. Please give me a full diagnosis of my writing journey, emotional support, and invite me to critically reflect on your assessment."
        handle_input()

    def action_reset():
        save_current_session()
        st.session_state.messages = []
        st.session_state.plan_completed = False
        st.session_state.monitoring_count = 0
        st.session_state.current_step = "plan"
        st.session_state.plan_in_progress = False
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"✨ **Fresh start, {st.session_state.user_name}!**\n\nTell me your topic and we'll begin with Step 1: Plan.\n\n🎨 *One brushstroke at a time.*"
        })
        st.rerun()

    # ── Step Buttons ──
    cur = st.session_state.current_step
    plan_done = st.session_state.plan_completed

    st.markdown("#### 🎨 The 4 Steps")

    # Row 1: 4 main step buttons
    c1, c2, c3a, c3b, c4 = st.columns([1, 1, 1, 1, 1])

    with c1:
        css = "step-active" if cur == "plan" else "step-locked"
        st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
        st.button("📋 PLAN\n\nGoals & outline", use_container_width=True, on_click=action_plan, key="btn_plan")
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        active = cur == "monitoring"
        locked = not plan_done
        css = "step-active" if active else ("step-locked" if locked else "")
        st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
        st.button("✍️ MONITORING\n\nSelf-check", use_container_width=True, on_click=action_monitoring,
                  disabled=locked, key="btn_monitoring")
        st.markdown('</div>', unsafe_allow_html=True)

    with c3a:
        active = cur == "evaluating"
        locked = not plan_done
        css = "step-active" if active else ("step-locked" if locked else "")
        st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
        st.button("📊 EVALUATE\n\n💬 Feedback only", use_container_width=True,
                  on_click=action_evaluating_no_score, disabled=locked, key="btn_eval_noscr")
        st.markdown('</div>', unsafe_allow_html=True)

    with c3b:
        active = cur == "evaluating"
        locked = not plan_done
        css = "step-active" if active else ("step-locked" if locked else "")
        st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
        st.button("📊 EVALUATE\n\n🎯 Score + feedback", use_container_width=True,
                  on_click=action_evaluating_with_score, disabled=locked, key="btn_eval_scr")
        st.markdown('</div>', unsafe_allow_html=True)

    with c4:
        active = cur == "interaction"
        locked = not plan_done
        css = "step-active" if active else ("step-locked" if locked else "")
        st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
        st.button("💬 INTERACTION\n\nReflect & debate", use_container_width=True,
                  on_click=action_interaction, disabled=locked, key="btn_interaction")
        st.markdown('</div>', unsafe_allow_html=True)

    # Row 2: utility buttons
    u1, u2, u3 = st.columns([1, 1, 1])
    with u1:
        st.button("🔄 Reset", use_container_width=True, on_click=action_reset)
    with u3:
        if st.button("💾 Save", use_container_width=True):
            if save_current_session():
                st.toast("Saved! 🌸", icon="✅")
            else:
                st.toast("Nothing to save yet.", icon="💡")

    st.caption(f"💡 Current step: **{cur.upper()}** · Flow: Plan → Monitoring → Evaluating → Interaction")

    # ── Chat Input ──
    st.chat_input("📝 Type your English writing here...", key="user_input", on_submit=handle_input)

    # ── Footer ──
    c1, c2, c3 = st.columns(3)
    with c1: st.caption("⚡ Powered by DeepSeek")
    with c2: st.caption("🎓 SRL Theory")
    with c3: st.caption("🔒 Your garden, your data")

# ========== Run ==========
init_session_state()
if st.session_state.logged_in:
    main_app()
else:
    show_login_page()
