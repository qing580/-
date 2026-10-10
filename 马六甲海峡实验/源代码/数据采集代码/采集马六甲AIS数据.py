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


DEFAULT_BBOX = [[1.0, 103.0], [3.5, 104.5]]
DEFAULT_FIELDS = [
    "mmsi",
    "timestamp",
    "received_at",
    "lat",
    "lon",
    "sog",
    "cog",
    "heading",
    "nav_status",
    "rate_of_turn",
    "vessel_type",
    "vessel_name",
    "call_sign",
    "imo",
    "destination",
    "message_type",
    "source",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def extract_position_report(message: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("MessageType") != "PositionReport":
        return None

    report = message.get("Message", {}).get("PositionReport", {})
    if not report:
        return None

    lat = report.get("Latitude")
    lon = report.get("Longitude")
    mmsi = report.get("UserID")
    if lat is None or lon is None or mmsi is None:
        return None

    return {
        "mmsi": mmsi,
        "timestamp": report.get("Timestamp") or message.get("MetaData", {}).get("time_utc"),
        "received_at": utc_now().isoformat(),
        "lat": lat,
        "lon": lon,
        "sog": report.get("Sog"),
        "cog": report.get("Cog"),
        "heading": report.get("TrueHeading"),
        "nav_status": report.get("NavigationalStatus"),
        "rate_of_turn": report.get("RateOfTurn"),
        "vessel_type": "",
        "vessel_name": "",
        "call_sign": "",
        "imo": "",
        "destination": "",
        "message_type": message.get("MessageType"),
        "source": "AISStream",
    }


def extract_ship_static_data(message: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("MessageType") != "ShipStaticData":
        return None

    static = message.get("Message", {}).get("ShipStaticData", {})
    if not static:
        return None

    mmsi = static.get("UserID")
    if mmsi is None:
        return None

    return {
        "mmsi": mmsi,
        "timestamp": static.get("Timestamp") or message.get("MetaData", {}).get("time_utc"),
        "received_at": utc_now().isoformat(),
        "lat": "",
        "lon": "",
        "sog": "",
        "cog": "",
        "heading": "",
        "nav_status": "",
        "rate_of_turn": "",
        "vessel_type": static.get("Type"),
        "vessel_name": static.get("Name"),
        "call_sign": static.get("CallSign"),
        "imo": static.get("ImoNumber"),
        "destination": static.get("Destination"),
        "message_type": message.get("MessageType"),
        "source": "AISStream",
    }


async def collect(args: argparse.Namespace) -> None:
    try:
        import websockets
    except ModuleNotFoundError as exc:
        raise SystemExit("缺少依赖 websockets。请先运行：pip install websockets") from exc

    api_key = args.api_key or os.getenv("AISSTREAM_API_KEY")
    if not api_key:
        raise SystemExit(
            "缺少 AISStream API Key。请先设置环境变量：$env:AISSTREAM_API_KEY='你的key'，"
            "或者运行时加 --api-key 你的key。"
        )

    output = Path(args.output)
    ensure_parent(output)

    stop_at = utc_now() + timedelta(hours=args.hours)
    total = 0
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

        while utc_now() < stop_at and not should_stop.is_set():
            try:
                async with websockets.connect(args.endpoint, ping_interval=20, ping_timeout=20) as websocket:
                    subscribe_message = {
                        "APIKey": api_key,
                        "BoundingBoxes": [args.bbox],
                        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
                    }
                    await websocket.send(json.dumps(subscribe_message))
                    print(f"[{utc_now().isoformat()}] started: bbox={args.bbox}, output={output}")

                    async for raw_message in websocket:
                        if utc_now() >= stop_at or should_stop.is_set():
                            break

                        try:
                            message = json.loads(raw_message)
                        except json.JSONDecodeError:
                            continue

                        row = extract_position_report(message) or extract_ship_static_data(message)
                        if row is None:
                            continue

                        writer.writerow(row)
                        total += 1

                        if total % args.flush_every == 0:
                            f.flush()
                            print(f"[{utc_now().isoformat()}] saved {total} AIS position rows")

            except KeyboardInterrupt:
                should_stop.set()
            except Exception as exc:
                reconnect_count += 1
                print(f"[{utc_now().isoformat()}] connection error: {exc}; reconnect #{reconnect_count}")
                await asyncio.sleep(min(60, 5 * reconnect_count))

    print(f"done. saved {total} rows to {output}")


def parse_bbox(text: str) -> list[list[float]]:
    parts = [float(x.strip()) for x in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox 格式应为 lat_min,lon_min,lat_max,lon_max")
    lat_min, lon_min, lat_max, lon_max = parts
    return [[lat_min, lon_min], [lat_max, lon_max]]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect one-day AIS position reports around the Malacca/Singapore Strait via AISStream."
    )
    parser.add_argument("--api-key", default=None, help="AISStream API Key. 推荐用环境变量 AISSTREAM_API_KEY。")
    parser.add_argument("--hours", type=float, default=24, help="采集时长，默认 24 小时。测试可设为 0.05。")
    parser.add_argument(
        "--bbox",
        type=parse_bbox,
        default=DEFAULT_BBOX,
        help="采集范围：lat_min,lon_min,lat_max,lon_max。默认马六甲东南段/新加坡海峡附近。",
    )
    parser.add_argument(
        "--output",
        default="data_raw/ais_malacca_aisstream.csv",
        help="输出 CSV 路径，默认 data_raw/ais_malacca_aisstream.csv。",
    )
    parser.add_argument("--endpoint", default="wss://stream.aisstream.io/v0/stream")
    parser.add_argument("--flush-every", type=int, default=100, help="每多少行刷新一次文件。")
    args = parser.parse_args()

    asyncio.run(collect(args))


if __name__ == "__main__":
    main()
