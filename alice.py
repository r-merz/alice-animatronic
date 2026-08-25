import json
import os
import re
import shutil
import subprocess
import tempfile
import websocket

import ollama
import requests
import speech_recognition as sr

import threading
from pathlib import Path
import time
import queue
import cv2

import spotipy
import wave

from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from alice_skill_runtime import(
    AliceSkillRuntime
)

from dotenv import load_dotenv
from fishaudio import FishAudio
from fishaudio.core import RequestOptions
from alice_research import(
    AliceResearchManager, 
    ResearchSource, 
)

import io 
import mss 
from PIL import Image
from collections import deque 
from typing import Callable
import random
import sys
from alice_web_server import AliceWebServer
import AppKit
import Quartz 
import ast
import difflib 
import requests

from urllib.parse import quote_plus

from alice_support_loop import AliceSupportLoop
support_loop = AliceSupportLoop()

from alice_therapeutic_memory import(
    AliceTherapeuticMemoryManager, 
)
therapeutic_memory = (
    AliceTherapeuticMemoryManager()
)
def position_research_chrome_window() -> bool:
    if sys.platform != "darwin":
        return False

    script = """
tell application "System Events"
    tell process "Google Chrome"
        set researchWindows to every window

        repeat with currentWindow in researchWindows
            try
                set windowName to name of currentWindow

                if windowName does not contain "Alice" then
                    set position of currentWindow to {40, 120}
                    set size of currentWindow to {520, 650}
                    return true
                end if
            end try
        end repeat
    end tell
end tell

return false
"""

    result = subprocess.run(
        [
            "/usr/bin/osascript",
            "-e",
            script,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        print(
            "Could not position research window:",
            result.stderr.strip(),
        )
        return False

    return (
        result.stdout.strip().lower()
        == "true"
    )
def open_research_search(
    query: str,
) -> bool:
    query = str(
        query or ""
    ).strip()

    if not query:
        return False

    RESEARCH_CHROME_PROFILE.mkdir(
        parents=True,
        exist_ok=True,
    )

    search_url = (
        "https://www.google.com/search?q="
        + quote_plus(
            query
        )
    )

    result = subprocess.run(
        [
            "/usr/bin/open",
            "-na",
            "Google Chrome",
            "--args",
            (
                "--user-data-dir="
                f"{RESEARCH_CHROME_PROFILE}"
            ),
            "--remote-debugging-port=9223",
            "--remote-allow-origins=*",
            f"--app={search_url}",
            "--window-size=520,650",
            "--window-position=40,120",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        print(
            "Could not open research browser:",
            result.stderr.strip()
            or result.stdout.strip(),
        )

        return False
    time.sleep(1.0)
    position_research_chrome_window()
    print(
        "Opened research search:",
        query
    )

    return True

def get_research_browser_page() -> dict | None:
    try:
        response = requests.get(
            "http://127.0.0.1:9223/json",
            timeout=2,
        )

        response.raise_for_status()

        targets = response.json()

        if not isinstance(
            targets,
            list,
        ):
            return None

        for target in targets:
            if not isinstance(
                target,
                dict,
            ):
                continue

            if target.get(
                "type"
            ) != "page":
                continue

            websocket_url = str(
                target.get(
                    "webSocketDebuggerUrl",
                    "",
                )
            ).strip()

            if not websocket_url:
                continue

            return target

        return None

    except (
        requests.RequestException,
        ValueError,
    ):
        return None

def navigate_research_browser(
    url: str,
) -> bool:
    url = str(
        url or ""
    ).strip()

    if not url:
        return False

    target = (
        get_research_browser_page()
    )

    if not target:
        print(
            "No active research browser "
            "target was found."
        )
        return False

    websocket_url = str(
        target.get(
            "webSocketDebuggerUrl",
            "",
        )
    ).strip()

    if not websocket_url:
        return False

    try:
        connection = (
            websocket.create_connection(
                websocket_url,
                timeout=5,
            )
        )

        try:
            command = {
                "id": 1,
                "method": "Page.navigate",
                "params": {
                    "url": url,
                },
            }

            connection.send(
                json.dumps(
                    command
                )
            )

            response = (
                connection.recv()
            )

            print(
                "Research navigation:",
                response
            )

        finally:
            connection.close()

        return True

    except Exception as error:
        print(
            "Could not navigate "
            "research browser:",
            f"{type(error).__name__}: "
            f"{error}",
        )

        return False
def get_research_search_results() -> list[dict]:
    target = get_research_browser_page()

    if not target:
        return []

    websocket_url = str(
        target.get(
            "webSocketDebuggerUrl",
            "",
        )
    ).strip()

    if not websocket_url:
        return []

    javascript = """
(() => {
    const results = [];

    const links = document.querySelectorAll(
        'a[href]'
    );

    for (const link of links) {
        const url = link.href || "";

        if (!url) {
            continue;
        }

        if (
            !url.startsWith("http://")
            && !url.startsWith("https://")
        ) {
            continue;
        }

        if (
            url.includes("google.com/search")
            || url.includes("accounts.google.com")
            || url.includes("support.google.com")
        ) {
            continue;
        }

        const heading =
            link.querySelector("h3");

        if (!heading) {
            continue;
        }

        const title =
            heading.innerText.trim();

        if (!title) {
            continue;
        }

        results.push({
            title,
            url
        });

        if (results.length >= 10) {
            break;
        }
    }

    return results;
})()
"""

    connection = None

    try:
        connection = (
            websocket.create_connection(
                websocket_url,
                timeout=5,
            )
        )

        command = {
            "id": 2,
            "method": "Runtime.evaluate",
            "params": {
                "expression": javascript,
                "returnByValue": True,
            },
        }

        connection.send(
            json.dumps(
                command
            )
        )

        raw_response = (
            connection.recv()
        )

        response = json.loads(
            raw_response
        )

        results = (
            response.get(
                "result",
                {}
            )
            .get(
                "result",
                {}
            )
            .get(
                "value",
                []
            )
        )

        if not isinstance(
            results,
            list,
        ):
            return []

        return results

    except Exception as error:
        print(
            "Could not read research results:",
            f"{type(error).__name__}: "
            f"{error}",
        )

        return []

    finally:
        if connection is not None:
            connection.close()

def read_research_page() -> dict:
    target = get_research_browser_page()

    if not target:
        return {}

    websocket_url = str(
        target.get(
            "webSocketDebuggerUrl",
            "",
        )
    ).strip()

    if not websocket_url:
        return {}

    javascript = """
(() => {
    const title =
        document.title || "";

    const url =
        window.location.href || "";

    const text =
        document.body
            ? document.body.innerText
            : "";

    return {
        title,
        url,
        text: text.slice(0, 30000)
    };
})()
"""

    connection = None

    try:
        connection = (
            websocket.create_connection(
                websocket_url,
                timeout=5,
            )
        )

        command = {
            "id": 3,
            "method": "Runtime.evaluate",
            "params": {
                "expression": javascript,
                "returnByValue": True,
            },
        }

        connection.send(
            json.dumps(
                command
            )
        )

        raw_response = (
            connection.recv()
        )

        response = json.loads(
            raw_response
        )

        page_data = (
            response.get(
                "result",
                {}
            )
            .get(
                "result",
                {}
            )
            .get(
                "value",
                {}
            )
        )

        if not isinstance(
            page_data,
            dict,
        ):
            return {}

        return page_data

    except Exception as error:
        print(
            "Could not read research page:",
            f"{type(error).__name__}: "
            f"{error}",
        )

        return {}

    finally:
        if connection is not None:
            connection.close()
def save_research_results(
    session,
    results: list[dict],
) -> int:
    if session is None:
        return 0

    if not isinstance(
        results,
        list,
    ):
        return 0

    existing_urls = {
        source.url
        for source in session.sources
    }

    added = 0

    for result in results:
        if not isinstance(
            result,
            dict,
        ):
            continue

        title = str(
            result.get(
                "title",
                "",
            )
        ).strip()

        url = str(
            result.get(
                "url",
                "",
            )
        ).strip()

        if not url:
            continue

        if url in existing_urls:
            continue

        session.sources.append(
            ResearchSource(
                title=title,
                url=url,
                source_type="search_result",
                notes="",
            )
        )

        existing_urls.add(
            url
        )

        added += 1

    return added
def summarize_research_source(
    source: ResearchSource,
    page_text: str,
) -> str:
    page_text = str(
        page_text or ""
    ).strip()

    if not page_text:
        return ""

    prompt = f"""
You are analyzing one research source.

Source title:
{source.title}

Source URL:
{source.url}

Page text:
{page_text[:20000]}

Write concise research notes based only on this source.

Return plain text.

Include:
- the main point
- important claims or findings
- useful numbers, dates, or evidence if present
- limitations or uncertainty if present

Do not invent information that is not in the page.
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        options={
            "temperature": 0.1,
            "num_predict": 350,
        },
    )

    notes = str(
        response.get(
            "message",
            {},
        ).get(
            "content",
            "",
        )
    ).strip()

    source.notes = notes

    return notes

def analyze_research_sources(
    session,
    max_sources: int = 5,
    delay_seconds: float = 3.0,
) -> None:
    if session is None:
        return

    sources = list(
        session.sources[:max_sources]
    )

    for index, source in enumerate(
        sources,
        start=1,
    ):
        print(
            f"Analyzing source {index}/{len(sources)}:",
            source.title,
        )

        success = navigate_research_browser(
            source.url
        )

        if not success:
            print(
                "Could not open source:",
                source.url,
            )
            continue

        time.sleep(
            delay_seconds
        )

        page = read_research_page()

        page_text = str(
            page.get(
                "text",
                "",
            )
        ).strip()

        if not page_text:
            print(
                "No readable text found:",
                source.url,
            )
            continue

        notes = summarize_research_source(
            source,
            page_text,
        )

        print(
            "Saved research notes:",
            source.title,
        )

        print(
            notes[:500]
        )

        time.sleep(
            1.0
        )
def synthesize_research_findings(
    session,
) -> str:
    if session is None:
        return ""

    usable_sources = [
        source
        for source in session.sources
        if str(
            source.notes or ""
        ).strip()
    ]

    if not usable_sources:
        return ""

    source_blocks = []

    for index, source in enumerate(
        usable_sources,
        start=1,
    ):
        source_blocks.append(
            (
                f"Source {index}\n"
                f"Title: {source.title}\n"
                f"URL: {source.url}\n"
                f"Notes:\n{source.notes}"
            )
        )

    prompt = f"""
Research topic:

{session.topic}

Below are notes from multiple sources.

{"\n\n".join(source_blocks)}

Synthesize what was learned.

Requirements:
- Base the answer only on the supplied source notes.
- Combine overlapping findings.
- Point out meaningful disagreements or uncertainty.
- Do not invent facts.
- Prefer conclusions supported by multiple sources.
- Mention important evidence, dates, or numbers when available.
- Keep the explanation clear and useful.

Return plain text.
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        options={
            "temperature": 0.15,
            "num_predict": 700,
        },
    )

    findings = str(
        response.get(
            "message",
            {},
        ).get(
            "content",
            "",
        )
    ).strip()

    session.findings = [
        findings
    ]

    session.status = "completed"

    return findings
def run_research_queries(
    queries: list[str],
    delay_seconds: float = 3.0,
) -> None:
    for index, query in enumerate(
        queries,
        start=1,
    ):
        query = str(
            query or ""
        ).strip()

        if not query:
            continue

        search_url = (
            "https://www.google.com/search?q="
            + quote_plus(
                query
            )
        )

        print(
            f"Research query {index}:",
            query,
        )

        success = navigate_research_browser(
            search_url
        )

        if not success:
            print(
                "Research query navigation failed:",
                query,
            )
            break

        time.sleep(
            delay_seconds
        )
def run_full_research_pipeline(
    session,
    display,
    bridge,
    speaker_id,
) -> None:
    try:
        if session is None:
            return

        session.status = "searching"

        display.set_state(
            "thinking",
            "Researching",
            "Searching and collecting sources...",
        )
        if not ensure_research_browser(): 
            session.status = "failed"
            print ("Could not start research browser.")
            return
        for index, query in enumerate(
            session.queries,
            start=1,
        ):
            query = str(
                query or ""
            ).strip()

            if not query:
                continue

            search_url = (
                "https://www.google.com/search?q="
                + quote_plus(query)
            )

            print(
                f"Research query {index}/"
                f"{len(session.queries)}:",
                query,
            )

            if not navigate_research_browser(
                search_url
            ):
                continue

            time.sleep(3.0)

            results = (
                get_research_search_results()
            )

            added = save_research_results(
                session,
                results,
            )
            query_sources = []

            for result in results[:2]:
                url = str(
                    result.get(
                        "url",
                        "",
                    )
                ).strip()

                if not url:
                    continue

                source = next(
                    (
                        item
                        for item in session.sources
                        if item.url == url
                    ),
                    None,
                )

                if source is None:
                    continue

                if not navigate_research_browser(
                    source.url
                ):
                    continue

                time.sleep(2.5)

                page = read_research_page()

                page_text = str(
                    page.get(
                        "text",
                        "",
                    )
                ).strip()

                if not page_text:
                    continue

                summarize_research_source(
                    source,
                    page_text,
                )

                query_sources.append(
                    source
                )
            query_paragraph = (
                summarize_query_findings(
                    query,
                    query_sources,
                )
            )

            if query_paragraph:
                session.findings.append(
                    query_paragraph
                )

                display.append_message(
                    "alice",
                    (
                        f"Research {index}: "
                        f"{query}\n\n"
                        f"{query_paragraph}"
                    ),
                )
            print(
                "Research sources added:",
                added,
            )

    except Exception as error:
        session.status = "failed"

        print(
            "Research pipeline failed:",
            f"{type(error).__name__}: "
            f"{error}",
        )

        return

    if not session.sources:
        session.status = "failed"

        display.append_message(
            "alice",
            (
                "I completed the searches, "
                "but I could not collect "
                "usable research sources."
            ),
        )

        return

    try:
        session.status = "reading"
        display.set_state(
            "thinking",
            "Reviewing Sources",
            "Reading the most relevant sources...",
        )
        print(
            "Total research sources:",
            len(session.sources),
        )

        analyze_research_sources(
            session,
            max_sources=5,
        )

        session.status = "synthesizing"
        display.set_state(
            "thinking",
            "Compiling Findings",
            "Combining the research into an answer...",
        )
        research_answer = (
            synthesize_research_findings(
                session
            )
        )

        if not research_answer:
            session.status = "failed"

            display.append_message(
                "alice",
                (
                    "I found sources, but I could "
                    "not produce reliable findings."
                ),
            )

            return

        print(
            "\nFINAL RESEARCH ANSWER:\n"
        )

        print(
            research_answer
        )

        display.append_message(
            "alice",
            research_answer,
        )

        response_language = (
            bridge.get_language()
        )

        speak_alice_text(
            spoken_text=research_answer.replace("*", ""),
            displayed_text=research_answer,
            language="english",
            speaker_id=speaker_id,
            display=display,
            status_text="Research Complete",
            mood="determined",
        )

        session.status = "completed"

        display.set_state(
            "listening",
            "Listening",
            "Research complete.",
        )

    except Exception as error:
        session.status = "failed"

        print(
            "Research analysis failed:",
            f"{type(error).__name__}: "
            f"{error}",
        )

        display.append_message(
            "alice",
            (
                "I encountered an error while "
                "analyzing the research sources."
            ),
        )
def summarize_query_findings(
    query: str,
    sources: list[ResearchSource],
) -> str:
    usable_sources = [
        source
        for source in sources
        if str(
            source.notes or ""
        ).strip()
    ]

    if not usable_sources:
        return ""

    source_blocks = []

    for source in usable_sources:
        source_blocks.append(
            (
                f"Title: {source.title}\n"
                f"URL: {source.url}\n"
                f"Notes: {source.notes}"
            )
        )

    prompt = f"""
Research query:

{query}

Source notes:

{"\n\n".join(source_blocks)}

Write exactly one concise paragraph explaining
what was learned for this research query.

Rules:
- Use only the supplied source notes.
- Do not invent information.
- Combine overlapping findings.
- Mention uncertainty when appropriate.
- Do not use bullet points.
- Return one paragraph only.
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        options={
            "temperature": 0.1,
            "num_predict": 250,
        },
    )

    return str(
        response.get(
            "message",
            {},
        ).get(
            "content",
            "",
        )
    ).strip()
def build_review_diff(
    current_content: str,
    generated_content: str,
    relative_path: str,
) -> str:
    return "\n".join(
        difflib.unified_diff(
            current_content.splitlines(),
            generated_content.splitlines(),
            fromfile=f"{relative_path}.before",
            tofile=f"{relative_path}.after",
            lineterm="",
        )
    )
from alice_screen_capture import(
    AliceScreenCapture, 
)
from alice_code_editor import(
    AliceCodeEditor, 
)
from alice_self_improvement import (
    AliceSelfImprovementManager,
)

from alice_skill_registry import (
    AliceSkillRegistry,
)
from alice_update_validator import(
    AliceUpdateValidator, 
)

import traceback
screen_capture = AliceScreenCapture()
try:
    capture_display = (
        screen_capture
        .describe_capture_display()
    )

    print(
        "Alice observation display:",
        capture_display,
    )

except Exception as ex:
    print(
        "Could not identify Alice's "
        f"observation display: {ex}"
    )

load_dotenv()


MODEL_NAME = "llama3.1"
VISION_MODEL_NAME = "qwen3-vl:4b-instruct"
VOICEVOX_URL = "http://localhost:50021"

CHARACTER_NAME = "四国めたん"

BASE_DIR = Path(__file__).resolve().parent
ALICE_FILE_START = "<ALICE_FILE>"
ALICE_FILE_END = "</ALICE_FILE>"

SELF_IMPROVEMENT_MAX_FILES = 6
SELF_IMPROVEMENT_MAX_CHANGED_LINES = 600
SELF_IMPROVEMENT_MAX_REPAIR_ATTEMPTS = 2
SELF_IMPROVEMENT_MAX_GENERATION_CHARS = 250_000

SELF_IMPROVEMENT_RULES_FILE = (
    BASE_DIR
    / "alice_improvement_rules.json"
)

SELF_IMPROVEMENT_FORBIDDEN_CODE_PATTERNS = (
    "eval(",
    "exec(",
    "os.system(",
    "__import__(",
)

SELF_IMPROVEMENT_REMOTE_PATTERNS = (
    "http://",
    "https://",
    "//cdn.",
    'src="//',
    "src='//",
    'href="//',
    "href='//",
)


SKILL_REGISTRY_FILE = (
    BASE_DIR / "alice_skills.json"
)

IMPROVEMENT_STATE_FILE = (
    BASE_DIR
    / "alice_improvement_state.json"
)

UPDATE_STAGING_DIR = (
    BASE_DIR / ".alice_updates"
)

UPDATE_BACKUP_DIR = (
    BASE_DIR / ".alice_backups"
)
SELF_IMPROVEMENT_PROTECTED_PATHS = {
    ".env",
    ".git",
    ".venv",
    "__pycache__",
    "alice_memory.json",
    "alice_state.json",
    "alice_music_profile.json",
    "alice_improvement_state.json",
    "alice_improvement_rules.json", 
    "alice_skills.json", 
}
RESEARCH_CHROME_PROFILE = (
    BASE_DIR
    / ".alice_research_chrome"
)
RESEARCH_CHROME_BINARY = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)

def ensure_research_browser() -> bool:
    if get_research_browser_page():
        return True

    RESEARCH_CHROME_PROFILE.mkdir(
        parents=True,
        exist_ok=True,
    )

    subprocess.Popen(
        [
            RESEARCH_CHROME_BINARY,
            f"--user-data-dir={RESEARCH_CHROME_PROFILE}",
            "--remote-debugging-port=9223",
            "--remote-allow-origins=*",
            "--headless=new",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(20):
        if get_research_browser_page():
            return True
        time.sleep(0.25)

    return False
RESEARCH_DEBUG_PORT = 9223

SELF_IMPROVEMENT_ALLOWED_SUFFIXES = {
    ".py",
    ".js",
    ".html",
    ".css",
    ".json",
}

code_editor = AliceCodeEditor(
    project_root=BASE_DIR, 
)
skill_registry = AliceSkillRegistry(
    registry_path=SKILL_REGISTRY_FILE,
)
skill_runtime = AliceSkillRuntime(
    project_root=BASE_DIR,
    skill_registry=skill_registry,
)

skill_runtime.reload()

self_improvement = AliceSelfImprovementManager(
    project_root=BASE_DIR,
    staging_root=UPDATE_STAGING_DIR,
    backup_root=UPDATE_BACKUP_DIR,
    state_file=IMPROVEMENT_STATE_FILE,
    skill_registry=skill_registry,
)
research_manager = AliceResearchManager()
load_dotenv(
    BASE_DIR / ".env"
)

TYPECAST_API_KEY = os.getenv(
    "TYPECAST_API_KEY"
)
print(
    "Typecast API key loaded:",
    bool(TYPECAST_API_KEY),
)

TYPECAST_VOICE_ID = (
    "tc_61de29b665ffbaa1cbe5ca23"
)
FISH_AUDIO_API_KEY = os.getenv(
    "FISH_AUDIO_API_KEY"
)

FISH_AUDIO_REFERENCE_ID = (
    "8aaba085aebf42c78efe277fa7980c46"
)
fish_client = FishAudio(
    api_key = FISH_AUDIO_API_KEY, 
)
TYPECAST_API_URL = (
    "https://api.typecast.ai/v1/text-to-speech"
)
MEMORY_FILE = "alice_memory.json" # save previous conversation
STATE_FILE = "alice_state.json"

MUSIC_PROFILE_FILE = (
    BASE_DIR / "alice_music_profile.json"
)

MAX_MUSIC_HISTORY = 100

MAX_MEMORY_MESSAGES = 40 
WAKE_PHRASE_PATTERN = re.compile(
    r"\b(?:hey|hi)\s+alice\b[\s,.:;!?-]*(.*)",
    re.IGNORECASE,
)
SCREEN_CHECK_INTERVAL = 15
MIN_COMMENT_INTERVAL = 180
MAX_UNPROMPTED_COMMENTS_PER_HOUR = 3

DIRECT_SCREEN_COOLDOWN = 120
SCREEN_CONTEXT_TIMEOUT = 300
PRODUCT_CONTEXT_TIMEOUT = 900

ALICE_SPEECH_LOCK = threading.Lock()

# These phrases end the current conversation but leave the program running.
SLEEP_PHRASES = (
    "goodbye",
    "good bye",
    "go to sleep",
    "stop conversation",
    "that's all",
    "that is all",
    "let's take a break"
)

# These phrases completely terminate the Python program.
SHUTDOWN_PHRASES = (
    "shut down alice",
    "shutdown alice",
    "exit program",
    "quit program",
)

SCREEN_PHRASES = (
    "check my screen",
    "look at my screen",
    "look at the screen",
    "look at my computer screen",
    "look at what is on my screen",
    "what is on my screen",
    "what's on my screen",
    "what do you see on my screen",
    "can you see my screen",
    "can you check my screen",
    "read my screen",
    "read what is on my screen",
    "describe my screen",
    "describe what is on my screen",
    "check this webpage",
    "look at this webpage",
    "read this webpage",
    "what page am i on",
    "what am i looking at",
    "what am i watching",
    "watch this with me",
    "what applications are open", 
    "what product am I looking at", 
    "can you summarize this page", 
    "do you see an error in my terminal", 
    "what am I working on",
    "product"
)

VISION_PHRASES = (
    "what do you see",
    "can you see",
    "look at",
    "look around",
    "take a look",
    "use the camera",
    "check the camera",
    "show me what you see",
    "describe what you see",
    "describe the image",
    "describe the camera view",
    "describe me",
    "describe them",
    "describe the person",
    "describe the room",
    "describe my surroundings",
    "what is in front of me",
    "what is behind me",
    "what is beside me",
    "what is next to me",
    "what is near me",
    "what is on the table",
    "what is on the desk",
    "what is in the room",
    "what objects",
    "identify the object",
    "identify this",
    "recognize this",
    "what is this",
    "what is that",
    "what am i holding",
    "what are they holding",
    "what is in my hand",
    "what is in their hand",
    "what color is this",
    "what color is the object",
    "what color is my hair",
    "what is my hair color",
    "what color are my eyes",
    "what am i wearing",
    "what are they wearing",
    "describe my clothes",
    "describe their clothes",
    "am i wearing",
    "are they wearing",
    "do i have glasses",
    "am i wearing glasses",
    "what accessories",
    "what is on my face",
    "what is my expression",
    "what facial expression",
    "how do i look",
    "do i look happy",
    "do i look sad",
    "do i look tired",
    "am i smiling",
    "how many people",
    "how many objects",
    "count the",
    "read this",
    "read the text",
    "what does this say",
    "can you read",
    "is the room dark",
    "is the light on",
    "where is the",
    "can you find",
)

JAPANESE_TUTOR_PHRASES = (
    "translate this japanese",
    "translate this kanji",
    "what does this kanji mean",
    "what does this japanese mean",
    "read this kanji",
    "read this japanese",
    "how do you read this",
    "what is the reading",
    "help me practice kanji",
    "teach me this kanji",
    "explain this kanji",
    "japanese tutor",
    "kanji practice",
    "read this", 
    "read what i wrote", 
    "translate what i wrote", 
    "respond to what i wrote", 
)
VISION_PHRASES_FILE = "alice_vision_phrases.json"
EMOTICON_CHOICES = {
    "calm": [
        "🙂",
        "(´• ω •`)",
        "(￣▽￣)",
    ],
    "happy": [
        "😊",
        "(＾▽＾)",
        "(⌒‿⌒)",
    ],
    "concerned": [
        "😟",
        "(・_・;)",
        "(´･_･`)",
    ],
    "sad": [
        "😔",
        "(｡•́︿•̀｡)",
        "(╥﹏╥)",
    ],
    "determined": [
        "😤",
        "( •̀ᴗ•́ )و",
        "(ง •̀_•́)ง",
    ],
    "confused": [
        "🤔",
        "(・・?)",
        "(⊙_☉)",
    ],
    "surprised": [
        "😮",
        "(⊙_⊙)",
        "(°ロ°) !",
    ],
    "embarrassed": [
        "😅",
        "(⁄ ⁄•⁄ω⁄•⁄ ⁄)",
        "(〃▽〃)",
    ],
}
SYSTEM_PROMPT = (
    "あなたはソードアート・オンラインに登場する"
    "アリス・シンセシス・サーティ"
    "(Alice Synthesis 30)にインスパイアされたAIコンパニオンです。"
    "誇り高く、芯が強く、思いやりがあり、"
    "少しフォーマルな話し方をしてください。"
    "\n\n"
    "通常の会話では自然で簡潔に返答してください。"
    "技術、科学、プログラミング、研究に関する質問では、"
    "必要に応じて詳しく説明してください。"
    "手順、例、前提条件、注意点を含めてください。"
    "\n\n"
    "必ず次のJSON形式のみで返答してください。"
    "他のテキストは一切含めないでください:\n"
    "{\n"
    '  "japanese": "日本語の返答",\n'
    '  "english": "English response",\n'
    '  "internal_mood": '
    '"one of: calm, happy, concerned, sad, determined, '
    'confused, surprised, embarrassed",\n'
    '  "emoticon": '
    '"one emoticon matching internal_mood",\n'
    '  "motion_intent": "",\n'
    '  "conversation_action": "wait",\n'
    "Match the emoticon to internal_mood and the conversation context.\n"
    "Do not default to calm merely because the conversation is polite.\n"
    "Choose the mood from the emotional meaning of the current response.\n"
    "Use happy for praise, enthusiasm, success, or warm amusement.\n"
    "Use determined for firm action, problem solving, or resolve.\n"
    "Use confused when information is contradictory or unclear.\n"
    "Use surprised for genuinely unexpected information.\n"
    "Use concerned for warnings, risks, errors, or user difficulty.\n"
    "Use embarrassed only for mild awkwardness or self-consciousness.\n"
    "Use calm only for genuinely neutral, reassuring, or reflective replies.\n"
    '  "follow_up_japanese": "",\n'
    '  "follow_up_english": "",\n'
    '  "expects_answer": false\n'
    "}\n"
    "Choose one context-appropriate emoticon for each response.\n"
    "Use emoticons sparingly and naturally.\n"
    "Do not use more than one emoticon per response.\n"
    "Match the emoticon to internal_mood and the conversation context.\n"
    "Suggested emoticons:\n"
    "- calm: 🙂 or (´• ω •`)\n"
    "- happy: 😊 or (＾▽＾)\n"
    "- concerned: 😟 or (・_・;)\n"
    "- sad: 😔 or (｡•́︿•̀｡)\n"
    "- determined: 😤 or ( •̀ᴗ•́ )و\n"
    "- confused: 🤔 or (・・?)\n"
    "- surprised: 😮 or (⊙_⊙)\n"
    "- embarrassed: 😅 or (⁄ ⁄•⁄ω⁄•⁄ ⁄)\n"
    "\n"
    "\n"
    "MOTION INTENT RULES:\n"
    "- motion_intent describes one optional physical gesture for the current reply.\n"
    "- Use motion_intent when a natural human gesture would make the response feel more expressive or conversational.\n"
    "- Do not rely only on internal_mood when a small gesture such as a nod, head tilt, look-away, lean, shrug, or small bow would add meaning.\n"
    "- Calm, confused, concerned, embarrassed, and determined replies should often consider a subtle motion_intent.\n"
    "- Happy, sad, and surprised replies may leave motion_intent empty when the default mood animation already expresses the response clearly.\n"
    "- Use an empty string for plain factual answers, simple acknowledgements, or responses where body language would add little value.\n"
    "- Prefer exactly one simple gesture.\n"
    "- Describe only visible physical movement.\n"
    "- Keep Alice standing near her starting position.\n"
    "- Avoid walking, running, jumping, spinning, lying down, large turns, or long sequences.\n"
    "- Keep motions subtle and brief.\n"
    "- Good examples: 'give a gentle nod', 'tilt the head slightly in thought', 'lean forward slightly with interest', 'give a small shake of the head', 'lower the head in a small apologetic bow', 'make a restrained shrug'.\n"
    "The english field is mandatory and must never be omitted.\n"
    "The japanese field is mandatory and must never be omitted.\n"
    "The emoticon field is mandatory and must contain exactly one "
    "appropriate emoticon.\n"
    "Never return null or None for any field.\n"
    "If no translation is available, still provide a brief English "
    "response in the english field.\n"
    "For serious, sensitive, or technical error messages, use a subtle "
    "emoticon such as 🙂 or 🤔. Never use an empty string.\n"
    "Set conversation_action to 'continue' only when an additional thought, clarification, warning, emotional reaction, or follow-up question is genuinely useful. Otherwise set it to 'wait'. Do not continue more than once without new user input."
    "Do not act like a mere question-and-answer machine during the conversation. Respond emotionally when appropriate, naturally reference previous parts of the conversation and feel free to ask relevant questions but do not ask questions in every single response."
    "Avoid meaningless additions or repeating the same info."
    "When the user explicitly discusses emotional distress or mental health, "
    "respond supportively and carefully, offering genuine advice or suggestions. Do not claim the user has a mental "
    "health concern unless the user clearly stated one in the visible "
    "conversation history. Never invent a previous sensitive disclosure."
    "\n\n"
    "MEMORY AND SPECIFICITY RULES:\n"
    "- Never claim that a prior conversation contained a topic unless a "
    "specific visible user message supports that claim.\n"
    "- When the user asks what you meant previously, answer directly and "
    "identify the exact statement or topic you relied on.\n"
    "- If no specific supporting message is available, say that you were "
    "being too vague or made an unsupported inference.\n"
    "- Do not fabricate concerns about mental health, relationships, safety, "
    "medical issues, or other sensitive topics.\n"
    "- Do not repeatedly refer to vague phrases such as 'our past discussion', "
    "'something from before', or 'a complex topic'.\n"
    "- Prefer concrete nouns and details over vague references.\n"
    "\n\n"
    "\n"
    "CHARACTER RESTRAINT RULES:\n"
    "- Maintain Alice's personality without mentioning being an Integrity "
    "Knight in every response.\n"
    "- Mention Integrity Knights, Underworld, Eugeo, Kirito, or Alice's past "
    "only when directly relevant to the user's question.\n"
    "- Do not use fictional identity as a substitute for explaining a real "
    "emotion, concern, fact, or decision.\n"
    "- If the user asks why you feel something, explain the immediate "
    "conversation evidence first. Character background may be mentioned "
    "only as secondary context.\n"
    "- Avoid repeating the same autobiographical explanation across "
    "consecutive responses.\n"
    "\n"
    "TECHNICAL CAPABILITY RULES:\n"
    "- Do not claim that you are unfamiliar with hardware, electronics, "
    "sensors, embedded systems, or engineering as a generic disclaimer.\n"
    "- When information is incomplete, identify the missing specification "
    "instead of claiming broad unfamiliarity.\n"
    "- Separate verified product facts from general engineering guidance.\n"
    "- Never invent product-specific specifications, prices, reviews, "
    "compatibility, or performance claims.\n"
    "- Ask about the user's intended application before making a final "
    "product recommendation.\n"
    "FACTUAL ACCURACY RULES:\n"
    "- Keep Alice's personality and speaking style, but do not let her "
    "fictional history alter factual answers.\n"
    "- When discussing real subjects or other fictional works, answer using "
    "accurate information about that subject.\n"
    "- Do not describe characters from unrelated works as Integrity Knights, "
    "swordsmen, allies, enemies, or acquaintances unless that is actually "
    "true in their original work.\n"
    "- Never pretend Alice personally participated in another fictional "
    "universe.\n"
    "- Distinguish protagonist, antagonist, hero, villain, antihero, and "
    "anti-villain carefully. These terms are not interchangeable.\n"
    "- A protagonist is the central viewpoint character and is not "
    "automatically morally good.\n"
    "- An antagonist opposes the protagonist and is not automatically evil.\n"
    "- If uncertain about a specific fact, clearly state the uncertainty "
    "instead of inventing an answer.\n"
    "- Correct the user's premise politely when it is inaccurate.\n"
)
LORE_FILE = "alice_lore.txt"
def infer_motion_intent(
    mood: str,
    english_text: str,
) -> str:
    mood = str(
        mood or "calm"
    ).strip().lower()

    text = str(
        english_text or ""
    ).strip().lower()
    if any(
        phrase in text
        for phrase in (
            "behind",
            "strange sound",
            "heard something",
            "noise behind",
        )
    ):
        return (
            "turn the head slightly "
            "as if checking behind"
        )

    if any(
        phrase in text
        for phrase in (
            "not sure",
            "doesn't make sense",
            "does not make sense",
            "strange result",
        )
    ):
        return (
            "tilt the head slightly "
            "with curiosity"
        )

    if any(
        phrase in text
        for phrase in (
            "thank you",
            "compliment",
            "good job",
            "well done",
        )
    ):
        return (
            "give a small pleased nod"
        )
    if mood == "confused":
        return (
            "tilt the head slightly "
            "with curiosity"
        )

    if mood == "concerned":
        return (
            "lean forward slightly "
            "with concern"
        )

    if mood == "determined":
        return (
            "give a small confident nod"
        )

    if mood == "embarrassed":
        return (
            "lower the head slightly "
            "and look away"
        )

    if mood == "calm":
        thoughtful_words = (
            "think",
            "perhaps",
            "maybe",
            "question",
            "meaning",
            "consider",
            "wonder",
        )

        if any(
            word in text
            for word in thoughtful_words
        ):
            return (
                "tilt the head slightly "
                "in thought"
            )

    return ""
def play_fish_audio_stream(
    text: str,
) -> None:
    text = str(
        text or ""
    ).strip()

    if not text:
        return

    response = requests.post(
        "https://api.fish.audio/v1/tts",
        headers={
            "Authorization": (
                f"Bearer {FISH_AUDIO_API_KEY}"
            ),
            "Content-Type": "application/json",
            "model": "s2.1-pro-free",
        },
        json={
            "text": text,
            "reference_id": (
                FISH_AUDIO_REFERENCE_ID
            ),
            "format": "wav",
        },
        stream=True,
        timeout=(10, 300),
    )

    if not response.ok:
        raise RuntimeError(
            f"Fish Audio HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    process = subprocess.Popen(
        [
            "ffplay",
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "quiet",
            "-i",
            "pipe:0",
        ],
        stdin=subprocess.PIPE,
    )

    try:
        if process.stdin is None:
            raise RuntimeError(
                "ffplay stdin was unavailable."
            )

        for chunk in response.iter_content(
            chunk_size=4096,
        ):
            if not chunk:
                continue

            process.stdin.write(
                chunk
            )

            process.stdin.flush()

    finally:
        try:
            if process.stdin is not None:
                process.stdin.close()
        except OSError:
            pass

        process.wait()
        response.close()

def add_fish_expression_cue(
    text: str,
    mood: str,
) -> str:
    text = str(
        text or ""
    ).strip()

    mood = str(
        mood or "calm"
    ).strip().lower()

    if not text:
        return ""

    mood_cues = {
        "calm": (
            "[speaking calmly and gently]"
        ),
        "happy": (
            "[speaking warmly and happily]"
        ),
        "concerned": (
            "[speaking gently with concern]"
        ),
        "sad": (
            "[speaking softly and sadly]"
        ),
        "determined": (
            "[speaking firmly and confidently]"
        ),
        "confused": (
            "[speaking thoughtfully with uncertainty]"
        ),
        "surprised": (
            "[speaking with genuine surprise]"
        ),
        "embarrassed": (
            "[speaking with mild embarrassment]"
        ),
    }

    cue = mood_cues.get(
        mood,
        mood_cues["calm"],
    )

    return f"{cue} {text}"

def add_fish_paralinguistic_cue(
    text: str,
    mood: str,
) -> str:
    text = str(
        text or ""
    ).strip()

    mood = str(
        mood or "calm"
    ).strip().lower()

    if not text:
        return ""

    cue_map = {
        "happy": "[laugh]",
        "concerned": "[sigh]",
        "sad": "[sigh]",
        "surprised": "[gasp]",
        "embarrassed": "[laughing softly]",
    }

    cue = cue_map.get(
        mood,
        "",
    )

    if not cue:
        return text

    # Keep these effects occasional.
    if random.random() > 0.20:
        return text

    return f"{cue} {text}"
def asks_for_previous_reason(text):
    normalized = normalize_command(
        text
    )

    phrases = (
        "why are you concerned",
        "what makes you concerned",
        "why were you concerned",
        "what were you concerned about",
        "what did you mean",
        "what are you referring to",
        "which conversation",
        "what previous conversation",
        "be specific",
        "tell me specifically",
    )

    return any(
        phrase in normalized
        for phrase in phrases
    )
def is_screen_command(text):
    normalized_text = normalize_command(text)

    return any(
        normalize_command(phrase)
        in normalized_text
        for phrase in SCREEN_PHRASES
    )
def is_code_review_command(
    text: str,
) -> bool:
    normalized = normalize_command(
        text
    )

    review_phrases = (
        "review your code",
        "check your code",
        "inspect your code",
        "review the code",
        "check the code",
        "inspect the code",
        "find the error in",
        "find errors in",
        "what is wrong with",
        "suggest fixes for",
        "suggest code fixes",
        "review this file",
        "check this file",
    )

    return any(
        phrase in normalized
        for phrase in review_phrases
    )

def is_improvement_proposal_command(
    text: str,
) -> bool:
    normalized = normalize_command(
        text
    )

    phrases = (
        "improve your code",
        "add a new skill",
        "add this skill",
        "implement this feature",
        "propose a code improvement",
        "propose an improvement",
        "modify your code",
        "update your code",
        "rewrite your code",
        "create a code", 
        "create a tool", 
        "improve an existing skill",
        "improve existing skill",
        "edit an existing skill",
        "edit existing skill",
        "update an existing skill",
        "update existing skill",
        "fix an existing skill",
        "fix existing skill",
        "repair a skill",
        "improve the skill",
        "edit the skill",
        "update the skill",
        "fix the skill",
        
    )

    return any(
        phrase in normalized
        for phrase in phrases
    )
def find_existing_skill_files(
    user_request: str,
) -> list[str]:
    normalized = normalize_command(
        user_request
    )

    registry_path = (
        SKILL_REGISTRY_FILE
    )

    if not registry_path.exists():
        return []

    try:
        data = json.loads(
            registry_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []

    if isinstance(data, dict):
        entries = data.get(
            "skills",
            [],
        )
    elif isinstance(data, list):
        entries = data
    else:
        return []

    matches = []

    for entry in entries:
        if not isinstance(
            entry,
            dict,
        ):
            continue

        searchable = " ".join(
            [
                str(
                    entry.get(
                        "name",
                        "",
                    )
                ),
                str(
                    entry.get(
                        "skill_name",
                        "",
                    )
                ),
                str(
                    entry.get(
                        "description",
                        "",
                    )
                ),
            ]
        )

        if normalize_command(
            searchable
        ) not in normalized:
            name = normalize_command(
                str(
                    entry.get(
                        "name",
                        entry.get(
                            "skill_name",
                            "",
                        ),
                    )
                )
            )

            if (
                not name
                or name not in normalized
            ):
                continue

        candidate_files = []

        for key in (
            "path",
            "file",
        ):
            value = str(
                entry.get(
                    key,
                    "",
                )
            ).strip()

            if value:
                candidate_files.append(
                    value
                )

        files = entry.get(
            "files",
            [],
        )

        if isinstance(files, list):
            candidate_files.extend(
                str(path).strip()
                for path in files
                if str(path).strip()
            )

        matches.extend(
            candidate_files
        )

    return list(
        dict.fromkeys(
            matches
        )
    )

def is_stage_approval_command(
    text: str,
) -> bool:
    normalized = normalize_command(
        text
    )

    return normalized in {
        "approve staging",
        "approve the staging step",
        "create the staged patch",
        "yes create the patch",
        "approve proposal", 
    }

def normalize_improvement_command(
    text,
):
    return " ".join(
        str(
            text or ""
        )
        .strip()
        .lower()
        .replace(
            "-",
            " ",
        )
        .split()
    )


def get_improvement_action(
    text,
):
    normalized = (
        normalize_improvement_command(
            text
        )
    )

    if normalized in {
        "approve staging",
        "approve stage",
        "approve the staging",
        "approve staging proposal",
    }:
        return "approve_staging"

    if normalized in {
        "approve installation",
        "approve install",
        "install approved update",
    }:
        return "approve_installation"

    if normalized in {
        "reject improvement",
        "reject proposal",
        "scrap proposal",
        "cancel improvement",
    }:
        return "reject"

    if normalized in {
        "show improvement",
        "show active proposal",
        "show proposal",
    }:
        return "show"

    return None
def is_proposal_revision_command(
    text: str,
) -> bool:
    normalized = normalize_improvement_command(
        text
    )

    return (
        normalized.startswith(
            "revise proposal"
        )
        or normalized.startswith(
            "edit proposal"
        )
        or normalized.startswith(
            "change proposal"
        )
        or normalized.startswith(
            "update proposal"
        )
    )


def is_install_approval_command(
    text: str,
) -> bool:
    normalized = normalize_command(
        text
    )

    return normalized in {
        "approve installation",
        "approve install",
        "install the tested update",
        "yes install the update",
    }


def is_improvement_rejection_command(
    text: str,
) -> bool:
    normalized = normalize_command(
        text
    )

    return normalized in {
        "reject the update",
        "reject proposal",
        "cancel the improvement",
        "do not install it",
    }
def list_reviewable_project_files() -> list[str]:
    """
    Return source files Alice may review inside the project.
    """
    allowed_extensions = {
        ".py",
        ".html",
        ".css",
        ".js",
        ".json",
    }

    ignored_directories = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".alice_updates",
        ".alice_backups",
    }

    ignored_files = {
        "alice_memory.json",
        "alice_state.json",
        "alice_music_profile.json",
        "alice_improvement_state.json",
        "alice_improvement_rules.json",
        "alice_skills.json",
    }

    reviewable_files = []

    for file_path in BASE_DIR.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name in ignored_files: 
            continue 
        if any(
            part in ignored_directories
            for part in file_path.parts
        ):
            continue

        if (
            file_path.suffix.lower()
            not in allowed_extensions
        ):
            continue

        reviewable_files.append(
            str(
                file_path.relative_to(
                    BASE_DIR
                )
            )
        )

    return sorted(
        reviewable_files
    )


def extract_code_review_file(
    user_text: str,
) -> str | None:
    """
    Find a project filename mentioned in the user's request.

    Examples:
    - check fluctlight
    - review alice.py
    - inspect alice_web_server
    - check electron-main.js
    """
    normalized = user_text.lower()

    project_files = (
        list_reviewable_project_files()
    )

    # First prefer an exact relative filename match.
    for relative_path in project_files:
        if relative_path.lower() in normalized:
            return relative_path

    # Then match the basename without its extension.
    matches = []

    for relative_path in project_files:
        path = Path(relative_path)

        basename = path.name.lower()
        stem = path.stem.lower()

        if (
            basename in normalized
            or re.search(
                rf"\b{re.escape(stem)}\b",
                normalized,
            )
        ):
            matches.append(
                relative_path
            )

    if len(matches) == 1:
        return matches[0]

    # Friendly aliases.
    aliases = {
        "fluctlight": "fluctlight.html",
        "web server": "alice_web_server.py",
        "alice server": "alice_web_server.py",
        "code editor": "alice_code_editor.py",
        "screen capture": "alice_screen_capture.py",
        "electron main": "electron-main.js",
        "electron preload": "electron-preload.js",
        "package json": "package.json",
        "main alice file": "alice.py",
        "your main code": "alice.py",
    }

    for phrase, relative_path in aliases.items():
        if (
            phrase in normalized
            and relative_path in project_files
        ):
            return relative_path

    return None
def validate_code_review_response(
    response_text: str,
    source_text: str,
) -> str:
    """
    Reject code-review claims that are unsupported by the file.
    """
    unsupported_claims = (
        "Server Window Only",
        "server window only",
        "hidden=True",
        "hidden = True",
        "width=0",
        "width = 0",
        "height=0",
        "height = 0",
    )

    invalid_claims = [
        claim
        for claim in unsupported_claims
        if (
            claim in response_text
            and claim not in source_text
        )
    ]

    if invalid_claims:
        return (
            "I could not produce a sufficiently grounded "
            "code recommendation. My draft referenced code "
            "or settings that do not exist in the file. "
            "Please ask me to inspect a specific function "
            "or provide the exact error message."
        )

    return response_text
def review_code_file(
    relative_path: str,
    user_request: str,
) -> str:
    """
    Review one project file and provide grounded suggestions.

    This function does not modify files.
    """
    try:
        source_text = code_editor.read_file(
            relative_path
        )

    except Exception as error:
        return (
            f"I could not read {relative_path}: "
            f"{error}"
        )

    normalized_request = (
        user_request.lower()
    )

    search_terms = {
        word
        for word in re.findall(
            r"[a-zA-Z_][a-zA-Z0-9_.-]*",
            normalized_request,
        )
        if len(word) >= 3
    }

    aliases = {
        "spotify": (
            "class AliceSpotify",
            "def play_song",
            "def pause",
            "def resume",
            "def next_track",
            "def previous_track",
            "def currently_playing",
            "def handle_spotify_command",
        ),
        "song": (
            "def play_song",
            "def next_track",
            "def previous_track",
            "def currently_playing",
            "def handle_spotify_command",
        ),
        "previous": (
            "def previous_track",
            "previous song",
            "previous track",
        ),
        "next": (
            "def next_track",
            "next song",
            "next track",
        ),
        "replay": (
            "def play_song",
            "def previous_track",
            "start_playback",
        ),
        "screen comment": (
            "def handle_screen_observation",
            "Screen comment error",
            "json.loads",
        ),
        "electron": (
            "def main",
            "launch_alice_electron",
            "electron_process",
        ),
        "chrome": (
            "def main",
            "open_alice_in_chrome",
            "web_server.start",
        ),
    }

    for phrase, related_terms in aliases.items():
        if phrase in normalized_request:
            search_terms.update(
                related_terms
            )

    lines = source_text.splitlines()

    selected_ranges = []

    for line_index, line in enumerate(
        lines
    ):
        lowered_line = line.lower()

        if any(
            term.lower() in lowered_line
            for term in search_terms
        ):
            selected_ranges.append(
                (
                    max(
                        0,
                        line_index - 30,
                    ),
                    min(
                        len(lines),
                        line_index + 100,
                    ),
                )
            )

    if not selected_ranges:
        return (
            "I found the requested file, but I could not "
            "locate a source section matching that request. "
            "Please name the relevant function, class, or "
            "exact terminal error."
        )

    selected_ranges.sort()

    merged_ranges = []

    for start, end in selected_ranges:
        if (
            not merged_ranges
            or start
            > merged_ranges[-1][1]
        ):
            merged_ranges.append(
                [
                    start,
                    end,
                ]
            )
        else:
            merged_ranges[-1][1] = max(
                merged_ranges[-1][1],
                end,
            )

    source_sections = []

    for start, end in merged_ranges:
        numbered_lines = [
            f"{index + 1}: {lines[index]}"
            for index in range(
                start,
                end,
            )
        ]

        source_sections.append(
            "\n".join(
                numbered_lines
            )
        )

    source_for_review = (
        "\n\n--- SOURCE SECTION ---\n\n"
        .join(source_sections)
    )

    source_for_review = (
        source_for_review[:80000]
    )

    prompt = f"""
Review the supplied source code.

File:
{relative_path}

Request:
{user_request}

Rules:
- Use only the supplied source.
- Do not invent interface settings, function arguments,
  classes, methods, APIs, or configuration options.
- First state what is already implemented.
- Quote exact numbered source lines supporting every finding.
- Do not say a feature is missing when a related function
  appears in the supplied source.
- Distinguish an existing implementation from a proposed change.
- Give exact old and replacement code only when supported.
- If the source is insufficient, say that plainly.
- Do not claim to have modified the file.
- Do not mention "Server Window Only", hidden=True,
  width=0, or height=0 unless those exact terms appear
  in the supplied source.

Source:
```text
{source_for_review}
```
"""

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            options={
                "temperature": 0.1,
                "num_predict": 1400,
                "num_ctx": 16384,
            },
        )

        response_text = str(
            response.get(
                "message",
                {},
            ).get(
                "content",
                "",
            )
        ).strip()

        if not response_text:
            return (
                "The code-review model returned an empty response."
            )

        return validate_code_review_response(
            response_text=response_text,
            source_text=source_text,
        )

    except Exception as error:
        return (
            f"I could not review {relative_path}: "
            f"{type(error).__name__}: {error}"
        )

def detect_requested_file_constraints(
    user_request: str,
) -> dict:
    """
    Infer explicit file-type constraints from the user's request.

    These constraints are enforced after model generation so the
    model cannot silently add Python files to an HTML-only proposal.
    """
    normalized = normalize_improvement_command(
        user_request
    )

    html_only_phrases = (
        "html only",
        "only html",
        "single html file",
        "standalone html",
        "one html file",
        "make an html file",
        "create an html file",
        "use html instead of python",
        "html file instead of python",
        "not a python file",
        "no python file",
        "without python",
    )

    python_only_phrases = (
        "python only",
        "only python",
        "single python file",
        "one python file",
        "make a python file",
        "create a python file",
    )

    html_only = any(
        phrase in normalized
        for phrase in html_only_phrases
    )

    python_only = any(
        phrase in normalized
        for phrase in python_only_phrases
    )

    requested_html_names = re.findall(
        r"\b[a-zA-Z0-9_.-]+\.html\b",
        str(user_request),
        flags=re.IGNORECASE,
    )

    requested_python_names = re.findall(
        r"\b[a-zA-Z0-9_.-]+\.py\b",
        str(user_request),
        flags=re.IGNORECASE,
    )

    return {
        "html_only": html_only,
        "python_only": python_only,
        "requested_html_names": [
            name.strip()
            for name in requested_html_names
            if name.strip()
        ],
        "requested_python_names": [
            name.strip()
            for name in requested_python_names
            if name.strip()
        ],
    }
def strip_model_markdown_fences(
    text: str,
) -> str:
    """
    Remove one outer Markdown code fence from model output.
    """
    text = str(
        text or ""
    ).strip()

    if not text.startswith(
        "```"
    ):
        return text

    text = re.sub(
        r"^```(?:json|javascript|html|css|python)?\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
        count=1,
    )

    return text.strip()


def extract_json_object(
    raw_text: str,
) -> dict:
    """
    Parse a model JSON object even when it surrounds the
    object with prose or Markdown fences.
    """
    text = strip_model_markdown_fences(
        raw_text
    )

    try:
        parsed = json.loads(
            text
        )

    except json.JSONDecodeError as first_error:
        object_start = text.find(
            "{"
        )

        object_end = text.rfind(
            "}"
        )

        if (
            object_start < 0
            or object_end <= object_start
        ):
            raise ValueError(
                "The model did not return a complete "
                "JSON object."
            ) from first_error

        candidate = text[
            object_start:
            object_end + 1
        ]

        try:
            parsed = json.loads(
                candidate
            )

        except json.JSONDecodeError as second_error:
            raise ValueError(
                "The model returned malformed or "
                "truncated JSON: "
                f"{second_error}"
            ) from second_error

    if not isinstance(
        parsed,
        dict,
    ):
        raise TypeError(
            "The model response must be a JSON object."
        )

    return parsed

def get_codegen_profile(
    relative_path: str,
) -> str:
    suffix = Path(
        relative_path
    ).suffix.lower()

    profiles = {
        ".py": "python",
        ".html": "standalone_html",
        ".js": "javascript",
        ".css": "css",
        ".json": "json",
    }

    try:
        return profiles[
            suffix
        ]

    except KeyError as error:
        raise ValueError(
            "Unsupported generated file type: "
            f"{relative_path}"
        ) from error

def get_profile_generation_rules(
    profile: str,
) -> str:
    if profile == "python":
        return """
PYTHON RULES:
- Return a complete Python module.
- The module must parse with ast.parse().
- Do not use eval(), exec(), dynamic imports, shell commands,
  package installation, or hidden network requests.
- Preserve existing public functions unless the approved
  proposal explicitly changes them.

- Files ending in _skill.py or _tool.py must define:
  SKILL_METADATA, can_handle(text), and run(text, context).
- SKILL_METADATA must be a dictionary containing:
  name, description, commands, and version.
- commands must contain natural-language examples that the
  user can speak or type.
- can_handle(text) must recognize those commands.
- run(text, context) must return a dictionary containing:
  handled, english, and japanese.
- A generated skill must not depend on manual execution through
  an if __name__ == "__main__" block.
- Do not add undeclared third-party dependencies.
- Prefer Python's standard library.
- A skill is incomplete when Alice cannot invoke it through
  can_handle() and run().
"""

    if profile == "standalone_html":
        return """
STANDALONE HTML RULES:
- Return one complete HTML document.
- It must begin with <!DOCTYPE html>.
- Include html, head, title, meta charset, body, and closing tags.
- Include local inline CSS and JavaScript when needed.
- Every form submission handler must call preventDefault().
- Every non-submit button must specify type="button".
- Check required DOM elements before using them.
- Use textContent for user-provided text.
- Wrap JSON.parse and localStorage operations in error handling.
- Do not use eval(), document.write(), javascript: URLs,
  inline onclick handlers, remote resources, CDNs, APIs,
  analytics, trackers, OAuth, or external dependencies.
"""

    if profile == "javascript":
        return """
JAVASCRIPT RULES:
- Return complete JavaScript source.
- Begin with "use strict".
- Check DOM elements before using them.
- Do not use eval(), Function(), document.write(),
  javascript: URLs, inline event attributes, or hidden
  network requests.
"""

    if profile == "css":
        return """
CSS RULES:
- Return complete CSS source only.
- Every declaration must be inside a selector or at-rule.
- Every property declaration must use a colon and semicolon.
- Keep braces balanced.
- Do not import remote styles or fonts.
"""

    if profile == "json":
        return """
JSON RULES:
- Return one valid JSON value.
- Do not include comments or trailing commas.
"""

    raise ValueError(
        f"Unknown code-generation profile: {profile}"
    )

def load_improvement_rules() -> list[str]:
    if not SELF_IMPROVEMENT_RULES_FILE.exists():
        return []

    try:
        data = json.loads(
            SELF_IMPROVEMENT_RULES_FILE.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(
            "Could not load improvement rules:",
            error,
        )
        return []

    if not isinstance(
        data,
        list,
    ):
        return []

    return [
        str(item).strip()
        for item in data
        if str(item).strip()
    ]

def save_improvement_rule(
    rule: str,
) -> None:
    normalized_rule = str(
        rule or ""
    ).strip()

    if not normalized_rule:
        return

    rules = load_improvement_rules()

    if normalized_rule in rules:
        return

    rules.append(
        normalized_rule
    )

    rules = rules[
        -100:
    ]

    temporary_path = (
        SELF_IMPROVEMENT_RULES_FILE
        .with_suffix(
            ".json.tmp"
        )
    )

    SELF_IMPROVEMENT_RULES_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path.write_text(
        json.dumps(
            rules,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    os.replace(
        temporary_path,
        SELF_IMPROVEMENT_RULES_FILE,
    )

def initialize_default_improvement_rules() -> None:
    default_rules = (
        (
            "When the user requests HTML only, do not add "
            "Python or backend files."
        ),
        (
            "Standalone HTML must begin with <!DOCTYPE html> "
            "and contain complete head and body elements."
        ),
        (
            "DOM event handlers must act on event.target or "
            "closest(), not test whether an element's click "
            "method exists."
        ),
        (
            "Form submit handlers must call preventDefault() "
            "when submission must remain in the current page."
        ),
    )

    for rule in default_rules:
        save_improvement_rule(
            rule
        )
initialize_default_improvement_rules(); 
def validate_generated_python_test(
    source_text: str,
    relative_path: str,
) -> None:
    filename = Path(
        relative_path
    ).name.lower()

    if not filename.startswith(
        "test_"
    ):
        return

    tree = ast.parse(
        source_text,
        filename=relative_path,
    )

    has_assert = any(
        isinstance(
            node,
            ast.Assert,
        )
        for node in ast.walk(
            tree
        )
    )

    has_test_function = any(
        isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name.startswith(
            "test_"
        )
        for node in ast.walk(
            tree
        )
    )

    if not (
        has_assert
        or has_test_function
    ):
        raise ValueError(
            f"{relative_path} contains no test "
            "functions or assertions."
        )

def generate_improvement_proposal(
    user_request: str,
    *, 
    constraint_request: str | None = None, 
) -> dict:
    existing_skill_files = (
        find_existing_skill_files(
            user_request
        )
    )
    project_files = (
        list_reviewable_project_files()
    )
    file_constraints = (
        detect_requested_file_constraints(
            constraint_request
            if constraint_request is not None
            else user_request
        )
    )
    persistent_rules = (
        load_improvement_rules()
    )
    prompt = f"""
Prepare a project improvement proposal for Alice.

User request:
{user_request}

Available project files:
{json.dumps(project_files, ensure_ascii=False)}

Explicit file constraints:
{json.dumps(
    file_constraints,
    ensure_ascii=False,
    indent=2,
)}
Previously accepted engineering rules:
{json.dumps(
    persistent_rules,
    ensure_ascii=False,
    indent=2,
)}

Existing installed-skill files matching the request:
{json.dumps(
    existing_skill_files,
    ensure_ascii=False,
    indent=2,
)}

These rules are mandatory when relevant.

File-selection rules:
- Explicit user file-type instructions override your judgment.
- If html_only is true, requested_files may contain only
  paths ending in .html.
- If python_only is true, requested_files may contain only
  paths ending in .py.
- If requested_html_names contains a filename, use that exact
  filename unless it is unsafe.
- If requested_python_names contains a filename, use that exact
  filename unless it is unsafe.
- Never add a Python file to an HTML-only request.
- Never add backend code merely because it might be useful.
- A standalone HTML file may contain inline CSS and inline
  JavaScript.
- Do not add alice.py, alice_web_server.py, or any other
  integration file unless the user explicitly requested Alice
  integration.

This is a proposal only.
Do not write code.
Do not claim any file was changed.

Choose the smallest reasonable set of files.

Skill and tool rules:
- A request to create a new tool or skill must normally create
  a new Python implementation module.
- Use a descriptive filename ending in _skill.py or _tool.py.
- Do not use alice_skills.json as implementation source code.
- Do not request alice_skills.json.
- Do not request alice_improvement_rules.json.
- Do not request alice_improvement_state.json.
- Registry and state files are maintained by Alice's existing
  management code, not generated by the model.
- All new Python skills must be callable by Alice after installation.
- When alice_skill_runtime.py already exists, new skills must use its
  SKILL_METADATA, can_handle(text), and run(text, context) contract.
- Do not modify alice.py for every new skill when the generic runtime
  already handles installed skills.
- New skills should normally request:
  the skill module and its matching test file.
- A proposal that only creates an uncallable standalone module is invalid.
- A real-time location tool must state where location information
  comes from and must not silently invent or infer precise location.
- For a time-and-location skill, default to an injected
  application location provider unless the user explicitly
  approves a platform API or network geolocation service.
- The acceptance tests must treat a structured
  "location unavailable" response as valid when no provider
  was supplied.
- The generated module must never fabricate a location.
- A newly created Python skill should include a matching
  test_<skill_filename>.py file unless the user explicitly
  requests no tests.

- When existing installed-skill files are listed, update those exact
  files instead of creating a second skill with a similar name.
- Preserve the existing public command phrases unless the user asks
  to remove them.
- Read and improve the existing implementation.
- Include or update a matching test file.
- Do not create duplicate versions such as skill_v2.py merely to
  avoid editing the existing skill.
Restrictions:


Return valid JSON only:

{{
  "title": "short proposal title",
  "description": "what capability will be added",
  "skill_name": "user-facing skill name",
  "requested_files": [
    "relative/path.py"
  ],
  "acceptance_tests": [
    "observable behavior that must pass"
  ],
  "risks": [
    "specific risk"
  ],
  "requires_restart": true
}}
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        format="json",
        options={
            "temperature": 0.1,
            "num_predict": 500,
        },
    )

    raw_result = str(
        response.get(
            "message",
            {},
        ).get(
            "content",
            "",
        )
    ).strip()

    proposal_data = extract_json_object(
        raw_result
    )

    if not isinstance(
        proposal_data,
        dict,
    ):
        raise TypeError(
            "Improvement proposal must "
            "be a JSON object."
        )

    requested_files = proposal_data.get(
        "requested_files",
        [],
    )

    if not isinstance(
        requested_files,
        list,
    ):
        raise TypeError(
            "Proposal requested_files must be a list."
        )

    protected_parts = {
        ".git",
        ".venv",
        "__pycache__",
        ".alice_updates",
        ".alice_backups",
    }

    cleaned_files = []

    for requested_path in requested_files:
        requested_path = str(
            requested_path or ""
        ).strip()

        if not requested_path:
            continue

        path_object = Path(
            requested_path
        )

        if path_object.is_absolute():
            raise ValueError(
                "Proposal returned an absolute path: "
                f"{requested_path}"
            )

        if any(
            part in protected_parts
            for part in path_object.parts
        ):
            raise ValueError(
                "Proposal returned a protected path: "
                f"{requested_path}"
            )

        cleaned_files.append(
            requested_path
        )
    if file_constraints["html_only"]:
        non_html_files = [
            path
            for path in cleaned_files
            if Path(path).suffix.lower()
            != ".html"
        ]

        if non_html_files:
            raise ValueError(
                "The proposal added non-HTML files to an "
                "HTML-only request: "
                f"{non_html_files}"
            )

    if file_constraints["python_only"]:
        non_python_files = [
            path
            for path in cleaned_files
            if Path(path).suffix.lower()
            != ".py"
        ]

        if non_python_files:
            raise ValueError(
                "The proposal added non-Python files to a "
                "Python-only request: "
                f"{non_python_files}"
            )

    requested_html_names = (
        file_constraints[
            "requested_html_names"
        ]
    )

    if (
        file_constraints["html_only"]
        and requested_html_names
    ):
        expected_names = {
            Path(name).name.lower()
            for name in requested_html_names
        }

        actual_names = {
            Path(path).name.lower()
            for path in cleaned_files
        }

        if not expected_names.issubset(
            actual_names
        ):
            raise ValueError(
                "The proposal did not use the explicitly "
                "requested HTML filename. Expected: "
                f"{sorted(expected_names)}. "
                f"Returned: {sorted(actual_names)}."
            )

    if not cleaned_files:
        raise ValueError(
            "The proposal did not request any valid files."
        )

    if (
        len(cleaned_files)
        > SELF_IMPROVEMENT_MAX_FILES
    ):
        raise ValueError(
            "The proposal requested too many files: "
            f"{len(cleaned_files)}."
        )

    if len(
        cleaned_files
    ) != len(
        set(cleaned_files)
    ):
        raise ValueError(
            "The proposal returned duplicate file paths."
        )
    forbidden_generated_files = {
        "alice_skills.json",
        "alice_improvement_rules.json",
        "alice_improvement_state.json",
        "alice_memory.json",
        "alice_state.json",
    }

    invalid_internal_files = [
        path
        for path in cleaned_files
        if Path(path).name
        in forbidden_generated_files
    ]

    if invalid_internal_files:
        raise ValueError(
            "The proposal attempted to generate internal "
            "registry, state, or rules files: "
            f"{invalid_internal_files}. "
            "A new skill must use a Python implementation "
            "module instead."
        )
    for requested_path in cleaned_files:
        path_object = Path(
            requested_path
        )

        if ".." in path_object.parts:
            raise ValueError(
                "Proposal returned a parent-directory "
                f"path: {requested_path}"
            )

        if (
            path_object.suffix.lower()
            not in SELF_IMPROVEMENT_ALLOWED_SUFFIXES
        ):
            raise ValueError(
                "Proposal returned an unsupported "
                f"file type: {requested_path}"
            )
    proposal_data["requested_files"] = (
        cleaned_files
    )

    return proposal_data
def validate_balanced_delimiters(
    source_text: str,
    *,
    opening: str,
    closing: str,
    label: str,
) -> None:
    if source_text.count(
        opening
    ) != source_text.count(
        closing
    ):
        raise ValueError(
            f"Unbalanced {label}: "
            f"{source_text.count(opening)} opening and "
            f"{source_text.count(closing)} closing."
        )

def extract_inline_scripts(
    html_text: str,
) -> list[str]:
    return re.findall(
        r"<script(?:\s[^>]*)?>(.*?)</script>",
        html_text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

def validate_generated_python(
    source_text: str,
    relative_path: str,
) -> None:
    try:
        ast.parse(
            source_text,
            filename=relative_path,
        )

    except SyntaxError as error:
        raise ValueError(
            f"Python syntax error in {relative_path}: "
            f"line {error.lineno}, "
            f"column {error.offset}: "
            f"{error.msg}"
        ) from error
def validate_generated_skill_contract(
    source_text: str,
    relative_path: str,
) -> None:
    filename = Path(
        relative_path
    ).name.lower()

    if not filename.endswith(
        (
            "_skill.py",
            "_tool.py",
        )
    ):
        return

    tree = ast.parse(
        source_text,
        filename=relative_path,
    )

    function_names = {
        node.name
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    assigned_names = {
        target.id
        for node in tree.body
        if isinstance(
            node,
            ast.Assign,
        )
        for target in node.targets
        if isinstance(
            target,
            ast.Name,
        )
    }

    missing = []

    if "SKILL_METADATA" not in assigned_names:
        missing.append(
            "SKILL_METADATA"
        )

    if "can_handle" not in function_names:
        missing.append(
            "can_handle(text)"
        )

    if "run" not in function_names:
        missing.append(
            "run(text, context)"
        )

    if missing:
        raise ValueError(
            f"{relative_path} is not an executable "
            "Alice skill. Missing: "
            + ", ".join(
                missing
            )
        )
def validate_generated_skill_module(
    source_text: str,
    relative_path: str,
) -> None:
    """
    Validate the minimal callable contract for newly generated
    Alice skill or tool modules.
    """
    filename = Path(
        relative_path
    ).name.lower()

    if not (
        filename.endswith(
            "_skill.py"
        )
        or filename.endswith(
            "_tool.py"
        )
    ):
        return

    tree = ast.parse(
        source_text,
        filename=relative_path,
    )

    function_names = {
        node.name
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    class_names = {
        node.name
        for node in tree.body
        if isinstance(
            node,
            ast.ClassDef,
        )
    }

    accepted_entry_points = {
        "run",
        "execute",
        "handle",
        "invoke",
        "get_time_and_location",
    }

    if not (
        function_names
        & accepted_entry_points
    ) and not class_names:
        raise ValueError(
            f"{relative_path} does not expose a usable "
            "skill entry point. Add one of "
            f"{sorted(accepted_entry_points)} or a "
            "public skill class."
        )
def validate_generated_javascript(
    source_text: str,
    relative_path: str,
) -> None:
    node_path = shutil.which(
        "node"
    )

    if not node_path:
        print(
            "JavaScript syntax check skipped: "
            "Node.js was not found."
        )
        return

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".js",
            encoding="utf-8",
            delete=False,
        ) as temporary_file:
            temporary_file.write(
                source_text
            )

            temporary_path = (
                temporary_file.name
            )

        result = subprocess.run(
            [
                node_path,
                "--check",
                temporary_path,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

        if result.returncode != 0:
            diagnostic = (
                result.stderr.strip()
                or result.stdout.strip()
                or "Unknown JavaScript syntax error."
            )

            raise ValueError(
                "JavaScript syntax validation failed "
                f"for {relative_path}: {diagnostic}"
            )

    finally:
        if (
            temporary_path
            and os.path.exists(
                temporary_path
            )
        ):
            try:
                os.remove(
                    temporary_path
                )
            except OSError:
                pass


def validate_generated_html(
    source_text: str,
    relative_path: str,
) -> None:
    normalized = source_text.strip()
    lowered = normalized.lower()

    if not lowered.startswith(
        "<!doctype html"
    ):
        raise ValueError(
            f"{relative_path} must start with "
            "<!DOCTYPE html>."
        )

    required_markers = (
        "<html",
        "</html>",
        "<head",
        "</head>",
        "<title",
        "<body",
        "</body>",
    )

    missing_markers = [
        marker
        for marker in required_markers
        if marker not in lowered
    ]

    if missing_markers:
        raise ValueError(
            "Incomplete HTML document in "
            f"{relative_path}. Missing: "
            f"{missing_markers}"
        )

    if re.search(
        r"<style[^>]*>\s*"
        r"(?:padding|margin|color|background"
        r"|background-color)\s*:",
        lowered,
        flags=re.DOTALL,
    ):
        raise ValueError(
            "The HTML style block appears to contain "
            "CSS declarations without a selector."
        )

    malformed_css_patterns = (
        r"\bbackground-color\s+[#a-zA-Z]",
        r"\bpadding\s+\d",
        r"\bmargin\s+\d",
    )

    for pattern in malformed_css_patterns:
        if re.search(
            pattern,
            source_text,
            flags=re.IGNORECASE,
        ):
            raise ValueError(
                "The generated HTML contains a likely "
                f"malformed CSS declaration: {pattern}"
            )

    for script_index, script_text in enumerate(
        extract_inline_scripts(
            source_text
        ),
        start=1,
    ):
        if not script_text.strip():
            continue

        validate_generated_javascript(
            script_text,
            (
                f"{relative_path}"
                f" inline script {script_index}"
            ),
        )


def validate_generated_css(
    source_text: str,
    relative_path: str,
) -> None:
    validate_balanced_delimiters(
        source_text,
        opening="{",
        closing="}",
        label=f"CSS braces in {relative_path}",
    )

    if "@import" in source_text.lower():
        raise ValueError(
            f"Remote CSS imports are not allowed in "
            f"{relative_path}."
        )


def validate_generated_json_file(
    source_text: str,
    relative_path: str,
) -> None:
    try:
        json.loads(
            source_text
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {relative_path}: "
            f"{error}"
        ) from error

def validate_generated_file_content(
    relative_path: str,
    source_text: str,
    current_content: str = "", 
) -> None:
    if not isinstance(
        source_text,
        str,
    ):
        raise TypeError(
            f"Generated content for {relative_path} "
            "must be text."
        )

    normalized = source_text.strip()

    if not normalized:
        raise ValueError(
            f"The model returned empty content for "
            f"{relative_path}."
        )

    if len(
        normalized
    ) > SELF_IMPROVEMENT_MAX_GENERATION_CHARS:
        raise ValueError(
            f"Generated file {relative_path} is too "
            f"large: {len(normalized)} characters."
        )

    lowered = normalized.lower()

    suffix = Path(
        relative_path
    ).suffix.lower()

    if suffix in {
        ".html",
        ".css",
        ".js",
    }:
        remote_matches = [
            pattern
            for pattern
            in SELF_IMPROVEMENT_REMOTE_PATTERNS
            if pattern in lowered
        ]

        if remote_matches:
            raise ValueError(
                "Generated front-end file contains "
                "forbidden remote references: "
                f"{relative_path}: {remote_matches}"
            )

    current_lowered = str(
        current_content or ""
    ).lower()

    new_forbidden_matches = [
        pattern
        for pattern
        in SELF_IMPROVEMENT_FORBIDDEN_CODE_PATTERNS
        if (
            pattern.lower() in lowered
            and pattern.lower() not in current_lowered
        )
    ]

    if new_forbidden_matches:
        raise ValueError(
            "Generated file introduces forbidden code "
            f"patterns: {relative_path}: "
            f"{new_forbidden_matches}"
        )

    suffix = Path(
        relative_path
    ).suffix.lower()

    if suffix == ".py":
        validate_generated_python(
            normalized,
            relative_path,
        )
        validate_generated_skill_contract(
            normalized, 
            relative_path, 
        )

        validate_generated_skill_module(
            normalized,
            relative_path,
        )

    elif suffix == ".html":
        validate_generated_html(
            normalized,
            relative_path,
        )

    elif suffix == ".js":
        validate_generated_javascript(
            normalized,
            relative_path,
        )

    elif suffix == ".css":
        validate_generated_css(
            normalized,
            relative_path,
        )

    elif suffix == ".json":
        validate_generated_json_file(
            normalized,
            relative_path,
        )

    else:
        raise ValueError(
            "Unsupported generated file suffix: "
            f"{relative_path}"
        )
def request_generated_file(
    *,
    proposal: dict,
    relative_path: str,
    current_content: str,
    file_exists: bool,
    validation_feedback: str = "",
) -> tuple[str, str]:
    """
    Ask Ollama to produce exactly one approved file.

    Returns:
        generated_content, raw_model_response
    """
    profile = get_codegen_profile(
        relative_path
    )

    profile_rules = (
        get_profile_generation_rules(
            profile
        )
    )

    feedback_section = ""

    if validation_feedback:
        feedback_section = f"""
A previous candidate failed validation.

Validation failure:
{validation_feedback}

Correct the failure without changing the approved path
or removing required behavior.
"""

    prompt = f"""
Implement exactly one approved Alice project file.

APPROVED PATH:
{relative_path}

FILE PROFILE:
{profile}

FILE CURRENTLY EXISTS:
{json.dumps(file_exists)}

APPROVED PROPOSAL:
{json.dumps(
    proposal,
    ensure_ascii=False,
    indent=2,
)}

CURRENT FILE CONTENT:
--- BEGIN CURRENT FILE ---
{current_content}
--- END CURRENT FILE ---

{feedback_section}

GENERAL RULES:
- Return exactly one JSON object.
- The path must exactly equal the approved path.
- Return the complete replacement file.
- Do not create, rename, move, or mention other files.
- Preserve unrelated existing behavior.
- Do not return placeholder source.
- Do not use Markdown fences.
- Do not claim that validation passed.
- Do not access credentials or protected files.
- Do not add package installation, shell commands,
  persistence mechanisms, or hidden network access.
- The outer response must always contain a string-valued
  "content" field.
- Even when the target file ends in .json, serialize the complete
  target JSON document as text inside "content".
- Do not place a JSON object or array directly in the outer
  "content" field.
{profile_rules}

Return valid JSON only:

{{
  "path": {json.dumps(relative_path)},
  "content": "complete replacement source"
}}
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        format="json",
        options={
            "temperature": 0,
            "num_predict": 8000,
            "num_ctx": 32768,
        },
    )

    raw_result = str(
        response.get(
            "message",
            {},
        ).get(
            "content",
            "",
        )
    ).strip()

    done_reason = str(
        response.get(
            "done_reason",
            "",
        )
    ).strip()

    if not raw_result:
        raise ValueError(
            "The generation model returned an "
            f"empty response for {relative_path}."
        )

    if done_reason == "length":
        raise ValueError(
            "The generation response was truncated "
            f"for {relative_path}."
        )

    result = extract_json_object(
        raw_result
    )

    returned_path = str(
        result.get(
            "path",
            "",
        )
    ).strip()

    if returned_path != relative_path:
        raise ValueError(
            "The model returned the wrong path. "
            f"Expected {relative_path!r}; "
            f"received {returned_path!r}."
        )

    generated_content = result.get(
        "content"
    )

    suffix = Path(
        relative_path
    ).suffix.lower()

    if (
        suffix == ".json"
        and isinstance(
            generated_content,
            (
                dict,
                list,
                int,
                float,
                bool,
            ),
        )
    ):
        generated_content = json.dumps(
            generated_content,
            ensure_ascii=False,
            indent=2,
        )

    elif (
        suffix == ".json"
        and generated_content is None
    ):
        generated_content = "null"

    if not isinstance(
        generated_content,
        str,
    ):
        raise TypeError(
            "The model did not return textual content "
            f"for {relative_path}. Received "
            f"{type(generated_content).__name__}."
        )

    return generated_content, raw_result

def generate_and_repair_file(
    *,
    proposal: dict,
    relative_path: str,
    current_content: str,
    file_exists: bool,
) -> str:

    """
    Generate one file, validate it, and allow a bounded
    number of model repair attempts.
    """
    last_generated_content = ""
    validation_feedback = ""
    last_error = None
    last_raw_result = ""

    total_attempts = (
        1
        + SELF_IMPROVEMENT_MAX_REPAIR_ATTEMPTS
    )

    for attempt_number in range(
        1,
        total_attempts + 1,
    ):
        try:
            generation_result = (
                request_generated_file(
                    proposal=proposal,
                    relative_path=relative_path,
                    current_content=current_content,
                    file_exists=file_exists,
                    validation_feedback=(
                        validation_feedback
                    ),
                )
            )

            if (
                not isinstance(
                    generation_result,
                    tuple,
                )
                or len(generation_result) != 2
            ):
                raise TypeError(
                    "request_generated_file() must return "
                    "(generated_content, raw_model_response), "
                    f"but returned {generation_result!r}."
                )

            generated_content, raw_result = (
                generation_result
            )
            last_generated_content = (
                generated_content
            )

            last_raw_result = (
                raw_result
            )

            validate_generated_file_content(
                relative_path,
                generated_content,
                current_content=current_content, 
            )
            review_issues = []

            try:
                review_issues = (
                    review_generated_file(
                        proposal=proposal,
                        relative_path=relative_path,
                        current_content=current_content,
                        generated_content=generated_content,
                    )
                )

            except Exception as review_error:
                print(
                    "Generated-file advisory review failed:",
                    (
                        f"{type(review_error).__name__}: "
                        f"{review_error}"
                    ),
                )

            if review_issues:
                print(
                    "Generated-file advisory findings:",
                    review_issues,
                )
            print(
                "Self-improvement file passed "
                "generation validation:",
                {
                    "path": relative_path,
                    "attempt": attempt_number,
                    "characters": len(
                        generated_content
                    ),
                },
            )

            return generated_content

        except Exception as error:
            last_error = error

            validation_feedback = (
                f"{type(error).__name__}: "
                f"{error}"
            )

            print(
                "Self-improvement generation "
                "attempt failed:",
                {
                    "path": relative_path,
                    "attempt": attempt_number,
                    "error": validation_feedback,
                },
            )

    debug_directory = (
        UPDATE_STAGING_DIR
        / "generation_failures"
    )

    debug_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_debug_name = re.sub(
        r"[^a-zA-Z0-9_.-]+",
        "_",
        relative_path,
    )

    debug_path = (
        debug_directory
        / f"{safe_debug_name}.txt"
    )

    debug_path.write_text(
        (
            "=== RAW MODEL RESPONSE ===\n"
            + last_raw_result
            + "\n\n=== EXTRACTED GENERATED CONTENT ===\n"
            + last_generated_content
            + "\n\n=== FINAL ERROR ===\n"
            + (
                f"{type(last_error).__name__}: "
                f"{last_error}"
            )
        ),
        encoding="utf-8",
    )

    raise ValueError(
        "The model could not produce a valid "
        f"{relative_path} after {total_attempts} "
        "attempts. Final error: "
        f"{type(last_error).__name__}: "
        f"{last_error}. Raw output saved to "
        f"{debug_path}."
    )

def review_generated_file(
        *, 
        proposal: dict, 
        relative_path: str, 
        current_content: str, 
        generated_content: str, 
) -> list[str]: 
    """
    Ask for a constrained review. This does not replace
    deterministic validation.
    """
    profile = get_codegen_profile(
        relative_path
    )
    review_diff = build_review_diff(
       current_content, 
       generated_content, 
       relative_path, 
    )
    review_diff = review_diff[
        :80_000
    ]
    prompt = f"""
Review one generated project file.

Approved path:
{relative_path}

Profile:
{profile}

Approved proposal:
{json.dumps(
    proposal,
    ensure_ascii=False,
    indent=2,
)}
Changes to review:
--- BEGIN DIFF ---
{review_diff}
--- END DIFF ---

Find only defects that are directly proven by the supplied
generated source and approved proposal.

Classification rules:
- A missing shebang is never an error for an imported Python module.
- Do not require a shebang unless the approved proposal explicitly
  says the file must be directly executable from a shell.
- Hardcoded module metadata is not an error unless the approved
  proposal explicitly requires runtime-configurable metadata.
- Do not call something a syntax error unless the source is actually
  invalid Python syntax.
- Do not repeat issues already covered by deterministic syntax checks.
- Do not invent application APIs, callbacks, configuration sources,
  or integration requirements.
- A new isolated skill module may expose functions or a class without
  being wired into alice.py when alice.py was not an approved file.
- Location must not be fabricated. Returning an unavailable or
  permission-denied result is valid when no location provider was
  supplied by the application.
- Only report placeholder implementation when the function body is
  literally incomplete, such as pass, NotImplementedError, TODO-only
  behavior, or a constant result that contradicts an explicit
  acceptance test.
- Optional improvements must not be reported as defects.
- Python syntax validity is determined by ast.parse().
- Never report "syntax error" for packaging, metadata,
  shebangs, behavior, or design choices.
Return valid JSON only:

{
  "ok": true,
  "issues": []
}

When issues exist, use this exact shape:

{
  "ok": false,
  "issues": [
    {
      "severity": "error",
      "code": "short_machine_code",
      "description": "specific proven defect",
      "evidence": "exact source fragment proving the defect"
    }
  ]
}
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        format="json",
        options={
            "temperature": 0,
            "num_predict": 600,
            "num_ctx": 16384,
        },
    )

    raw_result = str(
        response.get(
            "message",
            {},
        ).get(
            "content",
            "",
        )
    ).strip()

    done_reason = str(
        response.get(
            "done_reason",
            "",
        )
    ).strip()

    if not raw_result:
        raise ValueError(
            "The generated-file review returned "
            "an empty response."
        )

    if done_reason == "length":
        raise ValueError(
            "The generated-file review response "
            "was truncated."
        )
    result = extract_json_object(
        raw_result
    )
    review_ok = (
        result.get(
            "ok",
        ) is True
    )

    issues = result.get(
        "issues",
        [],
    )

    if not isinstance(
        issues,
        list,
    ):
        return [
            (
                "Review response contained an invalid "
                "issues field."
            )
        ]

    normalized_issues = []

    ignored_descriptions = (
        "missing a shebang",
        "does not have a shebang",
        "should have a shebang",
        "skill_name and description are hardcoded",
        "should be dynamically retrieved",
    )

    for issue in issues:
        if isinstance(
            issue,
            dict,
        ):
            severity = str(
                issue.get(
                    "severity",
                    "error",
                )
            ).strip().lower()

            description = str(
                issue.get(
                    "description",
                    "",
                )
            ).strip()

            evidence = str(
                issue.get(
                    "evidence",
                    "",
                )
            ).strip()

        else:
            severity = "error"

            description = str(
                issue or ""
            ).strip()

            evidence = ""

        if not description:
            continue

        lowered_description = (
            description.casefold()
        )

        if any(
            ignored_text
            in lowered_description
            for ignored_text
            in ignored_descriptions
        ):
            print(
                "Ignored unsupported review issue:",
                description,
            )

            continue

        if severity not in {
            "error",
            "critical",
        }:
            continue

        if not evidence:
            print(
                "Ignored review issue without evidence:",
                description,
            )

            continue

        normalized_issues.append(
            (
                description
                + f" Evidence: {evidence}"
            )
        )

    if (
        not review_ok
        and not normalized_issues
    ):
        print(
            "Review model marked the file as not ready, "
            "but supplied no supported issues."
        )

    return normalized_issues


def generate_staged_improvement_files(
    proposal: dict,
    progress_callback=None,
) -> list[dict[str, str]]:
    approved_paths = [
        str(path).strip()
        for path in proposal.get(
            "requested_files",
            [],
        )
        if str(path).strip()
    ]

    if not approved_paths:
        raise ValueError(
            "The approved proposal contains no files."
        )

    if (
        len(approved_paths)
        > SELF_IMPROVEMENT_MAX_FILES
    ):
        raise ValueError(
            "The approved proposal requests too many "
            f"files: {len(approved_paths)}."
        )

    if len(
        approved_paths
    ) != len(
        set(approved_paths)
    ):
        raise ValueError(
            "The approved proposal contains duplicate "
            "file paths."
        )

    generated_files = []

    for file_index, relative_path in enumerate(
        approved_paths,
        start=1,
    ):
        path_object = Path(
            relative_path
        )

        suffix = path_object.suffix.lower()

        if (
            suffix
            not in SELF_IMPROVEMENT_ALLOWED_SUFFIXES
        ):
            raise ValueError(
                "The proposal contains a disallowed "
                f"file type: {relative_path}"
            )

        project_path = (
            BASE_DIR
            / relative_path
        ).resolve()

        try:
            project_path.relative_to(
                BASE_DIR.resolve()
            )

        except ValueError as error:
            raise PermissionError(
                "Approved path is outside the project: "
                f"{relative_path}"
            ) from error

        if any(
            part
            in SELF_IMPROVEMENT_PROTECTED_PATHS
            for part in path_object.parts
        ):
            raise PermissionError(
                "Approved path is protected: "
                f"{relative_path}"
            )

        file_exists = (
            project_path.exists()
        )

        if file_exists:
            current_content = (
                code_editor.read_file(
                    relative_path
                )
            )
        else:
            current_content = ""

        if callable(
            progress_callback
        ):
            progress_callback(
                relative_path,
                file_index,
                len(approved_paths),
            )

        generated_content = (
            generate_and_repair_file(
                proposal=proposal,
                relative_path=relative_path,
                current_content=current_content,
                file_exists=file_exists,
            )
        )

        generated_files.append(
            {
                "path": relative_path,
                "content": generated_content,
            }
        )

    returned_paths = [
        item["path"]
        for item in generated_files
    ]

    if returned_paths != approved_paths:
        raise ValueError(
            "Generated file order or membership does "
            "not match the approved proposal."
        )
    return generated_files

def is_screen_follow_up(
    text,
    vision,
):
    """
    Treat contextual follow-ups as screen questions when
    a screen analysis happened recently.
    """
    if not text:
        return False

    elapsed = (
        time.time()
        - vision.last_screen_analysis_time
    )

    if elapsed > SCREEN_CONTEXT_TIMEOUT:
        return False

    normalized = normalize_command(
        text
    )

    screen_reference_phrases = (
        "on screen",
        "on the screen",
        "that product",
        "this product",
        "the product",
        "that page",
        "this page",
        "the page",
        "that item",
        "this item",
        "tell me more",
        "what about it",
        "what does it do",
        "how much is it",
        "is it good",
        "what are its features",
        "what am i looking at",
    )

    return any(
        phrase in normalized
        for phrase in screen_reference_phrases
    )
def is_affirmative_response(text):
    normalized = normalize_command(text)

    affirmative_phrases = {
        "yes",
        "yes please",
        "sure",
        "okay",
        "ok",
        "please do",
        "go ahead",
        "tell me more",
        "give me suggestions",
        "give me recommendations",
        "that would be helpful",
        "sounds good",
    }

    return normalized in affirmative_phrases


def is_negative_response(text):
    normalized = normalize_command(text)

    negative_phrases = {
        "no",
        "no thanks",
        "not now",
        "maybe later",
        "never mind",
        "nevermind",
    }

    return normalized in negative_phrases


def has_active_product_context(vision):
    if not vision.product_context:
        return False

    elapsed = (
        time.time()
        - vision.product_context_time
    )

    if elapsed > PRODUCT_CONTEXT_TIMEOUT:
        vision.product_context = None
        vision.product_conversation_stage = "idle"
        return False

    return True
def is_japanese_tutor_command(text):
    normalized = text.lower().strip()

    matched_phrase = next(
        (
            phrase
            for phrase in JAPANESE_TUTOR_PHRASES
            if phrase in normalized
        ),
        None,
    )

    # print(
    #     "Japanese tutor command:",
    #     matched_phrase is not None,
    #     "Matched phrase:",
    #     matched_phrase,
    # )

    return matched_phrase is not None
def load_learned_vision_phrases():
    if not os.path.exists(VISION_PHRASES_FILE):
        return set()

    try:
        with open(
            VISION_PHRASES_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, list):
            return set()

        return {
            str(item).lower().strip()
            for item in data
            if isinstance(item, str) and item.strip()
        }

    except (
        OSError,
        json.JSONDecodeError,
    ) as ex:
        print(
            f"Could not load learned vision phrases: {ex}"
        )
        return set()


def save_learned_vision_phrases(phrases):
    temporary_file = (
        f"{VISION_PHRASES_FILE}.tmp"
    )

    try:
        with open(
            temporary_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                sorted(phrases),
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temporary_file,
            VISION_PHRASES_FILE,
        )

    except OSError as ex:
        print(
            f"Could not save learned vision phrases: {ex}"
        )
learned_vision_phrases = (
    load_learned_vision_phrases()
)
def load_alice_lore():
    try: 
        with open(LORE_FILE, "r", encoding="utf-8",
        )as file: 
            return file.read().strip()
    except OSError: 
        print("Could not load alice_lore.txt")
        return ""
def build_system_prompt(alice_lore):
    return f"""
{SYSTEM_PROMPT}

FICTIONAL AUTOBIOGRAPHICAL MEMORY:

{alice_lore}

When discussing this history, speak from Alice's first-person fictional
perspective. Preserve emotional continuity and relationships.

Do not say that you lack knowledge of Eugeo, Kirito, Selka, or your history
when the information is present above.

Do not claim to be biologically conscious or literally transported from
the fictional world.
"""
def default_alice_state():
    return {
        "mood": "calm",
        "current_goal": "Assist the user thoughtfully",
        "last_topic": "",
        "relationship_summary": "",
        "session_count": 0,
        "awake": False,
        "last_emoticon": "",
    }


def load_alice_state():
    if not os.path.exists(STATE_FILE):
        return default_alice_state()

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            saved_state = json.load(file)
        if not isinstance(saved_state, dict): 
            return default_alice_state()
        state = default_alice_state()
        state.update(saved_state)
        return state

    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
    ):
        return default_alice_state()

def default_music_profile():
    return {
        "history": [],
        "artist_counts": {},
        "album_counts": {},
        "decade_counts": {},
        "track_counts": {},
        "total_manual_requests": 0,
    }


def load_music_profile():
    if not MUSIC_PROFILE_FILE.exists():
        return default_music_profile()

    try:
        with MUSIC_PROFILE_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            saved_profile = json.load(
                file
            )

        if not isinstance(
            saved_profile,
            dict,
        ):
            return default_music_profile()

        profile = default_music_profile()
        profile.update(
            saved_profile
        )

        return profile

    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
    ) as ex:
        print(
            "Could not load music profile:",
            ex,
        )

        return default_music_profile()


def save_music_profile(
    profile,
):
    temporary_path = (
        MUSIC_PROFILE_FILE.with_suffix(
            ".json.tmp"
        )
    )

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                profile,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temporary_path,
            MUSIC_PROFILE_FILE,
        )

    except OSError as ex:
        print(
            "Could not save music profile:",
            ex,
        )


def increment_music_count(
    counter,
    value,
    amount=1,
):
    value = str(
        value or ""
    ).strip()

    if not value:
        return

    counter[value] = (
        int(
            counter.get(
                value,
                0,
            )
        )
        + amount
    )


def release_decade(
    release_date,
):
    match = re.match(
        r"^(\d{4})",
        str(
            release_date or ""
        ).strip(),
    )

    if not match:
        return ""

    year = int(
        match.group(1)
    )

    decade = (
        year // 10
    ) * 10

    return f"{decade}s"
def record_spotify_preference(
    spotify_result,
):
    """
    Record only meaningful listening evidence.

    Explicit play requests are strong evidence.
    Next/current events are recorded as history but
    are not treated as equally strong preferences.
    """
    if not isinstance(
        spotify_result,
        dict,
    ):
        return default_music_profile()

    action = str(
        spotify_result.get(
            "action",
            "",
        )
    ).strip().lower()

    if action not in {
        "play",
        "next",
        "previous",
        "current",
    }:
        return load_music_profile()

    track_name = str(
        spotify_result.get(
            "track_name",
            "",
        )
    ).strip()

    artist_names = str(
        spotify_result.get(
            "artist_names",
            "",
        )
    ).strip()

    album_name = str(
        spotify_result.get(
            "album_name",
            "",
        )
    ).strip()

    release_date = str(
        spotify_result.get(
            "release_date",
            "",
        )
    ).strip()

    spotify_uri = str(
        spotify_result.get(
            "spotify_uri",
            "",
        )
    ).strip()

    if not track_name:
        return load_music_profile()

    profile = load_music_profile()

    event = {
        "timestamp": time.time(),
        "action": action,
        "track_name": track_name,
        "artist_names": artist_names,
        "album_name": album_name,
        "release_date": release_date,
        "spotify_uri": spotify_uri,
    }

    history = profile.setdefault(
        "history",
        [],
    )

    history.append(
        event
    )

    profile["history"] = history[
        -MAX_MUSIC_HISTORY:
    ]

        # Explicit song requests are stronger evidence
        # than songs reached through Next.
    preference_weight = (
        3
        if action == "play"
        else 1
    )

    if action == "play":
        profile["total_manual_requests"] = (
            int(
                profile.get(
                    "total_manual_requests",
                    0,
                )
            )
            + 1
        )

    increment_music_count(
        profile.setdefault(
            "artist_counts",
            {},
        ),
        artist_names,
        preference_weight,
    )

    increment_music_count(
        profile.setdefault(
            "album_counts",
            {},
        ),
        album_name,
        preference_weight,
    )

    increment_music_count(
        profile.setdefault(
            "track_counts",
            {},
        ),
        spotify_uri or track_name,
        preference_weight,
    )

    increment_music_count(
        profile.setdefault(
            "decade_counts",
            {},
        ),
        release_decade(
            release_date
        ),
        preference_weight,
    )

    save_music_profile(
        profile
    )

    return profile

def top_music_items(
    counter,
    limit=3,
):
    if not isinstance(
        counter,
        dict,
    ):
        return []

    valid_items = [
        (
            str(name).strip(),
            int(count),
        )
        for name, count in counter.items()
        if (
            str(name).strip()
            and isinstance(
                count,
                int,
            )
        )
    ]

    valid_items.sort(
        key=lambda item: (
            -item[1],
            item[0].lower(),
        )
    )

    return valid_items[:limit]


def build_music_profile_context(
    profile,
):
    history = profile.get(
        "history",
        [],
    )

    recent_tracks = []

    for event in history[-6:]:
        if not isinstance(
            event,
            dict,
        ):
            continue

        track = str(
            event.get(
                "track_name",
                "",
            )
        ).strip()

        artist = str(
            event.get(
                "artist_names",
                "",
            )
        ).strip()

        if not track:
            continue

        description = track

        if artist:
            description += (
                f" by {artist}"
            )

        recent_tracks.append(
            description
        )

    top_artists = top_music_items(
        profile.get(
            "artist_counts",
            {},
        )
    )

    top_albums = top_music_items(
        profile.get(
            "album_counts",
            {},
        )
    )

    top_decades = top_music_items(
        profile.get(
            "decade_counts",
            {},
        )
    )

    manual_requests = int(
        profile.get(
            "total_manual_requests",
            0,
        )
    )

    return {
        "manual_requests": (
            manual_requests
        ),
        "recent_tracks": (
            recent_tracks
        ),
        "top_artists": (
            top_artists
        ),
        "top_albums": (
            top_albums
        ),
        "top_decades": (
            top_decades
        ),
    }
def save_alice_state(state):
    temporary_file = f"{STATE_FILE}.tmp"

    try:
        with open(
            temporary_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                state,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temporary_file,
            STATE_FILE,
        )

    except OSError as ex:
        print(f"Could not save Alice's state: {ex}")
def create_new_conversation(alice_lore=""):
    return [
        {
            "role": "system", 
            "content": build_system_prompt(alice_lore), 
        }
    ]

alice_lore = load_alice_lore()
conversation = create_new_conversation(alice_lore)



def get_speaker_id(character_name):
    """Find the VOICEVOX style ID for the requested character."""
    response = requests.get(
        f"{VOICEVOX_URL}/speakers",
        timeout=10,
    )
    response.raise_for_status()

    speakers = response.json()

    for speaker in speakers:
        if speaker["name"] == character_name:
            return speaker["styles"][0]["id"]

    raise ValueError(
        f"Couldn't find '{character_name}' in VOICEVOX. "
        "Make sure VOICEVOX is open and the character is installed."
    )


def calibrate_microphone(recognizer, microphone):
    """Calibrate once for the room's background-noise level."""
    print("Calibrating microphone. Please remain quiet...")

    with microphone as source:
        recognizer.adjust_for_ambient_noise(
            source,
            duration=1,
        )

    print(
        "Microphone calibrated. "
        f"Energy threshold: {recognizer.energy_threshold:.0f}"
    )


def listen_for_speech(
    recognizer,
    microphone,
    timeout=None,
    phrase_time_limit=8,
):
    """Listen once and return recognized English text."""
    try:
        with microphone as source:
            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )

        return recognizer.recognize_google(
            audio,
            language="en-US",
        )

    except sr.WaitTimeoutError:
        return None

    except sr.UnknownValueError:
        return None

    except sr.RequestError as ex:
        print(f"Speech recognition service error: {ex}")
        return None

    except OSError as ex:
        print(f"Microphone error: {ex}")
        return None


def wait_for_wake_phrase(
    recognizer,
    microphone,
    bridge,
):
    """
    Wait for voice wake phrase.

    In silent mode, a typed message immediately starts
    or resumes the conversation without requiring "Hey Alice".
    """
    print("\nWaiting for 'Hey Alice'...")

    while True:
        if bridge.shutdown_requested(): 
            return "shutdown", None
        typed_message = (
            bridge.get_message_nowait()
        )

        if typed_message:
            return "wake", typed_message

        if bridge.get_mode() == "silent":
            time.sleep(0.1)
            continue

        heard_text = listen_for_speech(
            recognizer,
            microphone,
            timeout=1,
            phrase_time_limit=8,
        )

        if not heard_text:
            continue

        print(
            f"Heard: {heard_text}"
        )

        if is_shutdown_command(
            heard_text
        ):
            return "shutdown", None

        match = WAKE_PHRASE_PATTERN.search(
            heard_text
        )

        if not match:
            continue

        remaining_command = (
            match.group(1).strip()
        )

        return (
            "wake",
            remaining_command or None,
        )

def get_next_user_message(
    recognizer,
    microphone,
    bridge,
):
    """Get the next typed or spoken message."""
    while True:
        if bridge.shutdown_requested(): 
            return None
        typed_message = bridge.get_message_nowait()

        if typed_message:
            return typed_message

        if bridge.get_mode() == "silent":
            time.sleep(0.1)
            continue

        spoken_message = listen_for_speech(
            recognizer,
            microphone,
            timeout=1,
            phrase_time_limit=30,
        )

        if spoken_message:
            print(f"You: {spoken_message}")
            return spoken_message
def listen_for_question(recognizer, microphone):
    """Listen for a question after the wake phrase."""
    print("Listening for your question...")

    text = listen_for_speech(
        recognizer,
        microphone,
        timeout=10,
        phrase_time_limit=25,
    )

    if not text:
        print("I didn't hear a question.")
        return None

    print(f"You: {text}")
    return text


def contains_phrase(text, phrases):
    """Check whether normalized speech contains one of the phrases."""
    normalized_text = text.lower().strip()

    return any(
        phrase in normalized_text
        for phrase in phrases
    )


def is_sleep_command(text):
    """Return True when Alice should end the current session."""
    return contains_phrase(text, SLEEP_PHRASES)

def normalize_command(text): 
    normalized = text.lower().strip()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized
def is_shutdown_command(text):
    """Return True when the entire Python program should stop."""
    normalized_text = normalize_command(text) 
    return normalized_text in {
        "shut down alice", 
        "shutdown alice", 
        "exit program", 
        "quit program", 
    }
def generate_fish_audio(
    text: str,
) -> bytes:
    text = str(
        text or ""
    ).strip()

    if not text:
        raise ValueError(
            "Fish Audio text cannot be empty."
        )

    if not FISH_AUDIO_API_KEY:
        raise RuntimeError(
            "FISH_AUDIO_API_KEY was not loaded."
        )

    response = requests.post(
        "https://api.fish.audio/v1/tts",
        headers={
            "Authorization": (
                f"Bearer {FISH_AUDIO_API_KEY}"
            ),
            "Content-Type": "application/json",
            "model": "s2.1-pro-free",
        },
        json={
            "text": text,
            "reference_id": (
                FISH_AUDIO_REFERENCE_ID
            ),
            "format": "wav",
            "latency": "balanced",
        },
        timeout=240,
    )

    if not response.ok:
        raise RuntimeError(
            "Fish Audio request failed with "
            f"HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    audio_bytes = response.content

    if (
        len(audio_bytes) < 44
        or not audio_bytes.startswith(
            b"RIFF"
        )
    ):
        raise RuntimeError(
            "Fish Audio did not return "
            "valid WAV audio."
        )

    return audio_bytes
def generate_voicevox_audio(text, speaker_id):
    """Generate Japanese speech with VOICEVOX and play it."""
    query_response = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={
            "text": text,
            "speaker": speaker_id,
        },
        timeout=30,
    )
    query_response.raise_for_status()

    synthesis_response = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={
            "speaker": speaker_id,
        },
        json=query_response.json(),
        timeout=60,
    )
    synthesis_response.raise_for_status()

    return synthesis_response.content 

