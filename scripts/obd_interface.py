#!/usr/bin/env python3

import argparse
from collections import deque
import sys
import threading
import time

import obd
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from pint.delegates.formatter import full

from obd_logger import connect, get_commands, simple_value


is_mock = False
DEFAULT_PORTS = [
    "/dev/ttyUSB0",
    "/dev/ttyUSB1",
]

FAST_COMMANDS = [
    "RPM",
    "SPEED",
    "TIMING_ADVANCE",

]

UI_REFRESH_MS = 125
RETRY_INTERVAL_S = 10.0
SLOW_COMMANDS = {
    "THROTTLE_POS": 0.3,
    "ENGINE_LOAD": 0.3,
    "INTAKE_PRESSURE": 0.3,
    "INTAKE_TEMP": 15.0,
    "COOLANT_TEMP": 15.0,
    "STATUS": 20.0,
    "SHORT_FUEL_TRIM_1": 0.3,
    "LONG_FUEL_TRIM_1": 36.0,
}

ALL_COMMANDS = FAST_COMMANDS + list(SLOW_COMMANDS)
PRIMARY_COMMANDS = [
    "SPEED",
    "RPM",
]

MOCK_VALUES = {
    "RPM": "1805 revolutions_per_minute",
    "SPEED": "40 kilometer_per_hour",
    "TIMING_ADVANCE": "2.0 degree",
    "COOLANT_TEMP": "89 degree_Celsius",
    "THROTTLE_POS": "55 percent",
    "ENGINE_LOAD": "38 percent",
    "INTAKE_TEMP": "70 degree_Celsius",
    "INTAKE_PRESSURE": "48 kilopascal",
    "STATUS": "MIL=False DTC=0 ignition=spark",
    "SHORT_FUEL_TRIM_1": "5.46875 percent",
    "LONG_FUEL_TRIM_1": "9.375 percent",
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Use mock dashboard values")
    parser.add_argument("--port", help="ELM327 port, for example /dev/ttyUSB0")
    parser.add_argument("--mockfull", action="store_true")
    args = parser.parse_args()
    if args.mock and args.port:
        parser.error("--mock cannot be used with --port")
    return args


def compact_value(name, value):
    text = str(value)
    if name in PRIMARY_COMMANDS:
        return text.split(" ", 1)[0].split(".", 1)[0]

    return (
        text.replace(" revolutions_per_minute", " rpm")
        .replace(" kilometer_per_hour", " km/h")
        .replace(" degree_Celsius", " C")
        .replace(" kilopascal", " kPa")
        .replace(" percent", "%")
        .replace(" degree", " deg")
    )


def display_name(name):
    return name.replace("_", " ")


class QueryThread(QThread):
    values_changed = pyqtSignal(dict)
    status_changed = pyqtSignal(str)

    def __init__(self, port):
        super().__init__()
        self.setObjectName("query thread")
        self.port = port
        self.connection = None
        self.commands = {}
        self.next_slow_polls = {
            name: 0.0
            for name in SLOW_COMMANDS
        }
        self.pending_slow_commands = deque()
        self.pending_slow_command_names = set()
        self.running = True

    def run(self):
        threading.current_thread().name = "query thread"

        if is_mock:
            self.status_changed.emit("MOCK DATA")
            self.poll_loop()
            return

        retry_at = 0
        while self.running:
            now = time.monotonic()
            if now >= retry_at:
                if self.connect_live():
                    self.poll_loop()
                retry_at = time.monotonic() + RETRY_INTERVAL_S
            else:
                remaining = int(retry_at - now) + 1
                self.status_changed.emit("CANNOT CONNECT OBD - RETRY IN %dS" % remaining)
            self.msleep(100)

    def poll_loop(self):
        while self.running:
            now = time.monotonic()

            if not self.poll(FAST_COMMANDS):
                return

            self.queue_due_slow_commands(now)
            if not self.poll_next_slow_command():
                return

            self.msleep(1)

    def queue_due_slow_commands(self, now):
        for name in SLOW_COMMANDS:
            if name in self.pending_slow_command_names:
                continue
            if now >= self.next_slow_polls[name]:
                self.pending_slow_commands.append(name)
                self.pending_slow_command_names.add(name)

    def poll_next_slow_command(self):
        if not self.pending_slow_commands:
            return True

        name = self.pending_slow_commands.popleft()
        self.pending_slow_command_names.remove(name)
        if not self.poll([name]):
            return False

        self.next_slow_polls[name] = time.monotonic() + SLOW_COMMANDS[name]
        return True

    def stop(self):
        self.running = False
        self.close_connection()

    def connect_live(self):
        ports = [self.port] if self.port else DEFAULT_PORTS
        errors = []

        self.status_changed.emit("CONNECTING OBD")
        for port in ports:
            if not self.running:
                return False
            try:
                self.connect_port(port)
                self.status_changed.emit("LIVE %s" % port)
                return True
            except Exception as error:
                errors.append(str(error))

        self.close_connection()
        self.values_changed.emit({name: "-" for name in ALL_COMMANDS})
        self.status_changed.emit(
            "CANNOT CONNECT OBD - RETRY IN %dS" % int(RETRY_INTERVAL_S)
        )
        print("\n".join(errors))
        return False

    def connect_port(self, port):
        self.close_connection()
        self.connection = connect(port)
        if self.connection.status() == obd.OBDStatus.NOT_CONNECTED:
            raise RuntimeError("%s: could not connect to ELM327" % port)

        self.commands = {
            cmd.name: cmd
            for cmd in get_commands(self.connection, ALL_COMMANDS)
        }
        if not self.commands:
            raise RuntimeError("%s: no dashboard OBD commands supported" % port)

        for name in ALL_COMMANDS:
            cmd = self.commands.get(name)
            if cmd:
                response = self.connection.query(cmd)
                if not response.is_null():
                    return

        raise RuntimeError("%s: connected but no dashboard values returned" % port)

    def close_connection(self):
        if self.connection:
            self.connection.close()
        self.connection = None
        self.commands = {}
        self.pending_slow_commands.clear()
        self.pending_slow_command_names.clear()

    def poll(self, names):
        if is_mock:
            values = {name: MOCK_VALUES[name] for name in names}
        else:
            values = {}
            try:
                for name in names:
                    cmd = self.commands.get(name)
                    if cmd:
                        values[name] = simple_value(self.connection.query(cmd))
            except Exception as error:
                self.close_connection()
                self.values_changed.emit({name: "-" for name in ALL_COMMANDS})
                self.status_changed.emit("OBD LOST - RETRY IN 10S")
                print(error)
                return False

        if values:
            self.values_changed.emit(values)
        return True


class ObdWindow(QWidget):
    def __init__(self, query_thread):
        super().__init__()
        self.query_thread = query_thread
        self.latest_values = {name: "-" for name in ALL_COMMANDS}
        self.status = "STARTING"

        self.setWindowTitle("OBD Dashboard")
        self.resize(800, 480)
        self.setStyleSheet("background: #05080e; color: white;")

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 14, 18, 18)
        layout.setSpacing(12)

        self.status_label = QLabel(self.status)
        self.status_label.setStyleSheet("font-size: 18px; color: #ff6b6b;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.labels = {}

        primary_layout = QHBoxLayout()
        primary_layout.setSpacing(14)
        for name in PRIMARY_COMMANDS:
            primary_layout.addWidget(self.make_primary_panel(name))
        layout.addLayout(primary_layout, 3)

        data_grid = QGridLayout()
        data_grid.setHorizontalSpacing(10)
        data_grid.setVerticalSpacing(10)
        bottom_commands = [name for name in ALL_COMMANDS if name not in PRIMARY_COMMANDS]
        for index, name in enumerate(bottom_commands):
            data_grid.addWidget(self.make_data_panel(name), index // 3, index % 3)
        layout.addLayout(data_grid, 2)

        self.setLayout(layout)

        self.query_thread.values_changed.connect(self.save_latest_values)
        self.query_thread.status_changed.connect(self.save_status)
        self.query_thread.start()

        self.ui_timer = QTimer(self)
        self.ui_timer.setObjectName("ui thread refresh timer")
        self.ui_timer.timeout.connect(self.update_values)
        self.ui_timer.start(UI_REFRESH_MS)
        self.update_values()

    def make_primary_panel(self, name):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame {"
            "background: #101826;"
            "border: 2px solid #26384d;"
            "border-radius: 12px;"
            "}"
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 14, 18, 14)

        title = QLabel(display_name(name))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; color: #8fb3d9; font-weight: bold; border: 0;")
        layout.addWidget(title)

        value = QLabel("-")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setStyleSheet("font-size: 108px; color: #f8fafc; font-weight: bold; border: 0;")
        layout.addWidget(value, 1)

        frame.setLayout(layout)
        self.labels[name] = value
        return frame

    def make_data_panel(self, name):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame {"
            "background: #0b1220;"
            "border: 1px solid #223047;"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        title = QLabel(display_name(name))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 15px; color: #94a3b8; font-weight: bold; border: 0;")
        layout.addWidget(title)

        value = QLabel("-")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setStyleSheet("font-size: 20px; color: #e2e8f0; border: 0;")
        value.setWordWrap(True)
        layout.addWidget(value, 1)

        frame.setLayout(layout)
        self.labels[name] = value
        return frame

    def save_latest_values(self, values):
        self.latest_values.update(values)

    def save_status(self, status):
        self.status = status

    def update_values(self):
        self.status_label.setText(self.status)
        for name in ALL_COMMANDS:
            self.labels[name].setText(compact_value(name, self.latest_values[name]))

    def closeEvent(self, event):
        self.query_thread.stop()
        self.query_thread.wait()
        event.accept()


def main():
    global is_mock

    args = parse_args()
    is_mf = args.mockfull
    is_mock = is_mf
    if not is_mock:
        is_mock = args.mock

    app = QApplication(sys.argv)
    threading.current_thread().name = "ui thread"
    QThread.currentThread().setObjectName("ui thread")

    query_thread = QueryThread(args.port)
    window = ObdWindow(query_thread)

    if is_mf :
        window.showFullScreen()
    if is_mock:
        window.show()
    else:
        window.showFullScreen()

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
