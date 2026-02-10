import streamlit as st
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
import os
from PIL import Image
import io
from datetime import datetime
import pytz
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(page_title="Research Vault 2026", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .aksh-signature {
        position: fixed;
        bottom: 20px;
        left: 20px;
        color: #888888;
        font-size: 11px;
        font-family: 'Inter', sans-serif;
        letter-spacing: 0.5px;
        opacity: 0.7;
    }
    </style>
    <div class="aksh-signature">PRODUCTION_VAULT_V3 // AKSH • 2026</div>
    """, unsafe_allow_html=True)

# --- 2. CLOUD VAULT & COST TRACKING ---
conn = st.connection("gsheets", type=GSheetsConnection)

if "total_spend" not in st.session_state:
    st.session_state.total_spend = 0.0

def save_to_cloud_vault(role, content):
    try:
        df = conn.read(ttl=0)
        new_data = pd.DataFrame([{
            "Timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d %H:%M:%S"),
            "Role": role,
            "Content": content
        }])
        updated_df = pd.concat([df, new_data], ignore_index=True)
        conn.update(data=updated_df)
    except Exception as e:
        st.error(f"Cloud Save Error: {e}")

def load_cloud_vault():
    try:
        data = conn.read(ttl=0)
        return data.to_dict(orient="records") if not data.empty else []
    except:
        return []

# --- 3. CORE SETUP ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("⚠️ API Key Missing in Secrets!")
    st.stop()

MODEL_OPTIONS = {
    "Gemini 2.5 Flash-Lite ($0.10/1M)": "gemini-2.5-flash-lite",
    "Gemini 3 Flash ($0.50/1M)": "gemini-3-flash-preview"
}

PERSONAS = {
    "Professor P": "A grumpy, sarcastic British academic.",
    "Alfred": "A polite, formal butler.",
    "Zero": "A cool cyberpunk hacker."
}

local_tz = pytz.timezone('Asia/Kolkata')
current_time_str = datetime.now(local_tz).strftime("%I:%M %p")

# --- 4. SAFE SESSION INITIALIZATION ---
if "messages" not in st.session_state:
    saved_chats = load_cloud_vault()
    st.session_state.messages = saved_chats if saved_chats else [{"Role": "assistant", "Content": "👋 Vault Secure. Enter Password."}]

if "chat_history_summary" not in st.session_state:
    summary_list = []
    for m in st.session_state.messages:
        m_role = m.get("Role") or m.get("role")
        m_content = m.get("Content") or m.get("content", "")
        if m_role == "user":
            summary_list.append(str(m_content)[:25] + "...")
    st.session_state.chat_history_summary = summary_list

# --- 5. SIDEBAR (Control Panel) ---
with st.sidebar:
    st.header("Vault Control")
    
    # NEW: Friend Access Control
    password = st.text_input("Vault Key", type="password")
    is_authenticated = (password == st.secrets.get("VAULT_PASSWORD", "Aksh2026"))
    
    selected_model_label = st.selectbox("Switch Brain", list(MODEL_OPTIONS.keys()))
    current_model = MODEL_OPTIONS[selected_model_label]
    current_persona = st.selectbox("Switch Persona", list(PERSONAS.keys()))
    
    st.divider()
    st.metric("🕒 IST", current_time_str)
    st.metric("💳 Session Spend", f"${st.session_state.total_spend:.5f}")
    
    st.subheader("📜 Recent Logs")
    for q in st.session_state.chat_history_summary[-5:]:
        st.caption(f"• {q}")
    
    if st.button("Refresh & Sync"):
        st.session_state.clear()
        st.rerun()

# --- 6. UTILITIES ---
def process_image(uploaded_file):
    image = Image.open(uploaded_file)
    if image.mode in ("RGBA", "P"): image = image.convert("RGB")
    image.thumbnail((800, 800))
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG', quality=75)
    return img_byte_arr.getvalue()

# --- 7. CHAT INTERFACE ---
for message in st.session_state.messages:
    m_role = message.get("Role") or message.get("role") or "assistant"
    m_content = message.get("Content") or message.get("content") or ""
    with st.chat_message(m_role):
        st.markdown(m_content)

if is_authenticated:
    uploaded_file = st.file_uploader("Upload Data", type=["jpg", "png", "jpeg"])
    user_input = st.chat_input("Enter your research query...")

    if user_input:
        st.session_state.messages.append({"Role": "user", "Content": user_input})
        st.session_state.chat_history_summary.append(user_input[:25] + "...")
        save_to_cloud_vault("user", user_input)
        
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                try:
                    instruction = f"You are {current_persona}. {PERSONAS[current_persona]}. Time: {current_time_str}."
                    content_parts = [user_input]
                    if uploaded_file:
                        img_data = process_image(uploaded_file)
                        content_parts.append(types.Part.from_bytes(data=img_data, mime_type="image/jpeg"))

                    response = client.models.generate_content(
                        model=current_model, 
                        contents=content_parts, 
                        config={"system_instruction": instruction}
                    )
                    
                    # --- COST CALCULATION ---
                    usage = response.usage_metadata
                    p_tok = usage.prompt_token_count
                    o_tok = usage.candidates_token_count
                    # Rates: $0.10/1M input, $0.40/1M output (Lite default)
                    cost = (p_tok * (0.10 / 1_000_000)) + (o_tok * (0.40 / 1_000_000))
                    st.session_state.total_spend += cost
                    
                    answer = response.text
                    
                    if "SEARCH:" in answer:
                        query = answer.split("SEARCH:")[1].strip()
                        with DDGS() as ddgs:
                            search_results = [r['body'] for r in ddgs.text(query, max_results=2)]
                        final_res = client.models.generate_content(
                            model=current_model, 
                            contents=f"Context: {' '.join(search_results)} \n\n {user_input}", 
                            config={"system_instruction": instruction}
                        )
                        answer = final_res.text

                    st.markdown(answer)
                    st.caption(f"Tokens: {p_tok} in / {o_tok} out | Cost: ${cost:.5f}")
                    st.session_state.messages.append({"Role": "assistant", "Content": answer})
                    save_to_cloud_vault("assistant", answer)

                except Exception as e:
                    if "429" in str(e):
                        st.error("🚨 Credits Exhausted! Wait 60 seconds or switch to Lite.")
                    else:
                        st.error(f"Error: {e}")
else:
    st.info("🔓 Please enter the Vault Key in the sidebar to begin research.")