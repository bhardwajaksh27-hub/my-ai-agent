import streamlit as st
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
import os
from PIL import Image
import io

# --- 1. PAGE CONFIG & UI ---
st.set_page_config(page_title="AI Research Hub 2026", page_icon="🚀", layout="wide")
st.title("🤖 Multimodal Research Agent")

# --- 2. SECURE SETUP & 2026 MODELS ---
try:
    # Looks for GEMINI_API_KEY in Streamlit Secrets
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("⚠️ API Key Not Found! Go to Settings > Secrets and add GEMINI_API_KEY.")
    st.stop()

# UPDATED: Verified 2026 Model IDs
MODEL_OPTIONS = {
    "Gemini 3 Flash (Fastest/Newest)": "gemini-3-flash-preview",
    "Gemini 2.5 Flash (Most Reliable)": "gemini-2.5-flash",
    "Gemini 2.5 Pro (Deep Reasoning)": "gemini-2.5-pro",
    "Gemini 2.5 Flash-Lite (Best for Quota)": "gemini-2.5-flash-lite"
}

PERSONAS = {
    "Professor P": "A grumpy, sarcastic British academic. You find most questions tedious but provide brilliant data.",
    "Alfred": "A polite, formal butler. You refer to the user as 'Master' and focus on being impeccably helpful.",
    "Zero": "A punchy, cool cyberpunk hacker. You use tech slang and focus on speed and digital edge."
}

# --- 3. SESSION STATE (Welcome & History) ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "👋 **Welcome! You are speaking with an AI Research Agent created by Aksh.**"}
    ]
if "chat_history_summary" not in st.session_state:
    st.session_state.chat_history_summary = []

# --- 4. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("Control Panel")
    selected_model_label = st.selectbox("Switch Model", list(MODEL_OPTIONS.keys()))
    current_model = MODEL_OPTIONS[selected_model_label]
    current_persona = st.selectbox("Choose Persona", list(PERSONAS.keys()))
    
    st.divider()
    
    # NEW: Chat History Log
    st.subheader("📜 Recent Questions")
    if st.session_state.chat_history_summary:
        for q in st.session_state.chat_history_summary:
            st.write(f"• {q}")
    else:
        st.write("No questions yet.")

    st.divider()
    if st.button("Clear Conversation"):
        st.session_state.messages = [{"role": "assistant", "content": "👋 **Welcome to an agent made by Aksh.**"}]
        st.session_state.chat_history_summary = []
        st.rerun()

# --- 5. IMAGE PROCESSING (RGBA Fix) ---
def process_image(uploaded_file):
    image = Image.open(uploaded_file)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    image.thumbnail((800, 800))
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG', quality=75)
    return img_byte_arr.getvalue()

# --- 6. CHAT INTERFACE ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

uploaded_file = st.file_uploader("Drop an image for analysis...", type=["jpg", "png", "jpeg"])
user_input = st.chat_input("Ask a question...")

if user_input:
    # Add to Sidebar History
    st.session_state.chat_history_summary.append(user_input[:30] + "...")
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner(f"Consulting {current_model}..."):
            try:
                instruction = f"Your name is {current_persona}. {PERSONAS[current_persona]}. If you need live info, reply with 'SEARCH: <query>'."
                
                content_parts = [user_input]
                if uploaded_file:
                    compressed_img = process_image(uploaded_file)
                    content_parts.append(types.Part.from_bytes(data=compressed_img, mime_type="image/jpeg"))

                response = client.models.generate_content(
                    model=current_model,
                    contents=content_parts,
                    config={"system_instruction": instruction}
                )
                answer = response.text
                
                if "SEARCH:" in answer:
                    query = answer.split("SEARCH:")[1].strip()
                    st.write(f"🔍 *{current_persona} is searching for: {query}...*")
                    with DDGS() as ddgs:
                        search_results = [r['body'] for r in ddgs.text(query, max_results=2)]
                    
                    final_res = client.models.generate_content(
                        model=current_model,
                        contents=f"Context: {' '.join(search_results)} \n\n Question: {user_input}",
                        config={"system_instruction": instruction}
                    )
                    answer = final_res.text

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # macOS Voice Output
                voice = "Daniel" if current_persona == "Professor P" else "Samantha"
                os.system(f'say -v "{voice}" "{answer.replace("\"", "").replace("\n", " ")}"')

            except Exception as e:
                st.error(f"❌ Error: {e}")