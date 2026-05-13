## Run

```bash
python scripts/obd_logger.py --port /dev/ttyUSB0
```

Default output:

- `logs/obd_log.csv`

## Logging On/Off

Change this at the top of `scripts/obd_logger.py`:

```python
logging = True
```

- `True`: append CSV rows to `logs/obd_log.csv`
- `False`: print values in the terminal

Change output file here:

```python
log_path = "logs/obd_log.csv"
```

## Interval

Default:

```bash
python scripts/obd_logger.py --port /dev/ttyUSB0 --interval 1
```

The real CSV row interval is not exactly `--interval`.

Actual gap is roughly:

```text
time to query all supported OBD commands + interval sleep
```

On the sample `data.csv`, `--interval 1` produced about `3-4s` gaps because the car reported 18 supported commands and ELM327 queries them one by one.

## Data Scope

The logger records all supported standard live OBD-II mode `01` commands reported by the car.

This is not all possible car data. Manufacturer-specific CAN data needs custom PIDs or a different raw CAN approach.
