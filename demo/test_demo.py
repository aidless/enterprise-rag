"""Contract tests for the enterprise-rag evidence replay.

The demo does not rerun the private-corpus experiment. These tests pin the
committed result values, the negative results, the frozen-baseline query, and
the no-hand-written-metrics / no-secrets guards on the public artifact.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "demo") not in sys.path:
    sys.path.insert(0, str(ROOT / "demo"))

import server  # noqa: E402
from payload import build_payload, query_baseline, write_payload  # noqa: E402

PUBLIC = ROOT / "demo" / "public"
PUBLIC_FILES = [
    PUBLIC / "index.html",
    PUBLIC / "app.js",
    PUBLIC / "style.css",
    PUBLIC / "config.json",
]
UI_DATA_FILES = [PUBLIC / "index.html", PUBLIC / "app.js"]
FIXED_TIME = "2026-10-22T00:00:00+00:00"


def normalize(payload: dict) -> dict:
    data = json.loads(json.dumps(payload))
    for key in ("generated_at", "commit", "worktree_dirty", "dirty_paths",
                "python"):
        data["meta"].pop(key, None)
    return data


def banned_metric_values(payload: dict) -> set[str]:
    values = {
        payload["summary"]["hybrid"]["recall"],
        payload["summary"]["dense"]["recall"],
        str(payload["summary"]["hybrid"]["chunks"]),
    }
    for ablation in payload["ablations"]:
        if ablation["id"] in ("sweep", "overlap"):
            values.add(f"{ablation['best']['mrr']:.4f}")
    return values


def find_banned_metrics(text: str, banned: set[str]) -> list[str]:
    return sorted(value for value in banned if value in text)


def find_secret_patterns(text: str) -> list[str]:
    patterns = {
        "/home/": r"/home/",
        "/Users/": r"/Users/",
        "C-drive": r"C:\\\\",
        "sk-": r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{8,}",
        "ghp_": r"(?<![A-Za-z0-9])ghp_[A-Za-z0-9]",
        "AKIA": r"AKIA[0-9A-Z]{16}",
        "private-key": r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY",
    }
    return sorted(name for name, pattern in patterns.items()
                  if re.search(pattern, text))


class DemoPayloadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_payload(generated_at=FIXED_TIME)

    def test_verification_and_metrics(self) -> None:
        payload = self.payload
        self.assertEqual(payload["verification"]["status"], "MATCH")
        self.assertEqual(payload["verification"]["mismatches"], [])
        summary = payload["summary"]
        self.assertEqual(summary["hybrid"]["recall"], "8/10")
        self.assertEqual(summary["dense"]["recall"], "5/10")
        self.assertLess(summary["dense"]["recall_val"],
                        summary["hybrid"]["recall_val"])
        self.assertEqual(summary["rerank"]["delta_recall"], 0)
        self.assertEqual(summary["metamorphic"]["invariant_after"], 0)
        self.assertLess(summary["metamorphic"]["desirable_after"],
                        summary["metamorphic"]["desirable_before"])

    def test_negative_results_are_explicit(self) -> None:
        payload = self.payload
        ablations = {item["id"]: item for item in payload["ablations"]}
        self.assertEqual(ablations["rerank"]["delta_recall"], 0)
        self.assertGreater(ablations["sweep"]["best"]["mrr"],
                           ablations["sweep"]["chosen"]["mrr"])
        self.assertNotEqual(ablations["sweep"]["best"]["w_cos"],
                            ablations["sweep"]["chosen"]["w_cos"])
        self.assertGreater(ablations["overlap"]["best"]["mrr"],
                           ablations["overlap"]["chosen"]["mrr"])
        self.assertNotEqual(ablations["overlap"]["best"]["overlap"],
                            ablations["overlap"]["chosen"]["overlap"])
        dense = next(layer for layer in payload["layers"]
                     if layer["id"] == "dense")
        self.assertEqual(dense["tone"], "bad")
        self.assertIn("负结果", dense["verdict"])

    def test_committed_artifact_matches_current_values(self) -> None:
        artifact = PUBLIC / "results.json"
        self.assertTrue(artifact.exists(), "run demo/build_static.py first")
        committed = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertEqual(normalize(committed), normalize(self.payload))

    def test_reproducible_with_fixed_timestamp(self) -> None:
        second = build_payload(generated_at=FIXED_TIME)
        self.assertEqual(normalize(self.payload), normalize(second))

    def test_write_payload_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.json"
            write_payload(path, self.payload)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["verification"]["status"], "MATCH")

    def test_baseline_query(self) -> None:
        results = query_baseline("RAG 由哪几部分组成")
        self.assertTrue(results)
        self.assertEqual(results[0]["doc_id"], "rag_overview")
        self.assertGreater(results[0]["score"], 0)
        self.assertEqual(query_baseline(" "), [])


class DemoGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_payload(generated_at=FIXED_TIME)
        cls.banned = banned_metric_values(cls.payload)

    def test_ui_has_no_handwritten_metrics(self) -> None:
        for path in UI_DATA_FILES:
            text = path.read_text(encoding="utf-8")
            hits = find_banned_metrics(text, self.banned)
            self.assertEqual(hits, [], f"hardcoded metrics in {path.name}: {hits}")

    def test_metric_scanner_can_go_red(self) -> None:
        self.assertEqual(find_banned_metrics("recall 8/10", {"8/10"}), ["8/10"])
        self.assertEqual(find_banned_metrics("nothing", {"8/10"}), [])

    def test_no_secrets_or_absolute_paths(self) -> None:
        for path in PUBLIC_FILES + [PUBLIC / "results.json"] + [
            ROOT / "demo" / "payload.py",
            ROOT / "demo" / "build_static.py",
            ROOT / "demo" / "server.py",
        ]:
            text = path.read_text(encoding="utf-8")
            hits = find_secret_patterns(text)
            self.assertEqual(hits, [], f"secret/absolute path in {path.name}: {hits}")

    def test_secret_scanner_can_go_red(self) -> None:
        self.assertEqual(find_secret_patterns("/home/alice/x"), ["/home/"])
        self.assertEqual(
            find_secret_patterns("sk-" + "abcdefgh"), ["sk-"]
        )
        self.assertEqual(find_secret_patterns("safe text"), [])

    def test_static_index_contract(self) -> None:
        html = (PUBLIC / "index.html").read_text(encoding="utf-8")
        for element_id in (
            "mode-badge", "mode-note", "rerun", "summary", "layers",
            "ablations", "query-form", "query-input", "query-results",
            "findings", "refutes", "meta", "error",
        ):
            self.assertIn(f'id="{element_id}"', html, element_id)


class DemoServerTest(unittest.TestCase):
    def test_api_health_results_query_and_rerun(self) -> None:
        httpd, port = server.make_server(port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{port}"
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=5) as response:
                health = json.load(response)
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["mode"], "live")

            with urllib.request.urlopen(f"{base}/results.json", timeout=30) as response:
                payload = json.load(response)
            self.assertEqual(payload["verification"]["status"], "MATCH")

            query_request = urllib.request.Request(
                f"{base}/api/query",
                data=json.dumps({"query": "RAG 由哪几部分组成"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(query_request, timeout=30) as response:
                query_payload = json.load(response)
            self.assertEqual(query_payload["results"][0]["doc_id"], "rag_overview")

            rerun_request = urllib.request.Request(
                f"{base}/api/run",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(rerun_request, timeout=30) as response:
                rerun = json.load(response)
            self.assertEqual(rerun["verification"]["status"], "MATCH")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
