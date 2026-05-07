# A.T.L.A.S — Autonomous Task-Learning AI System

> A personal AI assistant with real-time voice interaction, 3D avatar, and full computer control.

---

## Project Overview

A.T.L.A.S (Autonomous Task-Learning AI System) is a desktop AI assistant built on Google Gemini 2.5 Flash Native Audio. It lets you control your computer, files, browsers, game platforms, and more through natural language commands. Audio captured from your microphone is processed in real time, the appropriate tools are selected and executed automatically, and the response is returned as synthesized speech. A browser-based 3D avatar interface provides a visual presence throughout every interaction.

**Key Highlights:**

- Near-zero-latency real-time voice input and output
- Full computer automation with 19 built-in tools
- 3D avatar with VRoid VRM models and phoneme-accurate lip sync
- Persistent long-term memory stored in JSON
- Autonomous multi-step agent engine for complex tasks
- Multi-language support — responses are delivered in the user's language

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        A.T.L.A.S                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Microphone (16 kHz)                                           │
│        │                                                         │
│        ▼                                                         │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │        Google Gemini 2.5 Flash Native Audio              │  │
│   │                  (Live API / Session)                    │  │
│   └────────────────────────┬─────────────────────────────────┘  │
│                            │                                      │
│               ┌────────────┴──────────────┐                      │
│               │                           │                      │
│          Tool Call                  Audio Response (24 kHz)      │
│               │                           │                      │
│               ▼                           ▼                      │
│   ┌────────────────────┐     ┌───────────────────────────────┐  │
│   │   Tool Router      │     │    sounddevice Playback       │  │
│   │   (main.py)        │     │           │                   │  │
│   └────────┬───────────┘     │  Amplitude Envelope           │  │
│            │                 │  (_jaw_smooth)                │  │
│   ┌────────▼───────────┐     │           │                   │  │
│   │    actions/        │     │  Text Transcription → Viseme  │  │
│   │  (19 tool modules) │     │  (14-channel ARKit)           │  │
│   └────────────────────┘     └──────────────┬────────────────┘  │
│                                             │                    │
│                                             ▼                    │
│                                   WebSocket (port 7862)          │
│                                             │                    │
│                                             ▼                    │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │        Browser UI (HTTP port 7861)                      │   │
│   │     avatar.html  →  Three.js + @pixiv/three-vrm         │   │
│   │     52 ARKit Blendshapes · Emotion · Auto-blink         │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│   ┌──────────────────────┐   ┌──────────────────────────────┐   │
│   │   memory/            │   │   agent/                     │   │
│   │   long_term.json     │   │   planner + executor         │   │
│   │   (persistent)       │   │   (multi-step automation)    │   │
│   └──────────────────────┘   └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Audio Pipeline

```
Microphone (16 kHz)
        │
        ▼
Gemini Live API  ──────────────────────────────────────────────┐
        │                                                        │
        │                                    Audio Response (24 kHz)
        ▼                                                        │
  Tool Router                                sounddevice playback
        │                                                        │
        ▼                                    Amplitude envelope (_jaw_smooth)
  actions/ modules                                               │
                                     Text transcription → Viseme worker thread
                                                                 │
                                     14-channel ARKit blendshape array
                                                                 │
                                     WebSocket message → Browser
                                                                 │
                                     Three.js VRM mesh → Real-time lip sync
```

---

## Capabilities

### 1. Open Application — `open_app`

Opens any application, program, or website on the computer.

| Parameter | Type | Description |
|-----------|------|-------------|
| `app_name` | string | Application name (e.g. `"Spotify"`, `"Chrome"`, `"WhatsApp"`) |

**Example commands:**
- "Open Spotify"
- "Launch Chrome"
- "Open the calculator"

---

### 2. Web Search — `web_search`

Searches the web; supports standard search and side-by-side comparison modes.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search query |
| `mode` | string | `search` (default) or `compare` |
| `items` | array | List of items to compare |
| `aspect` | string | `price`, `specs`, or `reviews` |

**Example commands:**
- "Search for the best Python frameworks"
- "Compare iPhone 15 and Galaxy S24 by price"

---

### 3. Weather Report — `weather_report`

