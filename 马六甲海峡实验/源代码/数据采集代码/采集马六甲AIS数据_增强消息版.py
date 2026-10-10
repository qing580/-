from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import signal
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TextIO


COLLECTOR_VERSION = "malacca_ais_reusable_v2_2026-09-09"
DEFAULT_BBOX = [[1.0, 103.0], [3.5, 104.5]]
DEFAULT_REGION_ID = "malacca_southeast_singapore_strait"
DEFAULT_MESSAGE_TYPES = [
    "PositionReport",
    "ShipStaticData",
    "StandardClassBPositionReport",
    "ExtendedClassBPositionReport",
    "StaticDataReport",
]
DEFAULT_FIELDS = [
    "collector_version", "batch_id", "region_id", "sequence_no", "source", "bbox",
    "message_type", "received_at_utc", "received_at", "metadata_time_utc", "ais_timestamp",
    "mmsi", "valid", "repeat_indicator", "message_id", "lat", "lon", "sog", "cog",
    "true_heading", "rate_of_turn", "navigational_status", "position_accuracy", "raim",
    "special_manoeuvre_indicator", "communication_state", "communication_state_is_itdma",
    "assigned_mode", "class_b_unit", "class_b_display", "class_b_dsc", "class_b_band",
    "class_b_msg22", "dte", "vessel_name", "call_sign", "imo", "vessel_type",
    "ais_version", "fix_type", "destination", "eta_month", "eta_day", "eta_hour",
    "eta_minute", "draught", "dimension_to_bow", "dimension_to_stern", "dimension_to_port",
    "dimension_to_starboard", "ship_length", "ship_width", "static_part_number",
    "vendor_id_name", "vendor_id_model", "vendor_id_serial", "parse_status", "parse_error",
    "raw_json",
]
CONNECTION_FIELDS = ["time_utc", "batch_id", "event", "detail", "count"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(moment: datetime | None = None) -> str:
    return (moment or utc_now()).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def get_nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
        if current is None:
            return ""
    return current


def clean_text(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return "" if stripped and set(stripped) <= {"@"} else stripped.replace("@", " ").strip()
    return value if value is not None else ""


def dimensions_from(payload: dict[str, Any]) -> tuple[Any, Any, Any, Any, Any, Any]:
    dim = payload.get("Dimension")
    if not isinstance(dim, dict):
        return "", "", "", "", "", ""
    bow = dim.get("A", "")
    stern = dim.get("B", "")
    port = dim.get("C", "")
    starboard = dim.get("D", "")
    length = bow + stern if isinstance(bow, (int, float)) and isinstance(stern, (int, float)) else ""
    width = port + starboard if isinstance(port, (int, float)) and isinstance(starboard, (int, float)) else ""
    return bow, stern, port, starboard, length, width


def base_row(
    message: dict[str, Any], raw_json: str, bbox: list[list[float]], keep_raw: bool,
    batch_id: str, region_id: str, sequence_no: int, received_at_utc: str,
) -> dict[str, Any]:
    metadata = message.get("MetaData") if isinstance(message.get("MetaData"), dict) else {}
    return {field: "" for field in DEFAULT_FIELDS} | {
        "collector_version": COLLECTOR_VERSION,
        "batch_id": batch_id,
        "region_id": region_id,
        "sequence_no": sequence_no,
        "source": "AISStream",
        "bbox": json.dumps(bbox, ensure_ascii=False, separators=(",", ":")),
        "message_type": message.get("MessageType", ""),
        "received_at_utc": received_at_utc,
        "received_at": received_at_utc,
        "metadata_time_utc": metadata.get("time_utc", ""),
        "mmsi": metadata.get("MMSI", ""),
        "lat": first_value(metadata.get("Latitude"), metadata.get("latitude")),
        "lon": first_value(metadata.get("Longitude"), metadata.get("longitude")),
        "vessel_name": clean_text(metadata.get("ShipName", "")),
        "parse_status": "parsed",
        "raw_json": raw_json if keep_raw else "",
    }


def update_common(row: dict[str, Any], payload: dict[str, Any]) -> None:
    row["mmsi"] = first_value(payload.get("UserID"), row["mmsi"])
    row["ais_timestamp"] = payload.get("Timestamp", "")
    row["valid"] = payload.get("Valid", "")
    row["repeat_indicator"] = payload.get("RepeatIndicator", "")
    row["message_id"] = payload.get("MessageID", "")
    row["lat"] = first_value(payload.get("Latitude"), row["lat"])
    row["lon"] = first_value(payload.get("Longitude"), row["lon"])
    row["sog"] = payload.get("Sog", "")
    row["cog"] = payload.get("Cog", "")
    row["true_heading"] = payload.get("TrueHeading", "")
    row["rate_of_turn"] = payload.get("RateOfTurn", "")
    row["navigational_status"] = payload.get("NavigationalStatus", "")
    row["position_accuracy"] = payload.get("PositionAccuracy", "")
    row["raim"] = payload.get("Raim", "")
    row["special_manoeuvre_indicator"] = payload.get("SpecialManoeuvreIndicator", "")
    row["communication_state"] = payload.get("CommunicationState", "")
    row["communication_state_is_itdma"] = payload.get("CommunicationStateIsItdma", "")
    row["assigned_mode"] = payload.get("AssignedMode", "")
    row["class_b_unit"] = payload.get("ClassBUnit", "")
    row["class_b_display"] = payload.get("ClassBDisplay", "")
    row["class_b_dsc"] = payload.get("ClassBDsc", "")
    row["class_b_band"] = payload.get("ClassBBand", "")
    row["class_b_msg22"] = payload.get("ClassBMsg22", "")
    row["dte"] = payload.get("Dte", "")


def update_static(row: dict[str, Any], payload: dict[str, Any]) -> None:
    row["vessel_name"] = first_value(clean_text(payload.get("Name", "")), row["vessel_name"])
    row["call_sign"] = clean_text(payload.get("CallSign", ""))
    row["imo"] = payload.get("ImoNumber", "")
    row["vessel_type"] = first_value(payload.get("Type"), payload.get("ShipType"))
    row["ais_version"] = payload.get("AisVersion", "")
    row["fix_type"] = payload.get("FixType", "")
    row["destination"] = clean_text(payload.get("Destination", ""))
    row["draught"] = payload.get("MaximumStaticDraught", "")
    eta = payload.get("Eta")
    if isinstance(eta, dict):
        row["eta_month"] = eta.get("Month", "")
        row["eta_day"] = eta.get("Day", "")
        row["eta_hour"] = eta.get("Hour", "")
        row["eta_minute"] = eta.get("Minute", "")
    bow, stern, port, starboard, length, width = dimensions_from(payload)
    row["dimension_to_bow"] = bow
    row["dimension_to_stern"] = stern
    row["dimension_to_port"] = port
    row["dimension_to_starboard"] = starboard
    row["ship_length"] = length
    row["ship_width"] = width


def update_static_data_report(row: dict[str, Any], payload: dict[str, Any]) -> None:
    report_a = payload.get("ReportA") if isinstance(payload.get("ReportA"), dict) else {}
    report_b = payload.get("ReportB") if isinstance(payload.get("ReportB"), dict) else {}
    row["static_part_number"] = payload.get("PartNumber", "")
    row["vessel_name"] = first_value(clean_text(report_a.get("Name", "")), row["vessel_name"])
    row["call_sign"] = clean_text(report_b.get("CallSign", ""))
    row["vessel_type"] = report_b.get("ShipType", "")
    row["fix_type"] = report_b.get("FixType", "")
    row["vendor_id_name"] = clean_text(report_b.get("VendorIDName", ""))
    row["vendor_id_model"] = first_value(report_b.get("VendorIDModel"), report_b.get("VenderIDModel"))
    row["vendor_id_serial"] = first_value(report_b.get("VendorIDSerial"), report_b.get("VenderIDSerial"))
    bow, stern, port, starboard, length, width = dimensions_from(report_b)
    row["dimension_to_bow"] = bow
    row["dimension_to_stern"] = stern
    row["dimension_to_port"] = port
    row["dimension_to_starboard"] = starboard
    row["ship_length"] = length
    row["ship_width"] = width


def extract_row(
    message: dict[str, Any], raw_json: str, bbox: list[list[float]], keep_raw: bool,
    batch_id: str, region_id: str, sequence_no: int, received_at_utc: str,
) -> dict[str, Any]:
    row = base_row(message, raw_json, bbox, keep_raw, batch_id, region_id, sequence_no, received_at_utc)
    message_type = message.get("MessageType")
    if message_type == "SubscriptionConfirmation":
        row["parse_status"] = "control"
        return row
    payload = get_nested(message, "Message", str(message_type))
    if not isinstance(payload, dict):
        row["parse_status"] = "unsupported"
        row["parse_error"] = f"missing payload for message type {message_type}"
        return row
    update_common(row, payload)
    if message_type == "ShipStaticData":
        update_static(row, payload)
    elif message_type == "StaticDataReport":
        update_static_data_report(row, payload)
    elif message_type == "ExtendedClassBPositionReport":
        update_static(row, payload)
    return row


def parse_message_types(text: str) -> list[str]:
    values = [part.strip() for part in text.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("message-types cannot be empty")
    return values


def short_value(value: Any, max_len: int = 28) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return "-"
    return text if len(text) <= max_len else text[: max_len - 1] + "~"


def print_row_progress(total: int, row: dict[str, Any]) -> None:
    static_bits = []
    if row.get("vessel_type") not in ("", None):
        static_bits.append(f"type={row['vessel_type']}")
    if row.get("ship_length") not in ("", None) or row.get("ship_width") not in ("", None):
        static_bits.append(f"size={short_value(row.get('ship_length'))}x{short_value(row.get('ship_width'))}")
    if row.get("draught") not in ("", None):
        static_bits.append(f"draft={short_value(row.get('draught'))}")
    if row.get("imo") not in ("", None, 0, "0"):
        static_bits.append(f"imo={row['imo']}")
    static_text = " ".join(static_bits) if static_bits else "static=-"
    print(
        f"[{iso_utc()}] row={total} msg={short_value(row.get('message_type'), 34)} "
        f"mmsi={short_value(row.get('mmsi'))} name={short_value(row.get('vessel_name'))} "
        f"lat={short_value(row.get('lat'))} lon={short_value(row.get('lon'))} "
        f"sog={short_value(row.get('sog'))} cog={short_value(row.get('cog'))} "
        f"heading={short_value(row.get('true_heading'))} rot={short_value(row.get('rate_of_turn'))} "
        f"nav={short_value(row.get('navigational_status'))} {static_text} "
        f"status={row.get('parse_status', '-')}",
        flush=True,
    )


def write_runtime(path: Path, data: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def log_connection(writer: csv.DictWriter, handle: TextIO, batch_id: str, event: str, detail: str = "", count: int = 0) -> None:
    writer.writerow({"time_utc": iso_utc(), "batch_id": batch_id, "event": event, "detail": detail, "count": count})
    handle.flush()


async def collect(args: argparse.Namespace) -> dict[str, Any]:
    try:
        import websockets
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing websockets. Use the provided PowerShell launcher.") from exc
    api_key = args.api_key or os.getenv("AISSTREAM_API_KEY")
    if not api_key:
        raise SystemExit("Missing AISSTREAM_API_KEY. Use hidden input in the PowerShell launcher.")

    output = Path(args.output)
    raw_output = Path(args.raw_output)
    connection_output = Path(args.connection_output)
    runtime_output = Path(args.runtime_output)
    for path in (output, raw_output, connection_output, runtime_output):
        ensure_parent(path)
    existing = [path for path in (output, raw_output, connection_output, runtime_output) if path.exists()]
    if existing:
        raise SystemExit("Refusing to overwrite existing batch files: " + ", ".join(str(path) for path in existing))

    started_at = utc_now()
    stop_at = started_at + timedelta(hours=args.hours)
    total = parsed = control = unsupported = reconnect_count = 0
    message_counts: dict[str, int] = {}
    should_stop = asyncio.Event()

    def stop_handler(*_: object) -> None:
        should_stop.set()

    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, stop_handler)
        loop.add_signal_handler(signal.SIGTERM, stop_handler)

    initial_runtime = {
        "collector_version": COLLECTOR_VERSION, "batch_id": args.batch_id,
        "region_id": args.region_id, "bbox": args.bbox, "message_types": args.message_types,
        "target_hours": args.hours, "started_at_utc": started_at.isoformat(),
        "planned_stop_at_utc": stop_at.isoformat(), "status": "running",
    }
    write_runtime(runtime_output, initial_runtime)

    with (
        output.open("x", newline="", encoding="utf-8-sig") as event_handle,
        raw_output.open("x", newline="", encoding="utf-8") as raw_handle,
        connection_output.open("x", newline="", encoding="utf-8-sig") as connection_handle,
    ):
        event_writer = csv.DictWriter(event_handle, fieldnames=DEFAULT_FIELDS)
        event_writer.writeheader()
        event_handle.flush()
        connection_writer = csv.DictWriter(connection_handle, fieldnames=CONNECTION_FIELDS)
        connection_writer.writeheader()
        connection_handle.flush()
        log_connection(connection_writer, connection_handle, args.batch_id, "collector_started", f"stop_at={stop_at.isoformat()}")

        while utc_now() < stop_at and not should_stop.is_set():
            try:
                async with websockets.connect(args.endpoint, ping_interval=20, ping_timeout=20, compression="deflate") as websocket:
                    log_connection(connection_writer, connection_handle, args.batch_id, "connected", count=reconnect_count)
                    subscribe_message = {"APIKey": api_key, "BoundingBoxes": [args.bbox], "FilterMessageTypes": args.message_types}
                    await websocket.send(json.dumps(subscribe_message))
                    log_connection(connection_writer, connection_handle, args.batch_id, "subscription_sent", count=reconnect_count)
                    print(
                        f"[{iso_utc()}] started enhanced AIS collection: batch={args.batch_id}, "
                        f"region={args.region_id}, bbox={args.bbox}, message_types={args.message_types}, output={output}",
                        flush=True,
                    )

                    while utc_now() < stop_at and not should_stop.is_set():
                        remaining = max(0.1, min(args.idle_timeout, (stop_at - utc_now()).total_seconds()))
                        try:
                            raw_message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                        except asyncio.TimeoutError:
                            print(
                                f"[{iso_utc()}] waiting for AIS messages... saved={total}, "
                                f"parsed={parsed}, control={control}, nonparsed={unsupported}", flush=True,
                            )
                            continue
                        received_at_utc = iso_utc()
                        raw_text = raw_message.decode("utf-8", errors="replace") if isinstance(raw_message, bytes) else raw_message
                        total += 1
                        raw_handle.write(json.dumps({
                            "collector_version": COLLECTOR_VERSION, "batch_id": args.batch_id,
                            "region_id": args.region_id, "sequence_no": total,
                            "received_at_utc": received_at_utc, "raw_message": raw_text,
                        }, ensure_ascii=False, separators=(",", ":")) + "\n")
                        try:
                            message = json.loads(raw_text)
                        except json.JSONDecodeError as exc:
                            row = {field: "" for field in DEFAULT_FIELDS}
                            row.update({
                                "collector_version": COLLECTOR_VERSION, "batch_id": args.batch_id,
                                "region_id": args.region_id, "sequence_no": total, "source": "AISStream",
                                "bbox": json.dumps(args.bbox, separators=(",", ":")),
                                "message_type": "JSONDecodeError", "received_at_utc": received_at_utc,
                                "received_at": received_at_utc, "parse_status": "error",
                                "parse_error": str(exc), "raw_json": raw_text if args.raw_json else "",
                            })
                        else:
                            row = extract_row(
                                message, raw_text, args.bbox, args.raw_json, args.batch_id,
                                args.region_id, total, received_at_utc,
                            )
                        event_writer.writerow(row)
                        message_type = str(row.get("message_type", ""))
                        message_counts[message_type] = message_counts.get(message_type, 0) + 1
                        if row["parse_status"] == "parsed":
                            parsed += 1
                        elif row["parse_status"] == "control":
                            control += 1
                        else:
                            unsupported += 1
                        if args.print_every > 0 and total % args.print_every == 0:
                            print_row_progress(total, row)
                        if total % args.flush_every == 0:
                            event_handle.flush()
                            raw_handle.flush()
                            print(
                                f"[{iso_utc()}] saved {total} rows "
                                f"(parsed={parsed}, control={control}, nonparsed={unsupported})", flush=True,
                            )
            except KeyboardInterrupt:
                should_stop.set()
            except Exception as exc:
                reconnect_count += 1
                detail = f"{type(exc).__name__}: {exc}"
                log_connection(connection_writer, connection_handle, args.batch_id, "connection_error", detail, reconnect_count)
                print(f"[{iso_utc()}] connection error: {exc}; reconnect #{reconnect_count}", flush=True)
                await asyncio.sleep(min(60, 5 * reconnect_count))

        event_handle.flush()
        raw_handle.flush()
        final_event = "collector_interrupted" if should_stop.is_set() else "collector_finished"
        log_connection(connection_writer, connection_handle, args.batch_id, final_event, count=total)

    ended_at = utc_now()
    result = initial_runtime | {
        "ended_at_utc": ended_at.isoformat(), "elapsed_seconds": (ended_at - started_at).total_seconds(),
        "status": "interrupted" if should_stop.is_set() else "completed", "rows": total,
        "parsed_rows": parsed, "control_rows": control, "nonparsed_rows": unsupported,
        "reconnect_count": reconnect_count, "message_counts": message_counts,
        "files": {
            "normalized_events_csv": str(output), "raw_events_jsonl": str(raw_output),
            "connection_events_csv": str(connection_output),
        },
    }
    if output.exists():
        result["files"]["normalized_events_sha256"] = sha256(output)
    if raw_output.exists():
        result["files"]["raw_events_sha256"] = sha256(raw_output)
    write_runtime(runtime_output, result)
    print(
        f"done. saved {total} rows to {output} "
        f"(parsed={parsed}, control={control}, nonparsed={unsupported}, reconnects={reconnect_count})", flush=True,
    )
    return result


def parse_bbox(text: str) -> list[list[float]]:
    parts = [float(x.strip()) for x in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be lat_min,lon_min,lat_max,lon_max")
    lat_min, lon_min, lat_max, lon_max = parts
    if not (-90 <= lat_min < lat_max <= 90 and -180 <= lon_min < lon_max <= 180):
        raise argparse.ArgumentTypeError("bbox coordinates or ordering are invalid")
    return [[lat_min, lon_min], [lat_max, lon_max]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect reusable AIS data for the Malacca/Singapore Strait study area.")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--hours", type=float, default=1 / 6)
    parser.add_argument("--bbox", type=parse_bbox, default=DEFAULT_BBOX)
    parser.add_argument("--region-id", default=DEFAULT_REGION_ID)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-output", required=True)
    parser.add_argument("--connection-output", required=True)
    parser.add_argument("--runtime-output", required=True)
    parser.add_argument("--endpoint", default="wss://stream.aisstream.io/v0/stream")
    parser.add_argument("--flush-every", type=int, default=1)
    parser.add_argument("--idle-timeout", type=float, default=30)
    parser.add_argument("--print-every", type=int, default=1)
    parser.add_argument("--message-types", type=parse_message_types, default=DEFAULT_MESSAGE_TYPES)
    parser.add_argument("--no-raw-json", action="store_false", dest="raw_json")
    parser.set_defaults(raw_json=True)
    args = parser.parse_args()
    if args.hours <= 0:
        parser.error("hours must be positive")
    if args.flush_every <= 0:
        parser.error("flush-every must be positive")
    asyncio.run(collect(args))


if __name__ == "__main__":
    main()
