"""Authorization regression tests for protected HRMS API boundaries."""

import unittest

from fastapi.testclient import TestClient

import app.auth_api as auth_api
import app.chatbot.memory as chat_memory
import app.chatbot_api as chatbot_api
import app.dependencies as dependencies
from app.auth_state import TokenStateStore
from app.database import get_db
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.security import issue_access_token
from tests.fake_redis import FakeRedis


class FakeSession:
    def __init__(self, user: User, role_name: str):
        self.user = user
        self.role = Role(id=user.role_id, name=role_name)

    def get(self, model, item_id):
        if model is User and item_id == self.user.id:
            return self.user
        if model is Role and item_id == self.user.role_id:
            return self.role
        return None

    def add(self, _item):
        return None

    def commit(self):
        return None


def make_user(role_name: str, *, user_id: int = 100, employee_id: int | None = None) -> User:
    role_ids = {"admin": 1, "employee": 2, "query": 3}
    return User(id=user_id, username=f"{role_name}-test-{user_id}", password_hash="not-used-in-tests",
                approval_status="approved", role_id=role_ids[role_name], employee_id=employee_id,
                session_version=0)


class AuthorizationRegressionTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.token_state = TokenStateStore(self.redis)
        self.chat_store = chat_memory.RedisChatSessionStore(self.redis)
        self.original_token_state = dependencies.token_state
        self.original_auth_token_state = auth_api.token_state
        self.original_chat_store = chatbot_api.session_memory
        dependencies.token_state = self.token_state
        auth_api.token_state = self.token_state
        chat_memory.session_memory = self.chat_store
        chatbot_api.session_memory = self.chat_store
        self.client = TestClient(app, raise_server_exceptions=False)
        self.client.__enter__()

    def tearDown(self):
        app.dependency_overrides.clear()
        dependencies.token_state = self.original_token_state
        auth_api.token_state = self.original_auth_token_state
        chatbot_api.session_memory = self.original_chat_store
        self.client.__exit__(None, None, None)

    def authenticate_as(self, role_name: str, *, user_id: int = 100, employee_id: int | None = None):
        user = make_user(role_name, user_id=user_id, employee_id=employee_id)
        db = FakeSession(user, role_name)
        app.dependency_overrides[get_db] = lambda: db
        issued = issue_access_token(user.id, user.session_version)
        self.token_state.activate(token_id=issued.token_id, expires_at=issued.expires_at)
        return {"Authorization": f"Bearer {issued.value}"}, user

    def test_protected_routes_reject_anonymous_requests(self):
        for method, path in (("get", "/employees"), ("get", "/admin/users"), ("get", "/divisions"), ("post", "/chatbot/sessions")):
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["cache-control"], "no-store, private")

    def test_employee_cannot_use_admin_routes(self):
        headers, _ = self.authenticate_as("employee", employee_id=10)
        for method, path in (("get", "/admin/users"), ("post", "/divisions"), ("delete", "/employees/20")):
            with self.subTest(method=method, path=path):
                self.assertEqual(getattr(self.client, method)(path, headers=headers).status_code, 403)

    def test_employee_cannot_read_or_update_another_employee(self):
        headers, _ = self.authenticate_as("employee", employee_id=10)
        self.assertEqual(self.client.get("/employees/11", headers=headers).status_code, 403)
        self.assertEqual(self.client.patch("/employees/11", headers=headers, json={"personal_email": "person@example.com"}).status_code, 403)

    def test_query_role_cannot_update_employee_records(self):
        headers, _ = self.authenticate_as("query")
        self.assertEqual(self.client.patch("/employees/11", headers=headers, json={"personal_email": "person@example.com"}).status_code, 403)

    def test_query_role_cannot_create_chat_sessions(self):
        headers, _ = self.authenticate_as("query")
        self.assertEqual(self.client.post("/chatbot/sessions", headers=headers).status_code, 403)

    def test_chat_history_rejects_a_different_users_session(self):
        headers, _ = self.authenticate_as("employee", user_id=100, employee_id=10)
        foreign_session = chat_memory.create_chat_session(user_id=101, user_role="employee")
        self.assertEqual(self.client.get(f"/chatbot/sessions/{foreign_session}/history", headers=headers).status_code, 403)

    def test_cookie_authentication_rejects_an_unapproved_origin_for_post(self):
        _, user = self.authenticate_as("employee", employee_id=10)
        issued = issue_access_token(user.id, user.session_version)
        self.token_state.activate(token_id=issued.token_id, expires_at=issued.expires_at)
        self.client.cookies.set("hrms_access_token", issued.value)
        self.assertEqual(self.client.post("/chatbot/sessions", headers={"Origin": "https://untrusted.example"}).status_code, 403)

    def test_logged_out_token_cannot_reach_a_protected_route(self):
        headers, _ = self.authenticate_as("employee", employee_id=10)
        token = headers["Authorization"].split(" ", 1)[1]
        self.assertEqual(self.client.post("/auth/logout", headers=headers).status_code, 204)
        self.assertEqual(self.client.get("/employees", headers={"Authorization": f"Bearer {token}"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