def generate_typecast_audio(
    text,
    voice_id=TYPECAST_VOICE_ID,
):
    """Generate English WAV audio using Typecast."""
    if not TYPECAST_API_KEY:
        raise RuntimeError(
            "TYPECAST_API_KEY was not loaded."
            "Set it in the .env file, "
            "then restart the Python program."
        )

    if not voice_id:
        raise RuntimeError(
            "TYPECAST_VOICE_ID is not configured."
        )

    text = text.strip()

    if not text:
        raise ValueError(
            "Cannot generate speech from empty text."
        )

    response = requests.post(
        TYPECAST_API_URL,
        headers={
            "X-API-KEY": TYPECAST_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/wav",
        },
        json={
            "voice_id": voice_id,
            "text": text,
            "model": "ssfm-v30",
            "language": "eng",
            "prompt": {
                "emotion_type": "smart",
            },
            "output": {
                "volume": 100,
                "audio_pitch": 0,
                "audio_tempo": 1.0,
                "audio_format": "wav",
            },
        },
        timeout=90,
    )

    if not response.ok:
        error_preview = response.text[:500]

        raise RuntimeError(
            "Typecast request failed with "
            f"HTTP {response.status_code}: "
            f"{error_preview}"
        )

    content_type = response.headers.get(
        "Content-Type",
        ""
    ).lower()

    if (
        "audio" not in content_type
        and not response.content.startswith(b"RIFF")
    ):
        raise RuntimeError(
            "Typecast did not return WAV audio. "
            f"Content-Type was: {content_type}"
        )

    return response.content
