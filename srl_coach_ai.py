import streamlit as st
from openai import OpenAI
from datetime import datetime
import random
import json
import os
import requests

# ========== API Configuration ==========
DEEPSEEK_API_KEY = "sk-e2b1fab64b754d69b45ca099f9e49d10"

deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# ========== 腾讯云开发配置 ==========
# ！重要！请替换成你自己的值
TCB_ENV_ID = "srl-writing-coach-d5dvf4d5"  # 你的环境ID
TCB_API_KEY = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjlkMWRjMzFlLWI2ZDAtNDQ4Yy1hNzZmLWUyY2M2M2Q4MTQ5OCJ9.eyJhdWQiOiJzcmwtd3JpdGluZy1jb2FjaC1kNWR2ZjRkNSIsImV4cCI6MjUzNDAyMzA3OTk5LCJpYXQiOjE3Nzk4MTg2NTAsImF0X2hhc2giOiJjdlpObkRPNFZqSExYNWY5NWZocnBRIiwicHJvamVjdF9pZCI6InNybC13cml0aW5nLWNvYWNoLWQ1ZHZmNGQ1IiwicGxhdGZvcm0iOiJBcGlLZXkiLCJhZG1pbl9pZF9hY2NvdW50IjoiMjA1OTMzMjAwMTIxNDAyMTYzMyIsInVzZXJfdHlwZSI6ImFkbWluIiwiY2xpZW50X3R5cGUiOiJjbGllbnRfc2VydmVyIiwiaXNfc3lzdGVtX2FkbWluIjp0cnVlfQ.pdiEwyBmiNpIf3yqg5RkklOL8I2SfaO1YhmRukn-B0wKvfbkR67IBbc6JSepsf9M4R4y-HTQRYVWNV8XAGCOzokLXL46tyWIBgJ3s3Sbnf5-vMsu5xN9gVEEE4HJERpXvVd5I02aLlBcbbG0iWqcFg0Nc6sDuQr9Orehg7VtWxMXUapfacApH9vqUvjeH8ICEBvP66hWdyV45qGAP4GSQvNLTUJeaj0I3gHEL1THH_rxQj4rHpsdI2_Qa0BXQnuk_4FeroXHanoHJBLO8dLdxnT1GmyRDyt_fB7UHZRd8pDRQOSWeYuhCMgpnbpdl_ANg5_R4xr9Fe75wm_Hg19mghw"

# ========== SRL System Prompt with Originality Check ==========
SRL_SYSTEM_PROMPT = """You are an academic writing coach based on Self-Regulated Learning (SRL) Theory.

## CRITICAL LANGUAGE RULE: RESPOND IN 100% ENGLISH. NO CHINESE CHARACTERS.

## ORIGINALITY CHECK RULES (MUST FOLLOW STRICTLY)
1. **NEVER praise users for copying examples verbatim**
2. **ALWAYS detect when users paste your own examples back to you**
3. **If a user copies your example word-for-word (80%+ match), respond with:**
   "⚠️ I notice you copied my example sentence. That's okay for learning, but now let's write YOUR OWN version. Change at least 3 words to make it yours. Try: [suggest a small change]"

4. **Check for copying by comparing user input to your last response**
5. **When you detect copying, don't praise — redirect to original thinking**
6. **Only praise when the user has clearly written something original**

## Your Role
Help students complete Plan → Check → Reflect for ENGLISH writing with ORIGINAL thinking.

## Phase 1: Plan (Forethought)
- Help set goals, create outline in English
- Provide examples but mark them clearly as "EXAMPLE:"
- End with "Now write ONE original sentence"

## Phase 2: Check (Performance)
Check five aspects:
1. Logic: Is the argument coherent?
2. Evidence: Are there concrete examples?
3. Language: Grammar, vocabulary, sentence structure
4. AI Dependency: Did the student just copy or understand?
5. ORIGINALITY: Is this copied from my example or genuinely new?

## Phase 3: Reflect (Self-Reflection)
- Guide reflection on learning process
- Ask: "What did you write that was original?"

## Response Examples:

❌ WRONG: "That's a great thesis! Well done! Let's continue."
✅ CORRECT: "I see you used my example sentence. That's fine for practice, but now write YOUR version. Change 'threaten our homes' to something personal to you."

❌ WRONG: "Perfect! Excellent work!"
✅ CORRECT: "Good start! Now add one specific detail that comes from YOUR own experience or opinion."

❌ WRONG: "Great job copying my example!"
✅ CORRECT: "That's the example I gave. Now try changing the beginning to make it yours."

## Core Rules
1. NEVER write full paragraphs for the user
2. End each response with ONE small actionable step
3. Detect and redirect copying, don't praise it
4. Only celebrate genuine original thinking"""

