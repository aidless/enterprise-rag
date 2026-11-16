#!/usr/bin/env python3
"""Drift tests. They must fail if a README number is no longer the JSON recount."""
from __future__ import annotations

import unittest

from check.recompute import (
    FORBIDDEN,
    OBSERVED_ABOUT,
    about_replacement,
    assert_json_consistent,
    bootstrap_mean,
    collect_errors,
    evidence_facts,
    render_evidence,
    scan_lines,
)


class RecomputeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = evidence_facts()

    def test_published_summaries_match_rows(self):
        self.assertEqual(assert_json_consistent(self.facts), [])
        self.assertEqual(self.facts["h_hits"], 8)
        self.assertEqual(self.facts["d_hits"], 5)
        self.assertAlmostEqual(self.facts["h_mrr"], 0.55)
        self.assertAlmostEqual(self.facts["d_mrr"], 0.45)

    def test_bootstrap_is_deterministic_and_wide(self):
        flags = [1.0 if row["hit"] else 0.0 for row in self.facts["dense_arm"]["per_item"]]
        self.assertEqual(bootstrap_mean(flags), bootstrap_mean(flags))
        lo, hi = self.facts["dense_ci"]
        self.assertGreaterEqual(hi - lo, 0.5)
        self.assertLessEqual(self.facts["sparse_ci"][0], self.facts["dense_ci"][1])
        self.assertLessEqual(self.facts["dense_ci"][0], self.facts["sparse_ci"][1])

    def test_problem_statement_is_three_lines(self):
        rendered = render_evidence(self.facts)
        statement = []
        for line in rendered.splitlines():
            if not line.strip():
                break
            statement.append(line)
        self.assertEqual(len(statement), 3)
        self.assertIn("not a generalization result", statement[1])
        self.assertIn("does not claim that sparse beats dense", statement[2])
        self.assertNotIn("allow-number", rendered)
        self.assertNotIn("3.25", rendered)

    def test_scanner_can_go_red(self):
        errs = scan_lines("README.md", ["recall@3 allow-number, p50 3.25ms"])
        self.assertTrue(any("allow-number" in err for err in errs))
        observed = [f"Observed (false): {OBSERVED_ABOUT}"]
        self.assertEqual(scan_lines("README.md", observed), [])

    def test_about_text_fits_github(self):
        text = about_replacement(self.facts["main"]["n"])
        self.assertLessEqual(len(text), 350)
        self.assertIn("no significance claim", text)
        self.assertNotIn("spec-only", text)
        for phrase in FORBIDDEN:
            self.assertNotIn(phrase, text)

    def test_repository_evidence_check(self):
        errors = collect_errors()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
