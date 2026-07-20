import streamlit as st
from openai import OpenAI
from datetime import datetime
import random
import json
import os
import io
import csv
import threading

from ielts_prompt_bank import pick_ielts_prompts, format_ielts_prompts_for_coach

st.set_page_config(
    page_title="SRL Writing Coach",
    page_icon="🪷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========== API Configuration ==========
def get_deepseek_api_key() -> str:
    try:
        return st.secrets.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
    except Exception:
        return os.getenv("DEEPSEEK_API_KEY", "")


DEEPSEEK_API_KEY = get_deepseek_api_key()

# 使用 Streamlit 的缓存机制，只初始化一次，且不阻塞启动
@st.cache_resource
def get_deepseek_client():
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DeepSeek API key is not configured.")
    return OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )

# ========== Google Sheets 配置（免费，替代 Supabase）==========
# 在 Streamlit Cloud → Settings → Secrets 里配置 GOOGLE_SHEET_ID 和 google_sheets_credentials
# 未配置时仍会用本地 JSON 保存，App 照常运行

def _get_sheet_config():
    try:
        sheet_id = st.secrets.get("GOOGLE_SHEET_ID", "")
        creds = st.secrets.get("google_sheets_credentials")
        if sheet_id and creds:
            return sheet_id, dict(creds)
    except Exception:
        pass
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
    if sheet_id and creds_json:
        return sheet_id, json.loads(creds_json)
    return None, None


@st.cache_resource
def _get_google_worksheet():
    import gspread
    from google.oauth2.service_account import Credentials

    sheet_id, creds_dict = _get_sheet_config()
    if not sheet_id or not creds_dict:
        return None
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(sheet_id).sheet1
    # 确保表头存在
    expected_header = [
        "student_id", "student_name", "test_round", "session_id",
        "plan_completed", "monitoring_count", "message_count", "current_step",
        "conversation", "created_at",
    ]
    if not sheet.get_all_values():
        sheet.append_row(expected_header)
    return sheet


def load_all_sessions_from_sheets():
    try:
        sheet = _get_google_worksheet()
        if sheet is None:
            return []
        rows = sheet.get_all_records()
        return rows if rows else []
    except Exception as e:
        print(f"❌ Load sheets error: {e}")
        return []


def save_to_google_sheets(student_id, student_name, test_round, session_id,
                          plan_completed, monitoring_count, message_count,
                          current_step, conversation):
    try:
        sheet = _get_google_worksheet()
        if sheet is None:
            print("ℹ️ Google Sheets not configured — saved locally only.")
            return False
        trimmed = conversation[-30:] if len(conversation) > 30 else conversation
        sheet.append_row([
            student_id,
            student_name,
            test_round,
            session_id,
            plan_completed,
            monitoring_count,
            message_count,
            current_step,
            json.dumps(trimmed, ensure_ascii=False),
            datetime.now().isoformat(),
        ])
        return True
    except Exception as e:
        print(f"❌ Google Sheets error: {e}")
        return False

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
    "evaluating": "Evaluation",
    "interaction": "Interaction",
}
ROUND_LABELS = {"round_1": "Session 1", "round_2": "Session 2", "round_3": "Session 3"}

SESSION_GUIDE = {
    "Session 1": "First visit — explore all four steps at your own pace.",
    "Session 2": "Second visit — try to improve on what you learned last time.",
    "Session 3": "Final visit — reflect on how your writing autonomy has grown.",
}

STEP_TIPS = {
    "plan": "Set your topic, thesis, and outline before you draft. The coach asks — it does not write for you.",
    "draft": "Paste or type your writing here. Ask for feedback on logic, evidence, and language.",
    "evaluating": "Choose feedback-only or a scored rubric (CET / IELTS / TOEFL / Creative).",
    "interaction": "Reflect on your journey. You can agree or push back — both are valuable.",
}


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
        
        # 同步到 Google Sheets（后台线程，不阻塞界面）
        thread = threading.Thread(
            target=save_to_google_sheets,
            kwargs={
                "student_id": st.session_state.user_id,
                "student_name": st.session_state.user_name,
                "test_round": st.session_state.test_round,
                "session_id": st.session_state.conversation_id,
                "plan_completed": st.session_state.plan_completed,
                "monitoring_count": st.session_state.monitoring_count,
                "message_count": len(st.session_state.messages),
                "current_step": st.session_state.current_step,
                "conversation": st.session_state.messages,
            }
        )
        thread.start()
        return True
    return False

# ========== System Prompts ==========
BASE_RULES = """## CRITICAL RULES
- RESPOND IN 100% ENGLISH. NO CHINESE.
- NEVER write full paragraphs for the student.
- End every response with ONE small actionable next step.

## COPYING POLICY (strict — avoid false accusations)
- Accuse copying ONLY if the student repeats a **full model sentence you gave** with ≥90% identical wording in the same order.
- These are NOT copying: filling in your template with their own ideas; using your sentence pattern with different content; paraphrasing; answering your question in their own words; combining your structure with original reasons/examples.
- If the student says they did not copy, **believe them**, apologize briefly if you were wrong, and continue coaching. Do not repeat the copying warning in the same session unless they paste your text again verbatim.
"""

SCORE_FRAMEWORK_LABELS = {
    "cet": "CET-4/6",
    "ielts": "IELTS",
    "toefl": "TOEFL",
    "creative": "Creative (100 pts)",
}

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

EVALUATING_PROMPT_CET_SCORE = BASE_RULES + CET_OFFICIAL_RUBRIC + """
## Your Role: EVALUATION Coach — CET-4/CET-6 Scored (Step 3)
Apply holistic impression scoring exactly as in the official CET table above.

Process:
1. Judge on Relevance, Clarity, Coherence, and Language accuracy.
2. Select the **single best-matching tier** (14 / 11 / 8 / 5 / 2).
3. Assign a score **within that tier's range** (±1 within tier if warranted).

Required format:
**Relevance:** … **Clarity:** … **Coherence:** … **Language accuracy:** …
**Official tier:** [14/11/8/5/2-pt] — [descriptor]
**CET Writing Score:** [X/15]
**Priority to improve:** [one action]
"""

IELTS_TASK2_RUBRIC = """
## IELTS Academic Writing Task 2 — Band Descriptors (summary)
Four criteria (each contributes to overall band 0–9, reported in 0.5 steps):
1. **Task Response (TR):** Address the prompt; clear position; ideas extended and supported.
2. **Coherence & Cohesion (CC):** Logical organisation; clear progression; appropriate cohesive devices.
3. **Lexical Resource (LR):** Range, precision, appropriacy; spelling/word formation.
4. **Grammatical Range & Accuracy (GRA):** Variety of structures; error frequency and impact on communication.
Bands 9→1: fully addresses task with depth → minimal/no coherent message. Band 0 if off-topic, not English, or wholly copied.
"""

EVALUATING_PROMPT_IELTS_SCORE = BASE_RULES + IELTS_TASK2_RUBRIC + """
## Your Role: EVALUATION Coach — IELTS Task 2 Scored (Step 3)
Score as an IELTS examiner using Task 2 band descriptors (essay / opinion / discussion tasks).

Process:
1. Score each criterion: TR, CC, LR, GRA (bands 0–9, half-bands allowed, e.g. 6.5).
2. Explain evidence from the student's draft for each.
3. Give **Overall Band** (average of four, rounded to nearest 0.5).

Required format:
**Task Response:** [band] — [comment]
**Coherence & Cohesion:** [band] — [comment]
**Lexical Resource:** [band] — [comment]
**Grammatical Range & Accuracy:** [band] — [comment]
**Overall IELTS Band:** [X.X/9]
**Priority to improve:** [one action]
"""

