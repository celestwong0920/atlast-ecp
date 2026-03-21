"""
Tests for streaming response recording in wrap.py.

Verifies that _RecordedStream:
1. Passes chunks through transparently (zero impact on user)
2. Records the complete response after stream ends
3. Works with iteration, context manager, and next()
4. Fail-Open: stream works even if recording fails
5. Works with OpenAI, Anthropic, and Gemini chunk formats
"""

import time
import threading
from unittest.mock import MagicMock, patch, PropertyMock
from atlast_ecp.wrap import _RecordedStream, _is_streaming


# ─── Mock Chunk Classes ──────────────────────────────────────────────────────

class MockOpenAIChunk:
    """Simulates an OpenAI streaming chunk."""
    def __init__(self, content=None, usage=None):
        self.choices = []
        if content is not None:
            delta = MagicMock()
            delta.content = content
            choice = MagicMock()
            choice.delta = delta
            self.choices = [choice]
        self.usage = usage


class MockAnthropicDelta:
    """Simulates an Anthropic content_block_delta event."""
    def __init__(self, text):
        self.delta = MagicMock()
        self.delta.text = text
        self.type = "content_block_delta"


class MockAnthropicMessageStart:
    """Simulates an Anthropic message_start event."""
    def __init__(self, input_tokens):
        self.message = MagicMock()
        self.message.usage = MagicMock()
        self.message.usage.input_tokens = input_tokens
        self.type = "message_start"


class MockAnthropicMessageDelta:
    """Simulates an Anthropic message_delta event."""
    def __init__(self, output_tokens):
        self.usage = MagicMock()
        self.usage.output_tokens = output_tokens
        self.type = "message_delta"


class MockGeminiChunk:
    """Simulates a Gemini streaming chunk."""
    def __init__(self, text, prompt_tokens=None, candidates_tokens=None):
        self.text = text
        if prompt_tokens is not None:
            self.usage_metadata = MagicMock()
            self.usage_metadata.prompt_token_count = prompt_tokens
            self.usage_metadata.candidates_token_count = candidates_tokens


# ─── Core Tests ──────────────────────────────────────────────────────────────

class TestRecordedStreamBasic:
    """Basic stream wrapper behavior."""

    def test_iteration_passes_all_chunks(self):
        """All chunks pass through unchanged."""
        chunks = ["Hello", " ", "world", "!"]
        stream = iter(chunks)
        recorded = []

        rs = _RecordedStream(
            stream, record_fn=lambda **kw: None,
            in_content="test", model="m", t_start=time.time(), provider="openai",
        )

        result = list(rs)
        assert result == chunks

    def test_next_passes_chunks(self):
        """next() works correctly."""
        chunks = ["a", "b", "c"]
        rs = _RecordedStream(
            iter(chunks), record_fn=lambda **kw: None,
            in_content="test", model="m", t_start=time.time(), provider="openai",
        )
        assert next(rs) == "a"
        assert next(rs) == "b"
        assert next(rs) == "c"

    def test_record_called_after_iteration(self):
        """record_fn is called exactly once after stream ends."""
        call_count = 0
        call_kwargs = {}

        def mock_record(**kwargs):
            nonlocal call_count, call_kwargs
            call_count += 1
            call_kwargs = kwargs

        chunks = ["Hello", " world"]
        rs = _RecordedStream(
            iter(chunks), record_fn=mock_record,
            in_content="prompt", model="gpt-4", t_start=time.time(), provider="openai",
        )
        list(rs)  # consume stream

        assert call_count == 1
        assert call_kwargs["input_content"] == "prompt"
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["step_type"] == "llm_call"

    def test_record_called_only_once(self):
        """Finalize is idempotent — only records once even if called multiple times."""
        call_count = 0

        def mock_record(**kwargs):
            nonlocal call_count
            call_count += 1

        rs = _RecordedStream(
            iter(["a"]), record_fn=mock_record,
            in_content="x", model="m", t_start=time.time(), provider="openai",
        )
        list(rs)
        rs._finalize()  # extra call
        rs._finalize()  # another extra call
        assert call_count == 1

    def test_context_manager(self):
        """Works as context manager."""
        call_count = 0

        def mock_record(**kwargs):
            nonlocal call_count
            call_count += 1

        stream = MagicMock()
        stream.__iter__ = MagicMock(return_value=iter(["a", "b"]))
        stream.__enter__ = MagicMock(return_value=stream)
        stream.__exit__ = MagicMock(return_value=False)

        rs = _RecordedStream(
            stream, record_fn=mock_record,
            in_content="x", model="m", t_start=time.time(), provider="openai",
        )

        with rs as s:
            pass  # __exit__ triggers finalize

        assert call_count == 1

    def test_fail_open_on_record_error(self):
        """Stream works even if record_fn raises."""
        def bad_record(**kwargs):
            raise RuntimeError("recording failed!")

        chunks = ["Hello", " world"]
        rs = _RecordedStream(
            iter(chunks), record_fn=bad_record,
            in_content="x", model="m", t_start=time.time(), provider="openai",
        )
        # Should not raise — fail-open
        result = list(rs)
        assert result == chunks

    def test_getattr_proxy(self):
        """Unknown attributes are proxied to underlying stream."""
        stream = MagicMock()
        stream.response = MagicMock()
        stream.response.status_code = 200

        rs = _RecordedStream(
            stream, record_fn=lambda **kw: None,
            in_content="x", model="m", t_start=time.time(), provider="openai",
        )
        assert rs.response.status_code == 200


