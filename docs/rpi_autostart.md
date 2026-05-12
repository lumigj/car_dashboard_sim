# Raspberry Pi Autostart

Use this for the HDMI screen production setup.

## Before Autostart

In `scripts/obd_interface.py`, set:

```python
is_mock = False
```

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
Exec=/home/lumi/CarDash/.venv/bin/python /home/lumi/CarDash/scripts/obd_interface.py --port /dev/ttyUSB0
WorkingDirectory=/home/lumi/CarDash
Terminal=false
X-GNOME-Autostart-enabled=true
```

Reboot:

```bash
sudo reboot
```

## VNC Note

VNC can either mirror the HDMI desktop or create a separate virtual desktop.

For this project, use VNC mirror mode. If you open a terminal in VNC and it also appears on the HDMI screen, it is mirrored.

## If The App Does Not Start

Run it manually first:

```bash
cd /home/lumi/CarDash
.venv/bin/python scripts/obd_interface.py --port /dev/ttyUSB0
```

Check that:

- HDMI screen shows the Pi desktop
- ELM327 is `/dev/ttyUSB0`
- `is_mock = False` only after real OBD is ready
- `.venv` has `obd` and `PyQt5` installed
