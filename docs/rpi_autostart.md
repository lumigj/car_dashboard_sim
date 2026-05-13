# Raspberry Pi Autostart

Use this for the HDMI screen production setup.

## Before Autostart

The app starts in live OBD mode by default. If no port is given, it tries:

- `/dev/ttyUSB0`
- `/dev/ttyUSB1`

Optional fullscreen:

```python
window.showFullScreen()
```

instead of:

```python
window.show()
```

## Enable Desktop Boot

On the Pi:

```bash
sudo raspi-config
```

Choose:

```text
System Options -> Boot / Auto Login -> Desktop Autologin
```

## Create Autostart File

```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/car-dashboard.desktop
```

Put this in the file:

```ini
[Desktop Entry]
Type=Application
Name=Car Dashboard
Exec=/home/lumi/CarDash/.venv/bin/python /home/lumi/CarDash/scripts/obd_interface.py
WorkingDirectory=/home/lumi/CarDash
Terminal=false
X-GNOME-Autostart-enabled=true
```

## To run without the car attached:

```bash
.venv/bin/python scripts/obd_interface.py --mock
```
