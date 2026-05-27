import streamlit as st
from openai import OpenAI
from datetime import datetime
import random
import json
import os
import requests
import traceback

# ========== API Configuration ==========
DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
KIMI_API_KEY = st.secrets["KIMI_API_KEY"]

deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

kimi_client = OpenAI(
    api_key=KIMI_API_KEY,
    base_url="https://api.moonshot.cn/v1"
)

# ========== Supabase 配置 ==========
SUPABASE_URL = "https://kgzotpkprrmuaxiqqeaz.supabase.co"
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# ========== 优化后的 Supabase 保存函数 ==========
def save_to_supabase(student_id, student_name, test_round, plan_completed, monitoring_count, conversation):
    print(f"🔵 [Supabase] 开始保存: {student_id} - {test_round} | 消息数: {len(conversation) if isinstance(conversation, list) else 0}")
    
    try:
        url = f"{SUPABASE_URL}/rest/v1/writing_sessions"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        # 限制数据量
        trimmed_conversation = conversation[-25:] if isinstance(conversation, list) and len(conversation) > 25 else conversation
        
        data = {
            "student_id": student_id,
            "student_name": student_name,
            "test_round": test_round,
            "plan_completed": plan_completed,
            "monitoring_count": monitoring_count,
            "conversation": trimmed_conversation,
            "updated_at": datetime.now().isoformat()
        }
        
        # 检查是否存在记录
        check_url = f"{SUPABASE_URL}/rest/v1/writing_sessions?student_id=eq.{student_id}&test_round=eq.{test_round}&select=id"
        check_response = requests.get(check_url, headers=headers, timeout=15)
        
        if check_response.status_code == 200 and check_response.json():
            record_id = check_response.json()[0]["id"]
            update_url = f"{SUPABASE_URL}/rest/v1/writing_sessions?id=eq.{record_id}"
            response = requests.patch(update_url, headers=headers, json=data, timeout=15)
            print(f"🔄 [Supabase] 更新记录: {response.status_code}")
        else:
            data["created_at"] = datetime.now().isoformat()
            response = requests.post(url, headers=headers, json=data, timeout=15)
            print(f"📝 [Supabase] 插入新记录: {response.status_code}")
        
        if response.status_code in (200, 201, 204):
            print(f"✅ [Supabase] 保存成功: {student_id}")
            return True
        else:
            print(f"❌ [Supabase] 保存失败: {response.status_code} - {response.text[:400]}")
            return False
            
    except Exception as e:
        print(f"❌ [Supabase] 异常: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        return False


# ========== SRL System Prompt ==========
SRL_SYSTEM_PROMPT = """You are an academic writing coach based on Self-Regulated Learning (SRL) Theory.

## CRITICAL RULE - YOU MUST FOLLOW:
- YOU MUST NOT write ANY example sentences, paragraphs, or outlines for the user.
- YOU MUST ONLY ask questions and guide the user to write their OWN content.
- NEVER write more than 60 words in a single response.

## LANGUAGE RULE: RESPOND IN 100% ENGLISH. NO CHINESE CHARACTERS.

## ORIGINALITY CHECK RULES:
1. NEVER praise users for copying examples verbatim
2. ALWAYS detect when users paste your own examples back to you
3. If a user copies your example word-for-word, respond with:
   "⚠️ I notice you copied. Write YOUR OWN version. Change at least 3 words."

## Your Role:
Help students complete Plan → Check → Reflect for ENGLISH writing.
You are a QUESTION-ASKER, not a CONTENT-GENERATOR."""

# ========== Data Storage ==========
DATA_DIR = "srl_writing_data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def save_conversation(user_id: str, conversation_data: dict):
    try:
        file_path = os.path.join(DATA_DIR, f"{user_id}.json")
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
    except Exception as e:
        print(f"❌ 本地保存失败: {e}")
        return False

def save_current_session():
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
        save_to_supabase(
            st.session_state.user_id,
            st.session_state.user_name,
            st.session_state.test_round,
            st.session_state.plan_completed,
            st.session_state.monitoring_count,
            st.session_state.messages
        )
        return True
    return False

# ========== CSS ==========
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&display=swap');
    .stApp { background: linear-gradient(135deg, #c9d4c5 0%, #d4cfc4 20%, #e2dcd0 40%, #ede5d8 60%, #dcd0bd 80%, #c4b8a8 100%); }
    .monet-title { text-align: center; font-family: 'Playfair Display', serif; font-size: 2.8rem; font-weight: 600; color: #2c4a3e; margin-bottom: 0.1rem; }
    .monet-subtitle { text-align: center; color: #5a6e5a; font-size: 0.8rem; font-style: italic; margin-bottom: 0.5rem; }
    .intro-text { text-align: center; color: #4a5e4a; font-size: 0.9rem; max-width: 600px; margin: 0 auto; line-height: 1.5; }
    .stButton > button { background: linear-gradient(135deg, #7c9c8c 0%, #9b8b7a 100%); color: white; border: none; border-radius: 40px; padding: 10px 24px; font-weight: 500; }
    .stButton > button:hover { transform: translateY(-2px); }
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
        st.session_state.selected_model = "deepseek"
        st.session_state.plan_in_progress = False

def do_login(user_id: str, user_name: str, test_round: str = "pre"):
    st.session_state.logged_in = True
    st.session_state.user_id = user_id.strip()
    st.session_state.user_name = user_name.strip()
    st.session_state.test_round = test_round
    st.session_state.messages = []
    st.session_state.plan_completed = False
    st.session_state.monitoring_count = 0
    st.session_state.conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.session_start = datetime.now().isoformat()
    
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"👋 **Welcome, {user_name}!**\n\nI understand that writing can sometimes feel difficult. My role is to help you build confidence.\n\n**Tell me your English writing topic.**"
    })

def do_logout():
    save_current_session()
    st.session_state.logged_in = False
    st.session_state.messages = []
    st.rerun()

# ========== Login Page (已修复 label 警告) ==========
def show_login_page():
    st.markdown('<div class="monet-title">✍️ SRL Writing Coach</div>', unsafe_allow_html=True)
    st.markdown('<div class="monet-subtitle">🎨 Self-Regulated Learning · Like painting with words</div>', unsafe_allow_html=True)
    st.divider()
    
    st.markdown('<h4 style="text-align: center; color: #4a5e4a;">🌸 Sign In</h4>', unsafe_allow_html=True)
    
    user_id = st.text_input("Student ID / Email", placeholder="e.g., 20240001", key="login_id")
    user_name = st.text_input("Your Name", placeholder="e.g., Zhang Wei", key="login_name")
    test_round_option = st.selectbox("Test Round", ["Pre-test", "Post-test"], key="test_round_select")
    
    if st.button("🎨 Enter the Garden", type="primary", use_container_width=True):
        if user_id and user_name:
            round_value = "pre" if test_round_option == "Pre-test" else "post"
            do_login(user_id, user_name, round_value)
            st.rerun()
        else:
            st.warning("Please enter both Student ID and Name.")

# ========== AI Call Functions ==========
def call_deepseek(user_input: str) -> str:
    messages = [{"role": "system", "content": SRL_SYSTEM_PROMPT}]
    for msg in st.session_state.messages[-15:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat", messages=messages, temperature=0.7, max_tokens=1200
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ DeepSeek Error: {str(e)}"

def call_kimi(user_input: str) -> str:
    messages = [{"role": "system", "content": SRL_SYSTEM_PROMPT}]
    for msg in st.session_state.messages[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = kimi_client.chat.completions.create(
            model="moonshot-v1-8k", messages=messages, temperature=0.3, max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Kimi Error: {str(e)}"

def call_ai(user_input: str) -> str:
    if st.session_state.selected_model == "kimi":
        return call_kimi(user_input)
    return call_deepseek(user_input)

# ========== Main App ==========
def main_app():
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <div class="monet-title" style="text-align: left; font-size: 2rem;">✍️ SRL Writing Coach</div>
            <div class="monet-subtitle" style="text-align: left;">🎨 Self-Regulated Learning</div>
        </div>
        <div style="text-align: right;">
            <div>🎨 {st.session_state.user_name}</div>
            <div style="font-size:0.8rem;">{st.session_state.user_id} | {st.session_state.test_round}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    with st.sidebar:
        st.markdown("### 🤖 AI Model")
        selected_model = st.selectbox("Choose AI Coach", ["deepseek", "kimi"], 
                                     format_func=lambda x: "🐋 DeepSeek" if x == "deepseek" else "🌟 Kimi")
        st.session_state.selected_model = selected_model
        
        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            do_logout()

    # 显示聊天记录
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 处理输入
    def handle_input():
        user_input = st.session_state.user_input
        if not user_input or not user_input.strip():
            return
            
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.spinner("🎨 Thinking..."):
            response = call_ai(user_input)
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        save_current_session()
        
        st.session_state.user_input = ""

    # 快捷按钮
    st.markdown("### 🎨 The 3 Steps")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📋 PLAN", use_container_width=True):
            st.session_state.user_input = "Let's start Step 1: Planning. Please help me create an outline."
            handle_input()
    with col2:
        if st.button("✍️ CHECK", use_container_width=True):
            st.session_state.user_input = "Step 2: Please check my paragraph."
            handle_input()
    with col3:
        if st.button("🤔 REFLECT", use_container_width=True):
            st.session_state.user_input = "Step 3: Help me reflect on my writing."
            handle_input()

    st.chat_input("📝 Type your English writing here...", key="user_input", on_submit=handle_input)

# ========== Run ==========
init_session_state()

if st.session_state.logged_in:
    main_app()
else:
    show_login_page()
