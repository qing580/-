import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build_vessel_query_manifest.py"
SPEC = importlib.util.spec_from_file_location("build_vessel_query_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ManifestTests(unittest.TestCase):
    def write_rows(self, directory, rows):
        path = Path(directory) / "input.csv"
        fields = [
            "mmsi",
            "imo",
            "vessel_name",
            "call_sign",
            "vessel_type",
            "message_type",
            "received_at",
            "lat",
            "lon",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_normalizers_and_imo_checksum(self):
        self.assertEqual(MODULE.normalize_mmsi("123456789.0"), "123456789")
        self.assertEqual(MODULE.normalize_mmsi("123"), "")
        self.assertEqual(MODULE.normalize_imo("IMO 9074729"), "9074729")
        self.assertEqual(MODULE.normalize_imo("9074728"), "")
        self.assertTrue(MODULE.is_missing_imo_sentinel("IMO 0"))

    def test_manifest_preserves_conflicts_and_region_anomalies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_rows(
                directory,
                [
                    {
                        "mmsi": "123456789",
                        "imo": "9074729",
                        "vessel_name": "Example One",
                        "call_sign": "CALL1",
                        "vessel_type": "70",
                        "message_type": "PositionReport",
                        "received_at": "2026-09-15T01:00:00+00:00",
                        "lat": "1.25",
                        "lon": "103.8",
                    },
                    {
                        "mmsi": "123456789",
                        "imo": "1234567",
                        "vessel_name": "Example Two",
                        "call_sign": "CALL2",
                        "vessel_type": "80",
                        "message_type": "PositionReport",
                        "received_at": "2026-09-15T02:00:00+00:00",
                        "lat": "8.0",
                        "lon": "103.8",
                    },
                ],
            )
            manifest, metadata = MODULE.build_manifest([path], MODULE.DEFAULT_BBOX)
            summary = MODULE.summarize(manifest, metadata)
            self.assertEqual(len(manifest), 1)
            row = manifest[0]
            self.assertEqual(row["imo_status"], "conflict")
            self.assertEqual(row["query_priority"], "mmsi")
            self.assertEqual(row["region_status"], "mixed_or_outside")
            self.assertEqual(row["out_of_region_position_rows"], 1)
            self.assertEqual(row["ais_rough_categories"], "cargo_unspecified|tanker")
            self.assertEqual(row["identity_conflict"], "imo|vessel_name|call_sign")
            self.assertEqual(summary["region_anomaly_vessels"], 1)

    def test_invalid_imo_falls_back_to_mmsi(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_rows(
                directory,
                [
                    {
                        "mmsi": "987654321",
                        "imo": "9074728",
                        "vessel_name": "No Valid IMO",
                        "call_sign": "",
                        "vessel_type": "60",
                        "message_type": "ShipStaticData",
                        "received_at": "2026-09-15T03:00:00Z",
                        "lat": "",
                        "lon": "",
                    }
                ],
            )
            manifest, _ = MODULE.build_manifest([path], MODULE.DEFAULT_BBOX)
            row = manifest[0]
            self.assertEqual(row["imo_status"], "invalid_only")
            self.assertEqual(row["preferred_imo"], "")
            self.assertEqual(row["invalid_imo_candidates"], "9074728")
            self.assertEqual(row["query_priority"], "mmsi")
            self.assertEqual(row["query_value"], "987654321")
            self.assertEqual(row["region_status"], "no_valid_position")

    def test_invalid_mmsi_is_reported_not_silently_padded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_rows(
                directory,
                [
                    {
                        "mmsi": "5631101",
                        "imo": "",
                        "vessel_name": "PSAB",
                        "call_sign": "",
                        "vessel_type": "99",
                        "message_type": "PositionReport",
                        "received_at": "2026-09-15T03:00:00Z",
                        "lat": "1.2",
                        "lon": "103.8",
                    },
                    {
                        "mmsi": "",
                        "imo": "",
                        "vessel_name": "",
                        "call_sign": "",
                        "vessel_type": "",
                        "message_type": "SubscriptionConfirmation",
                        "received_at": "2026-09-15T03:00:01Z",
                        "lat": "",
                        "lon": "",
                    },
                ],
            )
            manifest, metadata = MODULE.build_manifest([path], MODULE.DEFAULT_BBOX)
            self.assertEqual(manifest, [])
            self.assertEqual(metadata["blank_mmsi_rows"], 1)
            self.assertEqual(metadata["invalid_mmsi_rows"], 1)
            self.assertEqual(metadata["invalid_mmsi_values"], {"5631101": 1})


if __name__ == "__main__":
    unittest.main()
