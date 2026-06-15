import unittest

from scripts.diagnose_benchmark_mapping import _suggest_mapping


class BenchmarkMappingDiagnosisTest(unittest.TestCase):
    def test_high_confidence_group_suggestion(self):
        suggestion = _suggest_mapping("证券")
        self.assertEqual(suggestion["suggested_benchmark_code"], "512880.SH")
        self.assertEqual(suggestion["suggested_action"], "add_mapping")
        self.assertEqual(suggestion["confidence"], "high")

    def test_theme_cluster_falls_back_to_manual_review(self):
        suggestion = _suggest_mapping("", "AI服务")
        self.assertEqual(suggestion["suggested_action"], "manual_review")

    def test_unknown_group_stays_manual_review(self):
        suggestion = _suggest_mapping("其他通用设备")
        self.assertEqual(suggestion["suggested_action"], "manual_review")
        self.assertEqual(suggestion["suggested_benchmark_code"], "")


if __name__ == "__main__":
    unittest.main()
