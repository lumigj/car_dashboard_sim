#!/usr/bin/env python3

import argparse
from collections import deque
import sys
import threading
import time

import obd
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from obd_logger import DASHBOARD_COMMANDS, connect, get_commands, simple_value


is_mock = False
DEFAULT_PORTS = [
    "/dev/ttyUSB0",
    "/dev/ttyUSB1",
]

FAST_COMMANDS = [
    "RPM",
    "SPEED",
]

SLOW_COMMANDS = [
    "THROTTLE_POS",
    "ENGINE_LOAD",
    "COOLANT_TEMP",
    "INTAKE_TEMP",
]

UI_REFRESH_MS = 100
RETRY_INTERVAL_S = 10.0
SLOW_COMMAND_INTERVALS = {
    "THROTTLE_POS": 0.25,
    "ENGINE_LOAD": 0.25,
    "COOLANT_TEMP": 10.0,
    "INTAKE_TEMP": 10.0,
}

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
    parser.add_argument("--mock", action="store_true", help="Use mock dashboard values")
    parser.add_argument("--port", help="ELM327 port, for example /dev/ttyUSB0")
    args = parser.parse_args()
    if args.mock and args.port:
        parser.error("--mock cannot be used with --port")
    return args


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

        self.next_slow_polls[name] = time.monotonic() + SLOW_COMMAND_INTERVALS[name]
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
        self.values_changed.emit({name: "-" for name in DASHBOARD_COMMANDS})
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
            for cmd in get_commands(self.connection, FAST_COMMANDS + SLOW_COMMANDS)
        }
        if not self.commands:
            raise RuntimeError("%s: no dashboard OBD commands supported" % port)

        for name in FAST_COMMANDS + SLOW_COMMANDS:
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
                self.values_changed.emit({name: "-" for name in DASHBOARD_COMMANDS})
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
        self.latest_values = {name: "-" for name in DASHBOARD_COMMANDS}
        self.status = "STARTING"

        self.setWindowTitle("OBD Dashboard")
        self.setStyleSheet("background: black; color: white;")

        layout = QVBoxLayout()
        self.status_label = QLabel(self.status)
        self.status_label.setStyleSheet("font-size: 22px; color: #ff5555;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.labels = {}
        for name in DASHBOARD_COMMANDS:
            label = QLabel("%s: -" % name)
            if name in FAST_COMMANDS:
                label.setStyleSheet("font-size: 54px; font-weight: bold;")
            else:
                label.setStyleSheet("font-size: 26px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            self.labels[name] = label
        self.setLayout(layout)

        self.query_thread.values_changed.connect(self.save_latest_values)
        self.query_thread.status_changed.connect(self.save_status)
        self.query_thread.start()

        self.ui_timer = QTimer(self)
        self.ui_timer.setObjectName("ui thread refresh timer")
        self.ui_timer.timeout.connect(self.update_values)
        self.ui_timer.start(UI_REFRESH_MS)
        self.update_values()

    def save_latest_values(self, values):
        self.latest_values.update(values)

    def save_status(self, status):
        self.status = status

    def update_values(self):
        self.status_label.setText(self.status)
        for name in DASHBOARD_COMMANDS:
            self.labels[name].setText("%s: %s" % (name, self.latest_values[name]))

    def closeEvent(self, event):
        self.query_thread.stop()
        self.query_thread.wait()
        event.accept()


def main():
    global is_mock

    args = parse_args()
    is_mock = args.mock

    app = QApplication(sys.argv)
    threading.current_thread().name = "ui thread"
    QThread.currentThread().setObjectName("ui thread")

    query_thread = QueryThread(args.port)
    window = ObdWindow(query_thread)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