Retrieves current weather conditions for any city.

| Parameter | Type | Description |
|-----------|------|-------------|
| `city` | string | City name |

**Example commands:**
- "What's the weather in London?"
- "Give me the weather report for Tokyo"

---

### 4. Send Message — `send_message`

Sends messages via WhatsApp, Telegram, and other messaging platforms.

| Parameter | Type | Description |
|-----------|------|-------------|
| `receiver` | string | Recipient contact name |
| `message_text` | string | Message content |
| `platform` | string | `WhatsApp`, `Telegram`, etc. |

**Example commands:**
- "Send John a WhatsApp message: 'Meeting at 3 PM'"
- "Text Sarah on Telegram that I'll be late"

---

### 5. Reminder — `reminder`

Sets timed reminders using the Windows Task Scheduler.

| Parameter | Type | Description |
|-----------|------|-------------|
| `date` | string | Date in `YYYY-MM-DD` format |
| `time` | string | Time in `HH:MM` (24-hour) format |
| `message` | string | Reminder message text |

**Example commands:**
- "Remind me to take my medication tomorrow at 2:30 PM"
- "Set a reminder for the team meeting on Friday at 10:00"

---

### 6. YouTube Control — `youtube_video`

Plays, pauses, summarizes, and retrieves trending YouTube videos via voice command.

| Action | Description |
|--------|-------------|
| `play` | Searches for and plays a video |
| `pause` | Pauses playback |
| `resume` | Resumes playback |
| `stop` / `close` | Stops and closes the player |
| `summarize` | Summarizes the current video's content |
| `get_info` | Retrieves video metadata from a URL |
| `trending` | Lists trending videos (accepts country code, e.g. `US`) |

**Example commands:**
- "Play Lo-Fi music on YouTube"
- "Summarize this video"
- "Show me trending videos in the US"

---

### 7. Screen and Camera Analysis — `screen_process`

Captures the screen or webcam image and analyzes it using the AI vision model.

| Parameter | Type | Description |
|-----------|------|-------------|
| `angle` | string | `screen` for display capture, `camera` for webcam |
| `text` | string | Question or instruction about the captured image |

**Example commands:**
- "What's on my screen?"
- "Look at the camera and tell me what you see"
- "Find the errors in this form"

> A.T.L.A.S has no inherent visual capability — this tool must be called for any vision task.

---

### 8. Computer Settings — `computer_settings`

Handles all single-command OS-level control actions.

| Category | Examples |
|----------|---------|
| Volume | Raise volume, mute, set volume to 50% |
| Brightness | Increase brightness, set to 70% |
| Window management | Minimize, maximize, snap window |
| Power | Shut down, restart, lock screen |
| Dark mode | Toggle dark mode on/off |
| Wi-Fi | Turn Wi-Fi on/off |
| Keyboard shortcuts | Ctrl+C, Alt+Tab, etc. |
| Screenshot | Take a screenshot |
| Tab management | Open new tab, close current tab |
| Zoom | Zoom in/out on the page |

---

### 9. Browser Control — `browser_control`

Full web browser automation — multiple browsers can run simultaneously.

**Supported browsers:** Chrome, Edge, Firefox, Opera, Opera GX, Brave, Vivaldi

| Action | Description |
|--------|-------------|
| `go_to` | Navigates to a URL |
| `search` | Performs a web search |
| `click` | Clicks an element by CSS selector or text |
| `type` | Types text into an element |
| `scroll` | Scrolls the page |
| `fill_form` | Fills a form |
| `smart_click` | Clicks an element described in natural language |
| `smart_type` | Types into an element described in natural language |
| `screenshot` | Takes a browser screenshot |
| `new_tab` / `close_tab` | Tab management |
| `switch` | Switches between open browsers |
| `list_browsers` | Lists all currently open browsers |

**Example commands:**
- "Open GitHub in Edge"
- "Search for Python tutorials in Chrome"
- "Click the 'Sign In' button"
- "Fill out the contact form with my name and email"

---

### 10. File Management — `file_controller`

Manages files and folders across the entire filesystem.

