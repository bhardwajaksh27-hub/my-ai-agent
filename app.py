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

# --- 1. PAGE CONFIG & CUSTOM THEME ---
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
    <div class="aksh-signature">CLOUD_VAULT_GSHEETS // AKSH • 2026</div>
    """, unsafe_allow_html=True)

# --- 2. GOOGLE SHEETS CONNECTION (The Cloud Vault) ---
# Note: Requires "gsheets" configuration in st.secrets
conn = st.connection("gsheets", type=GSheetsConnection)

def save_to_cloud_vault(role, content):
    """Appends data to the Google Sheet."""
    try:
        # Fetch current data
        df = conn.read(ttl=0) 
        
        # Create new record
        new_data = pd.DataFrame([{
            "Timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d %H:%M:%S"),
            "Role": role,
            "Content": content
        }])
        
        # Combine and update
        updated_df = pd.concat([df, new_data], ignore_index=True)
        conn.update(data=updated_df)
    except Exception as e:
        st.error(f"Cloud Save Error: {e}")

def load_cloud_vault():
    """Retrieves history from Google Sheets."""
    try:
        df = conn.read(ttl=0)
        return df.to_dict(orient="records")
    except:
        return []

# --- 3. MODELS & SETUP ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("⚠️ API Key Not Found! Check Streamlit Secrets.")
    st.stop()

MODEL_OPTIONS = {
    "Gemini 2.5 Flash-Lite (High Quota)": "gemini-2.5-flash-lite",
    "Gemini 3 Flash (Fastest)": "gemini-3-flash-preview",
    "Gemini 2.5 Pro (Deep Reasoning)": "gemini-2.5-pro"
}

PERSONAS = {
    "Professor P": "A grumpy, sarcastic British academic.",
    "Alfred": "A polite, formal butler.",
    "Zero": "A punchy, cool cyberpunk hacker."
}

# --- 4. TEMPORAL AWARENESS ---
local_tz = pytz.timezone('Asia/Kolkata')
now = datetime.now(local_tz)
current_time_str = now.strftime("%I:%M %p")

# --- 5. SESSION STATE (Load from Cloud) ---
if "messages" not in st.session_state:
    saved_chats = load_cloud_vault()
    if saved_chats:
        st.session_state.messages = saved_chats
    else:
        st.session_state.messages = [{"role": "assistant", "content": "👋 **Cloud Vault Online.** History Sync Complete."}]

if "chat_history_summary" not in st.session_state:
    st.session_state.chat_history_summary = [m["Content"][:25] + "..." for m in st.session_state.messages if m["role"] == "user"]

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("Vault Control")
    selected_model_label = st.selectbox("Switch Brain", list(MODEL_OPTIONS.keys()))
    current_model = MODEL_OPTIONS[selected_model_label]
    current_persona = st.selectbox("Switch Persona", list(PERSONAS.keys()))
    
    st.divider()
    st.metric("🕒 IST", current_time_str)
    
    st.subheader("📜 Cloud Logs")
    for q in st.session_state.chat_history_summary[-5:]:
        st.caption(f"• {q}")
        
    if st.button("Reset View"):
        st.session_state.messages = [{"role": "assistant", "content": "👋 **View Reset.**"}]
        st.rerun()

# --- 7. OPTIMIZATION FUNCTIONS ---
def process_image(uploaded_file):
    image = Image.open(uploaded_file)
    if image.mode in ("RGBA", "P"): image = image.convert("RGB")
    image.thumbnail((800, 800))
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG', quality=75)
    return img_byte_arr.getvalue()

def speak(text, persona):
    voice = "Daniel" if persona == "Professor P" else "Samantha"
    os.system(f'say -v "{voice}" "{text.replace("\"", "").replace("\n", " ")}" &')

# --- 8. CHAT INTERFACE ---
for message in st.session_state.messages:
    # Handle both lowercase 'role' and uppercase 'Role' from DataFrame
    role = message.get("role") or message.get("Role")
    content = message.get("content") or message.get("Content")
    with st.chat_message(role):
        st.markdown(content)

uploaded_file = st.file_uploader("Upload Data", type=["jpg", "png", "jpeg"])
user_input = st.chat_input("Enter your research query...")

if user_input:
    # Update Session & Cloud
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_to_cloud_vault("user", user_input)
    
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner(f"Consulting {current_model}..."):
            try:
                instruction = f"You are {current_persona}. {PERSONAS[current_persona]}. Time: {current_time_str}."
                content_parts = [user_input]
                if uploaded_file:
                    img_data = process_image(uploaded_file)
                    content_parts.append(types.Part.from_bytes(data=img_data, mime_type="image/jpeg"))

                response = client.models.generate_content(model=current_model, contents=content_parts, config={"system_instruction": instruction})
                answer = response.text
                
                # Search Trigger Logic
                if "SEARCH:" in answer:
                    query = answer.split("SEARCH:")[1].strip()
                    with DDGS() as ddgs:
                        search_results = [r['body'] for r in ddgs.text(query, max_results=2)]
                    final_res = client.models.generate_content(model=current_model, contents=f"Context: {' '.join(search_results)} \n\n {user_input}", config={"system_instruction": instruction})
                    answer = final_res.text

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                save_to_cloud_vault("assistant", answer)
                speak(answer, current_persona)

            except Exception as e:
                if "429" in str(e):
                    st.error("🚨 Quota Limit! Switch to Flash-Lite.")
                else:
                    st.error(f"Error: {e}")