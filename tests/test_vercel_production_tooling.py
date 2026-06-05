import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VercelProductionToolingTests(unittest.TestCase):
    def test_production_scripts_exist(self):
        self.assertTrue((ROOT / "tools" / "check_production_readiness.ps1").exists())
        self.assertTrue((ROOT / "tools" / "configure_vercel_free_env.ps1").exists())
        self.assertTrue((ROOT / "tools" / "configure_vercel_production_env.ps1").exists())
        self.assertTrue((ROOT / "tools" / "deploy_vercel_production.ps1").exists())
        self.assertTrue((ROOT / "docs" / "FREE_DEPLOY_NO_BILLING.md").exists())

    def test_configure_script_uses_vercel_env_add_not_deploy_env_args(self):
        script = (ROOT / "tools" / "configure_vercel_production_env.ps1").read_text(encoding="utf-8")
        self.assertIn('"env", "add"', script)
        self.assertIn("--sensitive", script)
        self.assertNotIn("deploy --env", script)
        self.assertNotIn("--env DATABASE_URL", script)

    def test_free_mode_disables_openai_by_default(self):
        script = (ROOT / "tools" / "configure_vercel_production_env.ps1").read_text(encoding="utf-8")
        free_wrapper = (ROOT / "tools" / "configure_vercel_free_env.ps1").read_text(encoding="utf-8")
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn('Name = "OPENAI_ENABLED"; Value = ($(if ($IncludeOpenAI)', script)
        self.assertIn('Remove-VercelEnvIfPresent "OPENAI_API_KEY"', script)
        self.assertNotIn("-IncludeOpenAI", free_wrapper)
        self.assertIn("OPENAI_ENABLED=false", env_example)
        self.assertIn("OPENAI_USE_FOR_VERIFICATION=false", env_example)
        self.assertIn("OPENAI_FAST_ENABLED=false", env_example)

    def test_readiness_checks_no_billing_openai_flag(self):
        script = (ROOT / "tools" / "check_production_readiness.ps1").read_text(encoding="utf-8")
        self.assertIn("no_billing_openai_disabled", script)
        self.assertIn("AllowPaidProviders", script)

    def test_scripts_do_not_contain_known_secret_prefixes(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                ROOT / "tools" / "check_production_readiness.ps1",
                ROOT / "tools" / "configure_vercel_production_env.ps1",
                ROOT / "tools" / "deploy_vercel_production.ps1",
            ]
        )
        self.assertNotIn("sk-proj-", combined)
        self.assertNotIn("AIza", combined)


if __name__ == "__main__":
    unittest.main()
