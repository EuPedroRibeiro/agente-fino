from __future__ import annotations

import unittest

from app.agent.providers.provider_status_cache import STATUS_CACHE, classify_provider_error


class ProviderStatusCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        STATUS_CACHE.clear()

    def test_online_status_is_cached(self) -> None:
        status = STATUS_CACHE.set_status("openai-responses", {"available": True, "openai_status": "online"})
        self.assertFalse(status["provider_status_cache_hit"])
        cached = STATUS_CACHE.get_status("openai-responses")
        self.assertIsNotNone(cached)
        self.assertTrue(cached["provider_status_cache_hit"])

    def test_quota_creates_cooldown(self) -> None:
        STATUS_CACHE.set_status("gemini", {"available": False, "gemini_status": "quota_exceeded"}, error="quota exceeded")
        self.assertTrue(STATUS_CACHE.is_cooling_down("gemini"))

    def test_error_classifier(self) -> None:
        self.assertEqual(classify_provider_error("HTTP 429 too many requests"), "rate_limited")
        self.assertEqual(classify_provider_error("request timed out"), "timeout")


if __name__ == "__main__":
    unittest.main()