# ─── Provider-Specific Extraction Tests ──────────────────────────────────────

class TestOpenAIStreamExtraction:
    """Test OpenAI chunk format extraction."""

    def test_extracts_text_from_openai_chunks(self):
        recorded_kwargs = {}

        def mock_record(**kwargs):
            recorded_kwargs.update(kwargs)

        chunks = [
            MockOpenAIChunk(content="Hello"),
            MockOpenAIChunk(content=" world"),
            MockOpenAIChunk(content="!"),
        ]

        rs = _RecordedStream(
            iter(chunks), record_fn=mock_record,
            in_content="prompt", model="gpt-4", t_start=time.time(), provider="openai",
        )
        list(rs)

        assert recorded_kwargs["output_content"] == "Hello world!"

    def test_handles_empty_chunks(self):
        recorded_kwargs = {}

        def mock_record(**kwargs):
            recorded_kwargs.update(kwargs)

        chunks = [
            MockOpenAIChunk(content=None),
            MockOpenAIChunk(content="hi"),
            MockOpenAIChunk(content=None),
        ]

        rs = _RecordedStream(
            iter(chunks), record_fn=mock_record,
            in_content="p", model="m", t_start=time.time(), provider="openai",
        )
        list(rs)
        assert recorded_kwargs["output_content"] == "hi"


class TestAnthropicStreamExtraction:
    """Test Anthropic chunk format extraction."""

    def test_extracts_text_and_tokens(self):
        recorded_kwargs = {}

        def mock_record(**kwargs):
            recorded_kwargs.update(kwargs)

        chunks = [
            MockAnthropicMessageStart(input_tokens=50),
            MockAnthropicDelta("Hello"),
            MockAnthropicDelta(" world"),
            MockAnthropicMessageDelta(output_tokens=10),
        ]

        rs = _RecordedStream(
            iter(chunks), record_fn=mock_record,
            in_content="prompt", model="claude-3", t_start=time.time(), provider="anthropic",
        )
        list(rs)

        assert recorded_kwargs["output_content"] == "Hello world"
        assert recorded_kwargs["tokens_in"] == 50
        assert recorded_kwargs["tokens_out"] == 10


class TestGeminiStreamExtraction:
    """Test Gemini chunk format extraction."""

    def test_extracts_text_from_gemini_chunks(self):
        recorded_kwargs = {}

        def mock_record(**kwargs):
            recorded_kwargs.update(kwargs)

        chunks = [
            MockGeminiChunk("Hello", prompt_tokens=20, candidates_tokens=5),
            MockGeminiChunk(" world"),
        ]

        rs = _RecordedStream(
            iter(chunks), record_fn=mock_record,
            in_content="p", model="gemini", t_start=time.time(), provider="gemini",
        )
        list(rs)

        assert recorded_kwargs["output_content"] == "Hello world"
        assert recorded_kwargs["tokens_in"] == 20


# ─── Integration Tests ───────────────────────────────────────────────────────

class TestIsStreaming:
    """Test _is_streaming helper."""

    def test_detects_stream_true(self):
        assert _is_streaming({"stream": True}) is True

    def test_detects_stream_false(self):
        assert _is_streaming({"stream": False}) is False

    def test_defaults_to_false(self):
        assert _is_streaming({}) is False


class TestStreamLatency:
    """Verify streaming wrapper adds negligible overhead."""

    def test_per_chunk_latency(self):
        """Each chunk should be yielded with < 0.1ms overhead."""
        n = 1000
        chunks = list(range(n))
        rs = _RecordedStream(
            iter(chunks), record_fn=lambda **kw: None,
            in_content="x", model="m", t_start=time.time(), provider="openai",
        )

        t_start = time.perf_counter()
        result = list(rs)
        elapsed_ms = (time.perf_counter() - t_start) * 1000

        assert result == chunks
        # 1000 chunks should take < 10ms total overhead
        assert elapsed_ms < 50, f"Too slow: {elapsed_ms:.1f}ms for {n} chunks"


class TestWrapStreaming:
    """Test that wrap() correctly routes streaming calls."""

    def test_openai_streaming_detected(self):
        """wrap() + stream=True returns a _RecordedStream."""
        from atlast_ecp.wrap import _wrap_openai

        mock_client = MagicMock()
        mock_stream = iter([MockOpenAIChunk(content="hi")])
        mock_client.chat.completions.create = MagicMock(return_value=mock_stream)

        wrapped = _wrap_openai(mock_client)
        result = wrapped.chat.completions.create(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4",
            stream=True,
        )
        assert isinstance(result, _RecordedStream)

    def test_openai_non_streaming_returns_response(self):
        """wrap() without stream returns normal response."""
        from atlast_ecp.wrap import _wrap_openai

        mock_response = MagicMock()
        mock_response.choices = []
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(return_value=mock_response)

        wrapped = _wrap_openai(mock_client)
        result = wrapped.chat.completions.create(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4",
        )
        # Should return the original response, not a _RecordedStream
        assert not isinstance(result, _RecordedStream)
