#!/usr/bin/env python3

import argparse
import time
from datetime import datetime, timezone

import obd


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="ELM327 port, for example /dev/ttyUSB0")
    parser.add_argument("--interval", type=float, default=1.0)
    return parser.parse_args()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def simple_value(response):
    if response.is_null():
        return "-"

    value = response.value
    return str(value)


def main():
    args = parse_args()

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
    print("Reading %d commands every %.1f seconds" % (len(commands), args.interval))

    try:
        while True:
            print("\n%s" % utc_now())
            for cmd in commands:
                value = simple_value(connection.query(cmd))
                print("%s: %s" % (cmd.name, value))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
