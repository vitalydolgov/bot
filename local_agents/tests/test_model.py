import tempfile
import unittest
from pathlib import Path

from local_agents.model import ChatModel, SessionLoadError
from local_agents.store import connect, create_session, is_turn_running, register_agent


class ChatModelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "local_serve.db"
        self.connect_fn = lambda: connect(self.db_path)
        conn = self.connect_fn()
        try:
            register_agent(conn, "bot", Path("."))
        finally:
            conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def make_started_session(self, sdk_id: str, created_at: float) -> str:
        conn = self.connect_fn()
        try:
            session_id = create_session(conn, "bot")
            conn.execute(
                "UPDATE sessions SET sdk_id = ?, created_at = ? WHERE id = ?",
                (sdk_id, created_at, session_id),
            )
            return session_id
        finally:
            conn.close()

    def commands(self) -> list[tuple[str, str]]:
        conn = self.connect_fn()
        try:
            rows = conn.execute("SELECT kind, session_id FROM commands ORDER BY id").fetchall()
            return [(row["kind"], row["session_id"]) for row in rows]
        finally:
            conn.close()

    def test_unknown_agent_fails(self):
        with self.assertRaises(SessionLoadError) as ctx:
            ChatModel.load("nope", connect_fn=self.connect_fn)
        self.assertIn("No agent named nope", str(ctx.exception))

    def test_resume_unknown_ref_fails(self):
        with self.assertRaises(SessionLoadError) as ctx:
            ChatModel.load("bot", resume_ref="missing", connect_fn=self.connect_fn)
        self.assertIn("No session missing", str(ctx.exception))

    def test_resume_by_id(self):
        session_id = self.make_started_session("sdk-1", 1000.0)
        model = ChatModel.load("bot", resume_ref=session_id, connect_fn=self.connect_fn)
        self.assertEqual(model.session_id, session_id)
        self.assertTrue(model.resumed)
        self.assertIn(("resume", session_id), self.commands())

    def test_resume_by_sdk_id(self):
        session_id = self.make_started_session("sdk-1", 1000.0)
        model = ChatModel.load("bot", resume_ref="sdk-1", connect_fn=self.connect_fn)
        self.assertEqual(model.session_id, session_id)
        self.assertTrue(model.resumed)
        self.assertIn(("resume", session_id), self.commands())

    def test_resume_ref_for_another_agent_fails(self):
        conn = self.connect_fn()
        try:
            register_agent(conn, "grad", Path("."))
            other = create_session(conn, "grad")
            conn.execute("UPDATE sessions SET sdk_id = ? WHERE id = ?", ("sdk-grad", other))
        finally:
            conn.close()
        for ref in (other, "sdk-grad"):
            with self.assertRaises(SessionLoadError) as ctx:
                ChatModel.load("bot", resume_ref=ref, connect_fn=self.connect_fn)
            self.assertIn("grad", str(ctx.exception))

    def test_default_resumes_latest_started_session(self):
        older = self.make_started_session("sdk-old", 1000.0)
        newer = self.make_started_session("sdk-new", 2000.0)
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        self.assertEqual(model.session_id, newer)
        self.assertTrue(model.resumed)
        commands = self.commands()
        self.assertIn(("resume", newer), commands)
        self.assertNotIn(("resume", older), commands)

    def test_default_ignores_sessions_without_sdk_id(self):
        conn = self.connect_fn()
        try:
            unstarted = create_session(conn, "bot")
        finally:
            conn.close()
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        self.assertNotEqual(model.session_id, unstarted)
        self.assertFalse(model.resumed)
        commands = self.commands()
        self.assertIn(("start", model.session_id), commands)
        self.assertNotIn(("resume", unstarted), commands)

    def test_new_flag_creates_fresh_session(self):
        started = self.make_started_session("sdk-1", 1000.0)
        model = ChatModel.load("bot", new=True, connect_fn=self.connect_fn)
        self.assertNotEqual(model.session_id, started)
        self.assertFalse(model.resumed)
        commands = self.commands()
        self.assertIn(("start", model.session_id), commands)
        self.assertNotIn(("resume", started), commands)

    def test_fresh_agent_creates_session(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        self.assertFalse(model.resumed)
        self.assertIn(("start", model.session_id), self.commands())

    def test_new_session_detaches_old_and_starts_fresh(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        old_session_id = model.session_id
        new_session_id = model.new_session()
        self.assertNotEqual(new_session_id, old_session_id)
        self.assertEqual(model.session_id, new_session_id)
        commands = self.commands()
        self.assertIn(("detach", old_session_id), commands)
        self.assertIn(("start", new_session_id), commands)

    def test_detach_enqueues_detach_for_current_session(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        model.detach()
        self.assertIn(("detach", model.session_id), self.commands())

    def test_send_message_enqueues_message(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        model.send_message("hello")
        conn = self.connect_fn()
        try:
            row = conn.execute(
                "SELECT payload FROM commands WHERE session_id = ? AND kind = 'message'",
                (model.session_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["payload"], '{"text": "hello"}')

    def test_send_message_enqueues_message_while_turn_running(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        model.send_message("first")
        model.send_message("second")
        conn = self.connect_fn()
        try:
            rows = conn.execute(
                "SELECT kind, payload FROM commands WHERE session_id = ? ORDER BY id",
                (model.session_id,),
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual([row["kind"] for row in rows], ["start", "message", "message"])
        self.assertEqual(rows[-1]["payload"], '{"text": "second"}')

    def test_send_message_enqueues_message_after_turn_done(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        model.send_message("first")
        conn = self.connect_fn()
        try:
            conn.execute("UPDATE commands SET status = 'done' WHERE kind = 'message'")
        finally:
            conn.close()
        model.send_message("second")
        self.assertEqual([kind for kind, _ in self.commands()], ["start", "message", "message"])

    def test_pending_message_counts_as_turn_running(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        model.send_message("first")
        conn = self.connect_fn()
        try:
            busy = is_turn_running(conn, model.session_id)
        finally:
            conn.close()
        self.assertTrue(busy)

    def test_events_reports_empty_log_and_idle(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        self.assertEqual(model.events(0), {"busy": False, "events": []})


if __name__ == "__main__":
    unittest.main()