| Action | Description |
|--------|-------------|
| `list` | Lists directory contents |
| `create_file` | Creates a new file |
| `create_folder` | Creates a new folder |
| `delete` | Deletes a file or folder |
| `move` / `copy` | Moves or copies |
| `rename` | Renames a file or folder |
| `read` | Reads file contents |
| `write` | Writes content to a file |
| `find` | Searches by name or extension |
| `disk_usage` | Reports disk usage |
| `organize_desktop` | Organizes the desktop |
| `largest` | Finds the largest files |

**Shortcut paths:** `desktop`, `downloads`, `documents`, `home`

---

### 11. Desktop Control — `desktop_control`

Manages the desktop wallpaper, organization, and statistics.

| Action | Description |
|--------|-------------|
| `wallpaper` | Sets wallpaper from a file path |
| `wallpaper_url` | Sets wallpaper from a URL |
| `organize` | Organizes by type or date |
| `clean` | Cleans the desktop |
| `list` | Lists desktop items |
| `stats` | Shows desktop statistics |

---

### 12. Code Helper — `code_helper`

Writes, edits, explains, runs, and builds code in any programming language.

| Action | Description |
|--------|-------------|
| `write` | Creates a new code file |
| `edit` | Edits an existing file |
| `explain` | Explains what code does |
| `run` | Executes the code |
| `build` | Compiles or packages the project |
| `auto` | Automatically selects the best action |

**Example commands:**
- "Write a Python script that reads a CSV and prints the average"
- "Explain what this function does"
- "Run the script at C:/projects/app.py"

---

### 13. Developer Agent — `dev_agent`

Builds complete multi-file projects from scratch: plans the structure, writes all files, installs dependencies, opens VSCode, runs the project, and fixes errors.

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | string | What the project should do |
| `language` | string | Programming language (default: python) |
| `project_name` | string | Optional project folder name |
| `timeout` | integer | Run timeout in seconds (default: 30) |

**Example commands:**
- "Build a Flask REST API with user authentication"
- "Create a Tkinter calculator app"

---

### 14. Agent Task — `agent_task`

Executes complex multi-step tasks that require planning across multiple tools.

| Parameter | Type | Description |
|-----------|------|-------------|
| `goal` | string | Complete description of what to accomplish |
| `priority` | string | `low`, `normal`, or `high` (default: `normal`) |

The agent uses `planner.py` (Gemini-powered, max 5 steps) and `executor.py` to carry out each step sequentially.

**Example commands:**
- "Research the latest AI trends and save a summary to my desktop"
- "Find all PDF files in my downloads and move them to a new folder called Reports"

---

### 15. Computer Control — `computer_control`

Direct mouse and keyboard control via PyAutoGUI.

| Action | Description |
|--------|-------------|
| `type` / `smart_type` | Types text |
| `click` / `double_click` / `right_click` | Mouse click at coordinates |
| `hotkey` | Applies a key combination |
| `press` | Presses a single key |
| `scroll` | Scrolls in a direction |
| `move` | Moves the mouse cursor |
| `screenshot` | Captures a screenshot |
| `screen_find` | Finds an element on screen by description |
| `screen_click` | Clicks a found element |
| `focus_window` | Focuses a window by title |
| `copy` / `paste` | Clipboard operations |

---

### 16. Game Updater — `game_updater`

The exclusive handler for all Steam and Epic Games operations.

| Action | Description |
|--------|-------------|
| `update` | Updates installed games |
| `install` | Installs a game |
| `list` | Lists installed games |
| `download_status` | Checks download progress |
| `schedule` | Schedules an update at a specific time |
| `cancel_schedule` | Cancels a scheduled update |
| `schedule_status` | Shows scheduled update status |

| Parameter | Type | Description |
|-----------|------|-------------|
| `platform` | string | `steam`, `epic`, or `both` (default: `both`) |
| `game_name` | string | Game name (partial match supported) |
| `app_id` | string | Steam AppID for install |
| `hour` / `minute` | integer | Scheduled time (24h) |
| `shutdown_when_done` | boolean | Shut down PC when download completes |

**Example commands:**
- "Update all my Steam games"
- "Install CS2"
- "Schedule game updates for 3 AM tonight, then shut down when done"

---