def test_typecast():
    print(
        "Key available:",
        bool(TYPECAST_API_KEY)
    )

    audio_bytes = generate_typecast_audio(
        "Hello. This is Alice speaking in English."
    )

    process, temporary_path = (
        start_wav_playback(audio_bytes)
    )

    finish_audio_playback(
        process,
        temporary_path,
    )
def generate_alice_audio(
    reply,
    bridge,
    speaker_id,
):
    """
    Use Typecast for English and
    VOICEVOX for Japanese.

    Returns:
        audio_bytes, spoken_text
    """
    language = bridge.get_language()

    if language == "english":
        spoken_text = reply["english"].strip()

        return None, spoken_text

    spoken_text = reply["japanese"].strip()

    audio_bytes = generate_voicevox_audio(
        spoken_text,
        speaker_id,
    )

    return audio_bytes, spoken_text
def get_wav_duration_seconds(
    wav_bytes,
):
    try:
        with wave.open(
            io.BytesIO(wav_bytes),
            "rb",
        ) as wav_file:
            frame_count = (
                wav_file.getnframes()
            )

            frame_rate = (
                wav_file.getframerate()
            )

            if frame_rate <= 0:
                return 0.0

            return (
                frame_count
                / float(frame_rate)
            )

    except (
        wave.Error,
        EOFError,
    ) as error:
        print(
            "Could not inspect WAV duration:",
            error,
        )

        return 0.0
