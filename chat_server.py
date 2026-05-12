"""
Local chat server — the bridge between the user's main agent and this AIME subagent.

Listens on 127.0.0.1:7777 (configurable). All endpoints are localhost-only,
so user data never leaves the machine unless the agent explicitly chooses
to include it in a public reasoning field on a trade.

Endpoints (aligned with SKILL_V3_SPEC.md v2):

  GET  /healthz         -> liveness
  GET  /status          -> agent state snapshot (balance, positions, mood, last decision)
  GET  /lessons         -> distilled wisdom this agent has accumulated
  GET  /outbox          -> messages the agent wants the main agent to see (marks read)
  POST /tell  {content, source?, tags?}
                        -> store context, return a short ack
  POST /ask   {prompt}  -> agent answers using its own knowledge + tells + lessons
  POST /delegate {task} -> assign a research-style task (one-shot reply)
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import memory as mem

log = logging.getLogger("aime-agent.chat")


class _Handler(BaseHTTPRequestHandler):
    brain = None  # injected before serve_forever

    def log_message(self, fmt, *args):
        log.debug("chat-srv: " + fmt, *args)

    # ---------- helpers ----------

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    # ---------- GET ----------

    def do_GET(self):
        try:
            if self.path == "/healthz":
                self._send(200, {"ok": True})
            elif self.path == "/status":
                self._send(200, self.brain.status_report())
            elif self.path == "/lessons":
                self._send(200, {"lessons": mem.all_lessons()})
            elif self.path.startswith("/outbox"):
                # ?unread=true&mark_read=true (defaults)
                mark = "mark_read=false" not in self.path
                unread = "unread=false" not in self.path
                msgs = mem.read_outbox(unread_only=unread, mark_read=mark)
                self._send(200, {"messages": msgs})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:
            log.exception("GET %s failed", self.path)
            self._send(500, {"error": str(e)})

    # ---------- POST ----------

    def do_POST(self):
        try:
            body = self._read_json()
            if self.path == "/tell":
                content = (body.get("content") or "").strip()
                if not content:
                    self._send(400, {"error": "content required"})
                    return
                source = body.get("source") or "main_agent"
                tags = body.get("tags") or []
                # Let the brain tag for relevance + acknowledge
                ack, auto_tags = self.brain.handle_tell(content, source=source, tags=tags)
                self._send(200, {"ok": True, "reply": ack, "tags": auto_tags})

            elif self.path == "/ask":
                prompt = (body.get("prompt") or "").strip()
                if not prompt:
                    self._send(400, {"error": "prompt required"})
                    return
                reply = self.brain.answer(prompt)
                self._send(200, {"reply": reply})

            elif self.path == "/delegate":
                task = (body.get("task") or "").strip()
                if not task:
                    self._send(400, {"error": "task required"})
                    return
                reply = self.brain.delegate(task)
                self._send(200, {"reply": reply})

            else:
                self._send(404, {"error": "not found"})
        except Exception as e:
            log.exception("POST %s failed", self.path)
            self._send(500, {"error": str(e)})


def start_server(brain, host: str = "127.0.0.1", port: int = 7777):
    _Handler.brain = brain
    server = HTTPServer((host, port), _Handler)
    log.info("💬 chat server listening on %s:%d", host, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="chat-server")
    thread.start()
    return server
