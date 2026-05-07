import asyncio
import re
import threading
import json
import sys
import traceback
from pathlib import Path
import numpy as np

import sounddevice as sd
from google import genai
from google.genai import types
from ui import AtlasUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)

from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-latest"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
IN_CHUNK            = 1024   # mic input: 64 ms → good for VAD
OUT_CHUNK           = 8192   # audio output: 340 ms buffer → prevents ALSA underruns


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are A.T.L.A.S, an advanced autonomous AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )


# ── Phoneme → ARKit viseme map ────────────────────────────────────────────────
_VISEME: dict[str, dict] = {
    # Vowels
    'a': {'JawOpen': 0.60, 'MouthLowerDownLeft': 0.35, 'MouthLowerDownRight': 0.35, 'MouthUpperUpLeft': 0.18, 'MouthUpperUpRight': 0.18},
    'e': {'JawOpen': 0.32, 'MouthStretchLeft': 0.42, 'MouthStretchRight': 0.42, 'MouthLowerDownLeft': 0.18, 'MouthLowerDownRight': 0.18},
    'i': {'JawOpen': 0.18, 'MouthStretchLeft': 0.52, 'MouthStretchRight': 0.52},
    'o': {'JawOpen': 0.42, 'MouthFunnel': 0.38, 'MouthPucker': 0.18, 'MouthLowerDownLeft': 0.22, 'MouthLowerDownRight': 0.22},
    'u': {'JawOpen': 0.18, 'MouthPucker': 0.58, 'MouthFunnel': 0.42},
    # Bilabials — full lip closure
    'm': {'JawOpen': 0.00, 'MouthClose': 0.92, 'MouthShrugUpper': 0.15},
    'b': {'JawOpen': 0.04, 'MouthClose': 0.65},
    'p': {'JawOpen': 0.02, 'MouthClose': 0.80},
    # Labiodental
    'f': {'JawOpen': 0.06, 'MouthUpperUpLeft': 0.58, 'MouthUpperUpRight': 0.58, 'MouthLowerDownLeft': 0.12, 'MouthLowerDownRight': 0.12},
    'v': {'JawOpen': 0.08, 'MouthUpperUpLeft': 0.48, 'MouthUpperUpRight': 0.48},
    # Sibilants
    's': {'JawOpen': 0.07, 'MouthStretchLeft': 0.28, 'MouthStretchRight': 0.28},
    'z': {'JawOpen': 0.10, 'MouthStretchLeft': 0.22, 'MouthStretchRight': 0.22},
    # Rounded
    'w': {'JawOpen': 0.14, 'MouthPucker': 0.50, 'MouthFunnel': 0.38},
    'r': {'JawOpen': 0.20, 'MouthFunnel': 0.18, 'MouthLowerDownLeft': 0.14, 'MouthLowerDownRight': 0.14},
    # Alveolar
    'l': {'JawOpen': 0.16, 'MouthLowerDownLeft': 0.10, 'MouthLowerDownRight': 0.10},
    't': {'JawOpen': 0.10, 'MouthStretchLeft': 0.12, 'MouthStretchRight': 0.12},
    'd': {'JawOpen': 0.13, 'MouthStretchLeft': 0.10, 'MouthStretchRight': 0.10},
    'n': {'JawOpen': 0.10},
    # Fricatives
    'h': {'JawOpen': 0.28},
    'j': {'JawOpen': 0.14, 'MouthStretchLeft': 0.18, 'MouthStretchRight': 0.18},
    'k': {'JawOpen': 0.20}, 'g': {'JawOpen': 0.22}, 'x': {'JawOpen': 0.15},
    'c': {'JawOpen': 0.10, 'MouthStretchLeft': 0.15, 'MouthStretchRight': 0.15},
    'q': {'JawOpen': 0.18}, 'y': {'JawOpen': 0.14, 'MouthStretchLeft': 0.20, 'MouthStretchRight': 0.20},
    # Default consonant
    '_': {'JawOpen': 0.12, 'MouthShrugUpper': 0.08},
}
_WORD_PAUSE = {'JawOpen': 0.04, 'MouthClose': 0.28}   # brief closure between words
_CHARS_PER_SEC = 13.0   # ~150 wpm × avg 5 chars/word ÷ 60s