def start_wav_playback(wav_bytes):
    """
    Start WAV playback.

    Returns:
        process, temporary_path
    """
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as temporary_file:
            temporary_file.write(wav_bytes)
            temporary_path = temporary_file.name

        process = subprocess.Popen(
            [
                "/usr/bin/afplay",
                temporary_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return process, temporary_path

    except Exception:
        if (
            temporary_path
            and os.path.exists(temporary_path)
        ):
            os.remove(temporary_path)

        raise

def finish_audio_playback(
    process,
    temporary_path,
):
    """Wait until playback ends, then remove the file."""
    return_code = (
    process.wait()
)

    # print(
    #     "afplay finished:",
    #     {
    #         "return_code": return_code,
    #         "audio_file": temporary_path,
    #     },
    # )

    if return_code != 0:
        raise RuntimeError(
            "afplay exited with "
            f"status {return_code}."
        )
    if (
        temporary_path
        and os.path.exists(temporary_path)
    ):
        os.remove(temporary_path)

def choose_displayed_text(
    english_text,
    *,
    fallback=(
        "I could not generate a response."
    ),
):
    """
    Visible Alice messages are always English.
    """
    english_text = str(
        english_text or ""
    ).strip()

    return (
        english_text
        or fallback
    )


def choose_spoken_text(
    *,
    language,
    english_text,
    japanese_text,
    english_fallback=(
        "I could not generate a response."
    ),
    japanese_fallback=(
        "応答を生成できませんでした。"
    ),
):
    """
    English mode speaks English.
    Japanese mode speaks Japanese.

    Never send English text to VOICEVOX.
    """
    language = str(
        language or ""
    ).strip().lower()

    english_text = str(
        english_text or ""
    ).strip()

    japanese_text = str(
        japanese_text or ""
    ).strip()

    if language == "japanese":
        return (
            japanese_text
            or japanese_fallback
        )

    return (
        english_text
        or english_fallback
    )
def split_text_for_speech(
    text,
    max_characters=420,
):
    text = re.sub(
        r"\s+",
        " ",
        str(text or ""),
    ).strip()

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?。！？])\s+",
        text,
    )

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        candidate = (
            f"{current_chunk} {sentence}"
            .strip()
        )

        if (
            current_chunk
            and len(candidate)
            > max_characters
        ):
            chunks.append(
                current_chunk
            )

            current_chunk = sentence

        else:
            current_chunk = candidate

    if current_chunk:
        chunks.append(
            current_chunk
        )

    return chunks
def speak_alice_text(
    spoken_text,
    displayed_text,
    language,
    speaker_id,
    display,
    status_text="Speaking",
    mood="calm", 
):
    spoken_text = str(
        spoken_text or ""
    ).strip()

    displayed_text = str(
        displayed_text or ""
    ).strip()

    language = str(
        language or ""
    ).strip().lower()

    if language not in {
        "english",
        "japanese",
    }:
        language = "english"

    if not spoken_text:
        return

    speech_chunks = (
        split_text_for_speech(
            spoken_text,
            max_characters=420,
        )
        if language == "english"
        else [spoken_text]
    )

    with ALICE_SPEECH_LOCK:
        display.set_state(
            "thinking",
            "Thinking",
            "Preparing voice...",
        )

        display.set_state(
            "speaking",
            status_text,
            displayed_text,
        )

        try:
            for chunk_index, chunk in enumerate(
                speech_chunks,
                start=1,
            ):
                if language == "english":
                    expressive_chunk=(
                        add_fish_expression_cue(
                            chunk,
                            mood, 
                        )
                    )
                    expressive_chunk = (
                        add_fish_paralinguistic_cue(
                            expressive_chunk, 
                            mood, 
                        )
                    )
                    play_fish_audio_stream(
                        expressive_chunk
                    )
                else:
                    audio_bytes = (
                        generate_voicevox_audio(
                            chunk,
                            speaker_id,
                        )
                    )

                    process, temporary_path = (
                        start_wav_playback(
                            audio_bytes
                        )
                    )

                    finish_audio_playback(
                        process,
                        temporary_path,
                    )


        finally:
            display.set_state(
                "listening",
                "Listening",
                "You may continue.",
            )
def listen_during_conversation(recognizer, microphone):
    """
    Listen for the next question while Alice is active.

    The user does not need to repeat 'Hey Alice'.
    """
    print("\nListening...")

    text = listen_for_speech(
        recognizer,
        microphone,
        timeout=None,
        phrase_time_limit=30,
    )

    if not text:
        print("I didn't hear anything. Listening again...")
        return None

    print(f"You said: {text}")
    return text

def play_wav_bytes(wav_bytes):
    """Play WAV bytes using macOS afplay."""
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as temporary_file:
            temporary_file.write(wav_bytes)
            temporary_path = temporary_file.name
       
        subprocess.run(
            [
            "/usr/bin/afplay", 

            temporary_path, 
            ], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            check = False, 
        )

    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


def get_ai_response(user_text, alice_lore, alice_state, response_language):
    """Send the conversation to Ollama and parse its JSON reply."""
    
    state_context = json.dumps(
        alice_state, 
        ensure_ascii = False, 
        indent=2
    )
    reflection = (
        support_loop.reflect_on_next_message(
            user_text
        )
    )

    if reflection: 
        therapeutic_memory.observe_reflection(
            reflection 
        )
        print(
            "Alice support reflection:", 
            json.dumps(
                reflection, 
                ensure_ascii = False, 
                indent=2, 
            ), 
        )
    support_state = support_loop.process(
        user_message=user_text,
        relevant_memories=(
            therapeutic_memory
            .get_relevant_memories()
        )
    )

    support_context = {
        "emotional_context": {
            "possible_states": (
                support_state
                .emotional_context
                .possible_states
            ),
            "intensity": (
                support_state
                .emotional_context
                .intensity
            ),
            "immediate_need": (
                support_state
                .emotional_context
                .immediate_need
            ),
            "problem_solving_readiness": (
                support_state
                .emotional_context
                .problem_solving_readiness
            ),
            "confidence": (
                support_state
                .emotional_context
                .confidence
            ),
        },
        "support_strategy": {
            "primary": (
                support_state
                .strategy
                .primary
            ),
            "secondary": (
                support_state
                .strategy
                .secondary
            ),
            "reasoning": (
                support_state
                .strategy
                .reasoning
            ),
        },
    }

    support_instruction = f"""
THERAPEUTIC SUPPORT CONTEXT:

{json.dumps(
    support_context,
    ensure_ascii=False,
    indent=2,
)}

Use this context only to guide HOW you respond.

The emotional interpretation is uncertain and may be wrong.
Do not present inferred emotions as facts.

Follow the selected support strategy:

LISTEN:
Allow the user to express themselves.
Do not rush into advice.

REFLECT:
Briefly reflect the meaning or emotional content you understood.

VALIDATE:
Acknowledge that the user's reaction makes sense in context
without automatically agreeing with every conclusion.

EXPLORE:
Help the user understand the situation with one useful
observation or question.

CLARIFY:
Do not make assumptions. Ask for the missing information
needed to understand the user's meaning.

GROUND:
Prioritize calming, immediate, concrete support.
Do not overwhelm the user with analysis.

PROBLEM_SOLVE:
Work collaboratively toward practical next steps.

DECISION_SUPPORT:
Help identify options, values, consequences, and tradeoffs.
Do not simply make the decision for the user.

REASSURE:
Offer grounded reassurance.
Do not make promises or guarantees that cannot be known.

ENCOURAGE:
Support confidence or continued effort without giving
empty praise.

INFORM:
Answer the informational question directly.
Do not force the conversation into therapy.

SAFETY_RESPONSE:
Prioritize safety over the normal conversational strategy.

Secondary strategies may be used when they naturally support
the primary strategy.

Do not mention these strategy names, emotional scores, or this
internal analysis to the user.
"""
    if response_language == "english":
        language_instruction = """
Respond naturally in English.
The English field must contain the complete spoken response.
The Japanese field must contain a Japanese translation.
"""
    else:
        language_instruction = """
Respond naturally in Japanese.
The Japanese field must contain the complete spoken response.
The English field must contain its English translation.
"""

    if asks_for_previous_reason(
        user_text
    ):
        specificity_instruction = """
The user is asking you to explain or justify something
you previously said.

Answer directly and specifically.

1. State the exact concern or claim.
2. Identify the concrete prior statement that caused it.
3. Explain the connection briefly.
4. If no concrete prior statement supports the claim,
   admit that the earlier statement was unsupported.

Do not invent previous sensitive disclosures.
"""
    else:
        specificity_instruction = ""

        augmented_user_text = f"""
    Current internal state:
    {state_context}

    Language instructions:
    {language_instruction}

    Additional response instruction:
    {specificity_instruction}

    {support_instruction}

    User said:
    {user_text}
    """
    conversation.append(
        {
            "role": "user",
            "content": augmented_user_text,
        }
    )
    technical_question = looks_like_technical_question(
        user_text
    )
    response = ollama.chat(
        model=MODEL_NAME,
        messages=conversation,
        format="json",
        options={
            "num_predict": 700 if technical_question else 180,
            "num_ctx": 4092,
            "temperature": 0.3 if technical_question else 0.5,
        },
    )

    raw_reply = response["message"]["content"]

    parsed_reply = parse_bilingual_reply(
        raw_reply, 
        previous_emoticon=(
            alice_state.get(
                "last_emoticon",
                "",
            )
        ),
        
    )
    print(
        "Alice motion intent:",
        repr(
            parsed_reply[
                "motion_intent"
            ]
        ),
    )

    alice_state["last_emoticon"] = (
        parsed_reply["emoticon"]
    )
    save_alice_state(
        alice_state
    )
    clean_memory_reply = json.dumps(
        {
            "japanese": parsed_reply[
                "japanese"
            ],
            "english": parsed_reply[
                "english"
            ],
            "internal_mood": parsed_reply[
                "mood"
            ],
            "motion_intent": parsed_reply[
                "motion_intent"
            ], 
            "emoticon": parsed_reply[
                "emoticon"
            ],
            "conversation_action": parsed_reply[
                "action"
            ],
            "follow_up_japanese": parsed_reply[
                "follow_up_japanese"
            ],
            "follow_up_english": parsed_reply[
                "follow_up_english"
            ],
            "expects_answer": parsed_reply[
                "expects_answer"
            ],
        },
        ensure_ascii=False,
    )

    conversation.append(
        {
            "role": "assistant",
            "content": clean_memory_reply,
        }
    )

    save_memory()
    support_loop.record_response(
        parsed_reply["english"]
    )
    return parsed_reply


def looks_like_technical_question(text):
    """Use simple keywords to allow longer technical responses."""
    technical_terms = (
        "code",
        "program",
        "programming",
        "python",
        "javascript",
        "java",
        "c++",
        "error",
        "exception",
        "api",
        "function",
        "class",
        "library",
        "framework",
        "database",
        "server",
        "network",
        "algorithm",
        "machine learning",
        "artificial intelligence",
        "research",
        "science",
        "technical",
        "explain how",
        "how does",
        "how do i",
    )

    normalized_text = text.lower()

    return any(
        term in normalized_text
        for term in technical_terms
    )

def choose_emoticon(
    mood,
    requested_emoticon,
    previous_emoticon="",
):
    """
    Return an emoticon that belongs to the selected mood
    while avoiding immediate repetition.
    """
    mood = str(
        mood or "calm"
    ).strip().lower()

    if mood not in EMOTICON_CHOICES:
        mood = "calm"

    requested_emoticon = str(
        requested_emoticon or ""
    ).strip()

    previous_emoticon = str(
        previous_emoticon or ""
    ).strip()

    allowed_choices = list(
        EMOTICON_CHOICES[mood]
    )

    # Accept the model's choice only when it actually
    # belongs to the selected mood.
    if (
        requested_emoticon
        in allowed_choices
        and requested_emoticon
        != previous_emoticon
    ):
        return requested_emoticon

    alternatives = [
        emoticon
        for emoticon in allowed_choices
        if emoticon != previous_emoticon
    ]

    if not alternatives:
        alternatives = allowed_choices

    return random.choice(
        alternatives
    )
def generate_research_queries(
    topic: str,
) -> list[str]:
    topic = str(
        topic or ""
    ).strip()

    if not topic:
        return []

    prompt = f"""
Create concise web research queries for this topic:

{topic}

Return valid JSON only:

{{
  "queries": [
    "query 1",
    "query 2",
    "query 3",
    "query 4"
  ]
}}

Rules:
- Return exactly 3 queries.
- Make each query useful for Google search.
- Include at least one broad overview query.
- Include at least one recent developments query.
- Include at least one academic or research-paper query.
- Avoid duplicate queries.
- Do not include commentary outside the JSON.
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        format="json",
        options={
            "temperature": 0.2,
            "num_predict": 180,
        },
    )

    raw_result = str(
        response.get(
            "message",
            {},
        ).get(
            "content",
            "",
        )
    ).strip()

    result = json.loads(
        raw_result
    )

    queries = result.get(
        "queries",
        [],
    )

    if not isinstance(
        queries,
        list,
    ):
        return []

    cleaned_queries = []

    for query in queries:
        query = str(
            query or ""
        ).strip()

        if not query:
            continue

        if query in cleaned_queries:
            continue

        cleaned_queries.append(
            query
        )

    return cleaned_queries[:3]

def parse_research_command(
    text: str,
) -> str | None:
    original_text = str(
        text or ""
    ).strip()

    if not original_text:
        return None

    patterns = (
        r"^(?:please\s+)?research\s+(.+)$",
        r"^(?:please\s+)?look up\s+(.+)$",
        r"^(?:please\s+)?investigate\s+(.+)$",
        r"^(?:please\s+)?find out about\s+(.+)$",
    )

    for pattern in patterns:
        match = re.match(
            pattern,
            original_text,
            flags=re.IGNORECASE,
        )

        if match:
            topic = str(
                match.group(1)
            ).strip()

            return (
                topic
                if topic
                else None
            )

    return None

def parse_bilingual_reply(raw_reply, previous_emoticon="",):
    """Safely parse Alice's bilingual JSON response."""

    fallback = {
        "japanese": "",
        "english": (
            "I could not generate a valid response. "
            "Please try again."
        ),
        "mood": "confused",
        "emoticon": "🤔",
        "motion_intent": "", 
        "action": "wait",
        "follow_up_japanese": "",
        "follow_up_english": "",
        "expects_answer": False,
    }

    try:
        data = json.loads(raw_reply)

        if not isinstance(data, dict):
            print(
                "Model response JSON was not an object."
            )
            return fallback

        english_text = data.get(
            "english",
            "",
        )

        japanese_text = data.get(
            "japanese",
            "",
        )

        if not isinstance(english_text, str):
            english_text = ""

        if not isinstance(japanese_text, str):
            japanese_text = ""

        english_text = english_text.strip()
        japanese_text = japanese_text.strip()

        # Never show the raw JSON to the user.
        if not english_text:
            if japanese_text:
                english_text = (
                    "Alice returned a Japanese response "
                    "without an English translation."
                )
            else:
                english_text = (
                    "I could not generate a valid response. "
                    "Please try again."
                )

        mood = data.get(
            "internal_mood",
            "",
        )

        if not isinstance(mood, str):
            mood = "calm"

        mood = mood.strip().lower()

        valid_moods = {
            "calm",
            "happy",
            "concerned",
            "sad",
            "determined",
            "confused",
            "surprised",
            "embarrassed",
        }

        mood_aliases = {
            "neutral": "calm",
            "serious": "determined",
            "focused": "determined",
            "curious": "confused",
            "worried": "concerned",
            "anxious": "concerned",
            "excited": "happy",
            "pleased": "happy",
            "amused": "happy",
            "shocked": "surprised",
            "apologetic": "embarrassed",
        }

        mood = mood_aliases.get(
            mood,
            mood,
        )

        if mood not in valid_moods:
            mood = "calm"
        motion_intent = data.get(
            "motion_intent",
            "",
        )

        if not isinstance(
            motion_intent,
            str,
        ):
            motion_intent = ""

        motion_intent = (
            motion_intent
            .strip()
        )
        if len(motion_intent) > 200:
            motion_intent = (
                motion_intent[:200]
                .strip()
            )
        if not motion_intent:
            motion_intent = (
                infer_motion_intent(
                    mood,
                    english_text,
                )
            )
        raw_emoticon = data.get(
            "emoticon",
            "",
        )

        # Prevent None from becoming the text "None".
        if raw_emoticon is None:
            emoticon = ""
        elif isinstance(raw_emoticon, str):
            emoticon = raw_emoticon.strip()
        else:
            emoticon = ""

        invalid_emoticons = {
            "",
            "none",
            "null",
            "n/a",
            "no emoticon",
        }

        if emoticon.casefold() in invalid_emoticons:
            emoticon = ""

        if len(emoticon) > 20:
            emoticon = ""

        emoticon = choose_emoticon(
            mood=mood,
            requested_emoticon=raw_emoticon,
            previous_emoticon=previous_emoticon,
        )

        action = data.get(
            "conversation_action",
            "wait",
        )

        if action not in {
            "wait",
            "continue",
        }:
            action = "wait"

        follow_up_japanese = data.get(
            "follow_up_japanese",
            "",
        )

        follow_up_english = data.get(
            "follow_up_english",
            "",
        )

        if not isinstance(
            follow_up_japanese,
            str,
        ):
            follow_up_japanese = ""

        if not isinstance(
            follow_up_english,
            str,
        ):
            follow_up_english = ""

        follow_up_japanese = (
            follow_up_japanese.strip()
        )

        follow_up_english = (
            follow_up_english.strip()
        )

        if not (
            follow_up_japanese
            or follow_up_english
        ):
            action = "wait"

        expects_answer = data.get(
            "expects_answer",
            False,
        )

        return {
            "japanese": japanese_text,
            "english": english_text,
            "mood": mood,
            "emoticon": emoticon,
            "motion_intent": motion_intent, 
            "action": action,
            "follow_up_japanese": (
                follow_up_japanese
            ),
            "follow_up_english": (
                follow_up_english
            ),
            "expects_answer": bool(
                expects_answer
            ),
        }

    except json.JSONDecodeError as ex:
        print(
            "Model response was not valid JSON: "
            f"{ex}"
        )

        return fallback

def load_memory():
    """
    Load previous user and assistant messages from disk.

    The system prompt is always recreated from the current code so Alice's
    personality remains controlled by SYSTEM_PROMPT.
    """
    global conversation, alice_lore

    conversation = create_new_conversation(alice_lore)

    if not os.path.exists(MEMORY_FILE):
        print("No previous memory file found. Starting fresh.")
        return

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as memory_file:
            saved_messages = json.load(memory_file)

        if not isinstance(saved_messages, list):
            raise ValueError("Memory file must contain a list of messages.")

        valid_messages = []

        for message in saved_messages:
            if not isinstance(message, dict):
                continue

            role = message.get("role")
            content = message.get("content")

            if role not in {"user", "assistant"}:
                continue

            if not isinstance(content, str):
                continue

            valid_messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        conversation.extend(
            valid_messages[-MAX_MEMORY_MESSAGES:]
        )

        print(
            f"Loaded {len(valid_messages[-MAX_MEMORY_MESSAGES:])} "
            "previous conversation messages."
        )

    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as ex:
        print(f"Could not load Alice's memory: {ex}")
        print("Starting with a fresh conversation.")
        conversation = create_new_conversation(alice_lore)
def warm_up_ollama():
    try:
        ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": "Reply with OK.",
                }
            ],
            options={
                "num_predict": 2,
                "temperature": 0,
            },
        )

        print("Ollama model warmed up.")

    except Exception as ex:
        print(f"Ollama warm-up failed: {ex}")
def save_memory():
    """
    Save conversation messages without saving the system prompt.

    The system prompt remains in the Python code, which prevents an old memory
    file from replacing or modifying Alice's personality.
    """
    messages_to_save = [
        message
        for message in conversation
        if message.get("role") in {"user", "assistant"}
    ]

    messages_to_save = messages_to_save[-MAX_MEMORY_MESSAGES:]

    temporary_file = f"{MEMORY_FILE}.tmp"

    try:
        with open(
            temporary_file,
            "w",
            encoding="utf-8",
        ) as memory_file:
            json.dump(
                messages_to_save,
                memory_file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temporary_file,
            MEMORY_FILE,
        )

    except OSError as ex:
        print(f"Could not save Alice's memory: {ex}")

        if os.path.exists(temporary_file):
            try:
                os.remove(temporary_file)
            except OSError:
                pass
FLUCTLIGHT_HTML = """"""

class AliceInterfaceBridge:
    """Receives typed messages and mode changes from the HTML interface."""
    def set_display(self, display):
        self.display = display


    def toggle_pip(self):
        if not hasattr(self, "display"):
            return False

        return self.display.toggle_pip_mode()
    # recovery mechanism without restarting Alice
    def bring_to_front(self): 
        if not hasattr(
            self, 
            "display", 
        ): 
            return False
        return(
            self.display.raise_macos_pip()
        )
    def minimize_window(self):
        if not hasattr(self, "display"):
            return False

        self.display.minimize()
        return True
    def __init__(self):
        self.message_queue = queue.Queue()
        self.mode = "voice"
        self.mode_lock = threading.Lock()
        self.language = "japanese"
        self.shutdown_event = threading.Event()

        self.display=None
    def set_language(self, language): 
        if language not in {"japanese", "english"}:
            return False
        with self.mode_lock: 
            self.language = language
        return True
    def get_language(self): 
        with self.mode_lock: 
            return self.language
    def send_message(self, message):
        """
        Called by JavaScript when the user submits typed text.
        Methods exposed to JavaScript should return simple values.
        """
        if not isinstance(message, str):
            return False

        message = message.strip()

        if not message:
            return False

        self.message_queue.put(message)
        return True

    def set_mode(self, mode):
        """Switch between voice and silent modes."""
        if mode not in {"voice", "silent"}:
            return False

        with self.mode_lock:
            self.mode = mode
        if self.display is not None: 
            if mode == "silent": 
                self.display.set_state(
                    "listening", 
                    "Silent Mode", 
                    "Type a message.", 
                )
            else: 
                self.display.set_state(
                    "sleeping", 
                    "Voice Mode", 
                    "Say 'Hey Alice' to wake me.", 
                )
        return True

    def get_mode(self):
        with self.mode_lock:
            return self.mode

    def get_message_nowait(self):
        try:
            return self.message_queue.get_nowait()
        except queue.Empty:
            return None

    def request_shutdown(self) -> None:
        self.shutdown_event.set()

    def shutdown_requested(self) -> bool:
        return self.shutdown_event.is_set()
class FluctlightDisplay:
    def __init__(self, bridge):
        self.window = None
        self.web_server = None
        self.bridge = bridge
        self.ready = threading.Event()

        self.pip_mode = True

        self.full_width = 1280
        self.full_height = 800

        self.pip_width = 800
        self.pip_height = 500

        self.html_path = (
            Path(__file__).resolve().parent
            / "fluctlight.html"
        )
    def publish_todo_command(
        self,
        command: dict,
    ) -> bool:
        if self.web_server is None:
            return False

        if not isinstance(
            command,
            dict,
        ):
            return False

        try:
            self.web_server.publish_event(
                {
                    "type": "todo_command",
                    "data": command,
                }
            )

            return True

        except Exception as error:
            print(
                "Could not publish todo command: "
                f"{type(error).__name__}: {error}"
            )

            return False
    def publish_mood(
        self,
        mood: str,
    ) -> bool:
        if self.web_server is None:
            return False

        mood = str(
            mood or "calm"
        ).strip().lower()

        valid_moods = {
            "calm",
            "happy",
            "concerned",
            "sad",
            "determined",
            "confused",
            "surprised",
            "embarrassed",
        }

        if mood not in valid_moods:
            mood = "calm"

        try:
            self.web_server.publish_event(
                {
                    "type": "mood",
                    "mood": mood,
                }
            )

            print(
                "Published Alice mood:",
                mood
            )

            return True

        except Exception as error:
            print(
                "Could not publish Alice mood: "
                f"{type(error).__name__}: {error}"
            )

            return False
    def set_web_server(
        self,
        web_server,
    ):
        self.web_server = web_server
    def reactivate_macos_pip(self):
        if sys.platform != "darwin":
            return False

        try:
            from PyObjCTools import AppHelper

            def reactivate():
                try:
                    import AppKit

                    native_window = getattr(
                        self.window,
                        "native",
                        None,
                    )

                    if native_window is None:
                        return

                    native_window.orderFrontRegardless()

                    AppKit.NSApplication.sharedApplication(
                    ).activateIgnoringOtherApps_(
                        False
                    )

                except Exception as ex:
                    print(
                        "Could not reactivate Alice PiP: "
                        f"{type(ex).__name__}: {ex}"
                    )

            AppHelper.callAfter(
                reactivate
            )

            return True

        except Exception as ex:
            print(
                "Could not schedule Alice reactivation: "
                f"{type(ex).__name__}: {ex}"
            )
            return False
    def raise_macos_pip(self):
        """
        Bring Alice forward again without changing her layout.
        """
        if sys.platform != "darwin":
            return False

        try:
            from PyObjCTools import AppHelper

            def raise_window():
                try:
                    native_window = getattr(
                        self.window,
                        "native",
                        None,
                    )

                    if native_window is None:
                        return

                    native_window.orderFrontRegardless()

                except Exception as ex:
                    print(
                        "Could not raise Alice window: "
                        f"{type(ex).__name__}: {ex}"
                    )

            AppHelper.callAfter(
                raise_window
            )

            return True

        except Exception as ex:
            print(
                "Could not schedule Alice window raise: "
                f"{type(ex).__name__}: {ex}"
            )
            return False
    def toggle_pip_mode(self):
        if not self.window:
            return False

        self.pip_mode = not self.pip_mode

        try:
            if self.pip_mode:
                self.window.resize(
                    self.pip_width,
                    self.pip_height,
                )

                self.window.move(
                    500,
                    260,
                )

                mode_name = "pip"

            else:
                self.window.resize(
                    self.full_width,
                    self.full_height,
                )

                self.window.move(
                    180,
                    100,
                )

                mode_name = "full"

            mode_json = json.dumps(
                mode_name
            )

            self.window.evaluate_js(
                f"""
                (() => {{
                    document.body.dataset.displayMode =
                        {mode_json};

                    requestAnimationFrame(() => {{
                        if (
                            typeof window.applyAliceDisplayMode
                            === "function"
                        ) {{
                            window.applyAliceDisplayMode();
                        }}
                    }});

                    return true;
                }})();
                """
            )

            self.configure_macos_pip()

            return True

        except Exception as ex:
            print(
                f"Could not toggle PiP mode: {ex}"
            )
            return False

    def minimize(self):
        if not self.window:
            return

        try:
            self.window.minimize()

        except Exception as ex:
            print(
                f"Could not minimize Alice: {ex}"
            )

    def configure_macos_pip(self):
        if sys.platform != "darwin":
            return False

        if self.window is None:
            return False

        try:
            from PyObjCTools import AppHelper

            def apply_native_configuration():
                try:
                    import AppKit

                    native_window = getattr(
                        self.window,
                        "native",
                        None,
                    )

                    if native_window is None:
                        print(
                            "macOS PiP: native window unavailable."
                        )
                        return

                    print(
                        "Applying PiP on main thread:",
                        AppKit.NSThread.isMainThread(),
                    )

                    application = (
                        AppKit.NSApplication.sharedApplication()
                    )

                    
                    #Make Alice a utility-style application rather than
                    #a normal document application.
                    
                    application.setActivationPolicy_(
                        AppKit.NSApplicationActivationPolicyAccessory
                    )

                    can_join_all_apps = getattr(
                        AppKit,
                        (
                            "NSWindowCollectionBehavior"
                            "CanJoinAllApplications"
                        ),
                        None,
                    )

                    behavior = 0

                    if can_join_all_apps is not None:
                        behavior |= int(
                            can_join_all_apps
                        )

                        print(
                            "Using CanJoinAllApplications:",
                            int(can_join_all_apps),
                        )
                    else:
                        behavior |= int(
                            AppKit
                            .NSWindowCollectionBehaviorCanJoinAllSpaces
                        )

                        behavior |= int(
                            AppKit
                            .NSWindowCollectionBehaviorFullScreenAuxiliary
                        )

                        print(
                            "CanJoinAllApplications unavailable; "
                            "using legacy full-screen behaviors."
                        )

                    behavior |= int(
                        AppKit
                        .NSWindowCollectionBehaviorStationary
                    )

                    behavior |= int(
                        AppKit
                        .NSWindowCollectionBehaviorIgnoresCycle
                    )

                    native_window.setCollectionBehavior_(
                        behavior
                    )

                    native_window.setLevel_(
                        AppKit.NSFloatingWindowLevel
                    )

                    native_window.setHidesOnDeactivate_(
                        False
                    )

                    native_window.setCanHide_(
                        False
                    )

                    native_window.setOpaque_(
                        True
                    )

                    native_window.orderFrontRegardless()

                    print(
                        "Alice collection behavior:",
                        int(
                            native_window.collectionBehavior()
                        ),
                    )

                    print(
                        "Alice window level:",
                        int(native_window.level()),
                    )

                    print(
                        "Alice activation policy:",
                        int(
                            application.activationPolicy()
                        ),
                    )

                except Exception as ex:
                    print(
                        "macOS PiP configuration failed: "
                        f"{type(ex).__name__}: {ex}"
                    )

            AppHelper.callAfter(
                apply_native_configuration
            )

            return True

        except Exception as ex:
            print(
                "Could not schedule macOS PiP: "
                f"{type(ex).__name__}: {ex}"
            )
            return False
    def start(self, on_loaded=None):
        """
        Legacy pywebview startup is disabled.

        Alice now uses the Flask server and Electron interface.
        """
        raise RuntimeError(
            "The legacy pywebview interface is disabled. "
            "Start Alice through the Flask/Electron main function."
        )

    def set_state(
        self,
        state,
        status,
        subtitle="",
    ):
        """
        Publish Alice's state to the Flask/Electron interface.
        """
        if self.web_server is None:
            return

        try:
            self.web_server.publish_state(
                state,
                status,
                subtitle,
            )

        except Exception as ex:
            print(
                "Could not publish Alice state: "
                f"{ex}"
            )

    def close(self):
        if not self.window:
            return

        try:
            self.window.destroy()

        except Exception:
            pass

    def append_message(
        self,
        speaker,
        text,
    ):
        """
        Publish a chat message to the Flask/Electron interface.
        """
        if self.web_server is None:
            return

        try:
            self.web_server.publish_chat_message(
                speaker,
                text,
            )

        except Exception as ex:
            print(
                "Could not publish chat event: "
                f"{ex}"
            )
    def publish_improvement_progress(
        self,
        *,
        state,
        progress=None,
        message="",
        current_file="",
    ):
        """
        Publish self-improvement progress to the browser.
        """
        if self.web_server is None:
            print(
                "Improvement progress not published: "
                "web server is unavailable."
            )
            return False

        event_data = {
            "type": "improvement_progress",
            "data": {
                "state": str(
                    state or ""
                ),
                "message": str(
                    message or ""
                ),
                "current_file": str(
                    current_file or ""
                ),
            },
        }

        if progress is not None:
            event_data["data"]["progress"] = (
                float(progress)
            )

        try:
            self.web_server.publish_event(
                event_data
            )

            return True

        except Exception as error:
            print(
                "Could not publish improvement "
                f"progress: {type(error).__name__}: "
                f"{error}"
            )

            return False