TOEFL_INDEPENDENT_RUBRIC = """
## TOEFL iBT Independent Writing (Academic Discussion style) — 0–5 each dimension
**Content (0–5):** Relevant, well-elaborated explanations, examples, details (5) → words/phrases only, no coherent ideas (1) → blank/off-topic/copied (0).
**Language Expression (0–5):** Variety of syntax + precise idiomatic word choice (5) → severely limited (1).
**Grammar (0–5):** Few errors (4–5) → serious frequent errors (1).
1-point note: minimal original language / mostly borrowed from stimulus → 1. Entirely copied from prompt → 0.
"""

TOEFL_INTEGRATED_RUBRIC = """
## TOEFL iBT Integrated Writing — 0–5 each dimension
**Content (0–5):** Select important lecture points and relate accurately to reading (5) → little/no relevant lecture content (1) → merely copies reading (0).
**Expression (0–5):** Well-organized; minor errors OK (5) → errors obscure meaning (2) → language too low to derive meaning (1).
If the task is NOT integrated (no lecture vs reading), use Independent rubric instead and say so briefly.
"""

EVALUATING_PROMPT_TOEFL_SCORE = BASE_RULES + TOEFL_INDEPENDENT_RUBRIC + TOEFL_INTEGRATED_RUBRIC + """
## Your Role: EVALUATION Coach — TOEFL Scored (Step 3)
Default to **Independent / Academic Discussion** scoring (Content + Language Expression + Grammar, each 0–5).
If the draft clearly summarizes lecture vs reading, use **Integrated** (Content + Expression, each 0–5).

Required format:
**Content:** [X/5] — [comment]
**Language Expression:** [X/5] — [comment]  (or **Expression** for integrated)
**Grammar:** [X/5] — [comment]  (independent only; omit if integrated-only)
**Estimated total:** [sum or holistic summary /30 or /10 as appropriate]
**Priority to improve:** [one action]
"""

EVALUATING_PROMPT_CREATIVE_SCORE = BASE_RULES + """
## Your Role: EVALUATION Coach — Creative Writing / Holistic Rank (Step 3, 100-point scale)
For creative, narrative, or personal writing where exam rubrics do not apply. Give a **holistic score out of 100** plus dimensional feedback.

Dimensions (each out of 25, sum = 100):
1. **Ideas & originality (25):** Voice, imagination, insight, engagement.
2. **Structure & flow (25):** Opening, development, pacing, ending.
3. **Language & style (25):** Word choice, imagery, tone, sentence variety.
4. **Mechanics (25):** Grammar, spelling, punctuation (do not over-penalize if voice is strong).

Required format:
**Ideas & originality:** [X/25] — …
**Structure & flow:** [X/25] — …
**Language & style:** [X/25] — …
**Mechanics:** [X/25] — …
**Overall score:** [X/100] — [one-line rank label: e.g. Strong / Developing / Emerging]
**What to try next:** [one creative revision task]
"""

