import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "audit_gfw_pilot.py"
SPEC = importlib.util.spec_from_file_location("audit_gfw_pilot", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def sample(mmsi="123456789", category="cargo_unspecified"):
    return {
        "mmsi": mmsi,
        "vessel_name": "TEST SHIP",
        "ais_rough_categories": category,
        "query_priority": "imo",
        "query_value": "9074729",
    }


def status(value="success"):
    return {"status": value, "error": "network down" if value != "success" else ""}


def payload(shiptype, source="COMBINATION_OF_REGISTRY_AND_AIS_INFERRED_NN_INFO", registry=None):
    return {
        "entries": [
            {
                "selfReportedInfo": [{"ssvid": "123456789", "shipname": "TEST SHIP"}],
                "registryInfo": registry or [],
                "combinedSourcesInfo": [
                    {"shiptypes": [{"name": shiptype, "source": source}], "geartypes": []}
                ],
            }
        ]
    }


class EvidenceAuditTests(unittest.TestCase):
    def test_broad_cargo_is_not_split_into_container_or_bulk(self):
        row = MODULE.audit_payload(sample(), status(), payload("CARGO"))
        self.assertEqual(row["candidate_target_class"], "cargo_unspecified")
        self.assertEqual(row["five_class_label_status"], "insufficient_for_five_class")

    def test_combined_passenger_is_candidate_not_gold(self):
        row = MODULE.audit_payload(sample(category="passenger"), status(), payload("PASSENGER"))
        self.assertEqual(row["candidate_target_class"], "passenger")
        self.assertEqual(row["evidence_level"], "combined_inference_candidate")
        self.assertEqual(row["five_class_label_status"], "not_gold_label")

    def test_registry_fishing_is_kept_source_aware(self):
        registry = [{"ssvid": "123456789", "shipname": "TEST SHIP", "sourceCode": ["CCAMLR"], "geartypes": ["TRAWLERS"]}]
        row = MODULE.audit_payload(sample(category="fishing"), status(), payload("FISHING", registry=registry))
        self.assertEqual(row["evidence_level"], "registry_supported")
        self.assertEqual(row["registry_sources"], "CCAMLR")

    def test_mismatched_mmsi_requires_review(self):
        data = payload("PASSENGER")
        data["entries"][0]["selfReportedInfo"][0]["ssvid"] = "987654321"
        row = MODULE.audit_payload(sample(), status(), data)
        self.assertEqual(row["identity_alignment"], "not_aligned")
        self.assertEqual(row["five_class_label_status"], "manual_review")

    def test_network_failure_requires_retry(self):
        row = MODULE.audit_payload(sample(), status("network_error"), None)
        self.assertEqual(row["evidence_level"], "request_failed")
        self.assertEqual(row["five_class_label_status"], "retry_required")


if __name__ == "__main__":
    unittest.main()
