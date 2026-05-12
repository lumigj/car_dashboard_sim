#!/usr/bin/env python3

import argparse
import sys

import obd
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from obd_logger import DASHBOARD_COMMANDS, connect, get_commands, read_values


mock = True

MOCK_VALUES = {
    "RPM": "805 revolutions_per_minute",
    "SPEED": "0 kilometer_per_hour",
    "COOLANT_TEMP": "89 degree_Celsius",
    "THROTTLE_POS": "14 percent",
    "ENGINE_LOAD": "38 percent",
    "INTAKE_TEMP": "70 degree_Celsius",
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="ELM327 port, for example /dev/ttyUSB0")
    parser.add_argument("--interval", type=float, default=0.5)
    return parser.parse_args()


class ObdWindow(QWidget):
    def __init__(self, connection, commands, interval):
        super().__init__()
        self.connection = connection
        self.commands = commands

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

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_values)
        self.timer.start(int(interval * 1000))
        self.update_values()

    def update_values(self):
        values = MOCK_VALUES if mock else read_values(self.connection, self.commands)
        for name, value in values.items():
            self.labels[name].setText("%s: %s" % (name, value))

    def closeEvent(self, event):
        if self.connection:
            self.connection.close()
        event.accept()


def main():
    args = parse_args()
    app = QApplication(sys.argv)

    connection = None
    commands = []

    if not mock:
        connection = connect(args.port)
        if connection.status() == obd.OBDStatus.NOT_CONNECTED:
            print("Could not connect to ELM327")
            return 1
        commands = get_commands(connection, DASHBOARD_COMMANDS)

    window = ObdWindow(connection, commands, args.interval)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
