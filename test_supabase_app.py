import streamlit as st
import requests
from datetime import datetime

st.set_page_config(page_title="Supabase 连接测试", layout="centered")

st.title("🔌 Supabase 连接测试")

# 诊断：显示所有 secrets keys
st.write("📋 可用的 secrets keys:", list(st.secrets.keys()))

# 尝试获取 SUPABASE_KEY
try:
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    st.success("✅ SUPABASE_KEY 读取成功")
except KeyError as e:
    st.error(f"❌ 找不到 SUPABASE_KEY: {e}")
    st.stop()

SUPABASE_URL = "https://srl-writing-coach.supabase.co"

st.markdown("---")

# 测试输入
col1, col2 = st.columns(2)
with col1:
    user_id = st.text_input("Student ID", value="test_20260527")
with col2:
    user_name = st.text_input("Name", value="Test User")

if st.button("📤 发送测试数据"):
    url = f"{SUPABASE_URL}/rest/v1/writing_sessions"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "student_id": user_id,
        "student_name": user_name,
        "test_round": "test",
        "plan_completed": False,
        "monitoring_count": 0,
        "conversation": [{"role": "test", "content": "test"}],
        "created_at": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        st.write(f"状态码: {response.status_code}")
        st.write(f"响应: {response.text}")
        if response.status_code == 201:
            st.success("✅ 成功！")
    except Exception as e:
        st.error(f"错误: {e}")