### 17. Flight Finder — `flight_finder`

Searches Google Flights and presents the best flight options by voice.

| Parameter | Type | Description |
|-----------|------|-------------|
| `origin` | string | Departure city or airport code |
| `destination` | string | Arrival city or airport code |
| `date` | string | Departure date (any format) |
| `return_date` | string | Return date (for round trips) |
| `passengers` | integer | Number of passengers (default: 1) |
| `cabin` | string | `economy`, `premium`, `business`, or `first` |
| `save` | boolean | Save results to Notepad |

**Example commands:**
- "Find flights from New York to London on June 20"
- "Search for round-trip business class flights from Istanbul to Paris"

---

### 18. Save Memory — `save_memory`

Saves important user facts to persistent long-term memory so they carry over across sessions.

**Memory categories:**

| Category | Content |
|----------|---------|
| `identity` | Name, age, profession |
| `preferences` | Preferences and likes |
| `projects` | Ongoing projects |
| `relationships` | People and relationships |
| `wishes` | Goals and wishes |
| `notes` | General notes |

**Technical details:**

- Storage: `memory/long_term.json`
- Maximum value length: 380 characters
- Total memory limit: 2200 characters
- Thread-safe with a lock mechanism

---

### 19. Shutdown Assistant — `shutdown_jarvis`

Gracefully terminates the A.T.L.A.S session. Responds to shutdown intent in any language ("goodbye", "bye", "exit", "close", "kapat", "güle güle").

---

## Avatar System

### Overview

The A.T.L.A.S avatar system renders VRoid Studio VRM models in the browser using Three.js and the `@pixiv/three-vrm` library. During speech, the avatar performs real-time lip sync, emotion-driven facial expressions, and natural idle animations — all driven by the audio pipeline.

### Accessing the Avatar UI

```
http://localhost:7861/avatar.html
```

### VRM Models

| File | Description |
|------|-------------|
| `public/vroid_male.vrm` | Male VRoid model |
| `public/vroid_female.vrm` | Female VRoid model |

Models are served statically at `/public/` by the HTTP server on port 7861.

### Phoneme to ARKit Viseme Mapping

25 phoneme classes map to 14 ARKit facial channels, enabling frame-accurate lip sync:

| Phoneme group | Examples | Primary channels |
|---------------|----------|-----------------|
| Vowels | a, e, i, o, u | `JawOpen`, `MouthFunnel`, `MouthPucker` |
| Bilabials | m, b, p | `MouthClose`, `MouthShrugUpper` |
| Labiodentals | f, v | `MouthUpperUpLeft`, `MouthUpperUpRight` |
| Sibilants | s, z | `MouthStretchLeft`, `MouthStretchRight` |
| Rounded | w, r | `MouthPucker`, `MouthFunnel` |
| Alveolars | l, t, d, n | `MouthLowerDownLeft`, `MouthLowerDownRight` |
| Fricatives | h, j, k, g | `JawOpen` |

**Word pause shape:** A brief `MouthClose` closure is inserted between words to prevent the mouth from hanging open between syllables.

### Amplitude-Based Jaw Movement

While text transcription is in progress, the amplitude envelope follower (`_jaw_smooth`) derives jaw movement directly from the audio output waveform. This ensures the mouth moves naturally from the first audio frame — before the viseme worker thread produces frame-accurate data.

**Processing constant:** `_CHARS_PER_SEC = 13.0` (~150 words per minute, 5 chars/word average) governs timing of the viseme playback schedule.

### Emotion Detection System

Emotion is detected in two passes — real-time during streaming chunks, and as a full-text analysis after the response completes. Six emotion states drive the upper-face expression layer:

| Emotion | Trigger keywords |
|---------|-----------------|
| `happy` | great, perfect, excellent, amazing, wonderful, bravo |
| `thinking` | searching, let me, analyzing, checking, hmm |
| `concerned` | error, fail, sorry, unfortunately, could not |
| `surprised` | wow, really, seriously, incredible, no way |
| `listening` | tell me, go ahead, yes?, sure |
| `neutral` | (default state) |

**Separation rule:** During speech, only upper-face blendshapes (brows, eyelids) transition with emotion. The lower face runs the lip sync pipeline independently.

