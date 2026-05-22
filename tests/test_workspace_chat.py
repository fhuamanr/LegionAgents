from pathlib import Path

import pytest

from core.chat import FileChatConversationRepository, WorkspaceChatService
from core.contracts.chat import ChatAttachmentUpload, ChatMessageRequest, WorkspaceAttachmentKind


@pytest.mark.asyncio
async def test_workspace_chat_persists_conversation_uploads_and_messages() -> None:
    storage = Path.cwd() / "outputs" / "workspace_chat_tests" / "conversations.json"
    if storage.exists():
        storage.unlink()
    service = WorkspaceChatService(repository=FileChatConversationRepository(storage))

    conversation = await service.create_conversation("Deliver story from chat", created_by="tester")
    attachment = await service.upload_attachment(
        conversation.id,
        ChatAttachmentUpload(
            kind=WorkspaceAttachmentKind.MARKDOWN,
            name="story.md",
            content="# Story\nAs a user, I want chat-triggered workflow execution.",
            content_type="text/markdown",
        ),
    )
    message = await service.add_message(
        conversation.id,
        ChatMessageRequest(
            content="Trigger the delivery workflow.",
            attachment_ids=(attachment.id,),
            trigger_workflow=True,
        ),
    )

    stored = await service.get_conversation(conversation.id)
    events = await service.event_bus.history(conversation.id)

    assert stored.title == "Deliver story from chat"
    assert stored.attachments[0].name == "story.md"
    assert stored.messages[0].id == message.id
    assert any(event.type == "attachment_uploaded" for event in events)


@pytest.mark.asyncio
async def test_workspace_chat_supports_url_and_git_references() -> None:
    service = WorkspaceChatService()
    conversation = await service.create_conversation("Reference workspace")

    url = await service.upload_attachment(
        conversation.id,
        ChatAttachmentUpload(kind=WorkspaceAttachmentKind.URL, name="Spec", uri="https://example.com/spec"),
    )
    git = await service.upload_attachment(
        conversation.id,
        ChatAttachmentUpload(kind=WorkspaceAttachmentKind.GIT_REPOSITORY, name="Repo", uri="https://gitlab.com/example/repo.git"),
    )

    assert url.uri == "https://example.com/spec"
    assert git.kind == WorkspaceAttachmentKind.GIT_REPOSITORY
