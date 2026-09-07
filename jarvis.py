import ast
import base64
import html
import os
import platform
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import streamlit as st

# Optional packages. The app still runs without them.
try:
    import psutil
except ImportError:
    psutil = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from google import genai
except ImportError:
    genai = None

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="JARVIS AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# PATHS / CONFIG
# ============================================================

BACKGROUND_IMAGE = Path("assets/jarvis_background.jpg")
MAX_HISTORY = 20

# ============================================================
# BACKGROUND
# ============================================================


def set_background(image_path: Path):
    if image_path.exists():
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode()

        st.markdown(
            f"""
            <style>
            .stApp {{
                background:
                    linear-gradient(
                        rgba(3, 7, 18, 0.78),
                        rgba(3, 7, 18, 0.90)
                    ),
                    url("data:image/jpeg;base64,{encoded_image}");
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <style>
            .stApp {
                background: linear-gradient(135deg, #020617, #0f172a, #111827);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )


set_background(BACKGROUND_IMAGE)

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-left: 2.5rem;
        padding-right: 2.5rem;
        padding-bottom: 2rem;
    }

    .glass {
        background: rgba(15, 23, 42, 0.70);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 24px;
        padding: 26px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.45);
        margin-bottom: 18px;
    }

    .jarvis-title {
        font-size: 52px;
        font-weight: 800;
        letter-spacing: 6px;
        text-align: center;
        color: white;
        text-shadow: 0 0 10px rgba(56,189,248,0.8),
                     0 0 30px rgba(56,189,248,0.5);
    }

    .jarvis-subtitle {
        text-align: center;
        color: #94a3b8;
        font-size: 16px;
        letter-spacing: 2px;
        margin-bottom: 14px;
    }

    .online {
        text-align: center;
        color: #4ade80;
        font-size: 16px;
        font-weight: 700;
        letter-spacing: 1px;
    }

    .response {
        background: rgba(2,6,23,0.82);
        border: 1px solid rgba(56,189,248,0.30);
        border-radius: 18px;
        padding: 22px;
        color: white;
        font-size: 18px;
        line-height: 1.6;
        min-height: 110px;
        box-shadow: inset 0 0 25px rgba(14,165,233,0.05);
    }

    .history {
        background: rgba(15,23,42,0.65);
        border-radius: 15px;
        padding: 14px 16px;
        margin-bottom: 10px;
        border-left: 3px solid #38bdf8;
        color: #e2e8f0;
    }

    .metric-card {
        background: rgba(2,6,23,0.65);
        border: 1px solid rgba(148,163,184,0.15);
        border-radius: 16px;
        padding: 15px;
        text-align: center;
        margin-top: 8px;
    }

    .metric-value {
        color: #e0f2fe;
        font-size: 24px;
        font-weight: 800;
    }

    .metric-label {
        color: #94a3b8;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    section[data-testid="stSidebar"] {
        background: rgba(2,6,23,0.94);
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    .stButton > button,
    .stLinkButton > a {
        border-radius: 12px !important;
        border: 1px solid rgba(56,189,248,0.25) !important;
        background: rgba(15,23,42,0.78) !important;
        color: white !important;
        font-weight: 600 !important;
        transition: 0.2s !important;
        text-decoration: none !important;
    }

    .stButton > button:hover,
    .stLinkButton > a:hover {
        border-color: #38bdf8 !important;
        transform: translateY(-2px);
        box-shadow: 0 0 20px rgba(56,189,248,0.25);
    }

    input, textarea {
        background: rgba(2,6,23,0.75) !important;
        color: white !important;
    }

    .small-note {
        color: #94a3b8;
        font-size: 13px;
        line-height: 1.5;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# SESSION STATE
# ============================================================

if "history" not in st.session_state:
    st.session_state.history = []

if "response" not in st.session_state:
    st.session_state.response = "Hello Dhilleswar. JARVIS is online. How can I help you?"

if "last_command" not in st.session_state:
    st.session_state.last_command = ""

if "speak_response" not in st.session_state:
    st.session_state.speak_response = True

# ============================================================
# HELPERS
# ============================================================


def get_secret(name: str, default=None):
    """Read a Streamlit secret first, then an environment variable."""
    try:
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name, default)


def add_history(command: str, response: str):
    st.session_state.history.append(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "command": command,
            "response": response,
        }
    )
    st.session_state.history = st.session_state.history[-MAX_HISTORY:]


def safe_calculate(expression: str):
    """Safely evaluate basic arithmetic without eval()."""
    expression = expression.replace("×", "*").replace("÷", "/")
    if len(expression) > 100:
        raise ValueError("Expression is too long.")

    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult,
               ast.Div, ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Constant)
    tree = ast.parse(expression, mode="eval")

    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise ValueError("Only basic arithmetic is allowed.")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("Only numbers are allowed.")
        if isinstance(node, ast.Pow):
            # Prevent huge exponent calculations.
            if isinstance(node.right, ast.Constant) and abs(node.right.value) > 10:
                raise ValueError("Exponent is too large.")

    result = eval(compile(tree, "<calculator>", "eval"), {"__builtins__": {}}, {})
    return result


def system_information():
    cpu = f"{psutil.cpu_percent(interval=0.2):.0f}%" if psutil else "Unavailable"
    ram = "Unavailable"
    disk = "Unavailable"
    if psutil:
        ram = f"{psutil.virtual_memory().percent:.0f}%"
        disk = f"{psutil.disk_usage('/').percent:.0f}%"

    return (
        f"**System Information**\n\n"
        f"- OS: {platform.system()} {platform.release()}\n"
        f"- Machine: {platform.machine()}\n"
        f"- CPU usage: {cpu}\n"
        f"- RAM usage: {ram}\n"
        f"- Disk usage: {disk}"
    )


def battery_status():
    if not psutil:
        return "Battery information requires the `psutil` package."
    battery = psutil.sensors_battery()
    if battery is None:
        return "Battery information is not available on this system."
    charging = "charging" if battery.power_plugged else "not charging"
    remaining = "unknown"
    if battery.secsleft not in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN):
        minutes = max(0, battery.secsleft // 60)
        remaining = f"about {minutes // 60}h {minutes % 60}m remaining"
    return f"Battery is at **{battery.percent:.0f}%**, {charging} ({remaining})."


def get_ai_response(command: str):
    """Get an AI response from Google Gemini."""

    api_key = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")

    if not api_key:
        return (
            "Gemini API key is missing.\n\n"
            "Please add GEMINI_API_KEY to Streamlit Secrets."
        )

    if genai is None:
        return (
            "Google Gemini package is not installed.\n\n"
            "Please add google-genai to requirements.txt."
        )

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                "You are JARVIS, a professional AI assistant. "
                "Answer clearly, naturally and helpfully.\n\n"
                f"User command: {command}"
            ),
        )

        answer = getattr(response, "text", None)

        if answer:
            return answer.strip()

        return "Gemini returned an empty response."

    except Exception as exc:
        return (
            "⚠️ Google Gemini API Error\n\n"
            f"{type(exc).__name__}: {str(exc)}\n\n"
            "Please check your GEMINI_API_KEY in Streamlit Secrets."
        )


def execute_command(command: str):
    """Interpret common JARVIS commands and return response + optional URL."""
    original = command.strip()
    text = original.lower().strip()
    url = None

    if not text:
        return "Please give me a command, sir.", None

    # Greeting / conversational commands.
    if re.search(r"\b(hello|hi|hey)\b", text):
        return "Hello. JARVIS is online and ready for your command.", None

    if "who are you" in text or "what are you" in text:
        return "I am JARVIS — your AI voice and command assistant.", None

    if "time" in text:
        return f"The current time is **{datetime.now().strftime('%I:%M:%S %p')}**.", None

    if "date" in text or "today" in text:
        return f"Today is **{datetime.now().strftime('%A, %d %B %Y')}**.", None

    # Calculator.
    calc_match = re.search(r"(?:calculate|what is|solve)\s+(.+)$", text)
    if calc_match:
        expression = calc_match.group(1).strip().rstrip("?")
        try:
            result = safe_calculate(expression)
            return f"The result is **{result}**.", None
        except Exception:
            pass

    # Website commands. Links are returned because Streamlit Cloud cannot directly
    # open the end user's browser from Python.
    if "youtube" in text:
        url = "https://www.youtube.com"
        play_match = re.search(r"(?:play|search)\s+(.+?)(?:\s+on youtube)?$", text)
        if play_match and play_match.group(1).strip() not in {"youtube", "on youtube"}:
            query = play_match.group(1).strip()
            url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
            return f"Ready. I found a YouTube search for **{query}**.", url
        return "YouTube is ready. Use the button below to open it.", url

    if "google" in text or "search for" in text or text.startswith("search "):
        query = None
        if "search for" in text:
            query = re.sub(r".*search for\s+", "", text, count=1).strip()
        elif text.startswith("search "):
            query = text[7:].strip()
        if query:
            url = f"https://www.google.com/search?q={quote_plus(query)}"
            return f"Searching Google for **{query}**.", url
        url = "https://www.google.com"
        return "Google is ready. Use the button below to open it.", url

    if "system information" in text or text in {"system info", "computer information"}:
        return system_information(), None

    if "battery" in text:
        return battery_status(), None

    if "clear history" in text:
        st.session_state.history = []
        return "Command history cleared.", None

    if "help" in text or "what can you do" in text:
        return (
            "I can handle voice and text commands, calculate expressions, report time/date, "
            "show system and battery information, prepare Google/YouTube searches, and answer "
            "general questions when a GEMINI_API_KEY or GOOGLE_API_KEY is configured."
        ), None

    # AI fallback.
    ai_response = get_ai_response(original)
    if ai_response:
        return ai_response, None

    return (
        f"I received: **{original}**. For general AI questions, add a `GROQ_API_KEY` "
        "to Streamlit Secrets. I can still execute my built-in commands locally."
    ), None


def browser_speak(text: str):
    """Use the browser's built-in SpeechSynthesis API for text-to-speech."""
    clean = re.sub(r"[*_`#]", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return

    escaped = html.escape(clean).replace("\\", "\\\\").replace("'", "\\'")
    st.components.v1.html(
        f"""
        <script>
        const text = '{escaped}';
        if ('speechSynthesis' in window) {{
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 0.95;
            utterance.pitch = 0.9;
            utterance.volume = 1.0;
            window.speechSynthesis.speak(utterance);
        }}
        </script>
        """,
        height=0,
    )


def process_command(command: str):
    response, url = execute_command(command)
    st.session_state.last_command = command
    st.session_state.response = response
    add_history(command, response)
    return url

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## 🤖 JARVIS CONTROL")
    st.caption("Advanced AI Voice Assistant")

    st.session_state.speak_response = st.toggle(
        "🔊 Voice responses",
        value=st.session_state.speak_response,
    )

    st.markdown("### ⚡ Available Commands")
    st.markdown(
        """
        <div class="small-note">
        • open google<br>
        • open youtube<br>
        • play believer<br>
        • calculate 25*4<br>
        • what is the time<br>
        • system information<br>
        • battery status<br>
        • search for computer vision jobs<br>
        • help
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    if st.button("🗑️ Clear Command History", use_container_width=True):
        st.session_state.history = []
        st.session_state.response = "Command history cleared. JARVIS is ready."
        st.rerun()

    ai_ready = bool(get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")) and genai is not None
    st.markdown("### 🧠 AI Engine")
    if ai_ready:
        st.success("Google Gemini connected")
    else:
        st.info("Local command mode active")
        st.caption("Add GEMINI_API_KEY or GOOGLE_API_KEY to Streamlit Secrets for general AI chat.")

# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="glass">
        <div class="jarvis-title">🤖 J A R V I S</div>
        <div class="jarvis-subtitle">ADVANCED AI VOICE ASSISTANT</div>
        <div class="online">● SYSTEM ONLINE</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# DASHBOARD
# ============================================================

left, right = st.columns([1.5, 1])

# ============================================================
# LEFT: VOICE + TEXT
# ============================================================

with left:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("🎙️ Voice Command")

    audio = st.audio_input("Speak to JARVIS")

    if audio is not None:
        st.audio(audio)

        if sr is None:
            st.warning("Voice transcription needs `SpeechRecognition`. Add it to requirements.txt.")
        else:
            if st.button("🧠 Transcribe & Execute Voice Command", use_container_width=True):
                try:
                    recognizer = sr.Recognizer()
                    audio_bytes = audio.getvalue()
                    with open("_jarvis_voice.wav", "wb") as voice_file:
                        voice_file.write(audio_bytes)

                    with sr.AudioFile("_jarvis_voice.wav") as source:
                        recorded_audio = recognizer.record(source)

                    transcript = recognizer.recognize_google(recorded_audio)
                    st.session_state.last_command = transcript
                    url = process_command(transcript)
                    st.success(f"Heard: {transcript}")
                    if url:
                        st.link_button("🌐 Open Result", url, use_container_width=True)
                    if st.session_state.speak_response:
                        browser_speak(st.session_state.response)
                    st.rerun()
                except sr.UnknownValueError:
                    st.error("I could not understand the recording. Please speak clearly and try again.")
                except sr.RequestError:
                    st.error("Voice transcription service is unavailable. Check your internet connection.")
                except Exception as exc:
                    st.error(f"Voice processing failed: {exc}")

    st.subheader("⌨️ Text Command")
    command = st.text_input(
        "Command",
        placeholder="Try: open youtube, play believer, calculate 25*4...",
        label_visibility="collapsed",
    )

    if st.button("🚀 EXECUTE COMMAND", use_container_width=True):
        if command.strip():
            url = process_command(command)
            if url:
                st.session_state.pending_url = url
            else:
                st.session_state.pending_url = None
            st.rerun()
        else:
            st.warning("Please enter a command first.")

    # Display link from the latest command, if applicable.
    pending_url = st.session_state.get("pending_url")
    if pending_url:
        st.link_button("🌐 Open Command Result", pending_url, use_container_width=True)
        st.caption("Browser links are used because Streamlit Cloud cannot open your local browser directly from Python.")

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# RIGHT: RESPONSE + QUICK COMMANDS
# ============================================================

with right:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("🧠 JARVIS RESPONSE")

    response_text = st.session_state.response
    st.markdown(
        f'<div class="response">{html.escape(response_text).replace(chr(10), "<br>")}</div>',
        unsafe_allow_html=True,
    )

    st.write("")
    st.subheader("⚡ Quick Commands")

    if st.button("🌐 Open Google", use_container_width=True):
        st.session_state.pending_url = "https://www.google.com"
        st.session_state.response = "Google is ready."
        add_history("open google", st.session_state.response)
        st.rerun()

    if st.button("▶️ Open YouTube", use_container_width=True):
        st.session_state.pending_url = "https://www.youtube.com"
        st.session_state.response = "YouTube is ready."
        add_history("open youtube", st.session_state.response)
        st.rerun()

    if st.button("💻 System Information", use_container_width=True):
        st.session_state.pending_url = None
        st.session_state.response = system_information()
        add_history("system information", st.session_state.response)
        st.rerun()

    if st.button("🔋 Battery Status", use_container_width=True):
        st.session_state.pending_url = None
        st.session_state.response = battery_status()
        add_history("battery status", st.session_state.response)
        st.rerun()

    if st.button("🕒 Current Time", use_container_width=True):
        st.session_state.pending_url = None
        st.session_state.response = f"The current time is **{datetime.now().strftime('%I:%M:%S %p')}**."
        add_history("what is the time", st.session_state.response)
        st.rerun()

    if st.button("❓ Help", use_container_width=True):
        st.session_state.pending_url = None
        st.session_state.response = (
            "Try: open google, open youtube, play believer, calculate 25*4, "
            "system information, battery status, what is the time, or ask an AI question."
        )
        add_history("help", st.session_state.response)
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# COMMAND HISTORY
# ============================================================

st.markdown('<div class="glass">', unsafe_allow_html=True)
st.subheader("📜 COMMAND HISTORY")

if not st.session_state.history:
    st.info("No commands executed yet.")
else:
    for item in reversed(st.session_state.history[-10:]):
        command_html = html.escape(str(item["command"]))
        time_html = html.escape(str(item["time"]))
        st.markdown(
            f"""
            <div class="history">
                <div>🎤 <b>You:</b> {command_html}
                <span style="float:right;color:#64748b;font-size:12px">{time_html}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TTS FOR TEXT/QUICK COMMAND RESPONSES
# ============================================================

if st.session_state.speak_response and st.session_state.get("last_command"):
    # Only speak after a command has been processed, not on initial page load.
    last_spoken = st.session_state.get("last_spoken_response", "")
    if last_spoken != st.session_state.response:
        browser_speak(st.session_state.response)
        st.session_state.last_spoken_response = st.session_state.response

# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div style="text-align:center;color:#64748b;font-size:13px;margin-top:18px;">
        JARVIS AI ASSISTANT • ADVANCED EDITION • VOICE + AI + SYSTEM CONTROL
    </div>
    """,
    unsafe_allow_html=True,
)