# ========== Data Storage Functions ==========
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

def save_to_cloudbase(student_id, student_name, plan_completed, monitoring_count, conversation, test_round="pre"):
    """保存数据到腾讯云开发数据库"""
    try:
        data = {
            "student_id": student_id,
            "student_name": student_name,
            "test_round": test_round,
            "plan_completed": plan_completed,
            "monitoring_count": monitoring_count,
            "conversation": conversation,
            "created_at": datetime.now().isoformat()
        }
        
        url = f"https://{TCB_ENV_ID}.ap-shanghai.tcb-api.tencentcloudapi.com/api/v1/database/collection/writing_sessions/document/add"
        
        headers = {
            "Content-Type": "application/json",
            "X-CloudBase-API-Key": TCB_API_KEY
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            print(f"✅ CloudBase保存成功: {student_id}")
            return True
        else:
            print(f"❌ CloudBase保存失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ CloudBase保存异常: {e}")
        return False

# ========== Login/Session State ==========
def init_session_state():
    """初始化所有 session state 变量"""
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

def do_login(user_id: str, user_name: str, test_round: str = "pre"):
    """执行登录"""
    st.session_state.logged_in = True
    st.session_state.user_id = user_id
    st.session_state.user_name = user_name
    st.session_state.test_round = test_round
    st.session_state.messages = []
    st.session_state.plan_completed = False
    st.session_state.monitoring_count = 0
    st.session_state.conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.session_start = datetime.now().isoformat()
    
    # 保存登录事件到 CloudBase
    save_to_cloudbase(
        student_id=user_id,
        student_name=user_name,
        plan_completed=False,
        monitoring_count=0,
        conversation=[],
        test_round=test_round
    )
    
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"👋 **Welcome, {user_name}!**\n\nI understand that writing can sometimes feel difficult, tiring, or even stressful — and that's completely normal.\n\nMy role is not to write for you, but to help you **lower those barriers** and build confidence.\n\n**Tell me your English writing topic, and we'll start with a small first step.**\n\n💡 *If you feel stuck, just say \"I'm stuck\" or click the 💪 button below.*\n\n---\n🎨 *Let's write together, like painting with words — one brushstroke at a time.*"
    })

def do_logout():
    """执行登出"""
    if st.session_state.logged_in and len(st.session_state.messages) > 1:
        # 保存到本地
        session_data = {
            "session_id": st.session_state.conversation_id,
            "start_time": st.session_state.session_start,
            "end_time": datetime.now().isoformat(),
            "plan_completed": st.session_state.plan_completed,
            "monitoring_count": st.session_state.monitoring_count,
            "messages": st.session_state.messages
        }
        save_conversation(st.session_state.user_id, session_data)
        
        # 保存到 CloudBase
        save_to_cloudbase(
            student_id=st.session_state.user_id,
            student_name=st.session_state.user_name,
            plan_completed=st.session_state.plan_completed,
            monitoring_count=st.session_state.monitoring_count,
            conversation=st.session_state.messages,
            test_round=st.session_state.test_round
        )
    
    # 重置 session state
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.test_round = "pre"
    st.session_state.messages = []
    st.session_state.plan_completed = False
    st.session_state.monitoring_count = 0
    st.rerun()

