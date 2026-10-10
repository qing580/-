from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import signal
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


COLLECTOR_VERSION = "malacca_ais_enhanced_2026-09-06"
DEFAULT_BBOX = [[1.0, 103.0], [3.5, 104.5]]
DEFAULT_MESSAGE_TYPES = [
    "PositionReport",
    "ShipStaticData",
    "StandardClassBPositionReport",
    "ExtendedClassBPositionReport",
    "StaticDataReport",
]
DEFAULT_FIELDS = [
    "collector_version",
    "source",
    "bbox",
    "message_type",
    "received_at",
    "metadata_time_utc",
    "ais_timestamp",
    "mmsi",
    "valid",
    "repeat_indicator",
    "message_id",
    "lat",
    "lon",
    "sog",
    "cog",
    "true_heading",
    "rate_of_turn",
    "navigational_status",
    "position_accuracy",
    "raim",
    "special_manoeuvre_indicator",
    "communication_state",
    "assigned_mode",
    "dte",
    "vessel_name",
    "call_sign",
    "imo",
    "vessel_type",
    "ais_version",
    "fix_type",
    "destination",
    "eta_month",
    "eta_day",
    "eta_hour",
    "eta_minute",
    "draught",
    "dimension_to_bow",
    "dimension_to_stern",
    "dimension_to_port",
    "dimension_to_starboard",
    "ship_length",
    "ship_width",
    "vendor_id_name",
    "vendor_id_model",
    "vendor_id_serial",
    "parse_status",
    "parse_error",
    "raw_json",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
        return "" if set(stripped) <= {"@"} else stripped.replace("@", " ").strip()
    return value if value is not None else ""


def dimensions_from(payload: dict[str, Any]) -> tuple[Any, Any, Any, Any, Any, Any]:
    dim = payload.get("Dimension")
    if not isinstance(dim, dict):
        return "", "", "", "", "", ""
    bow = dim.get("A", "")
    stern = dim.get("B", "")
    port = dim.get("C", "")
    starboard = dim.get("D", "")

    length = ""
    width = ""
    if isinstance(bow, (int, float)) and isinstance(stern, (int, float)):
        length = bow + stern
    if isinstance(port, (int, float)) and isinstance(starboard, (int, float)):
        width = port + starboard
    return bow, stern, port, starboard, length, width


def base_row(message: dict[str, Any], raw_json: str, bbox: list[list[float]], keep_raw: bool) -> dict[str, Any]:
    metadata = message.get("MetaData") if isinstance(message.get("MetaData"), dict) else {}
    return {
        field: ""
        for field in DEFAULT_FIELDS
    } | {
        "collector_version": COLLECTOR_VERSION,
        "source": "AISStream",
        "bbox": json.dumps(bbox, ensure_ascii=False, separators=(",", ":")),
        "message_type": message.get("MessageType", ""),
        "received_at": utc_now().isoformat(),
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
    row["assigned_mode"] = payload.get("AssignedMode", "")
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


def extract_row(message: dict[str, Any], raw_json: str, bbox: list[list[float]], keep_raw: bool) -> dict[str, Any]:
    row = base_row(message, raw_json, bbox, keep_raw)
    message_type = message.get("MessageType")
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
        raise argparse.ArgumentTypeError("message-types 不能为空")
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
    if row.get("imo") not in ("", None, 0, "0"):
        static_bits.append(f"imo={row['imo']}")
    static_text = " ".join(static_bits) if static_bits else "static=-"

    print(
        f"[{utc_now().isoformat()}] row={total} "
        f"msg={short_value(row.get('message_type'), 34)} "
        f"mmsi={short_value(row.get('mmsi'))} "
        f"name={short_value(row.get('vessel_name'))} "
        f"lat={short_value(row.get('lat'))} lon={short_value(row.get('lon'))} "
        f"sog={short_value(row.get('sog'))} cog={short_value(row.get('cog'))} "
        f"nav={short_value(row.get('navigational_status'))} {static_text} "
        f"status={row.get('parse_status', '-')}",
        flush=True,
    )


async def collect(args: argparse.Namespace) -> None:
    try:
        import websockets
    except ModuleNotFoundError as exc:
        raise SystemExit("缺少依赖 websockets。请先运行：pip install websockets") from exc

    api_key = args.api_key or os.getenv("AISSTREAM_API_KEY")
    if not api_key:
        raise SystemExit(
            "缺少 AISStream API Key。请先设置环境变量：$env:AISSTREAM_API_KEY='你的key'，"
            "或者运行时加 --api-key 你的key。不要把 key 截图或写进文档。"
        )

    output = Path(args.output)
    ensure_parent(output)
    if output.exists() and output.stat().st_size > 0 and not args.append:
        raise SystemExit(f"输出文件已存在，为避免覆盖或追加旧数据已停止：{output}")

    stop_at = utc_now() + timedelta(hours=args.hours)
    total = 0
    parsed = 0
    unsupported = 0
    reconnect_count = 0
    should_stop = asyncio.Event()

    def stop_handler(*_: object) -> None:
        should_stop.set()

    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, stop_handler)
        loop.add_signal_handler(signal.SIGTERM, stop_handler)

    with output.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=DEFAULT_FIELDS)
        if output.stat().st_size == 0:
            writer.writeheader()
            f.flush()

        while utc_now() < stop_at and not should_stop.is_set():
            try:
                async with websockets.connect(
                    args.endpoint,
                    ping_interval=20,
                    ping_timeout=20,
                    compression="deflate",
                ) as websocket:
                    subscribe_message = {
                        "APIKey": api_key,
                        "BoundingBoxes": [args.bbox],
                        "FilterMessageTypes": args.message_types,
                    }
                    await websocket.send(json.dumps(subscribe_message))
                    print(
                        f"[{utc_now().isoformat()}] started enhanced AIS collection: "
                        f"bbox={args.bbox}, message_types={args.message_types}, output={output}",
                        flush=True,
                    )

                    while utc_now() < stop_at and not should_stop.is_set():
                        try:
                            raw_message = await asyncio.wait_for(websocket.recv(), timeout=args.idle_timeout)
                        except asyncio.TimeoutError:
                            print(
                                f"[{utc_now().isoformat()}] waiting for AIS messages... "
                                f"saved={total}, parsed={parsed}, nonparsed={unsupported}",
                                flush=True,
                            )
                            continue

                        if utc_now() >= stop_at or should_stop.is_set():
                            break

                        if isinstance(raw_message, bytes):
                            raw_text = raw_message.decode("utf-8", errors="replace")
                        else:
                            raw_text = raw_message

                        try:
                            message = json.loads(raw_text)
                        except json.JSONDecodeError as exc:
                            row = {field: "" for field in DEFAULT_FIELDS}
                            row.update(
                                {
                                    "collector_version": COLLECTOR_VERSION,
                                    "source": "AISStream",
                                    "bbox": json.dumps(args.bbox, ensure_ascii=False, separators=(",", ":")),
                                    "message_type": "JSONDecodeError",
                                    "received_at": utc_now().isoformat(),
                                    "parse_status": "error",
                                    "parse_error": str(exc),
                                    "raw_json": raw_text if args.raw_json else "",
                                }
                            )
                        else:
                            row = extract_row(message, raw_text, args.bbox, args.raw_json)

                        writer.writerow(row)
                        total += 1
                        if row["parse_status"] == "parsed":
                            parsed += 1
                        else:
                            unsupported += 1

                        if args.print_every > 0 and total % args.print_every == 0:
                            print_row_progress(total, row)

                        if total % args.flush_every == 0:
                            f.flush()
                            print(
                                f"[{utc_now().isoformat()}] saved {total} rows "
                                f"(parsed={parsed}, nonparsed={unsupported})",
                                flush=True,
                            )

            except KeyboardInterrupt:
                should_stop.set()
            except Exception as exc:
                reconnect_count += 1
                print(f"[{utc_now().isoformat()}] connection error: {exc}; reconnect #{reconnect_count}", flush=True)
                await asyncio.sleep(min(60, 5 * reconnect_count))

    print(f"done. saved {total} rows to {output} (parsed={parsed}, nonparsed={unsupported})", flush=True)


