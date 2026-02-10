import streamlit as st
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
import os
import sqlite3
from PIL import Image
import io
from datetime import datetime
import pytz

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
    <div class="aksh-signature">RESEARCH_VAULT_V1 // AKSH • 2026</div>
    """, unsafe_allow_html=True)

# --- 2. PERMANENT DATABASE (The Vault) ---
def init_db():
    """Initializes the SQLite database."""
    conn = sqlite3.connect('research_vault.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (timestamp TEXT, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

def save_to_vault(role, content):
    """Saves a single message to the permanent database."""
    conn = sqlite3.connect('research_vault.db')
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES (?, ?, ?)", 
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), role, content))
    conn.commit()
    conn.close()

def load_vault():
    """Retrieves all previous messages from the database."""
    conn = sqlite3.connect('research_vault.db')
    c = conn.cursor()
    c.execute("SELECT role, content FROM history ORDER BY timestamp ASC")
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

def clear_vault():
    """Wipes the database."""
    conn = sqlite3.connect('research_vault.db')
    c = conn.cursor()
    c.execute("DELETE FROM history")
    conn.commit()
    conn.close()

init_db()

# --- 3. MODELS & SETUP ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("⚠️ API Key Not Found in Secrets!")
    st.stop()

MODEL_OPTIONS = {
    "Gemini 2.5 Flash-Lite (High Quota)": "gemini-2.5-flash-lite",
    "Gemini 3 Flash (Fastest)": "gemini-3-flash-preview",
    "Gemini 2.5 Pro (Deep Reasoning)": "gemini-2.5-pro"
}

PERSONAS = {
    "Professor P": "A grumpy, sarcastic British academic.",
    "Alfred": "A polite, formal butler. You refer to the user as 'Master'.",
    "Zero": "A punchy, cool cyberpunk hacker."
}

# --- 4. TEMPORAL AWARENESS ---
local_tz = pytz.timezone('Asia/Kolkata')
now = datetime.now(local_tz)
current_time_str = now.strftime("%I:%M %p")
current_date_str = now.strftime("%A, %B %d, %Y")

# --- 5. SESSION STATE (Load from Vault) ---
if "messages" not in st.session_state:
    saved_chats = load_vault()
    if saved_chats:
        st.session_state.messages = saved_chats
    else:
        st.session_state.messages = [{"role": "assistant", "content": f"👋 **Vault Online.** Today is {current_date_str}. History Loaded."}]

if "chat_history_summary" not in st.session_state:
    st.session_state.chat_history_summary = [m["content"][:25] + "..." for m in st.session_state.messages if m["role"] == "user"]

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("Vault Control")
    selected_model_label = st.selectbox("Switch Brain", list(MODEL_OPTIONS.keys()))
    current_model = MODEL_OPTIONS[selected_model_label]
    current_persona = st.selectbox("Switch Persona", list(PERSONAS.keys()))
    
    st.divider()
    st.metric("🕒 IST", current_time_str)
    
    st.subheader("📜 History")
    for q in st.session_state.chat_history_summary[-7:]:
        st.caption(f"• {q}")
        
    st.divider()
    if st.button("Purge Vault"):
        clear_vault()
        st.session_state.messages = [{"role": "assistant", "content": "👋 **Vault Purged.**"}]
        st.session_state.chat_history_summary = []
        st.rerun()

# --- 7. CORE FUNCTIONS ---
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
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

uploaded_file = st.file_uploader("Upload Data", type=["jpg", "png", "jpeg"])
user_input = st.chat_input("Enter your research query...")

if user_input:
    # Save User message
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.chat_history_summary.append(user_input[:25] + "...")
    save_to_vault("user", user_input)
    
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner(f"Consulting {current_model}..."):
            try:
                instruction = f"You are {current_persona}. {PERSONAS[current_persona]}. Time: {current_time_str}. Search: 'SEARCH: <query>'."
                content_parts = [user_input]
                if uploaded_file:
                    img_data = process_image(uploaded_file)
                    content_parts.append(types.Part.from_bytes(data=img_data, mime_type="image/jpeg"))

                response = client.models.generate_content(model=current_model, contents=content_parts, config={"system_instruction": instruction})
                answer = response.text
                
                if "SEARCH:" in answer:
                    query = answer.split("SEARCH:")[1].strip()
                    with DDGS() as ddgs:
                        search_results = [r['body'] for r in ddgs.text(query, max_results=2)]
                    final_res = client.models.generate_content(model=current_model, contents=f"Context: {' '.join(search_results)} \n\n {user_input}", config={"system_instruction": instruction})
                    answer = final_res.text

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                save_to_vault("assistant", answer) # Save Assistant message
                speak(answer, current_persona)

            except Exception as e:
                if "429" in str(e):
                    st.error("🚨 Quota Limit! Switching to Flash-Lite is recommended.")
                else:
                    st.error(f"Error: {e}")