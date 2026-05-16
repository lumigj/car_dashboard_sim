# Backup Camera Reverse Trigger

This project can detect reverse gear by reading a 12V on/off signal from the car and converting it into a safe Raspberry Pi GPIO input.

The easiest signal sources are:

- Backup light positive wire: 12V when reverse gear is selected.
- Backup camera reverse trigger wire: 12V when reverse gear is selected.

Both are effectively the same for this use case: they provide a 12V signal when the car is in reverse.

Do not connect a car 12V wire directly to a Raspberry Pi GPIO pin. Raspberry Pi GPIO is 3.3V only.

## Recommended Design

Use an optocoupler input circuit. This keeps the car 12V side electrically isolated from the Raspberry Pi GPIO side.

Recommended parts:

- PC817 or EL817 optocoupler
- 2.7k ohm or 3.3k ohm resistor for the 12V input side
- 10k ohm resistor for GPIO pull-up, optional if using Raspberry Pi internal pull-up
- 1N4148 or 1N4007 diode for reverse-polarity protection, recommended
- Small inline fuse, 0.5A or 1A, recommended
- Wires, heat shrink, small perfboard or screw terminal module

You can also buy a ready-made 12V optocoupler input module. If using a module, make sure the output side is powered by 3.3V, not 5V.

## Wiring

Car side:

```text
Reverse 12V signal
        |
      Fuse
        |
      2.7k / 3.3k resistor
        |
   PC817 LED anode
   PC817 LED cathode
        |
     Car ground
```

Optional reverse protection diode across the optocoupler LED:

```text
PC817 LED anode  ----|<|----  PC817 LED cathode
```

Raspberry Pi side:

```text
Raspberry Pi 3.3V
        |
      10k pull-up
        |
GPIO input pin -------- PC817 transistor collector
                        PC817 transistor emitter
                                |
                         Raspberry Pi GND
```

With this circuit:

- Not in reverse: GPIO reads HIGH
- In reverse: GPIO reads LOW

This is an active-low input.

## Raspberry Pi GPIO Example

Example using BCM GPIO 17:

```python
import RPi.GPIO as GPIO

REVERSE_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(REVERSE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

is_reverse = GPIO.input(REVERSE_PIN) == GPIO.LOW
```

If `is_reverse` is `True`, the car is in reverse and the dashboard can switch to backup camera mode.

## Notes

- Car electrical systems are noisy. Do not rely on a simple resistor divider unless you also add protection.
- The optocoupler approach is preferred because it isolates the Raspberry Pi from voltage spikes and ground noise.
- If using a ready-made optocoupler module, confirm the output voltage with a multimeter before connecting to GPIO.
- Raspberry Pi GPIO pins are not 5V tolerant.
- Test the circuit with a multimeter before connecting it to the Raspberry Pi.

## Suggested GPIO Logic

The reverse signal should be treated as a simple boolean state:

```text
GPIO HIGH -> normal dashboard
GPIO LOW  -> reverse camera mode
```

Keep the hardware detection separate from the OBD data loop. Reverse detection should be fast and should not depend on OBD polling.
