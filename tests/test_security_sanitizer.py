from __future__ import annotations

import unittest

from app.agent.security.sanitizer import contains_secret, mask_secrets


class SecuritySanitizerTests(unittest.TestCase):
    def test_masks_api_keys(self) -> None:
        text = "GEMINI" + "_API_KEY=" + "AI" + "zaSyExampleSecretKeyThatShouldBeMasked"
        self.assertIn("***", mask_secrets(text))

    def test_detects_secret_payload(self) -> None:
        self.assertTrue(contains_secret("token: abcdefghijklmnopqrstuvwxyz123"))


if __name__ == "__main__":
    unittest.main()
