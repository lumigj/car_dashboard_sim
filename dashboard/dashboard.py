from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import random
from datetime import datetime
import sys

# painter render hints
_RENDER_HINTS = (
        QPainter.RenderHint.Antialiasing
        | QPainter.RenderHint.HighQualityAntialiasing
        | QPainter.RenderHint.SmoothPixmapTransform
        | QPainter.RenderHint.LosslessImageRendering
        | QPainter.RenderHint.Qt4CompatiblePainting
        | QPainter.RenderHint.NonCosmeticDefaultPen
        | QPainter.RenderHint.TextAntialiasing
)
_dash_board = None


class _DashBoardMain(QWidget):
    """WARNING: This is a private class. do not import this."""

    def __init__(self, parent, size: tuple | list = (1280, 720)):
        super().__init__()
        # Setting window to no icon, frameless and transparent
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(True)
        self.setFixedSize(*size)

        self.oldPos = QCursor().pos()

        self.initUI()

        self.keys_ = {Qt.Key.Key_W: False, Qt.Key.Key_H: False, Qt.Key.Key_Left: False,
                      Qt.Key.Key_Right: False, Qt.Key.Key_Space: False, Qt.Key.Key_Escape: False}

        self.key_action_timer = QTimer()
        self.key_action_timer.timeout.connect(self.keyAction)
        self.key_action_timer.start(5)

    def initUI(self):
        self.stacked_widget()
        self.dash_board_design()

        self.swidget.setCurrentIndex(0)

    def stacked_widget(self):
        self.swidget = QStackedWidget(self)
        self.swidget.setContentsMargins(0, 0, 0, 0)
        grad = "qlineargradient(spread:pad, x1:0.6, y1:0.4, x2:0.1, y2:0.8, stop:0 {color1}, stop:{value} {color2}, stop:1.0 {color1});".format(
            color1=QColor(0, 0, 0, 100).name(), color2=QColor(13, 13, 13).name(), value=0.5)
        self.setStyleSheet("background-color: %s;" % grad)
        self.swidget.setFixedSize(self.width(), self.height())
        self.swidget.setCurrentIndex(0)



    def dash_board_design(self):
        self.dash_board_design_widget = _DashBoardContolsDesign(self.swidget)
        self.swidget.addWidget(self.dash_board_design_widget)

    def mouseDoubleClickEvent(self, event):
        pass

    def mousePressEvent(self, event):
        pass

    def mouseMoveEvent(self, event):
        pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            QCoreApplication.instance().quit()

    def customKeyPressEvent(self, event):

        # speedometer
        if event.key() == Qt.Key.Key_W or self.keys_[Qt.Key.Key_W]:
            self.keys_[event.key()] = True

        # break
        if event.key() == Qt.Key.Key_Space or self.keys_[Qt.Key.Key_Space]:
            self.keys_[event.key()] = True

    def customKeyReleaseEvent(self, event):

        # speedometer
        if event.key() == Qt.Key.Key_W and not event.isAutoRepeat():
            self.keys_[event.key()] = False
            self.dash_board_design_widget.set_accelerator_state(0)


        # break
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.keys_[event.key()] = False
            self.dash_board_design_widget.set_break_state(0)

    def keyAction(self):
        if any(self.keys_.values()):

            # speedometer
            if self.keys_[Qt.Key.Key_W]:
                self.dash_board_design_widget.set_accelerator_state(1)

            # break
            if self.keys_[Qt.Key.Key_Space]:
                self.dash_board_design_widget.set_break_state(1)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
            self.customKeyPressEvent(event)
        if event.type() == QEvent.Type.KeyRelease:
            if not event.isAutoRepeat():
                self.customKeyReleaseEvent(event)

        return super().eventFilter(source, event)


