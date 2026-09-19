import unittest
import tempfile
import os
import json
from execution.pipeline import JobDiscoveryPipeline
from execution.sources.mock_source import MockJobSource
from execution.models import Recommendation


class TestJobDiscoveryPipeline(unittest.TestCase):

    def test_pipeline_end_to_end_with_mock_source(self):
        pipeline = JobDiscoveryPipeline(sources=[MockJobSource()])

        with tempfile.TemporaryDirectory() as tmp_dir:
            evaluations, md_report, json_report = pipeline.run(
                query="",
                limit_per_source=20,
                output_dir=tmp_dir
            )

            # Check that 6 fixtures with 1 duplicate produced 5 deduplicated jobs
            self.assertEqual(len(evaluations), 5)

            # Check ranking order (APPLY before REJECT)
            first_eval = evaluations[0]
            last_eval = evaluations[-1]
            self.assertEqual(first_eval.recommendation, Recommendation.APPLY)
            self.assertEqual(last_eval.recommendation, Recommendation.REJECT)
            self.assertGreaterEqual(first_eval.total_score, last_eval.total_score)

            # Check report output files
            md_path = os.path.join(tmp_dir, "job_discovery_report.md")
            json_path = os.path.join(tmp_dir, "job_discovery_report.json")
            self.assertTrue(os.path.exists(md_path))
            self.assertTrue(os.path.exists(json_path))

            # Verify JSON report structure
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(len(data), 5)
            self.assertIn("job_id", data[0])
            self.assertIn("score_breakdown", data[0])
            self.assertIn("evidence", data[0])


if __name__ == "__main__":
    unittest.main()
