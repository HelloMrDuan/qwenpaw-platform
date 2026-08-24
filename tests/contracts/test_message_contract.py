import json
import unittest

from core.contracts import (
    Artifact,
    ArtifactKind,
    ChannelRef,
    MESSAGE_SCHEMA_VERSION,
    MessageContent,
    MessageEvent,
    MessageType,
    UserRef,
)


class MessageContractTests(unittest.TestCase):
    def make_artifact(self, kind: ArtifactKind = ArtifactKind.FILE) -> Artifact:
        return Artifact(
            id="art_001",
            kind=kind,
            name="sample.bin",
            mime_type="application/octet-stream",
            size_bytes=12,
            uri="artifact://incoming/art_001",
            metadata={"safe": True},
        )

    def make_message(self, **changes: object) -> MessageEvent:
        values = {
            "id": "msg_001",
            "version": MESSAGE_SCHEMA_VERSION,
            "trace_id": "trc_001",
            "channel": ChannelRef(
                type="console",
                instance_id="console-local",
                message_id="provider-001",
            ),
            "user": UserRef(id="usr_001", external_id="local-user"),
            "session_id": "ses_001",
            "conversation_id": "conv_001",
            "timestamp": "2026-08-24T08:30:00Z",
            "type": MessageType.TEXT,
            "content": MessageContent(text="hello"),
            "attachments": (),
            "metadata": {"source": "fixture"},
        }
        values.update(changes)
        return MessageEvent(**values)

    def test_json_round_trip_uses_schema_version(self) -> None:
        original = self.make_message()

        encoded = json.dumps(original.to_dict(), ensure_ascii=False)
        decoded = MessageEvent.from_dict(json.loads(encoded))

        self.assertEqual(decoded, original)
        self.assertEqual(decoded.schema_version, MESSAGE_SCHEMA_VERSION)
        self.assertIn('"schema_version": "message.v1"', encoded)
        self.assertNotIn('"version"', encoded)

    def test_file_message_requires_matching_artifact(self) -> None:
        with self.assertRaisesRegex(ValueError, "matching attachment"):
            self.make_message(
                type=MessageType.FILE,
                content=MessageContent(),
                attachments=(),
            )

        message = self.make_message(
            type=MessageType.FILE,
            content=MessageContent(),
            attachments=(self.make_artifact(),),
        )
        self.assertEqual(message.attachments[0].kind, ArtifactKind.FILE)

    def test_event_message_requires_namespaced_event_object(self) -> None:
        with self.assertRaisesRegex(ValueError, "require content.event"):
            self.make_message(type=MessageType.EVENT, content=MessageContent())

        message = self.make_message(
            type=MessageType.EVENT,
            content=MessageContent(
                event={"name": "channel.message.edited", "payload": {}}
            ),
        )
        self.assertEqual(message.content.event["name"], "channel.message.edited")

    def test_rejects_invalid_timestamp_and_artifact_uri(self) -> None:
        with self.assertRaisesRegex(ValueError, "ending in Z"):
            self.make_message(timestamp="2026-08-24T08:30:00+08:00")

        with self.assertRaisesRegex(ValueError, "artifact://"):
            Artifact(
                id="art_bad",
                kind=ArtifactKind.FILE,
                name="bad.txt",
                mime_type="text/plain",
                size_bytes=1,
                uri="D:/private/bad.txt",
            )

    def test_rejects_unknown_message_version_and_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported message version"):
            self.make_message(version="message.v2")
        with self.assertRaisesRegex(ValueError, "unsupported message type"):
            self.make_message(type="location")


if __name__ == "__main__":
    unittest.main()