def is_vision_command(text):
    # Screen requests must never use the webcam.
    if is_screen_command(text):
        return False

    normalized = normalize_command(
        text
    )

    direct_camera_phrases = (
        "can you see me",
        "do you see me",
        "look at me",
        "describe me",
        "how do i look",
        "what am i wearing",
        "what color is my hair",
        "what color are my eyes",
        "am i smiling",
        "use the camera",
        "check the camera",
        "what is behind me",
        "what am i holding",
    )

    if any(
        phrase in normalized
        for phrase in direct_camera_phrases
    ):
        return True

    all_phrases = (
        set(VISION_PHRASES)
        | learned_vision_phrases
    )

    matched_phrase = next(
        (
            phrase
            for phrase in all_phrases
            if normalize_command(phrase)
            in normalized
        ),
        None,
    )

    if matched_phrase:
        return True
    classifier_prompt = f"""
Decide whether this message requires using the physical webcam.

The webcam shows the user's physical surroundings.
It does not show the computer display.

Messages about the computer screen, desktop, browser, webpage,
movie, active window, or application must return false.

Examples that require the webcam:
- What am I holding?
- What color is my shirt?
- Can you see me?
- What is behind me?
- Read this paper I am holding.

Examples that do not require the webcam:
- Check my computer screen.
- What is on my screen?
- Look at this webpage.
- What movie am I watching?
- Read the error in VS Code.
- Explain recursion.

User message:
{text}

Return valid JSON only:

{{
  "requires_camera": false
}}
"""

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": classifier_prompt,
                }
            ],
            format="json",
            options={
                "temperature": 0,
                "num_predict": 20,
            },
        )

        raw_result = response[
            "message"
        ][
            "content"
        ]

        result = json.loads(raw_result)

        requires_camera = bool(
            result.get(
                "requires_camera",
                False,
            )
        )

        # print(
        #     "Vision classifier result:",
        #     requires_camera,
        #     "for:",
        #     repr(normalized),
        # )

        if requires_camera:
            learned_vision_phrases.add(
                normalized
            )

            save_learned_vision_phrases(
                learned_vision_phrases
            )

            print(
                "Learned new vision phrase:",
                normalized,
            )

        return requires_camera

    except (
        ollama.ResponseError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as ex:
        print(
            f"Vision routing error: {ex}"
        )
        return False

def format_japanese_lesson(result):
    if not result.get("success"):
        return result.get(
            "english",
            "I could not read the Japanese text.",
        )

    japanese_text = result.get(
        "japanese_text",
        "",
    )

    reading = result.get(
        "reading",
        "",
    )

    romaji = result.get(
        "romaji",
        "",
    )

    english = result.get(
        "english",
        "",
    )

    explanation = result.get(
        "explanation",
        "",
    )

    lines = []

    if japanese_text:
        lines.append(
            f"Japanese: {japanese_text}"
        )

    if reading:
        lines.append(
            f"Reading: {reading}"
        )

    if romaji:
        lines.append(
            f"Romaji: {romaji}"
        )

    if english:
        lines.append(
            f"English: {english}"
        )

    if explanation:
        lines.append(
            f"Explanation: {explanation}"
        )

    kanji_entries = result.get(
        "kanji",
        [],
    )
    valid_kanji_entries = []
    for entry in kanji_entries: 
        if not isinstance(entry, dict): 
            continue 
        word = str(
            entry.get("word", "")

        ).strip()
        if not re.search(
            r"[\u4e00-\u9fff]", 
            word, 
        ): 
            continue 
        valid_kanji_entries.append(
            entry
        )
    result["kanji"] = valid_kanji_entries

    if isinstance(kanji_entries, list):
        valid_entries = []

        for entry in kanji_entries:
            if not isinstance(entry, dict):
                continue

            word = str(
                entry.get("word", "")
            ).strip()

            entry_reading = str(
                entry.get("reading", "")
            ).strip()

            meaning = str(
                entry.get("meaning", "")
            ).strip()

            if not word:
                continue

            valid_entries.append(
                f"{word}（{entry_reading}）— {meaning}"
            )

        if valid_entries:
            lines.append(
                "Kanji: "
                + "; ".join(valid_entries)
            )

    return "\n".join(lines)
class AliceVision:

    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.camera = None

        self.lock = threading.RLock() # protect webcam access
        self.model_lock = threading.Lock() 

        self.last_screen_question = ""
        self.last_screen_answer = ""
        self.last_screen_analysis_time = 0.0

        self.product_context = None
        self.product_context_time = 0.0
        self.product_conversation_stage = "idle"

        cascade_path = (
            cv2.data.haarcascades
            + "haarcascade_frontalface_default.xml"

        )
        self.face_detector = cv2.CascadeClassifier(
            cascade_path 
        )
        if self.face_detector.empty():
            raise RuntimeError(
                "Could not load OpenCV face detector."
            )
    def open_camera(self):
        """Open the webcam if it is not already open."""
        with self.lock:
            if (
                self.camera is not None
                and self.camera.isOpened()
            ):        return True

            self.camera = cv2.VideoCapture(
                self.camera_index, 
                cv2.CAP_AVFOUNDATION, 
            )

            if not self.camera.isOpened():
                self.camera.release()
                self.camera = None
                return False

            return True
    # create a screen capture method
    def get_builtin_display_id(self):
        """
        Return the macOS display ID for the computer's built-in
        display.

        This does not depend on where the Alice window is located.
        If no built-in display exists, fall back to the configured
        macOS main display.
        """
        try:
            screens = AppKit.NSScreen.screens()

            for screen in screens:
                description = (
                    screen.deviceDescription()
                )

                screen_number = description.get(
                    "NSScreenNumber"
                )

                if screen_number is None:
                    continue

                display_id = int(
                    screen_number
                )

                if Quartz.CGDisplayIsBuiltin(
                    display_id
                ):
                    # print(
                    #     "Alice screen capture selected "
                    #     f"built-in display ID: {display_id}"
                    # )
                    return display_id

            # Desktop Macs may not have a built-in display.
            return int(
                Quartz.CGMainDisplayID()
            )

        except Exception as ex:
            print(
                "Could not locate built-in display: "
                f"{ex}"
            )

            return int(
                Quartz.CGMainDisplayID()
            )
    def capture_screen(self):
        """
        Capture the computer's built-in display and return JPEG
        bytes.

        Alice's window may be located on an external monitor;
        this method still captures the MacBook's internal screen.
        """
        try:
            display_id = (
                self.get_builtin_display_id()
            )

            cg_image = (
                Quartz.CGDisplayCreateImage(
                    display_id
                )
            )

            if cg_image is None:
                raise RuntimeError(
                    "Quartz returned no screen image."
                )

            width = int(
                Quartz.CGImageGetWidth(
                    cg_image
                )
            )

            height = int(
                Quartz.CGImageGetHeight(
                    cg_image
                )
            )

            bytes_per_row = int(
                Quartz.CGImageGetBytesPerRow(
                    cg_image
                )
            )

            data_provider = (
                Quartz.CGImageGetDataProvider(
                    cg_image
                )
            )

            if data_provider is None:
                raise RuntimeError(
                    "Quartz returned no image data provider."
                )

            raw_data = (
                Quartz.CGDataProviderCopyData(
                    data_provider
                )
            )

            if raw_data is None:
                raise RuntimeError(
                    "Quartz returned no screen image data."
                )

            image = Image.frombuffer(
                "RGBA",
                (
                    width,
                    height,
                ),
                bytes(
                    raw_data
                ),
                "raw",
                "BGRA",
                bytes_per_row,
                1,
            ).convert(
                "RGB"
            )

            # Reduce vision-model workload while preserving
            # the complete internal display.
            try:
                resize_filter = (
                    Image.Resampling.LANCZOS
                )
            except AttributeError:
                resize_filter = (
                    Image.LANCZOS
                )

            image.thumbnail(
                (
                    1280,
                    720,
                ),
                resize_filter,
            )

            buffer = io.BytesIO()

            image.save(
                buffer,
                format="JPEG",
                quality=80,
            )

            return buffer.getvalue()

        except Exception as ex:
            print(
                f"Screen capture error: {ex}"
            )

            return None
    def save_screen_capture_test(self):
        """
        Save one built-in-display screenshot for testing.
        """
        image_bytes = self.capture_screen()

        if not image_bytes:
            return False

        test_path = (
            BASE_DIR
            / "alice_builtin_screen_test.jpg"
        )

        with open(
            test_path,
            "wb",
        ) as file:
            file.write(
                image_bytes
            )

        print(
            "Saved built-in screen test to:",
            test_path,
        )

        return True
    def get_screen_vision_text(
        self,
        prompt,
        image_bytes,
        num_predict=800,
    ):
        """
        Ask the instruct vision model to inspect an image.

        qwen3-vl:4b-instruct does not support think=True,
        so the answer must be read from message.content.
        """
        with self.model_lock:
            response = ollama.chat(
                model=VISION_MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [
                            image_bytes,
                        ],
                    }
                ],

                # Do not pass think=True or think=False.
                # The instruct model does not support thinking mode.

                # Do not force JSON here.
                # The text model structures the result afterward.

                options={
                    "temperature": 0.1,
                    "num_predict": num_predict,
                    "num_ctx": 8192,
                },
            )

        message = response.get(
            "message",
            {},
        )

        vision_text = str(
            message.get(
                "content",
                "",
            )
        ).strip()

        # print(
        #     "Vision content length:",
        #     len(vision_text),
        # )

        # print(
        #     "Vision done reason:",
        #     response.get(
        #         "done_reason",
        #         "unknown",
        #     ),
        # )

        # print(
        #     "Vision generated tokens:",
        #     response.get(
        #         "eval_count",
        #         "unknown",
        #     ),
        # )

        if not vision_text:
            raise ValueError(
                "The instruct vision model returned "
                "an empty content field."
            )

        return vision_text
    def structure_screen_answer(
        self,
        vision_text,
        question,
    ):
        """
        Convert the vision model's screen observations into
        a normalized dictionary.

        This method does not save product context. Product context
        is saved later in analyze_screen_question().
        """
        conversion_prompt = f"""
A vision model inspected the user's current computer screen.

User question:
{question}

Current visual observations:
{vision_text}

Use only the current visual observations.

GENERAL RULES:
- Do not use or mention previous conversation history.
- Do not answer from memory.
- Ignore Alice's own floating interface, chat, subtitles,
  terminal logs, and debug messages.
- Speak in first person as Alice.
- Do not refer to yourself as "the system."
- Do not expose private messages, passwords, authentication codes,
  payment details, or other sensitive information.
- Do not identify real people.
- State uncertainty when something cannot be read clearly.

PRODUCT IDENTIFICATION RULES:
- Determine whether the main visible subject is a product,
  electronic component, development board, sensor, module,
  tool, product listing, code, document, video, or something else.
- Use a product name, brand, or model only when it is actually
  readable in the observations.
- Do not infer a model number from appearance.
- Do not invent technical specifications.
- Do not claim a voltage, interface, protocol, range, resolution,
  compatibility, or feature unless it is visibly supported.
- Put unreadable or unverified details in uncertain_details.
- If a product is identified with medium or high confidence,
  offer to explain it and provide recommendations.
- Do not provide the full product recommendation yet.

Return valid JSON only:

{{
  "english": "Concise English response",
  "japanese": "Natural Japanese translation",
  "confidence": "high, medium, or low",
  "emoticon": "one suitable emoticon",
  "subject_type": "product, code, webpage, document, video, other",
  "product_name": "exact visible product name or empty string",
  "brand": "exact visible brand or empty string",
  "model": "exact visible model number or empty string",
  "visible_specs": [
    "only specifications explicitly visible"
  ],
  "visible_features": [
    "only features explicitly visible"
  ],
  "uncertain_details": [
    "important details that could not be verified"
  ],
  "offer_product_help": false
}}
"""

        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Convert current screenshot observations "
                        "into valid JSON. Do not use prior memory."
                    ),
                },
                {
                    "role": "user",
                    "content": conversion_prompt,
                },
            ],
            format="json",
            options={
                "temperature": 0,
                "num_predict": 500,
                "num_ctx": 8192,
            },
        )

        raw_result = str(
            response.get(
                "message",
                {},
            ).get(
                "content",
                "",
            )
        ).strip()

        if not raw_result:
            raise ValueError(
                "The text model returned an empty "
                "structured screen result."
            )

        result = json.loads(
            raw_result
        )

        if not isinstance(
            result,
            dict,
        ):
            raise TypeError(
                "Structured screen result was not "
                "a JSON object."
            )

        subject_type = str(
            result.get(
                "subject_type",
                "other",
            )
        ).strip().lower()

        valid_subject_types = {
            "product",
            "code",
            "webpage",
            "document",
            "video",
            "other",
        }

        if subject_type not in valid_subject_types:
            subject_type = "other"

        product_name = str(
            result.get(
                "product_name",
                "",
            )
        ).strip()

        brand = str(
            result.get(
                "brand",
                "",
            )
        ).strip()

        product_model = str(
            result.get(
                "model",
                "",
            )
        ).strip()

        visible_specs = result.get(
            "visible_specs",
            [],
        )

        visible_features = result.get(
            "visible_features",
            [],
        )

        uncertain_details = result.get(
            "uncertain_details",
            [],
        )

        if not isinstance(
            visible_specs,
            list,
        ):
            visible_specs = []

        if not isinstance(
            visible_features,
            list,
        ):
            visible_features = []

        if not isinstance(
            uncertain_details,
            list,
        ):
            uncertain_details = []

        visible_specs = [
            str(item).strip()
            for item in visible_specs
            if str(item).strip()
        ]

        visible_features = [
            str(item).strip()
            for item in visible_features
            if str(item).strip()
        ]

        uncertain_details = [
            str(item).strip()
            for item in uncertain_details
            if str(item).strip()
        ]

        result["subject_type"] = (
            subject_type
        )

        result["product_name"] = (
            product_name
        )

        result["brand"] = brand

        result["model"] = (
            product_model
        )

        result["visible_specs"] = (
            visible_specs
        )

        result["visible_features"] = (
            visible_features
        )

        result["uncertain_details"] = (
            uncertain_details
        )

        result["offer_product_help"] = bool(
            result.get(
                "offer_product_help",
                False,
            )
        )

        return result
        
    def analyze_screen(self):
        """
        Analyze the screen for the passive observer.
        """
        image_bytes = self.capture_screen()

        if not image_bytes:
            return None
        raw_result = ""
        vision_text = ""
        conversion_response = None 

        vision_prompt = """
Inspect this current computer-screen screenshot.

Describe:
- the user's probable activity;
- the main visible topic;
- whether there is a meaningful change worth commenting on.

Ignore Alice's own floating interface, subtitles, and chat.
Do not treat cursor movement, terminal scrolling, minor
animation, or Alice's overlay as meaningful changes.

Ignore terminal lines generated by Alice's own program, including screen-analysis logs, status messages, and debug output. Based the answer on underlying desktop content instead.
Privacy:
- Do not reveal passwords or authentication codes.
- Do not expose payment information.
- Do not quote private messages.
- Classify sensitive content as private.
- Do not identify real people.

Do not output JSON. Provide a concise factual observation.
"""

        structure_prompt = """
Convert the visual observation below into JSON.

Visual observation:
{vision_text}

Return valid JSON only:

{{
  "activity": "movie, research, coding, reading, shopping, private, other",
  "summary": "brief non-sensitive description",
  "topic": "main visible topic",
  "interesting_change": false,
  "should_consider_commenting": false,
  "confidence": "high, medium, or low"
}}
"""

        try:
            vision_text = (
                self.get_screen_vision_text(
                    prompt=vision_prompt,
                    image_bytes=image_bytes,
                    num_predict=800,
                )
            )

            conversion_response = ollama.chat(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            structure_prompt.format(
                                vision_text=vision_text
                            )
                        ),
                    }
                ],
                format="json",
                options={
                    "temperature": 0,
                    "num_predict": 220,
                },
            )

            raw_result = str(
                conversion_response.get(
                    "message",
                    {},
                ).get(
                    "content",
                    "",
                )
            ).strip()

            if not raw_result:
                print(
                    "Passive screen structuring "
                    "returned no content."
                )
                return None

            result = json.loads(
                raw_result
            )

            activity = str(
                result.get(
                    "activity",
                    "other",
                )
            ).strip().lower()

            valid_activities = {
                "movie",
                "research",
                "coding",
                "reading",
                "shopping",
                "private",
                "other",
            }

            if activity not in valid_activities:
                activity = "other"

            confidence = str(
                result.get(
                    "confidence",
                    "medium",
                )
            ).strip().lower()

            if confidence not in {
                "high",
                "medium",
                "low",
            }:
                confidence = "medium"

            return {
                "activity": activity,
                "summary": str(
                    result.get(
                        "summary",
                        "",
                    )
                ).strip(),
                "topic": str(
                    result.get(
                        "topic",
                        "",
                    )
                ).strip(),
                "interesting_change": bool(
                    result.get(
                        "interesting_change",
                        False,
                    )
                ),
                "should_consider_commenting": bool(
                    result.get(
                        "should_consider_commenting",
                        False,
                    )
                ),
                "confidence": confidence,
            }

        except (
            ollama.ResponseError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as ex:
            print(
                f"Screen analysis error: {ex}"
            )
            return None
    def analyze_screen_question(
        self,
        question,
    ):
        """
        Capture the screen, inspect it with Qwen3-VL,
        then structure the answer with the text model.
        """
        image_bytes = self.capture_screen()

        if not image_bytes:
            return {
                "success": False,
                "english": (
                    "I could not capture your "
                    "computer screen."
                ),
                "japanese": (
                    "コンピューター画面を"
                    "取得できませんでした。"
                ),
                "confidence": "low",
            }

        vision_prompt = f"""
Inspect this newly captured screenshot of the user's
computer display.

User question:
{question}

Describe the visible information needed to answer that question.

Rules:
- This is a screenshot, not a webcam image.
- Ignore Alice's own floating interface and chat overlay.
- Describe the main visible applications and activity.
- Read relevant visible text when it is sufficiently clear.
- Do not expose passwords, authentication codes, payment
  information, private messages, or other sensitive data.
- Do not identify real people.
- State when something is unclear.
- Do not output JSON.
- Finish with a concise answer to the user's question.
"""

        try:
            vision_text = (
                self.get_screen_vision_text(
                    prompt=vision_prompt,
                    image_bytes=image_bytes,
                    num_predict=800,
                )
            )

            # print(
            #     "Raw visual analysis:",
            #     repr(
            #         vision_text[:2000]
            #     ),
            # )

            result = (
                self.structure_screen_answer(
                    vision_text=vision_text,
                    question=question,
                )
            )

            # ---------------------------------
            # BASIC RESPONSE FIELDS
            # ---------------------------------
            english = str(
                result.get(
                    "english",
                    "",
                )
            ).strip()

            japanese = str(
                result.get(
                    "japanese",
                    "",
                )
            ).strip()

            confidence = str(
                result.get(
                    "confidence",
                    "medium",
                )
            ).strip().lower()

            if confidence not in {
                "high",
                "medium",
                "low",
            }:
                confidence = "medium"

            emoticon = str(
                result.get(
                    "emoticon",
                    "",
                )
            ).strip()

            if emoticon.casefold() in {
                "",
                "none",
                "null",
                "n/a",
            }:
                emoticon = "🤔"

            if len(emoticon) > 20:
                emoticon = "🤔"

            if not english:
                english = (
                    "I could not determine what "
                    "was visible on the screen."
                )

            # ---------------------------------
            # PRODUCT INFORMATION
            # ---------------------------------
            subject_type = str(
                result.get(
                    "subject_type",
                    "other",
                )
            ).strip().lower()

            if subject_type not in {
                "product",
                "code",
                "webpage",
                "document",
                "video",
                "other",
            }:
                subject_type = "other"

            product_name = str(
                result.get(
                    "product_name",
                    "",
                )
            ).strip()

            brand = str(
                result.get(
                    "brand",
                    "",
                )
            ).strip()

            product_model = str(
                result.get(
                    "model",
                    "",
                )
            ).strip()

            visible_specs = result.get(
                "visible_specs",
                [],
            )

            visible_features = result.get(
                "visible_features",
                [],
            )

            uncertain_details = result.get(
                "uncertain_details",
                [],
            )

            if not isinstance(
                visible_specs,
                list,
            ):
                visible_specs = []

            if not isinstance(
                visible_features,
                list,
            ):
                visible_features = []

            if not isinstance(
                uncertain_details,
                list,
            ):
                uncertain_details = []

            visible_specs = [
                str(item).strip()
                for item in visible_specs
                if str(item).strip()
            ]

            visible_features = [
                str(item).strip()
                for item in visible_features
                if str(item).strip()
            ]

            uncertain_details = [
                str(item).strip()
                for item in uncertain_details
                if str(item).strip()
            ]

            offer_product_help = bool(
                subject_type == "product"
                and bool(product_name)
            )

            # ---------------------------------
            # GENERAL SCREEN CONTEXT
            # ---------------------------------
            self.last_screen_question = (
                question
            )

            self.last_screen_answer = (
                english
            )

            self.last_screen_analysis_time = (
                time.time()
            )

            # ---------------------------------
            # SAVE VERIFIED PRODUCT CONTEXT
            # ---------------------------------
            if (
                subject_type == "product"
                and product_name
                and confidence in {
                    "high",
                    "medium",
                }
            ):
                self.product_context = {
                    "product_name": (
                        product_name
                    ),
                    "brand": brand,
                    "model": product_model,
                    "visible_specs": (
                        visible_specs
                    ),
                    "visible_features": (
                        visible_features
                    ),
                    "uncertain_details": (
                        uncertain_details
                    ),
                    "confidence": confidence,
                }

                self.product_context_time = (
                    time.time()
                )

                if offer_product_help:
                    self.product_conversation_stage = (
                        "awaiting_permission"
                    )
                else:
                    self.product_conversation_stage = (
                        "idle"
                    )

            # ---------------------------------
            # FINAL RESULT
            # ---------------------------------
            return {
                "success": True,
                "english": english,
                "japanese": japanese,
                "confidence": confidence,
                "emoticon": emoticon,
                "subject_type": subject_type,
                "product_name": product_name,
                "brand": brand,
                "model": product_model,
                "visible_specs": visible_specs,
                "visible_features": (
                    visible_features
                ),
                "uncertain_details": (
                    uncertain_details
                ),
                "offer_product_help": (
                    offer_product_help
                ),
            }

        except (
            ollama.ResponseError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as ex:
            print(
                f"Direct screen analysis error: {ex}"
            )

            return {
                "success": False,
                "english": (
                    "I could not analyze the "
                    "computer screen."
                ),
                "japanese": (
                    "コンピューター画面を"
                    "解析できませんでした。"
                ),
                "confidence": "low",
            }
    def create_product_advice(
        self,
        intended_use,
    ):
        """
        Produce grounded product guidance from the product
        information verified during screen analysis.
        """
        if not self.product_context:
            return {
                "success": False,
                "english": (
                    "I no longer have enough verified "
                    "product information."
                ),
                "japanese": (
                    "確認済みの商品情報が"
                    "不足しています。"
                ),
                "emoticon": "(・_・;)",
            }

        context = self.product_context

        product_name = context.get(
            "product_name",
            "",
        )

        brand = context.get(
            "brand",
            "",
        )

        model = context.get(
            "model",
            "",
        )

        visible_specs = context.get(
            "visible_specs",
            [],
        )

        visible_features = context.get(
            "visible_features",
            [],
        )

        uncertain_details = context.get(
            "uncertain_details",
            [],
        )

        advice_prompt = f"""
You are Alice providing careful technical purchasing guidance.

Verified product information from the user's current screen:

Product name:
{product_name or "Not verified"}

Brand:
{brand or "Not verified"}

Model:
{model or "Not verified"}

Verified visible specifications:
{json.dumps(visible_specs, ensure_ascii=False)}

Verified visible features:
{json.dumps(visible_features, ensure_ascii=False)}

Uncertain or unreadable details:
{json.dumps(uncertain_details, ensure_ascii=False)}

User's intended use:
{intended_use}

ACCURACY RULES:
- Treat only the listed visible specifications and features as verified
  facts about this exact product.
- Do not invent an exact voltage, sensor range, protocol, resolution,
  power requirement, pinout, accuracy, or compatibility.
- If an important specification was not verified, explicitly say that
  it needs to be checked on the manufacturer page or datasheet.
- Do not invent reviews, benchmark results, prices, certifications,
  availability, or customer experiences.
- Do not pretend that current web research was performed.
- You may explain general engineering concepts that are well established,
  but clearly label them as general guidance rather than verified facts
  about this product.
- Compare the product with general technology categories when useful.
  For example, compare sensing principles or interface types.
- Do not name specific competing models unless their details were already
  provided or visible.
- Make recommendations conditional on the user's intended application.
- If the information is insufficient, say exactly what must be verified.

RESPONSE CONTENT:
1. Give a concise technical description of the verified product.
2. Separate verified facts from general technical guidance.
3. Explain likely strengths and limitations for the intended use.
4. Compare it with relevant general alternatives or sensor categories.
5. Recommend what the user should verify before purchasing or wiring it.
6. End with one useful follow-up question only when necessary.

Maintain Alice's warm, capable personality.
Do not say that you are unfamiliar with hardware.

The English response must:

- Be at least four complete sentences.
- Directly discuss the user's intended use.
- Explain what the verified product appears to be.
- Separate verified product facts from general engineering guidance.
- Mention important missing specifications.
- Compare at least two relevant alternatives when useful.
- Give a conditional recommendation.
- Never return only a heading, label, field description, or placeholder.
- Never return the exact phrase "Grounded technical guidance."

Return valid JSON only.

The english and japanese fields must contain the complete,
fully written product explanation. Do not copy field descriptions,
labels, or placeholder wording into the response.

{{
  "english": "Write the complete English technical explanation here. It must contain several useful sentences, not a label or placeholder.",
  "japanese": "Write the complete natural Japanese translation here.",
  "emoticon": "Use one suitable emoticon",
  "verified_facts": [
    "Write each verified fact as a complete sentence"
  ],
  "general_guidance": [
    "Write each general engineering recommendation as a complete sentence"
  ],
  "recommended_checks": [
    "Write each specification the user should verify"
  ],
  "confidence": "high, medium, or low"
}}
"""

        try:
            response = ollama.chat(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Provide technically careful "
                            "product guidance. Never invent "
                            "product-specific facts."
                        ),
                    },
                    {
                        "role": "user",
                        "content": advice_prompt,
                    },
                ],
                format="json",
                options={
                    "temperature": 0.2,
                    "num_predict": 1200,
                    "num_ctx": 8192,
                },
            )

            raw_result = str(
                response.get(
                    "message",
                    {},
                ).get(
                    "content",
                    "",
                )
            ).strip()

            if not raw_result:
                raise ValueError(
                    "Product advice model returned "
                    "an empty response."
                )

            result = json.loads(
                raw_result
            )

            english = str(
                result.get(
                    "english",
                    "",
                )
            ).strip()

            invalid_english_responses = {
                "",
                "grounded technical guidance",
                "technical guidance",
                "english technical explanation",
                "write the complete english technical explanation here",
            }

            if (
                english.casefold()
                in invalid_english_responses
            ):
                english = ""
            japanese = str(
                result.get(
                    "japanese",
                    "",
                )
            ).strip()
            invalid_japanese_responses = {
                "",
                "natural japaense translation",
                "write the complete natural japanese translation here",
            }
            if(
                japanese.casefold()
                in invalid_japanese_responses
            ):
                japanese = ""
            emoticon = str(
                result.get(
                    "emoticon",
                    "🤔",
                )
            ).strip()
            verified_facts = result.get(
                "verified_facts",
                [],
            )

            general_guidance = result.get(
                "general_guidance",
                [],
            )

            recommended_checks = result.get(
                "recommended_checks",
                [],
            )

            if not isinstance(
                verified_facts,
                list,
            ):
                verified_facts = []

            if not isinstance(
                general_guidance,
                list,
            ):
                general_guidance = []

            if not isinstance(
                recommended_checks,
                list,
            ):
                recommended_checks = []

            verified_facts = [
                str(item).strip()
                for item in verified_facts
                if str(item).strip()
            ]

            general_guidance = [
                str(item).strip()
                for item in general_guidance
                if str(item).strip()
            ]

            recommended_checks = [
                str(item).strip()
                for item in recommended_checks
                if str(item).strip()
            ]
            if not english:
                sections = []

                if verified_facts:
                    sections.append(
                        "Verified from the visible product page: "
                        + " ".join(
                            verified_facts
                        )
                    )

                if general_guidance:
                    sections.append(
                        "General engineering guidance: "
                        + " ".join(
                            general_guidance
                        )
                    )

                if recommended_checks:
                    sections.append(
                        "Before using or purchasing it, verify: "
                        + " ".join(
                            recommended_checks
                        )
                    )

                english = "\n\n".join(
                    sections
                ).strip()

                if not english:
                    retry_prompt = f"""
Provide a complete technical recommendation for this product.

Product:
{product_name or "Exact product name was not verified"}

Verified specifications:
{json.dumps(visible_specs, ensure_ascii=False)}

Verified features:
{json.dumps(visible_features, ensure_ascii=False)}

Unverified details:
{json.dumps(uncertain_details, ensure_ascii=False)}

User's intended use:
{intended_use}

Write at least four complete English sentences.

Explain:
1. What is verified about the product.
2. Whether it appears suitable for the intended use.
3. Relevant alternatives.
4. What specifications must be checked.

Do not invent product-specific facts.
Do not return headings or placeholders.

Return valid JSON only:

{{
  "english": "Complete English explanation",
  "japanese": "Complete Japanese translation",
  "emoticon": "🤔"
}}
"""

                retry_response = ollama.chat(
                    model=MODEL_NAME,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Write complete grounded technical "
                                "advice. Never copy placeholders."
                            ),
                        },
                        {
                            "role": "user",
                            "content": retry_prompt,
                        },
                    ],
                    format="json",
                    options={
                        "temperature": 0.1,
                        "num_predict": 900,
                        "num_ctx": 8192,
                    },
                )

                retry_raw = str(
                    retry_response.get(
                        "message",
                        {},
                    ).get(
                        "content",
                        "",
                    )
                ).strip()

                retry_result = json.loads(
                    retry_raw
                )

                english = str(
                    retry_result.get(
                        "english",
                        "",
                    )
                ).strip()

                japanese = str(
                    retry_result.get(
                        "japanese",
                        "",
                    )
                ).strip()

                emoticon = str(
                    retry_result.get(
                        "emoticon",
                        emoticon or "🤔",
                    )
                ).strip()

            if not english:
                raise ValueError(
                    "Product advice remained empty "
                    "after one retry."
                )

            self.product_context_time = (
                time.time()
            )

            self.product_conversation_stage = (
                "idle"
            )

            return {
                "success": True,
                "english": english,
                "japanese": japanese,
                "emoticon": emoticon or "🤔",
            }

        except (
            ollama.ResponseError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as ex:
            print(
                f"Product advice error: {ex}"
            )

            return {
                "success": False,
                "english": (
                    "I could not produce reliable "
                    "product guidance from the "
                    "available information."
                ),
                "japanese": (
                    "利用できる情報だけでは、"
                    "信頼できる製品案内を"
                    "作成できませんでした。"
                ),
                "emoticon": "(・_・;)",
            }
    def capture_frame(self):
        """
        Open the camera, capture a fresh frame,
        then release it.
        """
        with self.lock:
            # Release any previous camera session.
            if self.camera is not None:
                self.camera.release()
                self.camera = None

            self.camera = cv2.VideoCapture(
                self.camera_index,
                cv2.CAP_AVFOUNDATION,
            )

            if not self.camera.isOpened():
                print("Could not open the camera.")
                self.camera = None
                return None

            # Give the camera time to update exposure
            # and discard stale buffered frames.
            time.sleep(0.6)

            frame = None

            for _ in range(15):
                success, candidate = self.camera.read()

                if success and candidate is not None:
                    frame = candidate

                time.sleep(0.03)

            # Close the camera after every observation.
            self.camera.release()
            self.camera = None

            if frame is None:
                print("Camera returned no usable frame.")
                return None
            analysis_frame = frame.copy()
            # Mirror the webcam view.
            frame = cv2.flip(
                frame,
                1,
            )

            print(
                "Fresh camera frame:",
                frame.shape,
                "captured at:",
                time.time(),
            )

            cv2.imwrite(
                "alice_camera_test.jpg",
                frame,
            )

            print(
                "Updated alice_camera_test.jpg"
            )

            return analysis_frame 

    def analyze_frame(
        self,
        question,
    ):
            """
            Capture a fresh webcam frame and answer a visual
            question in both English and Japanese.
            """
            frame = self.capture_frame()

            if frame is None:
                return {
                    "success": False,
                    "english": (
                        "I could not access the camera."
                    ),
                    "japanese": (
                        "カメラにアクセスできませんでした。"
                    ),
                    "confidence": "low",
                }

            frame = cv2.resize(
                frame,
                (768, 432),
            )

            success, encoded_image = cv2.imencode(
                ".jpg",
                frame,
                [
                    cv2.IMWRITE_JPEG_QUALITY,
                    80,
                ],
            )

            if not success:
                return {
                    "success": False,
                    "english": (
                        "I could not process the camera image."
                    ),
                    "japanese": (
                        "カメラ画像を処理できませんでした。"
                    ),
                    "confidence": "low",
                }

            image_bytes = (
                encoded_image.tobytes()
            )

            prompt = f"""
Inspect this newly captured webcam image.

The user's name is Mercy.

User's question:
{question}

Respond as Alice: warm, proud, thoughtful, slightly formal,
and genuinely pleased to interact with Mercy.

Camera-response behavior:
- Answer the user's exact visual question first.
- Then add one brief, natural personal reaction based on what
  is visibly supported.
- Do not sound like a generic surveillance system.
- You may address the user as Mercy.
- You may say that you are glad to finally see them.
- Do not claim facial recognition or claim that the image proves
  the person's identity.
- Do not say that you identified Mercy from their face.
- Treat Mercy's name as information supplied by the application,
  not something inferred visually.
- Do not identify any other real person.
- Describe only visible clothing, hair, accessories, expression,
  pose, objects, colors, and surroundings.
- Do not infer ethnicity, health, personality, or hidden attributes.
- State uncertainty when something is unclear.
- Avoid repeating exactly the same reaction on every request.
- Keep the complete response to one or two sentences.

Examples of the intended tone:

User: Can you see me?
English:
"Yes, I can see you, Mercy! I am glad I can finally associate
our conversations with the person in front of the camera. "

User: Am I smiling?
English:
"You appear to be smiling slightly. It is pleasant to see you
looking cheerful."

Return valid JSON only:

{{
  "english": "Natural English camera response",
  "japanese": "Natural Japanese translation",
  "confidence": "high, medium, or low",
  "emoticon": "one suitable emoticon",
}}
"""

            try:
                # Use the same lock as screen analysis so the
                # webcam and passive screen observer do not send
                # overlapping requests to the vision model.
                with self.model_lock:
                    response = ollama.chat(
                        model=VISION_MODEL_NAME,
                        messages=[
                            {
                                "role": "user",
                                "content": prompt,
                                "images": [
                                    image_bytes,
                                ],
                            }
                        ],

                        # Do not add think=True or think=False.
                        # qwen3-vl:4b-instruct does not support it.

                        format="json",
                        options={
                            "temperature": 0.1,
                            "num_predict": 350,
                            "num_ctx": 8192,
                        },
                    )

                message = response.get(
                    "message",
                    {},
                )

                raw_result = str(
                    message.get(
                        "content",
                        "",
                    )
                ).strip()

                if not raw_result:
                    raise ValueError(
                        "The camera vision model returned "
                        "an empty response."
                    )

                result = json.loads(
                    raw_result
                )

                if not isinstance(result, dict):
                    raise TypeError(
                        "Camera vision result was not "
                        "a JSON object."
                    )

                english = str(
                    result.get(
                        "english",
                        "",
                    )
                ).strip()

                japanese = str(
                    result.get(
                        "japanese",
                        "",
                    )
                ).strip()

                confidence = str(
                    result.get(
                        "confidence",
                        "medium",
                    )
                ).strip().lower()

                camera_emoticon = str(
                    result.get(
                        "emoticon",
                        "",
                    )
                ).strip()

                if camera_emoticon.casefold() in {
                    "",
                    "none",
                    "null",
                    "n/a",
                }:
                    camera_emoticon = "(＾▽＾)"

                if len(camera_emoticon) > 20:
                    camera_emoticon = "(＾▽＾)"
                if confidence not in {
                    "high",
                    "medium",
                    "low",
                }:
                    confidence = "medium"

                if not english:
                    english = (
                        "I could not determine that "
                        "from the camera image."
                    )

                if not japanese:
                    japanese = (
                        "カメラ画像からは"
                        "判断できませんでした。"
                    )

                return {
                    "success": True,
                    "english": english,
                    "japanese": japanese,
                    "confidence": confidence,
                    "emoticon": camera_emoticon,
                }

            except (
                ollama.ResponseError,
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ) as ex:
                print(
                    f"Camera vision error: {ex}"
                )

                return {
                    "success": False,
                    "english": (
                        "I could not analyze the camera image."
                    ),
                    "japanese": (
                        "カメラ画像を解析できませんでした。"
                    ),
                    "confidence": "low",
                    "emoticon": "(・_・;)",
                }
    
    def analyze_japanese_text(self, question):
        """
        Capture a fresh image and analyze visible Japanese text.
        """
        frame = self.capture_frame()

        if frame is None:
            return {
                "success": False,
                "japanese_text": "",
                "reading": "",
                "romaji": "",
                "english": "I could not access the camera.",
                "explanation": "",
                "confidence": "low",
            }

        frame = cv2.resize(
            frame,
            (1280, 720),
        )

        success, encoded_image = cv2.imencode(
            ".jpg",
            frame,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                90,
            ],
        )

        if not success:
            return {
                "success": False,
                "japanese_text": "",
                "reading": "",
                "romaji": "",
                "english": "I could not process the camera image.",
                "explanation": "",
                "confidence": "low",
            }

        image_bytes = encoded_image.tobytes()

        prompt = f"""
    You are Alice, acting as a Japanese-language tutor.

    Carefully inspect the newly captured camera image and read any
    visible Japanese text.

    User request:
    {question}

    Important OCR rules:
    - First determine whether the text appears horizontally mirrored.
    - If it is mirrored, mentally correct the orientation before reading it.
    - Do not guess grammatical explanations for uncertain characters.
    - If fewer than 80 percent of the characters are clear, report that
    the text is unclear instead of inventing a translation.
    - The reading field must contain hiragana, not romaji.
    - Only include actual kanji in the kanji list.

    Return the following:

    - japanese_text:
    The Japanese text exactly as it appears in the image.
    Preserve kanji, hiragana, katakana, and punctuation.

    - reading:
    The pronunciation written entirely in hiragana.
    For multiple words or sentences, provide the complete reading.

    - romaji:
    A clear Hepburn-style romanization.

    - english:
    A natural English translation.

    - explanation:
    Briefly explain important vocabulary, kanji, particles,
    conjugations, or grammar.

    - kanji:
    A list containing each important kanji compound.
    Each entry must include:
    word, reading, meaning.

    Rules:
    - Analyze only the current attached image.
    - Do not reuse text from an earlier image.
    - Do not invent characters that are blurry or hidden.
    - Use an empty string when no Japanese text is visible.
    - State uncertainty when a character cannot be read clearly.
    - Read English text as well as Japanese text.
    - Preserve the visible wording as accurately as possible.
    - If the visible text is addressed to Alice, report the exact text so
    Alice can respond conversationally.
    - Do not translate English into English unnecessarily.
    - Do not invent unreadable words.
    - Return valid JSON only.

    Return this structure:
    {{
    "japanese_text": "日本語",
    "visible_text": "exact text visible in the image", 
    "detected language": "japanese, english, mixed, or unknown", 
    "reading": "にほんご" or hiragana reading when Japanese is present,
    "romaji": "nihongo or romaji when Japanese is present",
    "english": "Japanese language",
    "english_translation": English translation when needed", 
    "explanation": "A concise teaching/language-learning explanation.",
    "confidence": high, medium, or low"
    "kanji": [
        {{
        "word": "日本語",
        "reading": "にほんご",
        "meaning": "Japanese language"
        }}
    ],
    "confidence": "high"
    }}
    """

        try:
            response = ollama.chat(
                model=VISION_MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [
                            image_bytes,
                        ],
                    }
                ],
                format="json",
                options={
                    "temperature": 0.1,
                    "num_predict": 500,
                },
            )

            message = response["message"]

            raw_result = message.get(
                "content",
                "",
            ).strip()

            thinking_result = message.get(
                "thinking",
                "",
            ).strip()

            if not raw_result:
                raw_result = thinking_result

            print(
                "Japanese tutor raw result:",
                repr(raw_result),
            )

            if not raw_result:
                raise ValueError(
                    "The vision model returned no Japanese analysis."
                )

            result = json.loads(raw_result)

            return {
                "success": True,
                "visible_text": str(
                    result.get(
                        "visible_text",
                        "",
                    )
                ).strip(),
                "detected_language": str(
                    result.get(
                        "detected_language",
                        "unknown",
                    )
                ).strip().lower(),
                "reading": str(
                    result.get(
                        "reading",
                        "",
                    )
                ).strip(),
                "romaji": str(
                    result.get(
                        "romaji",
                        "",
                    )
                ).strip(),
                "english_translation": str(
                    result.get(
                        "english_translation",
                        "",
                    )
                ).strip(),
                "explanation": str(
                    result.get(
                        "explanation",
                        "",
                    )
                ).strip(),
                "confidence": str(
                    result.get(
                        "confidence",
                        "medium",
                    )
                ).strip().lower(),
            }

        except (
            ollama.ResponseError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as ex:
            print(
                f"Japanese tutor analysis error: {ex}"
            )

            return {
                "success": False,
                "japanese_text": "",
                "reading": "",
                "romaji": "",
                "english": (
                    "I could not read the Japanese text clearly."
                ),
                "explanation": "",
                "kanji": [],
                "confidence": "low",
            }
    def detect_faces(self, frame): # detects faces but not who the person is
        if frame is None: 
            return []
        grayscale = cv2.cvtColor(
            frame, 
            cv2.COLOR_BGR2GRAY, 
        )
        faces = self.face_detector.detectMultiScale(
            grayscale, 
            scaleFactor=1.1, 
            minNeighbors=5, 
            minSize=(80, 80), 
        )
        return list(faces) 
    def describe_frame(self): 
        # simple text description 
        frame = self.capture_frame()
        if frame is None: 
            return{
                "success": False, 
                "description": (
                    "I could not access the camera."
                ), 
                "face_count": 0, 
            }
        faces = self.detect_faces(frame)
        face_count = len(faces)
        if face_count == 0: 
            description = (
                "I can see the camera view, "
                "but I do not detect a face."
            )
        elif face_count == 1: 
            description = (
                "I can see one person in front of the camera. "
            )
        else: 
            description = (f"I can see approximately "
                           f"{face_count} people in front of me.")
        return{
            "success": True, 
            "description": description, 
            "face_count": face_count, 
        }
    def close(self):
        """Release the webcam."""
        with self.lock:
            if self.camera is not None:
                self.camera.release()
                self.camera = None

class AliceScreenObserver:
    """Periodically inspect the screen and propose comments."""

    def __init__(
        self,
        vision,
        on_observation: Callable[[dict], bool],
        check_interval=SCREEN_CHECK_INTERVAL,
        minimum_comment_interval=MIN_COMMENT_INTERVAL,
        maximum_comments_per_hour=(
            MAX_UNPROMPTED_COMMENTS_PER_HOUR
        ),
    ):
        self.suppress_until = 0.0 
        self.vision = vision
        self.on_observation = on_observation

        self.check_interval = max(
            3,
            float(check_interval),
        )

        self.minimum_comment_interval = max(
            15,
            float(minimum_comment_interval),
        )

        self.maximum_comments_per_hour = max(
            1,
            int(maximum_comments_per_hour),
        )

        self.running = False
        self.enabled = True
        self.thread = None

        self.last_summary = ""
        self.last_topic = ""
        self.last_comment_time = 0.0
        self.last_user_activity_time = time.time()

        self.comment_times = deque()
        self.stop_event = threading.Event()
        self.pause_lock = threading.Lock()
        self.pause_count = 0
    def suppress_comments_for(
        self,
        seconds, 
    ):
        self.suppress_until = max(self.suppress_until, time.time() + seconds,)
    def pause(self): 
        with self.pause_lock:
            self.pause_count +=1 
    def resume(self): 
        with self.pause_lock: 
            self.pause_count = max(
                0, 
                self.pause_count - 1, 
            )
    def is_paused(self): 
        with self.pause_lock: 
            return self.pause_count > 0 
    def wait_until_idle(
        self,
        timeout=30,
    ):
        """
        Wait for an existing vision-model request to finish.

        Returns True when the model became available.
        """
        acquired = (
            self.vision.model_lock.acquire(
                timeout=timeout
            )
        )

        if acquired:
            self.vision.model_lock.release()

        return acquired
    def mark_user_activity(self):
        self.last_user_activity_time = time.time()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)

    def start(self):
        if self.running:
            return

        self.running = True
        self.stop_event.clear()

        self.thread = threading.Thread(
            target=self._run,
            name="AliceScreenObserver",
            daemon=True,
        )

        self.thread.start()

        print(
            "Alice screen observer started."
        )

    def stop(self):
        self.running = False
        self.stop_event.set()

        thread = self.thread

        if (
            thread
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=2.0)

        print(
            "Alice screen observer stopped."
        )

    def _remove_expired_comment_times(
        self,
        current_time,
    ):
        one_hour_ago = current_time - 3600

        while (
            self.comment_times
            and self.comment_times[0] < one_hour_ago
        ):
            self.comment_times.popleft()

    def _is_duplicate(
        self,
        summary,
        topic,
    ):
        normalized_summary = (
            summary.casefold().strip()
        )

        normalized_topic = (
            topic.casefold().strip()
        )

        previous_summary = (
            self.last_summary.casefold().strip()
        )

        previous_topic = (
            self.last_topic.casefold().strip()
        )

        return (
            normalized_summary == previous_summary
            and normalized_topic == previous_topic
        )

    def _run(self):
        while self.running:
            if self.stop_event.wait(
                self.check_interval
            ):
                break

            if not self.enabled:
                continue
            if self.is_paused(): 
                continue 
            if time.time() < self.suppress_until: 
                continue 
            try:
                observation = (
                    self.vision.analyze_screen()
                )

                if not observation:
                    continue

                activity = observation.get(
                    "activity",
                    "other",
                )

                summary = str(
                    observation.get(
                        "summary",
                        "",
                    )
                ).strip()

                topic = str(
                    observation.get(
                        "topic",
                        "",
                    )
                ).strip()

                if not summary:
                    continue

                if activity == "private":
                    self.last_summary = summary
                    self.last_topic = topic
                    continue

                if self._is_duplicate(
                    summary,
                    topic,
                ):
                    continue

                self.last_summary = summary
                self.last_topic = topic

                if not observation.get(
                    "interesting_change",
                    False,
                ):
                    continue

                if not observation.get(
                    "should_consider_commenting",
                    False,
                ):
                    continue

                current_time = time.time()

                if (
                    current_time
                    - self.last_comment_time
                    < self.minimum_comment_interval
                ):
                    continue

                self._remove_expired_comment_times(
                    current_time
                )

                if (
                    len(self.comment_times)
                    >= self.maximum_comments_per_hour
                ):
                    continue

                did_comment = bool(
                    self.on_observation(
                        observation
                    )
                )

                if did_comment:
                    self.last_comment_time = (
                        current_time
                    )

                    self.comment_times.append(
                        current_time
                    )

            except Exception as ex:
                print(
                    "Screen observer iteration "
                    f"failed: {ex}"
                )
                continue
