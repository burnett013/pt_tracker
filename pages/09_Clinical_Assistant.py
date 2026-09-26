import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from services.ui_components import apply_custom_css
from services.chatbot_service import load_system_knowledge, get_gemini_client

st.set_page_config(
    page_title="Clinical Assistant | Anti-Amyloid Tracker",
    page_icon="🤖",
    layout="wide"
)
apply_custom_css()

st.title("🤖 Clinical AI Assistant")
st.caption("Ask questions about anti-amyloid therapy schedules, ARIA safety guidelines, and how to navigate workflows.")

# Resolve API Key
client = get_gemini_client()

if not client:
    st.info("🔑 **Gemini API Key Required**  \nEnter your Gemini API key below to activate the Clinical Assistant. (You can also store it permanently in `.streamlit/secrets.toml` as `GEMINI_API_KEY` or `[gemini] api_key = ...`).")
    user_key = st.text_input("Gemini API Key*", type="password", placeholder="AIzaSy...")
    if user_key:
        client = get_gemini_client(api_key=user_key)
        if client:
            st.session_state["custom_gemini_key"] = user_key
            st.success("API key accepted!")
            st.rerun()
        else:
            st.error("Invalid API key or failed to initialize client.")
            st.stop()
    else:
        st.stop()

# Initialize Chat Session State
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "👋 Hello! I am your **Clinical Workflow Assistant**. I can guide you through drug surveillance schedules (*Lecanemab* & *Donanemab*), explain required MRI checkpoints, clarify ARIA severity ratings, or help you link follow-up phone calls. How can I help you today?"
        }
    ]

# Top Action Toolbar (Quick Prompts & Reset)
col_prompts, col_clear = st.columns([5, 1])

with col_clear:
    if st.button("🧹 Clear Chat"):
        st.session_state["messages"] = [st.session_state["messages"][0]]
        st.rerun()

with col_prompts:
    st.markdown("**Quick Topics:**")
    q1, q2, q3, q4 = st.columns(4)
    quick_query = None
    if q1.button("📅 Lecanemab MRIs", use_container_width=True):
        quick_query = "When are routine surveillance MRIs required for Lecanemab patients?"
    if q2.button("💊 Donanemab MRIs", use_container_width=True):
        quick_query = "What is the surveillance MRI schedule and interval for Donanemab?"
    if q3.button("📞 Phone Call Linking", use_container_width=True):
        quick_query = "How do I tie a follow-up phone call back to an original call with a pending follow-up?"
    if q4.button("⚠️ ARIA Hold Protocols", use_container_width=True):
        quick_query = "When does the app automatically place a patient on HOLD during MRI or ARIA tracking?"

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# Render Chat History
for msg in st.session_state["messages"]:
    avatar = "🧬" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# Handle Input (via chat input or quick prompt button)
user_prompt = st.chat_input("Ask a question about the tracker, drug schedules, or workflow...") or quick_query

if user_prompt:
    # 1. Display user message
    st.session_state["messages"].append({"role": "user", "content": user_prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_prompt)

    # 2. Generate response from Gemini
    system_instruction = load_system_knowledge()

    # Build conversation contents for Gemini
    contents = []
    for m in st.session_state["messages"]:
        if m["role"] == "user":
            contents.append(f"User: {m['content']}")
        elif m["role"] == "assistant":
            contents.append(f"Assistant: {m['content']}")

    prompt_with_history = "\n\n".join(contents)

    with st.chat_message("assistant", avatar="🧬"):
        with st.spinner("Consulting clinical guidelines..."):
            try:
                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt_with_history,
                    config={
                        "system_instruction": system_instruction,
                        "temperature": 0.2
                    }
                )
                assistant_reply = response.text
                st.markdown(assistant_reply)
                st.session_state["messages"].append({"role": "assistant", "content": assistant_reply})
            except Exception as e:
                st.error(f"Error communicating with Gemini: {e}")