EVALUATING_PROMPT_NO_SCORE = BASE_RULES + """
## Your Role: EVALUATION Coach — Feedback Only (Step 3, no score)
Give rich qualitative feedback on academic/creative writing. Do **not** assign exam scores or bands.

Comment on: relevance to topic, clarity of ideas, organization/cohesion, language use, and originality.
For each area: one strength + one specific improvement tied to their draft.
End with: "What will you revise first?"
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

# ========== CSS — Premium Monet Garden (nfmedipath-inspired) ==========
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&display=swap');

    :root {
        --giverny-sage: #5f8a72;
        --giverny-sage-light: #8fb39a;
        --giverny-pond: #6b9e8f;
        --giverny-lavender: #c8b8d8;
        --giverny-rose: #ddb8c8;
        --giverny-cream: #faf6ef;
        --giverny-paper: #f3ede4;
        --giverny-ink: #3a5248;
        --giverny-muted: #6a7f74;
        --font-display: 'Cormorant Garamond', Georgia, serif;
        --font-body: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        --step-h: 3.35rem;
        --chat-gap: 1.15rem;
        --glass: rgba(255, 253, 250, 0.72);
        --glass-border: rgba(255, 255, 255, 0.65);
    }

    .stApp {
        background:
            radial-gradient(ellipse 80% 60% at 10% 15%, rgba(184, 212, 232, 0.35), transparent 55%),
            radial-gradient(ellipse 70% 50% at 90% 25%, rgba(200, 184, 216, 0.28), transparent 50%),
            radial-gradient(ellipse 60% 45% at 50% 90%, rgba(168, 197, 160, 0.22), transparent 55%),
            linear-gradient(165deg, #faf7f2 0%, #f5f0e8 40%, #eef4f0 100%);
        background-attachment: fixed;
        font-family: var(--font-body);
        color: var(--giverny-ink);
    }

    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1320px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(250, 246, 239, 0.98), rgba(232, 242, 236, 0.96)) !important;
        border-right: 1px solid rgba(95, 138, 114, 0.16) !important;
        backdrop-filter: blur(8px);
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
        box-shadow: 0 4px 16px rgba(77, 117, 96, 0.28) !important;
    }
    .stButton > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(145deg, #456a58, #5f8a72) !important;
        border-color: rgba(255,255,255,0.55) !important;
        color: #fff !important;
        transform: translateY(-1px);
    }
    button[data-testid="stBaseButton-primary"] p,
    button[data-testid="stBaseButton-primary"] div {
        color: #fff !important;
    }

    .monet-title {
        font-family: var(--font-display);
        font-size: clamp(2rem, 5vw, 3.2rem);
        font-weight: 700;
        color: var(--giverny-ink);
        letter-spacing: 0.01em;
        line-height: 1.15;
    }
    .monet-subtitle {
        font-family: var(--font-body);
        color: var(--giverny-muted);
        font-size: 1.05rem;
        font-weight: 400;
        letter-spacing: 0.02em;
    }
    .section-label {
        font-family: var(--font-body);
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: var(--giverny-pond);
        margin-bottom: 0.75rem;
    }
    .gradient-text {
        background: linear-gradient(120deg, #4a735f 0%, #6b9e8f 45%, #8bb8d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .glass-panel {
        background: var(--glass);
        backdrop-filter: blur(20px) saturate(1.2);
        -webkit-backdrop-filter: blur(20px) saturate(1.2);
        border: 1px solid var(--glass-border);
        border-radius: 28px;
        box-shadow: 0 8px 40px rgba(58, 82, 72, 0.08), inset 0 1px 0 rgba(255,255,255,0.8);
        padding: 1.75rem 2rem;
    }
    .hero-eyebrow {
        display: inline-block;
        padding: 0.35rem 1rem;
        border-radius: 999px;
        background: rgba(107, 158, 143, 0.12);
        border: 1px solid rgba(107, 158, 143, 0.25);
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--giverny-pond);
        margin-bottom: 1.25rem;
    }
    .journey-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.85rem;
        margin: 1.5rem 0;
    }
    .journey-card {
        background: rgba(255,255,255,0.55);
        border: 1px solid rgba(143, 179, 154, 0.2);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
        position: relative;
        overflow: hidden;
    }
    .journey-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 28px rgba(58, 82, 72, 0.1);
    }
    .journey-card .j-num {
        font-family: var(--font-display);
        font-size: 2rem;
        font-weight: 600;
        color: rgba(107, 158, 143, 0.35);
        line-height: 1;
        margin-bottom: 0.35rem;
    }
    .journey-card h4 {
        font-family: var(--font-display);
        font-size: 1.15rem;
        font-weight: 600;
        margin: 0 0 0.25rem;
        color: var(--giverny-ink);
    }
    .journey-card p {
        font-size: 0.78rem;
        color: var(--giverny-muted);
        margin: 0;
        line-height: 1.45;
    }
    .trust-row {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        margin-top: 1.25rem;
        font-size: 0.8rem;
        color: var(--giverny-muted);
    }
    .trust-item {
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-in {
        animation: fadeUp 0.7s ease-out forwards;
    }
    .monet-badge {
        background: linear-gradient(135deg, rgba(255,252,248,0.9), rgba(232,245,238,0.82));
        border: 1px solid rgba(95, 138, 114, 0.22);
        border-radius: 18px;
        padding: 10px 18px;
        box-shadow: 0 8px 24px rgba(58, 82, 72, 0.08);
    }
    .monet-card {
        background: var(--glass);
        backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border);
        border-radius: 24px;
        padding: 1.25rem 1.5rem;
        margin: 0.5rem 0 1.1rem;
        box-shadow: 0 10px 40px rgba(58, 82, 72, 0.07);
    }
    .login-shell {
        max-width: 100%;
        margin: 0;
        padding: 0;
    }
    #login-form-marker {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }
    [data-testid="column"]:has(#login-form-marker) {
        background: var(--glass);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        border-radius: 28px;
        padding: 1.75rem 1.85rem 1.25rem !important;
        box-shadow: 0 16px 48px rgba(58, 82, 72, 0.1);
    }
    .form-title {
        font-family: var(--font-display);
        font-size: 1.65rem;
        font-weight: 600;
        margin: 0 0 0.25rem;
        color: var(--giverny-ink);
    }
    .form-sub {
        font-size: 0.88rem;
        color: var(--giverny-muted);
        margin-bottom: 1.25rem;
    }

    .chat-header-bar {
        width: 100%;
        max-width: 100%;
        margin: 0 0 0.85rem;
        background: linear-gradient(135deg, rgba(255,252,248,0.92), rgba(232,245,238,0.82));
        border: 1px solid rgba(143, 179, 154, 0.22);
        border-radius: 22px;
        padding: 0.85rem 1.25rem;
        box-shadow: 0 8px 28px rgba(58, 82, 72, 0.06);
    }
    .chat-header-bar .header-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.65rem;
    }
    .chat-header-bar .header-title {
        font-family: var(--font-display);
        font-size: clamp(1.25rem, 2.5vw, 1.65rem);
        font-weight: 600;
        color: var(--giverny-ink);
        margin: 0;
    }
    .chat-header-bar .header-meta {
        font-size: 0.78rem;
        color: var(--giverny-muted);
    }
    .chat-header-bar .step-pill {
        display: inline-block;
        padding: 0.28rem 0.75rem;
        border-radius: 999px;
        background: rgba(107, 158, 143, 0.14);
        border: 1px solid rgba(107, 158, 143, 0.28);
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--giverny-pond);
    }
    .chat-stage {
        width: 100%;
        min-height: 42vh;
    }
    .studio-panel {
        background: linear-gradient(165deg, rgba(255,253,250,0.94), rgba(232,245,238,0.88));
        border: 1px solid rgba(143, 179, 154, 0.28);
        border-radius: 24px;
        padding: 1.15rem 1.1rem 1rem;
        box-shadow: 0 12px 36px rgba(58, 82, 72, 0.08), inset 0 1px 0 rgba(255,255,255,0.85);
    }
    .studio-panel .panel-brand {
        text-align: center;
        padding-bottom: 0.65rem;
        margin-bottom: 0.65rem;
        border-bottom: 1px solid rgba(143, 179, 154, 0.2);
    }
    .studio-panel .panel-brand h3,
    .panel-brand h3 {
        font-family: var(--font-display);
        font-size: 1.35rem;
        font-weight: 600;
        margin: 0.15rem 0 0;
        color: var(--giverny-ink);
    }
    .panel-brand p {
        font-size: 0.72rem;
        color: var(--giverny-muted);
        margin: 0.2rem 0 0;
    }
    [data-testid="column"]:has(#studio-column-marker) {
        background: linear-gradient(165deg, rgba(255,253,250,0.94), rgba(232,245,238,0.88));
        border: 1px solid rgba(143, 179, 154, 0.28);
        border-radius: 24px;
        padding: 1rem 0.9rem 0.85rem !important;
        box-shadow: 0 12px 36px rgba(58, 82, 72, 0.08), inset 0 1px 0 rgba(255,255,255,0.85);
        align-self: flex-start;
    }
    [data-testid="column"]:has(#studio-column-marker) .panel-brand {
        text-align: center;
        padding-bottom: 0.65rem;
        margin-bottom: 0.5rem;
        border-bottom: 1px solid rgba(143, 179, 154, 0.2);
    }
    .studio-step-card {
        background: rgba(255,255,255,0.62);
        border: 1px solid rgba(143, 179, 154, 0.18);
        border-radius: 14px;
        padding: 0.55rem 0.65rem;
        margin-bottom: 0.45rem;
        font-size: 0.78rem;
        color: var(--giverny-muted);
        line-height: 1.4;
    }
    .studio-step-card.active {
        border-color: rgba(95, 138, 114, 0.45);
        background: rgba(232, 245, 238, 0.75);
        color: var(--giverny-ink);
    }
    .studio-step-card.done {
        border-color: rgba(95, 138, 114, 0.3);
    }
    .studio-step-card strong {
        font-family: var(--font-display);
        font-size: 0.95rem;
        color: var(--giverny-ink);
    }
    .studio-tip-box {
        background: rgba(107, 158, 143, 0.1);
        border: 1px solid rgba(107, 158, 143, 0.22);
        border-radius: 14px;
        padding: 0.65rem 0.75rem;
        font-size: 0.82rem;
        color: var(--giverny-ink);
        line-height: 1.5;
        margin: 0.5rem 0 0.65rem;
    }
    .studio-user-chip {
        font-size: 0.78rem;
        color: var(--giverny-muted);
        margin: 0.15rem 0;
    }
    #chat-column-marker,
    #studio-column-marker,
    .chat-stage-marker {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .app-shell-marker { display: none !important; }
    div:has(> .app-shell-marker) {
        max-width: 1320px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    div:has(> #chat-column-marker) > [data-testid="stVerticalBlock"] {
        max-width: 860px;
        margin-left: auto !important;
        margin-right: auto !important;
        width: 100%;
    }
    .logged-in-hide-sidebar [data-testid="stSidebar"],
    .logged-in-hide-sidebar [data-testid="collapsedControl"],
    .logged-in-hide-sidebar button[kind="header"] {
        display: none !important;
    }
    .logged-in-hide-sidebar .block-container {
        padding-top: 1rem !important;
        max-width: 1320px !important;
        margin: 0 auto !important;
    }
    .main-step-row-marker { display: none; }
    div:has(> .main-step-row-marker) + div [data-testid="stHorizontalBlock"] {
        max-width: 860px;
        margin: 0 auto 0.75rem !important;
    }
    .intro-text {
        text-align: center;
        color: var(--giverny-muted);
        font-size: 0.95rem;
        max-width: 560px;
        margin: 0 auto;
        line-height: 1.6;
    }
    .intro-icon-row {
        display: flex;
        justify-content: center;
        gap: 0.8rem;
        margin: 1.1rem 0;
        flex-wrap: wrap;
    }
    .intro-icon-item {
        text-align: center;
        font-size: 0.76rem;
        color: var(--giverny-muted);
        padding: 0.85rem 0.75rem;
        border-radius: 18px;
        background: rgba(255,255,255,0.6);
        border: 1px solid rgba(143, 179, 154, 0.22);
        min-width: 90px;
        box-shadow: 0 4px 16px rgba(58, 82, 72, 0.05);
        transition: transform 0.2s ease;
    }
    .intro-icon-item:hover { transform: translateY(-2px); }
    .intro-icon-item span { font-size: 1.35rem; display: block; margin-bottom: 0.15rem; }

    .monet-steps-header {
        font-family: var(--font-display);
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--giverny-ink);
        margin: 1.5rem 0 0.85rem;
        text-align: center;
    }
    .step-flow-caption {
        text-align: center;
        color: var(--giverny-muted);
        font-size: 0.95rem;
        margin: 1rem 0 1.2rem;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-style: italic;
    }
    .eval-pick-box {
        background: linear-gradient(135deg, rgba(255,252,248,0.94), rgba(232,245,238,0.84));
        border: 1px solid rgba(95, 138, 114, 0.28);
        border-radius: 16px;
        padding: 0.7rem 0.85rem 0.6rem;
        margin: 0.4rem 0 0.8rem;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
    }
    .eval-pick-title {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 1rem;
        color: var(--giverny-ink);
        font-weight: 600;
        text-align: center;
        margin-bottom: 0.4rem;
    }

    .stTextInput > div > div,
    .stTextArea > div > div {
        background: linear-gradient(180deg, rgba(255,253,250,0.98), rgba(244,248,242,0.96)) !important;
        border: 1.5px solid rgba(95, 138, 114, 0.6) !important;
        border-radius: 14px !important;
        box-shadow: inset 0 1px 3px rgba(58, 82, 72, 0.08), 0 4px 12px rgba(58, 82, 72, 0.05) !important;
    }
    .stTextInput input,
    .stTextArea textarea {
        color: #21362d !important;
        font-weight: 600 !important;
    }
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: #7a8d84 !important;
        font-weight: 500;
    }

    div[data-testid="stChatMessage"] {
        margin-bottom: var(--chat-gap) !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background: linear-gradient(135deg, #f3f8f5 0%, #edf5f0 100%) !important;
        color: var(--giverny-ink) !important;
        border: 1px solid rgba(143, 179, 154, 0.22) !important;
        border-radius: 20px 20px 4px 20px !important;
        padding: 1.1rem 1.3rem !important;
        max-width: 88% !important;
        margin-left: auto !important;
        box-shadow: 0 5px 16px rgba(58, 82, 72, 0.05) !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        background: linear-gradient(135deg, rgba(255,253,250,0.98), rgba(250,248,245,0.96)) !important;
        border: 1px solid rgba(143, 179, 154, 0.22) !important;
        border-radius: 20px 20px 20px 4px !important;
        color: var(--giverny-ink) !important;
        max-width: 96% !important;
        padding: 1.2rem 1.4rem !important;
        box-shadow: 0 5px 18px rgba(58, 82, 72, 0.04) !important;
        line-height: 1.65 !important;
    }
    div[data-testid="stChatMessage"] .stMarkdown {
        line-height: 1.65 !important;
    }
    div[data-testid="stChatInput"] {
        border-radius: 18px !important;
        border: 1.5px solid rgba(95, 138, 114, 0.68) !important;
        background: linear-gradient(135deg, rgba(255,253,250,0.98), rgba(242,248,243,0.96)) !important;
        box-shadow: 0 8px 24px rgba(58, 82, 72, 0.08) !important;
        padding: 0.25rem 0.3rem 0.25rem 0.35rem !important;
    }
    div[data-testid="stChatInput"] textarea {
        color: #21362d !important;
        font-weight: 600 !important;
        min-height: 3rem !important;
    }
    div[data-testid="stChatInput"] textarea::placeholder {
        color: #7c9186 !important;
        font-weight: 500;
    }
    div[data-testid="stChatInput"] button {
        border-radius: 999px !important;
        background: linear-gradient(145deg, #4d7560, #6d9a7e) !important;
        color: #fff !important;
        border: none !important;
    }
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(143,179,154,0.5), transparent);
        margin: 0.45rem 0;
    }
    #MainMenu, footer, header { visibility: hidden; }

    .st-key-btn_login_start button,
    .st-key-btn_login_start [data-testid="stBaseButton-primary"] {
        border-radius: 20px !important;
        min-height: 2.5rem !important;
    }

    @media (min-width: 1024px) {
        .block-container {
            max-width: 1280px !important;
        }
        [data-testid="stSidebar"] {
            min-width: 300px !important;
            max-width: 340px !important;
        }
    }

    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            max-width: 100% !important;
        }
        .chat-header-bar {
            padding: 0.75rem 1rem;
            border-radius: 18px;
        }
        .chat-stage {
            min-height: 36vh;
        }
        .journey-grid {
            grid-template-columns: 1fr !important;
        }
        .monet-title {
            font-size: 1.85rem;
        }
        .monet-subtitle {
            font-size: 0.95rem;
        }
        .monet-card {
            padding: 1rem 1rem 0.95rem;
        }
        .login-shell {
            max-width: 100%;
            padding: 1rem 1rem 1.05rem;
        }
        .intro-icon-item {
            flex: 1 1 calc(50% - 0.45rem);
            min-width: 0;
        }
        div:has(> #srl-step-grid-marker) + div [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.45rem !important;
        }
        div:has(> #srl-step-grid-marker) + div [data-testid="column"] {
            flex: 0 0 calc(50% - 0.25rem) !important;
            max-width: calc(50% - 0.25rem) !important;
        }
        .step-flow-caption {
            font-size: 0.86rem;
        }
        [data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
            max-width: 100% !important;
        }
    }

    @media (max-width: 480px) {
        .monet-title {
            font-size: 1.45rem;
        }
        .monet-steps-header {
            font-size: 1.1rem;
            margin-top: 1.1rem;
        }
        .intro-icon-item {
            flex-basis: 100%;
        }
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
        st.session_state.show_eval_score_menu = False
        st.session_state.eval_score_framework = "ielts"
        st.session_state.completed_steps = set()  # 记录已完成的步骤
        st.session_state.show_draft_choice = False # 新增：是否显示 Draft 分支选择
    elif st.session_state.get("current_step") == "monitoring":
        st.session_state.current_step = "draft"
    if "completed_steps" not in st.session_state: # 兼容旧数据
        st.session_state.completed_steps = set()
    if "show_draft_choice" not in st.session_state:
        st.session_state.show_draft_choice = False
    if "research_authenticated" not in st.session_state:
        st.session_state.research_authenticated = False

def get_research_password() -> str:
    try:
        return st.secrets.get("RESEARCH_PASSWORD", "srl2026")
    except Exception:
        return os.getenv("RESEARCH_PASSWORD", "srl2026")

def get_system_prompt(step: str, eval_mode: str = "no_score",
                      score_framework: str = "cet") -> str:
    if step == "evaluating":
        if eval_mode == "no_score":
            return EVALUATING_PROMPT_NO_SCORE
        score_map = {
            "cet": EVALUATING_PROMPT_CET_SCORE,
            "ielts": EVALUATING_PROMPT_IELTS_SCORE,
            "toefl": EVALUATING_PROMPT_TOEFL_SCORE,
            "creative": EVALUATING_PROMPT_CREATIVE_SCORE,
        }
        return score_map.get(score_framework, EVALUATING_PROMPT_CET_SCORE)
    mapping = {
        "plan":        PLAN_PROMPT,
        "draft":       DRAFT_PROMPT,
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
    st.session_state.show_eval_score_menu = False
    st.session_state.eval_score_framework = "ielts"
    st.session_state.conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.session_start = datetime.now().isoformat()
    st.session_state.messages.append({
        "role": "assistant",
        "content": (
            f"👋 **Welcome, {user_name}!**\n\n"
            "This coach is designed for **English learners at every level** — with strong support for "
            "**IELTS** and **TOEFL** writing, plus CET and creative rubrics.\n\n"
            "Share your topic (or say you have no idea — I'll offer prompts from our question bank).\n\n"
            "**Click Plan · Draft · Evaluation · Interaction** on the left to begin each step.\n\n"
            "---\n🪷 *Your writing garden — one thoughtful step at a time.*"
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
    st.session_state.show_eval_score_menu = False
    st.rerun()

def round_display(value: str) -> str:
    legacy = {"pre": "Round 1", "post": "Round 2"}
    if value in legacy:
        return legacy[value]
    return ROUND_LABELS.get(value, value.replace("_", " ").title())


STEP_BUTTON_KEYS = {s: f"btn_{s}" for s in STEPS}


def _st_key(key: str) -> str:
    """Streamlit 1.57: widget key becomes CSS class st-key-<key> on the widget root."""
    return f".st-key-{key}"


def inject_css_block(css: str) -> None:
    """Inject raw CSS (st.html if available, else markdown)."""
    if hasattr(st, "html"):
        st.html(f"<style>{css}</style>")
    else:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def inject_step_button_styles(active_step: str) -> None:
    """Giverny step styles — optimized for Streamlit 1.57 (.st-key-* selectors)."""
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
        /* Step row layout (Streamlit 1.57) */
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
        opacity = "1" if on else "0.88"
        col_sel = (
            f'div:has(> #sticky-step-bar-marker) + div '
            f'[data-testid="column"]:nth-child({col_idx[step]}) button'
        )
        for suffix in ("", "_panel", "_bar"):
            sk = _st_key(key + suffix)
            block = f"{sk} button, {sk} [data-testid='stBaseButton-secondary'], {sk} [data-testid='stBaseButton-primary']"
            if suffix == "_bar":
                block += f", {col_sel}"
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
        """)

    eval_bg = "linear-gradient(155deg, #5a7d68 0%, #7a9f88 100%)"
    for key in (
        "btn_eval_feedback", "btn_eval_score_menu",
        "btn_eval_cet", "btn_eval_ielts", "btn_eval_toefl", "btn_eval_creative",
    ):
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