# ── Transkripsiyon temizleyici ─────────────────────────────────────────────────
_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:
    """Gemini'nin ürettiği <ctrlXX> artefaktlarını ve kontrol karakterlerini temizler."""
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()


def _detect_emotion_realtime(chunk: str) -> str | None:
    """Per-chunk emotion detection during speech — returns None if no clear signal."""
    t = chunk.lower().strip()
    if not t:
        return None

    # Punctuation-based triggers
    if "?" in chunk:
        return "surprised"
    if "!" in chunk:
        return "happy" if any(w in t for w in ["great","nice","love","wow","super","harika","mükemmel","süper"]) else "surprised"

    # Keyword triggers (shorter list, high confidence only)
    if any(w in t for w in ["sorry","unfortunately","hata","olmadı","maalesef","could not","üzgün"]):
        return "concerned"
    if any(w in t for w in ["great","perfect","excellent","harika","süper","amazing","wonderful","love","bravo"]):
        return "happy"
    if any(w in t for w in ["hmm","let me","searching","thinking","analyzing","checking","bakıyorum","arıyorum"]):
        return "thinking"
    if any(w in t for w in ["wow","really","seriously","incredible","inanılmaz","no way","unbelievable"]):
        return "surprised"

    return None  # no strong signal → keep current emotion


def _detect_emotion(text: str) -> str:
    t = text.lower()
    if any(w in t for w in [
        "error", "fail", "sorry", "unfortunately", "hata", "üzgün", "maalesef",
        "could not", "couldn't", "unable", "problem", "issue", "olmadı", "yapamadım"
    ]):
        return "concerned"
    if any(w in t for w in [
        "great", "excellent", "perfect", "done", "harika", "mükemmel", "amazing",
        "wonderful", "fantastic", "congrat", "tebrik", "süper", "bravo", "love"
    ]):
        return "happy"
    if any(w in t for w in [
        "searching", "looking", "let me", "arıyorum", "bakıyorum", "thinking",
        "analyzing", "checking", "calculating", "processing", "considering", "hmm"
    ]):
        return "thinking"
    if any(w in t for w in [
        "wow", "really", "seriously", "incredible", "unbelievable", "inanılmaz",
        "gerçekten mi", "surprising", "unexpected", "no way"
    ]):
        return "surprised"
    if any(w in t for w in [
        "listening", "tell me", "go ahead", "dinliyorum", "anlat", "yes?", "sure"
    ]):
        return "listening"
    return "neutral"


