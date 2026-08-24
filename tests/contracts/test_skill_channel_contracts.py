import asyncio
import json
import unittest

from core.contracts import (
    Artifact,
    ArtifactKind,
    ChannelAdapter,
    ChannelRef,
    DeliveryReceipt,
    DeliveryStatus,
    MESSAGE_SCHEMA_VERSION,
    MessageContent,
    MessageEvent,
    MessageType,
    SkillMetadata,
    SkillRequest,
    SkillResult,
    UserRef,
)


def fixture_message() -> MessageEvent:
    return MessageEvent(
        id="msg_001",
        version=MESSAGE_SCHEMA_VERSION,
        trace_id="trc_001",
        channel=ChannelRef(
            type="fake", instance_id="fake-local", message_id="provider-001"
        ),
        user=UserRef(id="usr_001", external_id="fake-user"),
        session_id="ses_001",
        conversation_id="conv_001",
        timestamp="2026-08-24T08:30:00Z",
        type=MessageType.TEXT,
        content=MessageContent(text="fixture"),
    )


class FakeChannelAdapter:
    """Local structural fixture; it does not connect to a provider."""

    channel_type = "fake"

    def parse_message(self, payload):
        del payload
        return fixture_message()

    async def send_message(
        self, session_id, message, *, artifacts=(), metadata=None
    ) -> DeliveryReceipt:
        del message, artifacts, metadata
        return DeliveryReceipt(
            delivery_id="delivery_001",
            channel=self.channel_type,
            session_id=session_id,
            status=DeliveryStatus.SENT,
        )

    async def send_stream_event(self, event):
        del event
        return None


class SkillAndChannelContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact = Artifact(
            id="art_001",
            kind=ArtifactKind.FILE,
            name="input.pdf",
            mime_type="application/pdf",
            size_bytes=128,
            uri="artifact://incoming/art_001",
        )

    def test_skill_metadata_and_request_are_serializable(self) -> None:
        metadata = SkillMetadata(
            id="pdf-editor",
            name="PDF Editor",
            version="1.0.0",
            description="Edits a PDF through an existing Skill boundary.",
            input_schema={"type": "object"},
        )
        request = SkillRequest(
            request_id="req_001",
            skill_id=metadata.id,
            files=(self.artifact,),
            parameters={"operation": "replace_text"},
            context={"task_id": "task_001"},
        )

        self.assertEqual(SkillMetadata.from_dict(metadata.to_dict()), metadata)
        encoded = json.dumps(request.to_dict())
        self.assertEqual(SkillRequest.from_dict(json.loads(encoded)), request)

    def test_skill_result_contains_message_artifacts_and_events(self) -> None:
        result = SkillResult(
            request_id="req_001",
            success=True,
            message="created",
            artifacts=(self.artifact,),
            events=(),
        )
        decoded = SkillResult.from_dict(result.to_dict())

        self.assertEqual(decoded.message, "created")
        self.assertEqual(decoded.artifacts, (self.artifact,))
        self.assertEqual(decoded.events, ())

    def test_failed_skill_result_requires_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "require an error"):
            SkillResult(
                request_id="req_001",
                success=False,
                message="failed",
            )

    def test_fake_adapter_satisfies_protocol_without_external_io(self) -> None:
        adapter = FakeChannelAdapter()
        self.assertIsInstance(adapter, ChannelAdapter)
        self.assertEqual(adapter.parse_message({}).channel.type, "fake")

        receipt = asyncio.run(adapter.send_message("ses_001", "hello"))
        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertIsNone(asyncio.run(adapter.send_stream_event(object())))


if __name__ == "__main__":
    unittest.main()
