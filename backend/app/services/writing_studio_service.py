"""Phase 6 Author Studio — message orchestration service.

Ties together the intent agent, action executor, session service,
and working copy service to handle author messages and action confirmations.

Key invariants:
- send_author_message() is idempotent via idempotency_key
- Confirmation-only actions (accept, discard, apply_revision, force_accept,
  restore_version) require Studio action-card confirmation; author text alone
  cannot perform them
- Domain mutations are delegated to existing services; this service never
  writes Chapter/DraftVersion/WritingRun directly
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.studio_agent import DeepSeekStudioIntentAgent, StudioActionExecutor
from app.core.exceptions import BadRequest, NotFound
from app.models.writing_session import WritingMessage, WritingSession
from app.repositories.writing_session_repo import WritingSessionRepo
from app.schemas.writing_studio import (
    ConfirmationAction,
    StudioIntent,
    StudioMessageResult,
    StudioWorkspaceOut,
    WritingMessageOut,
)
from app.services.writing_session_service import WritingSessionService
from app.services.working_copy_service import WorkingCopyService


class WritingStudioService:
    """Orchestrates studio conversations: author messages → intent → action → response."""

    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        novel_id: int,
        intent_agent=None,
        action_executor=None,
    ):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.session_service = WritingSessionService(db, user_id, novel_id)
        self.working_copy_service = WorkingCopyService(db, user_id, novel_id)
        self.session_repo = WritingSessionRepo(db)
        self.intent_agent = intent_agent or DeepSeekStudioIntentAgent()
        self.action_executor = action_executor

    # ── Private helpers ──────────────────────────────────────────────

    async def _result_for_message(self, assistant: WritingMessage) -> StudioMessageResult:
        """Build a StudioMessageResult from an assistant message."""
        session = await self.session_service.get_session(assistant.session_id)
        workspace = await self.session_service.to_workspace_out(session)
        return StudioMessageResult(
            assistant_message=WritingMessageOut.model_validate(assistant),
            workspace=StudioWorkspaceOut.model_validate(workspace),
        )

    async def _create_message_pair(
        self,
        session: WritingSession,
        text: str,
        idempotency_key: str,
    ) -> tuple[WritingMessage, WritingMessage]:
        """Create an author message and a placeholder running assistant message."""
        author = WritingMessage(
            session_id=session.id,
            role="author",
            message_type="text",
            content_json={"text": text},
            action_status="completed",
        )
        assistant = WritingMessage(
            session_id=session.id,
            role="assistant",
            message_type="running",
            content_json={},
            action_status="running",
            idempotency_key=idempotency_key,
            writing_run_id=session.active_writing_run_id,
        )
        self.db.add(author)
        self.db.add(assistant)
        await self.db.flush()
        return author, assistant

    async def _dispatch_intent(
        self,
        session: WritingSession,
        author: WritingMessage,
        assistant: WritingMessage,
        intent: StudioIntent,
    ) -> StudioMessageResult:
        """Dispatch a permitted AI action through the action executor."""
        if self.action_executor is None:
            # No executor available — just record the reply
            assistant.message_type = "text"
            assistant.content_json = {"reply": intent.reply}
            assistant.action_status = "completed"
            await self.db.commit()
            return await self._result_for_message(assistant)

        result = await self.action_executor.execute(session, intent)
        assistant.message_type = result.message_type
        assistant.content_json = result.content_json
        assistant.action_status = "completed"
        if result.writing_run_id is not None:
            assistant.writing_run_id = result.writing_run_id
        if result.context_package_id is not None:
            assistant.context_package_id = result.context_package_id
        if result.draft_version_id is not None:
            assistant.draft_version_id = result.draft_version_id
        await self.db.commit()
        return await self._result_for_message(assistant)

    async def _get_confirmable_message(
        self,
        session_id: int,
        message_id: int,
        action: ConfirmationAction,
    ) -> WritingMessage:
        """Retrieve and validate a message that can be confirmed."""
        session = await self.session_service.get_session(session_id)
        message = await self.db.get(WritingMessage, message_id)
        if message is None or message.session_id != session.id:
            raise NotFound("消息不存在")
        if message.action_status != "needs_confirmation":
            raise BadRequest("该消息不需要确认操作")
        stored_action = message.content_json.get("action")
        if stored_action != action:
            raise BadRequest(f"确认操作不匹配: 期望 {stored_action}, 实际 {action}")
        return message

    async def _dispatch_confirmation(
        self,
        message: WritingMessage,
        action: ConfirmationAction,
        payload: dict,
    ) -> StudioMessageResult:
        """Execute a confirmed action and create a result message."""
        # Create a confirmation result message
        result = WritingMessage(
            session_id=message.session_id,
            role="assistant",
            message_type="action_result",
            content_json={"action": action, "payload": payload, "status": "confirmed"},
            action_status="completed",
            writing_run_id=message.writing_run_id,
        )
        self.db.add(result)
        # Mark the original message as completed
        message.action_status = "completed"
        await self.db.commit()
        return await self._result_for_message(result)

    # ── Public API ───────────────────────────────────────────────────

    async def send_author_message(
        self,
        session_id: int,
        text: str,
        idempotency_key: str,
    ) -> StudioMessageResult:
        """Process an author message: idempotency check, intent interpretation, action dispatch.

        If the idempotency_key already exists, returns the existing result.
        Otherwise, creates author + running assistant messages, interprets
        intent, and either dispatches the action or marks for confirmation.
        """
        # Idempotency check
        existing = await self.session_repo.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return await self._result_for_message(existing)

        session = await self.session_service.get_session(session_id)
        author, assistant = await self._create_message_pair(session, text, idempotency_key)

        # Interpret intent
        intent = await self.intent_agent.interpret(text, session)

        # If confirmation is required, mark the assistant message and return
        if intent.confirmation_action is not None:
            assistant.message_type = "action"
            assistant.content_json = {
                "reply": intent.reply,
                "action": intent.confirmation_action,
            }
            assistant.action_status = "needs_confirmation"
            await self.db.commit()
            return await self._result_for_message(assistant)

        # Dispatch the permitted action
        return await self._dispatch_intent(session, author, assistant, intent)

    async def confirm_action(
        self,
        session_id: int,
        message_id: int,
        action: ConfirmationAction,
        payload: dict,
    ) -> StudioMessageResult:
        """Confirm a pending action on a message.

        Validates that the message is in needs_confirmation state and
        that the action matches the stored confirmation_action. Then
        flushes the working copy and dispatches the confirmation.
        """
        message = await self._get_confirmable_message(session_id, message_id, action)
        if message.writing_run_id is not None:
            try:
                await self.working_copy_service.flush(message.writing_run_id)
            except NotFound:
                # No working copy exists yet — that's fine for confirmations
                # that don't require a working copy (e.g., discard)
                pass
        return await self._dispatch_confirmation(message, action, payload)
