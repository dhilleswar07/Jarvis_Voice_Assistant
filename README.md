# JARVIS — AI Voice Assistant

JARVIS is a Streamlit-based voice assistant and command center. It combines voice transcription, Gemini-powered conversational responses, useful local commands, browser links, speech playback, and a live system-status dashboard.

## Features

- **Voice and text input:** Record a command in the dashboard and transcribe it with Google Speech Recognition, or type a command directly.
- **Gemini conversations:** Send general questions to Google Gemini. Recent AI conversation messages are retained in the current Streamlit session for context.
- **Built-in commands:** Ask for the time or date, calculate basic arithmetic, view system information or battery status, search Google or YouTube, open supported websites, clear history, or ask for help.
- **Dashboard:** View CPU, memory, disk, and battery metrics when `psutil` can provide them.
- **Speech output:** Let the browser read JARVIS responses aloud; this uses the browser's Web Speech API.
- **Command history and quick actions:** Review recent commands and use the dashboard's quick-command buttons.

## Requirements

- Python 3.9 or newer
- A modern browser and microphone for voice input
- Internet access for Google speech recognition and Gemini requests
- A Gemini API key for AI conversations. Built-in commands work without a key.

Install the packages listed in `requirements.txt`:

```text
streamlit>=1.45.0
google-genai>=1.20.0
SpeechRecognition>=3.14.0
psutil>=6.0.0
```

## Run locally

1. Clone the repository and enter its folder:

   ```bash
   git clone https://github.com/dhilleswar07/Jarvis_Voice_Assistant.git
   cd Jarvis_Voice_Assistant
   ```

2. (Recommended) Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   ```

   Windows PowerShell:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

   macOS/Linux:

   ```bash
   source .venv/bin/activate
   ```

3. Install dependencies and launch the app:

   ```bash
   python -m pip install -r requirements.txt
   streamlit run jarvis.py
   ```

Streamlit prints a local URL (usually `http://localhost:8501`) to open in your browser.

## Configure Gemini

Set a key as an environment variable before launching the app. The app accepts `GEMINI_API_KEY` or `GOOGLE_API_KEY`:

PowerShell:

```powershell
$env:GEMINI_API_KEY = "your-api-key"
streamlit run jarvis.py
```

macOS/Linux:

```bash
export GEMINI_API_KEY="your-api-key"
streamlit run jarvis.py
```

Alternatively, create `.streamlit/secrets.toml` in the project folder:

```toml
GEMINI_API_KEY = "your-api-key"
# Optional: override the model name used by the app
GEMINI_MODEL = "gemini-3.6-flash"
```

Keep API keys private. Do not commit `secrets.toml` or publish your key. The app defaults to `gemini-3.6-flash`; set `GEMINI_MODEL` to a model available to your Google AI account if that default is unavailable.

## Example commands

| Say or enter | What JARVIS does |
| --- | --- |
| `hello` | Greets you |
| `what is the time` / `today's date` | Reports the current time or date |
| `calculate 25*4` | Evaluates basic arithmetic |
| `system information` | Shows OS, processor, CPU, memory, and disk details |
| `battery status` | Reports battery level and charging state when available |
| `open google` / `open github` | Provides a link to the website |
| `search for computer vision jobs` | Creates a Google search link |
| `play believer` | Creates a YouTube search link |
| `help` | Lists available capabilities |
| Any other question | Sends it to Gemini when configured |

Website commands show a link for you to open. The Python server does not directly control the browser, especially when hosted remotely.

## Voice input and output

Use **Speak to JARVIS** to record audio, then select **Transcribe & Execute**. Speech recognition uses `recognize_google`, which requires internet access. If transcription fails, check microphone permission, connectivity, and whether your browser can capture audio.

Voice responses use the browser's built-in speech synthesis. Enable **Voice responses** in the sidebar and allow audio in your browser. Available voices depend on the browser and operating system.

## System monitoring

`psutil` supplies CPU, RAM, disk, and battery readings. Some systems do not expose battery sensors or may report disk metrics differently; unavailable values are expected in those cases. On a hosted deployment, these metrics describe the host running Streamlit, not the visitor's device.

## Deploying

The app can be deployed to a Streamlit-compatible host. Add `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`) to the host's Streamlit secrets, install dependencies from `requirements.txt`, and use `jarvis.py` as the app entry point. Microphone permissions and audio support depend on the host and visitor's browser. Commands that create website links do not launch a browser on the server.

## Project files

- `jarvis.py` — Streamlit application, command handling, Gemini integration, and dashboard.
- `requirements.txt` — Python dependencies.
- `assets/` — Static assets included with the project (the app looks for `assets/jarvis_background.jpg`).

## Troubleshooting

- **Gemini is not connected:** Check that the API key is set in Streamlit secrets or the environment, that `google-genai` is installed, and that the selected model is available to your account.
- **Voice transcription is unavailable:** Confirm `SpeechRecognition` installed successfully, grant microphone access, and check internet connectivity.
- **System values show as unavailable:** Install `psutil`; battery and some disk readings are also hardware/OS dependent.
- **No spoken response:** Turn on **Voice responses** and check browser audio or speech-synthesis support.

## License

No license is specified in the repository. Unless a license file is added, all rights remain with the copyright holder and reuse is not granted by default.
