# OBD Logger

Install on the Pi:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-rpi.txt
```

Run:

```bash
python scripts/obd_logger.py --port /dev/ttyUSB0
```

Output:

- `logs/obd_log.csv`
