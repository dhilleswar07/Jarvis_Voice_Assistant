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

# Optional packages
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
    page_title="JARVIS AI Command Center",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONFIGURATION
# ============================================================

APP_NAME = "JARVIS"
MAX_HISTORY = 30
MAX_AI_MESSAGES = 12
BACKGROUND_IMAGE = Path("assets/jarvis_background.jpg")

DEFAULT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

QUICK_COMMANDS = {
    "🌐 Google": "open google",
    "▶️ YouTube": "open youtube",
    "🖥️ System": "system information",
    "🔋 Battery": "battery status",
    "🕒 Time": "what is the time",
    "📅 Date": "today's date",
    "❓ Help": "help",
}


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "history": [],
    "response": "Hello. JARVIS is online. How can I assist you?",
    "last_command": "",
    "pending_url": None,
    "speak_response": True,
    "ai_messages": [],
    "last_spoken_response": "",
    "command_count": 0,
    "voice_transcript": "",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


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


def get_model():
    return (
        get_secret("GEMINI_MODEL")
        or os.getenv("GEMINI_MODEL")
        or DEFAULT_MODELS[0]
    )


def clean_text(text: str) -> str:
    """Remove markdown/code symbols before browser speech."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"[*_`#>]", "", text)
    text = re.sub(r"\s+", " ", str(text))
    return text.strip()


def add_history(command: str, response: str):
    st.session_state.history.append(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "command": command,
            "response": response,
        }
    )
    st.session_state.history = st.session_state.history[-MAX_HISTORY:]
    st.session_state.command_count += 1


def safe_calculate(expression: str):
    """Safely evaluate basic arithmetic using AST."""
    expression = expression.replace("×", "*").replace("÷", "/")
    expression = expression.replace("^", "**").strip()

    if len(expression) > 100:
        raise ValueError("Expression is too long.")

    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Constant,
        ast.FloorDiv,
    )

    tree = ast.parse(expression, mode="eval")

    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise ValueError("Only basic arithmetic is allowed.")

        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError("Only numbers are allowed.")

        if isinstance(node, ast.Pow):
            if isinstance(node.right, ast.Constant):
                if abs(node.right.value) > 10:
                    raise ValueError("Exponent is too large.")

    result = eval(
        compile(tree, "<jarvis-calculator>", "eval"),
        {"__builtins__": {}},
        {},
    )

    if isinstance(result, (int, float)) and abs(result) > 1e100:
        raise ValueError("Result is too large.")

    return result


def system_information():
    cpu = "Unavailable"
    ram = "Unavailable"
    disk = "Unavailable"

    if psutil:
        cpu = f"{psutil.cpu_percent(interval=0.1):.0f}%"
        ram = f"{psutil.virtual_memory().percent:.0f}%"

        try:
            disk = f"{psutil.disk_usage('/').percent:.0f}%"
        except Exception:
            disk = "Unavailable"

    return (
        f"**Operating System:** {platform.system()} {platform.release()}\n\n"
        f"**Machine:** {platform.machine()}\n\n"
        f"**Processor:** {platform.processor() or 'Unavailable'}\n\n"
        f"**CPU Usage:** {cpu}\n\n"
        f"**RAM Usage:** {ram}\n\n"
        f"**Disk Usage:** {disk}"
    )


def battery_status():
    if not psutil:
        return "Battery information requires the `psutil` package."

    try:
        battery = psutil.sensors_battery()
    except Exception:
        battery = None

    if battery is None:
        return "Battery information is not available on this system."

    charging = "charging" if battery.power_plugged else "not charging"

    remaining = "unknown"
    if battery.secsleft not in (
        psutil.POWER_TIME_UNLIMITED,
        psutil.POWER_TIME_UNKNOWN,
    ):
        minutes = max(0, battery.secsleft // 60)
        remaining = f"about {minutes // 60}h {minutes % 60}m remaining"

    return (
        f"Battery is at **{battery.percent:.0f}%**, "
        f"{charging} ({remaining})."
    )


def open_url_response(name: str, url: str):
    return f"{name} is ready. Use the button below to open it.", url


# ============================================================
# GEMINI AI
# ============================================================

@st.cache_resource
def create_gemini_client(api_key: str):
    if genai is None or not api_key:
        return None
    return genai.Client(api_key=api_key)


def get_ai_response(command: str):
    """Generate a contextual response using Gemini."""
    api_key = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")

    if not api_key:
        return (
            "Gemini API key is missing.\n\n"
            "Add `GEMINI_API_KEY` to Streamlit Secrets."
        )

    if genai is None:
        return (
            "The Google Gemini package is not installed.\n\n"
            "Add `google-genai` to requirements.txt."
        )

    model = get_model()
    client = create_gemini_client(api_key)

    if client is None:
        return "JARVIS could not initialize the Gemini client."

    # Keep a small conversation memory for multi-turn AI responses.
    recent = st.session_state.ai_messages[-MAX_AI_MESSAGES:]

    conversation = []
    for item in recent:
        conversation.append(
            f"{item['role'].upper()}: {item['content']}"
        )

    conversation_text = "\n".join(conversation)

    prompt = f"""