class _DashBoardContolsDesign(QWidget):
    """WARNING: This is a private class. do not import this."""

    def __init__(self, parent=None):
        super(_DashBoardContolsDesign, self).__init__(parent)
        self.parent_ = parent
        self.resize(self.parent_.size())
        self.setContentsMargins(0, 0, 0, 0)

        self.break_properties()
        self.accelerator_properties()
        self.speedometer_properties()
        self.rpm_properties()

    def break_properties(self):
        self.break_state = 0
        self.break_color_lst = (QColor(67, 13, 13, 200), QGradient(QGradient.Preset.ColorfulPeach))

    def set_break_state(self, val):
        self.break_state = val
        self.repaint()

    def break_painting(self, painter: QPainter):
        # setting break font
        break_font = QFont("Consolas", 0, 0, True)
        break_font.setPixelSize(round(self.width() * 0.045))
        break_fm = QFontMetrics(break_font)
        break_rect = break_fm.boundingRect("BREAK")
        painter.setFont(break_font)

        break_rect.moveTo(
            self.rect().center() + QPointF(self.rect().width() * 0.345, self.rect().height() * 0.1).toPoint())

        painter.setPen(QPen(self.break_color_lst[self.break_state], round(self.width() * 0.0025)))
        painter.drawText(break_rect, Qt.AlignmentFlag.AlignCenter, "BREAK")

    def accelerator_properties(self):
        self.speed_angle_factor = 200 / 300  # 200 default top speed and 300 available angle of speedometer
        self.speed = 0
        self.accelerator_state = 0
        self.accelerator_color_lst = (QColor(67, 13, 13, 200), QGradient(QGradient.Preset.FruitBlend))

    def set_speed(self, val):
        self.speed = round(val / self.speed_angle_factor) if round(val / self.speed_angle_factor) <= 300 else 300
        self.repaint()

    def get_speed(self):
        return round(self.speed * self.speed_angle_factor)

    def speedometer_properties(self):
        self.speedometer_bounding_rect = QRectF(self.width() * 0.173, self.height() * 0.2, self.width() * 0.4,
                                                self.width() * 0.4)

        self.enable_speedometer_resetter = True

        self.speedometer_resetter_timer = QTimer()
        self.speedometer_resetter_timer.timeout.connect(self.speedometer_resetter)
        self.speedometer_resetter_timer.start(5)

        self.speed_range = 200
        self.for_loop_count = self.speed_range // 20 + 2
        self.angle_to_rotate = 300 / (self.speed_range / 20)
        self.compromise_angle = 30 - self.angle_to_rotate
        self.compromise_angle_half = self.compromise_angle + self.angle_to_rotate / 2
        self.enable_sub_number = True

    def set_speedometer_range(self, top_speed):
        if 40 <= top_speed <= 400:
            self.speed_range = int(top_speed - top_speed % -20 if top_speed % 20 >= 10 else top_speed - top_speed % 20)
        elif top_speed < 40:
            self.speed_range = 40
        elif top_speed > 400:
            self.speed_range = 400

        self.speed_angle_factor = self.speed_range / 300
        self.for_loop_count = self.speed_range // 20 + 2
        self.angle_to_rotate = 300 / (self.speed_range / 20)
        self.compromise_angle = 30 - self.angle_to_rotate
        self.compromise_angle_half = self.compromise_angle + self.angle_to_rotate / 2
        self.enable_sub_number = True if self.speed_range <= 260 else False
        self.repaint()

    def set_speedometer_resetter_state(self, val):
        self.enable_speedometer_resetter = val

    def speedometer_resetter(self):
        if self.speed > 0 and self.enable_speedometer_resetter:
            if not self.accelerator_state:  # accelerator released
                if self.break_state:  # break presssed
                    self.speed -= 3 * self.speed_angle_factor
                else:
                    self.speed -= self.speed_angle_factor
            if self.break_state:  # break presssed
                self.speed -= 2 * self.speed_angle_factor
            if self.speed < 0: self.speed = 0
            self.repaint()

    def speedometer_painting(self, painter: QPainter):
        # inner dial design
        speed_arc_start_angle = -59
        speed_arc_span_angle = 298
        conicalGradient = QConicalGradient(self.speedometer_bounding_rect.center(), speed_arc_start_angle)
        conicalGradient.setColorAt(0.0, QColor(66, 245, 66, 220))
        conicalGradient.setColorAt(speed_arc_span_angle / 720, QColor(224, 210, 13, 220))
        conicalGradient.setColorAt(speed_arc_span_angle / 360, QColor(230, 40, 40, 220))
        conicalGradient.setColorAt(1.0, QColor(66, 245, 66, 220))
        inner_dial = self.speedometer_bounding_rect.toRect()
        inner_dial.setSize(QSizeF(self.speedometer_bounding_rect.width() * 0.975,
                                  self.speedometer_bounding_rect.width() * 0.975).toSize())
        inner_dial.moveCenter(self.speedometer_bounding_rect.center().toPoint())
        painter.setPen(QPen(conicalGradient, self.width() * 0.01))
        painter.drawArc(inner_dial, speed_arc_start_angle * 16, speed_arc_span_angle * 16)

        # setting number font
        number_font = QFont("Consolas", 0, 0, True)
        number_font.setPixelSize(round(self.width() * 0.02))
        number_fm = QFontMetrics(number_font)
        number_rect = number_fm.boundingRect("000")
        painter.setFont(number_font)

        # drawing main number and spike
        painter.setPen(QPen(QGradient(QGradient.Preset.FebruaryInk), self.width() * 0.005))
        center = self.speedometer_bounding_rect.center()
        painter.save()
        painter.translate(center.x(), center.y())
        painter.rotate(self.compromise_angle)
        painter.translate(-center.x(), -center.y())
        for a in range(1, self.for_loop_count):
            painter.translate(center.x(), center.y())
            painter.rotate(self.angle_to_rotate)
            painter.translate(-center.x(), -center.y())
            # spike
            spike_p1 = center + QPointF(0, self.speedometer_bounding_rect.height() // 2)
            spike_p2 = center + QPointF(0, self.speedometer_bounding_rect.height() * 0.45)
            painter.drawLine(spike_p1, spike_p2)
            # number
            number_point = spike_p2.toPoint() - QPoint(0, round(self.width() * 0.02))
            painter.save()
            painter.translate(number_point.x(), number_point.y())
            painter.rotate(a * -self.angle_to_rotate - self.compromise_angle)
            painter.translate(-number_point.x(), -number_point.y())
            number_rect.moveCenter(number_point)
            painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, str((a - 1) * 20))
            painter.restore()
        painter.restore()

        # drawing sub number and spike
        painter.setPen(QPen(QGradient(QGradient.Preset.FebruaryInk), self.width() * 0.003))
        number_font.setPixelSize(round(self.width() * 0.015))
        painter.setFont(number_font)
        painter.save()
        painter.translate(center.x(), center.y())
        painter.rotate(self.compromise_angle_half)
        painter.translate(-center.x(), -center.y())
        for a in range(1, self.for_loop_count - 1):
            painter.translate(center.x(), center.y())
            painter.rotate(self.angle_to_rotate)
            painter.translate(-center.x(), -center.y())
            # spike
            spike_p1 = center + QPointF(0, self.speedometer_bounding_rect.height() // 2)
            spike_p2 = center + QPointF(0, self.speedometer_bounding_rect.height() * 0.47)
            painter.drawLine(spike_p1, spike_p2)
            # number
            number_point = spike_p2.toPoint() - QPoint(0, round(self.width() * 0.02))
            if self.enable_sub_number:
                painter.save()
                painter.translate(number_point.x(), number_point.y())
                painter.rotate(a * -self.angle_to_rotate - self.compromise_angle_half)
                painter.translate(-number_point.x(), -number_point.y())
                number_rect.moveCenter(number_point)
                painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, str((2 * a - 1) * 10))
                painter.restore()
        painter.restore()

        # drawing hand
        painter.setPen(
            QPen(QGradient(QGradient.Preset.Blessing), round(self.width() * 0.003), cap=Qt.PenCapStyle.RoundCap))
        painter.setBrush(QBrush(QGradient(QGradient.Preset.Blessing)))
        hand_polygon = (center + QPoint(0, round(self.height() * 0.0055)),
                        center + QPoint(0, -round(self.height() * 0.0055)),
                        center + QPoint(round(self.height() * 0.28), 0))
        painter.save()
        painter.translate(center.x(), center.y())
        painter.rotate(120 + self.speed)
        painter.translate(-center.x(), -center.y())
        painter.drawPolygon(hand_polygon)
        painter.restore()

        # drawing center point
        painter.setPen(
            QPen(QGradient(QGradient.Preset.CrystalRiver), round(self.width() * 0.03), cap=Qt.PenCapStyle.RoundCap))
        painter.drawPoint(center)

        # drawing outer dial
        painter.setPen(QPen(QGradient(QGradient.Preset.CrystalRiver), self.width() * 0.005))
        painter.drawArc(self.speedometer_bounding_rect.toRect(), -60 * 16, 300 * 16)

        # drawing speed in word
        painter.setPen(QPen(QGradient(QGradient.Preset.Crystalline), self.width() * 0.005))
        speed_font = QFont("Consolas", 0, 0, True)
        speed_font.setPixelSize(round(self.width() * 0.035))
        speed_fm = QFontMetrics(speed_font)
        # speed hm/h
        speed_kmph_rect = speed_fm.boundingRect("000-km/h")
        painter.setFont(speed_font)
        speed_kmph_rect.moveCenter(center.toPoint())
        speed_kmph_rect.moveBottom(round(self.speedometer_bounding_rect.bottom()))
        painter.drawText(speed_kmph_rect, Qt.AlignmentFlag.AlignCenter, f'{self.get_speed()} km/h')
        # speed
        speed_word_rect = speed_fm.boundingRect("SPEED")
        painter.setFont(speed_font)
        speed_word_rect.moveCenter(center.toPoint())
        speed_word_rect.moveBottom(round(self.speedometer_bounding_rect.bottom() - speed_kmph_rect.height()))
        painter.drawText(speed_word_rect, Qt.AlignmentFlag.AlignCenter, "SPEED")

    def rpm_properties(self):
        self.max_rpm = 7000
        self.rpm_arc_start_angle = -240
        self.rpm_arc_span_angle = -180
        self.rpm_tick_count = 7
        self.set_rpm(0)

    def set_rpm(self, val):
        self.rpm = max(0, min(self.max_rpm, round(val)))
        self.repaint()

    def get_rpm(self):
        return self.rpm

    def rpm_arc_angle(self, rpm):
        return self.rpm_arc_start_angle + rpm / self.max_rpm * self.rpm_arc_span_angle

    def draw_rpm_arc(self, painter, rect, start_rpm, end_rpm):
        start_angle = self.rpm_arc_angle(start_rpm)
        span_angle = (end_rpm - start_rpm) / self.max_rpm * self.rpm_arc_span_angle
        painter.drawArc(rect, round(start_angle * 16), round(span_angle * 16))

    def rpm_segment_pen(self, color):
        pen = QPen(color, self.width() * 0.01)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        return pen

    def rpm_tick_rotation(self, rpm):
        return -self.rpm_arc_angle(rpm) - 90

    def tachometer_painting(self, painter):
        rpm_bounding_rect = self.speedometer_bounding_rect.toRect()
        rpm_bounding_rect.setSize(
            QSizeF(rpm_bounding_rect.width() * 0.8, rpm_bounding_rect.width() * 0.8).toSize())
        rpm_overlap = round(rpm_bounding_rect.width() * 0.31)
        rpm_bounding_rect.moveBottomLeft(
            self.speedometer_bounding_rect.toRect().bottomRight() - QPoint(rpm_overlap, 0))

        # inner dial
        inner_dial = QRect(*rpm_bounding_rect.getRect())
        inner_dial.setSize(
            QSizeF(rpm_bounding_rect.width() * 0.975, rpm_bounding_rect.width() * 0.975).toSize())
        inner_dial.moveCenter(rpm_bounding_rect.center())
        painter.setPen(self.rpm_segment_pen(QColor(66, 245, 66, 190)))
        self.draw_rpm_arc(painter, inner_dial, 0, 2500)
        painter.setPen(self.rpm_segment_pen(QColor(224, 210, 13, 210)))
        self.draw_rpm_arc(painter, inner_dial, 2500, 3500)
        painter.setPen(self.rpm_segment_pen(QColorConstants.Svg.red))
        self.draw_rpm_arc(painter, inner_dial, 3500, self.max_rpm)

        # setting number font
        number_font = QFont("Consolas", 0, 0, True)
        number_font.setPixelSize(round(self.width() * 0.02))
        number_fm = QFontMetrics(number_font)
        number_rect = number_fm.boundingRect("0000")
        painter.setFont(number_font)

        # drawing main number and spike
        painter.setPen(QPen(QGradient(QGradient.Preset.FebruaryInk), self.width() * 0.005))
        center = rpm_bounding_rect.center()
        for a in range(self.rpm_tick_count + 1):
            rpm_label = round(a * self.max_rpm / self.rpm_tick_count)
            tick_rotation = self.rpm_tick_rotation(rpm_label)
            painter.save()
            painter.translate(center.x(), center.y())
            painter.rotate(tick_rotation)
            painter.translate(-center.x(), -center.y())
            # spike
            spike_p1 = center + QPointF(0, rpm_bounding_rect.height() * 0.495)
            spike_p2 = center + QPointF(0, rpm_bounding_rect.height() * 0.45)
            painter.drawLine(spike_p1, spike_p2)
            # number
            number_point = spike_p2.toPoint() - QPoint(0, round(self.width() * 0.02))
            painter.save()
            painter.translate(number_point.x(), number_point.y())
            painter.rotate(-tick_rotation)
            painter.translate(-number_point.x(), -number_point.y())
            number_rect.moveCenter(number_point)
            painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, str(rpm_label))
            painter.restore()
            painter.restore()

        # drawing hand
        painter.setPen(
            QPen(QGradient(QGradient.Preset.AmyCrisp), round(self.width() * 0.003), cap=Qt.PenCapStyle.RoundCap,
                 join=Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QBrush(QGradient(QGradient.Preset.AmyCrisp)))
        hand_polygon = (center + QPoint(0, round(self.height() * 0.0045)),
                        center + QPoint(0, -round(self.height() * 0.0045)),
                        center + QPoint(round(self.height() * 0.22), 0))
        painter.save()
        painter.translate(center.x(), center.y())
        painter.rotate(-self.rpm_arc_angle(self.rpm))
        painter.translate(-center.x(), -center.y())
        painter.drawPolygon(hand_polygon)
        painter.restore()

        # drawing center point
        painter.setPen(QPen(QColorConstants.Svg.lemonchiffon, round(self.width() * 0.02), cap=Qt.PenCapStyle.RoundCap))
        painter.drawPoint(center)

        # drawing outer dial
        painter.setPen(QPen(QColorConstants.Svg.lemonchiffon, self.width() * 0.005))
        self.draw_rpm_arc(painter, rpm_bounding_rect, 0, self.max_rpm)

        # once again drawing outer dial of speedometer to hide overlap
        painter.setPen(QPen(QGradient(QGradient.Preset.CrystalRiver), self.width() * 0.005))
        painter.drawArc(self.speedometer_bounding_rect.toRect(), -60 * 16, 300 * 16)

        # drawing rpm value in word
        painter.setPen(QPen(QGradient(QGradient.Preset.CrystalRiver), self.width() * 0.005))
        rpm_font = QFont("Consolas", 0, 0, True)
        rpm_font.setPixelSize(round(self.width() * 0.035))
        rpm_fm = QFontMetrics(rpm_font)
        rpm_value_rect = rpm_fm.boundingRect("0000")
        painter.setFont(rpm_font)
        rpm_value_rect.moveCenter(center)
        rpm_value_rect.moveBottom(rpm_bounding_rect.bottom())
        rpm_value_rect.moveLeft(round(rpm_bounding_rect.x() + rpm_bounding_rect.width() * 0.23))
        painter.drawText(rpm_value_rect, Qt.AlignmentFlag.AlignCenter, str(self.get_rpm()))
        rpm_word_rect = rpm_fm.boundingRect("RPM")
        painter.setFont(rpm_font)
        rpm_word_rect.moveCenter(center)
        rpm_word_rect.moveBottom(rpm_bounding_rect.bottom() - rpm_value_rect.height())
        rpm_word_rect.moveLeft(round(rpm_bounding_rect.x() + rpm_bounding_rect.width() * 0.27))
        painter.drawText(rpm_word_rect, Qt.AlignmentFlag.AlignCenter, "RPM")

    def speedometer_animation(self, val):
        self.speed = val
        self.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(_RENDER_HINTS, True)

        linearGradient = QLinearGradient(self.rect().topLeft(), self.rect().bottomRight())
        linearGradient.setColorAt(0.2, QColor(0, 0, 0))
        linearGradient.setColorAt(0.7, QColor(16, 0, 0))
        linearGradient.setColorAt(0.5, QColor(56, 0, 0))

        painter.setBrush(linearGradient)
        painter.drawRect(self.rect())

        self.speedometer_painting(painter)
        self.tachometer_painting(painter)


class _DashBoardControls(QObject):
    """WARNING: This is a private class. do not import this."""
    set_speedometer_range_sig = pyqtSignal(int)
    accelerator_sig = pyqtSignal(int)
    set_current_speed_signal = pyqtSignal(int)
    set_speedometer_resetter_sig = pyqtSignal(int)
    break_sig = pyqtSignal(int)

    set_rpm_signal = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        global _dash_board

        self.required_values()

        if _dash_board is not None:
            self.dash_board = _dash_board
            self.startup_values_setter()
            if __name__ == "__main__":  # for install default key event if dashboard called in main thread
                self.dash_board.installEventFilter(self.dash_board)
            self.all_connector()

    def required_values(self):
        # default keys to prevent error
        self.keys_ = {Qt.Key.Key_W: False, Qt.Key.Key_H: False, Qt.Key.Key_Left: False,
                      Qt.Key.Key_Right: False, Qt.Key.Key_Space: False, Qt.Key.Key_Escape: False}
        self.dashboard_height = 720
        self.dashboard_width = 1280
        self.speedometer_topspeed = 200
        self.rpm = 0

    def startup_values_setter(self):
        self.keys_ = self.dash_board.keys_  # orginal keys
        self.dash_board.dash_board_design_widget.set_speedometer_range(self.speedometer_topspeed)
        self.dash_board.dash_board_design_widget.set_rpm(self.rpm)

    def launch_dashboard(self):
        app = QApplication(sys.argv)
        self.dash_board = _DashBoardMain(None, (self.dashboard_width, self.dashboard_height))
        self.startup_values_setter()
        if __name__ == "__main__":  # for install default key event if dashboard called in main thread
            self.dash_board.installEventFilter(self.dash_board)
        self.all_connector()
        self.dash_board.show()
        app.exec()

    def all_connector(self):
        self.set_speedometer_range_sig.connect(self.dash_board.dash_board_design_widget.set_speedometer_range)
        self.set_current_speed_signal.connect(self.dash_board.dash_board_design_widget.set_speed)
        self.set_speedometer_resetter_sig.connect(
            self.dash_board.dash_board_design_widget.set_speedometer_resetter_state)
        self.break_sig.connect(self.dash_board.dash_board_design_widget.set_break_state)
        self.set_rpm_signal.connect(self.dash_board.dash_board_design_widget.set_rpm)

    def set_dashboard_size(self, width, height):
        self.dashboard_height = height
        self.dashboard_width = width

    def set_speedometer_range(self, top_speed):
        self.speedometer_topspeed = top_speed
        self.set_speedometer_range_sig.emit(top_speed)

    def set_rpm(self, current_rpm):
        self.rpm = current_rpm
        self.set_rpm_signal.emit(current_rpm)


class DashBoard(QWidget):
    """This is a pyqt widget class to embed this dashboard to other pyqt widgets"""

    def __init__(self, parent=None):
        super(DashBoard, self).__init__(parent)

        self.vlayout = QVBoxLayout()
        self.setLayout(self.vlayout)

    def show_dashboard(self):
        """This method is to show the dashboard in your window"""
        global _dash_board

        self.dash_board_widget = _DashBoardMain(self, (self.width(), self.height()))
        self.dash_board_widget.move(0, 0)
        self.vlayout.addWidget(self.dash_board_widget)

        _dash_board = self.dash_board_widget


class TriggerAction():
    """This class contain all functionality settings of dashboard \
        including lunch_dashboard() method to show dashboard as seperate window"""

    def __init__(self):
        self.__dbc = _DashBoardControls()

    def launch_dashboard(self):
        """Open dashboard window"""
        self.__dbc.launch_dashboard()

    def set_dashboard_size(self, width: int, height: int):
        """Size should be aspect ratio of width:height = 16:9 \n note: this method should \
            be called before you call launch_dashboard() method to take effect"""
        if height is not None and width is not None:
            self.__dbc.set_dashboard_size(width, height)

    def set_speedometer_range(self, top_speed: int):
        """Set speedometer range (i.e.) 0 to top speed \n
        Note: given value should be between 40 to 400 and the given value \
        will internally converted to nearest multiple of 20"""
        self.__dbc.set_speedometer_range(top_speed)

# main
if __name__ == "__main__":
    ta = TriggerAction()
    ta.launch_dashboard()
