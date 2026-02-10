import streamlit as st
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
import os
import time
from PIL import Image
import io

# --- 1. PAGE CONFIG & UI ---
st.set_page_config(page_title="AI Research Hub 2026", page_icon="🚀", layout="wide")
st.title("🤖 Multimodal Research Agent")

# --- 2. SECURE SETUP & 2026 MODELS ---
# SECURE: Using Streamlit Secrets instead of hardcoding the key
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("Missing API Key! Please add GEMINI_API_KEY to your Streamlit Secrets.")
    st.stop()

# UPDATED: Current 2026 Model IDs
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

# --- 3. SESSION STATE (Memory) ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 4. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("Control Panel")
    selected_model_label = st.selectbox("Switch Model", list(MODEL_OPTIONS.keys()))
    current_model = MODEL_OPTIONS[selected_model_label]
    
    current_persona = st.selectbox("Choose Persona", list(PERSONAS.keys()))
    
    st.divider()
    if st.button("Clear Conversation"):
        st.session_state.messages = []
        st.rerun()
    
    st.info("💡 2026 Tip: Use 'Flash-Lite' if you hit rate limits.")

# --- 5. IMAGE PROCESSING (RGBA Fix) ---
def process_image(uploaded_file):
    """Resizes and converts images to prevent 'RGBA to JPEG' errors."""
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

                # API Call
                response = client.models.generate_content(
                    model=current_model,
                    contents=content_parts,
                    config={"system_instruction": instruction}
                )
                
                answer = response.text
                
                # Search Tool Logic
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
                
                # macOS Voice Output (Note: Works locally only)
                voice = "Daniel" if current_persona == "Professor P" else "Samantha"
                os.system(f'say -v "{voice}" "{answer.replace("\"", "").replace("\n", " ")}"')

            except Exception as e:
                if "429" in str(e):
                    st.error("🚨 Rate Limit! Switch to 'Flash-Lite' or wait 30s.")
                else:
                    st.error(f"❌ Error: {e}")