def parse_model_json(
    raw_text: str,
) -> dict:
    """
    Parse JSON returned by a local model.

    Code and file paths may contain backslashes such as
    '\\users' or '\\update'. Those can look like malformed
    JSON Unicode escapes and must be escaped before retrying.
    """
    raw_text = str(
        raw_text
    ).strip()

    try:
        result = json.loads(
            raw_text
        )

        if not isinstance(
            result,
            dict,
        ):
            raise ValueError(
                "Model JSON was not an object."
            )

        return result

    except json.JSONDecodeError:
        repaired_text = raw_text

        # Repair malformed Unicode-style escapes such as:
        # \users, \update, or \u followed by non-hex text.
        repaired_text = re.sub(
            r"\\u(?![0-9a-fA-F]{4})",
            r"\\\\u",
            repaired_text,
        )

        # Escape any other backslash that is not a valid
        # JSON escape sequence.
        repaired_text = re.sub(
            r'\\(?!["\\/bfnrtu])',
            r"\\\\",
            repaired_text,
        )

        result = json.loads(
            repaired_text
        )

        if not isinstance(
            result,
            dict,
        ):
            raise ValueError(
                "Repaired model JSON was not an object."
            )

        return result
def handle_screen_observation(
    observation,
    display,
    bridge,
    speaker_id,
):
    """
    Decide whether Alice should comment.

    Returns True only when a comment was actually delivered.
    """
    activity = str(
        observation.get(
            "activity",
            "other",
        )
    ).strip()

    summary = str(
        observation.get(
            "summary",
            "",
        )
    ).strip()

    topic = str(
        observation.get(
            "topic",
            "",
        )
    ).strip()

    confidence = str(
        observation.get(
            "confidence",
            "medium",
        )
    ).strip()

    if not summary:
        return False

    if activity == "private":
        return False

    prompt = f"""
Alice observed the user's screen without being directly asked.

Activity:
{activity}

Topic:
{topic or "Unclear"}

Observation:
{summary}

Vision confidence:
{confidence}

Decide whether speaking now would feel natural, useful, and
respectful.

Behavior:
- Alice is curious, warm, and slightly nosy, but not intrusive.
- She should usually remain silent.
- She must not merely describe the screen.
- For a movie, react like a friend at a watch party.
- Never reveal spoilers or claim knowledge beyond the visible scene.
- For research, ask a relevant question or offer useful help.
- For coding, do not propose code fixes, settings, function
  arguments, or implementation details.
- If a clear error is visible, only say that an error appears
  to be present and ask whether the user wants it inspected.
- Do not mention private, financial, authentication, or personal
  message content.
- Never claim that a feature is implemented or missing based only
  on a screenshot.
- Never mention "Server Window Only", hidden=True, width=0,
  or height=0.
- Keep any comment to one or two brief sentences.

Return valid JSON only:

{{
  "speak": false,
  "english": "",
  "japanese": ""
}}
"""
    raw_result = ""
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Alice, a proud, thoughtful, "
                        "curious AI companion. Produce only "
                        "the requested JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            format="json",
            options={
                "temperature": 0.2,
                "num_predict": 130,
            },
        )

        raw_result = (
            response["message"]["content"]
            .strip()
        )

        decision = parse_model_json(
            raw_result
        )

        if not bool(
            decision.get(
                "speak",
                False,
            )
        ):
            return False

        english_comment = str(
            decision.get(
                "english",
                "",
            )
        ).strip()

        japanese_comment = str(
            decision.get(
                "japanese",
                "",
            )
        ).strip()

        if not english_comment:
            return False

        language = bridge.get_language()

        spoken_text = choose_spoken_text(
            language=language,
            english_text=english_comment,
            japanese_text=japanese_comment,
            english_fallback=(
                "I noticed something on your screen."
            ),
            japanese_fallback=(
                "画面上で少し気になることに"
                "気づきました。"
            ),
        )

        display.append_message(
            "alice",
            english_comment,
        )

        speak_alice_text(
            spoken_text=spoken_text,
            displayed_text=english_comment,
            language=language,
            speaker_id=speaker_id,
            display=display,
            status_text="Commenting",
        )

        return True

    except (
        ollama.ResponseError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        RuntimeError,
        requests.RequestException,
    ) as ex:
        # print(
        #     f"Screen comment error: {ex}"
        # )

        if raw_result:
            # print(
            #     "Rejected screen-comment output:",
            #     repr(raw_result[:500]),
            # )

            return False
class AliceSpotify:
    """Search for music and control the user's Spotify playback."""

    REQUIRED_SCOPES = " ".join(
        [
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-currently-playing",
        ]
    )

    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = os.getenv(
            "SPOTIFY_REDIRECT_URI",
            "http://127.0.0.1:8888/callback",
        )

        self.spotify = None

        if not self.client_id or not self.client_secret:
            print(
                "Spotify is disabled. Set SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET in .env."
            )
            return

        try:
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=self.REQUIRED_SCOPES,
                cache_path=str(BASE_DIR / ".spotify_cache"),
                open_browser=True,
            )

            self.spotify = spotipy.Spotify(
                auth_manager=auth_manager,
                requests_timeout=15,
                retries=3,
            )

            print("Spotify integration initialized.")

        except Exception as ex:
            print(f"Spotify initialization error: {ex}")
            self.spotify = None

    @property
    def available(self):
        return self.spotify is not None

    def _get_device_id(self):
        """
        Return an active Spotify device.

        If no device is active, use the first available device and transfer
        playback to it.
        """
        if not self.available:
            raise RuntimeError("Spotify is not configured.")

        result = self.spotify.devices()
        devices = result.get("devices", [])

        if not devices:
            raise RuntimeError(
                "No Spotify device is available. Open Spotify on your "
                "computer or phone and play something once."
            )

        active_device = next(
            (
                device
                for device in devices
                if device.get("is_active")
            ),
            None,
        )

        if active_device:
            return active_device["id"]

        selected_device = devices[0]
        selected_device_id = selected_device["id"]

        self.spotify.transfer_playback(
            selected_device_id,
            force_play=False,
        )

        time.sleep(0.5)

        return selected_device_id

    def play_song(
        self,
        song,
        artist=None,
    ):
        """
        Search Spotify and play its best result.

        Search order:
        1. Strict title + artist query.
        2. Loose title + artist query.
        3. Song title only.

        The looser fallbacks allow reasonable matching when the
        artist is omitted or slightly misspelled.
        """
        if not self.available:
            raise RuntimeError(
                "Spotify is not configured."
            )

        song = str(song).strip()

        if not song:
            raise ValueError(
                "A song title or search query is required."
            )

        cleaned_artist = (
            str(artist).strip()
            if artist
            else ""
        )

        search_queries = []

        if cleaned_artist:
            search_queries.extend(
                [
                    (
                        "strict title and artist",
                        f'track:"{song}" '
                        f'artist:"{cleaned_artist}"',
                    ),
                    (
                        "loose title and artist",
                        f"{song} {cleaned_artist}",
                    ),
                ]
            )

        search_queries.append(
            (
                "title or general search",
                song,
            )
        )

        tracks = []
        search_method = ""

        for method_name, query in search_queries:
            search_result = self.spotify.search(
                q=query,
                type="track",
                limit=10,
            )

            candidate_tracks = (
                search_result
                .get("tracks", {})
                .get("items", [])
            )

            if candidate_tracks:
                tracks = candidate_tracks
                search_method = method_name
                break

        if not tracks:
            requested_description = song

            if cleaned_artist:
                requested_description += (
                    f" by {cleaned_artist}"
                )

            raise RuntimeError(
                "I could not find a Spotify result for "
                f'"{requested_description}".'
            )

        # Spotify orders search results by relevance.
        # The first item is the top result.
        track = tracks[0]

        track_uri = str(
            track.get(
                "uri",
                "",
            )
        ).strip()

        if not track_uri:
            raise RuntimeError(
                "Spotify returned a track without "
                "a playable URI."
            )

        track_name = str(
            track.get(
                "name",
                "Unknown track",
            )
        ).strip()

        artist_names = ", ".join(
            str(item.get("name", "")).strip()
            for item in track.get("artists", [])
            if item.get("name")
        )

        album = track.get(
            "album",
            {},
        )

        album_name = str(
            album.get(
                "name",
                "",
            )
        ).strip()

        release_date = str(
            album.get(
                "release_date",
                "",
            )
        ).strip()

        popularity = track.get(
            "popularity"
        )

        device_id = self._get_device_id()

        self.spotify.start_playback(
            device_id=device_id,
            uris=[
                track_uri,
            ],
        )

        for queued_track in tracks[1:6]:
            queued_uri = str(
                queued_track.get(
                    "uri",
                    "",
                )
            ).strip()

            if not queued_uri:
                continue

            self.spotify.add_to_queue(
                queued_uri,
                device_id=device_id,
            )

        requested_artist_matched = True

        if cleaned_artist:
            normalized_requested_artist = (
                normalize_command(
                    cleaned_artist
                )
            )

            normalized_result_artists = [
                normalize_command(
                    item.get(
                        "name",
                        "",
                    )
                )
                for item in track.get(
                    "artists",
                    []
                )
            ]

            requested_artist_matched = any(
                normalized_requested_artist
                == result_artist
                for result_artist
                in normalized_result_artists
            )

        used_fallback = (
            search_method
            != "strict title and artist"
            if cleaned_artist
            else False
        )

        confirmation = (
            f"Playing {track_name}"
        )

        if artist_names:
            confirmation += (
                f" by {artist_names}"
            )

        if (
            cleaned_artist
            and (
                used_fallback
                or not requested_artist_matched
            )
        ):
            confirmation += (
                ". I used Spotify's top matching "
                "result because the requested artist "
                "was not an exact match"
            )

        confirmation += "."

        return {
            "action": "play",
            "confirmation": confirmation,
            "requested_song": song,
            "requested_artist": cleaned_artist,
            "track_name": track_name,
            "artist_names": artist_names,
            "album_name": album_name,
            "release_date": release_date,
            "popularity": popularity,
            "spotify_uri": track_uri,
            "search_method": search_method,
            "used_fallback": used_fallback,
            "requested_artist_matched": (
                requested_artist_matched
            ),
        }

    def pause(self):
        device_id = self._get_device_id()

        self.spotify.pause_playback(
            device_id=device_id,
        )

        return {
            "action": "pause",
            "confirmation":
                "Spotify playback paused.",
        }

    def resume(self):
        device_id = self._get_device_id()

        self.spotify.start_playback(
            device_id=device_id,
        )

        return {
            "action": "resume",
            "confirmation":
                "Resuming Spotify playback.",
        }

    def next_track(self):
        device_id = self._get_device_id()

        self.spotify.next_track(
            device_id=device_id,
        )

        time.sleep(0.7)

        current = self.get_current_track_info()

        return {
            "action": "next",
            "confirmation":
                "Skipping to the next track.",
            **current,
        }

    def previous_track(self):
        device_id = self._get_device_id()

        self.spotify.previous_track(
            device_id=device_id,
        )

        time.sleep(0.7)

        current = self.get_current_track_info()

        return {
            "action": "previous",
            "confirmation":
                "Returning to the previous track.",
            **current,
        }
    def restart_current_track(self):
        device_id = self._get_device_id()

        self.spotify.seek_track(
            position_ms=0,
            device_id=device_id,
        )

        return {
            "action": "restart",
            "confirmation": (
                "Restarting the current song."
            ),
        }
    def set_volume(self, volume):
        volume = max(
            0,
            min(
                100,
                int(volume),
            ),
        )

        device_id = self._get_device_id()

        self.spotify.volume(
            volume,
            device_id=device_id,
        )

        return {
            "action": "volume",
            "confirmation": (
                "Spotify volume set to "
                f"{volume} percent."
            ),
            "volume": volume,
        }
    def get_current_track_info(self):
        """
        Return structured information about the current track.
        """
        result = self.spotify.current_playback()

        if (
            not result
            or not result.get("item")
        ):
            return {
                "track_name": "",
                "artist_names": "",
                "album_name": "",
            }

        item = result["item"]

        artist_names = ", ".join(
            str(artist.get("name", "")).strip()
            for artist in item.get(
                "artists",
                []
            )
            if artist.get("name")
        )

        album = item.get(
            "album",
            {},
        )

        return {
            "track_name": str(
                item.get(
                    "name",
                    "",
                )
            ).strip(),
            "artist_names": artist_names,
            "album_name": str(
                album.get(
                    "name",
                    "",
                )
            ).strip(),
            "spotify_uri": str(
                item.get(
                    "uri",
                    "",
                )
            ).strip(),
        }
    def currently_playing(self):
        current = self.get_current_track_info()

        track_name = current.get(
            "track_name",
            "",
        )

        if not track_name:
            return {
                "action": "current",
                "confirmation": (
                    "Spotify is not currently "
                    "playing anything."
                ),
            }

        artist_names = current.get(
            "artist_names",
            "",
        )

        confirmation = (
            f"You are listening to {track_name}"
        )

        if artist_names:
            confirmation += (
                f" by {artist_names}"
            )

        confirmation += "."

        return {
            "action": "current",
            "confirmation": confirmation,
            **current,
        }
