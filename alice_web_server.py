from __future__ import annotations

import queue
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import queue
import threading
import logging

BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = "fluctlight.html"


class AliceWebServer:
    def __init__(
        self, 
        bridge,
    ): 
        self.latest_state = {
            "type": "state",
            "state": "sleeping",
            "status": "Sleeping",
            "subtitle":
                "Say 'Hey Alice' to wake me.",
        }
        self.subscribers = set()
        self.todo_briefing_queue = (
            queue.Queue()
        )
        self.subscribers_lock = threading.Lock()
        self.bridge = bridge
        self.app = Flask(
            __name__,
            static_folder=str(BASE_DIR),
            static_url_path="",
        )

        CORS(
            self.app,
            resources={
                r"/api/*": {
                    "origins": "*",
                },
            },
        )

        self._register_routes()

    def _register_routes(self) -> None:
        @self.app.get("/")
        def index():
            return send_from_directory(
                BASE_DIR,
                HTML_FILE,
            )

        @self.app.get("/<path:asset_path>")
        def assets(asset_path: str):
            return send_from_directory(
                BASE_DIR,
                asset_path,
            )
        
        @self.app.post("/api/message")
        def send_message():
            payload = request.get_json(
                silent=True,
            ) or {}

            text = str(
                payload.get(
                    "text",
                    "",
                )
            ).strip()

            if not text:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": (
                                "Message text is required."
                            ),
                        }
                    ),
                    400,
                )

            success = bool(
                self.bridge.send_message(
                    text
                )
            )

            if not success:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": (
                                "Alice rejected the message."
                            ),
                        }
                    ),
                    400,
                )

            return jsonify(
                {
                    "success": True,
                }
            )

        @self.app.post("/api/todo-briefing")
        def receive_todo_briefing():
            try:
                payload = request.get_json(
                    silent=True,
                ) or {}

                english_text = str(
                    payload.get(
                        "english",
                        payload.get(
                            "text",
                            "",
                        ),
                    )
                ).strip()

                japanese_text = str(
                    payload.get(
                        "japanese",
                        "",
                    )
                ).strip()

                if not english_text:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": (
                                    "Todo briefing text "
                                    "was empty."
                                ),
                            }
                        ),
                        400,
                    )

                self.todo_briefing_queue.put(
                    {
                        "english": english_text,
                        "japanese": japanese_text,
                    }
                )

                return jsonify(
                    {
                        "success": True,
                    }
                )

            except Exception as error:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": str(
                                error
                            ),
                        }
                    ),
                    500,
                )
        @self.app.post("/api/mode")
        def set_mode():
            payload = request.get_json(
                silent=True,
            ) or {}

            mode = str(
                payload.get(
                    "mode",
                    "",
                )
            ).strip().lower()

            # print(
            #     f"HTTP mode request: {mode}"
            # )

            if mode not in {
                "voice",
                "silent",
            }:
                return jsonify(
                    {
                        "success": False,
                        "error": "Invalid mode.",
                    }
                ), 400

            success = bool(
                self.bridge.set_mode(mode)
            )

            return jsonify(
                {
                    "success": success,
                }
            )

        @self.app.post("/api/language")
        def set_language():
            payload = request.get_json(
                silent=True,
            ) or {}

            language = str(
                payload.get(
                    "language",
                    "",
                )
            ).strip().lower()
            # print(
            #     f"HTTP mode request: {language}"
            # )

            if language not in {
                "english",
                "japanese",
            }:
                return jsonify(
                    {
                        "success": False,
                        "error": "Invalid language.",
                    }
                ), 400

            success = bool(
                self.bridge.set_language(
                    language
                )
            )

            return jsonify(
                {
                    "success": success,
                }
            )

        @self.app.get("/api/health")
        def health():
            return jsonify(
                {
                    "success": True,
                    "service": "alice",
                }
            )
        @self.app.get("/api/events")
        def events():
            subscriber_queue = queue.Queue(
                maxsize=100
            )

            with self.subscribers_lock:
                self.subscribers.add(
                    subscriber_queue
                )
            subscriber_queue.put_nowait(
                self.latest_state
            )
            def generate_events():
                try:
                    while True:
                        try:
                            event = (
                                subscriber_queue.get(
                                    timeout=15
                                )
                            )

                            yield (
                                "data: "
                                + json.dumps(
                                    event,
                                    ensure_ascii=False,
                                )
                                + "\n\n"
                            )

                        except queue.Empty:
                            yield ": keep-alive\n\n"

                finally:
                    with self.subscribers_lock:
                        self.subscribers.discard(
                            subscriber_queue
                        )

            return Response(
                generate_events(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control":
                        "no-cache",
                    "Connection":
                        "keep-alive",
                    "X-Accel-Buffering":
                        "no",
                },
            )

    def start(self) -> None:
        logging.getLogger(
            "werkzeug"
        ).setLevel(
            logging.ERROR
        )
        server_thread = threading.Thread(
            target=self.app.run,
            kwargs={
                "host": "127.0.0.1",
                "port": 8765,
                "debug": False,
                "use_reloader": False,
                "threaded": True,
            },
            daemon=True,
            name="alice-web-server",
        )

        server_thread.start()
    def publish_event(
        self,
        event,
    ):
        with self.subscribers_lock:
            subscribers = list(
                self.subscribers
            )

        for subscriber_queue in subscribers:
            try:
                subscriber_queue.put_nowait(
                    event
                )

            except queue.Full:
                try:
                    subscriber_queue.get_nowait()
                except queue.Empty:
                    pass

                try:
                    subscriber_queue.put_nowait(
                        event
                    )
                except queue.Full:
                    pass
    def publish_chat_message(
        self,
        speaker,
        text,
    ):
        self.publish_event(
            {
                "type": "chat",
                "speaker": str(speaker),
                "text": str(text),
            }
        )
    def publish_skill_installed(
        self,
        data,
    ):
        self.publish_event(
            {
                "type": "skill_installed",
                "data": data,
            }
        )

    def publish_state(
        self,
        state,
        status,
        subtitle="",
    ):
        state_event = {
            "type": "state",
            "state": str(state),
            "status": str(status),
            "subtitle": str(subtitle),
        }

        self.latest_state = state_event

        self.publish_event(
            state_event
        )

        self.publish_event(
            {
                "type": "speaking",
                "speaking":
                    str(state) == "speaking",
            }
        )


    def publish_speaking(
        self,
        speaking,
    ):
        self.publish_event(
            {
                "type": "speaking",
                "speaking": bool(
                    speaking
                ),
            }
        )