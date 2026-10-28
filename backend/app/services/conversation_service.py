import json
import time
import uuid
from typing import Optional
from pydantic import BaseModel, Field
from backend.app.services.auth_service import AuthorizationService, ROLE_PLAN_PERMISSIONS
from backend.app.services.generation_service import SourceCitation
from backend.app.db.sqlite_manager import sqlite_db
from backend.app.core.config import settings
from backend.app.core.logging_config import logger

CONVERSATIONS_STORE_PATH = settings.STAGING_DIR / "conversations.json"

class ChatMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:10]}")
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    citations: list[SourceCitation] = Field(default_factory=list)
    effective_scope: list[str] = Field(default_factory=list)
    is_comparison: bool = False
    is_clarification: bool = False
    contains_unverified_notice: bool = False
    suggested_follow_ups: list[str] = Field(default_factory=list)

class ConversationSession(BaseModel):
    conversation_id: str
    user_id: str
    role: str
    selected_plan_id: str
    created_at: str
    updated_at: str
    messages: list[ChatMessage] = Field(default_factory=list)

class ConversationManager:
    """
    Manages server-side, plan-scoped conversation state.
    Enforces authorization upon creation and guarantees that conversations
    never leak context across distinct plans.
    """

    def __init__(self):
        self.sessions: dict[str, ConversationSession] = {}
        self._load_store()

    def _load_store(self) -> None:
        if CONVERSATIONS_STORE_PATH.exists():
            try:
                with open(CONVERSATIONS_STORE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for cid, s_dict in data.items():
                        self.sessions[cid] = ConversationSession(**s_dict)
                logger.info(f"Loaded {len(self.sessions)} active conversations from store.")
            except Exception as e:
                logger.error(f"Error reading conversation store: {e}")

    def _persist_store_sync(self) -> None:
        try:
            # Only persist sessions that have at least one message (no empty chats)
            active_data = {
                cid: s.model_dump()
                for cid, s in list(self.sessions.items())
                if len(s.messages) > 0
            }
            tmp_path = CONVERSATIONS_STORE_PATH.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(active_data, f, indent=2)
            tmp_path.replace(CONVERSATIONS_STORE_PATH)
        except Exception as e:
            logger.error(f"Failed to persist conversation store: {e}")

    def _persist_store(self, async_write: bool = True) -> None:
        if async_write:
            import threading
            threading.Thread(target=self._persist_store_sync, daemon=True).start()
        else:
            self._persist_store_sync()

    def clear_all_conversations(self) -> None:
        """Wipes all active in-memory sessions, persistent JSON cache, and SQLite records."""
        self.sessions.clear()
        if CONVERSATIONS_STORE_PATH.exists():
            try:
                CONVERSATIONS_STORE_PATH.unlink()
            except Exception as e:
                logger.error(f"Failed to remove conversation JSON file: {e}")
        sqlite_db.clear_all_conversations()
        logger.info("Cleared all conversation history across all sessions.")

    def create_conversation(
        self,
        user_id: str,
        role: str,
        selected_plan_id: str
    ) -> ConversationSession:
        """Create a new conversation session for an authorized plan. Fails closed with 403 if unauthorized."""
        AuthorizationService.validate_plan_access(role, selected_plan_id)
        
        cid = f"conv_{uuid.uuid4().hex[:12]}"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        session = ConversationSession(
            conversation_id=cid,
            user_id=user_id,
            role=role,
            selected_plan_id=selected_plan_id,
            created_at=now,
            updated_at=now,
            messages=[]
        )
        self.sessions[cid] = session
        # Persist conversation session immediately in SQLite so server restarts/reloads retain it
        try:
            sqlite_db.save_conversation(
                conversation_id=cid,
                user_id=user_id,
                role=role,
                selected_plan_id=selected_plan_id,
                created_at=now,
                updated_at=now
            )
        except Exception as e:
            logger.error(f"Failed to persist initial conversation session to SQLite: {e}")

        logger.info(f"Initialized active session '{cid}' for plan '{selected_plan_id}' (User: {user_id}, Role: {role})")
        return session

    def get_conversation(
        self,
        conversation_id: str,
        user_id: str,
        role: Optional[str] = None,
        allow_admin_inspection: bool = False
    ) -> Optional[ConversationSession]:
        session = self.sessions.get(conversation_id)
        if not session:
            # Fallback check in SQLite
            db_c = sqlite_db.get_conversation(conversation_id)
            if db_c:
                db_msgs = sqlite_db.get_messages_for_conversation(conversation_id)
                session = ConversationSession(
                    conversation_id=db_c["conversation_id"],
                    user_id=db_c["user_id"],
                    role=db_c["role"],
                    selected_plan_id=db_c["selected_plan_id"],
                    created_at=db_c["created_at"],
                    updated_at=db_c["updated_at"],
                    messages=[
                        ChatMessage(
                            message_id=m["message_id"],
                            role=m["role"],
                            content=m["content"],
                            timestamp=m["timestamp"],
                            citations=[SourceCitation(**c) for c in m.get("citations", [])],
                            effective_scope=m.get("effective_scope", []),
                            is_comparison=m.get("is_comparison", False),
                            is_clarification=m.get("is_clarification", False),
                            contains_unverified_notice=m.get("contains_unverified_notice", False)
                        )
                        for m in db_msgs
                    ]
                )
                self.sessions[conversation_id] = session
            else:
                return None

        # Enforce strict user isolation boundary (prevent cross-user conversation snooping)
        if session.user_id != user_id and not (role == "admin" and allow_admin_inspection):
            logger.warning(f"User '{user_id}' (role='{role}') denied access to conversation '{conversation_id}' owned by '{session.user_id}'")
            return None

        # Enforce strict role-based plan access (e.g. Customer can never access employee plans)
        if role:
            authorized_plans = ROLE_PLAN_PERMISSIONS.get(role, set())
            if session.selected_plan_id not in authorized_plans:
                logger.warning(f"Role '{role}' denied access to plan '{session.selected_plan_id}' in conversation '{conversation_id}'")
                return None

        return session

    def list_conversations_for_user(
        self,
        user_id: str,
        role: str,
        plan_id: Optional[str] = None
    ) -> list[dict]:
        """
        List all saved conversations strictly owned by user_id and authorized for role.
        Enforces RBAC: customers never see employee plans.
        Filters out empty chats (message_count == 0).
        """
        authorized_plans = list(ROLE_PLAN_PERMISSIONS.get(role, set()))
        if plan_id and plan_id not in authorized_plans:
            return []

        db_convs = sqlite_db.list_conversations_for_user(
            user_id=user_id,
            authorized_plans=authorized_plans,
            plan_id=plan_id
        )
        seen_ids = set()
        results = []

        for c in db_convs:
            cid = c["conversation_id"]
            seen_ids.add(cid)
            msg_count = c.get("msg_count", 0)
            if msg_count == 0:
                continue

            session = self.sessions.get(cid)
            if session and session.messages:
                first_user_msg = next((m.content for m in session.messages if m.role == "user"), None)
            else:
                msgs = sqlite_db.get_messages_for_conversation(cid)
                first_user_msg = next((m.get("content") for m in msgs if m.get("role") == "user"), None)

            title = (first_user_msg[:65] + "...") if first_user_msg and len(first_user_msg) > 65 else (first_user_msg or "Policy Inquiry")
            results.append({
                "conversation_id": cid,
                "selected_plan_id": c.get("selected_plan_id", ""),
                "created_at": c.get("created_at", ""),
                "updated_at": c.get("updated_at", ""),
                "message_count": msg_count,
                "preview_title": title
            })

        # Also inspect in-memory sessions that belong strictly to this user and have user messages
        for cid, s in self.sessions.items():
            if cid in seen_ids:
                continue
            if s.user_id != user_id and s.user_id != "guest_user" and user_id != "guest_user":
                continue
            if s.selected_plan_id not in authorized_plans:
                continue
            if plan_id and s.selected_plan_id != plan_id:
                continue
            user_msgs = [m for m in s.messages if m.role == "user"]
            if not user_msgs:
                continue

            first_user_msg = user_msgs[0].content
            title = (first_user_msg[:65] + "...") if len(first_user_msg) > 65 else first_user_msg
            results.append({
                "conversation_id": cid,
                "selected_plan_id": s.selected_plan_id,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "message_count": len(s.messages),
                "preview_title": title
            })

        results.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return results

    def add_turn(
        self,
        conversation_id: str,
        user_id: str,
        user_query: str,
        assistant_answer: str,
        citations: list[SourceCitation],
        effective_scope: list[str],
        is_comparison: bool = False,
        is_clarification: bool = False,
        contains_unverified: bool = False,
        suggested_follow_ups: Optional[list[str]] = None
    ) -> ChatMessage:
        session = self.get_conversation(conversation_id, user_id)
        if not session:
            raise ValueError(f"Conversation '{conversation_id}' not found or access denied.")

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # User turn (only append if user_query is provided)
        if user_query:
            u_msg = ChatMessage(
                role="user",
                content=user_query,
                timestamp=now
            )
            session.messages.append(u_msg)

        # Assistant turn
        a_msg = ChatMessage(
            role="assistant",
            content=assistant_answer,
            timestamp=now,
            citations=citations,
            effective_scope=effective_scope,
            is_comparison=is_comparison,
            is_clarification=is_clarification,
            contains_unverified_notice=contains_unverified,
            suggested_follow_ups=suggested_follow_ups or []
        )
        session.messages.append(a_msg)
        session.updated_at = now

        # Keep session bounded (last 20 messages)
        if len(session.messages) > 20:
            session.messages = session.messages[-20:]

        try:
            # Ensure conversation row is created in SQLite if not yet saved
            if not sqlite_db.get_conversation(conversation_id):
                sqlite_db.save_conversation(
                    conversation_id=conversation_id,
                    user_id=session.user_id,
                    role=session.role,
                    selected_plan_id=session.selected_plan_id,
                    created_at=session.created_at,
                    updated_at=now
                )

            if user_query:
                sqlite_db.save_message(
                    message_id=u_msg.message_id,
                    conversation_id=conversation_id,
                    role=u_msg.role,
                    content=u_msg.content,
                    citations_json="[]",
                    effective_scope_json="[]",
                    is_comparison=False,
                    is_clarification=False,
                    contains_unverified_notice=False,
                    timestamp=u_msg.timestamp
                )
            sqlite_db.save_message(
                message_id=a_msg.message_id,
                conversation_id=conversation_id,
                role=a_msg.role,
                content=a_msg.content,
                citations_json=json.dumps([c.model_dump() for c in citations]),
                effective_scope_json=json.dumps(effective_scope),
                is_comparison=is_comparison,
                is_clarification=is_clarification,
                contains_unverified_notice=contains_unverified,
                timestamp=a_msg.timestamp
            )
        except Exception as e:
            logger.error(f"Failed to persist chat messages to SQLite: {e}")

        self._persist_store(async_write=True)
        return a_msg

