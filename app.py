import streamlit as st
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
import os
from PIL import Image
import io
from datetime import datetime
import pytz

# --- 1. PAGE CONFIG & CUSTOM THEMING ---
st.set_page_config(page_title="Research Hub 2026", page_icon="🚀", layout="wide")

# Custom CSS for the Subtle Signature and Sidebar Styling
st.markdown("""
    <style>
    /* Styling the sidebar signature */
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
    /* Making sidebar metrics cleaner */
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #4A90E2;
    }
    </style>
    <div class="aksh-signature">DEV_SYSTEM_V3 // AKSH • 2026</div>
    """, unsafe_allow_html=True)

st.title("🤖 AI Research Agent")

# --- 2. SECURE SETUP & 2026 MODELS ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("⚠️ API Key Not Found! Update your Streamlit Cloud Secrets.")
    st.stop()

# 2026 Model IDs: Switch to Flash-Lite if you hit quota limits
MODEL_OPTIONS = {
    "Gemini 3 Flash (Fastest)": "gemini-3-flash-preview",
    "Gemini 2.5 Flash-Lite (Quota Friendly)": "gemini-2.5-flash-lite",
    "Gemini 2.5 Pro (Deep Reasoning)": "gemini-2.5-pro"
}

PERSONAS = {
    "Professor P": "A grumpy, sarcastic British academic.",
    "Alfred": "A polite, formal butler. You refer to the user as 'Master'.",
    "Zero": "A punchy, cool cyberpunk hacker."
}

# --- 3. TEMPORAL AWARENESS ---
local_tz = pytz.timezone('Asia/Kolkata')
now = datetime.now(local_tz)
current_time_str = now.strftime("%I:%M %p")
current_date_str = now.strftime("%A, %B %d, %Y")

# --- 4. SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": f"👋 **Research Hub Online.** \n\nSystem Time: {current_time_str}. How can I assist?"}]
if "chat_history_summary" not in st.session_state:
    st.session_state.chat_history_summary = []

# --- 5. SIDEBAR (Themed & Clean) ---
with st.sidebar:
    st.header("Control Panel")
    selected_model_label = st.selectbox("Switch Brain", list(MODEL_OPTIONS.keys()))
    current_model = MODEL_OPTIONS[selected_model_label]
    current_persona = st.selectbox("Switch Persona", list(PERSONAS.keys()))
    
    st.divider()
    st.metric("🕒 IST", current_time_str)
    
    st.subheader("📜 History")
    for q in st.session_state.chat_history_summary[-5:]: # Show last 5
        st.caption(f"• {q}")
        
    st.divider()
    if st.button("Reset Session"):
        st.session_state.messages = [{"role": "assistant", "content": "👋 **System Reset.**"}]
        st.session_state.chat_history_summary = []
        st.rerun()

# --- 6. OPTIMIZATION & VOICE FUNCTIONS ---
def process_image(uploaded_file):
    """Compresses images to save tokens and prevent RGBA errors."""
    image = Image.open(uploaded_file)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    image.thumbnail((800, 800))
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG', quality=75)
    return img_byte_arr.getvalue()

def speak(text, persona):
    """Local macOS Voice Output."""
    voice = "Daniel" if persona == "Professor P" else "Samantha"
    clean_text = text.replace('"', '').replace('\n', ' ')
    os.system(f'say -v "{voice}" "{clean_text}" &')

# --- 7. CHAT INTERFACE ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

uploaded_file = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg"])
user_input = st.chat_input("Enter your query...")

if user_input:
    st.session_state.chat_history_summary.append(user_input[:25] + "...")
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner(f"Processing via {current_model}..."):
            try:
                instruction = (
                    f"You are {current_persona}. {PERSONAS[current_persona]}. "
                    f"Time: {current_time_str}. Search trigger: 'SEARCH: <query>'."
                )
                
                content_parts = [user_input]
                if uploaded_file:
                    img_data = process_image(uploaded_file)
                    content_parts.append(types.Part.from_bytes(data=img_data, mime_type="image/jpeg"))

                response = client.models.generate_content(
                    model=current_model, contents=content_parts, config={"system_instruction": instruction}
                )
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
                st.session_state.messages.append({"role": "assistant", "content": answer})
                speak(answer, current_persona)

            except Exception as e:
                if "429" in str(e):
                    st.error("🚨 Quota Limit! Switch to Flash-Lite in the sidebar.")
                else:
                    st.error(f"Error: {e}")