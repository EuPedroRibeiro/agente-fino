from __future__ import annotations

import unittest

from app.agent.providers.model_router import ModelRouter
from app.agent.providers.provider_status_cache import STATUS_CACHE


class CircuitBreakerTests(unittest.TestCase):
    def setUp(self) -> None:
        STATUS_CACHE.clear()

    def test_gemini_quota_skips_direct_fast_attempt(self) -> None:
        STATUS_CACHE.set_status("gemini", {"available": False, "gemini_status": "quota_exceeded"}, error="quota exceeded")
        chain = ModelRouter().provider_chain_for_mode("FAST", direct=True)
        self.assertNotIn("gemini", [provider.name for provider in chain])

    def test_openai_rate_limit_skips_direct_fast_attempt(self) -> None:
        STATUS_CACHE.set_status("openai-responses", {"available": False, "openai_status": "rate_limited"}, error="429 rate limit")
        chain = ModelRouter().provider_chain_for_mode("FAST", direct=True)
        self.assertNotIn("openai-responses", [provider.name for provider in chain])


if __name__ == "__main__":
    unittest.main()
