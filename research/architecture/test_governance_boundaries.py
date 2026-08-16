import unittest

from governance_boundaries import (assess_freshness_vector,
                                   suppress_small_groups, valid_time_bind)


class GovernanceBoundaryExperimentTest(unittest.TestCase):
    def test_valid_time_binding_preserves_historical_segment(self):
        facts = [
            {"customer_id": "c1", "date": "2026-06-15", "sales": 100},
            {"customer_id": "c1", "date": "2026-07-15", "sales": 200},
        ]
        versions = [
            {"customer_id": "c1", "valid_from": "2026-01-01",
             "valid_to": "2026-07-01", "tier": "silver"},
            {"customer_id": "c1", "valid_from": "2026-07-01",
             "valid_to": None, "tier": "gold"},
        ]
        current_row_join = [{**fact, "tier": "gold"} for fact in facts]
        self.assertEqual([row["tier"] for row in current_row_join], ["gold", "gold"])
        bound = valid_time_bind(facts, versions, "customer_id", "date")
        self.assertEqual([row["tier"] for row in bound], ["silver", "gold"])

    def test_privacy_suppression_preserves_residual_not_false_visible_total(self):
        rows = [
            {"region": "A", "customers": 10, "delta": 8},
            {"region": "B", "customers": 3, "delta": -2},
            {"region": "C", "customers": 2, "delta": 4},
        ]
        result = suppress_small_groups(rows, "customers", "delta", minimum_count=5)
        self.assertEqual(result["visible"], [rows[0]])
        self.assertEqual(result["suppressed"], {"groups": 2, "entity_count": 5, "value": 2})
        self.assertEqual(result["total"]["value"], 10)
        self.assertNotEqual(sum(row["delta"] for row in result["visible"]), 10)

    def test_multi_source_freshness_cannot_collapse_stale_source_to_fresh(self):
        result = assess_freshness_vector(
            {"sales": "sha:a", "fx": "sha:b"},
            {"sales": "sha:a", "fx": "sha:c"})
        self.assertEqual(result["freshness"], "stale")
        self.assertEqual(
            {row["source"]: row["status"] for row in result["sources"]},
            {"fx": "stale", "sales": "fresh"})

    def test_missing_current_source_suspends_freshness_claim(self):
        result = assess_freshness_vector(
            {"sales": "sha:a", "fx": "sha:b"}, {"sales": "sha:a"})
        self.assertEqual(result["status"], "suspended")
        self.assertEqual(result["freshness"], "suspended")


if __name__ == "__main__":
    unittest.main()
