
# Termosmart

> **Learning project** exploring how Python, exercise physiology and data science can be combined to study heat stress during endurance exercise.

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Status](https://img.shields.io/badge/status-learning-orange)
![License](https://img.shields.io/badge/license-MIT-green)

## About

I'm a Sport and Exercise Science (CAFYD) student and recently started learning Python. Instead of practicing with small exercises, I wanted to build something related to a topic I know well as an athlete.

Termosmart is the result.

It is **not a medical device**, **not clinically validated**, and **not intended to diagnose or prevent heat illness**. It is simply a personal learning project that helped me practice software design, data processing, APIs, testing and scientific thinking.

---

## Project idea

The project explores whether combining several signals may provide a more informative estimation than relying only on wrist temperature.

Current prototype combines:

- Environmental heat stress (WBGT approximation).
- Simplified internal heat production model.
- Cardiovascular drift detection.
- Wrist temperature as a secondary confirmation signal.

A rule-based engine combines these variables and classifies the situation into GREEN, YELLOW or RED.

---

## Project architecture

```text
Open-Meteo API
        │
        ▼
 Environmental variables
        │
        ├──────────────► WBGT estimation
        │
 Athlete inputs
(weight, speed, slope)
        │
        ▼
 Core temperature estimator
        │
Heart rate ───────────────► Cardiovascular drift detector
        │
 Wrist temperature
        │
        ▼
 Risk evaluation engine
        │
        ▼
 Alert hysteresis
        │
        ▼
 Dashboard + Alerts
```

## Main components

### Weather provider

`ProveedorMeteo`

Downloads temperature, humidity, wind speed, solar radiation and elevation from Open-Meteo. If the request fails, fallback values are used so the simulation can continue.

### WBGT estimation

Environmental stress is estimated from temperature, humidity, radiation and wind using a simplified WBGT approximation.

### Core temperature estimator

A simplified thermal balance model estimates changes in core temperature from:

- body mass
- running speed
- slope
- estimated metabolic heat
- environmental heat dissipation

This is **not** a physiological simulator. It is only an educational approximation.

### Cardiovascular drift detector

Instead of looking at a single heart-rate value, the algorithm checks whether heart rate keeps increasing while workload remains stable.

A sliding time window and linear trend are used to detect this behaviour.

### Decision engine

The algorithm combines every signal through simple logical rules and assigns one of three states:

- Green
- Yellow
- Red

### Alert hysteresis

Repeated confirmations are required before changing the visible alert level.

This prevents alert flickering caused by noisy sensor readings.

---

## Simulation

The repository contains a simulated running session.

During execution the project:

- downloads weather data
- estimates WBGT
- simulates core temperature
- evaluates cardiovascular drift
- generates alerts
- creates a Matplotlib dashboard

Example output:

```text
Minute 20 | HR 150 bpm | Core 38.1°C | GREEN
Minute 35 | HR 172 bpm | Core 38.6°C | YELLOW
Minute 40 | HR 180 bpm | Core 38.9°C | RED
```

---

## Tests

The project includes unit tests covering:

- invalid inputs
- humidity validation
- physiological consistency
- cardiovascular drift
- risk evaluation
- hysteresis behaviour

---

## What I learned

This project helped me practice much more than Python.

I learned about:

- project structure
- object-oriented programming
- consuming REST APIs
- scientific programming
- simulation
- unit testing
- data visualization
- documenting assumptions and limitations

Probably the biggest lesson was understanding that building models is often more about making reasonable assumptions than finding perfect equations.

---

## Limitations

This repository should be understood as a learning exercise.

Current limitations include:

- simplified physiological equations
- no calibration with experimental data
- no validation against measured core temperature
- simulated sessions only
- offline execution
- not intended for medical decisions

---

## Future work

Ideas I'd like to explore in the future:

- Real wearable integration
- Bluetooth sensors
- Real-time streaming
- Edge computing
- Machine learning models
- Validation using public datasets

---

## Technologies

- Python
- requests
- matplotlib
- unittest
- Open-Meteo API

---

## Repository structure

```text
src/
    Main source code

tests/
    Unit tests

examples/
    Simulation scripts

images/
    Dashboard screenshots
```

---

## Feedback

I'm still at the beginning of my journey in programming and health technology.

If you have suggestions, notice mistakes or think something could be improved, I'd genuinely appreciate your feedback.