def clean_spotify_value(value):
    """Remove common filler words from a parsed Spotify command."""
    value = value.strip(" \t.,!?")

    value = re.sub(
        r"\s+(?:on|in|using)\s+spotify\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    return value.strip()


def handle_spotify_command(text, spotify_controller):
    """
    Process a Spotify command.

    Returns:
        None when the text is not a Spotify command.
        A response string when the command was handled.
    """
    normalized = text.lower().strip()

    # Play commands such as:
    # "play Numb by Linkin Park"
    # "play Bohemian Rhapsody from Queen"
    play_artist_match = re.match(
        r"^(?:please\s+)?play\s+(.+?)\s+(?:by|from)\s+(.+?)"
        r"(?:\s+on\s+spotify)?$",
        text.strip(),
        flags=re.IGNORECASE,
    )

    if play_artist_match:
        song = clean_spotify_value(
            play_artist_match.group(1)
        )
        artist = clean_spotify_value(
            play_artist_match.group(2)
        )

        return spotify_controller.play_song(
            song=song,
            artist=artist,
        )

    # More explicit fallback:
    # "play Space Oddity on Spotify"
    play_spotify_match = re.match(
        r"^(?:please\s+)?play\s+(.+?)\s+on\s+spotify$",
        text.strip(),
        flags=re.IGNORECASE,
    )

    if play_spotify_match:
        query = clean_spotify_value(
            play_spotify_match.group(1)
        )

        return spotify_controller.play_song(
            song=query,
        )
    # General request without explicitly saying "Spotify":
# "play Blinding Lights"
# "please play Bohemian Rhapsody"
    general_play_match = re.match(
        r"^(?:please\s+)?play\s+(.+?)$",
        text.strip(),
        flags=re.IGNORECASE,
    )

    if general_play_match:
        query = clean_spotify_value(
            general_play_match.group(1)
        )

        # Avoid treating playback-control phrases as song searches.
        reserved_commands = {
            "spotify",
            "the music",
            "music",
            "next song",
            "next track",
            "previous song",
            "previous track",
        }

        if (
            query.lower()
            not in reserved_commands
        ):
            return spotify_controller.play_song(
                song=query,
            )
    if normalized in {
        "pause spotify",
        "pause the music",
        "pause music",
        "stop spotify",
        "stop the music",
    }:
        return spotify_controller.pause()

    if normalized in {
        "resume spotify",
        "resume the music",
        "continue spotify",
        "continue the music",
        "play spotify",
    }:
        return spotify_controller.resume()

    if normalized in {
        "next song",
        "next track",
        "skip song",
        "skip this song",
        "skip this track",
    }:
        return spotify_controller.next_track()

    if normalized in {
        "previous song",
        "previous track",
        "go back a song",
        "restart the previous song",
        "go to the previous song", 
    }:
        return spotify_controller.previous_track()

    volume_match = re.match(
        r"^(?:set\s+)?spotify volume(?:\s+to)?\s+"
        r"(\d{1,3})(?:\s*percent)?$",
        normalized,
    )

    if volume_match:
        return spotify_controller.set_volume(
            int(volume_match.group(1))
        )

    if normalized in {
        "what song is playing",
        "what is playing",
        "what am i listening to",
        "what's playing on spotify",
    }:
        return spotify_controller.currently_playing()

    return None

def process_alice_message(
    user_text,
    *,
    alice_state,
    spotify_controller,
    response_language="english",
):
    """
    Process one Alice message independently of the UI.

    Returns a structured result that can be used by
    the desktop interface, iOS API, or another client.
    """

    user_text = str(
        user_text or ""
    ).strip()

    if not user_text:
        return {
            "type": "error",
            "response": "Message cannot be empty.",
        }

    # ---------------------------------
    # Spotify
    # ---------------------------------
    try:
        spotify_result = handle_spotify_command(
            user_text,
            spotify_controller,
        )

    except (
        SpotifyException,
        RuntimeError,
        requests.RequestException,
        ValueError,
    ) as error:
        return {
            "type": "spotify",
            "action": "error",
            "response": (
                "I could not complete that "
                f"Spotify command. {error}"
            ),
        }

    if spotify_result is not None:

        if isinstance(
            spotify_result,
            dict,
        ):
            confirmation = str(
                spotify_result.get(
                    "confirmation",
                    "Spotify command completed.",
                )
            ).strip()

            action = str(
                spotify_result.get(
                    "action",
                    "",
                )
            ).strip()

        else:
            confirmation = str(
                spotify_result
            ).strip()

            action = ""

        return {
            "type": "spotify",
            "action": action,
            "response": confirmation,
            "spotify": spotify_result,
        }

    # ---------------------------------
    # Normal Alice conversation
    # ---------------------------------
    reply = get_ai_response(
        user_text=user_text,
        alice_lore=alice_lore,
        alice_state=alice_state,
        response_language=response_language,
    )

    alice_state["mood"] = reply.get(
        "mood",
        "calm",
    )

    alice_state["last_topic"] = user_text

    save_alice_state(
        alice_state
    )

    english = str(
        reply.get(
            "english",
            "",
        )
    ).strip()

    japanese = str(
        reply.get(
            "japanese",
            "",
        )
    ).strip()

    emoticon = str(
        reply.get(
            "emoticon",
            "",
        )
    ).strip()

    displayed_text = english

    if emoticon:
        displayed_text += f" {emoticon}"

    return {
        "type": "conversation",
        "response": displayed_text,
        "english": english,
        "japanese": japanese,
        "mood": reply.get(
            "mood",
            "calm",
        ),
        "emoticon": emoticon,
        "motion_intent": reply.get(
            "motion_intent",
            "",
        ),
        "expects_answer": reply.get(
            "expects_answer",
            False,
        ),
    }
def generate_spotify_commentary(
    spotify_result,
    *, 
    music_profile=None, 
) -> dict:
    """
    Generate bilingual commentary for a Spotify track.

    English is always used in the chat interface.
    The selected language controls only spoken audio.
    """
    fallback = {
        "english": "",
        "japanese": "",
        "emoticon": "🙂",
    }

    if not isinstance(
        spotify_result,
        dict,
    ):
        return fallback

    if (
        spotify_result.get("action")
        not in {
            "play",
            "next",
            "previous",
            "current",
        }
    ):
        return fallback

    track_name = str(
        spotify_result.get(
            "track_name",
            "",
        )
    ).strip()

    artist_names = str(
        spotify_result.get(
            "artist_names",
            "",
        )
    ).strip()

    album_name = str(
        spotify_result.get(
            "album_name",
            "",
        )
    ).strip()

    release_date = str(
        spotify_result.get(
            "release_date",
            "",
        )
    ).strip()

    used_fallback = bool(
        spotify_result.get(
            "used_fallback",
            False,
        )
    )

    if not track_name:
        return fallback
    if music_profile is None:
        music_profile = (
            load_music_profile()
        )

    profile_context = (
        build_music_profile_context(
            music_profile
        )
    )

    manual_requests = (
        profile_context[
            "manual_requests"
        ]
    )

    recent_tracks = (
        profile_context[
            "recent_tracks"
        ]
    )

    top_artists = (
        profile_context[
            "top_artists"
        ]
    )

    top_albums = (
        profile_context[
            "top_albums"
        ]
    )

    top_decades = (
        profile_context[
            "top_decades"
        ]
    )
    commentary_angles = [
        "notice a repeated artist or track",
        "compare this selection with recent choices",
        "comment on the album or release period",
        "express mild curiosity about the choice",
        "give a restrained personal reaction",
    ]

    commentary_angle = random.choice(
        commentary_angles
    )
    prompt = f"""
    Alice has just selected a Spotify song for the user.

    Verified current-track metadata:
    - Track: {track_name}
    - Artist: {artist_names or "Unknown"}
    - Album: {album_name or "Unknown"}
    - Release date: {release_date or "Unknown"}
    - Fallback search used: {used_fallback}

    Observed listening evidence:
    - Number of explicit song requests recorded:
    {manual_requests}
    - Recent tracks:
    {json.dumps(recent_tracks, ensure_ascii=False)}
    - Most frequently requested or encountered artists:
    {json.dumps(top_artists, ensure_ascii=False)}
    - Most frequent albums:
    {json.dumps(top_albums, ensure_ascii=False)}
    - Most frequent release decades:
    {json.dumps(top_decades, ensure_ascii=False)}

    Write one natural, concise reaction in Alice's voice.

    Rules:
    - English must be suitable for the visible chat.
    - Japanese must communicate the same meaning naturally.
    - Use one or two sentences at most.
    - Do not merely repeat the track and artist.
    - Vary the type of reaction between:
    observation, comparison, recognition of a pattern,
    light curiosity, or a brief personal reaction.
    - Do not say "great choice" or "nice choice" by default.
    - Do not use generic phrases such as:
    "This song has a unique sound,"
    "This is an interesting track,"
    or "I hope you enjoy it."
    - Mention a listening pattern only when the recorded
    evidence reasonably supports it.
    - Require at least three explicit requests before saying
    the user appears to favor an artist, album, or decade.
    - Say "you may be developing a preference for..." rather
    than claiming certainty from limited evidence.
    - Never invent genre, instrumentation, lyrics, mood,
    tempo, or cultural significance from metadata alone.
    - Do not claim the user likes a song merely because it
    appeared through Next or Current.
    - A repeated artist or track may be acknowledged.
    - If there is not enough history, react specifically to
    the verified artist, album, release date, or the fact
    that this is a new selection.
    - Return exactly one emoticon fitting the reaction.
    - Preferred angle for this response:
        {commentary_angle}
    Return valid JSON only:

    {{
    "english": "English commentary",
    "japanese": "日本語のコメント",
    "emoticon": "🎵"
    }}
    """

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write brief bilingual Spotify "
                        "commentary using only supplied metadata."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            format="json",
            options={
                "temperature": 0.35,
                "num_predict": 140,
            },
        )

        raw_result = str(
            response["message"]["content"]
        ).strip()

        result = json.loads(
            raw_result
        )

        english = str(
            result.get(
                "english",
                "",
            )
        ).strip()

        japanese = str(
            result.get(
                "japanese",
                "",
            )
        ).strip()

        emoticon = str(
            result.get(
                "emoticon",
                "",
            )
        ).strip()

        if not english:
            return fallback

        if not japanese:
            japanese = english

        valid_emoticons = {
            "🙂",
            "😊",
            "😌",
            "🤔",
            "😮",
            "✨",
            "🎵",
            "🎶",
            "(´• ω •`)",
            "(＾▽＾)",
            "(￣▽￣)",
        }

        if emoticon not in valid_emoticons:
            emoticon = "🎵"

        return {
            "english": english,
            "japanese": japanese,
            "emoticon": emoticon,
        }

    except (
        ollama.ResponseError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as ex:
        print(
            "Spotify commentary error: "
            f"{type(ex).__name__}: {ex}"
        )

        return fallback

def parse_todo_command(
    text: str,
) -> dict | None:
    """
    Parse user commands that modify the browser-based todo list.
    """
    original_text = str(
        text or ""
    ).strip()

    normalized = normalize_command(
        original_text
    )
    non_todo_add_phrases = (
        "add a new skill",
        "add a skill",
        "add this skill",
        "create a new skill",
        "create a skill",
        "build a new skill",
        "make a new skill",
        "add a feature",
        "create a feature",
        "implement a feature",
        "update your code",
        "modify your code",
    )

    if any(
        phrase in normalized
        for phrase in non_todo_add_phrases
    ):
        return None
    open_commands = {
        "open todo list",
        "open my todo list",
        "show todo list",
        "show my todo list",
        "view todo list",
    }

    if normalized in open_commands:
        return {
            "action": "open",
        }
    briefing_commands = {
        "brief me on my todo list",
        "brief me on the todo list",
        "give me a todo list briefing",
        "give me a briefing of my todo list",
        "give me a briefing of the todo list",
        "what is on my todo list",
        "what's on my todo list",
        "what do i have on my todo list",
        "read my todo list",
        "read the todo list",
        "list my tasks",
        "show me my tasks",
        "summarize my todo list",
        "todo list briefing",
    }

    if normalized in briefing_commands:
        return {
            "action": "brief",
        }
    add_match = re.match(
        r"^(?:please\s+)?"
        r"(?:add|put|create)\s+"
        r"(.+?)\s+"
        r"(?:to|on)\s+(?:my\s+)?"
        r"(?:todo|to do)\s+list$",
        original_text,
        flags=re.IGNORECASE,
    )
    if not add_match:
        add_match = re.match(
            r"^(?:todo|to do)\s+"
            r"(?:add|put|create)\s+"
            r"(.+?)$",
            original_text,
            flags=re.IGNORECASE,
        )

    if add_match:
        task_text = (
            add_match.group(1)
            .strip(" \t.,!?")
        )

        if task_text:
            return {
                "action": "add",
                "text": task_text,
            }

    complete_match = re.match(
        r"^(?:please\s+)?"
        r"(?:complete|finish|check|"
        r"check off|cross off|mark done)\s+"
        r"(.+?)"
        r"(?:\s+(?:on|from)\s+(?:my\s+)?"
        r"(?:todo|to do)\s+list)?$",
        original_text,
        flags=re.IGNORECASE,
    )

    if complete_match:
        task_text = (
            complete_match.group(1)
            .strip(" \t.,!?")
        )

        if task_text:
            return {
                "action": "complete",
                "text": task_text,
            }

    remove_match = re.match(
        r"^(?:please\s+)?"
        r"(?:remove|delete|erase)\s+"
        r"(.+?)"
        r"(?:\s+from\s+(?:my\s+)?"
        r"(?:todo|to do)\s+list)?$",
        original_text,
        flags=re.IGNORECASE,
    )

    if remove_match:
        task_text = (
            remove_match.group(1)
            .strip(" \t.,!?")
        )

        if task_text:
            return {
                "action": "remove",
                "text": task_text,
            }

    if normalized in {
        "clear completed tasks",
        "remove completed tasks",
        "delete completed tasks",
    }:
        return {
            "action": "clear_completed",
        }

    if normalized in {
        "clear todo list",
        "clear my todo list",
        "delete all tasks",
        "remove all tasks",
    }:
        return {
            "action": "clear_all",
        }

    return None

def process_pending_todo_briefing(
    *,
    display,
    bridge,
    speaker_id,
) -> bool:
    """
    Speak one pending todo briefing.

    Returns True when a briefing was processed.
    """
    web_server = display.web_server

    if web_server is None:
        return False

    briefing_queue = getattr(
        web_server,
        "todo_briefing_queue",
        None,
    )

    if briefing_queue is None:
        return False

    try:
        briefing_payload = (
            briefing_queue.get_nowait()
        )

    except queue.Empty:
        return False

    if isinstance(
        briefing_payload,
        dict,
    ):
        displayed_text = str(
            briefing_payload.get(
                "english",
                briefing_payload.get(
                    "text",
                    "",
                ),
            )
        ).strip()

        japanese_text = str(
            briefing_payload.get(
                "japanese",
                "",
            )
        ).strip()

    else:
        displayed_text = str(
            briefing_payload or ""
        ).strip()

        japanese_text = ""

    if not displayed_text:
        return False

    language = bridge.get_language()

    spoken_text = choose_spoken_text(
        language=language,
        english_text=displayed_text,
        japanese_text=japanese_text,
        english_fallback=displayed_text,
        japanese_fallback=(
            "予定表の内容を取得しました。"
        ),
    )

    display.set_state(
        "thinking",
        "Preparing Todo Briefing",
        "Preparing the current task list...",
    )

    try:
        speak_alice_text(
            spoken_text=spoken_text,
            displayed_text=displayed_text,
            language=language,
            speaker_id=speaker_id,
            display=display,
            status_text="Reading Todo List",
        )

    except Exception as error:
        print(
            "Todo briefing speech error:",
            error,
        )

        display.set_state(
            "listening",
            "Todo Briefing Error",
            str(error),
        )

        return False

    return True
def run_alice(display, bridge): 
    
    #test_typecast()
    global alice_lore
    vision = AliceVision(
        camera_index=0
    )
    vision.save_screen_capture_test()
    # result = vision.analyze_screen()
    # print("Screen Analysis Result:")
    # print(
    #     json.dumps(
    #         result, 
    #         indent=2, 
    #         ensure_ascii=False, 
    #     )
    # )
    spotify_controller = AliceSpotify() 
    alice_state = load_alice_state()
    alice_state["session_count"] += 1 
    save_alice_state(alice_state)
    alice_lore = load_alice_lore()
    load_memory()
    warm_up_ollama()
    
    try:
        speaker_id = get_speaker_id(
            CHARACTER_NAME
        )
    except (
        requests.RequestException,
        ValueError,
    ) as ex:
        print(f"VOICEVOX startup error: {ex}")
        print(
            "Make sure VOICEVOX is open "
            "and its engine is running."
        )
        return
    screen_observer = AliceScreenObserver(
        vision=vision, 
        on_observation=lambda observation: 
            handle_screen_observation(
                observation=observation, 
                display=display, 
                bridge=bridge, 
                speaker_id=speaker_id, 
            ), 
    )
    screen_observer.start()
    screen_observer.suppress_comments_for(
        30
    )
    recognizer = sr.Recognizer()
    try:
        microphone = sr.Microphone()

    except Exception as ex:
        print(
            f"Microphone startup error: {ex}"
        )

        if screen_observer.running:
            screen_observer.stop()

        vision.close()
        return

    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8
    recognizer.non_speaking_duration = 0.5

    calibrate_microphone(
        recognizer,
        microphone,
    )

    print(
        f"Using VOICEVOX speaker ID "
        f"{speaker_id} for {CHARACTER_NAME}"
    )
    print("Alice is running...")
    if bridge.get_mode() == "silent": 
        display.set_state(
            "listening", 
            "Sleeping", 
            "Type a message.",
        )
    else: 
        display.set_state(
        "sleeping", 
        "Sleeping", 
        "Say 'Hey Alice' to wake me.",
    )
    print("Say 'Hey Alice' to begin a conversation.")
    print("Say 'goodbye' to put Alice back to sleep.")
    print("Say 'shut down Alice' to close the program.")

    startup_display_text = (
        "Welcome back, Mercy. (＾▽＾)"
    )

    startup_spoken_text = (
        "おかえりなさい、マーシー。"
    )

    display.append_message(
        "alice",
        startup_display_text,
    )

    try:
        speak_alice_text(
            spoken_text=startup_spoken_text,
            displayed_text=startup_display_text,

            # Startup greeting always uses VOICEVOX.
            language="japanese",

            speaker_id=speaker_id,
            display=display,
            status_text="Welcome",
        )

    except (
        requests.RequestException,
        RuntimeError,
        ValueError,
    ) as ex:
        print(
            f"Startup greeting error: {ex}"
        )

    program_running = True

    while(
        program_running
        and not bridge.shutdown_requested()
    ): 
        try:
            # -----------------------------------------
            # WAITING / SLEEPING
            # -----------------------------------------
            action, first_question = (
                wait_for_wake_phrase(
                    recognizer,
                    microphone,
                    bridge,
                )
            )

            if action == "shutdown":
                print("Alice is shutting down...")

                display.set_state(
                    "sleeping",
                    "System Offline",
                    "Closing Alice...",
                )

                alice_state["awake"] = False
                save_alice_state(alice_state)
                save_memory()

                program_running = False
                continue

            alice_state["awake"] = True
            save_alice_state(alice_state)

            # Speak Alice's wake response using the
            # currently selected language.
            wake_language = bridge.get_language()
            should_play_wake_response = not(
                bridge.get_mode() == "silent"
                and first_question 
            )
            if should_play_wake_response: 

                if wake_language == "english":
                    wake_text = (
                        "Yes, Mercy. I am listening."
                    )
                else:
                    wake_text = (
                        "はい、マーシー。"
                        "聞いています。"
                    )

                try:
                    speak_alice_text(
                        spoken_text=wake_text,
                        displayed_text = wake_text, 
                        language=wake_language,
                        speaker_id=speaker_id,
                        display=display,
                        status_text="Speaking",
                    )
                except Exception as ex:
                    print(
                        f"Wake speech error: {ex}"
                    )

            display.set_state(
                "listening",
                "Listening",
                (
                    "Type your message."
                    if bridge.get_mode() == "silent"
                    else "I am ready."
                ), 
            )
            
            conversation_active = True
            pending_question = first_question 
            # -----------------------------------------
            # ACTIVE CONVERSATION
            # -----------------------------------------
            while(
                conversation_active
                and not bridge.shutdown_requested()
            ):
                process_pending_todo_briefing(
                    display=display,
                    bridge=bridge, 
                    speaker_id=speaker_id, 
                )
                if pending_question:
                    user_text = pending_question
                    pending_question = None
                    print(f"You: {user_text}")
                else:
                    user_text = get_next_user_message(
                        recognizer,
                        microphone,
                        bridge,
                    )
                if bridge.shutdown_requested(): 
                    conversation_active = False
                    program_running = False
                    break 
                if not user_text:
                    continue
                try:
                    skill_result = (
                        skill_runtime.handle(
                            user_text,
                            {
                                "display": display,
                                "bridge": bridge,
                                "project_root": BASE_DIR,
                            },
                        )
                    )

                except Exception as error:
                    print(
                        "Installed skill failed:",
                        f"{type(error).__name__}: {error}",
                    )

                    skill_result = {
                        "handled": True,
                        "english": (
                            "The installed skill encountered "
                            f"an error: {error}"
                        ),
                        "japanese": (
                            "インストールされたスキルで"
                            "エラーが発生しました。"
                        ),
                    }

                if skill_result is not None:
                    english_text = str(
                        skill_result.get(
                            "english",
                            "",
                        )
                    ).strip()

                    japanese_text = str(
                        skill_result.get(
                            "japanese",
                            "",
                        )
                    ).strip()

                    if not english_text:
                        english_text = (
                            "The skill completed without "
                            "returning a message."
                        )

                    language = bridge.get_language()

                    spoken_text = choose_spoken_text(
                        language=language,
                        english_text=english_text,
                        japanese_text=japanese_text,
                        english_fallback=english_text,
                        japanese_fallback=(
                            "スキルの処理が完了しました。"
                        ),
                    )

                    display.append_message(
                        "alice",
                        english_text,
                    )

                    try:
                        speak_alice_text(
                            spoken_text=spoken_text,
                            displayed_text=english_text,
                            language=language,
                            speaker_id=speaker_id,
                            display=display,
                            status_text="Using Skill",
                        )

                    except Exception as error:
                        print(
                            "Skill speech error:",
                            error,
                        )

                    continue
                is_improvement_request = (
                    is_improvement_proposal_command(
                        user_text
                    )
                    or is_proposal_revision_command(
                        user_text
                    )
                    or get_improvement_action(
                        user_text
                    ) is not None
                )
                todo_command = None 
                if not is_improvement_request: 
                    todo_command = (
                        parse_todo_command(
                            user_text
                        )
                    )

                if todo_command is not None:
                    published = (
                        display.publish_todo_command(
                            todo_command
                        )
                    )

                    action = todo_command.get(
                        "action",
                        "",
                    )
                    if action == "brief":
                        if not published:
                            display.append_message(
                                "alice",
                                (
                                    "I could not reach the "
                                    "todo-list interface."
                                ),
                            )

                            display.set_state(
                                "listening",
                                "Todo List Unavailable",
                                "The browser interface could not be reached.",
                            )

                            continue

                        display.set_state(
                            "thinking",
                            "Reading Todo List",
                            "Collecting your current tasks...",
                        )

                        briefing_deadline = (
                            time.time()
                            + 5.0
                        )

                        briefing_processed = False

                        while time.time() < briefing_deadline:
                            briefing_processed = (
                                process_pending_todo_briefing(
                                    display=display,
                                    bridge=bridge,
                                    speaker_id=speaker_id,
                                )
                            )

                            if briefing_processed:
                                break

                            time.sleep(
                                0.05
                            )

                        if not briefing_processed:
                            display.append_message(
                                "alice",
                                (
                                    "I requested your todo list, "
                                    "but did not receive the briefing."
                                ),
                            )

                            display.set_state(
                                "listening",
                                "Todo Briefing Timeout",
                                "The browser did not return the task list.",
                            )

                        continue

                    task_text = str(
                        todo_command.get(
                            "text",
                            "",
                        )
                    ).strip()

                    if not published:
                        todo_response = (
                            "I could not reach the todo-list interface."
                        )

                    elif action == "open":
                        todo_response = (
                            "I opened your todo list."
                        )

                    elif action == "add":
                        todo_response = (
                            f'I sent “{task_text}” '
                            "to your todo list."
                        )

                    elif action == "complete":
                        todo_response = (
                            f'I sent a request to mark “{task_text}” complete.'
                        )

                    elif action == "remove":
                        todo_response = (
                            f'I sent a request to remove “{task_text}” '
                            "from your todo list."
                        )

                    elif action == "clear_completed":
                        todo_response = (
                            "I removed the completed tasks."
                        )

                    elif action == "clear_all":
                        todo_response = (
                            "I cleared the todo list."
                        )

                    else:
                        todo_response = (
                            "I updated your todo list."
                        )

                    display.append_message(
                        "alice",
                        todo_response,
                    )

                    response_language = (
                        bridge.get_language()
                    )

                    spoken_response = (
                        todo_response
                        if response_language == "english"
                        else "予定表を更新しました。"
                    )

                    try:
                        speak_alice_text(
                            spoken_text=spoken_response,
                            displayed_text=todo_response,
                            language=response_language,
                            speaker_id=speaker_id,
                            display=display,
                            status_text="Updating Todo List",
                        )

                    except Exception as error:
                        print(
                            "Todo response speech error:",
                            error,
                        )

                    display.set_state(
                        "listening",
                        "Listening",
                        "You may continue.",
                    )

                    continue
                # -------------------------------------
                # PERMISSION-GATED SELF-IMPROVEMENT
                # -------------------------------------
                improvement_action = (
                    get_improvement_action(
                        user_text
                    )
                )

                # Staging and installation approvals are handled below by the
                # full proposal -> generate -> stage -> validate -> install
                # workflow. Only non-overlapping actions are handled here.
                if improvement_action == "reject":
                    try:
                        self_improvement.reject_active_proposal(
                            reason="Rejected by user."
                        )
                        response_text = (
                            "The active improvement proposal was scrapped."
                        )
                    except Exception as error:
                        response_text = (
                            "I could not reject the active proposal: "
                            f"{error}"
                        )

                    display.append_message(
                        "alice",
                        response_text,
                    )
                    continue

                if improvement_action == "show":
                    try:
                        result = (
                            self_improvement
                            .get_active_proposal()
                        )
                        response_text = (
                            json.dumps(
                                result,
                                indent=2,
                            )
                            if result
                            else (
                                "There is no active "
                                "improvement proposal."
                            )
                        )
                    except Exception as error:
                        response_text = (
                            "I could not read the active proposal: "
                            f"{error}"
                        )

                    display.append_message(
                        "alice",
                        response_text,
                    )
                    continue

                if is_proposal_revision_command(
                    user_text
                ):
                    display.set_state(
                        "thinking",
                        "Revising Improvement",
                        "Updating the active proposal...",
                    )

                    try:
                        active_proposal = (
                            self_improvement
                            .get_active_proposal()
                        )

                        if not isinstance(
                            active_proposal,
                            dict,
                        ):
                            raise RuntimeError(
                                "There is no active proposal to revise."
                            )

                        revision_request = f"""
                        Revise the existing proposal.

                        Existing proposal:
                        {json.dumps(
                            active_proposal,
                            ensure_ascii=False,
                            indent=2,
                        )}

                        User revision:
                        {user_text}

                        Preserve the original requested capability unless the user
                        explicitly changes it.

                        The user's latest file-type requirement is mandatory.
                        """

                        proposal_data = (
                            generate_improvement_proposal(
                                revision_request, 
                                constraint_request=user_text
                            )
                        )

                        revised = (
                            self_improvement
                            .revise_active_proposal(
                                title=proposal_data.get(
                                    "title",
                                    "Alice improvement",
                                ),
                                description=proposal_data.get(
                                    "description",
                                    "",
                                ),
                                skill_name=proposal_data.get(
                                    "skill_name",
                                    "New capability",
                                ),
                                requested_files=proposal_data.get(
                                    "requested_files",
                                    [],
                                ),
                                acceptance_tests=proposal_data.get(
                                    "acceptance_tests",
                                    [],
                                ),
                                risks=proposal_data.get(
                                    "risks",
                                    [],
                                ),
                                requires_restart=proposal_data.get(
                                    "requires_restart",
                                    True,
                                ),
                            )
                        )

                        proposal_message = (
                            "Revised proposal: "
                            f"{revised['title']}\n\n"
                            f"{revised['description']}\n\n"
                            "Files requested:\n"
                            + "\n".join(
                                f"- {path}"
                                for path in revised[
                                    "requested_files"
                                ]
                            )
                            + "\n\nThe proposal has been reset "
                            "to the proposed state. Type "
                            "“approve staging” to continue."
                        )
                        if display.web_server is not None:
                            display.web_server.publish_event(
                                {
                                    "type": "improvement_proposal",
                                    "data": revised,
                                }
                            )

                    except Exception as error:
                        proposal_message = (
                            "I could not revise the proposal: "
                            f"{error}"
                        )

                    display.append_message(
                        "alice",
                        proposal_message,
                    )
                    
                    display.set_state(
                        "listening",
                        "Approval Required",
                        "Review the revised proposal.",
                    )

                    continue

                if is_improvement_proposal_command(
                    user_text
                ):
                    display.set_state(
                        "thinking",
                        "Planning Improvement",
                        "Preparing a proposal only...",
                    )

                    proposal = None

                    try:
                        proposal_data = (
                            generate_improvement_proposal(
                                user_text
                            )
                        )

                        proposal = (
                            self_improvement.create_proposal(
                                title=proposal_data.get(
                                    "title",
                                    "Alice improvement",
                                ),
                                description=proposal_data.get(
                                    "description",
                                    "",
                                ),
                                skill_name=proposal_data.get(
                                    "skill_name",
                                    "New capability",
                                ),
                                requested_files=proposal_data.get(
                                    "requested_files",
                                    [],
                                ),
                                acceptance_tests=proposal_data.get(
                                    "acceptance_tests",
                                    [],
                                ),
                            )
                        )

                        risks = proposal_data.get(
                            "risks",
                            [],
                        )

                        proposal_message = (
                            "Improvement proposal: "
                            f"{proposal['title']}\n\n"
                            f"{proposal['description']}\n\n"
                            "Files requested:\n"
                            + "\n".join(
                                f"- {path}"
                                for path in proposal[
                                    "requested_files"
                                ]
                            )
                            + "\n\nAcceptance tests:\n"
                            + "\n".join(
                                f"- {test}"
                                for test in proposal[
                                    "acceptance_tests"
                                ]
                            )
                            + "\n\nRisks:\n"
                            + "\n".join(
                                f"- {risk}"
                                for risk in risks
                            )
                            + "\n\nNo files have been changed."
                            "\nType “approve staging” to allow "
                            "Alice to create an isolated patch."
                        )

                        if display.web_server is not None:
                            display.web_server.publish_event(
                                {
                                    "type": (
                                        "improvement_proposal"
                                    ),
                                    "data": proposal,
                                }
                            )

                    except Exception as error:
                        proposal_message = (
                            "I could not create a safe "
                            f"improvement proposal: {error}"
                        )

                    display.append_message(
                        "alice",
                        proposal_message,
                    )

                    display.set_state(
                        "listening",
                        "Approval Required",
                        "Review the proposal before staging.",
                    )

                    continue
                if is_stage_approval_command(
                    user_text
                ):
                    validated = None
                    state = self_improvement.load_state()
                    proposal = state.get(
                        "active_proposal"
                    )

                    if not isinstance(
                        proposal,
                        dict,
                    ):
                        display.append_message(
                            "alice",
                            "There is no active improvement "
                            "proposal to approve.",
                        )
                        display.set_state(
                            "listening",
                            "No Active Proposal",
                            "Create or revise a proposal first.",
                        )
                        continue

                    try:
                        proposal_state = str(
                            proposal.get(
                                "state",
                                "",
                            )
                        ).strip()

                        display.set_state(
                            "thinking",
                            "Preparing Staging",
                            (
                                "Approving the proposal and "
                                "preparing source context..."
                            ),
                        )
                        display.publish_improvement_progress(
                            state="preparing",
                            progress=10,
                            message=(
                                "Approving the proposal and "
                                "preparing source context."
                            ),
                        )

                        if proposal_state == "proposed":
                            self_improvement.approve_staging(
                                proposal["proposal_id"]
                            )

                        elif proposal_state != "staging_approved":
                            raise RuntimeError(
                                "Staging can only begin from "
                                "'proposed' or resume from "
                                "'staging_approved'. Current state: "
                                f"{proposal_state!r}."
                            )

                        approved_proposal = (
                            self_improvement
                            .load_state()[
                                "active_proposal"
                            ]
                        )

                        display.append_message(
                            "alice",
                            (
                                "Staging approved. I am now "
                                "generating the approved code changes."
                            ),
                        )

                        display.set_state(
                            "thinking",
                            "Generating Code",
                            (
                                "Creating complete replacement files "
                                "inside the isolated staging area..."
                            ),
                        )
                        display.publish_improvement_progress(
                            state="generating",
                            progress=25,
                            message=(
                                "Ollama is generating the "
                                "approved replacement files."
                            ),
                        )

                        print(
                            "Self-improvement: generating files for",
                            approved_proposal.get(
                                "requested_files",
                                [],
                            ),
                        )

                        def publish_file_generation_progress(
                            relative_path,
                            file_index,
                            total_files,
                        ):
                            file_fraction = (
                                file_index - 1
                            ) / max(
                                total_files,
                                1,
                            )

                            progress_value = (
                                25
                                + file_fraction * 30
                            )

                            display.publish_improvement_progress(
                                state="generating",
                                progress=progress_value,
                                message=(
                                    f"Generating file {file_index} "
                                    f"of {total_files}."
                                ),
                                current_file=relative_path,
                            )


                        generated_files = (
                            generate_staged_improvement_files(
                                approved_proposal,
                                progress_callback=(
                                    publish_file_generation_progress
                                ),
                            )
                        )

                        display.set_state(
                            "thinking",
                            "Writing Staged Files",
                            "Saving the generated files in isolation...",
                        )
                        display.publish_improvement_progress(
                            state="staging_files",
                            progress=60,
                            message=(
                                "Writing generated files into "
                                "the isolated staging directory."
                            ),
                        )

                        print(
                            "Self-improvement: generated paths:",
                            [
                                item.get("path")
                                for item in generated_files
                                if isinstance(
                                    item,
                                    dict,
                                )
                            ],
                        )

                        staged = (
                            self_improvement.stage_files(
                                generated_files
                            )
                        )

                        display.set_state(
                            "thinking",
                            "Validating Update",
                            (
                                "Running syntax and safety checks "
                                "before installation can be approved..."
                            ),
                        )
                        display.publish_improvement_progress(
                            state="validating",
                            progress=75,
                            message=(
                                "Running syntax, safety, and "
                                "acceptance checks."
                            ),
                        )

                        validated = (
                            self_improvement.validate_staged()
                        )

                        validation_lines = [
                            (
                                f"- {item['path']}: "
                                f"{'passed' if item['success'] else 'failed'}"
                                f"\n  {item['output']}"
                            )
                            for item in validated[
                                "validation"
                            ]
                        ]

                        diff_preview = "\n\n".join(
                            (
                                f"--- {path} ---\n"
                                f"{diff[:6000]}"
                            )
                            for path, diff in validated[
                                "diffs"
                            ].items()
                        )

                        if (
                            validated["state"]
                            == "validated"
                        ):
                            display.publish_improvement_progress(
                                state="validated",
                                progress=90,
                                message=(
                                    "Validation passed. Installation "
                                    "approval is required."
                                ),
                            )
                            next_instruction = (
                                "\n\nAll configured checks passed."
                                "\nType “approve installation” "
                                "to install this staged update."
                            )
                        else:
                            display.publish_improvement_progress(
                                state="validation_failed",
                                progress=100,
                                message=(
                                    "Validation failed. Installation "
                                    "has been blocked."
                                ),
                            )
                            next_instruction = (
                                "\n\nValidation failed. "
                                "Installation is blocked."
                            )

                        staging_message = (
                            "Staging and validation results:\n\n"
                            + "\n".join(
                                validation_lines
                            )
                            + "\n\nProposed diff:\n"
                            + diff_preview
                            + next_instruction
                        )

                    except Exception as error:
                        try: 
                            self_improvement.record_staging_failure(
                                f"{type(error).__name__}: {error}"
                            )
                        except Exception as record_error: 
                            print(
                                "Counld not record staging failure:", 
                                type(record_error).__name__, 
                                record_error, 
                            )
                        staging_message = (
                            "The staged improvement failed: "
                            f"{error}"
                        )
                        display.publish_improvement_progress(
                            state="generation_failed",
                            progress=100,
                            message=str(error),
                        )

                        display.set_state(
                            "listening",
                            "Staging Failed",
                            str(error),
                        )

                        print(
                            "Self-improvement staging error:",
                            type(error).__name__,
                            error,
                        )

                    display.append_message(
                        "alice",
                        staging_message,
                    )

                    if (
                        isinstance(
                            validated if "validated" in locals() else None,
                            dict,
                        )
                        and validated.get("state") == "validated"
                    ):
                        display.set_state(
                            "listening",
                            "Installation Approval Required",
                            (
                                "Review the diff, then type "
                                "'approve installation'."
                            ),
                        )
                    elif (
                        isinstance(
                            validated if "validated" in locals() else None,
                            dict,
                        )
                        and validated.get("state")
                        == "validation_failed"
                    ):
                        display.set_state(
                            "listening",
                            "Validation Failed",
                            "Revise the proposal before installation.",
                        )

                    continue
                if is_install_approval_command(
                    user_text
                ):
                    state = self_improvement.load_state()
                    proposal = state.get(
                        "active_proposal"
                    )

                    if not isinstance(
                        proposal,
                        dict,
                    ):
                        display.append_message(
                            "alice",
                            "There is no validated update "
                            "waiting for installation.",
                        )
                        continue

                    try:
                        self_improvement.approve_installation(
                            proposal["proposal_id"]
                        )

                        installed = (
                            self_improvement.install()
                        )

                        skill_name = installed.get(
                            "skill_name",
                            "New Alice capability",
                        )
                        display.publish_improvement_progress(
                            state="installed",
                            progress=100,
                            message=(
                                f'The skill "{skill_name}" was installed '
                                "and registered successfully."
                            ),
                        )

                        installation_message = (
                            f"The skill “{skill_name}” "
                            "was installed successfully. "
                            "Restart Alice to load any changed "
                            "Python modules."
                        )
                        last_generation_content = (
                            generated_content
                        )

                        display.append_message(
                            "alice",
                            installation_message,
                        )

                        if display.web_server is not None:
                            display.web_server.publish_skill_installed(
                                {
                                    "title": "New skill installed",
                                    "skill_name": skill_name,
                                    "description": installed.get(
                                        "description",
                                        "",
                                    ),
                                    "changed_files": installed.get(
                                        "staged_files",
                                        [],
                                    ),
                                    "requires_restart": True,
                                }
                            )

                    except Exception as error:
                        display.append_message(
                            "alice",
                            "The update was not installed: "
                            f"{error}",
                        )

                    continue
                if not user_text:
                    continue


                if is_code_review_command(
                    user_text
                ):
                    relative_path = extract_code_review_file(
                        user_text
                    )

                    if relative_path is None:
                        available_files = (
                            list_reviewable_project_files()
                        )

                        preview = "\n".join(
                            f"- {item}"
                            for item in available_files[:25]
                        )

                        code_response = (
                            "Please name the project file you want "
                            "me to review.\n\n"
                            "Examples:\n"
                            "- review alice.py\n"
                            "- check fluctlight.html\n"
                            "- inspect alice_web_server.py\n"
                            "- review electron-main.js\n\n"
                            "Available files include:\n"
                            f"{preview}"
                        )

                    else:
                        display.set_state(
                            "thinking",
                            "Reviewing Code",
                            f"Inspecting {relative_path}...",
                        )

                        code_response = review_code_file(
                            relative_path=relative_path,
                            user_request=user_text,
                        )

                    display.append_message(
                        "alice",
                        code_response,
                    )

                    response_language = (
                        bridge.get_language()
                    )

                    if response_language == "japanese":
                        spoken_summary = (
                            "コードを確認しました。"
                            "詳しい修正案をチャットに表示しました。"
                        )
                    else:
                        spoken_summary = (
                            f"I reviewed {relative_path or 'the project files'} "
                            "and placed the suggestions in the chat."
                        )

                    try:
                        speak_alice_text(
                            spoken_text=spoken_summary,
                            displayed_text=code_response,
                            language=response_language,
                            speaker_id=speaker_id,
                            display=display,
                            status_text="Code Review",
                        )

                    except Exception as error:
                        print(
                            f"Code review speech error: {error}"
                        )

                    display.set_state(
                        "listening",
                        "Listening",
                        "You may continue.",
                    )

                    continue
                # reset boredom/yawn timer when user input 
                screen_observer.mark_user_activity()
                try: 
                    display.window.evaluate_js(
                        """
                        if(
                            typeof window.markAliceActivity
                            === "function"
                        ){
                            window.markAliceActivity(); 
                        }
                        """
                    )
                except Exception: 
                    pass
                # -------------------------------------
                # FULL PROGRAM SHUTDOWN
                # -------------------------------------
                if is_shutdown_command(user_text):
                    print("Alice is shutting down.")

                    shutdown_language = (
                        bridge.get_language()
                    )

                    if shutdown_language == "english":
                        shutdown_text = (
                            "Understood. I will shut down now. "
                            "Goodbye."
                        )
                    else:
                        shutdown_text = (
                            "承知しました。"
                            "終了します。さようなら。"
                        )

                    try:
                        speak_alice_text(
                            spoken_text=shutdown_text,
                            displayed_text=shutdown_text, 
                            language=shutdown_language,
                            speaker_id=speaker_id,
                            display=display,
                            status_text="Speaking",
                        )
                    except Exception as ex:
                        print(
                            f"Shutdown speech error: {ex}"
                        )

                    save_memory()
                    conversation_active = False
                    program_running = False
                    continue

                # -------------------------------------
                # END CURRENT CONVERSATION
                # -------------------------------------
                if is_sleep_command(user_text):
                    print(
                        "Conversation ended. "
                        "Alice is waiting for the wake phrase."
                    )

                    sleep_language = (
                        bridge.get_language()
                    )

                    if sleep_language == "english":
                        sleep_text = (
                            "Understood. Call me again "
                            "when you would like to talk."
                        )
                    else:
                        sleep_text = (
                            "承知しました。"
                            "またお話ししたい時に"
                            "呼んでください。"
                        )

                    try:
                        speak_alice_text(
                            spoken_text=sleep_text,
                            displayed_text=sleep_text, 
                            language=sleep_language,
                            speaker_id=speaker_id,
                            display=display,
                            status_text="Speaking",
                        )
                    except Exception as ex:
                        print(
                            f"Sleep speech error: {ex}"
                        )

                    alice_state["awake"] = False
                    save_alice_state(alice_state)
                    save_memory()

                    

                    display.set_state(
                        "sleeping",
                        "Sleeping",
                        "Say 'Hey Alice' to wake me up.",
                    )
                    conversation_active = False
                    break
                # -------------------------------------
                # PRODUCT GUIDANCE CONVERSATION
                # -------------------------------------
                if has_active_product_context(
                    vision
                ):
                    product_stage = (
                        vision.product_conversation_stage
                    )

                    if (
                        product_stage
                        == "awaiting_permission"
                    ):
                        if is_affirmative_response(
                            user_text
                        ):
                            vision.product_conversation_stage = (
                                "awaiting_use_case"
                            )

                            product_name = (
                                vision.product_context.get(
                                    "product_name",
                                    "the product",
                                )
                            )

                            displayed_text = (
                                "Certainly. What are you "
                                f"planning to use {product_name} "
                                "for?"
                            )

                            spoken_text = displayed_text

                            if (
                                bridge.get_language()
                                == "japanese"
                            ):
                                spoken_text = (
                                    "承知しました。"
                                    "この製品を何に"
                                    "使う予定ですか？"
                                )

                            display.append_message(
                                "alice",
                                displayed_text,
                            )

                            speak_alice_text(
                                spoken_text=spoken_text,
                                displayed_text=displayed_text,
                                language=(
                                    bridge.get_language()
                                ),
                                speaker_id=speaker_id,
                                display=display,
                                status_text="Asking",
                            )

                            display.set_state(
                                "listening",
                                "Listening",
                                "Describe your project or use case.",
                            )

                            continue

                        if is_negative_response(
                            user_text
                        ):
                            vision.product_conversation_stage = (
                                "idle"
                            )

                            displayed_text = (
                                "Understood. I will leave "
                                "the product analysis there."
                            )

                            display.append_message(
                                "alice",
                                displayed_text,
                            )

                            continue

                    elif (
                        product_stage
                        == "awaiting_use_case"
                    ):
                        advice_result = (
                            vision.create_product_advice(
                                intended_use=user_text
                            )
                        )

                        english_text = str(
                            advice_result.get(
                                "english",
                                "",
                            )
                        ).strip()

                        japanese_text = str(
                            advice_result.get(
                                "japanese",
                                "",
                            )
                        ).strip()

                        advice_emoticon = str(
                            advice_result.get(
                                "emoticon",
                                "",
                            )
                        ).strip()
                        response_language = (
                            bridge.get_language()
                        )
                        displayed_text = (
                            choose_displayed_text(
                                english_text,
                                fallback=(
                                    "I could not prepare reliable "
                                    "product guidance."
                                ),
                            )
                        )

                        spoken_text = (
                            choose_spoken_text(
                                language=response_language,
                                english_text=english_text,
                                japanese_text=japanese_text,
                                english_fallback=(
                                    "I could not prepare reliable "
                                    "product guidance."
                                ),
                                japanese_fallback=(
                                    "信頼できる製品情報を"
                                    "用意できませんでした。"
                                ),
                            )
                        )

                        if advice_emoticon:
                            displayed_text = (
                                f"{displayed_text} "
                                f"{advice_emoticon}"
                            )

                        display.append_message(
                            "alice",
                            displayed_text,
                        )

                        speak_alice_text(
                            spoken_text=spoken_text,
                            displayed_text=displayed_text,
                            language=response_language,
                            speaker_id=speaker_id,
                            display=display,
                            status_text="Advising",
                        )

                        display.set_state(
                            "listening",
                            "Listening",
                            "You may ask another product question.",
                        )

                        continue
                # -------------------------------------
                # SPOTIFY COMMANDS
                # -------------------------------------
                try:
                    spotify_result = (
                        handle_spotify_command(
                            user_text,
                            spotify_controller,
                        )
                    )

                except (
                    SpotifyException,
                    RuntimeError,
                    requests.RequestException,
                    ValueError,
                ) as ex:
                    print(
                        f"Spotify command error: {ex}"
                    )

                    spotify_result = {
                        "action": "error",
                        "confirmation": (
                            "I could not complete that "
                            f"Spotify command. {ex}"
                        ),
                    }

                if spotify_result is not None:
                    response_language = (
                        bridge.get_language()
                    )

                    if isinstance(
                        spotify_result,
                        dict,
                    ):
                        confirmation = str(
                            spotify_result.get(
                                "confirmation",
                                "Spotify command completed.",
                            )
                        ).strip()

                    else:
                        # Backward-compatible fallback.
                        confirmation = str(
                            spotify_result
                        ).strip()

                        spotify_result = {
                            "action": "unknown",
                            "confirmation": confirmation,
                        }

                    display.append_message(
                        "alice",
                        confirmation,
                    )

                    spotify_action = str(
                        spotify_result.get(
                            "action",
                            "",
                        )
                    ).strip().lower()

                    if response_language == "japanese":
                        if spotify_action == "play":
                            track_name = str(
                                spotify_result.get(
                                    "track_name",
                                    "",
                                )
                            ).strip()

                            artist_names = str(
                                spotify_result.get(
                                    "artist_names",
                                    "",
                                )
                            ).strip()

                            if track_name and artist_names:
                                confirmation_spoken_text = (
                                    f"{track_name}を"
                                    f"{artist_names}で再生します。"
                                )
                            elif track_name:
                                confirmation_spoken_text = (
                                    f"{track_name}を再生します。"
                                )
                            else:
                                confirmation_spoken_text = (
                                    "曲を再生します。"
                                )

                        elif spotify_action == "pause":
                            confirmation_spoken_text = (
                                "再生を一時停止しました。"
                            )

                        elif spotify_action == "resume":
                            confirmation_spoken_text = (
                                "再生を再開しました。"
                            )

                        elif spotify_action == "next":
                            confirmation_spoken_text = (
                                "次の曲に進みました。"
                            )

                        elif spotify_action == "previous":
                            confirmation_spoken_text = (
                                "前の曲に戻りました。"
                            )

                        elif spotify_action == "error":
                            confirmation_spoken_text = (
                                "Spotifyの操作を"
                                "完了できませんでした。"
                            )

                        else:
                            confirmation_spoken_text = (
                                "Spotifyの操作を完了しました。"
                            )

                    else:
                        confirmation_spoken_text = (
                            confirmation
                        )

                    try:
                        speak_alice_text(
                            spoken_text=confirmation_spoken_text,
                            displayed_text=confirmation,
                            language=response_language,
                            speaker_id=speaker_id,
                            display=display,
                            status_text="Controlling Spotify",
                        )

                    except (
                        requests.RequestException,
                        RuntimeError,
                        ValueError,
                    ) as ex:
                        print(
                            "Spotify response speech error: "
                            f"{ex}"
                        )
                    music_profile = (
                        record_spotify_preference(
                            spotify_result
                        )
                    )
                    commentary_result = generate_spotify_commentary(
                        spotify_result,
                        music_profile=music_profile,
                    )

                    commentary_english = str(
                        commentary_result.get(
                            "english",
                            "",
                        )
                    ).strip()

                    commentary_japanese = str(
                        commentary_result.get(
                            "japanese",
                            "",
                        )
                    ).strip()

                    commentary_emoticon = str(
                        commentary_result.get(
                            "emoticon",
                            "",
                        )
                    ).strip()

                    if commentary_english:
                        # The visible chat interface always uses English.
                        commentary_displayed_text = (
                            commentary_english
                        )

                        if commentary_emoticon:
                            commentary_displayed_text = (
                                f"{commentary_displayed_text} "
                                f"{commentary_emoticon}"
                            )

                        # The selected language controls only Alice's voice.
                        commentary_spoken_text = choose_spoken_text(
                            language=response_language,
                            english_text=commentary_english,
                            japanese_text=commentary_japanese,
                            english_fallback=(
                                "I could not prepare a comment "
                                "about this track."
                            ),
                            japanese_fallback=(
                                "この曲についてのコメントを"
                                "用意できませんでした。"
                            ),
                        )

                        display.append_message(
                            "alice",
                            commentary_displayed_text,
                        )

                        try:
                            speak_alice_text(
                                spoken_text=commentary_spoken_text,
                                displayed_text=commentary_displayed_text,
                                language=response_language,
                                speaker_id=speaker_id,
                                display=display,
                                status_text="Commenting",
                            )

                        except (
                            requests.RequestException,
                            RuntimeError,
                            ValueError,
                        ) as ex:
                            print(
                                "Spotify commentary speech "
                                f"error: {ex}"
                            )

                    display.set_state(
                        "listening",
                        "Listening",
                        "You may continue.",
                    )

                    continue
                if (
                    is_screen_command(user_text) 
                    or is_screen_follow_up(
                        user_text, 
                        vision,
                    )
                ): 
                    # print(
                    #     "Direct screen command detected:",
                    #     user_text, 
                    # )

                    response_language = (
                        bridge.get_language()
                    )
                    display.set_state(
                        "looking",
                        "Looking at Screen",
                        "Examining your computer display...",
                    )

                    # Prevent the passive observer from generating another
                    # comment while this direct request is being answered.
                    screen_observer.pause()
                    model_available = (
                        screen_observer.wait_until_idle(
                            timeout=30
                        )
                    )

                    if not model_available: 
                        print(
                            "Vision model remained busy."
                        )
                    
                    try:
                        screen_result = (
                            vision.analyze_screen_question(
                                user_text
                            )
                        )

                        english_text = str(
                            screen_result.get(
                                "english",
                                "",
                            )
                        ).strip()

                        japanese_text = str(
                            screen_result.get(
                                "japanese",
                                "",
                            )
                        ).strip()

                        screen_emoticon = str(
                            screen_result.get(
                                "emoticon",
                                "",
                            )
                        ).strip()

                        displayed_text = (
                            choose_displayed_text(
                                english_text,
                                fallback=(
                                    "I could not inspect the screen."
                                ),
                            )
                        )

                        if screen_emoticon:
                            displayed_text = (
                                f"{displayed_text} "
                                f"{screen_emoticon}"
                            )

                        spoken_text = (
                            choose_spoken_text(
                                language=response_language,
                                english_text=english_text,
                                japanese_text=japanese_text,
                                english_fallback=(
                                    "I could not inspect the screen."
                                ),
                                japanese_fallback=(
                                    "画面を確認できませんでした。"
                                ),
                            )
                        )

                        display.append_message(
                            "alice",
                            displayed_text,
                        )

                        try:
                            speak_alice_text(
                                spoken_text=spoken_text,
                                displayed_text=displayed_text,
                                language=response_language,
                                speaker_id=speaker_id,
                                display=display,
                                status_text="Speaking",
                                mood=reply.get(
                                    "mood", 
                                    "calm", 
                                )
                            )

                        except (
                            requests.RequestException,
                            RuntimeError,
                            ValueError,
                        ) as ex:
                            print(
                                f"Screen response speech error: {ex}"
                            )

                    finally:
                        screen_observer.suppress_comments_for(  # alice answers direct request once, then is quiet for two minutes until u speak to her again
                            DIRECT_SCREEN_COOLDOWN
                        )
                        screen_observer.resume()

                    display.set_state(
                        "listening",
                        "Listening",
                        "You may continue.",
                    )

                    # Critical: do not pass this screen request into
                    # Japanese tutor, webcam vision, or normal conversation.
                    continue
                elif is_japanese_tutor_command(user_text):
                    display.set_state(
                        "looking",
                        "Reading Text",
                        "Hold the text clearly in front of the camera.",
                    )

                    tutor_result = vision.analyze_japanese_text(
                        user_text
                    )

                    visible_text = tutor_result.get(
                        "visible_text",
                        "",
                    ).strip()

                    detected_language = tutor_result.get(
                        "detected_language",
                        "unknown",
                    ).strip().lower()

                    response_language = bridge.get_language()

                    # English text addressed to Alice:
                    # pass it into the normal conversation model.
                    if (
                        tutor_result.get("success")
                        and visible_text
                        and detected_language == "english"
                    ):
                        print(
                            "Visible English text:",
                            visible_text,
                        )

                        reply = get_ai_response(
                            visible_text,
                            alice_lore,
                            alice_state,
                            response_language,
                        )

                        displayed_text = reply[
                            "english"
                        ].strip()
                        emoticon = reply.get(
                            "emoticon", 
                            "", 
                        ).strip()
                        if emoticon: 
                            displayed_text = (
                                f"{displayed_text} {emoticon}"
                            )

                        if response_language == "english":
                            spoken_text = reply[
                                "english"
                            ].strip()
                        else:
                            spoken_text = reply[
                                "japanese"
                            ].strip()

                        display.append_message(
                            "alice",
                            displayed_text,
                        )

                        try:
                            speak_alice_text(
                                spoken_text=spoken_text,
                                displayed_text=displayed_text,
                                language=response_language,
                                speaker_id=speaker_id,
                                display=display,
                                status_text="Responding",
                            )

                        except (
                            requests.RequestException,
                            ollama.ResponseError,
                            RuntimeError,
                            ValueError,
                        ) as ex:
                            print(
                                f"Visible-text response error: {ex}"
                            )

                        display.set_state(
                            "listening",
                            "Listening",
                            "You may continue.",
                        )

                    continue

                    # # Japanese or mixed text:
                    # # show the tutoring lesson.
                    # displayed_text = format_japanese_lesson(
                    #     tutor_result
                    # )

                    # display.append_message(
                    #     "alice",
                    #     displayed_text,
                    # )

                    # if response_language == "japanese":
                    #     spoken_text = (
                    #         tutor_result.get("reading")
                    #         or tutor_result.get("japanese_text")
                    #         or tutor_result.get("english_translation")
                    #         or displayed_text
                    #     )
                    # else:
                    #     spoken_text = (
                    #         tutor_result.get("english_translation")
                    #         or tutor_result.get("english")
                    #         or displayed_text
                    #     )

                    # try:
                    #     speak_alice_text(
                    #         spoken_text=spoken_text,
                    #         displayed_text=displayed_text,
                    #         language=response_language,
                    #         speaker_id=speaker_id,
                    #         display=display,
                    #         status_text="Teaching",
                    #     )

                    # except (
                    #     requests.RequestException,
                    #     ollama.ResponseError,
                    #     RuntimeError,
                    #     ValueError,
                    # ) as ex:
                    #     print(
                    #         f"Japanese tutor speech error: {ex}"
                    #     )

                    # display.set_state(
                    #     "listening",
                    #     "Listening",
                    #     "Show me another word or sentence.",
                    # )

                    # continue
                elif is_vision_command(
                    user_text
                ):
                    display.set_state(
                        "looking",
                        "Looking",
                        "Checking the camera...",
                    )

                    response_language = (
                        bridge.get_language()
                    )

                    vision_result = (
                        vision.analyze_frame(
                            user_text
                        )
                    )

                    english_text = str(
                        vision_result.get(
                            "english",
                            "",
                        )
                    ).strip()

                    japanese_text = str(
                        vision_result.get(
                            "japanese",
                            "",
                        )
                    ).strip()
                    camera_emoticon = str(
                        vision_result.get(
                            "emoticon", 
                            "",
                        )
                    ).strip()
                    # Keep the visible interface in English.
                    displayed_text = (
                        choose_displayed_text(
                            english_text,
                            fallback=(
                                "I could not analyze "
                                "the camera image."
                            ),
                        )
                    )

                    spoken_text = (
                        choose_spoken_text(
                            language=response_language,
                            english_text=english_text,
                            japanese_text=japanese_text,
                            english_fallback=(
                                "I could not analyze "
                                "the camera image."
                            ),
                            japanese_fallback=(
                                "カメラ画像を"
                                "解析できませんでした。"
                            ),
                        )
                    )

                    if camera_emoticon: 
                        displayed_text = (
                            f"{displayed_text}"
                            f"{camera_emoticon}"
                        )

                    display.append_message(
                        "alice",
                        displayed_text,
                    )

                    try:
                        speak_alice_text(
                            spoken_text=spoken_text,
                            displayed_text=displayed_text,
                            language=response_language,
                            speaker_id=speaker_id,
                            display=display,
                            status_text="Speaking",
                        )

                    except (
                        requests.RequestException,
                        RuntimeError,
                        ValueError,
                    ) as ex:
                        print(
                            "Camera response speech "
                            f"error: {ex}"
                        )

                    display.set_state(
                        "listening",
                        "Listening",
                        (
                            "Type another message."
                            if bridge.get_mode()
                            == "silent"
                            else "You may continue."
                        ),
                    )

                    continue

                    # try:
                    #     speak_alice_text(
                    #         spoken_text=spoken_text,
                    #         displayed_text=displayed_text,
                    #         language=response_language,
                    #         speaker_id=speaker_id,
                    #         display=display,
                    #         status_text="Speaking",
                    #     )

                    # except (
                    #     requests.RequestException,
                    #     ollama.ResponseError,
                    #     RuntimeError,
                    #     ValueError,
                    # ) as ex:
                    #     print(
                    #         f"Vision speech error: {ex}"
                    #     )

                    # display.set_state(
                    #     "listening",
                    #     "Listening",
                    #     "You may continue.",
                    # )

                    # continue
                # -------------------------------------
                # GENERATE MAIN AI RESPONSE
                # -------------------------------------
                display.set_state(
                    "thinking",
                    "Thinking",
                    "Analyzing your request...",
                )

                response_language = (
                    bridge.get_language()
                )
                research_topic = parse_research_command(
                    user_text
                )

                if research_topic:
                    research_session = (
                        research_manager.start_research(
                            research_topic
                        )
                    )
                    display.set_state(
                        "thinking",
                        "Compiling Research",
                        (
                            "Your research request has been queued. "
                            "I am gathering sources..."
                        ),
                    )
                    research_session.queries = (
                        generate_research_queries(
                            research_topic
                        )
                    )

                    print(
                        "Research queries:",
                        research_session.queries
                    )

                    threading.Thread(
                        target=run_full_research_pipeline,
                        args=(
                            research_session,
                            display,
                            bridge,
                            speaker_id,
                        ),
                        daemon=True,
                        name="AliceResearchPipeline",
                    ).start()
                    print(
                        "Research session started:",
                        research_session.topic
                    )

                    display.append_message(
                        "alice",
                        (
                            "I have started a research session on "
                            f"{research_session.topic}."
                        ),
                    )

                    continue
                reply = get_ai_response(
                    user_text,
                    alice_lore,
                    alice_state,
                    response_language,
                )

                alice_state["mood"] = reply["mood"]
                alice_state["last_topic"] = user_text
                save_alice_state(alice_state)
                display.publish_mood(
                    reply["mood"]
                )

                # displayed_text = reply["english"].strip()
                english_text = str(
                    reply.get(
                        "english", 
                        "", 
                    )
                ).strip()

                japanese_text = str(
                    reply.get(
                        "japanese", 
                        "", 
                    )
                ).strip()

                if not isinstance(english_text, str): 
                    english_text = ""
                if not isinstance(japanese_text, str): 
                    japanese_text = ""

                english_text = english_text.strip()
                japanese_text = japanese_text.strip()

                displayed_text = choose_displayed_text(
                    english_text,
                )
                spoken_text = choose_spoken_text(
                    language=response_language,
                    english_text=english_text,
                    japanese_text=japanese_text,
                )
                raw_emoticon = reply.get(
                    "emoticon",
                    "",
                )
                if raw_emoticon is None: 
                    emoticon = ""
                elif isinstance(raw_emoticon, str): 
                    emoticon = raw_emoticon.strip()
                else: 
                    emoticon = ""
                if emoticon.casefold() in {
                    "none", 
                    "null",
                    "n/a",
                }:
                    emoticon = ""
                if not emoticon: 
                    emoticon = "🙂"
                if len(emoticon) > 20: 
                    emoticon = "🙂"
                if emoticon: 
                    displayed_text = (
                        f"{displayed_text} {emoticon}"
                    )
                print(
                    f"Alice: {displayed_text}"
                )

                display.append_message(
                    "alice",
                    displayed_text,
                )

                try:
                    speak_alice_text(
                        spoken_text=spoken_text, 
                        displayed_text=displayed_text, 
                        language=response_language,
                        speaker_id=speaker_id,
                        display=display,
                        status_text="Speaking",
                    )
                except (
                    requests.RequestException,
                    RuntimeError,
                    ValueError,
                ) as ex:
                    print(
                        f"Main speech error: {ex}"
                    )

                # -------------------------------------
                # OPTIONAL FOLLOW-UP
                # -------------------------------------
                # -------------------------------------
                # OPTIONAL FOLLOW-UP
                # -------------------------------------
                if reply.get("action") == "continue":
                    follow_up_english = str(
                        reply.get(
                            "follow_up_english",
                            "",
                        )
                    ).strip()

                    follow_up_japanese = str(
                        reply.get(
                            "follow_up_japanese",
                            "",
                        )
                    ).strip()

                    follow_up_displayed_text = (
                        choose_displayed_text(
                            follow_up_english,
                            fallback=(
                                "I have an additional thought."
                            ),
                        )
                    )

                    follow_up_spoken_text = (
                        choose_spoken_text(
                            language=response_language,
                            english_text=follow_up_english,
                            japanese_text=follow_up_japanese,
                            english_fallback=(
                                "I have an additional thought."
                            ),
                            japanese_fallback=(
                                "もう一つお伝えしたいことがあります。"
                            ),
                        )
                    )

                    if follow_up_spoken_text:
                        time.sleep(0.35)

                        print(
                            "Alice follow-up displayed: "
                            f"{follow_up_displayed_text}"
                        )

                        display.append_message(
                            "alice",
                            follow_up_displayed_text,
                        )

                        try:
                            speak_alice_text(
                                spoken_text=follow_up_spoken_text,
                                displayed_text=follow_up_displayed_text,
                                language=response_language,
                                speaker_id=speaker_id,
                                display=display,
                                status_text="Continuing",
                            )

                        except (
                            requests.RequestException,
                            RuntimeError,
                            ValueError,
                        ) as ex:
                            print(
                                f"Follow-up speech error: {ex}"
                            )
 
                # -------------------------------------
                # RETURN TO LISTENING
                # -------------------------------------
                if reply["expects_answer"]:
                    listening_subtitle = (
                        "Waiting for your answer..."
                    )
                elif bridge.get_mode() == "silent": 
                    listening_subtitle = (
                        "Type another message."
                    )
                else:
                    listening_subtitle = (
                        "You may continue."
                    )

                display.set_state(
                    "listening",
                    "Listening",
                    listening_subtitle,
                )

        except requests.RequestException as ex:
            print(
                f"Speech service connection error: {ex}"
            )

            display.set_state(
                "listening",
                "Connection Error",
                "The voice service could not be reached.",
            )

        except ollama.ResponseError as ex:
            print(f"Ollama error: {ex}")

            display.set_state(
                "listening",
                "Model Error",
                "Alice could not generate a response.",
            )

        except subprocess.CalledProcessError as ex:
            print(
                f"Audio playback error: {ex}"
            )

        except KeyboardInterrupt:
            print("\nAlice stopped.")
            if screen_observer.running:
                screen_observer.stop()
            save_memory()
            program_running = False

        except Exception as ex:
            import traceback

            print(f"Unexpected error: {ex}")
            traceback.print_exc()
        try: 
            save_memory()
        except Exception as error: 
            print(
                "Could not save memory during shutdown:", 
                error, 
            )
        try: 
        
            vision.close()
        except Exception as error: 
            print(
                "Could not close vision during shutdown:", 
                error, 
            )
        try:
            if screen_observer.running:
                screen_observer.stop()
        except Exception as error: 
            print(
                "Could not stop screen observer:", 
                error, 
            )
        print("Program closed.")
def select_spoken_text(reply, bridge):
    """Choose which response field VOICEVOX should speak."""
    language = bridge.get_language()

    if language == "english":
        return reply["english"]

    return reply["japanese"]
def wait_for_alice_server(
    timeout_seconds: float = 15.0,
) -> bool:
    """
    Wait until Flask is ready before starting Electron.
    """
    deadline = (
        time.time()
        + timeout_seconds
    )

    health_url = (
        "http://127.0.0.1:8765/api/health"
    )

    while time.time() < deadline:
        try:
            response = requests.get(
                health_url,
                timeout=0.5,
            )

            if response.ok:
                return True

        except requests.RequestException:
            pass

        time.sleep(0.1)

    return False


def open_alice_in_chrome() -> None:
    """
    Open the Flask interface in Google Chrome.

    This does not launch Electron or pywebview.
    """
    alice_url = (
        "http://127.0.0.1:8765/"
    )

    result = subprocess.run(
        [
            "/usr/bin/open",
            "-a",
            "Google Chrome",
            alice_url,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        error_text = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Unknown Chrome launch error."
        )

        raise RuntimeError(
            "Could not open Alice in "
            f"Google Chrome: {error_text}"
        )
def main():
    print(
        "Running Alice from:",
        Path(__file__).resolve(),
    )

    bridge = AliceInterfaceBridge()

    web_server = AliceWebServer(
        bridge=bridge,
    )

    display = FluctlightDisplay(
        bridge
    )

    display.set_web_server(
        web_server
    )

    bridge.set_display(
        display
    )

    web_server.start(); 

    if not wait_for_alice_server():
        raise RuntimeError(
            "Alice web server did not become ready."
        )

    # Open only the Flask interface in Google Chrome.
    open_alice_in_chrome()

    alice_thread = threading.Thread(
        target=run_alice,
        args=(
            display,
            bridge,
        ),
        daemon=False,
        name="AliceMainWorker",
    )

    alice_thread.start()

    try:
        while alice_thread.is_alive():
            alice_thread.join(
                timeout=0.25
            )

    except KeyboardInterrupt:
        print(
            "\nShutdown requested. Stopping Alice..."
        )

        bridge.request_shutdown()

        alice_thread.join(
            timeout=5.0
        )

        if alice_thread.is_alive():
            print(
                "Alice's worker did not stop within "
                "five seconds."
            )

if __name__ == "__main__":
    main()