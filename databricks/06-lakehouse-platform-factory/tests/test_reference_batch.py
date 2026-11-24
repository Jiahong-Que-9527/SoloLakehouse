from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from reference_batch import KEY, run

STACK = "slh-alpha-dev"
SCHEMAS = {layer: f"slh_alpha_dev_{layer}" for layer in ("bronze", "silver", "gold")}


class ReferenceBatchTests(TestCase):
    def test_foreign_schema_is_rejected_before_sql(self):
        spark = Mock()
        wrong = {**SCHEMAS, "gold": "slh_bravo_dev_gold"}
        with self.assertRaisesRegex(ValueError, "do not all belong"):
            run(spark, "land", STACK, "workspace", wrong, "reference")
        spark.sql.assert_not_called()

    def test_invalid_silver_cannot_update_gold(self):
        row = SimpleNamespace(fixture_id=KEY, fixture_value="", stack_id=STACK)
        spark = Mock()
        spark.sql.return_value.collect.return_value = [row]
        with self.assertRaisesRegex(ValueError, "must be non-empty"):
            run(spark, "publish", STACK, "workspace", SCHEMAS, "")
        spark.sql.assert_called_once_with("SELECT * FROM workspace.slh_alpha_dev_silver.fixture")

    def test_quality_rejects_duplicate_keys(self):
        row = SimpleNamespace(fixture_id=KEY, fixture_value="reference", stack_id=STACK)
        spark = Mock()
        spark.sql.return_value.collect.return_value = [row, row]
        with self.assertRaisesRegex(ValueError, "exactly one reference key"):
            run(spark, "quality", STACK, "workspace", SCHEMAS, "reference")

    def test_ingest_treats_fixture_value_as_a_bound_parameter(self):
        spark = Mock()
        value = "owner's fixture"
        run(spark, "land", STACK, "workspace", SCHEMAS, value)
        merge = spark.sql.call_args
        self.assertIn("MERGE INTO workspace.slh_alpha_dev_bronze.fixture", merge.args[0])
        self.assertNotIn(value, merge.args[0])
        self.assertEqual(merge.kwargs["args"]["value"], value)