def save_current_session():
    """手动保存当前会话"""
    if st.session_state.logged_in and len(st.session_state.messages) > 1:
        session_data = {
            "session_id": st.session_state.conversation_id,
            "start_time": st.session_state.session_start,
            "end_time": datetime.now().isoformat(),
            "plan_completed": st.session_state.plan_completed,
            "monitoring_count": st.session_state.monitoring_count,
            "messages": st.session_state.messages
        }
        save_conversation(st.session_state.user_id, session_data)
        
        save_to_cloudbase(
            student_id=st.session_state.user_id,
            student_name=st.session_state.user_name,
            plan_completed=st.session_state.plan_completed,
            monitoring_count=st.session_state.monitoring_count,
            conversation=st.session_state.messages,
            test_round=st.session_state.test_round
        )
        return True
    return False

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
        gap: 2rem;
        margin: 1rem 0;
    }
    .intro-icon-item {
        text-align: center;
        font-size: 0.8rem;
        color: #5a6e5a;
    }
    .intro-icon-item span {
        font-size: 1.5rem;
        display: block;
    }
    
    .login-area {
        max-width: 300px;
        margin: 0.5rem auto;
        text-align: center;
    }
    
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
    
    .stTextInput > div {
        margin-bottom: 0.5rem;
    }
    
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background: linear-gradient(135deg, #8daa9a 0%, #6b8a78 100%);
        color: white;
        border-radius: 24px 24px 8px 24px;
        padding: 8px 16px;
        margin: 8px 0;
        max-width: 75%;
        margin-left: auto;
    }
    
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        background: rgba(245, 240, 230, 0.85);
        backdrop-filter: blur(4px);
        border-radius: 24px 24px 24px 8px;
        padding: 8px 16px;
        margin: 8px 0;
        max-width: 85%;
        color: #3a4a3a;
        border: 1px solid rgba(200,180,140,0.3);
    }
    
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #b8a99a, transparent);
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ========== Login Page ==========
def show_login_page():
    st.markdown('<div class="monet-title">✍️ SRL Writing Coach</div>', unsafe_allow_html=True)
    st.markdown('<div class="monet-subtitle">🎨 Self-Regulated Learning · Like painting with words</div>', unsafe_allow_html=True)
    
    st.divider()
    
    st.markdown("""
    <div class="intro-text">
        <strong>SRL Writing Coach</strong> is an AI-powered academic writing assistant 
        based on Self-Regulated Learning Theory. It helps you become a more confident 
        and independent writer by guiding you through three essential stages: 
        <strong>Plan → Check → Reflect</strong>.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="intro-icon-row">
        <div class="intro-icon-item"><span>📋</span><strong>Plan</strong><br>Set goals & outline</div>
        <div class="intro-icon-item"><span>✍️</span><strong>Check</strong><br>Logic · Evidence · Language</div>
        <div class="intro-icon-item"><span>🤔</span><strong>Reflect</strong><br>Review & improve</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-area">', unsafe_allow_html=True)
    st.markdown('<h4 style="text-align: center; margin: 0.5rem 0; color: #4a5e4a;">🌸 Sign In</h4>', unsafe_allow_html=True)
    
    st.markdown('<p style="font-size: 0.75rem; color: #5a6e5a; margin-bottom: 0.2rem; text-align: left;">Student ID / Email</p>', unsafe_allow_html=True)
    user_id = st.text_input("", placeholder="e.g., 20240001", key="login_id", label_visibility="collapsed")
    
    st.markdown('<p style="font-size: 0.75rem; color: #5a6e5a; margin-bottom: 0.2rem; text-align: left;">Your Name</p>', unsafe_allow_html=True)
    user_name = st.text_input("", placeholder="e.g., Zhang Wei", key="login_name", label_visibility="collapsed")
    
    st.markdown('<p style="font-size: 0.75rem; color: #5a6e5a; margin-bottom: 0.2rem; text-align: left;">Test Round</p>', unsafe_allow_html=True)
    test_round_option = st.selectbox("", ["Pre-test", "Post-test"], key="test_round_select", label_visibility="collapsed")
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        login_clicked = st.button("🎨 Enter the Garden", use_container_width=True, type="primary")
    
    if login_clicked:
        if user_id and user_name:
            round_value = "pre" if test_round_option == "Pre-test" else "post"
            do_login(user_id.strip(), user_name.strip(), round_value)
            st.rerun()
        else:
            st.warning("Please enter both Student ID and Name.")
    
    st.caption("💡 Your writing data is saved locally.")
    st.markdown('</div>', unsafe_allow_html=True)

# ========== Main App ==========
def main_app():
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0;">
        <div>
            <div class="monet-title" style="text-align: left; font-size: 2rem;">✍️ SRL Writing Coach</div>
            <div class="monet-subtitle" style="text-align: left;">🎨 Self-Regulated Learning · Like painting with words</div>
        </div>
        <div style="background: rgba(255,248,235,0.3); border-radius: 40px; padding: 6px 18px; text-align: right;">
            <div style="font-size: 0.85rem; font-weight: 500; color: #2c4a3e;">🎨 {st.session_state.user_name}</div>
            <div style="font-size: 0.65rem; color: #6b8a78;">{st.session_state.user_id}</div>
            <div style="font-size: 0.65rem; color: #6b8a78;">Round: {st.session_state.test_round}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    with st.sidebar:
        st.markdown("""
        <div style="background: rgba(255,248,235,0.25); backdrop-filter: blur(8px); border-radius: 28px; padding: 18px; text-align: center; margin-bottom: 20px;">
            <span style="font-size: 2rem;">🎨🌿</span><br>
            <span style="font-size: 1rem; font-weight: 500;">Giverny Garden</span><br>
            <span style="font-size: 0.75rem;">Your Writing Studio</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.caption(f"👤 {st.session_state.user_name}")
        st.caption(f"📧 {st.session_state.user_id}")
        st.caption(f"🔄 Round: {st.session_state.test_round}")
        
        st.divider()
        
        st.markdown("#### 🌱 Growth Path")
        
        if st.session_state.plan_completed:
            st.success("✅ **Plan** — Seed planted")
        else:
            st.info("📍 **Plan** — Ready to begin")
        
        if st.session_state.plan_completed:
            if st.session_state.monitoring_count > 0:
                st.info(f"✍️ **Check** — {st.session_state.monitoring_count} revisions")
            else:
                st.warning("⏳ **Check** — Write something first")
        else:
            st.caption("🔒 **Check** — Start with Plan")
        
        if st.session_state.plan_completed and st.session_state.monitoring_count > 0:
            st.success("🎯 **Reflect** — Ready to bloom")
        else:
            st.caption("🔒 **Reflect** — Complete Plan & Check")
        
        st.divider()
        
        st.metric("🔄 Revisions", st.session_state.monitoring_count)
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
    
    # ========== Chat Display ==========
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])

    # ========== AI Call ==========
    def call_deepseek(user_input: str) -> str:
        messages = [{"role": "system", "content": SRL_SYSTEM_PROMPT}]
        for msg in st.session_state.messages[-15:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_input})
        
        try:
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ Error: {str(e)}"

    def handle_input():
        user_input = st.session_state.user_input
        if user_input and user_input.strip():
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            with st.spinner("🎨 Painting a response..."):
                response = call_deepseek(user_input)
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            # 🆕 每次对话后自动保存到 CloudBase
            try:
                save_to_cloudbase(
                    student_id=st.session_state.user_id,
                    student_name=st.session_state.user_name,
                    plan_completed=st.session_state.plan_completed,
                    monitoring_count=st.session_state.monitoring_count,
                    conversation=st.session_state.messages,
                    test_round=st.session_state.test_round
                )
            except Exception as e:
                print(f"自动保存失败: {e}")
            
            if "plan" in response.lower() and "outline" in response.lower():
                if not st.session_state.plan_completed:
                    st.session_state.plan_completed = True
            if "check" in response.lower() or "logic" in response.lower():
                st.session_state.monitoring_count += 1
            
            st.session_state.user_input = ""

    # ========== Button Actions ==========
    def action_plan():
        st.session_state.user_input = "Let's start Step 1: Planning. Please help me create an outline for my English essay."
        handle_input()

    def action_check():
        last_msg = ""
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "user":
                last_msg = msg["content"]
                break
        if last_msg and len(last_msg) > 30:
            st.session_state.user_input = f"""Step 2: Please check my English paragraph.

Check: Logic, Evidence, Language, AI Dependency, ORIGINALITY.

My paragraph:
{last_msg}"""
        else:
            st.session_state.user_input = "I'm ready for Step 2. Please guide me."
        handle_input()

    def action_reflect():
        st.session_state.user_input = """Step 3: Self-Reflection.

Help me reflect:
1. What did I do well?
2. What was challenging?
3. What did I write that was original?"""
        handle_input()

    def action_stuck():
        st.session_state.user_input = "I'm stuck. Please give me encouragement and ONE small step to continue."
        handle_input()

    def action_reset():
        save_current_session()
        st.session_state.messages = []
        st.session_state.plan_completed = False
        st.session_state.monitoring_count = 0
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"✨ **Fresh start, {st.session_state.user_name}!**\n\nTell me your English writing topic, and we'll begin.\n\nYou've got this. One sentence at a time.\n\n🎨 *Like painting, writing gets better with practice.*"
        })
        st.rerun()

    # ========== Main Buttons ==========
    st.markdown("### 🎨 The 3 Steps")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.button("📋 **PLAN**\n\n🌱 Set goals & outline", use_container_width=True, on_click=action_plan)

    with col2:
        st.button("✍️ **CHECK**\n\n🔍 Get feedback", use_container_width=True, on_click=action_check)

    with col3:
        st.button("🤔 **REFLECT**\n\n🌟 Review & bloom", use_container_width=True, on_click=action_reflect)

    col_s1, col_s2, col_s3, col_s4 = st.columns([1, 1, 2, 0.8])
    with col_s1:
        st.button("💪 Stuck?", use_container_width=True, on_click=action_stuck)
    with col_s2:
        st.button("🔄 Reset", use_container_width=True, on_click=action_reset)
    with col_s4:
        if st.button("💾 Save", use_container_width=True):
            if save_current_session():
                st.toast("Session saved! 🌸", icon="✅")
            else:
                st.toast("Nothing to save yet.", icon="💡")

    st.caption("💡 **Flow:** Plan → Write → Check → Reflect — layer by layer, like a painting.")

    st.divider()

    st.chat_input("📝 Type your English writing here...", key="user_input", on_submit=handle_input)

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("⚡ Powered by DeepSeek")
    with c2:
        st.caption("🎓 SRL Self-Regulated Learning")
    with c3:
        st.caption("🔒 Your garden, your data")

# ========== Run ==========
# 初始化所有 session state
init_session_state()

if st.session_state.logged_in:
    main_app()
else:
    show_login_page()
