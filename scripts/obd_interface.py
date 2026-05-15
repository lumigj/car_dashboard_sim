#!/usr/bin/env python3

import argparse
from collections import deque
from pathlib import Path
import sys
import threading
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import obd
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from dashboard.dashboard import DashBoard
from obd_logger import connect, get_commands, simple_value


is_mock = False
BACKGROUND_COLOR = "#000000"
BASE_WINDOW_WIDTH = 1280
BASE_WINDOW_HEIGHT = 720
BASE_DASHBOARD_WIDTH = 900
BASE_DASHBOARD_HEIGHT = 600
DASHBOARD_HEIGHT_RATIO = 0.9
DEFAULT_PORTS = [
    "/dev/ttyUSB0",
    "/dev/ttyUSB1",
]

FAST_COMMANDS = [
    "RPM",
    "SPEED",
    # "TIMING_ADVANCE",

]

UI_REFRESH_MS = 200
RETRY_INTERVAL_S = 10.0
SLOW_COMMANDS = {
    # "THROTTLE_POS": 0.3,
    # "ENGINE_LOAD": 0.3,
    # "INTAKE_PRESSURE": 0.3,
    # "INTAKE_TEMP": 15.0,
    # "COOLANT_TEMP": 15.0,
    # "STATUS": 20.0,
    # "SHORT_FUEL_TRIM_1": 0.3,
    # "LONG_FUEL_TRIM_1": 36.0,
}

ALL_COMMANDS = FAST_COMMANDS + list(SLOW_COMMANDS)
PRIMARY_COMMANDS = [
    "SPEED",
    "RPM",
]
RIGHT_SIDE_COMMANDS = [
    # "THROTTLE_POS",
    # "ENGINE_LOAD",
    # "COOLANT_TEMP",
]

