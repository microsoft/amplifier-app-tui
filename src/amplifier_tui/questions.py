"""Scoped user questions, not approvals. Answer delivery uses normal tool results."""

import asyncio
import copy
import re
import uuid


def validate_questions(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 3:
        raise ValueError("Ask 1–3 questions per request")
    rows = []
    for question in value:
        if not isinstance(question, dict) or set(question) - {"id", "question", "options"}:
            raise ValueError("Invalid question fields")
        identity, text = question.get("id"), question.get("question")
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identity):
            raise ValueError("Question IDs must be 1–64 letters, digits, underscores or hyphens")
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Question text requires 1–2000 characters")
        options = question.get("options", [])
        if not isinstance(options, list) or len(options) > 6:
            raise ValueError("Offer at most 6 choices per question")
        for option in options:
            if (
                not isinstance(option, dict)
                or set(option) - {"label", "description"}
                or not isinstance(option.get("label"), str)
                or not option["label"].strip()
                or len(option["label"]) > 100
                or not isinstance(option.get("description", ""), str)
                or len(option.get("description", "")) > 1000
            ):
                raise ValueError("Invalid offered choice")
        if len({o["label"] for o in options}) != len(options):
            raise ValueError("Choice labels must be unique")
        rows.append({"id": identity, "question": text, "options": copy.deepcopy(options)})
    if len({q["id"] for q in rows}) != len(rows):
        raise ValueError("Question IDs must be unique")
    return rows


class Questions:
    def __init__(self, host):
        self.host = host
        self.pending = {}
        self.count = 0

    def publish(self, identity, row, status, answers=None):
        lines = [f"Questions · {status} · {row.get('source', 'request_user_input')}"]
        for question in row["questions"]:
            lines.append(question["question"])
            if answers is not None:
                answer = answers[question["id"]]
                lines.append(f"Answer: {answer.get('option') or answer['text']}")
        self.host.emit(
            "question.updated",
            identity,
            text="\n".join(lines),
            status=status,
            questions=row["questions"],
            answers=answers,
            source=row.get("source", "request_user_input"),
        )

    async def ask(self, questions, *, session_id, timeout=600):
        host = self.host
        if (
            (
                session_id != host.session_id
                and (not host.children or session_id not in host.children.active)
            )
            or not host.ready
            or host.auto_deny_approvals
            or host._stop_requested
            or not host.task
            or host.task.done()
        ):
            return {"status": "unavailable", "answers": {}}
        if len(self.pending) >= 4 or self.count >= 20:
            return {"status": "limit_reached", "answers": {}}
        rows = validate_questions(questions)
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 600:
            raise ValueError("Question timeout must be greater than zero and at most 600 seconds")
        identity = uuid.uuid4().hex
        row = {
            "turn_id": host.turn_id,
            "questions": rows,
            "source": "request_user_input"
            if session_id == host.session_id
            else f"Child {session_id}",
        }
        future = asyncio.get_running_loop().create_future()
        self.pending[identity] = (future, row)
        self.count += 1
        try:
            self.publish(identity, row, "waiting")
            return await asyncio.wait_for(asyncio.shield(future), timeout)
        except TimeoutError:
            return self.finish(identity, "timed_out")
        except asyncio.CancelledError:
            self.finish(identity, "stopped")
            raise
        except Exception:
            host.ready = False
            raise
        finally:
            self.pending.pop(identity, None)

    def finish(self, identity, status, answers=None):
        pending = self.pending.get(identity)
        if pending is None:
            return {"status": "unavailable", "answers": {}}
        future, row = pending
        response = {"status": status, "request_id": identity, "answers": answers or {}}
        # Save the exact decision before releasing the module; never deliver an
        # answer that this host could not record. Failed persistence disables work.
        try:
            self.publish(identity, row, status, answers)
        except Exception:
            self.host.ready = False
            self.pending.pop(identity, None)
            if not future.done():
                future.set_result({"status": "recording_failed", "answers": {}})
            raise
        self.pending.pop(identity, None)
        if not future.done():
            future.set_result(copy.deepcopy(response))
        return response

    def answer(self, request):
        identity = request.get("question_id")
        pending = self.pending.get(identity)
        if (
            not pending
            or pending[0].done()
            or self.host._stop_requested
            or request.get("turn_id") != pending[1]["turn_id"]
            or not self.host.ready
        ):
            return False, "Question expired or changed; no answer delivered"
        if request.get("op") == "question_cancel":
            self.finish(identity, "cancelled")
            return True, "Question cancelled; no answer invented"
        answers = request.get("answers")
        rows = pending[1]["questions"]
        if not isinstance(answers, dict) or set(answers) != {q["id"] for q in rows}:
            return False, "Answer every question before submitting"
        for question in rows:
            answer = answers[question["id"]]
            if not isinstance(answer, dict) or set(answer) != {"option", "text"}:
                return False, "Invalid answer fields"
            option, text = answer["option"], answer["text"]
            if not isinstance(text, str) or len(text) > 65536:
                return False, "Each text answer must fit within 65536 characters"
            if option is not None:
                if option not in [o["label"] for o in question["options"]] or text:
                    return False, "Choose an offered option or write your own answer"
            elif not text.strip():
                return False, "Write an answer or select a choice for every question"
        self.finish(identity, "answered", copy.deepcopy(answers))
        return True, "Answers delivered to the requesting tool; no permission granted"

    def cancel_all(self):
        for identity in list(self.pending):
            self.finish(identity, "stopped")
