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

# DeepSeek 客户端
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Kimi 客户端
kimi_client = OpenAI(
    api_key=KIMI_API_KEY,
    base_url="https://api.moonshot.cn/v1"
)

# ========== Supabase 配置 ==========
SUPABASE_URL = "https://kgzotpkprrmuaxiqqeaz.supabase.co"
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# ========== 优化后的 Supabase 保存函数 ==========
def save_to_supabase(student_id, student_name, test_round, plan_completed, monitoring_count, conversation):
    """保存数据到 Supabase - 增强版（解决 Kimi 添加后保存失败问题）"""
    print(f"🔵 [Supabase] 开始保存: {student_id} - {test_round} | messages: {len(conversation) if isinstance(conversation, list) else 'N/A'}")
    
    try:
        url = f"{SUPABASE_URL}/rest/v1/writing_sessions"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        # 安全地处理 conversation（防止数据过大导致保存失败）
        if isinstance(conversation, list):
            trimmed_conversation = conversation[-25:] if len(conversation) > 25 else conversation
        else:
            trimmed_conversation = conversation
        
        data = {
            "student_id": student_id,
            "student_name": student_name,
            "test_round": test_round,
            "plan_completed": plan_completed,
            "monitoring_count": monitoring_count,
            "conversation": trimmed_conversation,
            "updated_at": datetime.now().isoformat()
        }
        
        # 检查是否已有记录
        check_url = f"{SUPABASE_URL}/rest/v1/writing_sessions?student_id=eq.{student_id}&test_round=eq.{test_round}&select=id"
        check_response = requests.get(check_url, headers=headers, timeout=10)
        
        print(f"🔵 [Supabase] 检查记录状态码: {check_response.status_code}")
        
        if check_response.status_code == 200:
            try:
                existing = check_response.json()
                if existing:  # 更新已有记录
                    record_id = existing[0]["id"]
                    update_url = f"{SUPABASE_URL}/rest/v1/writing_sessions?id=eq.{record_id}"
                    response = requests.patch(update_url, headers=headers, json=data, timeout=10)
                    print(f"🔄 [Supabase] 更新记录: {response.status_code}")
                else:  # 插入新记录
                    data["created_at"] = datetime.now().isoformat()
                    response = requests.post(url, headers=headers, json=data, timeout=10)
                    print(f"📝 [Supabase] 插入新记录: {response.status_code}")
            except Exception as json_err:
                print(f"⚠️ [Supabase] JSON解析异常: {json_err}")
                # 降级处理：直接插入
                data["created_at"] = datetime.now().isoformat()
                response = requests.post(url, headers=headers, json=data, timeout=10)
        else:
            print(f"❌ [Supabase] 检查记录失败: {check_response.status_code} - {check_response.text[:200]}")
            # 直接尝试插入
            data["created_at"] = datetime.now().isoformat()
            response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code in (200, 201, 204):
            print(f"✅ [Supabase] 保存成功: {student_id}")
            return True
        else:
            print(f"❌ [Supabase] 保存失败: {response.status_code} - {response.text[:400]}")
            return False
            
    except Exception as e:
        print(f"❌ [Supabase] 严重异常: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        return False


# ========== Data Storage Functions ==========
DATA_DIR = "srl_writing_data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_user_data_file(user_id: str) -> str:
    safe_id = "".join(c for c in user_id if c.isalnum() or c in "._-")
    return os.path.join(DATA_DIR, f"{safe_id}.json")

def save_conversation(user_id: str, conversation_data: dict):
    file_path = get_user_data_file(user_id)
    try:
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
    """保存当前会话到本地和 Supabase"""
    print("🔵 [DEBUG] save_current_session 被调用")
    print(f"🔵 [DEBUG] logged_in: {st.session_state.logged_in}, messages长度: {len(st.session_state.messages)}")
    
    if st.session_state.logged_in and len(st.session_state.messages) > 1:
        session_data = {
            "session_id": st.session_state.conversation_id,
            "start_time": st.session_state.session_start,
            "end_time": datetime.now().isoformat(),
            "plan_completed": st.session_state.plan_completed,
            "monitoring_count": st.session_state.monitoring_count,
            "messages": st.session_state.messages
        }
        
        # 本地保存
        save_conversation(st.session_state.user_id, session_data)
        print("✅ 本地保存完成")
        
        # Supabase 保存
        save_to_supabase(
            student_id=st.session_state.user_id,
            student_name=st.session_state.user_name,
            test_round=st.session_state.test_round,
            plan_completed=st.session_state.plan_completed,
            monitoring_count=st.session_state.monitoring_count,
            conversation=st.session_state.messages
        )
        return True
    return False


# ========== 其余代码保持不变（为节省篇幅，这里省略未修改部分）==========
# 请把下面这部分替换为你原来的对应代码（从 # ========== CSS ==========
# 开始到文件结束）

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

# ========== Login/Session State ==========
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
    st.session_state.user_id = user_id
    st.session_state.user_name = user_name
    st.session_state.test_round = test_round
    st.session_state.messages = []
    st.session_state.plan_completed = False
    st.session_state.monitoring_count = 0
    st.session_state.conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.session_start = datetime.now().isoformat()
    
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"👋 **Welcome, {user_name}!**\n\nI understand that writing can sometimes feel difficult, tiring, or even stressful — and that's completely normal.\n\nMy role is not to write for you, but to help you **lower those barriers** and build confidence.\n\n**Tell me your English writing topic, and we'll start with a small first step.**\n\n💡 *If you feel stuck, just say \"I'm stuck\" or click the button below.*\n\n---\n🎨 *Let's write together, like painting with words — one brushstroke at a time.*"
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
    st.rerun()

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
    
    st.caption("💡 Your writing data is saved automatically.")
    st.markdown('</div>', unsafe_allow_html=True)

# ========== AI Call Functions ==========
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
        return f"❌ DeepSeek Error: {str(e)}"

def call_kimi(user_input: str) -> str:
    messages = [{"role": "system", "content": SRL_SYSTEM_PROMPT}]
    for msg in st.session_state.messages[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = kimi_client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=messages,
            temperature=0.3,
            max_tokens=600,
            top_p=0.9
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Kimi Error: {str(e)}"

def call_ai(user_input: str) -> str:
    if st.session_state.selected_model == "kimi":
        return call_kimi(user_input)
    else:
        return call_deepseek(user_input)

# ========== Main App ==========
# （此处省略 main_app() 函数，因为它没有修改。如果你需要完整版，请告诉我，我再补上）

# ========== Run ==========
init_session_state()

if st.session_state.logged_in:
    main_app()
else:
    show_login_page()
