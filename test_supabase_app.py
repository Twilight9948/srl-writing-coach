import streamlit as st
import requests
from datetime import datetime

st.set_page_config(page_title="Supabase 连接测试", layout="centered")

st.title("🔌 Supabase 连接测试")
st.markdown("测试 Streamlit Cloud 能否成功写入 Supabase")

# 从 secrets 读取配置
SUPABASE_URL = "https://srl-writing-coach.supabase.co"
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

st.markdown("---")

# 测试输入
col1, col2 = st.columns(2)
with col1:
    user_id = st.text_input("Student ID", value="test_20260527")
with col2:
    user_name = st.text_input("Name", value="Test User")

# 测试按钮
if st.button("📤 发送测试数据到 Supabase", type="primary"):
    with st.spinner("正在发送..."):
        url = f"{SUPABASE_URL}/rest/v1/writing_sessions"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        data = {
            "student_id": user_id,
            "student_name": user_name,
            "test_round": "test",
            "plan_completed": False,
            "monitoring_count": 0,
            "conversation": [{"role": "test", "content": "This is a test message"}],
            "created_at": datetime.now().isoformat()
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=15)
            st.markdown("---")
            st.subheader("📡 响应结果")
            st.write(f"**状态码:** `{response.status_code}`")
            st.write(f"**响应内容:**")
            st.code(response.text, language="json")
            
            if response.status_code == 201:
                st.success("✅ 测试成功！数据已写入 Supabase")
                st.balloons()
            elif response.status_code == 401:
                st.error("❌ 认证失败：API Key 无效")
            elif response.status_code == 403:
                st.error("❌ 权限不足：请检查 RLS 设置")
            else:
                st.warning(f"⚠️ 未预期的状态码: {response.status_code}")
        except requests.exceptions.Timeout:
            st.error("❌ 连接超时：Supabase 响应太慢")
        except Exception as e:
            st.error(f"❌ 错误: {str(e)}")

st.markdown("---")
st.caption("💡 如果测试成功，说明 Supabase 连接正常，问题在主应用代码中")
st.caption("🔑 使用的 Supabase Key 类型: publishable key")