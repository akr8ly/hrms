import unittest

from app.audit import record_audit_event
from app.auth_state import TokenStateStore
from app.chatbot.memory import RedisChatSessionStore, SessionAccessError
from app.login_protection import LoginAttemptLimiter
from app.security import issue_access_token
from tests.fake_redis import FakeRedis


class FakeDatabase:
    def __init__(self):
        self.items = []
    def add(self, item):
        self.items.append(item)


class SecurityStateTests(unittest.TestCase):
    def test_token_revocation_and_active_session(self):
        redis = FakeRedis()
        state = TokenStateStore(redis)
        issued = issue_access_token(7, 2)
        state.activate(token_id=issued.token_id, expires_at=issued.expires_at)
        self.assertTrue(state.validate_and_touch(token_id=issued.token_id, expires_at=issued.expires_at))
        state.revoke(token_id=issued.token_id, expires_at=issued.expires_at)
        self.assertFalse(state.validate_and_touch(token_id=issued.token_id, expires_at=issued.expires_at))

    def test_login_limiter_locks_after_maximum_attempts(self):
        limiter = LoginAttemptLimiter(3, 60, 120, FakeRedis())
        self.assertIsNone(limiter.record_failure("account:user"))
        self.assertIsNone(limiter.record_failure("account:user"))
        self.assertEqual(limiter.record_failure("account:user"), 120)
        self.assertEqual(limiter.blocked("account:user"), 120)

    def test_chat_session_is_owned_and_keeps_ordered_history(self):
        store = RedisChatSessionStore(FakeRedis())
        session_id = store.create_session(user_id=11, user_role="employee")
        store.add_message(session_id=session_id, user_id=11, user_role="employee", role="user", content="Leave policy")
        store.add_message(session_id=session_id, user_id=11, user_role="employee", role="assistant", content="Here is the policy")
        self.assertEqual([item.role for item in store.get_history(session_id=session_id, user_id=11, user_role="employee")], ["user", "assistant"])
        with self.assertRaises(SessionAccessError):
            store.get_history(session_id=session_id, user_id=12, user_role="employee")

    def test_audit_event_excludes_message_content(self):
        db = FakeDatabase()
        event = record_audit_event(db, event_type="chatbot.guardrail.prompt_injection", actor_user_id=3)
        self.assertEqual(event.event_type, "chatbot.guardrail.prompt_injection")
        self.assertEqual(event.details, {})
        self.assertEqual(db.items, [event])


if __name__ == "__main__":
    unittest.main()