You are JARVIS, a professional futuristic AI assistant.

Rules:
- Be concise but useful.
- Use natural professional language.
- If the user asks for code, provide production-quality code.
- If the user asks a technical question, explain clearly.
- Do not claim to perform actions that you cannot actually perform.
- Remember the recent conversation included below.

Recent conversation:
{conversation_text}

USER:
{command}
"""

    try:
        result = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        answer = getattr(result, "text", None)

        if not answer:
            return "Gemini returned an empty response."

        answer = answer.strip()

        st.session_state.ai_messages.append(
            {"role": "user", "content": command}
        )
        st.session_state.ai_messages.append(
            {"role": "assistant", "content": answer}
        )
        st.session_state.ai_messages = (
            st.session_state.ai_messages[-MAX_AI_MESSAGES:]
        )

        return answer

    except Exception as exc:
        return (
            "⚠️ Gemini is temporarily unavailable.\n\n"
            f"`{type(exc).__name__}: {exc}`\n\n"
            "Check your API key, selected model, quota, and network connection."
        )


# ============================================================
# COMMAND ROUTER
# ============================================================

def execute_command(command: str):
    original = command.strip()
    text = original.lower().strip()

    if not text:
        return "Please give me a command, sir.", None

    # Greetings
    if re.search(r"\b(hello|hi|hey)\b", text):
        return "Hello. JARVIS is online and ready for your command.", None

    if "who are you" in text or "what are you" in text:
        return (
            "I am JARVIS — your AI voice, automation and command assistant."
        ), None

    # Time
    if re.search(r"\b(what is|tell me|current)?\s*time\b", text):
        return (
            f"The current time is "
            f"**{datetime.now().strftime('%I:%M:%S %p')}**."
        ), None

    # Date
    if (
        "today" in text
        or "what is the date" in text
        or "today's date" in text
        or "current date" in text
    ):
        return (
            f"Today is **{datetime.now().strftime('%A, %d %B %Y')}**."
        ), None

    # Calculator
    calc_match = re.search(
        r"(?:calculate|solve|compute|what is)\s+(.+)$",
        text,
    )

    if calc_match:
        expression = calc_match.group(1).strip().rstrip("?")

        # Don't interpret ordinary questions as calculations.
        if re.fullmatch(r"[0-9+\-*/%.() ×÷^]+", expression):
            try:
                result = safe_calculate(expression)
                return f"The result is **{result}**.", None
            except Exception as exc:
                return f"Calculator error: **{exc}**", None

    # Google search
    if "search for" in text or text.startswith("search "):
        if "search for" in text:
            query = re.sub(
                r".*search for\s+",
                "",
                text,
                count=1,
            ).strip()
        else:
            query = text[7:].strip()

        if query:
            url = (
                "https://www.google.com/search?q="
                + quote_plus(query)
            )
            return f"Searching Google for **{query}**.", url

    if text in {"open google", "google"} or (
        "open google" in text
    ):
        return open_url_response(
            "Google",
            "https://www.google.com",
        )

    # YouTube
    if "youtube" in text:
        if text.startswith("play "):
            query = text[5:].replace(" on youtube", "").strip()
            if query:
                url = (
                    "https://www.youtube.com/results?search_query="
                    + quote_plus(query)
                )
                return (
                    f"Ready. I found a YouTube search for **{query}**.",
                    url,
                )

        if text.startswith("search "):
            query = text[7:].replace(" on youtube", "").strip()
            if query:
                url = (
                    "https://www.youtube.com/results?search_query="
                    + quote_plus(query)
                )
                return (
                    f"Searching YouTube for **{query}**.",
                    url,
                )

        return open_url_response(
            "YouTube",
            "https://www.youtube.com",
        )

    # Social platforms
    social_sites = {
        "instagram": "https://www.instagram.com/",
        "linkedin": "https://www.linkedin.com/",
        "github": "https://github.com/",
        "facebook": "https://www.facebook.com/",
        "x": "https://x.com/",
    }

    for name, url in social_sites.items():
        if (
            f"open {name}" in text
            or text == name
            or f"go to {name}" in text
        ):
            return open_url_response(name.title(), url)

    # System
    if any(
        phrase in text
        for phrase in [
            "system information",
            "system info",
            "computer information",
            "computer status",
        ]
    ):
        return system_information(), None

    # Battery
    if "battery" in text:
        return battery_status(), None

    # Clear history
    if "clear history" in text or "clear command history" in text:
        st.session_state.history = []
        st.session_state.ai_messages = []
        st.session_state.command_count = 0
        return "Command and AI history cleared.", None

    # Help
    if "help" in text or "what can you do" in text:
        return (
            "**JARVIS capabilities**\n\n"
            "- Voice commands\n"
            "- AI conversations with Gemini\n"
            "- Google and YouTube search\n"
            "- Calculator\n"
            "- Time and date\n"
            "- System information\n"
            "- Battery status\n"
            "- Command history\n"
            "- Browser text-to-speech\n"
            "- Quick command controls"
        ), None

    # AI fallback
    return get_ai_response(original), None


def process_command(command: str):
    response, url = execute_command(command)

    st.session_state.last_command = command
    st.session_state.response = response
    st.session_state.pending_url = url

    add_history(command, response)

    return url


# ============================================================
# BROWSER TEXT TO SPEECH
# ============================================================

def browser_speak(text: str):
    clean = clean_text(text)

    if not clean:
        return

    escaped = (
        clean.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", " ")
    )

    st.components.v1.html(
        f"""
        <script>
        const text = '{escaped}';

        if ("speechSynthesis" in window) {{
            window.speechSynthesis.cancel();

            const utterance =
                new SpeechSynthesisUtterance(text);

            utterance.rate = 0.92;
            utterance.pitch = 0.88;
            utterance.volume = 1.0;

            window.speechSynthesis.speak(utterance);
        }}
        </script>
        """,
        height=0,
    )


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>
/* ---------- Global ---------- */

.stApp {
    background:
        radial-gradient(circle at 15% 15%, rgba(14,165,233,.12), transparent 28%),
        radial-gradient(circle at 85% 20%, rgba(59,130,246,.10), transparent 30%),
        linear-gradient(135deg, #020617 0%, #07111f 50%, #020617 100%);
    color: #e5eefb;
}

.block-container {
    max-width: 1500px;
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}

[data-testid="stHeader"] {
    background: rgba(2,6,23,.72);
}

[data-testid="stSidebar"] {
    background: linear-gradient(
        180deg,
        rgba(2,6,23,.98),
        rgba(3,10,25,.96)
    );
    border-right: 1px solid rgba(56,189,248,.16);
}

/* ---------- Typography ---------- */

h1, h2, h3, h4 {
    color: #f8fafc !important;
}

.jarvis-title {
    font-size: clamp(38px, 5vw, 68px);
    font-weight: 900;
    letter-spacing: 10px;
    text-align: center;
    color: #f8fafc;
    text-shadow:
        0 0 8px rgba(56,189,248,.95),
        0 0 22px rgba(56,189,248,.65),
        0 0 55px rgba(14,165,233,.35);
    animation: pulseGlow 2.8s ease-in-out infinite;
}

.jarvis-subtitle {
    text-align: center;
    color: #94a3b8;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 4px;
    margin-top: 6px;
}

.online {
    text-align: center;
    color: #4ade80;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 2px;
    margin-top: 12px;
}

@keyframes pulseGlow {
    0%, 100% {
        filter: brightness(1);
        text-shadow:
            0 0 8px rgba(56,189,248,.75),
            0 0 25px rgba(56,189,248,.35);
    }
    50% {
        filter: brightness(1.25);
        text-shadow:
            0 0 12px rgba(56,189,248,1),
            0 0 38px rgba(56,189,248,.7);
    }
}

/* ---------- Cards ---------- */

.jarvis-card {
    background: linear-gradient(
        145deg,
        rgba(15,23,42,.88),
        rgba(2,6,23,.72)
    );
    border: 1px solid rgba(148,163,184,.16);
    border-radius: 24px;
    padding: 24px;
    box-shadow:
        0 20px 60px rgba(0,0,0,.35),
        inset 0 0 35px rgba(56,189,248,.025);
    margin-bottom: 18px;
}

.header-card {
    padding: 30px 24px;
    border-color: rgba(56,189,248,.22);
    box-shadow:
        0 20px 70px rgba(0,0,0,.40),
        0 0 45px rgba(14,165,233,.08);
}

/* ---------- Metrics ---------- */

.metric-box {
    background: rgba(2,6,23,.75);
    border: 1px solid rgba(56,189,248,.14);
    border-radius: 18px;
    padding: 17px 12px;
    text-align: center;
    transition: .2s ease;
}

.metric-box:hover {
    border-color: rgba(56,189,248,.55);
    transform: translateY(-2px);
    box-shadow: 0 0 25px rgba(56,189,248,.10);
}

.metric-value {
    font-size: 26px;
    font-weight: 900;
    color: #e0f2fe;
}

.metric-label {
    margin-top: 4px;
    color: #64748b;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.5px;
}

/* ---------- Response ---------- */

.response-box {
    background:
        linear-gradient(
            145deg,
            rgba(2,6,23,.94),
            rgba(7,18,35,.88)
        );
    border: 1px solid rgba(56,189,248,.30);
    border-radius: 20px;
    padding: 22px;
    min-height: 180px;
    color: #e5eefb;
    line-height: 1.7;
    box-shadow:
        inset 0 0 30px rgba(14,165,233,.035),
        0 12px 40px rgba(0,0,0,.22);
}

/* ---------- History ---------- */

.history-item {
    background: rgba(15,23,42,.68);
    border: 1px solid rgba(148,163,184,.10);
    border-left: 3px solid #38bdf8;
    border-radius: 14px;
    padding: 13px 15px;
    margin-bottom: 9px;
}

.history-command {
    color: #e2e8f0;
    font-weight: 700;
}

.history-time {
    float: right;
    color: #64748b;
    font-size: 11px;
}

/* ---------- Buttons ---------- */

.stButton > button,
.stLinkButton > a {
    min-height: 44px;
    border-radius: 12px !important;
    border: 1px solid rgba(56,189,248,.20) !important;
    background: rgba(15,23,42,.82) !important;
    color: #f8fafc !important;
    font-weight: 700 !important;
    transition: all .18s ease !important;
}

.stButton > button:hover,
.stLinkButton > a:hover {
    border-color: rgba(56,189,248,.75) !important;
    box-shadow: 0 0 22px rgba(56,189,248,.15);
    transform: translateY(-1px);
}

/* ---------- Inputs ---------- */

.stTextInput input,
.stTextArea textarea {
    background: rgba(2,6,23,.78) !important;
    color: #f8fafc !important;
    border: 1px solid rgba(148,163,184,.18) !important;
    border-radius: 12px !important;
}

.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: rgba(56,189,248,.75) !important;
    box-shadow: 0 0 18px rgba(56,189,248,.10) !important;
}

/* ---------- Sidebar ---------- */

.sidebar-brand {
    text-align: center;
    padding: 10px 0 20px;
}

.sidebar-brand-title {
    font-size: 25px;
    font-weight: 900;
    letter-spacing: 2px;
}

.sidebar-brand-subtitle {
    color: #64748b;
    font-size: 12px;
    margin-top: 4px;
}

.status-online {
    background: rgba(20,83,45,.42);
    border: 1px solid rgba(74,222,128,.25);
    color: #4ade80;
    border-radius: 12px;
    padding: 12px;
    text-align: center;
    font-weight: 800;
}

.status-offline {
    background: rgba(127,29,29,.25);
    border: 1px solid rgba(248,113,113,.25);
    color: #fca5a5;
    border-radius: 12px;
    padding: 12px;
    text-align: center;
    font-weight: 800;
}

.small-note {
    color: #94a3b8;
    font-size: 12px;
    line-height: 1.7;
}

.footer {
    text-align: center;
    color: #475569;
    font-size: 12px;
    letter-spacing: 1px;
    padding: 18px 0;
}

/* ---------- Mobile ---------- */

@media (max-width: 768px) {
    .block-container {
        padding-left: .8rem;
        padding-right: .8rem;
    }

    .jarvis-title {
        letter-spacing: 5px;
    }

    .jarvis-subtitle {
        letter-spacing: 2px;
        font-size: 11px;
    }

    .jarvis-card {
        padding: 16px;
        border-radius: 18px;
    }
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">🤖 JARVIS CONTROL</div>
            <div class="sidebar-brand-subtitle">
                ADVANCED AI COMMAND CENTER
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.session_state.speak_response = st.toggle(
        "🔊 Voice responses",
        value=st.session_state.speak_response,
    )

    st.divider()

    api_ready = bool(
        get_secret("GEMINI_API_KEY")
        or get_secret("GOOGLE_API_KEY")
    ) and genai is not None

    st.markdown("### 🧠 AI ENGINE")

    if api_ready:
        st.markdown(
            '<div class="status-online">● GEMINI CONNECTED</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="status-offline">● LOCAL COMMAND MODE</div>',
            unsafe_allow_html=True,
        )

    st.caption(f"Model: `{get_model()}`")

    if not api_ready:
        st.caption(
            "Add GEMINI_API_KEY to Streamlit Secrets "
            "for general AI conversations."
        )

    st.divider()

    st.markdown("### ⚡ AVAILABLE COMMANDS")
    st.markdown(
        """
        <div class="small-note">
        • hello / hi<br>
        • who are you<br>
        • what is the time<br>
        • today's date<br>
        • calculate 25*4<br>
        • system information<br>
        • battery status<br>
        • open google<br>
        • search for computer vision jobs<br>
        • open youtube<br>
        • play believer<br>
        • open github<br>
        • open linkedin<br>
        • open instagram<br>
        • clear history<br>
        • help
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    if st.button(
        "🗑️ Clear All History",
        use_container_width=True,
    ):
        st.session_state.history = []
        st.session_state.ai_messages = []
        st.session_state.command_count = 0
        st.session_state.response = "History cleared. JARVIS is ready."
        st.session_state.pending_url = None
        st.rerun()

    st.divider()

    st.markdown("### 📊 SESSION")
    st.metric(
        "Commands executed",
        st.session_state.command_count,
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="jarvis-card header-card">
        <div class="jarvis-title">🤖 J A R V I S</div>
        <div class="jarvis-subtitle">
            ADVANCED ARTIFICIAL INTELLIGENCE COMMAND SYSTEM
        </div>
        <div class="online">● SYSTEM ONLINE</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LIVE SYSTEM METRICS
# ============================================================

cpu_value = "N/A"
ram_value = "N/A"
disk_value = "N/A"
battery_value = "N/A"

if psutil:
    try:
        cpu_value = f"{psutil.cpu_percent(interval=0.1):.0f}%"
        ram_value = f"{psutil.virtual_memory().percent:.0f}%"
        disk_value = f"{psutil.disk_usage('/').percent:.0f}%"

        battery = psutil.sensors_battery()
        if battery:
            battery_value = f"{battery.percent:.0f}%"
    except Exception:
        pass

metric_columns = st.columns(4)

metrics = [
    ("CPU", cpu_value),
    ("RAM", ram_value),
    ("DISK", disk_value),
    ("BATTERY", battery_value),
]

for col, (label, value) in zip(metric_columns, metrics):
    with col:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-value">{html.escape(value)}</div>
                <div class="metric-label">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


st.write("")


# ============================================================
# MAIN DASHBOARD
# ============================================================

left, right = st.columns([1.45, 1])


# ============================================================
# LEFT PANEL — VOICE + TEXT
# ============================================================

with left:
    st.markdown(
        '<div class="jarvis-card">',
        unsafe_allow_html=True,
    )

    st.subheader("🎙️ Voice Command")

    if sr is None:
        st.warning(
            "SpeechRecognition is not installed. "
            "Add it to requirements.txt to enable transcription."
        )

    audio = st.audio_input("Speak to JARVIS")

    if audio is not None:
        st.audio(audio)

        if sr is not None:
            if st.button(
                "🧠 TRANSCRIBE & EXECUTE",
                use_container_width=True,
            ):
                try:
                    recognizer = sr.Recognizer()
                    audio_bytes = audio.getvalue()

                    voice_file_path = Path("_jarvis_voice.wav")

                    with open(voice_file_path, "wb") as voice_file:
                        voice_file.write(audio_bytes)

                    with sr.AudioFile(str(voice_file_path)) as source:
                        recorded_audio = recognizer.record(source)

                    transcript = recognizer.recognize_google(
                        recorded_audio
                    )

                    st.session_state.voice_transcript = transcript

                    process_command(transcript)

                    if st.session_state.speak_response:
                        browser_speak(
                            st.session_state.response
                        )

                    st.rerun()

                except sr.UnknownValueError:
                    st.error(
                        "I could not understand the recording. "
                        "Please speak clearly and try again."
                    )

                except sr.RequestError:
                    st.error(
                        "Voice transcription service is unavailable. "
                        "Check your internet connection."
                    )

                except Exception as exc:
                    st.error(
                        f"Voice processing failed: {type(exc).__name__}: {exc}"
                    )

    if st.session_state.voice_transcript:
        st.caption(
            f"Last transcript: "
            f"**{st.session_state.voice_transcript}**"
        )

    st.divider()

    st.subheader("⌨️ Text Command")

    command = st.text_input(
        "Command",
        placeholder=(
            "Try: open youtube, play believer, "
            "calculate 25*4..."
        ),
        label_visibility="collapsed",
    )

    if st.button(
        "🚀 EXECUTE COMMAND",
        use_container_width=True,
    ):
        if command.strip():
            process_command(command)

            if st.session_state.speak_response:
                browser_speak(
                    st.session_state.response
                )

            st.rerun()
        else:
            st.warning("Please enter a command first.")

    if st.session_state.pending_url:
        st.write("")
        st.link_button(
            "🌐 OPEN COMMAND RESULT",
            st.session_state.pending_url,
            use_container_width=True,
        )
        st.caption(
            "Streamlit Cloud uses a browser link because "
            "server-side Python cannot directly control your local browser."
        )

    st.markdown(
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# RIGHT PANEL — RESPONSE + QUICK COMMANDS
# ============================================================

with right:
    st.markdown(
        '<div class="jarvis-card">',
        unsafe_allow_html=True,
    )

    st.subheader("🧠 JARVIS RESPONSE")

    response_html = html.escape(
        str(st.session_state.response)
    ).replace("\n", "<br>")

    st.markdown(
        f"""
        <div class="response-box">
            {response_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    st.subheader("⚡ QUICK COMMANDS")

    quick_columns = st.columns(2)

    for index, (label, cmd) in enumerate(
        QUICK_COMMANDS.items()
    ):
        with quick_columns[index % 2]:
            if st.button(
                label,
                key=f"quick_{index}",
                use_container_width=True,
            ):
                process_command(cmd)

                if st.session_state.speak_response:
                    browser_speak(
                        st.session_state.response
                    )

                st.rerun()

    st.markdown(
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# AI CHAT PANEL
# ============================================================

st.markdown(
    '<div class="jarvis-card">',
    unsafe_allow_html=True,
)

st.subheader("💬 AI CONVERSATION MEMORY")

if st.session_state.ai_messages:
    for message in st.session_state.ai_messages[-8:]:
        role = (
            "👤 YOU"
            if message["role"] == "user"
            else "🤖 JARVIS"
        )

        st.markdown(
            f"**{role}:** {message['content']}"
        )
else:
    st.caption(
        "AI conversation memory will appear here after "
        "you ask a general question."
    )

st.markdown(
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# COMMAND HISTORY
# ============================================================

st.markdown(
    '<div class="jarvis-card">',
    unsafe_allow_html=True,
)

st.subheader("📜 COMMAND HISTORY")

if not st.session_state.history:
    st.info("No commands executed yet.")
else:
    for item in reversed(
        st.session_state.history[-10:]
    ):
        command_html = html.escape(
            str(item["command"])
        )
        time_html = html.escape(
            str(item["time"])
        )

        st.markdown(
            f"""
            <div class="history-item">
                <span class="history-command">
                    🎤 {command_html}
                </span>
                <span class="history-time">
                    {time_html}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown(
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# AUTO SPEECH FOR NEW RESPONSE
# ============================================================

if (
    st.session_state.speak_response
    and st.session_state.last_command
    and st.session_state.last_spoken_response
    != st.session_state.response
):
    browser_speak(st.session_state.response)
    st.session_state.last_spoken_response = (
        st.session_state.response
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        JARVIS AI ASSISTANT • ADVANCED EDITION •
        VOICE + GEMINI AI + SYSTEM MONITORING + COMMAND CENTER
    </div>
    """,
    unsafe_allow_html=True,
)
