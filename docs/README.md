# CarDash

Reads live data from car.

## Setup

### Enable Desktop Boot

On the Pi:

```bash
sudo raspi-config
```

Choose:

```text
System Options -> Boot / Auto Login -> Desktop Autologin
```

### Create Autostart File

#### Install on Raspberry Pi

```bash
git clone https://github.com/lumigj/CarDash.git
cd CarDash
sudo apt install python3-pyqt5
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements-rpi.txt
```


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

The app starts in live OBD mode by default. If no port is given, it tries:

- `/dev/ttyUSB0`
- `/dev/ttyUSB1`

If neither port connects, the UI stays open, shows a retry countdown, and retries every 10 seconds.

If `--port` is given, it retries only that port.