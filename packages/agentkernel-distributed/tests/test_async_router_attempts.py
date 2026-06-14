import json
import unittest

from agentkernel_distributed.toolkit.models.async_router import AsyncModelRouter


class _FakeProvider:
    capabilities = ["chat"]
    model = "fake-model"

    def get_request_params(self, user_prompt, system_prompt, **kwargs):
        return {"url": "https://example.test/chat", "headers": {}, "json": {"prompt": user_prompt}}

    def parse_response(self, response):
        return [json.loads(response)["choices"][0]["message"]["content"]]


class _FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def text(self):
        return self.body

    def raise_for_status(self):
        return None


class _FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.closed = False

    def post(self, **kwargs):
        return next(self.responses)

    async def close(self):
        self.closed = True


class AsyncRouterAttemptTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.router = AsyncModelRouter()
        await self.router.session.close()
        self.router.providers = [_FakeProvider()]

    async def asyncTearDown(self):
        await self.router.close()

    async def test_chat_stops_at_max_attempts_and_records_failures(self):
        self.router.session = _FakeSession([
            _FakeResponse(500, "first failure"),
            _FakeResponse(503, "second failure"),
        ])

        result = await self.router.chat(
            "hello",
            max_attempts=2,
            _trace_context={"request_id": "req-1", "agent_id": "alice"},
        )

        self.assertIsNone(result)
        traces = self.router.drain_attempt_traces()
        self.assertEqual([row["attempt_number"] for row in traces], [1, 2])
        self.assertEqual([row["http_status"] for row in traces], [500, 503])
        self.assertTrue(all(row["status"] == "failed" for row in traces))
        self.assertTrue(all(row["request_id"] == "req-1" for row in traces))

    async def test_chat_records_exact_usage_on_success(self):
        body = json.dumps({
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        })
        self.router.session = _FakeSession([_FakeResponse(200, body)])

        result = await self.router.chat("hello", max_attempts=1)

        self.assertEqual(result, ["ok"])
        trace = self.router.drain_attempt_traces()[0]
        self.assertEqual(trace["status"], "success")
        self.assertEqual(trace["usage"]["total_tokens"], 6)
