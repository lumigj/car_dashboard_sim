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
from PyQt5.QtCore import Qt, QRectF, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from dashboard.dashboard import DashBoard
from obd_logger import connect, get_commands, simple_value


is_mock = False
BACKGROUND_COLOR = "#000000"
BASE_WINDOW_WIDTH = 1280
BASE_WINDOW_HEIGHT = 720
BASE_DASHBOARD_WIDTH = 928
BASE_DASHBOARD_HEIGHT = 600
DASHBOARD_HEIGHT_RATIO = 0.9
DEFAULT_PORTS = [
    "/dev/ttyUSB0",
    "/dev/ttyUSB1",
]

FAST_COMMANDS = [
    "RPM",
    "SPEED",
    "TIMING_ADVANCE",

]

UI_REFRESH_MS = 300 # UI_REFRESH_MS 是数据同步频率，DASHBOARD_ANIMATION_INTERVAL_MS 是动画帧率
DASHBOARD_ANIMATION_INTERVAL_MS = 30
GAUGE_ANIMATION_EASING = 0.2
GAUGE_ANIMATION_MIN_STEP = 0.2
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
GAUGE_COMMANDS = [
    "TIMING_ADVANCE",
    "THROTTLE_POS",
    "ENGINE_LOAD",
]
DIRECT_GAUGE_COMMANDS = [
    "COOLANT_TEMP",
]
RIGHT_INFO_COMMANDS = [
    "INTAKE_PRESSURE",
    "INTAKE_TEMP",
    "SHORT_FUEL_TRIM_1",
    "LONG_FUEL_TRIM_1",
    "STATUS",
]
GAUGE_RANGES = {
    "TIMING_ADVANCE": (-20, 40),
    "THROTTLE_POS": (0, 100),
    "ENGINE_LOAD": (0, 100),
    "COOLANT_TEMP": (40, 120),
}

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
    if name == "STATUS" and text != "-":
        return text.replace("MIL=False", "MIL OFF").replace("MIL=True", "MIL ON").replace(" ignition=", " ")

    return (
        text.replace(" revolutions_per_minute", " rpm")
        .replace(" kilometer_per_hour", " km/h")
        .replace(" degree_Celsius", " C")
        .replace(" kilopascal", " kPa")
        .replace(" percent", "%")
        .replace(" degree", " deg")
    )


def display_name(name):
    names = {
        "TIMING_ADVANCE": "TIMING",
        "THROTTLE_POS": "THROTTLE",
        "ENGINE_LOAD": "LOAD",
        "INTAKE_PRESSURE": "INTAKE kPa",
        "INTAKE_TEMP": "INTAKE C",
        "COOLANT_TEMP": "COOLANT",
        "SHORT_FUEL_TRIM_1": "ST FUEL",
        "LONG_FUEL_TRIM_1": "LT FUEL",
    }
    return names.get(name, name.replace("_", " "))


def numeric_value(value):
    text = str(value)
    if text == "-":
        return 0
    return round(float(text.split(" ", 1)[0]))


def gauge_value(name, value):
    if str(value) == "-":
        return 0

    minimum, maximum = GAUGE_RANGES[name]
    number = numeric_value(value)
    return max(minimum, min(maximum, number))


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


class GaugeBar(QWidget):
    def __init__(self, name, scale):
        super().__init__()
        self.name = name
        self.scale = scale
        self.value = 0
        self.setFixedHeight(scaled(14, scale))

    def set_value(self, value):
        self.value = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(0, 0, -1, -1)
        radius = scaled(4, self.scale)
        painter.setPen(QColor("#303030"))
        painter.setBrush(QColor("#101010"))
        painter.drawRoundedRect(rect, radius, radius)

        value = self.value
        minimum, maximum = GAUGE_RANGES[self.name]

        if self.name == "TIMING_ADVANCE":
            center = rect.left() + rect.width() / 2
            half_width = rect.width() / 2
            if value < 0:
                width = abs(value) / abs(minimum) * half_width
                fill = QRectF(center - width, rect.top(), width, rect.height())
                color = QColor("#ef4444")
            else:
                width = value / maximum * half_width
                fill = QRectF(center, rect.top(), width, rect.height())
                color = QColor("#22c55e")

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(fill, radius, radius)
            painter.setPen(QColor("#64748b"))
            painter.drawLine(round(center), round(rect.top()), round(center), round(rect.bottom()))
        else:
            width = (value - minimum) / (maximum - minimum) * rect.width()
            fill = QRectF(rect.left(), rect.top(), width, rect.height())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.fill_color(value))
            painter.drawRoundedRect(fill, radius, radius)

    def fill_color(self, value):
        if self.name != "COOLANT_TEMP":
            return QColor("#22c55e")
        if value >= 105:
            return QColor("#ef4444")
        if value >= 95:
            return QColor("#eab308")
        return QColor("#22c55e")


