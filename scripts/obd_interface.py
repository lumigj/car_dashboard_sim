#!/usr/bin/env python3

import argparse
import sys
import threading
import time

import obd
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from obd_logger import DASHBOARD_COMMANDS, connect, get_commands, simple_value


is_mock = True

FAST_COMMANDS = [
    "RPM",
    "SPEED",
]

SLOW_COMMANDS = [
    "COOLANT_TEMP",
    "THROTTLE_POS",
    "ENGINE_LOAD",
    "INTAKE_TEMP",
]

UI_REFRESH_MS = 100
FAST_INTERVAL_S = 0.2
SLOW_INTERVAL_S = 1.0

MOCK_VALUES = {
    "RPM": "1805 revolutions_per_minute",
    "SPEED": "40 kilometer_per_hour",
    "COOLANT_TEMP": "89 degree_Celsius",
    "THROTTLE_POS": "55 percent",
    "ENGINE_LOAD": "38 percent",
    "INTAKE_TEMP": "70 degree_Celsius",
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="ELM327 port, for example /dev/ttyUSB0")
    return parser.parse_args()


class QueryThread(QThread):
    values_changed = pyqtSignal(dict)

    def __init__(self, connection, commands):
        super().__init__()
        self.setObjectName("query thread")
        self.connection = connection
        self.commands = commands
        self.fast_interval = FAST_INTERVAL_S
        self.slow_interval = SLOW_INTERVAL_S
        self.running = True

    def run(self):
        threading.current_thread().name = "query thread"

        next_fast_poll = 0
        next_slow_poll = 0

        while self.running:
            now = time.monotonic()
            did_poll = False

            if now >= next_fast_poll:
                self.poll(FAST_COMMANDS)
                next_fast_poll = now + self.fast_interval
                did_poll = True

            if now >= next_slow_poll:
                self.poll(SLOW_COMMANDS)
                next_slow_poll = now + self.slow_interval
                did_poll = True

            if not did_poll:
                next_poll = min(next_fast_poll, next_slow_poll)
                sleep_ms = max(10, min(50, int((next_poll - now) * 1000)))
                self.msleep(sleep_ms)

    def stop(self):
        self.running = False

    def poll(self, names):
        if is_mock:
            values = {name: MOCK_VALUES[name] for name in names}
        else:
            values = {}
            for name in names:
                cmd = self.commands.get(name)
                if cmd:
                    values[name] = simple_value(self.connection.query(cmd))

        if values:
            self.values_changed.emit(values)


class ObdWindow(QWidget):
    def __init__(self, connection, query_thread):
        super().__init__()
        self.connection = connection
        self.query_thread = query_thread
        self.latest_values = {name: "-" for name in DASHBOARD_COMMANDS}

        self.setWindowTitle("OBD Dashboard")
        self.setStyleSheet("background: black; color: white;")

        layout = QVBoxLayout()
        self.labels = {}
        for name in DASHBOARD_COMMANDS:
            label = QLabel("%s: -" % name)
            label.setStyleSheet("font-size: 32px;")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            self.labels[name] = label
        self.setLayout(layout)

        self.query_thread.values_changed.connect(self.save_latest_values)
        self.query_thread.start()

        self.ui_timer = QTimer(self)
        self.ui_timer.setObjectName("ui thread refresh timer")
        self.ui_timer.timeout.connect(self.update_values)
        self.ui_timer.start(UI_REFRESH_MS)
        self.update_values()

    def save_latest_values(self, values):
        self.latest_values.update(values)

    def update_values(self):
        for name in DASHBOARD_COMMANDS:
            self.labels[name].setText("%s: %s" % (name, self.latest_values[name]))

    def closeEvent(self, event):
        self.query_thread.stop()
        self.query_thread.wait()
        if self.connection:
            self.connection.close()
        event.accept()


def main():
    args = parse_args()
    app = QApplication(sys.argv)
    threading.current_thread().name = "ui thread"
    QThread.currentThread().setObjectName("ui thread")

    connection = None
    commands = {}

    if not is_mock:
        connection = connect(args.port)
        if connection.status() == obd.OBDStatus.NOT_CONNECTED:
            print("Could not connect to ELM327")
            return 1
        commands = {
            cmd.name: cmd
            for cmd in get_commands(connection, FAST_COMMANDS + SLOW_COMMANDS)
        }

    query_thread = QueryThread(
        connection,
        commands,
    )
    window = ObdWindow(connection, query_thread)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
