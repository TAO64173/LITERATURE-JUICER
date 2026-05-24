"""Comprehensive invite system tests — 6 scenarios, fully automated.

Tests:
1. Normal registration — quota=3, auto invite code, invite link
2. Invite registration — A invites B → A+2, B stays 3, B gets own code
3. Chain invite — B invites C → B+2, C stays 3
4. Duplicate prevention — can't use invite code twice
5. Upload deduction — success deducts, failure doesn't
6. Admin — unlimited quota, no deduction

Uses a stateful in-memory MockDB instead of simple lambdas.
Overrides conftest's autouse mock_supabase via a local fixture.
"""

from __future__ import annotations

import random
import string
import uuid

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.auth import verify_clerk_token
from backend.api import upload_api, invite_api
from backend.supabase_client import is_admin


# ─── Stateful mock database ──────────────────────────────────────

class MockDB:
    """In-memory simulation of Supabase tables."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.users: dict[str, dict] = {}       # clerk_user_id → row
        self.quotas: dict[str, dict] = {}      # user_id → quota row
        self.invite_records: list[dict] = []

    def _uid(self) -> str:
        return str(uuid.uuid4())

    def add_user(self, clerk_id: str, email: str) -> dict:
        uid = self._uid()
        user = {
            "id": uid, "clerk_user_id": clerk_id, "email": email,
            "role": "user", "invite_code": None,
            "invited_by": None, "invite_rewarded": False,
        }
        self.users[clerk_id] = user
        self.quotas[uid] = {"user_id": uid, "total_quota": 3, "used_quota": 0}
        return user

    def user_by_clerk(self, cid: str) -> dict | None:
        return self.users.get(cid)

    def user_by_code(self, code: str) -> dict | None:
        for u in self.users.values():
            if u.get("invite_code") == code:
                return u
        return None

    def quota(self, uid: str) -> dict | None:
        return self.quotas.get(uid)

    def set_code(self, cid: str, code: str):
        if cid in self.users:
            self.users[cid]["invite_code"] = code

    def mark_invited(self, cid: str, by_code: str):
        if cid in self.users:
            self.users[cid]["invited_by"] = by_code
            self.users[cid]["invite_rewarded"] = True

    def add_quota(self, uid: str, amount: int):
        if uid in self.quotas:
            self.quotas[uid]["total_quota"] += amount

    def deduct(self, uid: str) -> int | None:
        q = self.quotas.get(uid)
        if not q:
            return None
        rem = q["total_quota"] - q["used_quota"]
        if rem <= 0:
            return -1
        q["used_quota"] += 1
        return q["total_quota"] - q["used_quota"]

    def add_record(self, inviter_id: str, invited_id: str, code: str):
        self.invite_records.append({
            "inviter_user_id": inviter_id,
            "invited_user_id": invited_id,
            "invite_code": code,
        })

    def count_invited(self, uid: str) -> int:
        return sum(1 for r in self.invite_records if r["inviter_user_id"] == uid)


db = MockDB()
_current_user: dict = {}


def _mock_verify():
    return _current_user


# ─── Mock functions that use MockDB ──────────────────────────────

def _ensure(uid, email):
    user = db.user_by_clerk(uid)
    if not user:
        user = db.add_user(uid, email)
    if is_admin(email):
        return {"total_quota": 999999, "used_quota": 0, "role": "admin"}
    q = db.quota(user["id"])
    return {"total_quota": q["total_quota"], "used_quota": q["used_quota"], "role": "user"}


def _get_remaining(uid, email=""):
    if is_admin(email):
        return 999999
    user = db.user_by_clerk(uid)
    if not user:
        return 3
    q = db.quota(user["id"])
    return q["total_quota"] - q["used_quota"]


def _deduct_batch(uid, count, email=""):
    if is_admin(email):
        return True, 999999
    user = db.user_by_clerk(uid)
    if not user:
        return False, None
    for _ in range(count):
        rem = db.deduct(user["id"])
        if rem is None or rem < 0:
            return False, 0
    return True, rem


def _get_role(email):
    return "admin" if is_admin(email) else "user"


def _get_invite_info(uid, email):
    if is_admin(email):
        return {"invite_code": "ADMIN0", "invited_count": 0}
    user = db.user_by_clerk(uid)
    if not user:
        return {"invite_code": "", "invited_count": 0}
    code = user.get("invite_code") or ""
    if not code:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        db.set_code(uid, code)
    return {"invite_code": code, "invited_count": db.count_invited(user["id"])}


def _generate_code(uid, email):
    if is_admin(email):
        return "ADMIN0"
    user = db.user_by_clerk(uid)
    if not user:
        return ""
    if user.get("invite_code"):
        return user["invite_code"]
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    db.set_code(uid, code)
    return code


def _apply_invite(uid, email, invite_code):
    if not invite_code or len(invite_code) != 5:
        return {"success": False, "message": "邀请码格式无效"}
    invited = db.user_by_clerk(uid)
    if not invited:
        return {"success": False, "message": "用户不存在"}
    if invited.get("invited_by"):
        return {"success": False, "message": "你已经使用过邀请码了"}
    inviter = db.user_by_code(invite_code.upper())
    if not inviter:
        return {"success": False, "message": "邀请码不存在"}
    if inviter["id"] == invited["id"]:
        return {"success": False, "message": "不能使用自己的邀请码"}
    if is_admin(inviter.get("email", "")):
        return {"success": False, "message": "该邀请码不可用"}
    db.mark_invited(uid, invite_code.upper())
    db.add_quota(inviter["id"], 2)
    db.add_record(inviter["id"], invited["id"], invite_code.upper())
    return {"success": True, "message": "邀请码使用成功！邀请人已获得 2 篇额度"}



def _login(clerk_id: str, email: str):
    global _current_user
    _current_user = {"sub": clerk_id, "email": email}
    app.dependency_overrides[verify_clerk_token] = _mock_verify


client = TestClient(app)


def _make_pdf(pages: int = 1) -> bytes:
    try:
        import fitz
        doc = fitz.open()
        for _ in range(pages):
            doc.new_page()
        b = doc.tobytes()
        doc.close()
        return b
    except ImportError:
        return b"%PDF-1.0\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"


MOCK_LLM = {
    "author": "Test Author et al.", "year": "2024", "journal": "Test Conf",
    "doi": "10.1234/test", "keywords": "test", "abstract": "Test abstract.",
    "question": "test question", "background": "test background",
    "gap": "test gap", "objective": "test objective", "method": "test method",
    "dataset": "test dataset", "metrics": "test metrics",
    "comparison": "test comparison", "innovation": "test innovation",
    "findings": "test findings", "conclusion": "test conclusion",
    "limitation": "test limitation text long enough", "future_work": "test future",
    "inspiration": "test inspiration",
}


# ─── Fixture: reset DB + patch modules (overrides conftest) ──────

@pytest.fixture(autouse=True)
def _setup_db(monkeypatch):
    """Reset stateful DB and patch modules. Runs AFTER conftest, overriding its mocks."""
    db.reset()
    # Override auth to return a default user (tests call _login to switch)
    global _current_user
    _current_user = {"sub": "default", "email": "default@test.com"}
    app.dependency_overrides[verify_clerk_token] = _mock_verify
    # Use monkeypatch so patches are applied AFTER conftest's and cleaned up properly
    monkeypatch.setattr(upload_api, "ensure_user_and_quota", _ensure)
    monkeypatch.setattr(upload_api, "get_remaining_quota", _get_remaining)
    monkeypatch.setattr(upload_api, "deduct_quota_batch", _deduct_batch)
    monkeypatch.setattr(upload_api, "get_user_role", _get_role)
    monkeypatch.setattr(invite_api, "ensure_user_and_quota", _ensure)
    monkeypatch.setattr(invite_api, "get_invite_info", _get_invite_info)
    monkeypatch.setattr(invite_api, "generate_user_invite_code", _generate_code)
    monkeypatch.setattr(invite_api, "apply_invite_code", _apply_invite)
    yield
    app.dependency_overrides.pop(verify_clerk_token, None)


# ═══════════════════════════════════════════════════════════════════
# Test 1: Normal Registration
# ═══════════════════════════════════════════════════════════════════

class Test1_NormalRegistration:
    def test_initial_quota_is_3(self):
        _login("user_a", "a@test.com")
        r = client.get("/quota")
        assert r.status_code == 200
        assert r.json()["remaining"] == 3
        assert r.json()["role"] == "user"

    def test_auto_generate_invite_code(self):
        _login("user_a", "a@test.com")
        r = client.get("/invite/info")
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert len(d["invite_code"]) == 5
        assert d["invite_code"].isalnum()

    def test_invite_code_is_uppercase(self):
        _login("user_a", "a@test.com")
        code = client.get("/invite/info").json()["invite_code"]
        assert code == code.upper()


# ═══════════════════════════════════════════════════════════════════
# Test 2: Invite Registration (A → B)
# ═══════════════════════════════════════════════════════════════════

class Test2_InviteRegistration:
    def test_a_invites_b_quota_changes(self):
        _login("user_a", "a@test.com")
        a_code = client.get("/invite/info").json()["invite_code"]
        assert client.get("/quota").json()["remaining"] == 3

        _login("user_b", "b@test.com")
        r = client.post("/invite/apply", json={"code": a_code})
        assert r.json()["success"] is True

        # A: 3 → 5
        _login("user_a", "a@test.com")
        assert client.get("/quota").json()["remaining"] == 5

        # B: still 3
        _login("user_b", "b@test.com")
        assert client.get("/quota").json()["remaining"] == 3

    def test_b_has_own_invite_code(self):
        _login("user_a", "a@test.com")
        a_code = client.get("/invite/info").json()["invite_code"]

        _login("user_b", "b@test.com")
        client.post("/invite/apply", json={"code": a_code})

        b_code = client.get("/invite/info").json()["invite_code"]
        assert len(b_code) == 5
        assert b_code != a_code

    def test_a_invited_count_is_1(self):
        _login("user_a", "a@test.com")
        a_code = client.get("/invite/info").json()["invite_code"]

        _login("user_b", "b@test.com")
        client.post("/invite/apply", json={"code": a_code})

        _login("user_a", "a@test.com")
        assert client.get("/invite/info").json()["invited_count"] == 1


# ═══════════════════════════════════════════════════════════════════
# Test 3: Chain Invite (A → B → C)
# ═══════════════════════════════════════════════════════════════════

class Test3_ChainInvite:
    def test_b_invites_c(self):
        # A → B
        _login("user_a", "a@test.com")
        a_code = client.get("/invite/info").json()["invite_code"]
        _login("user_b", "b@test.com")
        client.post("/invite/apply", json={"code": a_code})

        # B → C
        _login("user_b", "b@test.com")
        b_code = client.get("/invite/info").json()["invite_code"]
        _login("user_c", "c@test.com")
        r = client.post("/invite/apply", json={"code": b_code})
        assert r.json()["success"] is True

        # B: 3 → 5
        _login("user_b", "b@test.com")
        assert client.get("/quota").json()["remaining"] == 5

        # C: still 3
        _login("user_c", "c@test.com")
        assert client.get("/quota").json()["remaining"] == 3

    def test_full_chain_quota_progression(self):
        _login("user_a", "a@test.com")
        assert client.get("/quota").json()["remaining"] == 3
        a_code = client.get("/invite/info").json()["invite_code"]

        _login("user_b", "b@test.com")
        assert client.get("/quota").json()["remaining"] == 3
        client.post("/invite/apply", json={"code": a_code})

        # A=5, B=3
        _login("user_a", "a@test.com")
        assert client.get("/quota").json()["remaining"] == 5
        _login("user_b", "b@test.com")
        assert client.get("/quota").json()["remaining"] == 3

        # B → C
        b_code = client.get("/invite/info").json()["invite_code"]
        _login("user_c", "c@test.com")
        client.post("/invite/apply", json={"code": b_code})

        # B=5, C=3
        _login("user_b", "b@test.com")
        assert client.get("/quota").json()["remaining"] == 5
        _login("user_c", "c@test.com")
        assert client.get("/quota").json()["remaining"] == 3


# ═══════════════════════════════════════════════════════════════════
# Test 4: Duplicate Prevention
# ═══════════════════════════════════════════════════════════════════

class Test4_DuplicatePrevention:
    def test_cannot_use_invite_twice(self):
        _login("user_a", "a@test.com")
        a_code = client.get("/invite/info").json()["invite_code"]

        _login("user_b", "b@test.com")
        assert client.post("/invite/apply", json={"code": a_code}).json()["success"] is True
        assert client.post("/invite/apply", json={"code": a_code}).json()["success"] is False

    def test_cannot_self_invite(self):
        _login("user_a", "a@test.com")
        a_code = client.get("/invite/info").json()["invite_code"]
        r = client.post("/invite/apply", json={"code": a_code})
        assert r.json()["success"] is False
        assert "自己" in r.json()["message"]

    def test_invalid_code_rejected(self):
        _login("user_a", "a@test.com")
        r = client.post("/invite/apply", json={"code": "XX"})
        assert r.json()["success"] is False
        assert "无效" in r.json()["message"]

    def test_nonexistent_code_rejected(self):
        _login("user_a", "a@test.com")
        r = client.post("/invite/apply", json={"code": "ZZZZZ"})
        assert r.json()["success"] is False
        assert "不存在" in r.json()["message"]


# ═══════════════════════════════════════════════════════════════════
# Test 5: Upload Deduction
# ═══════════════════════════════════════════════════════════════════

class Test5_UploadDeduction:
    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM)
    def test_success_deducts(self, mock_llm, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        _login("user_a", "a@test.com")

        assert client.get("/quota").json()["remaining"] == 3

        r = client.post("/upload", files=[("files", ("t.pdf", _make_pdf(), "application/pdf"))])
        assert r.json()["success"] is True

        assert client.get("/quota").json()["remaining"] == 2

    @patch("backend.api.upload_api.extract_paper_info", side_effect=Exception("LLM failed"))
    def test_failure_no_deduction(self, mock_llm, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        _login("user_a", "a@test.com")

        assert client.get("/quota").json()["remaining"] == 3

        r = client.post("/upload", files=[("files", ("t.pdf", _make_pdf(), "application/pdf"))])
        assert r.json()["success"] is False

        assert client.get("/quota").json()["remaining"] == 3


# ═══════════════════════════════════════════════════════════════════
# Test 6: Admin Account
# ═══════════════════════════════════════════════════════════════════

class Test6_AdminAccount:
    def test_unlimited_quota(self):
        _login("admin_user", "2463776055@qq.com")
        r = client.get("/quota")
        assert r.json()["role"] == "admin"
        assert r.json()["remaining"] == 999999

    def test_upload_no_deduction(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        _login("admin_user", "2463776055@qq.com")

        with patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM):
            r = client.post("/upload", files=[("files", ("t.pdf", _make_pdf(), "application/pdf"))])
            assert r.json()["success"] is True

        assert client.get("/quota").json()["remaining"] == 999999

    def test_invite_code_is_admin0(self):
        _login("admin_user", "2463776055@qq.com")
        assert client.get("/invite/info").json()["invite_code"] == "ADMIN0"

    def test_admin_code_cannot_be_used(self):
        _login("admin_user", "2463776055@qq.com")
        # ADMIN0 is 6 chars, rejected by 5-char validation
        _login("user_a", "a@test.com")
        r = client.post("/invite/apply", json={"code": "ADMIN0"})
        assert r.json()["success"] is False