### Idle Animations

When not speaking, the avatar runs three continuous idle animations:

- **Auto-blink** — randomized eyelid blink cycle
- **Breathing** — subtle chest and shoulder rise/fall
- **Head sway** — gentle head micro-movement

### Expression Tester Panel

`avatar.html` includes an expression tester panel with 70 configurable expressions for development and demonstration purposes.

---

## Installation

### Requirements

| Requirement | Version / Detail |
|-------------|-----------------|
| Python | 3.12+ |
| Operating System | Windows 10/11 (recommended) |
| Browser | Chrome / Chromium (recommended) |
| Gemini API Key | Free tier — [aistudio.google.com](https://aistudio.google.com) |
| Microphone | Any microphone |

### Step-by-Step Setup

**Step 1 — Clone the repository:**

```bash
git clone https://github.com/your-username/atlas.git
cd atlas
```

**Step 2 — Install dependencies:**

```bash
python setup.py
```

This installs all Python packages and downloads Playwright browser binaries.

To install manually:

```bash
pip install -r requirements.txt
playwright install
```

**Step 3 — Configure the API key:**

Create `config/api_keys.json`:

```json
{
    "gemini_api_key": "YOUR_API_KEY_HERE"
}
```

Get a free API key at: [https://aistudio.google.com](https://aistudio.google.com)

**Step 4 — Start the assistant:**

```bash
python main.py
```

The browser opens automatically at `http://localhost:7861`.

### Python Dependencies

| Package | Purpose |
|---------|---------|
| `sounddevice` | Real-time microphone input and audio playback |
| `google-genai` | Gemini Live API client |
| `google-generativeai` | Gemini SDK |
| `playwright` | Browser automation |
| `pyautogui` | Mouse and keyboard control |
| `numpy` | Audio buffer processing |
| `mss` | Screen capture |
| `Pillow` | Image processing |
| `psutil` | Process and system information |
| `pyperclip` | Clipboard management |
| `pygetwindow` | Window management |
| `opencv-python` | Image analysis |
| `comtypes` | Windows COM interface |
| `pycaw` | Windows audio control |
| `win10toast` | Windows toast notifications |
| `send2trash` | Recycle bin deletion |
| `youtube-transcript-api` | YouTube transcript retrieval |
| `pywinauto` | Windows UI automation |
| `pyaudio` | Audio streaming |
| `websockets` | WebSocket server |

---

## Usage

### Starting the Assistant

```bash
python main.py
```

When the session initializes, the console prints:

```
=======================================================
  A.T.L.A.S  →  http://localhost:7861
=======================================================
```

The browser opens automatically. When the interface is ready, speak into your microphone.

### Interface Options

| URL | Interface | Description |
|-----|-----------|-------------|
| `http://localhost:7861` | Text UI (atlas.html) | Classic text-based chat interface |
| `http://localhost:7861/avatar.html` | 3D Avatar UI | Visual interface with the VRM avatar |

### WebSocket Message Protocol

The browser connects to `ws://localhost:7862`.

**State update:**
```json
{ "type": "state", "value": "LISTENING" }
```

**Log entry:**
```json
{ "type": "log", "text": "Tool call: web_search" }
```

**Lip sync data (sent per audio chunk):**
```json
{
    "type": "lipsync",
    "blendshapes": {
        "JawOpen": 0.6,
        "MouthStretchLeft": 0.3,
        "MouthStretchRight": 0.3
    }
}
```

### Audio Configuration (main.py)

| Constant | Value | Description |
|----------|-------|-------------|
| `SEND_SAMPLE_RATE` | 16000 Hz | Microphone sample rate |
| `RECEIVE_SAMPLE_RATE` | 24000 Hz | Audio output sample rate |
| `IN_CHUNK` | 1024 samples | Microphone buffer (~64 ms, good for VAD) |
| `OUT_CHUNK` | 8192 samples | Audio output buffer (~340 ms, prevents underruns) |

### Example Voice Commands

```
"Open Spotify"
"What's the weather in Paris?"
"Send John a WhatsApp message: 'Running 10 minutes late'"
"Remind me about the team standup tomorrow at 9 AM"
"Play relaxing music on YouTube"
"What's on my screen?"
"Open github.com in Edge"
"Organize my desktop"
"Update all my Steam games"
"Find flights from Istanbul to Amsterdam on July 10"
"Write a Python script that renames all files in a folder"
"Set the volume to 50%"
"Take a screenshot"
"Shut down the computer"
```

### System Prompt Behavior

The system identity is loaded from `core/prompt.txt` at startup. Key behavioral rules:

- **Action flow:** For slow tools (search, vision, agent), A.T.L.A.S speaks two short sentences, then calls the tool and stays silent.
- **One-call policy:** Tools are called exactly once — no retries or guessing.
- **Language:** The response language matches the user's input language; tool parameters are extracted in English.
- **Memory:** Critical user preferences are stored automatically during conversation.

---

## File Structure

```
Atlas/
├── main.py                    # Entry point: Gemini Live session,
│                              #   audio pipeline, tool router, lip sync
├── ui.py                      # Browser UI: HTTP server (7861) + WebSocket (7862)
├── setup.py                   # Setup script: pip + Playwright install
├── requirements.txt           # Python dependencies
│
├── core/
│   └── prompt.txt             # System identity and execution rules
│
├── actions/                   # Tool implementations (each a standalone module)
│   ├── browser_control.py     # Playwright browser automation
│   ├── code_helper.py         # Code writing, running, and explanation
│   ├── computer_control.py    # PyAutoGUI mouse/keyboard control
│   ├── computer_settings.py   # Windows OS settings control
│   ├── desktop.py             # Desktop wallpaper and organization
│   ├── dev_agent.py           # Full project builder from scratch
│   ├── file_controller.py     # File and folder management
│   ├── flight_finder.py       # Google Flights search
│   ├── game_updater.py        # Steam/Epic Games management
│   ├── open_app.py            # Application launcher
│   ├── reminder.py            # Windows Task Scheduler integration
│   ├── screen_processor.py    # Screen/webcam capture and AI analysis
│   ├── send_message.py        # WhatsApp/Telegram messaging
│   ├── weather_report.py      # Weather data retrieval
│   ├── web_search.py          # DuckDuckGo web search
│   └── youtube_video.py       # YouTube playback and analysis
│
├── agent/                     # Multi-step autonomous agent engine
│   ├── planner.py             # Gemini-powered task planner (max 5 steps)
│   ├── executor.py            # Step executor
│   ├── task_queue.py          # Task queue management
│   └── error_handler.py       # Error recovery
│
├── memory/                    # Long-term memory system
│   ├── memory_manager.py      # Load / update / format memory
│   └── long_term.json         # Persistent user data store
│
├── lipsync/
│   └── client.py              # audio2lipsync client (port 8765)
│
├── web/                       # Browser front-end
│   ├── atlas.html             # Classic text interface
│   ├── avatar.html            # 3D avatar interface
│   └── avatar_renderer.js     # Three.js + VRM renderer
│
├── public/                    # Avatar models (served at /public/)
│   ├── vroid_male.vrm         # Male VRoid model
│   └── vroid_female.vrm       # Female VRoid model
│
├── models/                    # Animation clips
│
└── config/
    └── api_keys.json          # Gemini API key configuration
```

---

## Troubleshooting

### Microphone not detected

- Confirm `sounddevice` is installed and your microphone is set as the default input device at the OS level.
- Verify that `CHANNELS = 1` and `SEND_SAMPLE_RATE = 16000` in `main.py` are compatible with your microphone hardware.

### Browser does not open automatically

- Navigate manually to `http://localhost:7861`.
- Check that no firewall or antivirus software is blocking ports 7861 or 7862.

### API key error

- Confirm `config/api_keys.json` exists and contains the correct JSON structure.
- Verify your API key is active at [aistudio.google.com](https://aistudio.google.com).

### Playwright installation error

```bash
playwright install chromium
```

### Avatar not rendering

- Use Chrome or Chromium — WebGL support is required for Three.js VRM rendering.
- Open the browser console and check for errors on `http://localhost:7861/avatar.html`.

---

## License

This project is intended for educational and research use.
