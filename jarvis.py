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

# ============================================================
# OPTIONAL PACKAGES
# ============================================================

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
# CONFIGURATION
# ============================================================

APP_NAME = "JARVIS"
APP_VERSION = "4.0 ADVANCED"

BACKGROUND_IMAGE = Path("assets/jarvis_background.jpg")

MAX_HISTORY = 30
MAX_CHAT_HISTORY = 20


# ============================================================
# SECRET MANAGEMENT
# ============================================================

def get_secret(name: str, default=None):
    """
    Read Streamlit secrets first and environment variables second.
    """

    try:
        value = st.secrets.get(name)

        if value:
            return value

    except Exception:
        pass

    return os.getenv(name, default)


GEMINI_API_KEY = (
    get_secret("GEMINI_API_KEY")
    or get_secret("GOOGLE_API_KEY")
)

# Recommended default model.
# You can override this in Streamlit Secrets:
#
# GEMINI_MODEL = "gemini-2.5-flash"
#
GEMINI_MODEL = get_secret(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)


# ============================================================
# BACKGROUND
# ============================================================

def set_background(image_path: Path):

    if image_path.exists():

        try:

            with open(image_path, "rb") as image_file:

                encoded_image = base64.b64encode(
                    image_file.read()
                ).decode()

            st.markdown(
                f"""
                <style>

                .stApp {{
                    background:
                        linear-gradient(
                            rgba(2, 6, 23, 0.78),
                            rgba(2, 6, 23, 0.93)
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

            return

        except Exception:
            pass

    st.markdown(
        """
        <style>

        .stApp {
            background:
                radial-gradient(
                    circle at top left,
                    #0f172a,
                    #020617 45%,
                    #000000
                );
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


set_background(BACKGROUND_IMAGE)


# ============================================================
# ADVANCED CSS
# ============================================================

st.markdown(
    """
    <style>

    /* ======================================================
       GLOBAL
       ====================================================== */

    .block-container {
        padding-top: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
        padding-bottom: 2rem;
        max-width: 1600px;
    }


    /* ======================================================
       GLASS CARDS
       ====================================================== */

    .glass {

        background:
            linear-gradient(
                135deg,
                rgba(15, 23, 42, 0.88),
                rgba(2, 6, 23, 0.76)
            );

        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);

        border:
            1px solid rgba(148, 163, 184, 0.15);

        border-radius: 24px;

        padding: 25px;

        box-shadow:
            0 20px 60px rgba(0,0,0,0.45),
            inset 0 1px 0 rgba(255,255,255,0.03);

        margin-bottom: 18px;
    }


    /* ======================================================
       JARVIS TITLE
       ====================================================== */

    .jarvis-title {

        font-size: 56px;

        font-weight: 900;

        letter-spacing: 10px;

        text-align: center;

        color: #f8fafc;

        text-shadow:
            0 0 10px rgba(56,189,248,0.9),
            0 0 30px rgba(56,189,248,0.6),
            0 0 60px rgba(56,189,248,0.35);

        animation: glow 3s ease-in-out infinite alternate;
    }


    @keyframes glow {

        from {
            text-shadow:
                0 0 10px rgba(56,189,248,0.7),
                0 0 25px rgba(56,189,248,0.4);
        }

        to {
            text-shadow:
                0 0 20px rgba(56,189,248,1),
                0 0 50px rgba(56,189,248,0.7);
        }
    }


    .jarvis-subtitle {

        text-align: center;

        color: #94a3b8;

        font-size: 14px;

        letter-spacing: 4px;

        margin-top: -5px;

        margin-bottom: 8px;
    }


    /* ======================================================
       ONLINE STATUS
       ====================================================== */

    .online {

        text-align: center;

        color: #4ade80;

        font-weight: 800;

        letter-spacing: 2px;

        font-size: 14px;
    }


    /* ======================================================
       RESPONSE PANEL
       ====================================================== */

    .response {

        background:
            linear-gradient(
                145deg,
                rgba(2, 6, 23, 0.95),
                rgba(15, 23, 42, 0.78)
            );

        border:
            1px solid rgba(56,189,248,0.25);

        border-radius: 18px;

        padding: 22px;

        color: #f8fafc;

        font-size: 17px;

        line-height: 1.7;

        min-height: 130px;

        box-shadow:
            inset 0 0 30px rgba(14,165,233,0.04);
    }


    /* ======================================================
       METRIC CARDS
       ====================================================== */

    .metric-card {

        background:
            rgba(2, 6, 23, 0.72);

        border:
            1px solid rgba(148,163,184,0.15);

        border-radius: 18px;

        padding: 16px;

        text-align: center;

        transition: all 0.25s ease;
    }


    .metric-card:hover {

        transform: translateY(-3px);

        border-color:
            rgba(56,189,248,0.45);

        box-shadow:
            0 10px 30px rgba(0,0,0,0.35);
    }


    .metric-value {

        color: #e0f2fe;

        font-size: 25px;

        font-weight: 900;
    }


    .metric-label {

        color: #94a3b8;

        font-size: 11px;

        text-transform: uppercase;

        letter-spacing: 1.5px;

        margin-top: 3px;
    }


    /* ======================================================
       HISTORY
       ====================================================== */

    .history {

        background:
            rgba(15,23,42,0.70);

        border-radius: 14px;

        padding: 14px 16px;

        margin-bottom: 10px;

        border-left:
            3px solid #38bdf8;

        color: #e2e8f0;

        transition: 0.2s;
    }


    .history:hover {

        background:
            rgba(30,41,59,0.82);
    }


    /* ======================================================
       CHAT MESSAGE
       ====================================================== */

    .user-message {

        background:
            rgba(14,165,233,0.12);

        border:
            1px solid rgba(14,165,233,0.22);

        border-radius: 15px;

        padding: 13px;

        margin-bottom: 8px;

        color: #e0f2fe;
    }


    .ai-message {

        background:
            rgba(30,41,59,0.62);

        border:
            1px solid rgba(148,163,184,0.12);

        border-radius: 15px;

        padding: 13px;

        margin-bottom: 12px;

        color: #f8fafc;
    }


    /* ======================================================
       BUTTONS
       ====================================================== */

    .stButton > button,
    .stLinkButton > a {

        border-radius: 13px !important;

        border:
            1px solid rgba(56,189,248,0.22) !important;

        background:
            rgba(15,23,42,0.78) !important;

        color: white !important;

        font-weight: 700 !important;

        transition:
            all 0.2s ease !important;
    }


    .stButton > button:hover,
    .stLinkButton > a:hover {

        border-color:
            #38bdf8 !important;

        transform:
            translateY(-2px);

        box-shadow:
            0 0 25px rgba(56,189,248,0.22);
    }


    /* ======================================================
       INPUTS
       ====================================================== */

    input,
    textarea {

        background:
            rgba(2,6,23,0.78) !important;

        color:
            white !important;
    }


    /* ======================================================
       SIDEBAR
       ====================================================== */

    section[data-testid="stSidebar"] {

        background:
            rgba(2,6,23,0.97);

        border-right:
            1px solid rgba(255,255,255,0.07);
    }


    /* ======================================================
       SMALL TEXT
       ====================================================== */

    .small-note {

        color: #94a3b8;

        font-size: 12px;

        line-height: 1.7;
    }


    /* ======================================================
       STATUS BADGES
       ====================================================== */

    .badge {

        display: inline-block;

        padding: 5px 10px;

        border-radius: 20px;

        font-size: 11px;

        font-weight: 800;

        letter-spacing: 1px;

        background:
            rgba(34,197,94,0.12);

        border:
            1px solid rgba(34,197,94,0.25);

        color:
            #4ade80;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {

    "history": [],

    "chat_history": [],

    "response":
        "Hello Dhilleswar. JARVIS is online. How can I help you?",

    "last_command": "",

    "last_spoken_response": "",

    "speak_response": True,

    "pending_url": None,

    "ai_requests": 0,

    "start_time": time.time(),
}


for key, value in defaults.items():

    if key not in st.session_state:

        st.session_state[key] = value


# ============================================================
# SYSTEM FUNCTIONS
# ============================================================

def system_information():

    cpu = "Unavailable"
    ram = "Unavailable"
    disk = "Unavailable"

    if psutil:

        try:
            cpu = f"{psutil.cpu_percent(interval=0.1):.0f}%"
        except Exception:
            pass

        try:
            ram = f"{psutil.virtual_memory().percent:.0f}%"
        except Exception:
            pass

        try:
            disk = f"{psutil.disk_usage('/').percent:.0f}%"
        except Exception:
            pass

    return (
        f"### 💻 System Information\n\n"
        f"- **Operating System:** {platform.system()} "
        f"{platform.release()}\n"
        f"- **Machine:** {platform.machine()}\n"
        f"- **Processor:** {platform.processor() or 'Unknown'}\n"
        f"- **CPU Usage:** {cpu}\n"
        f"- **RAM Usage:** {ram}\n"
        f"- **Disk Usage:** {disk}"
    )


def battery_status():

    if not psutil:

        return (
            "Battery monitoring requires the `psutil` package."
        )

    try:

        battery = psutil.sensors_battery()

    except Exception:

        return "Unable to read battery information."

    if battery is None:

        return (
            "Battery information is not available "
            "on this system."
        )

    status = (
        "charging"
        if battery.power_plugged
        else "not charging"
    )

    return (
        f"🔋 Battery is at **{battery.percent:.0f}%**, "
        f"{status}."
    )


# ============================================================
# SAFE CALCULATOR
# ============================================================

def safe_calculate(expression: str):

    expression = (
        expression
        .replace("×", "*")
        .replace("÷", "/")
        .strip()
    )

    if len(expression) > 100:

        raise ValueError(
            "Expression is too long."
        )

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
    )

    tree = ast.parse(
        expression,
        mode="eval"
    )

    for node in ast.walk(tree):

        if not isinstance(node, allowed):

            raise ValueError(
                "Only basic arithmetic is allowed."
            )

        if (
            isinstance(node, ast.Constant)
            and not isinstance(
                node.value,
                (int, float)
            )
        ):

            raise ValueError(
                "Only numbers are allowed."
            )

        if isinstance(node, ast.Pow):

            if (
                isinstance(
                    node.right,
                    ast.Constant
                )
                and abs(node.right.value) > 10
            ):

                raise ValueError(
                    "Exponent is too large."
                )

    return eval(
        compile(
            tree,
            "<calculator>",
            "eval"
        ),
        {
            "__builtins__": {}
        },
        {},
    )


# ============================================================
# AI RESPONSE
# ============================================================

def get_ai_response(command: str):

    if not GEMINI_API_KEY:

        return (
            "⚠️ **Gemini API key is not configured.**\n\n"
            "Add `GEMINI_API_KEY` to Streamlit Secrets."
        )

    if genai is None:

        return (
            "⚠️ The `google-genai` package is not installed.\n\n"
            "Add `google-genai` to requirements.txt."
        )

    try:

        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        system_prompt = """
You are JARVIS, an advanced professional AI assistant.

Your personality:
- intelligent
- concise
- professional
- helpful
- futuristic
- natural

Rules:
1. Answer directly.
2. Use Markdown when useful.
3. Explain technical concepts clearly.
4. Do not claim to perform actions that you cannot actually perform.
5. If the user asks for code, provide clean production-quality code.
"""

        prompt = f"""
{system_prompt}

User command:
{command}
"""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        answer = getattr(
            response,
            "text",
            None
        )

        if answer:

            st.session_state.ai_requests += 1

            return answer.strip()

        return "JARVIS received an empty response."

    except Exception as exc:

        return (
            "⚠️ **Gemini request failed.**\n\n"
            f"`{type(exc).__name__}: {exc}`\n\n"
            "Check your API key, model name, quota, "
            "and internet connection."
        )


# ============================================================
# COMMAND HISTORY
# ============================================================

def add_history(
    command: str,
    response: str
):

    st.session_state.history.append(
        {
            "time":
                datetime.now().strftime(
                    "%H:%M:%S"
                ),

            "command":
                command,

            "response":
                response,
        }
    )

    st.session_state.history = (
        st.session_state.history[-MAX_HISTORY:]
    )


# ============================================================
# CHAT HISTORY
# ============================================================

def add_chat_message(
    role: str,
    content: str
):

    st.session_state.chat_history.append(
        {
            "role": role,
            "content": content,
        }
    )

    st.session_state.chat_history = (
        st.session_state.chat_history[
            -MAX_CHAT_HISTORY:
        ]
    )


# ============================================================
# COMMAND ROUTER
# ============================================================

def execute_command(command: str):

    original = command.strip()

    text = original.lower().strip()

    url = None

    if not text:

        return (
            "Please give me a command, sir.",
            None
        )


    # --------------------------------------------------------
    # GREETINGS
    # --------------------------------------------------------

    if re.search(
        r"\b(hello|hi|hey)\b",
        text
    ):

        return (
            "Hello. JARVIS is online and ready for your command.",
            None
        )


    # --------------------------------------------------------
    # IDENTITY
    # --------------------------------------------------------

    if (
        "who are you" in text
        or "what are you" in text
    ):

        return (
            "I am **JARVIS**, your advanced AI voice "
            "and command assistant.",
            None
        )


    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    if re.search(
        r"\b(time|current time)\b",
        text
    ):

        return (
            f"The current time is "
            f"**{datetime.now().strftime('%I:%M:%S %p')}**.",
            None
        )


    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    if (
        "date" in text
        or "today" in text
    ):

        return (
            f"Today is "
            f"**{datetime.now().strftime('%A, %d %B %Y')}**.",
            None
        )


    # --------------------------------------------------------
    # CALCULATOR
    # --------------------------------------------------------

    calc_match = re.search(
        r"(?:calculate|solve|what is)\s+(.+)$",
        text
    )

    if calc_match:

        expression = (
            calc_match
            .group(1)
            .strip()
            .rstrip("?")
        )

        try:

            result = safe_calculate(
                expression
            )

            return (
                f"🧮 The result is **{result}**.",
                None
            )

        except Exception:

            pass


    # --------------------------------------------------------
    # YOUTUBE
    # --------------------------------------------------------

    if "youtube" in text:

        url = "https://www.youtube.com"

        play_match = re.search(
            r"(?:play|search)\s+(.+?)"
            r"(?:\s+on youtube)?$",
            text
        )

        if play_match:

            query = (
                play_match
                .group(1)
                .strip()
            )

            if query not in {
                "youtube",
                "on youtube",
            }:

                url = (
                    "https://www.youtube.com/results"
                    "?search_query="
                    + quote_plus(query)
                )

                return (
                    f"▶️ YouTube search prepared "
                    f"for **{query}**.",
                    url
                )

        return (
            "YouTube is ready. "
            "Click the button below.",
            url
        )


    # --------------------------------------------------------
    # GOOGLE
    # --------------------------------------------------------

    if (
        "google" in text
        or "search for" in text
        or text.startswith("search ")
    ):

        query = None

        if "search for" in text:

            query = re.sub(
                r".*search for\s+",
                "",
                text,
                count=1
            ).strip()

        elif text.startswith("search "):

            query = text[7:].strip()

        if query:

            url = (
                "https://www.google.com/search?q="
                + quote_plus(query)
            )

            return (
                f"🔎 Searching Google for **{query}**.",
                url
            )

        url = "https://www.google.com"

        return (
            "Google is ready.",
            url
        )


    # --------------------------------------------------------
    # SOCIAL MEDIA
    # --------------------------------------------------------

    social_sites = {

        "instagram":
            (
                "https://www.instagram.com/",
                "Instagram"
            ),

        "linkedin":
            (
                "https://www.linkedin.com/",
                "LinkedIn"
            ),

        "github":
            (
                "https://github.com/",
                "GitHub"
            ),
    }


    for keyword, (
        site_url,
        site_name
    ) in social_sites.items():

        if keyword in text:

            return (
                f"{site_name} is ready. "
                "Click the button below.",
                site_url
            )


    # --------------------------------------------------------
    # SYSTEM INFORMATION
    # --------------------------------------------------------

    if (
        "system information" in text
        or text in {
            "system info",
            "computer information",
        }
    ):

        return (
            system_information(),
            None
        )


    # --------------------------------------------------------
    # BATTERY
    # --------------------------------------------------------

    if "battery" in text:

        return (
            battery_status(),
            None
        )


    # --------------------------------------------------------
    # CLEAR HISTORY
    # --------------------------------------------------------

    if (
        "clear history" in text
        or "clear commands" in text
    ):

        st.session_state.history = []

        return (
            "Command history cleared. "
            "JARVIS is ready.",
            None
        )


    # --------------------------------------------------------
    # HELP
    # --------------------------------------------------------

    if (
        "help" in text
        or "what can you do" in text
    ):

        return (
            """
### 🤖 JARVIS Capabilities

- 🎙️ Voice commands
- 💬 AI conversations
- 🧮 Mathematical calculations
- 🕒 Current time and date
- 💻 System information
- 🔋 Battery monitoring
- 🌐 Google search
- ▶️ YouTube search
- 💼 LinkedIn
- 🐙 GitHub
- 📸 Instagram
- 📜 Command history
- 🔊 Text-to-speech
            """,
            None
        )


    # --------------------------------------------------------
    # AI FALLBACK
    # --------------------------------------------------------

    return (
        get_ai_response(original),
        None
    )


# ============================================================
# PROCESS COMMAND
# ============================================================

def process_command(command: str):

    response, url = execute_command(
        command
    )

    st.session_state.last_command = command

    st.session_state.response = response

    st.session_state.pending_url = url

    add_history(
        command,
        response
    )

    return url


# ============================================================
# BROWSER TEXT TO SPEECH
# ============================================================

def browser_speak(text: str):

    clean = re.sub(
        r"[*_`#]",
        "",
        text
    )

    clean = re.sub(
        r"\s+",
        " ",
        clean
    ).strip()

    if not clean:

        return

    escaped = (
        html.escape(clean)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
    )

    st.components.v1.html(
        f"""
        <script>

        const text = '{escaped}';

        if ("speechSynthesis" in window) {{

            window.speechSynthesis.cancel();

            const utterance =
                new SpeechSynthesisUtterance(text);

            utterance.rate = 0.95;
            utterance.pitch = 0.85;
            utterance.volume = 1.0;

            window.speechSynthesis.speak(
                utterance
            );
        }}

        </script>
        """,
        height=0,
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🤖 JARVIS CONTROL"
    )

    st.caption(
        f"{APP_VERSION} • AI COMMAND CENTER"
    )

    st.divider()


    # Voice
    st.session_state.speak_response = st.toggle(
        "🔊 Voice Responses",
        value=st.session_state.speak_response,
    )


    st.markdown(
        "### 🧠 AI Engine"
    )

    if GEMINI_API_KEY and genai:

        st.success(
            "Gemini Connected"
        )

        st.caption(
            f"Model: `{GEMINI_MODEL}`"
        )

    elif not GEMINI_API_KEY:

        st.warning(
            "Gemini API key missing"
        )

    else:

        st.error(
            "google-genai not installed"
        )


    st.divider()


    st.markdown(
        "### ⚡ Available Commands"
    )

    st.markdown(
        """
        <div class="small-note">

        • hello<br>
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
        • help

        </div>
        """,
        unsafe_allow_html=True,
    )


    st.divider()


    # Session statistics
    st.markdown(
        "### 📊 Session Statistics"
    )

    st.metric(
        "Commands",
        len(st.session_state.history)
    )

    st.metric(
        "AI Requests",
        st.session_state.ai_requests
    )


    st.divider()


    if st.button(
        "🗑️ Clear History",
        use_container_width=True
    ):

        st.session_state.history = []

        st.session_state.chat_history = []

        st.session_state.response = (
            "Command history cleared. "
            "JARVIS is ready."
        )

        st.session_state.last_command = ""

        st.session_state.pending_url = None

        st.rerun()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="glass">

        <div class="jarvis-title">
            🤖 J A R V I S
        </div>

        <div class="jarvis-subtitle">
            ADVANCED ARTIFICIAL INTELLIGENCE COMMAND SYSTEM
        </div>

        <div class="online">
            ● SYSTEM ONLINE
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LIVE SYSTEM METRICS
# ============================================================

if psutil:

    try:

        cpu_value = (
            f"{psutil.cpu_percent(interval=0.1):.0f}%"
        )

        ram_value = (
            f"{psutil.virtual_memory().percent:.0f}%"
        )

        disk_value = (
            f"{psutil.disk_usage('/').percent:.0f}%"
        )

    except Exception:

        cpu_value = "N/A"
        ram_value = "N/A"
        disk_value = "N/A"

else:

    cpu_value = "N/A"
    ram_value = "N/A"
    disk_value = "N/A"


metric1, metric2, metric3, metric4 = st.columns(4)


with metric1:

    st.markdown(
        f"""
        <div class="metric-card">

            <div class="metric-value">
                {cpu_value}
            </div>

            <div class="metric-label">
                CPU
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with metric2:

    st.markdown(
        f"""
        <div class="metric-card">

            <div class="metric-value">
                {ram_value}
            </div>

            <div class="metric-label">
                RAM
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with metric3:

    st.markdown(
        f"""
        <div class="metric-card">

            <div class="metric-value">
                {disk_value}
            </div>

            <div class="metric-label">
                DISK
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with metric4:

    st.markdown(
        f"""
        <div class="metric-card">

            <div class="metric-value">
                {len(st.session_state.history)}
            </div>

            <div class="metric-label">
                COMMANDS
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


st.write("")


# ============================================================
# MAIN DASHBOARD
# ============================================================

left, right = st.columns(
    [1.45, 1]
)


# ============================================================
# LEFT PANEL
# ============================================================

with left:

    st.markdown(
        '<div class="glass">',
        unsafe_allow_html=True
    )

    st.subheader(
        "🎙️ Voice Command"
    )

    audio = st.audio_input(
        "Speak to JARVIS"
    )


    if audio is not None:

        st.audio(audio)

        if sr is None:

            st.warning(
                "Install SpeechRecognition "
                "to enable transcription."
            )

        else:

            if st.button(
                "🧠 Transcribe & Execute",
                use_container_width=True
            ):

                try:

                    recognizer = sr.Recognizer()

                    audio_bytes = (
                        audio.getvalue()
                    )

                    with open(
                        "_jarvis_voice.wav",
                        "wb"
                    ) as voice_file:

                        voice_file.write(
                            audio_bytes
                        )


                    with sr.AudioFile(
                        "_jarvis_voice.wav"
                    ) as source:

                        recorded_audio = (
                            recognizer.record(
                                source
                            )
                        )


                    transcript = (
                        recognizer
                        .recognize_google(
                            recorded_audio
                        )
                    )


                    process_command(
                        transcript
                    )

                    add_chat_message(
                        "user",
                        transcript
                    )

                    add_chat_message(
                        "assistant",
                        st.session_state.response
                    )


                    st.success(
                        f"Heard: {transcript}"
                    )


                    if (
                        st.session_state.speak_response
                    ):

                        browser_speak(
                            st.session_state.response
                        )


                    st.rerun()


                except sr.UnknownValueError:

                    st.error(
                        "I could not understand "
                        "the recording."
                    )


                except sr.RequestError:

                    st.error(
                        "Voice transcription "
                        "service is unavailable."
                    )


                except Exception as exc:

                    st.error(
                        f"Voice processing failed: {exc}"
                    )


    st.divider()


    # ========================================================
    # TEXT COMMAND
    # ========================================================

    st.subheader(
        "⌨️ Text Command"
    )

    command = st.text_input(
        "Command",
        placeholder=(
            "Try: open youtube, calculate 25*4, "
            "or ask JARVIS anything..."
        ),
        label_visibility="collapsed",
    )


    if st.button(
        "🚀 EXECUTE COMMAND",
        use_container_width=True
    ):

        if command.strip():

            process_command(
                command
            )

            add_chat_message(
                "user",
                command
            )

            add_chat_message(
                "assistant",
                st.session_state.response
            )

            st.rerun()

        else:

            st.warning(
                "Please enter a command first."
            )


    # ========================================================
    # URL RESULT
    # ========================================================

    if st.session_state.pending_url:

        st.link_button(
            "🌐 OPEN COMMAND RESULT",
            st.session_state.pending_url,
            use_container_width=True,
        )

        st.caption(
            "The link opens in your browser."
        )


    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )


    # ========================================================
    # CHAT
    # ========================================================

    st.markdown(
        '<div class="glass">',
        unsafe_allow_html=True
    )

    st.subheader(
        "💬 Conversation"
    )


    if not st.session_state.chat_history:

        st.info(
            "Start a conversation with JARVIS."
        )

    else:

        for message in (
            st.session_state.chat_history
        ):

            if message["role"] == "user":

                st.markdown(
                    f"""
                    <div class="user-message">
                        👤 <b>You:</b><br>
                        {html.escape(
                            message["content"]
                        )}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            else:

                content = message["content"]

                st.markdown(
                    f"""
                    <div class="ai-message">
                        🤖 <b>JARVIS:</b><br>
                        {html.escape(content)}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )


# ============================================================
# RIGHT PANEL
# ============================================================

with right:

    st.markdown(
        '<div class="glass">',
        unsafe_allow_html=True
    )

    st.subheader(
        "🧠 JARVIS RESPONSE"
    )

    response_text = (
        st.session_state.response
    )


    st.markdown(
        f"""
        <div class="response">

            {html.escape(
                response_text
            ).replace(chr(10), "<br>")}

        </div>
        """,
        unsafe_allow_html=True,
    )


    st.write("")


    # ========================================================
    # QUICK COMMANDS
    # ========================================================

    st.subheader(
        "⚡ Quick Commands"
    )


    if st.button(
        "🌐 Open Google",
        use_container_width=True
    ):

        st.session_state.pending_url = (
            "https://www.google.com"
        )

        st.session_state.response = (
            "Google is ready."
        )

        add_history(
            "open google",
            st.session_state.response
        )

        st.rerun()


    if st.button(
        "▶️ Open YouTube",
        use_container_width=True
    ):

        st.session_state.pending_url = (
            "https://www.youtube.com"
        )

        st.session_state.response = (
            "YouTube is ready."
        )

        add_history(
            "open youtube",
            st.session_state.response
        )

        st.rerun()


    if st.button(
        "💻 System Information",
        use_container_width=True
    ):

        st.session_state.pending_url = None

        st.session_state.response = (
            system_information()
        )

        add_history(
            "system information",
            st.session_state.response
        )

        st.rerun()


    if st.button(
        "🔋 Battery Status",
        use_container_width=True
    ):

        st.session_state.pending_url = None

        st.session_state.response = (
            battery_status()
        )

        add_history(
            "battery status",
            st.session_state.response
        )

        st.rerun()


    if st.button(
        "🕒 Current Time",
        use_container_width=True
    ):

        st.session_state.pending_url = None

        st.session_state.response = (
            f"The current time is "
            f"**{datetime.now().strftime('%I:%M:%S %p')}**."
        )

        add_history(
            "what is the time",
            st.session_state.response
        )

        st.rerun()


    if st.button(
        "❓ JARVIS Help",
        use_container_width=True
    ):

        st.session_state.pending_url = None

        st.session_state.response = (
            "Try: open google, open youtube, "
            "play believer, calculate 25*4, "
            "system information, battery status, "
            "or ask me any AI question."
        )

        add_history(
            "help",
            st.session_state.response
        )

        st.rerun()


    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )


# ============================================================
# COMMAND HISTORY
# ============================================================

st.markdown(
    '<div class="glass">',
    unsafe_allow_html=True
)

st.subheader(
    "📜 COMMAND HISTORY"
)


if not st.session_state.history:

    st.info(
        "No commands executed yet."
    )

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
            <div class="history">

                <div>

                    🎤 <b>You:</b>
                    {command_html}

                    <span
                        style="
                            float:right;
                            color:#64748b;
                            font-size:12px
                        "
                    >
                        {time_html}
                    </span>

                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


st.markdown(
    "</div>",
    unsafe_allow_html=True
)


# ============================================================
# TEXT-TO-SPEECH
# ============================================================

if (
    st.session_state.speak_response
    and st.session_state.last_command
):

    current_response = (
        st.session_state.response
    )

    last_spoken = (
        st.session_state.last_spoken_response
    )

    if (
        current_response
        != last_spoken
    ):

        browser_speak(
            current_response
        )

        st.session_state.last_spoken_response = (
            current_response
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div
        style="
            text-align:center;
            color:#64748b;
            font-size:12px;
            margin-top:20px;
            padding-bottom:10px;
        "
    >

        🤖 JARVIS AI ASSISTANT
        • ADVANCED EDITION
        • VOICE
        • GEMINI AI
        • SYSTEM CONTROL

    </div>
    """,
    unsafe_allow_html=True,
)
