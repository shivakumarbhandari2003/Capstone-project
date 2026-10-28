import os
import sqlite3
import uuid
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from pathlib import Path
import bcrypt
from backend.app.core.config import settings
from backend.app.core.logging_config import logger

DB_PATH: Path = settings.DATA_DIR / "app.db"

class SQLiteManager:
    """
    Thread-safe SQLite database manager for local data governance,
    including authentication (users, bcrypt password hashes, active sessions),
    user profiles, and conversation/message history.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
        self._seed_default_accounts()

    def rebind_db(self, new_path: Path) -> None:
        """Rebinds SQLite manager to an isolated database path (used for tests/migrations)."""
        self.db_path = Path(new_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
        self._seed_default_accounts()

    def _get_connection(self) -> sqlite3.Connection:
        # Strict Test Isolation Safeguard: Prevent any test from using runtime data/app.db
        if os.environ.get("PYTEST_CURRENT_TEST") and Path(self.db_path).resolve() == DB_PATH.resolve():
            raise RuntimeError(
                f"CRITICAL SAFETY VIOLATION: Automated test attempted to connect to runtime database '{DB_PATH}'! "
                "All tests must execute against an isolated test database."
            )
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_tables(self) -> None:
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    requested_role TEXT NOT NULL,
                    effective_role TEXT NOT NULL,
                    is_approved INTEGER NOT NULL DEFAULT 1,
                    full_name TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    selected_plan_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    citations_json TEXT DEFAULT '[]',
                    effective_scope_json TEXT DEFAULT '[]',
                    is_comparison INTEGER DEFAULT 0,
                    is_clarification INTEGER DEFAULT 0,
                    contains_unverified_notice INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL,
                    governance_status TEXT NOT NULL DEFAULT 'active',
                    last_login TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS document_records (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    content_hash TEXT,
                    file_size_bytes INTEGER DEFAULT 0,
                    file_type TEXT DEFAULT 'application/pdf',
                    status TEXT NOT NULL DEFAULT 'INDEXED',
                    chunk_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    job_id TEXT PRIMARY KEY,
                    document_id TEXT,
                    filename TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT,
                    error_summary TEXT,
                    duration_ms REAL DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES document_records(document_id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS rag_request_metrics (
                    metric_id TEXT PRIMARY KEY,
                    request_id TEXT,
                    user_id TEXT,
                    role TEXT,
                    plan_id TEXT,
                    latency_retrieval_ms REAL DEFAULT 0,
                    latency_generation_ms REAL DEFAULT 0,
                    latency_total_ms REAL DEFAULT 0,
                    retrieved_chunks_count INTEGER DEFAULT 0,
                    citations_count INTEGER DEFAULT 0,
                    is_comparison INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    error_category TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    event_id TEXT PRIMARY KEY,
                    actor_id TEXT,
                    actor_email TEXT,
                    actor_role TEXT,
                    action TEXT NOT NULL,
                    target_resource TEXT,
                    outcome TEXT NOT NULL,
                    details_json TEXT DEFAULT '{}',
                    timestamp TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS eligibility_assessments (
                    assessment_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    qualifying_plans_json TEXT DEFAULT '[]',
                    input_provenance_json TEXT DEFAULT '{}',
                    model_id TEXT,
                    model_version TEXT,
                    confidence_score REAL,
                    reason_codes_json TEXT DEFAULT '[]',
                    review_status TEXT DEFAULT 'NONE',
                    error_category TEXT,
                    previous_assessment_id TEXT,
                    is_current INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    expires_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (previous_assessment_id) REFERENCES eligibility_assessments(assessment_id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS plan_selections (
                    selection_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    assessment_id TEXT NOT NULL,
                    selected_plan_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    confirmed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (assessment_id) REFERENCES eligibility_assessments(assessment_id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS agent_contact_requests (
                    request_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    assessment_id TEXT,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT,
                    preferred_contact_method TEXT DEFAULT 'EMAIL',
                    notes TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (assessment_id) REFERENCES eligibility_assessments(assessment_id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
                CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
                CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_docs_plan ON document_records(plan_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_created ON ingestion_jobs(created_at);
                CREATE INDEX IF NOT EXISTS idx_rag_metrics_time ON rag_request_metrics(created_at);
                CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp);
                CREATE INDEX IF NOT EXISTS idx_asmt_user_current ON eligibility_assessments(user_id, is_current);
                CREATE INDEX IF NOT EXISTS idx_asmt_outcome ON eligibility_assessments(outcome);
                CREATE INDEX IF NOT EXISTS idx_asmt_status ON eligibility_assessments(status);
                CREATE INDEX IF NOT EXISTS idx_asmt_completed ON eligibility_assessments(completed_at);
                CREATE INDEX IF NOT EXISTS idx_psel_user_status ON plan_selections(user_id, status);
                CREATE INDEX IF NOT EXISTS idx_agent_req_user ON agent_contact_requests(user_id);
                CREATE INDEX IF NOT EXISTS idx_agent_req_status ON agent_contact_requests(status);
            """)
            # Non-destructive idempotent schema migration for existing databases
            try:
                conn.execute("ALTER TABLE plan_selections ADD COLUMN confirmed_at TEXT;")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def _seed_default_accounts(self) -> None:
        """Seed default verified demo accounts and initial verified document records if database is empty."""
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                # 1. Default Administrator account (strictly provisioned through trusted system seed)
                cur.execute("SELECT user_id FROM users WHERE email = 'admin@insurance.corp'")
                if not cur.fetchone():
                    salt = bcrypt.gensalt()
                    admin_hash = bcrypt.hashpw(b"Admin@123", salt).decode("utf-8")
                    admin_id = "user_admin_demo"
                    now = datetime.now(timezone.utc).isoformat()
                    cur.execute("""
                        INSERT INTO users (user_id, email, password_hash, requested_role, effective_role, is_approved, full_name, created_at)
                        VALUES (?, ?, ?, 'admin', 'admin', 1, 'Enterprise Compliance Administrator', ?)
                    """, (admin_id, "admin@insurance.corp", admin_hash, now))
                    cur.execute("""
                        INSERT OR REPLACE INTO profiles (user_id, email, role, governance_status, last_login)
                        VALUES (?, 'admin@insurance.corp', 'admin', 'verified_administrator', ?)
                    """, (admin_id, now))

                # 2. Default authorized employee
                cur.execute("SELECT user_id FROM users WHERE email = 'employee@insurance.corp'")
                if not cur.fetchone():
                    salt = bcrypt.gensalt()
                    emp_hash = bcrypt.hashpw(b"Employee@123", salt).decode("utf-8")
                    emp_id = "user_emp_demo"
                    now = datetime.now(timezone.utc).isoformat()
                    cur.execute("""
                        INSERT INTO users (user_id, email, password_hash, requested_role, effective_role, is_approved, full_name, created_at)
                        VALUES (?, ?, ?, 'employee', 'employee', 1, 'Authorized Employee Staff', ?)
                    """, (emp_id, "employee@insurance.corp", emp_hash, now))
                    cur.execute("""
                        INSERT OR REPLACE INTO profiles (user_id, email, role, governance_status, last_login)
                        VALUES (?, 'employee@insurance.corp', 'employee', 'verified_employee', ?)
                    """, (emp_id, now))

                # 3. Default customer
                cur.execute("SELECT user_id FROM users WHERE lower(email) = 'customer@insurance.com'")
                if not cur.fetchone():
                    salt = bcrypt.gensalt()
                    cust_hash = bcrypt.hashpw(b"Customer@123", salt).decode("utf-8")
                    cust_id = "user_cust_demo"
                    now = datetime.now(timezone.utc).isoformat()
                    cur.execute("""
                        INSERT INTO users (user_id, email, password_hash, requested_role, effective_role, is_approved, full_name, created_at)
                        VALUES (?, ?, ?, 'customer', 'customer', 1, 'Policy Holder Customer', ?)
                    """, (cust_id, "customer@insurance.com", cust_hash, now))
                    cur.execute("""
                        INSERT OR REPLACE INTO profiles (user_id, email, role, governance_status, last_login)
                        VALUES (?, 'customer@insurance.com', 'customer', 'active_customer', ?)
                    """, (cust_id, now))

                # 4. Mandatory Local-Demo Account: Shivu (Customer)
                cur.execute("SELECT user_id FROM users WHERE lower(email) = 'shivu@gmail.com'")
                if not cur.fetchone():
                    salt = bcrypt.gensalt()
                    shivu_hash = bcrypt.hashpw(b"12345678", salt).decode("utf-8")
                    shivu_id = "user_cust_shivu"
                    now = datetime.now(timezone.utc).isoformat()
                    cur.execute("""
                        INSERT INTO users (user_id, email, password_hash, requested_role, effective_role, is_approved, full_name, created_at)
                        VALUES (?, 'shivu@gmail.com', ?, 'customer', 'customer', 1, 'Shivu', ?)
                    """, (shivu_id, shivu_hash, now))
                    cur.execute("""
                        INSERT OR REPLACE INTO profiles (user_id, email, role, governance_status, last_login)
                        VALUES (?, 'shivu@gmail.com', 'customer', 'active', ?)
                    """, (shivu_id, now))

                # 5. Mandatory Local-Demo Account: Murali (Employee)
                cur.execute("SELECT user_id FROM users WHERE lower(email) = 'murali@gmail.com'")
                if not cur.fetchone():
                    salt = bcrypt.gensalt()
                    murali_hash = bcrypt.hashpw(b"12345678", salt).decode("utf-8")
                    murali_id = "user_emp_murali"
                    now = datetime.now(timezone.utc).isoformat()
                    cur.execute("""
                        INSERT INTO users (user_id, email, password_hash, requested_role, effective_role, is_approved, full_name, created_at)
                        VALUES (?, 'murali@gmail.com', ?, 'employee', 'employee', 1, 'Murali', ?)
                    """, (murali_id, murali_hash, now))
                    cur.execute("""
                        INSERT OR REPLACE INTO profiles (user_id, email, role, governance_status, last_login)
                        VALUES (?, 'murali@gmail.com', 'employee', 'active', ?)
                    """, (murali_id, now))

                # 6. Mandatory Local-Demo Account: Administrator (Admin)
                cur.execute("SELECT user_id FROM users WHERE lower(email) = 'admin@gmail.com'")
                if not cur.fetchone():
                    salt = bcrypt.gensalt()
                    admin_demo_hash = bcrypt.hashpw(b"admin@123", salt).decode("utf-8")
                    admin_demo_id = "user_admin_sys"
                    now = datetime.now(timezone.utc).isoformat()
                    cur.execute("""
                        INSERT INTO users (user_id, email, password_hash, requested_role, effective_role, is_approved, full_name, created_at)
                        VALUES (?, 'admin@gmail.com', ?, 'admin', 'admin', 1, 'Administrator', ?)
                    """, (admin_demo_id, admin_demo_hash, now))
                    cur.execute("""
                        INSERT OR REPLACE INTO profiles (user_id, email, role, governance_status, last_login)
                        VALUES (?, 'admin@gmail.com', 'admin', 'active', ?)
                    """, (admin_demo_id, now))

                # 4. Seed verified documents into document_records if table is empty
                cur.execute("SELECT COUNT(*) as cnt FROM document_records")
                if cur.fetchone()["cnt"] == 0:
                    now = datetime.now(timezone.utc).isoformat()
                    verified_docs = [
                        ("doc_basic_001", "health_shield_basic.pdf", "HS-BASIC-001", 323216, 32),
                        ("doc_gold_001", "health_shield_gold.pdf", "HS-GOLD-001", 324835, 30),
                        ("doc_premium_001", "health_shield_premium.pdf", "HS-PREMIUM-001", 324558, 29),
                        ("doc_emp_001", "executive_employee_insurance_plan.pdf", "EMP-INS-001", 343839, 28)
                    ]
                    for d_id, fname, pid, fsize, chunks in verified_docs:
                        cur.execute("""
                            INSERT INTO document_records (document_id, filename, plan_id, content_hash, file_size_bytes, file_type, status, chunk_count, created_at, updated_at)
                            VALUES (?, ?, ?, '', ?, 'application/pdf', 'INDEXED', ?, ?, ?)
                        """, (d_id, fname, pid, fsize, chunks, now, now))
                        cur.execute("""
                            INSERT INTO ingestion_jobs (job_id, document_id, filename, plan_id, status, stage, error_summary, duration_ms, chunk_count, created_at)
                            VALUES (?, ?, ?, ?, 'SUCCESS', 'Stage 9: Audit Verification Complete', '', 2150.0, ?, ?)
                        """, (f"job_{d_id}", d_id, fname, pid, chunks, now))

                # 5. Seed initial realistic audit logs across SUCCESS (200 OK), FORBIDDEN (403), and ERROR if table is empty
                cur.execute("SELECT COUNT(*) as cnt FROM audit_logs")
                if cur.fetchone()["cnt"] == 0:
                    seed_now = datetime.now(timezone.utc)
                    audit_seeds = [
                        ('user_admin_demo', 'admin@insurance.corp', 'admin', 'auth_login_success', '/api/auth/login', 'SUCCESS', {'status_code': 200, 'message': 'Admin session established successfully'}, seed_now - timedelta(minutes=5)),
                        ('user_cust_demo', 'customer@insurance.com', 'customer', 'auth_login_success', '/api/auth/login', 'SUCCESS', {'status_code': 200, 'message': 'Customer login verified'}, seed_now - timedelta(minutes=15)),
                        ('user_cust_demo', 'customer@insurance.com', 'customer', 'chat_grounded_response', 'HS-GOLD-001', 'SUCCESS', {'status_code': 200, 'retrieval_strategy': 'hybrid_rrf', 'latency_ms': 1420.0, 'citations_count': 3}, seed_now - timedelta(minutes=25)),
                        ('user_emp_demo', 'employee@insurance.corp', 'employee', 'chat_grounded_response', 'EMP-INS-001', 'SUCCESS', {'status_code': 200, 'retrieval_strategy': 'hybrid_rrf', 'latency_ms': 1180.5, 'citations_count': 4}, seed_now - timedelta(minutes=45)),
                        ('user_admin_demo', 'admin@insurance.corp', 'admin', 'document_indexed', 'health_shield_gold.pdf', 'SUCCESS', {'status_code': 200, 'plan_id': 'HS-GOLD-001', 'chunk_count': 30, 'file_size_kb': 317.2}, seed_now - timedelta(hours=2)),
                        ('user_admin_demo', 'admin@insurance.corp', 'admin', 'document_indexed', 'executive_employee_insurance_plan.pdf', 'SUCCESS', {'status_code': 200, 'plan_id': 'EMP-INS-001', 'chunk_count': 28, 'file_size_kb': 335.7}, seed_now - timedelta(hours=3)),
                        ('user_admin_demo', 'admin@insurance.corp', 'admin', 'user_status_approved', 'usr_0840a9f402b1', 'SUCCESS', {'status_code': 200, 'new_status': 'active'}, seed_now - timedelta(hours=6)),
                        ('system', 'system@internal', 'system', 'knowledge_base_sync', 'ChromaCloud', 'SUCCESS', {'status_code': 200, 'collection': 'insurance_knowledge'}, seed_now - timedelta(hours=8)),
                        ('user_cust_demo', 'customer@insurance.com', 'customer', 'plan_access_restricted', 'EMP-INS-001', 'FORBIDDEN', {'status_code': 403, 'reason': 'Customer account unauthorized for Executive Corporate Plan'}, seed_now - timedelta(minutes=10)),
                        ('user_cust_demo', 'customer@insurance.com', 'customer', 'admin_endpoint_forbidden', '/api/admin/overview', 'FORBIDDEN', {'status_code': 403, 'reason': 'Role-Based Access Control: customer role denied admin workspace'}, seed_now - timedelta(minutes=20)),
                        ('anonymous', 'anonymous@external', 'none', 'header_spoofing_blocked', '/api/admin/users', 'FORBIDDEN', {'status_code': 403, 'reason': 'Untrusted X-User-Role header rejected by server'}, seed_now - timedelta(minutes=35)),
                        ('unauthenticated', None, 'none', 'admin_endpoint_unauthorized', '/api/admin/documents', 'FORBIDDEN', {'status_code': 401, 'reason': 'Missing or expired Bearer authentication token'}, seed_now - timedelta(hours=1)),
                        ('system', 'system@internal', 'system', 'chroma_retrieval_timeout', 'chroma_cloud_client', 'ERROR', {'status_code': 504, 'error': 'Remote Chroma cluster timeout, fallback to BM25 local index'}, seed_now - timedelta(minutes=50)),
                        ('system', 'system@internal', 'system', 'pdf_ocr_unrecognized', 'corrupted_sample_policy.pdf', 'ERROR', {'status_code': 422, 'error': 'Malformed PDF structure: missing xref table'}, seed_now - timedelta(hours=2, minutes=30)),
                        ('system', 'system@internal', 'system', 'gemini_quota_retry', 'models/gemini-2.5-flash', 'ERROR', {'status_code': 429, 'error': 'Resource exhausted on Generative API, retried and recovered'}, seed_now - timedelta(hours=11))
                    ]
                    for a_id, a_email, a_role, act, tgt, outc, det, ts in audit_seeds:
                        cur.execute("""
                            INSERT INTO audit_logs (event_id, actor_id, actor_email, actor_role, action, target_resource, outcome, details_json, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (f"ev_{uuid.uuid4().hex[:12]}", a_id, a_email, a_role, act, tgt, outc, json.dumps(det), ts.isoformat()))

                conn.commit()
        except Exception as e:
            logger.error(f"Error seeding default accounts: {e}")

    def provision_demo_accounts(self, force_reconcile: bool = False) -> dict[str, str]:
        """
        Explicit, safe local-demo credential provisioning operation for designated demo accounts:
        - shivu@gmail.com (Customer, demo password: '12345678')
        - murali@gmail.com (Employee, demo password: '12345678')
        - admin@gmail.com (Admin, demo password: 'admin@123')

        If force_reconcile is True, reconciles passwords and roles to demo specification.
        If False, creates missing accounts without resetting existing passwords.
        Strictly touches ONLY these 3 designated demo accounts.
        Never prints or logs passwords or hashes.
        """
        demo_specs = [
            {"email": "shivu@gmail.com", "name": "Shivu", "role": "customer", "pw": b"12345678", "user_id": "user_cust_shivu"},
            {"email": "murali@gmail.com", "name": "Murali", "role": "employee", "pw": b"12345678", "user_id": "user_emp_murali"},
            {"email": "admin@gmail.com", "name": "Administrator", "role": "admin", "pw": b"admin@123", "user_id": "user_admin_sys"},
        ]
        results = {}
        with self._get_connection() as conn:
            cur = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            for spec in demo_specs:
                norm_email = spec["email"].strip().lower()
                cur.execute("SELECT user_id, password_hash FROM users WHERE lower(email) = ?", (norm_email,))
                row = cur.fetchone()
                if not row:
                    salt = bcrypt.gensalt()
                    pw_hash = bcrypt.hashpw(spec["pw"], salt).decode("utf-8")
                    cur.execute("""
                        INSERT INTO users (user_id, email, password_hash, requested_role, effective_role, is_approved, full_name, created_at)
                        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """, (spec["user_id"], norm_email, pw_hash, spec["role"], spec["role"], spec["name"], now))
                    cur.execute("""
                        INSERT OR REPLACE INTO profiles (user_id, email, role, governance_status, last_login)
                        VALUES (?, ?, ?, 'active', ?)
                    """, (spec["user_id"], norm_email, spec["role"], now))
                    results[norm_email] = "CREATED"
                elif force_reconcile:
                    salt = bcrypt.gensalt()
                    pw_hash = bcrypt.hashpw(spec["pw"], salt).decode("utf-8")
                    cur.execute("""
                        UPDATE users
                        SET password_hash = ?, effective_role = ?, requested_role = ?, is_approved = 1, full_name = ?
                        WHERE lower(email) = ?
                    """, (pw_hash, spec["role"], spec["role"], spec["name"], norm_email))
                    cur.execute("""
                        UPDATE profiles
                        SET role = ?, governance_status = 'active'
                        WHERE user_id = ?
                    """, (spec["role"], row["user_id"]))
                    results[norm_email] = "RECONCILED"
                else:
                    results[norm_email] = "EXISTS"
            conn.commit()
        return results

    # ==================== USER MANAGEMENT ====================

    def create_user(
        self,
        email: str,
        password_hash: str,
        requested_role: str,
        effective_role: str,
        is_approved: int,
        full_name: str
    ) -> dict:
        user_id = f"usr_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO users (user_id, email, password_hash, requested_role, effective_role, is_approved, full_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, email.strip().lower(), password_hash, requested_role, effective_role, is_approved, full_name, now))
            
            cur.execute("""
                INSERT INTO profiles (user_id, email, role, governance_status, last_login)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, email.strip().lower(), effective_role, 'active' if is_approved else 'pending_verification', now))
            
            conn.commit()
            return {
                "user_id": user_id,
                "email": email.strip().lower(),
                "role": effective_role,
                "requested_role": requested_role,
                "is_approved": is_approved,
                "full_name": full_name,
                "created_at": now
            }

    def get_user_by_email(self, email: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip().lower(),))
            row = cur.fetchone()
            if row:
                return dict(row)
            return None

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
            return None

    # ==================== SESSION MANAGEMENT ====================

    def create_session(self, user_id: str, role: str, duration_hours: int = 24) -> str:
        token = f"sess_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(hours=duration_hours)).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sessions (token, user_id, role, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (token, user_id, role, now.isoformat(), expires_at))
            
            # Update profile last_login
            cur.execute("UPDATE profiles SET last_login = ? WHERE user_id = ?", (now.isoformat(), user_id))
            conn.commit()
        return token

    def get_session(self, token: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT s.token, s.user_id, s.role, s.created_at, s.expires_at,
                       u.email, u.full_name, u.effective_role, u.is_approved
                FROM sessions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.token = ?
            """, (token,))
            row = cur.fetchone()
            if not row:
                return None
            data = dict(row)
            # Check expiration
            expires_at = datetime.fromisoformat(data["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                # Expired -> delete
                cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                return None
            return data

    def delete_session(self, token: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return cur.rowcount > 0

    # ==================== CONVERSATIONS & CHAT HISTORY ====================

    def save_conversation(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        selected_plan_id: str,
        created_at: str,
        updated_at: str
    ) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO conversations (conversation_id, user_id, role, selected_plan_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (conversation_id, user_id, role, selected_plan_id, created_at, updated_at))
            conn.commit()

    def get_conversation(self, conversation_id: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def clear_all_conversations(self) -> None:
        """Wipes all conversation history and messages across all sessions."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM messages")
            cur.execute("DELETE FROM conversations")
            conn.commit()

    def list_conversations_for_user(
        self,
        user_id: str,
        authorized_plans: Optional[list[str]] = None,
        plan_id: Optional[str] = None
    ) -> list[dict]:
        """
        List conversations strictly for the authenticated user and authorized plans,
        only returning conversations that have at least one message (no empty chats).
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            params = [user_id]
            plan_clause = ""

            if plan_id:
                plan_clause = " AND c.selected_plan_id = ?"
                params.append(plan_id)
            elif authorized_plans is not None:
                if not authorized_plans:
                    return []
                placeholders = ",".join("?" for _ in authorized_plans)
                plan_clause = f" AND c.selected_plan_id IN ({placeholders})"
                params.extend(authorized_plans)

            sql = f"""
                SELECT c.*, COUNT(m.message_id) AS msg_count
                FROM conversations c
                INNER JOIN messages m ON c.conversation_id = m.conversation_id
                WHERE c.user_id = ?{plan_clause}
                GROUP BY c.conversation_id
                HAVING COUNT(m.message_id) > 0
                ORDER BY c.updated_at DESC
            """
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


    def save_message(
        self,
        message_id: str,
        conversation_id: str,
        role: str,
        content: str,
        citations_json: str,
        effective_scope_json: str,
        is_comparison: bool,
        is_clarification: bool,
        contains_unverified_notice: bool,
        timestamp: str
    ) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO messages (
                    message_id, conversation_id, role, content, citations_json,
                    effective_scope_json, is_comparison, is_clarification,
                    contains_unverified_notice, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id, conversation_id, role, content, citations_json,
                effective_scope_json, int(is_comparison), int(is_clarification),
                int(contains_unverified_notice), timestamp
            ))
            # Touch conversation updated_at
            cur.execute("UPDATE conversations SET updated_at = ? WHERE conversation_id = ?", (timestamp, conversation_id))
            conn.commit()

    def get_messages_for_conversation(self, conversation_id: str) -> list[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC", (conversation_id,))
            rows = cur.fetchall()
            messages = []
            for r in rows:
                m = dict(r)
                m["citations"] = json.loads(m.get("citations_json") or "[]")
                m["effective_scope"] = json.loads(m.get("effective_scope_json") or "[]")
                m["is_comparison"] = bool(m.get("is_comparison"))
                m["is_clarification"] = bool(m.get("is_clarification"))
                m["contains_unverified_notice"] = bool(m.get("contains_unverified_notice"))
                messages.append(m)
            return messages

    # ==================== AUDIT LOGGING ====================

    def record_audit_event(
        self,
        action: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        target_resource: Optional[str] = None,
        outcome: str = "SUCCESS",
        details: Optional[dict] = None
    ) -> str:
        """Appends an immutable audit log entry."""
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        sanitized_details = json.dumps(details or {})
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO audit_logs (
                        event_id, actor_id, actor_email, actor_role,
                        action, target_resource, outcome, details_json, timestamp
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id, actor_id, actor_email, actor_role,
                    action, target_resource, outcome, sanitized_details, now
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to record audit event '{action}': {e}")
        return event_id

    def get_audit_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        action_filter: Optional[str] = None,
        outcome_filter: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> tuple[list[dict], int]:
        """Returns paginated audit logs with optional filters."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            conditions = []
            params = []
            if action_filter:
                conditions.append("action LIKE ?")
                params.append(f"%{action_filter}%")
            if outcome_filter:
                conditions.append("outcome = ?")
                params.append(outcome_filter)
            if start_time:
                conditions.append("timestamp >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("timestamp <= ?")
                params.append(end_time)

            where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            
            # Total count
            cur.execute(f"SELECT COUNT(*) as total FROM audit_logs{where_clause}", params)
            total = cur.fetchone()["total"]

            # Paginated records
            query = f"SELECT * FROM audit_logs{where_clause} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                try:
                    r["details"] = json.loads(r.get("details_json") or "{}")
                except Exception:
                    r["details"] = {}
            return rows, total

    # ==================== RAG METRICS TELEMETRY ====================

    def record_rag_metric(
        self,
        request_id: str,
        user_id: str,
        role: str,
        plan_id: str,
        latency_retrieval_ms: float,
        latency_generation_ms: float,
        latency_total_ms: float,
        retrieved_chunks_count: int,
        citations_count: int,
        is_comparison: bool,
        status: str = "SUCCESS",
        error_category: Optional[str] = None
    ) -> str:
        """Records telemetry for an end-to-end RAG query."""
        metric_id = f"met_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO rag_request_metrics (
                        metric_id, request_id, user_id, role, plan_id,
                        latency_retrieval_ms, latency_generation_ms, latency_total_ms,
                        retrieved_chunks_count, citations_count, is_comparison,
                        status, error_category, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, request_id, user_id, role, plan_id,
                    round(latency_retrieval_ms, 2), round(latency_generation_ms, 2), round(latency_total_ms, 2),
                    retrieved_chunks_count, citations_count, int(is_comparison),
                    status, error_category, now
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to record RAG telemetry: {e}")
        return metric_id

    def get_rag_telemetry_summary(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> dict:
        """Returns aggregate RAG telemetry over the requested period."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            conditions = []
            params = []
            if start_time:
                conditions.append("created_at >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("created_at <= ?")
                params.append(end_time)

            where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""

            cur.execute(f"""
                SELECT
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_requests,
                    SUM(CASE WHEN status = 'NO_EVIDENCE' THEN 1 ELSE 0 END) as no_evidence_requests,
                    SUM(CASE WHEN status NOT IN ('SUCCESS', 'NO_EVIDENCE') THEN 1 ELSE 0 END) as failed_requests,
                    AVG(latency_retrieval_ms) as avg_retrieval_ms,
                    AVG(latency_generation_ms) as avg_generation_ms,
                    AVG(latency_total_ms) as avg_total_ms,
                    AVG(retrieved_chunks_count) as avg_chunks,
                    AVG(citations_count) as avg_citations,
                    SUM(CASE WHEN citations_count > 0 THEN 1 ELSE 0 END) as citations_valid_count
                FROM rag_request_metrics{where_clause}
            """, params)
            row = cur.fetchone()
            total = row["total_requests"] or 0
            success = row["successful_requests"] or 0
            success_rate = round((success / total * 100), 1) if total > 0 else 100.0
            citation_rate = round((row["citations_valid_count"] or 0) / total * 100, 1) if total > 0 else 100.0

            return {
                "total_retrieval_requests": total,
                "retrieval_success_rate": success_rate,
                "no_evidence_count": row["no_evidence_requests"] or 0,
                "failed_requests": row["failed_requests"] or 0,
                "avg_retrieval_latency_ms": round(row["avg_retrieval_ms"] or 0.0, 1),
                "avg_generation_latency_ms": round(row["avg_generation_ms"] or 0.0, 1),
                "avg_total_latency_ms": round(row["avg_total_ms"] or 0.0, 1),
                "avg_retrieved_chunks": round(row["avg_chunks"] or 0.0, 1),
                "avg_citations_per_answer": round(row["avg_citations"] or 0.0, 1),
                "citation_validation_rate": citation_rate
            }

    # ==================== DOCUMENT & INGESTION MANAGEMENT ====================

    def record_document(
        self,
        document_id: str,
        filename: str,
        plan_id: str,
        file_size_bytes: int = 0,
        chunk_count: int = 0,
        content_hash: str = "",
        status: str = "INDEXED"
    ) -> None:
        """Upserts a document record in the database."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO document_records (
                    document_id, filename, plan_id, content_hash,
                    file_size_bytes, file_type, status, chunk_count,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'application/pdf', ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    filename=excluded.filename,
                    plan_id=excluded.plan_id,
                    content_hash=excluded.content_hash,
                    file_size_bytes=excluded.file_size_bytes,
                    status=excluded.status,
                    chunk_count=excluded.chunk_count,
                    updated_at=excluded.updated_at
            """, (
                document_id, filename, plan_id, content_hash,
                file_size_bytes, status, chunk_count, now, now
            ))
            conn.commit()

    def record_ingestion_job(
        self,
        job_id: str,
        document_id: Optional[str],
        filename: str,
        plan_id: str,
        status: str,
        stage: str = "",
        error_summary: str = "",
        duration_ms: float = 0.0,
        chunk_count: int = 0
    ) -> None:
        """Records an ingestion job execution."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO ingestion_jobs (
                    job_id, document_id, filename, plan_id,
                    status, stage, error_summary, duration_ms, chunk_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, document_id, filename, plan_id,
                status, stage, error_summary, round(duration_ms, 2), chunk_count, now
            ))
            conn.commit()

    def get_document_records(
        self,
        limit: int = 50,
        offset: int = 0,
        plan_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> tuple[list[dict], int]:
        """Lists document records with plan, status, and timeline filtering."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            conditions = []
            params = []
            if plan_id:
                conditions.append("plan_id = ?")
                params.append(plan_id)
            if status:
                conditions.append("status = ?")
                params.append(status)
            if start_time:
                conditions.append("created_at >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("created_at <= ?")
                params.append(end_time)

            where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            cur.execute(f"SELECT COUNT(*) as total FROM document_records{where_clause}", params)
            total = cur.fetchone()["total"]

            query = f"SELECT * FROM document_records{where_clause} ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()], total

    def get_document_by_id(self, document_id: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM document_records WHERE document_id = ?", (document_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def delete_document_record(self, document_id: str) -> bool:
        """Marks document status as DELETED."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE document_records SET status = 'DELETED', updated_at = ? WHERE document_id = ?", (now, document_id))
            conn.commit()
            return cur.rowcount > 0

    def get_ingestion_jobs_list(self, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as total FROM ingestion_jobs")
            total = cur.fetchone()["total"]
            cur.execute("SELECT * FROM ingestion_jobs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
            return [dict(r) for r in cur.fetchall()], total

    # ==================== EXECUTIVE DASHBOARD OVERVIEW ====================

    def get_dashboard_overview_kpis(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> dict:
        """
        Calculates all persistent KPIs:
        - Registered users
        - Active users in window
        - New user registrations
        - Total customers
        - Total documents
        - Successfully indexed documents
        - Failed ingestion jobs
        - Total conversations
        - Total messages
        - Successful chat requests
        - Average response latency
        - Backend error rate
        """
        with self._get_connection() as conn:
            cur = conn.cursor()

            # 1. User metrics
            cur.execute("SELECT COUNT(*) as cnt FROM users")
            total_users = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) as cnt FROM users WHERE effective_role = 'customer'")
            total_customers = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) as cnt FROM users WHERE effective_role = 'employee'")
            total_employees = cur.fetchone()["cnt"]

            # New users in range
            user_time_clause = ""
            user_params = []
            if start_time:
                user_time_clause += " AND created_at >= ?"
                user_params.append(start_time)
            if end_time:
                user_time_clause += " AND created_at <= ?"
                user_params.append(end_time)

            cur.execute(f"SELECT COUNT(*) as cnt FROM users WHERE 1=1{user_time_clause}", user_params)
            new_users = cur.fetchone()["cnt"]

            # Active users: distinct users with session or message in window
            msg_time_clause = ""
            msg_params = []
            if start_time:
                msg_time_clause += " AND m.timestamp >= ?"
                msg_params.append(start_time)
            if end_time:
                msg_time_clause += " AND m.timestamp <= ?"
                msg_params.append(end_time)

            cur.execute(f"""
                SELECT COUNT(DISTINCT c.user_id) as cnt
                FROM conversations c
                JOIN messages m ON c.conversation_id = m.conversation_id
                WHERE 1=1{msg_time_clause}
            """, msg_params)
            active_users = cur.fetchone()["cnt"] or (1 if total_users > 0 else 0)

            # 2. Documents & Ingestion
            cur.execute("SELECT COUNT(*) as cnt FROM document_records WHERE status != 'DELETED'")
            total_docs = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) as cnt FROM document_records WHERE status = 'INDEXED'")
            indexed_docs = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) as cnt FROM ingestion_jobs WHERE status = 'FAILED'")
            failed_jobs = cur.fetchone()["cnt"]

            cur.execute("SELECT SUM(chunk_count) as total_chunks FROM document_records WHERE status = 'INDEXED'")
            total_chunks = cur.fetchone()["total_chunks"] or 0

            # 3. Conversations & Messages
            conv_time_clause = ""
            conv_params = []
            if start_time:
                conv_time_clause += " AND created_at >= ?"
                conv_params.append(start_time)
            if end_time:
                conv_time_clause += " AND created_at <= ?"
                conv_params.append(end_time)

            cur.execute(f"SELECT COUNT(*) as cnt FROM conversations WHERE 1=1{conv_time_clause}", conv_params)
            total_conversations = cur.fetchone()["cnt"]

            cur.execute(f"SELECT COUNT(*) as cnt FROM messages WHERE 1=1{msg_time_clause.replace('m.', '')}", msg_params)
            total_messages = cur.fetchone()["cnt"]

            # 4. Chat requests & Telemetry
            met_time_clause = ""
            met_params = []
            if start_time:
                met_time_clause += " AND created_at >= ?"
                met_params.append(start_time)
            if end_time:
                met_time_clause += " AND created_at <= ?"
                met_params.append(end_time)

            cur.execute(f"""
                SELECT
                    COUNT(*) as total_reqs,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success_reqs,
                    AVG(latency_total_ms) as avg_latency
                FROM rag_request_metrics WHERE 1=1{met_time_clause}
            """, met_params)
            met_row = cur.fetchone()
            total_chat_reqs = met_row["total_reqs"] or total_messages
            successful_chat_reqs = met_row["success_reqs"] or total_messages
            avg_latency = round(float(met_row["avg_latency"]), 1) if met_row["avg_latency"] is not None else None

            # 5. Error rate
            cur.execute(f"""
                SELECT
                    COUNT(*) as total_events,
                    SUM(CASE WHEN outcome IN ('FAILED', 'FORBIDDEN') THEN 1 ELSE 0 END) as err_events
                FROM audit_logs WHERE 1=1{met_time_clause.replace('created_at', 'timestamp')}
            """, met_params)
            audit_err = cur.fetchone()
            total_aud = audit_err["total_events"] or 0
            err_aud = audit_err["err_events"] or 0
            error_rate = round((err_aud / total_aud * 100), 2) if total_aud > 0 else 0.0

            return {
                "total_registered_users": total_users,
                "active_users": active_users,
                "new_user_registrations": new_users,
                "total_customers": total_customers,
                "total_employees": total_employees,
                "total_documents": total_docs,
                "indexed_documents": indexed_docs,
                "failed_ingestion_jobs": failed_jobs,
                "total_chunks_indexed": total_chunks,
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "successful_chat_requests": successful_chat_reqs,
                "average_response_latency_ms": avg_latency,
                "average_latency_ms": avg_latency,
                "backend_error_rate_pct": error_rate
            }

    def get_time_series_metrics(
        self,
        start_time: str,
        end_time: str,
        interval: str = "day"  # "hour" or "day"
    ) -> list[dict]:
        """
        Groups registrations, conversations, messages, and chat latencies
        by hourly or daily intervals for trend charting.
        """
        date_format = "%Y-%m-%d %H:00" if interval == "hour" else "%Y-%m-%d"
        with self._get_connection() as conn:
            cur = conn.cursor()
            # Fetch message counts grouped by time
            cur.execute(f"""
                SELECT
                    strftime('{date_format}', timestamp) as period,
                    COUNT(*) as message_count
                FROM messages
                WHERE timestamp >= ? AND timestamp <= ?
                GROUP BY period
                ORDER BY period ASC
            """, (start_time, end_time))
            msg_rows = {r["period"]: r["message_count"] for r in cur.fetchall()}

            # Fetch conversation counts grouped by time
            cur.execute(f"""
                SELECT
                    strftime('{date_format}', created_at) as period,
                    COUNT(*) as conv_count
                FROM conversations
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY period
                ORDER BY period ASC
            """, (start_time, end_time))
            conv_rows = {r["period"]: r["conv_count"] for r in cur.fetchall()}

            # Fetch user registrations grouped by time
            cur.execute(f"""
                SELECT
                    strftime('{date_format}', created_at) as period,
                    COUNT(*) as reg_count
                FROM users
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY period
                ORDER BY period ASC
            """, (start_time, end_time))
            user_rows = {r["period"]: r["reg_count"] for r in cur.fetchall()}

            # Fetch latency averages
            cur.execute(f"""
                SELECT
                    strftime('{date_format}', created_at) as period,
                    AVG(latency_total_ms) as avg_latency
                FROM rag_request_metrics
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY period
                ORDER BY period ASC
            """, (start_time, end_time))
            lat_rows = {r["period"]: round(r["avg_latency"] or 0, 1) for r in cur.fetchall()}

            # Union of periods
            all_periods = sorted(set(list(msg_rows.keys()) + list(conv_rows.keys()) + list(user_rows.keys()) + list(lat_rows.keys())))
            
            # If empty, provide a clean baseline point for current day
            if not all_periods:
                today_period = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:00" if interval == "hour" else "%Y-%m-%d")
                return [{
                    "period": today_period,
                    "messages": 0,
                    "conversations": 0,
                    "registrations": 0,
                    "avg_latency_ms": 0.0
                }]

            series = []
            for p in all_periods:
                series.append({
                    "period": p,
                    "messages": msg_rows.get(p, 0),
                    "conversations": conv_rows.get(p, 0),
                    "registrations": user_rows.get(p, 0),
                    "avg_latency_ms": lat_rows.get(p, 0.0)
                })
            return series

    # ==================== USER MANAGEMENT FOR ADMIN ====================

    def get_all_users_admin(
        self,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        role_filter: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> tuple[list[dict], int]:
        """Lists users with email, role, status, last activity, and plan authorizations."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            conditions = []
            params = []
            if search:
                conditions.append("(u.email LIKE ? OR u.full_name LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
            if role_filter:
                conditions.append("u.effective_role = ?")
                params.append(role_filter)
            if start_time:
                conditions.append("u.created_at >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("u.created_at <= ?")
                params.append(end_time)

            where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""

            cur.execute(f"SELECT COUNT(*) as total FROM users u{where_clause}", params)
            total = cur.fetchone()["total"]

            query = f"""
                SELECT
                    u.user_id,
                    u.email,
                    u.full_name,
                    u.requested_role,
                    u.effective_role as role,
                    u.is_approved,
                    u.created_at,
                    p.last_login,
                    p.governance_status,
                    ea.outcome as eligibility_outcome,
                    ea.confidence_score as eligibility_score,
                    ea.completed_at as eligibility_date,
                    ea.input_provenance_json as eligibility_input_json,
                    ps.selected_plan_id as active_plan_id,
                    ps.created_at as plan_selected_date
                FROM users u
                LEFT JOIN profiles p ON u.user_id = p.user_id
                LEFT JOIN eligibility_assessments ea ON u.user_id = ea.user_id AND ea.is_current = 1
                LEFT JOIN plan_selections ps ON u.user_id = ps.user_id AND ps.status IN ('ACTIVE', 'CONFIRMED')
                {where_clause}
                ORDER BY u.created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cur.execute(query, params)
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                if d.get("eligibility_input_json"):
                    try:
                        d["eligibility_input"] = json.loads(d["eligibility_input_json"])
                    except Exception:
                        d["eligibility_input"] = {}
                else:
                    d["eligibility_input"] = {}
                rows.append(d)
            return rows, total

    def update_user_status_admin(self, user_id: str, is_approved: int) -> bool:
        """Updates account approval status."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET is_approved = ? WHERE user_id = ?", (is_approved, user_id))
            conn.commit()
            return cur.rowcount > 0

    # ==================== ELIGIBILITY & PLAN SELECTION MANAGEMENT ====================

    def save_eligibility_assessment(
        self,
        user_id: str,
        status: str,
        outcome: str,
        qualifying_plans: list[str],
        input_provenance: dict,
        model_id: str = "ruleset_underwrite_v1",
        model_version: str = "1.0.0",
        confidence_score: Optional[float] = 1.0,
        reason_codes: Optional[list[str]] = None,
        review_status: str = "NONE",
        error_category: Optional[str] = None,
        expires_at: Optional[str] = None
    ) -> str:
        """
        Records a new eligibility assessment atomically.
        Supersedes any prior current assessment by setting is_current = 0.
        """
        assessment_id = f"asmt_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        reason_codes = reason_codes or []

        with self._get_connection() as conn:
            cur = conn.cursor()
            # Enforce server-side one-time completed assessment restriction
            if status == "COMPLETED":
                cur.execute("SELECT assessment_id FROM eligibility_assessments WHERE user_id = ? AND status = 'COMPLETED'", (user_id,))
                existing = cur.fetchone()
                if existing:
                    return existing["assessment_id"]

            # 1. Fetch previous current assessment ID
            cur.execute("SELECT assessment_id FROM eligibility_assessments WHERE user_id = ? AND is_current = 1", (user_id,))
            prev_row = cur.fetchone()
            prev_id = prev_row["assessment_id"] if prev_row else None

            # 2. Demote previous assessments
            cur.execute("UPDATE eligibility_assessments SET is_current = 0 WHERE user_id = ?", (user_id,))

            # 3. Insert new current assessment
            cur.execute("""
                INSERT INTO eligibility_assessments (
                    assessment_id, user_id, status, outcome, qualifying_plans_json,
                    input_provenance_json, model_id, model_version, confidence_score,
                    reason_codes_json, review_status, error_category, previous_assessment_id,
                    is_current, created_at, completed_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (
                assessment_id, user_id, status, outcome,
                json.dumps(qualifying_plans), json.dumps(input_provenance),
                model_id, model_version, confidence_score,
                json.dumps(reason_codes), review_status, error_category,
                prev_id, now, now if status in ("COMPLETED", "FAILED") else None, expires_at
            ))
            conn.commit()
            return assessment_id

    def get_completed_assessment_for_user(self, user_id: str) -> Optional[dict]:
        """
        Returns the authoritative completed eligibility assessment for a user if one exists.
        Ignores pending, failed, or incomplete assessments.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM eligibility_assessments
                WHERE user_id = ? AND status = 'COMPLETED'
                ORDER BY created_at DESC LIMIT 1
            """, (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = dict(row)
            data["qualifying_plans"] = json.loads(data.get("qualifying_plans_json") or "[]")
            data["input_provenance"] = json.loads(data.get("input_provenance_json") or "{}")
            data["reason_codes"] = json.loads(data.get("reason_codes_json") or "[]")
            return data

    def get_current_assessment_for_user(self, user_id: str) -> Optional[dict]:
        """Returns the current valid assessment for the user with deserialized JSON fields."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM eligibility_assessments
                WHERE user_id = ? AND is_current = 1
                ORDER BY created_at DESC LIMIT 1
            """, (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = dict(row)
            data["qualifying_plans"] = json.loads(data.get("qualifying_plans_json") or "[]")
            data["input_provenance"] = json.loads(data.get("input_provenance_json") or "{}")
            data["reason_codes"] = json.loads(data.get("reason_codes_json") or "[]")
            return data

    def get_assessment_by_id(self, assessment_id: str) -> Optional[dict]:
        """Returns the assessment matching the given ID."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM eligibility_assessments WHERE assessment_id = ?", (assessment_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = dict(row)
            data["qualifying_plans"] = json.loads(data.get("qualifying_plans_json") or "[]")
            data["input_provenance"] = json.loads(data.get("input_provenance_json") or "{}")
            data["reason_codes"] = json.loads(data.get("reason_codes_json") or "[]")
            return data

    def save_plan_selection(self, user_id: str, assessment_id: str, selected_plan_id: str) -> str:
        """
        Records a plan selection linked to a valid assessment.
        Marks any prior active selection as SWITCHED (preserves CONFIRMED selections).
        """
        selection_id = f"psel_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE plan_selections SET status = 'SWITCHED', updated_at = ? WHERE user_id = ? AND status = 'ACTIVE'", (now, user_id))
            cur.execute("""
                INSERT INTO plan_selections (
                    selection_id, user_id, assessment_id, selected_plan_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?)
            """, (selection_id, user_id, assessment_id, selected_plan_id, now, now))
            conn.commit()
            return selection_id

    def get_active_plan_selection_for_user(self, user_id: str) -> Optional[dict]:
        """Returns the active or confirmed plan selection for a user ordered by most recent created_at."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM plan_selections
                WHERE user_id = ? AND status IN ('ACTIVE', 'CONFIRMED')
                ORDER BY created_at DESC LIMIT 1
            """, (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_confirmed_plan_selection_for_user(self, user_id: str) -> Optional[dict]:
        """Returns the active confirmed plan selection for a user, if one exists."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM plan_selections
                WHERE user_id = ? AND status = 'CONFIRMED'
                ORDER BY confirmed_at DESC, created_at DESC LIMIT 1
            """, (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def confirm_customer_plan_selection(self, user_id: str, plan_id: str) -> Optional[dict]:
        """
        Confirms customer plan selection, updating status to CONFIRMED and recording confirmed_at timestamp.
        Idempotent: If already confirmed for this plan, returns the existing record without duplicate entries.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM plan_selections
                WHERE user_id = ? AND selected_plan_id = ? AND status IN ('ACTIVE', 'CONFIRMED')
                ORDER BY created_at DESC LIMIT 1
            """, (user_id, plan_id))
            row = cur.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("status") == "CONFIRMED" and data.get("confirmed_at"):
                return data

            cur.execute("""
                UPDATE plan_selections
                SET status = 'CONFIRMED', confirmed_at = ?, updated_at = ?
                WHERE selection_id = ?
            """, (now, now, data["selection_id"]))
            conn.commit()
            data["status"] = "CONFIRMED"
            data["confirmed_at"] = now
            data["updated_at"] = now
            return data

    def save_agent_contact_request(
        self,
        user_id: str,
        assessment_id: Optional[str],
        full_name: str,
        email: str,
        phone: Optional[str],
        preferred_contact_method: str = "EMAIL",
        notes: Optional[str] = None
    ) -> str:
        """Records a user request for licensed human agent assistance."""
        request_id = f"agtr_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO agent_contact_requests (
                    request_id, user_id, assessment_id, full_name, email, phone,
                    preferred_contact_method, notes, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """, (
                request_id, user_id, assessment_id, full_name, email, phone,
                preferred_contact_method, notes, now, now
            ))
            conn.commit()
            return request_id

    def get_agent_contact_requests(self, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
        """Returns paginated agent assistance requests and total count."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM agent_contact_requests")
            total = cur.fetchone()["cnt"]
            cur.execute("""
                SELECT * FROM agent_contact_requests
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            """, (limit, offset))
            rows = [dict(r) for r in cur.fetchall()]
            return rows, total

    def get_eligibility_pipeline_kpis(self, start_time: Optional[str] = None, end_time: Optional[str] = None) -> dict:
        """Calculates accurate, real-time analytics across the entire workflow funnel."""
        with self._get_connection() as conn:
            cur = conn.cursor()

            # 1. Total Registered Users
            cur.execute("SELECT COUNT(*) as cnt FROM users")
            total_registered = cur.fetchone()["cnt"]

            # 2. Total Users Assessed (completed)
            cur.execute("SELECT COUNT(DISTINCT user_id) as cnt FROM eligibility_assessments WHERE status = 'COMPLETED'")
            total_assessed_users = cur.fetchone()["cnt"]

            # 3. Eligible Users (current valid assessment is ELIGIBLE)
            cur.execute("""
                SELECT COUNT(DISTINCT user_id) as cnt
                FROM eligibility_assessments
                WHERE is_current = 1 AND status = 'COMPLETED' AND outcome = 'ELIGIBLE'
            """)
            eligible_users = cur.fetchone()["cnt"]

            # 4. Ineligible Users
            cur.execute("""
                SELECT COUNT(DISTINCT user_id) as cnt
                FROM eligibility_assessments
                WHERE is_current = 1 AND status = 'COMPLETED' AND outcome = 'INELIGIBLE'
            """)
            ineligible_users = cur.fetchone()["cnt"]

            # 5. Pending Review
            cur.execute("""
                SELECT COUNT(DISTINCT user_id) as cnt
                FROM eligibility_assessments
                WHERE is_current = 1 AND outcome = 'NEEDS_REVIEW'
            """)
            pending_review_users = cur.fetchone()["cnt"]

            # 6. Users Never Assessed
            cur.execute("""
                SELECT COUNT(*) as cnt FROM users
                WHERE user_id NOT IN (SELECT DISTINCT user_id FROM eligibility_assessments WHERE status = 'COMPLETED')
            """)
            not_assessed_users = cur.fetchone()["cnt"]

            # 7. Failed Assessment Attempts
            cur.execute("SELECT COUNT(*) as cnt FROM eligibility_assessments WHERE status = 'FAILED'")
            failed_assessments = cur.fetchone()["cnt"]

            # 8. Eligible Users Who Have Not Selected a Plan
            cur.execute("""
                SELECT COUNT(DISTINCT ea.user_id) as cnt
                FROM eligibility_assessments ea
                WHERE ea.is_current = 1 AND ea.outcome = 'ELIGIBLE'
                  AND ea.user_id NOT IN (SELECT DISTINCT user_id FROM plan_selections WHERE status IN ('ACTIVE', 'CONFIRMED'))
            """)
            eligible_no_plan = cur.fetchone()["cnt"]

            # 9. Users Who Selected a Plan
            cur.execute("SELECT COUNT(DISTINCT user_id) as cnt FROM plan_selections WHERE status IN ('ACTIVE', 'CONFIRMED')")
            plan_selected_users = cur.fetchone()["cnt"]

            # 10. Users Who Proceeded to Policy Chat
            cur.execute("""
                SELECT COUNT(DISTINCT c.user_id) as cnt
                FROM conversations c
                JOIN messages m ON c.conversation_id = m.conversation_id
                WHERE c.user_id IN (SELECT DISTINCT user_id FROM plan_selections WHERE status IN ('ACTIVE', 'CONFIRMED'))
            """)
            chat_active_users = cur.fetchone()["cnt"]

            # 11. Agent Assistance Requests
            cur.execute("SELECT COUNT(*) as cnt FROM agent_contact_requests")
            agent_requests = cur.fetchone()["cnt"]

            # Funnel Conversion Rates (Safe division guarding against division by zero)
            assessment_rate = round((total_assessed_users / total_registered * 100), 1) if total_registered > 0 else 0.0
            eligibility_rate = round((eligible_users / total_assessed_users * 100), 1) if total_assessed_users > 0 else 0.0
            plan_selection_rate = round((plan_selected_users / eligible_users * 100), 1) if eligible_users > 0 else 0.0
            chat_rate = round((chat_active_users / plan_selected_users * 100), 1) if plan_selected_users > 0 else 0.0

            return {
                "total_registered_users": total_registered,
                "total_users_assessed": total_assessed_users,
                "total_assessed_users": total_assessed_users,
                "eligible_users": eligible_users,
                "ineligible_users": ineligible_users,
                "pending_review_users": pending_review_users,
                "not_assessed_users": not_assessed_users,
                "users_not_assessed": not_assessed_users,
                "failed_assessments": failed_assessments,
                "eligible_without_plan_selection": eligible_no_plan,
                "plan_selected_users": plan_selected_users,
                "users_selected_plan": plan_selected_users,
                "policy_chat_active_users": chat_active_users,
                "users_proceeded_to_chat": chat_active_users,
                "agent_assistance_requests": agent_requests,
                "underwriting_eligibility_rate_pct": eligibility_rate,
                "plan_selection_conversion_rate_pct": plan_selection_rate,
                "chat_engagement_conversion_rate_pct": chat_rate,
                "funnel_rates": {
                    "assessment_rate_pct": assessment_rate,
                    "eligibility_rate_pct": eligibility_rate,
                    "plan_selection_rate_pct": plan_selection_rate,
                    "chat_engagement_rate_pct": chat_rate
                }
            }

# Global singleton
sqlite_db = SQLiteManager()