MOCK_VALUES = {
    "RPM": "6024 revolutions_per_minute",
    "SPEED": "196 kilometer_per_hour",
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


def numeric_value(value):
    text = str(value)
    if text == "-":
        return 0
    return round(float(text.split(" ", 1)[0]))


def clamped_numeric_value(value, minimum, maximum):
    return max(minimum, min(maximum, numeric_value(value)))


def fit_16_9_size(width, height):
    fitted_height = round(width * 9 / 16)
    if fitted_height <= height:
        return width, fitted_height
    return round(height * 16 / 9), height


def scaled(value, scale):
    return max(1, round(value * scale))


def dashboard_size(window_height):
    height = round(window_height * DASHBOARD_HEIGHT_RATIO)
    width = round(height * BASE_DASHBOARD_WIDTH / BASE_DASHBOARD_HEIGHT)
    return width, height


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


class ProgressMetric(QFrame):
    def __init__(self, title, scale=1.0):
        super().__init__()
        self.setStyleSheet(
            "QFrame { background-color: #000000; border: 1px solid #202020; border-radius: 8px; }"
            "QLabel { border: 0; }"
            "QProgressBar {"
            "background-color: #111111;"
            "border: 1px solid #303030;"
            "border-radius: 5px;"
            "height: %dpx;"
            "}"
            "QProgressBar::chunk { background-color: #38bdf8; border-radius: 5px; }"
            % scaled(16, scale)
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(
            scaled(8, scale),
            scaled(6, scale),
            scaled(8, scale),
            scaled(6, scale),
        )
        layout.setSpacing(scaled(4, scale))

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "font-size: %dpx; color: #94a3b8; font-weight: bold;"
            % scaled(15, scale)
        )
        layout.addWidget(title_label)

        self.value_label = QLabel("-")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.value_label.setStyleSheet(
            "font-size: %dpx; color: #e2e8f0; font-weight: bold;"
            % scaled(24, scale)
        )
        layout.addWidget(self.value_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)

        self.setLayout(layout)

    def set_value(self, value):
        self.bar.setValue(value)
        self.value_label.setText("%d%%" % value)


class TemperatureMetric(QFrame):
    def __init__(self, title, scale=1.0):
        super().__init__()
        self.minimum_temp = 40
        self.maximum_temp = 120
        self.setFixedWidth(scaled(150, scale))
        self.setStyleSheet(
            "QFrame { background-color: #000000; border: 1px solid #202020; border-radius: 8px; }"
            "QLabel { border: 0; }"
            "QProgressBar {"
            "background-color: #111111;"
            "border: 1px solid #303030;"
            "border-radius: 7px;"
            "width: %dpx;"
            "}"
            "QProgressBar::chunk { background-color: #ef4444; border-radius: 7px; }"
            % scaled(18, scale)
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(
            scaled(6, scale),
            scaled(6, scale),
            scaled(6, scale),
            scaled(6, scale),
        )
        layout.setSpacing(scaled(4, scale))

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(
            "font-size: %dpx; color: #94a3b8; font-weight: bold;"
            % scaled(15, scale)
        )
        layout.addWidget(title_label)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(scaled(4, scale))

        self.bar = QProgressBar()
        self.bar.setOrientation(Qt.Orientation.Vertical)
        self.bar.setRange(self.minimum_temp, self.maximum_temp)
        self.bar.setTextVisible(False)
        body_layout.addWidget(self.bar, 0, Qt.AlignmentFlag.AlignCenter)

        self.value_label = QLabel("-")
        self.value_label.setStyleSheet(
            "font-size: %dpx; color: #e2e8f0; font-weight: bold;"
            % scaled(24, scale)
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        body_layout.addWidget(self.value_label, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(body_layout, 1)
        self.setLayout(layout)

    def set_value(self, value):
        self.bar.setValue(value)
        self.value_label.setText("%d C" % value)


class ObdWindow(QWidget):
    def __init__(self, query_thread, window_size):
        super().__init__()
        self.query_thread = query_thread
        self.latest_values = {name: "-" for name in ALL_COMMANDS}
        self.status = "STARTING"
        self.window_width, self.window_height = window_size
        self.scale = min(
            self.window_width / BASE_WINDOW_WIDTH,
            self.window_height / BASE_WINDOW_HEIGHT,
        )
        self.dashboard_width, self.dashboard_height = dashboard_size(self.window_height)

        self.setWindowTitle("OBD Dashboard")
        self.resize(self.window_width, self.window_height)
        self.setStyleSheet("background-color: %s; color: white;" % BACKGROUND_COLOR)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            scaled(8, self.scale),
            scaled(4, self.scale),
            scaled(8, self.scale),
            scaled(6, self.scale),
        )
        layout.setSpacing(scaled(4, self.scale))

        self.status_label = QLabel(self.status)
        self.status_label.setStyleSheet(
            "font-size: %dpx; color: #ff6b6b;" % scaled(18, self.scale)
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.labels = {}
        self.progress_metrics = {}

        dashboard_row = QHBoxLayout()
        dashboard_row.setContentsMargins(0, 0, 0, 0)
        dashboard_row.setSpacing(0)
        self.dashboard_widget = DashBoard(self)
        self.dashboard_widget.setFixedSize(
            self.dashboard_width,
            self.dashboard_height,
        )
        self.dashboard_widget.setStyleSheet("background-color: %s; border: 0;" % BACKGROUND_COLOR)
        self.dashboard_widget.show_dashboard()
        dashboard_row.addWidget(self.dashboard_widget, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(dashboard_row, 1)

        self.setLayout(layout)

        self.query_thread.values_changed.connect(self.save_latest_values)
        self.query_thread.status_changed.connect(self.save_status)
        self.query_thread.start()

        self.ui_timer = QTimer(self)
        self.ui_timer.setObjectName("ui thread refresh timer")
        self.ui_timer.timeout.connect(self.update_values)
        self.ui_timer.start(UI_REFRESH_MS)
        self.update_values()

    def make_data_panel(self, name):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame {"
            "background-color: %s;"
            "border: 1px solid #202020;"
            "border-radius: 8px;"
            "}" % BACKGROUND_COLOR
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(
            scaled(6, self.scale),
            scaled(3, self.scale),
            scaled(6, self.scale),
            scaled(3, self.scale),
        )
        layout.setSpacing(scaled(2, self.scale))

        title = QLabel(display_name(name))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: %dpx; color: #94a3b8; font-weight: bold; border: 0;"
            % scaled(14, self.scale)
        )
        layout.addWidget(title)

        value = QLabel("-")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setStyleSheet(
            "font-size: %dpx; color: #e2e8f0; border: 0;" % scaled(18, self.scale)
        )
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
        self.dashboard_widget.set_values(
            numeric_value(self.latest_values["SPEED"]),
            numeric_value(self.latest_values["RPM"]),
        )
        for name in self.labels:
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

    screen = app.primaryScreen().geometry()
    window_size = fit_16_9_size(screen.width(), screen.height())

    query_thread = QueryThread(args.port)
    window = ObdWindow(query_thread, window_size)

    if is_mock and not is_mf:
        window.show()
    else:
        window.showFullScreen()

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