class GaugeMetric(QFrame):
    def __init__(self, name, scale, animated=True):
        super().__init__()
        self.name = name
        self.animated = animated
        self.target_value = 0
        self.display_value = 0
        self.setFixedWidth(scaled(220, scale))
        self.setStyleSheet(
            "QFrame { background-color: #050505; border: 1px solid #181818; border-radius: 4px; }"
            "QLabel { border: 0; }"
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(
            scaled(5, scale),
            scaled(3, scale),
            scaled(5, scale),
            scaled(3, scale),
        )
        layout.setSpacing(scaled(3, scale))

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(scaled(4, scale))

        title = QLabel(display_name(name))
        title.setStyleSheet(
            "font-size: %dpx; color: #94a3b8; font-weight: bold;" % scaled(12, scale)
        )
        header.addWidget(title)

        self.value_label = QLabel("-")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.value_label.setStyleSheet(
            "font-size: %dpx; color: #e5e7eb; font-weight: bold;" % scaled(14, scale)
        )
        header.addWidget(self.value_label, 1)
        layout.addLayout(header)

        self.bar = GaugeBar(name, scale)
        layout.addWidget(self.bar)
        self.setLayout(layout)

        if self.animated:
            self.animation_timer = QTimer(self)
            self.animation_timer.timeout.connect(self.update_display_value)
            self.animation_timer.start(DASHBOARD_ANIMATION_INTERVAL_MS)

    def set_value(self, value):
        self.target_value = gauge_value(self.name, value)
        if not self.animated:
            self.display_value = self.target_value
            self.value_label.setText(self.display_text())
            self.bar.set_value(self.display_value)

    def update_display_value(self):
        next_value = self.approach_display_value(self.display_value, self.target_value)
        if next_value == self.display_value:
            return

        self.display_value = next_value
        self.value_label.setText(self.display_text())
        self.bar.set_value(self.display_value)

    def approach_display_value(self, current, target):
        diff = target - current
        if abs(diff) <= GAUGE_ANIMATION_MIN_STEP:
            return target
        return current + diff * GAUGE_ANIMATION_EASING

    def display_text(self):
        if self.name == "TIMING_ADVANCE":
            return "%.1f deg" % self.display_value
        if self.name == "COOLANT_TEMP":
            return "%d C" % round(self.display_value)
        return "%d%%" % round(self.display_value)


class InfoMetric(QFrame):
    def __init__(self, name, scale):
        super().__init__()
        self.name = name
        self.setFixedWidth(scaled(220, scale))
        self.setStyleSheet(
            "QFrame { background-color: #050505; border: 1px solid #181818; border-radius: 4px; }"
            "QLabel { border: 0; }"
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(
            scaled(6, scale),
            scaled(3, scale),
            scaled(6, scale),
            scaled(3, scale),
        )
        layout.setSpacing(scaled(5, scale))

        title = QLabel(display_name(name))
        title.setStyleSheet(
            "font-size: %dpx; color: #94a3b8; font-weight: bold;" % scaled(11, scale)
        )
        layout.addWidget(title)

        self.value_label = QLabel("-")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setWordWrap(True)
        self.value_label.setStyleSheet(
            "font-size: %dpx; color: #e5e7eb; font-weight: bold;" % scaled(12, scale)
        )
        layout.addWidget(self.value_label, 1)

        self.setLayout(layout)

    def set_value(self, value):
        self.value_label.setText(compact_value(self.name, value))


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
            scaled(6, self.scale),
            scaled(2, self.scale),
            scaled(6, self.scale),
            scaled(4, self.scale),
        )
        layout.setSpacing(scaled(3, self.scale))

        self.status_label = QLabel(self.status)
        self.status_label.setStyleSheet(
            "font-size: %dpx; color: #ff6b6b;" % scaled(16, self.scale)
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.labels = {}
        self.gauge_metrics = {}
        self.info_metrics = {}

        dashboard_row = QHBoxLayout()
        dashboard_row.setContentsMargins(0, 0, 0, 0)
        dashboard_row.setSpacing(scaled(6, self.scale))
        self.dashboard_widget = DashBoard(self)
        self.dashboard_widget.setFixedSize(
            self.dashboard_width,
            self.dashboard_height,
        )
        self.dashboard_widget.setStyleSheet("background-color: %s; border: 0;" % BACKGROUND_COLOR)
        self.dashboard_widget.set_animation_interval_ms(DASHBOARD_ANIMATION_INTERVAL_MS)
        self.dashboard_widget.show_dashboard()
        dashboard_row.addWidget(self.dashboard_widget, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        right_metrics = QVBoxLayout()
        right_metrics.setContentsMargins(0, scaled(8, self.scale), 0, 0)
        right_metrics.setSpacing(scaled(5, self.scale))
        for name in GAUGE_COMMANDS:
            self.gauge_metrics[name] = GaugeMetric(name, self.scale)
            right_metrics.addWidget(self.gauge_metrics[name])
        for name in DIRECT_GAUGE_COMMANDS:
            self.gauge_metrics[name] = GaugeMetric(name, self.scale, animated=False)
            right_metrics.addWidget(self.gauge_metrics[name])
        for name in RIGHT_INFO_COMMANDS:
            self.info_metrics[name] = InfoMetric(name, self.scale)
            right_metrics.addWidget(self.info_metrics[name])
        right_metrics.addStretch(1)
        dashboard_row.addLayout(right_metrics)
        dashboard_row.addStretch(1)
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
        for name in self.gauge_metrics:
            self.gauge_metrics[name].set_value(self.latest_values[name])
        for name in self.info_metrics:
            self.info_metrics[name].set_value(self.latest_values[name])

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