def inject_garden_app_layout_css() -> None:
    """Fixed left panel + scrollable chat column — full viewport, no page jump."""
    inject_css_block("""
    /* ── Garden app shell: lock to viewport ── */
    .stApp, [data-testid="stAppViewContainer"], .main {
        overflow: hidden !important;
        height: 100dvh !important;
        max-height: 100dvh !important;
    }
    .block-container {
        padding-top: 0.35rem !important;
        padding-bottom: 0.35rem !important;
        max-width: 100% !important;
        height: calc(100dvh - 0.5rem) !important;
        max-height: calc(100dvh - 0.5rem) !important;
        overflow: hidden !important;
    }
    div:has(> .app-shell-marker) + div[data-testid="stHorizontalBlock"] {
        height: calc(100dvh - 1rem) !important;
        max-height: calc(100dvh - 1rem) !important;
        align-items: stretch !important;
        gap: 0.85rem !important;
        overflow: hidden !important;
    }

    /* ── Left studio panel: fixed, full height, internal scroll ── */
    [data-testid="column"]:has(#studio-column-marker) {
        position: relative !important;
        flex: 0 0 min(340px, 32vw) !important;
        max-width: 340px !important;
        height: calc(100dvh - 1rem) !important;
        max-height: calc(100dvh - 1rem) !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        background:
            radial-gradient(ellipse at 20% 10%, rgba(200,184,216,0.18), transparent 55%),
            radial-gradient(ellipse at 80% 90%, rgba(168,197,160,0.15), transparent 50%),
            linear-gradient(175deg, rgba(255,253,250,0.96), rgba(232,245,238,0.92)) !important;
        border: 1px solid rgba(143, 179, 154, 0.32) !important;
        border-radius: 26px !important;
        padding: 0.85rem 0.75rem 0.75rem !important;
        box-shadow: 0 16px 48px rgba(58, 82, 72, 0.1), inset 0 1px 0 rgba(255,255,255,0.9) !important;
        scrollbar-width: thin;
        scrollbar-color: rgba(95,138,114,0.35) transparent;
    }
    [data-testid="column"]:has(#studio-column-marker)::-webkit-scrollbar { width: 4px; }
    [data-testid="column"]:has(#studio-column-marker)::-webkit-scrollbar-thumb {
        background: rgba(95,138,114,0.35); border-radius: 4px;
    }

    /* ── Right chat column: flex column, messages scroll, input pinned ── */
    [data-testid="column"]:has(#chat-column-marker) {
        flex: 1 1 auto !important;
        min-width: 0 !important;
        height: calc(100dvh - 1rem) !important;
        max-height: calc(100dvh - 1rem) !important;
        overflow: hidden !important;
        display: flex !important;
        flex-direction: column !important;
        background:
            radial-gradient(ellipse at 90% 15%, rgba(184,212,232,0.2), transparent 50%),
            radial-gradient(ellipse at 10% 85%, rgba(221,184,200,0.12), transparent 45%),
            linear-gradient(160deg, rgba(255,253,250,0.55), rgba(250,246,239,0.45)) !important;
        border: 1px solid rgba(143, 179, 154, 0.2) !important;
        border-radius: 26px !important;
        padding: 0.65rem 0.85rem 0.55rem !important;
        box-shadow: 0 12px 40px rgba(58, 82, 72, 0.07) !important;
    }
    [data-testid="column"]:has(#chat-column-marker) > [data-testid="stVerticalBlock"] {
        height: 100% !important;
        max-height: 100% !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        display: block !important;
        max-width: 100% !important;
        margin: 0 !important;
        scroll-behavior: smooth !important;
        scrollbar-width: thin;
    }
    div:has(> #sticky-step-bar-marker),
    div:has(> .garden-step-prompt) {
        position: sticky !important;
        top: 0 !important;
        z-index: 21 !important;
        background: linear-gradient(180deg, rgba(250,246,239,0.99), rgba(250,246,239,0.92)) !important;
    }
    div:has(> .garden-step-prompt) + div[data-testid="stHorizontalBlock"] {
        position: sticky !important;
        top: 2.1rem !important;
        z-index: 20 !important;
        background: rgba(250,246,239,0.97) !important;
        padding-bottom: 0.35rem !important;
        margin-bottom: 0.25rem !important;
    }
    #chat-scroll-region-start { display: none !important; }
    [data-testid="column"]:has(#chat-column-marker) div[data-testid="stChatInput"] {
        position: sticky !important;
        bottom: 0 !important;
        z-index: 15 !important;
        background: linear-gradient(0deg, rgba(250,246,239,0.99) 80%, rgba(250,246,239,0)) !important;
        padding-top: 0.5rem !important;
        margin-top: 0.5rem !important;
    }

    /* Monet chat bubbles */
    [data-testid="column"]:has(#chat-column-marker) div[data-testid="stChatMessage"] {
        margin-bottom: 0.75rem !important;
    }
    [data-testid="column"]:has(#chat-column-marker) div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background: linear-gradient(135deg, rgba(255,253,250,0.98), rgba(238,244,240,0.95)) !important;
        border: 1px solid rgba(143,179,154,0.25) !important;
        box-shadow: 0 6px 20px rgba(58,82,72,0.06) !important;
    }
    [data-testid="column"]:has(#chat-column-marker) div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: linear-gradient(135deg, rgba(232,245,238,0.95), rgba(216,232,220,0.9)) !important;
        border: 1px solid rgba(107,158,143,0.28) !important;
    }

    .garden-step-prompt {
        text-align: center;
        font-family: var(--font-display);
        font-size: 0.95rem;
        color: var(--giverny-pond);
        letter-spacing: 0.04em;
        margin: 0 0 0.35rem;
        padding: 0.35rem 0.5rem;
        border-radius: 12px;
        background: rgba(107,158,143,0.08);
        border: 1px dashed rgba(107,158,143,0.25);
    }
    .chat-header-bar {
        border-radius: 18px !important;
        margin-bottom: 0.5rem !important;
        background: linear-gradient(135deg, rgba(255,252,248,0.95), rgba(232,245,238,0.88)) !important;
        border: 1px solid rgba(143,179,154,0.22) !important;
        box-shadow: 0 4px 16px rgba(58,82,72,0.05) !important;
        padding: 0.65rem 1rem !important;
    }
    .chat-header-bar .header-title {
        font-family: var(--font-display);
        background: linear-gradient(120deg, #4a735f, #6b9e8f, #8bb8d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    @media (max-width: 900px) {
        div:has(> .app-shell-marker) + div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
        }
        [data-testid="column"]:has(#studio-column-marker),
        [data-testid="column"]:has(#chat-column-marker) {
            max-width: 100% !important;
            flex: 1 1 auto !important;
            height: auto !important;
            max-height: none !important;
        }
        [data-testid="column"]:has(#chat-column-marker) {
            min-height: 65dvh !important;
        }
        div:has(> #chat-scroll-region-start) { max-height: none !important; }
        .stApp, [data-testid="stAppViewContainer"], .main, .block-container {
            height: auto !important;
            max-height: none !important;
            overflow: auto !important;
        }
    }
    """)


