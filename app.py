import re, io, hashlib, urllib.parse, time
import requests
import streamlit as st
from google import genai
from google.genai import types
from gtts import gTTS

st.set_page_config(page_title="Adventure AI", page_icon="🧭")
st.title("🧭 Adventure AI")

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
SYSTEM = "You are Adventure AI, a friendly assistant. Reply in the same language the user uses (Bangla or English). Keep answers clear."

PREFERRED = ["gemini-3.8-flash"]


@st.cache_resource
def get_models():
    names = list(PREFERRED)
    try:
        for m in client.models.list():
            n = m.name.replace("models/", "")
            if "flash" in n and n not in names and "image" not in n and "tts" not in n:
                names.append(n)
    except Exception:
        pass
    return names[:4]


def ask_gemini(contents):
    last_err = None
    for model in get_models():
        for attempt in range(3):
            try:
                res = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM),
                )
                return res.text
            except Exception as e:
                last_err = e
                s = str(e)
                if "404" in s:
                    break  # ei model nei, porer model e jao
                if "503" in s or "UNAVAILABLE" in s or "429" in s or "disconnected" in s:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
    raise last_err


def speak_out(text):
    clean = re.sub(r"[*#`_>]", "", text)[:600]
    lang = "bn" if re.search(r"[\u0980-\u09FF]", clean) else "en"
    fp = io.BytesIO()
    gTTS(clean, lang=lang).write_to_fp(fp)
    st.audio(fp.getvalue(), format="audio/mp3")


if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    speak = st.toggle("🔊 Voice reply", True)
    up = st.file_uploader("Image / PDF / TXT", type=["png", "jpg", "jpeg", "pdf", "txt"])
    st.caption("Chhobi banate lekho: /image a dragon over mountains")
    voice = st.audio_input("🎤 Voice message")
    if st.button("Clear chat"):
        st.session_state.history = []
        st.rerun()

for m in st.session_state.history:
    with st.chat_message(m["role"]):
        st.write(m["text"])
        if m.get("img"):
            st.image(m["img"])

prompt = st.chat_input("Message likho...")

audio_bytes = None
if voice:
    b = voice.getvalue()
    h = hashlib.md5(b).hexdigest()
    if st.session_state.get("last_audio") != h:
        st.session_state.last_audio = h
        audio_bytes = b

if prompt or audio_bytes:
    user_text = prompt or "🎤 (voice message)"
    st.session_state.history.append({"role": "user", "text": user_text})
    with st.chat_message("user"):
        st.write(user_text)

    with st.chat_message("assistant"):
        # Image generation
        if prompt and prompt.lower().startswith("/image"):
            desc = prompt[6:].strip() or "beautiful adventure landscape"
            with st.spinner("Chhobi toiri hochhe..."):
                url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(desc) + "?width=768&height=768&nologo=true"
                try:
                    r = requests.get(url, timeout=120)
                except Exception:
                    r = None
            if r is not None and r.ok:
                st.image(r.content)
                st.session_state.history.append({"role": "assistant", "text": f"Image: {desc}", "img": r.content})
            else:
                st.error("Image toiri hoyni, abar chesta koro.")
        else:
            contents = []
            for m in st.session_state.history[:-1]:
                role = "user" if m["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part(text=m["text"])]))
            parts = []
            if up:
                parts.append(types.Part.from_bytes(data=up.getvalue(), mime_type=up.type or "text/plain"))
            if audio_bytes:
                parts.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"))
                parts.append(types.Part(text="This is the user's voice message. Understand it and reply."))
            else:
                parts.append(types.Part(text=prompt))
            contents.append(types.Content(role="user", parts=parts))
            try:
                with st.spinner("Bhabchi..."):
                    answer = ask_gemini(contents)
            except Exception as e:
                answer = f"Error: {e}"
            st.write(answer)
            st.session_state.history.append({"role": "assistant", "text": answer})
            if speak and not answer.startswith("Error"):
                try:
                    speak_out(answer)
                except Exception:
                    st.caption("Voice reply toiri hoyni (internet check koro).")