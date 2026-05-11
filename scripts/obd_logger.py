#!/usr/bin/env python3

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

import obd


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="ELM327 port, for example /dev/ttyUSB0")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--output", default="logs/obd_log.csv")
    return parser.parse_args()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def simple_value(response):
    if response.is_null():
        return ""

    value = response.value
    if hasattr(value, "magnitude"):
        return value.magnitude
    return str(value)


def main():
    args = parse_args()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    connection = obd.OBD(args.port)
    if connection.status() == obd.OBDStatus.NOT_CONNECTED:
        print("Could not connect to ELM327")
        return 1

    commands = sorted(
        [
            cmd
            for cmd in connection.supported_commands
            if cmd.mode == 1 and not cmd.name.startswith("PIDS_")
        ],
        key=lambda cmd: (cmd.mode, cmd.pid, cmd.name),
    )

    print("Connected")
    print("Logging %d commands to %s" % (len(commands), args.output))

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_utc"] + [cmd.name for cmd in commands])

        try:
            while True:
                row = [utc_now()]
                for cmd in commands:
                    row.append(simple_value(connection.query(cmd)))
                writer.writerow(row)
                f.flush()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped")
        finally:
            connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