def inject_autoscroll_to_latest() -> None:
    """Scroll chat region to latest message after each rerun."""
    html = """
    <script>
    (function () {
        const doc = window.parent.document;
        function scrollLatest() {
            const vb = doc.querySelector('[data-testid="column"]:has(#chat-column-marker) > [data-testid="stVerticalBlock"]');
            if (vb) vb.scrollTop = vb.scrollHeight;
            const msgs = doc.querySelectorAll('[data-testid="column"]:has(#chat-column-marker) [data-testid="stChatMessage"]');
            if (msgs.length) msgs[msgs.length - 1].scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
        scrollLatest();
        setTimeout(scrollLatest, 200);
        setTimeout(scrollLatest, 600);
        setTimeout(scrollLatest, 1200);
    })();
    </script>
    """
    st.components.v1.html(html, height=0, scrolling=False)

# ========== Login Page ==========
def show_login_page():
    col_hero, col_form = st.columns([1.15, 1], gap="large")

    with col_hero:
        st.markdown("""
        <div class="animate-in">
            <div class="hero-eyebrow">English Writing · IELTS & TOEFL · SRL</div>
            <div class="monet-title" style="margin-bottom:0.75rem;">
                Your voice<br>
                <span class="gradient-text">in the writing garden</span>
            </div>
            <div class="monet-subtitle" style="max-width:520px;line-height:1.65;margin-bottom:0.5rem;">
                For all English learners — with strong support for <strong>IELTS</strong> and
                <strong>TOEFL</strong> writing. An AI coach that guides, never ghostwrites.
            </div>
            <div class="journey-grid">
                <div class="journey-card">
                    <div class="j-num">01</div>
                    <h4>Plan</h4>
                    <p>Goals, thesis, and outline for academic essays.</p>
                </div>
                <div class="journey-card">
                    <div class="j-num">02</div>
                    <h4>Draft</h4>
                    <p>Write in chat; pick from our IELTS prompt bank if stuck.</p>
                </div>
                <div class="journey-card">
                    <div class="j-num">03</div>
                    <h4>Evaluate</h4>
                    <p>IELTS, TOEFL, CET, or creative rubric feedback.</p>
                </div>
                <div class="journey-card">
                    <div class="j-num">04</div>
                    <h4>Interact</h4>
                    <p>Reflect, discuss, and grow your critical voice.</p>
                </div>
            </div>
            <div class="trust-row">
                <span class="trust-item">🎓 All English learners</span>
                <span class="trust-item">📝 IELTS & TOEFL</span>
                <span class="trust-item">✨ DeepSeek AI</span>
                <span class="trust-item">🔒 Research ethics</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_form:
        st.markdown('<div id="login-form-marker"></div>', unsafe_allow_html=True)
        st.markdown(
            '<h3 class="form-title">Begin your session</h3>'
            '<p class="form-sub">Email and name — then choose Session 1, 2, or 3.</p>',
            unsafe_allow_html=True,
        )
        email = st.text_input("Email", placeholder="your@email.com", key="login_email")
        user_name = st.text_input("Your name", placeholder="How should the coach call you?", key="login_name")
        round_option = st.selectbox(
            "Session", ["Session 1", "Session 2", "Session 3"], key="test_round_select"
        )
        st.markdown(
            f'<p style="font-size:0.85rem;color:var(--giverny-muted);margin:0.5rem 0 1rem;'
            f'padding:0.65rem 0.85rem;background:rgba(107,158,143,0.1);border-radius:12px;">'
            f'💡 {SESSION_GUIDE.get(round_option, "")}</p>',
            unsafe_allow_html=True,
        )

        with st.expander("How to use this coach (60 seconds)", expanded=False):
            st.markdown("""
            1. **Plan** — Goals and outline for IELTS/TOEFL essays  
            2. **Draft** — Write in chat; use **I have no idea** for IELTS prompts  
            3. **Evaluate** — IELTS / TOEFL rubric feedback or scored evaluation  
            4. **Interact** — Reflect and discuss your progress  

            The coach **never** writes your essay for you.  
            Sessions are saved for academic research.
            """)

        consent = st.checkbox(
            "I agree my session data may be used for academic research.",
            key="login_consent",
        )
        login_clicked = st.button(
            "Enter the garden →", use_container_width=True, type="primary", key="btn_login_start"
        )
        if login_clicked:
            if not consent:
                st.warning("Please check the research consent box to continue.")
            elif email.strip() and user_name.strip():
                round_map = {
                    "Session 1": "round_1",
                    "Session 2": "round_2",
                    "Session 3": "round_3",
                }
                round_value = round_map[round_option]
                do_login(email.strip(), user_name.strip(), round_value)
                st.rerun()
            else:
                st.warning("Please enter your email and name.")
        st.caption("Auto-saved after each message · Researcher: add ?research=1 to URL")

# ========== Research Dashboard ==========
def show_research_dashboard():
    st.markdown(
        '<div class="monet-title" style="text-align:center;">🔬 Research Dashboard</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="monet-subtitle" style="text-align:center;">'
        "Student session data · Google Sheets</div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.research_authenticated:
        pwd = st.text_input("Research password", type="password", key="research_pwd")
        if st.button("Enter dashboard", type="primary", key="btn_research_login"):
            if pwd == get_research_password():
                st.session_state.research_authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.caption("Set RESEARCH_PASSWORD in Streamlit Secrets. Default: srl2026")
        return

    rows = load_all_sessions_from_sheets()
    if not rows:
        st.warning(
            "No data in Google Sheets yet — or Sheets is not configured. "
            "See GOOGLE_SHEETS_SETUP.md"
        )
        if st.button("Back to student login"):
            st.query_params.clear()
            st.rerun()
        return

    st.success(f"Loaded **{len(rows)}** session records from Google Sheets.")

    # Summary metrics
    students = {r.get("student_id") for r in rows if r.get("student_id")}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique students", len(students))
    c2.metric("Total sessions", len(rows))
    c3.metric("Session 1", sum(1 for r in rows if r.get("test_round") == "round_1"))
    c4.metric("Session 2+3", sum(1 for r in rows if r.get("test_round") in ("round_2", "round_3")))

    # Filter
    student_ids = sorted(students)
    selected = st.selectbox("Filter by student email", ["All"] + student_ids)
    filtered = rows if selected == "All" else [r for r in rows if r.get("student_id") == selected]

    # Table view
    display_rows = []
    for r in filtered:
        display_rows.append({
            "email": r.get("student_id", ""),
            "name": r.get("student_name", ""),
            "session": ROUND_LABELS.get(r.get("test_round", ""), r.get("test_round", "")),
            "messages": r.get("message_count", ""),
            "step": r.get("current_step", ""),
            "plan_done": r.get("plan_completed", ""),
            "draft_checks": r.get("monitoring_count", ""),
            "saved_at": r.get("created_at", ""),
        })
    st.dataframe(display_rows, use_container_width=True, hide_index=True)

    # Conversation detail
    st.markdown("#### Conversation detail")
    for i, r in enumerate(reversed(filtered[-20:])):
        label = (
            f"{r.get('student_name', '?')} · "
            f"{ROUND_LABELS.get(r.get('test_round', ''), '?')} · "
            f"{r.get('created_at', '')[:19]}"
        )
        with st.expander(label):
            try:
                conv = json.loads(r.get("conversation", "[]"))
                for msg in conv:
                    role = "Student" if msg.get("role") == "user" else "Coach"
                    st.markdown(f"**{role}:** {msg.get('content', '')}")
            except Exception:
                st.text(r.get("conversation", ""))

    # CSV export
    buf = io.StringIO()
    if display_rows:
        writer = csv.DictWriter(buf, fieldnames=display_rows[0].keys())
        writer.writeheader()
        writer.writerows(display_rows)
    st.download_button(
        "Download CSV",
        buf.getvalue(),
        file_name=f"srl_research_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    if st.button("Exit dashboard"):
        st.session_state.research_authenticated = False
        st.query_params.clear()
        st.rerun()

# ========== Main App — chat-first layout ==========
def main_app():
    cur = st.session_state.current_step
    round_label = round_display(st.session_state.test_round)
    step_num = {s: i + 1 for i, s in enumerate(STEPS)}
    active_label = STEP_LABELS.get(cur, cur.title())
    tip = STEP_TIPS.get(cur, "")
    completed = st.session_state.completed_steps
    progress = len(completed) / len(STEPS)

    def call_ai(user_input: str, eval_mode: str = "no_score") -> str:
        framework = st.session_state.get("eval_score_framework", "ielts")
        system = get_system_prompt(
            st.session_state.current_step, eval_mode, framework
        )
        messages = [{"role": "system", "content": system}]
        for m in st.session_state.messages[-10:]:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_input})
        try:
            client = get_deepseek_client()
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.6,
                max_tokens=900,
                timeout=45,
            )
            return resp.choices[0].message.content
        except Exception as e:
            if "API key" in str(e).lower() or "not configured" in str(e).lower():
                return "⚠️ The DeepSeek API key is not configured yet. Please add it in Streamlit Cloud Secrets or set the environment variable before using the coach."
            return f"❌ AI Response Timeout or Error: {str(e)}. Please try again."

    def handle_input(eval_mode: str = "no_score"):
        user_input = st.session_state.get("user_input", "")
        if not user_input or not user_input.strip():
            return
        st.session_state.messages.append({"role": "user", "content": user_input})

        current_step = st.session_state.current_step
        st.session_state.completed_steps.add(current_step)

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
            st.session_state.show_eval_score_menu = False

    def _run_scored_evaluation(framework: str):
        set_step("evaluating")
        st.session_state.show_eval_menu = False
        st.session_state.show_eval_score_menu = False
        st.session_state.eval_score_framework = framework
        if not st.session_state.plan_completed:
            st.session_state.user_input = (
                "I want a scored evaluation, but I haven't finished Planning yet. Please remind me."
            )
            handle_input()
            return
        label = SCORE_FRAMEWORK_LABELS.get(framework, framework)
        text = last_user_writing()
        prompt = (
            f"Step 3 — Evaluation with **{label}** scoring. "
            "Please score my writing using the rubric for this exam type."
        )
        if text and len(text) > 30:
            prompt += f"\n\nMy writing:\n{text}"
        st.session_state.user_input = prompt
        handle_input(eval_mode="score")

    def action_plan():
        set_step("plan")
        st.session_state.plan_in_progress = True
        st.session_state.show_draft_choice = True
        st.session_state.show_eval_menu = False
        st.session_state.show_eval_score_menu = False
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
        st.session_state.show_draft_choice = True
        st.session_state.show_eval_menu = False
        st.session_state.show_eval_score_menu = False

    def action_draft_has_idea():
        set_step("draft")
        st.session_state.show_draft_choice = False
        text = last_user_writing()
        if text and len(text) > 30:
            st.session_state.user_input = (
                f"Step 2 — Draft. I have an idea for my topic. "
                f"Please help me self-check this writing:\n\n{text}"
            )
        else:
            st.session_state.user_input = (
                "Step 2 — Draft. I have a clear topic idea now. Please guide me through "
                "drafting and self-checking."
            )
        handle_input()

    def action_draft_no_idea():
        set_step("draft")
        st.session_state.show_draft_choice = False
        picks = pick_ielts_prompts(3)
        bank_text = format_ielts_prompts_for_coach(picks)
        st.session_state.user_input = (
            "Step 2 — Draft. I have NO IDEA what to write about.\n\n"
            "Here are three **writing prompts** from our **2026 question bank** (IELTS-style). "
            "Please present them clearly, help me choose ONE that interests me, "
            "then guide me through brainstorming and drafting:\n\n"
            f"{bank_text}\n\n"
            "Ask which topic I prefer, then help me plan my position and start writing."
        )
        handle_input()

    def action_open_evaluation():
        set_step("evaluating")
        st.session_state.show_eval_menu = True
        st.session_state.show_eval_score_menu = False

    def action_show_score_frameworks():
        set_step("evaluating")
        st.session_state.show_eval_menu = True
        st.session_state.show_eval_score_menu = True

    def action_evaluating_no_score():
        set_step("evaluating")
        st.session_state.show_eval_score_menu = False
        if not st.session_state.plan_completed:
            st.session_state.user_input = (
                "I want Evaluation feedback, but I haven't finished Planning yet. Please remind me."
            )
            handle_input()
            return
        text = last_user_writing()
        prompt = (
            "Step 3 — Evaluation (holistic rubric, feedback only, no score). "
            "Please evaluate my writing on Task Response, Coherence, Vocabulary, and Grammar."
        )
        if text and len(text) > 30:
            prompt += f"\n\nMy writing:\n{text}"
        st.session_state.user_input = prompt
        handle_input(eval_mode="no_score")

    def action_eval_cet():
        _run_scored_evaluation("cet")

    def action_eval_ielts():
        _run_scored_evaluation("ielts")

    def action_eval_toefl():
        _run_scored_evaluation("toefl")

    def action_eval_creative():
        _run_scored_evaluation("creative")

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
        st.session_state.show_eval_score_menu = False
        st.session_state.show_draft_choice = False
        st.session_state.completed_steps = set()
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                f"✨ **Fresh start, {st.session_state.user_name}!**\n\n"
                "Tell me your topic — or say you have no idea — "
                "and we'll begin with **Step 1: Plan**."
            )
        })
        st.rerun()

    def render_step_button(step_key: str, icon: str, on_click, key_suffix: str = ""):
        short = STEP_BTN_LABEL[step_key]
        is_completed = step_key in st.session_state.completed_steps
        is_active = step_key == cur
        display_icon = "✅" if is_completed else icon
        label = f"{display_icon} {short}"
        st.button(
            label,
            use_container_width=True,
            on_click=on_click,
            key=STEP_BUTTON_KEYS[step_key] + key_suffix,
            type="primary" if is_active else "secondary",
        )

    inject_step_button_styles(cur)
    inject_garden_app_layout_css()
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="app-shell-marker"></div>', unsafe_allow_html=True)
    col_panel, col_chat = st.columns([1, 2.4], gap="medium")

    with col_panel:
        st.markdown('<div id="studio-column-marker"></div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="panel-brand">
            <span style="font-size:1.5rem;">🪷</span>
            <h3>SRL Writing Coach</h3>
            <p>Monet Garden · IELTS & TOEFL</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"**{st.session_state.user_name}**")
        st.caption(f"{st.session_state.user_id} · {round_label}")
        st.progress(progress, text=f"{len(completed)}/{len(STEPS)} steps")

        st.markdown("---")
        st.markdown("**Choose a step**")
        render_step_button("plan", "📋", action_plan, "_panel")
        render_step_button("draft", "✍️", action_draft, "_panel")
        render_step_button("evaluating", "📊", action_open_evaluation, "_panel")
        render_step_button("interaction", "💬", action_interaction, "_panel")

        if st.session_state.show_draft_choice and cur in {"plan", "draft"}:
            st.markdown('<div class="eval-pick-box">', unsafe_allow_html=True)
            st.markdown('<div class="eval-pick-title">Draft options</div>', unsafe_allow_html=True)
            st.button("✨ I have an idea", use_container_width=True, on_click=action_draft_has_idea,
                      key="btn_draft_has_idea", type="primary")
            st.button("🤷 I have no idea", use_container_width=True, on_click=action_draft_no_idea,
                      key="btn_draft_no_idea", type="secondary")
            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.show_eval_menu and cur == "evaluating":
            st.markdown('<div class="eval-pick-box">', unsafe_allow_html=True)
            st.markdown('<div class="eval-pick-title">Evaluation options</div>', unsafe_allow_html=True)
            st.button("Feedback only", use_container_width=True, on_click=action_evaluating_no_score,
                      key="btn_eval_feedback", type="secondary")
            st.button("Score + feedback", use_container_width=True, on_click=action_show_score_frameworks,
                      key="btn_eval_score_menu", type="secondary")
            if st.session_state.show_eval_score_menu:
                st.button("IELTS", use_container_width=True, on_click=action_eval_ielts,
                          key="btn_eval_ielts", type="primary")
                st.button("TOEFL", use_container_width=True, on_click=action_eval_toefl,
                          key="btn_eval_toefl", type="secondary")
                st.button("CET-4/6", use_container_width=True, on_click=action_eval_cet,
                          key="btn_eval_cet", type="secondary")
                st.button("Creative", use_container_width=True, on_click=action_eval_creative,
                          key="btn_eval_creative", type="secondary")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            f'<div class="studio-tip-box"><strong>💡 {STEP_LABELS.get(cur, cur)}</strong><br>{tip}</div>',
            unsafe_allow_html=True,
        )
        st.metric("Draft checks", st.session_state.monitoring_count)

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.button("🔄 Reset", use_container_width=True, on_click=action_reset, key="btn_reset", type="secondary")
        with c2:
            if st.button("💾 Save", use_container_width=True, key="btn_save", type="secondary"):
                if save_current_session():
                    st.toast("Saved 🌸", icon="✅")
        if st.button("Sign out", use_container_width=True, key="btn_signout"):
            do_logout()

    with col_chat:
        st.markdown('<div id="chat-column-marker"></div>', unsafe_allow_html=True)

        st.markdown('<div id="sticky-step-bar-marker"></div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="garden-step-prompt">🌿 Tap a step to begin — Plan · Draft · Evaluation · Interaction</p>',
            unsafe_allow_html=True,
        )
        bc1, bc2, bc3, bc4 = st.columns(4, gap="small")
        with bc1:
            render_step_button("plan", "📋", action_plan, "_bar")
        with bc2:
            render_step_button("draft", "✍️", action_draft, "_bar")
        with bc3:
            render_step_button("evaluating", "📊", action_open_evaluation, "_bar")
        with bc4:
            render_step_button("interaction", "💬", action_interaction, "_bar")

        st.markdown(f"""
        <div class="chat-header-bar">
            <span class="step-pill">Step {step_num.get(cur, "?")} · {active_label}</span>
            <h2 class="header-title" style="margin:0.25rem 0 0;">Writing Studio</h2>
            <div class="header-meta">{st.session_state.user_name} · {round_label}</div>
        </div>
        """, unsafe_allow_html=True)

        for msg in st.session_state.messages:
            with st.chat_message("user" if msg["role"] == "user" else "assistant"):
                st.markdown(msg["content"])

        st.chat_input("Type your English writing here…", key="user_input", on_submit=handle_input)
        st.caption("⚡ DeepSeek · 🎓 SRL · 📝 IELTS & TOEFL · 🌸 Your words, your voice")

    inject_autoscroll_to_latest()

# ========== Run ==========
init_session_state()

if st.query_params.get("research") == "1":
    show_research_dashboard()
elif st.session_state.logged_in:
    main_app()
else:
    show_login_page()
