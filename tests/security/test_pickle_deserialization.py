"""Security tests for data-only RAG index persistence."""

from __future__ import annotations

import inspect
import json
import pickle

import numpy as np
import pytest

from pentestagent.knowledge.rag import Document, RAGEngine

_rce_executed: list[str] = []


def _rce_trigger() -> None:
    _rce_executed.append("EXECUTED")


class _RCEPayload:
    def __reduce__(self):
        return (_rce_trigger, ())


def _engine_with_index(tmp_path) -> RAGEngine:
    engine = RAGEngine(knowledge_path=tmp_path)
    engine.documents = [
        Document(
            content="hello security",
            source="test.txt",
            metadata={"kind": "test"},
        )
    ]
    engine.embeddings = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
    return engine


class TestRAGIndexSafety:
    def test_rag_module_does_not_use_pickle(self):
        import pentestagent.knowledge.rag as rag_module

        assert "pickle" not in inspect.getsource(rag_module)

    def test_json_index_round_trip(self, tmp_path):
        destination = tmp_path / "index.json"
        engine = _engine_with_index(tmp_path)

        engine.save_index(destination)

        raw = json.loads(destination.read_text(encoding="utf-8"))
        assert raw["schema_version"] == 1
        assert raw["documents"][0]["content"] == "hello security"

        restored = RAGEngine(knowledge_path=tmp_path)
        restored.load_index(destination)

        assert restored.documents[0].content == "hello security"
        assert restored.documents[0].metadata == {"kind": "test"}
        np.testing.assert_allclose(restored.embeddings, engine.embeddings)
        assert restored.documents[0].embedding is not None
        assert restored.get_document_count() == 1

    def test_malicious_pickle_is_rejected_without_execution(self, tmp_path):
        destination = tmp_path / "malicious.pkl"
        destination.write_bytes(pickle.dumps(_RCEPayload()))
        _rce_executed.clear()

        with pytest.raises(ValueError, match="UTF-8 JSON"):
            RAGEngine(knowledge_path=tmp_path).load_index(destination)

        assert _rce_executed == []

    def test_unknown_schema_is_rejected(self, tmp_path):
        destination = tmp_path / "index.json"
        destination.write_text(
            json.dumps(
                {
                    "schema_version": 999,
                    "documents": [],
                    "embeddings": None,
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="schema version"):
            RAGEngine(knowledge_path=tmp_path).load_index(destination)

    def test_document_embedding_count_mismatch_is_rejected(self, tmp_path):
        destination = tmp_path / "index.json"
        destination.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "documents": [
                        {
                            "content": "one",
                            "source": "test",
                            "metadata": {},
                            "doc_id": "one",
                        }
                    ],
                    "embeddings": [[0.1], [0.2]],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="counts do not match"):
            RAGEngine(knowledge_path=tmp_path).load_index(destination)

    def test_symlink_index_is_rejected(self, tmp_path):
        target = tmp_path / "target.json"
        _engine_with_index(tmp_path).save_index(target)
        link = tmp_path / "index.json"
        try:
            link.symlink_to(target)
        except OSError as exc:
            pytest.skip(f"symlinks are unavailable: {exc}")

        with pytest.raises(ValueError, match="non-symlink"):
            RAGEngine(knowledge_path=tmp_path).load_index(link)

    def test_non_finite_embeddings_are_rejected_on_save(self, tmp_path):
        engine = _engine_with_index(tmp_path)
        engine.embeddings[0, 0] = np.nan

        with pytest.raises(ValueError, match="non-finite"):
            engine.save_index(tmp_path / "index.json")

    def test_non_json_metadata_does_not_leave_partial_index(self, tmp_path):
        engine = _engine_with_index(tmp_path)
        engine.documents[0].metadata = {"opaque": object()}
        destination = tmp_path / "index.json"

        with pytest.raises(TypeError):
            engine.save_index(destination)

        assert not destination.exists()