def parse_bbox(text: str) -> list[list[float]]:
    parts = [float(x.strip()) for x in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox 格式应为 lat_min,lon_min,lat_max,lon_max")
    lat_min, lon_min, lat_max, lon_max = parts
    return [[lat_min, lon_min], [lat_max, lon_max]]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect enhanced AIS messages around the Malacca/Singapore Strait via AISStream."
    )
    parser.add_argument("--api-key", default=None, help="AISStream API Key。推荐用环境变量 AISSTREAM_API_KEY。")
    parser.add_argument("--hours", type=float, default=0.5, help="采集时长，默认 0.5 小时，先做字段覆盖试运行。")
    parser.add_argument(
        "--bbox",
        type=parse_bbox,
        default=DEFAULT_BBOX,
        help="采集范围：lat_min,lon_min,lat_max,lon_max。默认马六甲东南段/新加坡海峡附近。",
    )
    parser.add_argument(
        "--output",
        default="data_raw/ais_malacca_enhanced.csv",
        help="输出 CSV 路径，建议文件名包含日期、小时数和 enhanced 标记。",
    )
    parser.add_argument("--endpoint", default="wss://stream.aisstream.io/v0/stream")
    parser.add_argument("--flush-every", type=int, default=1, help="每多少行刷新一次文件。默认每条刷新，便于实时确认已落盘。")
    parser.add_argument("--idle-timeout", type=float, default=30, help="多少秒没收到消息就在终端打印等待状态，并检查是否到达结束时间。")
    parser.add_argument(
        "--print-every",
        type=int,
        default=1,
        help="每多少行在终端打印一次数据摘要。默认每条打印；设为 0 可关闭逐行显示。",
    )
    parser.add_argument(
        "--message-types",
        type=parse_message_types,
        default=DEFAULT_MESSAGE_TYPES,
        help="逗号分隔的 AISStream 消息类型。默认覆盖 Class A/B 动态和静态船舶资料。",
    )
    parser.add_argument(
        "--no-raw-json",
        action="store_false",
        dest="raw_json",
        help="不保存 raw_json。正式排查字段覆盖时不建议使用。",
    )
    parser.add_argument("--append", action="store_true", help="允许追加到已有输出文件。默认禁止，以免污染历史采集数据。")
    parser.set_defaults(raw_json=True)
    args = parser.parse_args()

    asyncio.run(collect(args))


if __name__ == "__main__":
    main()
