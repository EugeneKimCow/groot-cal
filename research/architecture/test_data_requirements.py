import sqlite3
import unittest

from data_requirements import (AggregateExpr, DataRequirement, Relationship,
                               RequirementError, lower_sqlite,
                               validate_requirement)


class DataRequirementExperimentTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
            CREATE TABLE order_lines (
                line_id INTEGER PRIMARY KEY,
                sales REAL NOT NULL,
                claims REAL NOT NULL,
                premium REAL NOT NULL
            );
            CREATE TABLE line_tags (line_id INTEGER NOT NULL, tag TEXT NOT NULL);
            INSERT INTO order_lines VALUES
                (1, 100.0, 20.0, 100.0),
                (2, 60.0, 30.0, 60.0);
            INSERT INTO line_tags VALUES
                (1, 'new'), (1, 'promo'), (2, 'promo');
        """)

    def tearDown(self):
        self.db.close()

    def relationship(self, allocation_rule=None):
        return Relationship(
            bridge="line_tags", source_key="line_id", bridge_key="line_id",
            dimension_field="tag", cardinality="many_to_many",
            allocation_rule=allocation_rule)

    def test_naive_join_demonstrates_fanout(self):
        base = self.db.execute("SELECT SUM(sales) FROM order_lines").fetchone()[0]
        naive = self.db.execute(
            "SELECT SUM(sales) FROM order_lines JOIN line_tags USING(line_id)").fetchone()[0]
        self.assertEqual(base, 160.0)
        self.assertEqual(naive, 260.0)

    def test_many_to_many_without_policy_is_rejected_before_sql(self):
        requirement = DataRequirement(
            source="order_lines", source_grain=("line_id",),
            aggregate=AggregateExpr("sum", value_field="sales"),
            group_by=("tag",), relationship=self.relationship())
        with self.assertRaisesRegex(RequirementError, "allocation rule"):
            validate_requirement(requirement)

    def test_equal_split_additive_lowering_reconciles_to_source(self):
        requirement = DataRequirement(
            source="order_lines", source_grain=("line_id",),
            aggregate=AggregateExpr("sum", value_field="sales"),
            group_by=("tag",), relationship=self.relationship("equal_split"))
        lowered = lower_sqlite(requirement)
        rows = self.db.execute(lowered["sql"], lowered["params"]).fetchall()
        self.assertEqual(dict(rows), {"new": 50.0, "promo": 110.0})
        self.assertEqual(sum(value for _, value in rows), 160.0)
        self.assertNotIn("sqlite", repr(lowered["logical_requirement"]).lower())

    def test_ratio_of_sums_survives_allocation_and_pushdown(self):
        requirement = DataRequirement(
            source="order_lines", source_grain=("line_id",),
            aggregate=AggregateExpr(
                "ratio_of_sums", numerator_field="claims",
                denominator_field="premium"),
            group_by=("tag",), relationship=self.relationship("equal_split"))
        lowered = lower_sqlite(requirement)
        rows = self.db.execute(lowered["sql"], lowered["params"]).fetchall()
        components = {tag: (numerator, denominator, value)
                      for tag, numerator, denominator, value in rows}
        self.assertEqual(components["new"][:2], (10.0, 50.0))
        self.assertEqual(components["promo"][:2], (40.0, 110.0))
        total_numerator = sum(row[1] for row in rows)
        total_denominator = sum(row[2] for row in rows)
        self.assertEqual(total_numerator, 50.0)
        self.assertEqual(total_denominator, 160.0)
        self.assertAlmostEqual(total_numerator / total_denominator, 0.3125)
        self.assertIn("SUM(s.claims", lowered["sql"])
        self.assertIn("SUM(s.premium", lowered["sql"])


if __name__ == "__main__":
    unittest.main()