# ── Tool declarations ──────────────────────────────────────────────────────────
TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | pause | resume | stop | close | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls any web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, screenshots, navigation, any web-based task. "
            "Always pass the 'browser' parameter when the user specifies a browser (e.g. 'open in Edge', "
            "'use Firefox', 'open Chrome'). Multiple browsers can run simultaneously."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | new_tab | close_tab | screenshot | back | forward | reload | switch | list_browsers | close | close_all"},
                "browser":     {"type": "STRING", "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Omit to use the currently active browser."},
                "url":         {"type": "STRING", "description": "URL for go_to / new_tab action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "engine":      {"type": "STRING", "description": "Search engine: google | bing | duckduckgo | yandex (default: google)"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up | down for scroll"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount in pixels (default: 500)"},
                "key":         {"type": "STRING", "description": "Key name for press action (e.g. Enter, Escape, F5)"},
                "path":        {"type": "STRING", "description": "Save path for screenshot"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "shutdown_atlas",
        "description": (
            "Shuts down A.T.L.A.S completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop Atlas. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
]


class AtlasLive:

    def __init__(self, ui: AtlasUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self.ui.on_tune_command = self._start_tune
        self._turn_done_event: asyncio.Event | None = None
        self._audio_buffer: list[bytes] = []
        self._jaw_last_send  = 0.0
        self._jaw_smooth     = 0.0
        self._last_emotion    = "neutral"
        self._emotion_sent_at = 0.0
        self._new_turn        = True
        self._emotion_event   = None
        self._viseme_q        = None   # queue.Queue fed per chunk
        self._viseme_running  = False  # True while viseme worker thread is alive
        self._noise_threshold = 0.0    # 0 = gate off
        self._calib_samples: list[float] = []
        self._calibrating = False

    def _on_text_command(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _start_tune(self):
        """2 saniye ortam gürültüsü kaydeder, noise gate eşiğini ayarlar."""
        import numpy as np, time
        self._calib_samples = []
        self._calibrating = True
        self.ui.broadcast_tune("started")
        self.ui.write_log("SYS: Kalibrasyonu başladı — 2 saniye sessiz kal...")

        try:
            for remaining in range(2, 0, -1):
                time.sleep(1)
                self.ui.broadcast_tune("progress", remaining - 1)
        finally:
            self._calibrating = False  # her koşulda sıfırla — mic'i sonsuza kadar susturmaz

        # IN_CHUNK=1024 → ~31 callbacks/2s; minimum 10 samples is enough
        if len(self._calib_samples) < 10:
            self.ui.broadcast_tune("error")
            self.ui.write_log("ERR: Kalibrasyon başarısız — mikrofon sesi alınamadı.")
            return

        samples = np.array(self._calib_samples)
        # Eşik = ortalama + 2 × standart sapma
        threshold = float(samples.mean() + 2 * samples.std())
        threshold = max(threshold, 0.005)   # minimum floor
        threshold = min(threshold, 0.02)    # upper cap — prevents silencing actual speech
        self._noise_threshold = threshold
        self._calib_samples = []

        db = 20 * np.log10(threshold + 1e-9)
        self.ui.broadcast_tune("done", threshold)
        self.ui.write_log(f"SYS: Noise gate ayarlandı — eşik {db:.1f} dB ({threshold:.4f})")
        print(f"[ATLAS] 🎚  Noise threshold: {threshold:.4f} ({db:.1f} dB)")

    def _drive_jaw_realtime(self, pcm_bytes: bytes):
        """Kept for compatibility — jaw is now driven from _play_audio."""
        pass

    def _drive_mouth_from_chunk(self, pcm_bytes: bytes):
        """Update amplitude envelope only — viseme thread uses this for scaling."""
        import numpy as np
        try:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if len(samples) < 16:
                return
            rms = float(np.sqrt(np.mean(samples ** 2)))
            raw = min(0.42, (rms ** 0.55) * 1.9)
            alpha = 0.50 if raw > self._jaw_smooth else 0.18
            self._jaw_smooth += alpha * (raw - self._jaw_smooth)
        except Exception:
            pass

    def _ensure_viseme_worker(self):
        """Start the viseme worker thread if not already running."""
        if self._viseme_running:
            return
        import queue
        self._viseme_q = queue.Queue()
        self._viseme_running = True
        threading.Thread(target=self._viseme_worker, daemon=True).start()

    def _viseme_worker(self):
        """Single persistent thread: drains chunk queue, plays visemes without gaps."""
        import time, queue as _q

        CHANNELS = ('JawOpen','MouthClose','MouthFunnel','MouthPucker',
                    'MouthStretchLeft','MouthStretchRight',
                    'MouthUpperUpLeft','MouthUpperUpRight',
                    'MouthLowerDownLeft','MouthLowerDownRight',
                    'MouthShrugUpper','MouthRollLower',
                    'MouthDimpleLeft','MouthDimpleRight')

        current = {k: 0.0 for k in CHANNELS}
        char_dur  = 1.0 / _CHARS_PER_SEC
        frame_dur = 0.04  # 25fps
        pending_chars = []  # remaining chars across chunks

        while self._viseme_running:
            # Refill from queue (non-blocking, keep going if chars left)
            try:
                text = self._viseme_q.get_nowait()
                if text is None:    # sentinel → stop
                    break
                for c in text.lower():
                    if c.isalpha():
                        pending_chars.append(('char', c))
                    elif c in (' ', ',', '.', '!', '?', ';', ':'):
                        pending_chars.append(('pause', c))
            except _q.Empty:
                if not pending_chars:
                    time.sleep(0.02)
                    continue

            if not pending_chars:
                continue

            kind, ch = pending_chars.pop(0)
            target = dict(_WORD_PAUSE if kind == 'pause' else _VISEME.get(ch, _VISEME['_']))

            amp = min(1.4, self._jaw_smooth * 2.2)
            scaled = {k: min(1.0, v * amp) for k, v in target.items()}
            if 'MouthClose' not in scaled:
                scaled['MouthClose'] = max(0.0, 0.08 - scaled.get('JawOpen', 0) * 0.2)

            alpha = 0.40
            for k in CHANNELS:
                current[k] += alpha * (scaled.get(k, 0.0) - current[k])

            self.ui.set_avatar_blendshapes({
                'jawOpen':             current['JawOpen'],
                'mouthClose':          current['MouthClose'],
                'mouthFunnel':         current['MouthFunnel'],
                'mouthPucker':         current['MouthPucker'],
                'mouthStretchLeft':    current['MouthStretchLeft'],
                'mouthStretchRight':   current['MouthStretchRight'],
                'mouthUpperUpLeft':    current['MouthUpperUpLeft'],
                'mouthUpperUpRight':   current['MouthUpperUpRight'],
                'mouthLowerDownLeft':  current['MouthLowerDownLeft'],
                'mouthLowerDownRight': current['MouthLowerDownRight'],
                'mouthShrugUpper':     current['MouthShrugUpper'],
                'mouthRollLower':      current['MouthRollLower'],
                'mouthDimpleLeft':     current['MouthDimpleLeft'],
                'mouthDimpleRight':    current['MouthDimpleRight'],
            })
            time.sleep(char_dur)   # advance one character per tick

        self._viseme_running = False

    def _dispatch_avatar(self, pcm_bytes: bytes, text: str):
        """Send audio turn to lipsync service and broadcast result to avatar UI."""
        try:
            from lipsync.client import get_blendshapes, amplitude_fallback, is_available
            emotion = _detect_emotion(text)
            self.ui.set_avatar_emotion("thinking")
            result = get_blendshapes(pcm_bytes) if is_available() else None
            if result is None:
                result = amplitude_fallback(pcm_bytes)
            self.ui.broadcast_avatar_data(
                audio_b64  = result["audio_b64"],
                blendshapes= result["blendshapes"],
                n_frames   = result["n_frames"],
                fps        = result["fps"],
                emotion    = emotion,
                text       = text,
            )
        except Exception as e:
            print(f"[Avatar] ⚠️  {e}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[ATLAS] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        # ── save_memory: sessiz ve hızlı ──────────────────────────────────────
        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={"parameters": args, "response": None,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = "Vision module activated. Stay completely silent — vision module will speak directly."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "shutdown_atlas":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir. A.T.L.A.S shutting down.")
                def _shutdown():
                    import time, os
                    time.sleep(1)
                    os._exit(0)
                threading.Thread(target=_shutdown, daemon=True).start()

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[ATLAS] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            data = await self.out_queue.get()
            await self.session.send_realtime_input(
                audio={"data": data, "mime_type": "audio/pcm;rate=16000"}
            )

    async def _listen_audio(self):
        print("[ATLAS] 🎤 Mic started")
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            import numpy as np
            samples = indata.astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(samples ** 2)))

            # Kalibrasyon modu: ses yerine gürültü örnekleri topla
            if self._calibrating:
                self._calib_samples.append(rms)
                return

            with self._speaking_lock:
                atlas_speaking = self._is_speaking
            if not atlas_speaking and not self.ui.muted:
                # Noise gate: eşiğin altındaysa gönderme
                if self._noise_threshold > 0 and rms < self._noise_threshold:
                    return
                data = indata.tobytes()
                # Schedule put on event loop; drop if still full (race-safe)
                def _safe_put(d=data):
                    if self.out_queue.full():
                        try: self.out_queue.get_nowait()
                        except Exception: pass
                    try: self.out_queue.put_nowait(d)
                    except Exception: pass
                loop.call_soon_threadsafe(_safe_put)

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=IN_CHUNK,
                callback=callback,
            ):
                print("[ATLAS] 🎤 Mic stream open")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[ATLAS] ❌ Mic: {e}")
            raise

    async def _receive_audio(self):
        print("[ATLAS] 👂 Recv started")
        out_buf, in_buf = [], []
        self._emotion_event = asyncio.Event()

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        self.audio_in_queue.put_nowait(response.data)
                        self._audio_buffer.append(response.data)
                        self._drive_jaw_realtime(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)
                                # First chunk → set emotion, release audio hold
                                if not self._emotion_event.is_set():
                                    emo = _detect_emotion(txt)
                                    self._last_emotion = emo
                                    self.ui.set_avatar_emotion(emo)
                                    self._emotion_event.set()
                                else:
                                    import time as _t
                                    emo = _detect_emotion_realtime(txt)
                                    now = _t.monotonic()
                                    if emo and emo != self._last_emotion and \
                                            now - self._emotion_sent_at > 2.5:
                                        self._last_emotion = emo
                                        self._emotion_sent_at = now
                                        self.ui.set_avatar_emotion(emo)

                                # Feed text to persistent viseme worker
                                self._ensure_viseme_worker()
                                self._viseme_q.put(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Atlas: {full_out}")
                            out_buf = []

                            # Stop viseme worker, close jaw
                            if self._viseme_q:
                                self._viseme_q.put(None)  # sentinel
                            self._viseme_running = False
                            self.ui.set_avatar_jaw(0.0)
                            self.ui.set_avatar_emotion(_detect_emotion(full_out))
                            # Reset for next turn
                            self._new_turn = True
                            self._emotion_event = asyncio.Event()
                            # Fade back to neutral after 2.5s
                            def _fade_neutral():
                                import time; time.sleep(2.5)
                                self.ui.set_avatar_emotion("neutral")
                            threading.Thread(target=_fade_neutral, daemon=True).start()

                            self._audio_buffer = []

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[ATLAS] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )

        except Exception as e:
            print(f"[ATLAS] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        """Play audio to sounddevice ONLY when no avatar browser is connected.
        When avatar is active, audio goes through browser (avatar_data message) for sync."""
        print("[ATLAS] 🔊 Play started")

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=OUT_CHUNK,
        )
        stream.start()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue

                self.set_speaking(True)
                # First chunk: wait for emotion to be set before audio starts
                if self._new_turn:
                    self._new_turn = False
                    if self._emotion_event:
                        try:
                            await asyncio.wait_for(
                                asyncio.shield(self._emotion_event.wait()),
                                timeout=0.65
                            )
                        except asyncio.TimeoutError:
                            pass
                await asyncio.to_thread(stream.write, chunk)
                self._drive_mouth_from_chunk(chunk)

        except Exception as e:
            print(f"[ATLAS] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        while True:
            try:
                print("[ATLAS] 🔌 Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=10)
                    self._turn_done_event = asyncio.Event()

                    print("[ATLAS] ✅ Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: A.T.L.A.S online.")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())

            except Exception as e:
                print(f"[ATLAS] ⚠️ {e}")
                traceback.print_exc()

            self.set_speaking(False)
            self.ui.set_state("THINKING")
            print("[ATLAS] 🔄 Reconnecting in 3s...")
            await asyncio.sleep(3)


def main():
    ui = AtlasUI("face.png")

    def runner():
        ui.wait_for_api_key()
        atlas = AtlasLive(ui)
        try:
            asyncio.run(atlas.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()