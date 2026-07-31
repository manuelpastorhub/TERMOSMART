Markdown
<h1 align="center">🌡️ Termosmart</h1>
<p align="center"><strong>A decision-support engine for real-time exertional heat stroke prevention, built for endurance sport wearables.</strong></p>
<p align="center">
<img alt="Status" src="https://img.shields.io/badge/status-research%20prototype-orange">
<img alt="Python" src="https://img.shields.io/badge/python-3.8%2B-blue">
<img alt="License" src="https://img.shields.io/badge/License-MIT-yellow.svg">
<img alt="Tests" src="https://img.shields.io/badge/automated%20tests-passing-success">
</p>

Most sport watches try to prevent heat stroke by watching wrist skin temperature. This project starts from the observation that this is the wrong variable — and tries to build something more defensible instead: an engine that estimates the temperature that actually matters (core temperature), cross-checks it against how the cardiovascular system is behaving, and only alerts when the evidence actually adds up.

This README is deliberately long, because I'd rather show you the reasoning than just the result. If you want the short version: skip to What Termosmart Does and Known Limitations.

<p align="center">
  <img src="termosmart_dashboard.png" alt="Termosmart session dashboard: estimated core temperature and heart rate over time" width="720">
  <br>
  <em>Output from a simulated session (generated via the interactive demo script).</em>
</p>

## Table of Contents
* [The Problem](#the-problem)
* [What Termosmart Does](#what-termosmart-does)
* [The Engineering Journey](#the-engineering-journey)
* [The Simulated Heat-Stroke Case](#the-simulated-heat-stroke-case)
* [Known Limitations](#known-limitations)
* [Roadmap](#roadmap)
* [Tech Stack & How to Run](#tech-stack--how-to-run)
* [Project Structure](#project-structure)
* [References](#references)
* [About This Project](#about-This-project)

---

## The Problem

Wrist-worn optical/thermal sensors measure skin temperature, not core temperature — and core temperature is what actually defines exertional heat stroke, clinically. The two are weakly correlated during exercise: skin temperature is constantly being pushed up and down by vasodilation and sweating, largely independently of what core temperature is doing. A watch that fires its heat alarm off wrist temperature alone will produce false positives (hot day, no real risk) and, more dangerously, false negatives (core rising while the wrist doesn't reflect it).

Termosmart's premise is simple to state and hard to build well: stop trying to measure what you can't measure reliably, and estimate what actually matters instead.

---

## What Termosmart Does

Instead of one unreliable sensor, four independent signals are combined:

| Signal | What it captures | How |
| :--- | :--- | :--- |
| **WBGT (ambient heat stress)** | How hostile the environment is | A Wet-Bulb Globe Temperature approximation (Australian BOM formula), fed by live weather data queried by GPS coordinate, not by city name |
| **Estimated core temperature** | Internal heat balance | Metabolic heat production (from pace + elevation, via the ACSM running economy equation) minus heat dissipation, with negative feedback from the body's own thermoregulatory response |
| **Cardiovascular drift** | Heat strain not explained by effort | A rolling-window trend detector that isolates heart rate rising because of heat, from heart rate rising because of effort (see below — this was the hardest part) |
| **Wrist skin temperature** | Secondary, low-trust confirmation | Only ever escalates an alert that's already been triggered by something else — never fires an alarm on its own |

> **A quick note on terminology**, because it matters here: this is WBGT, not the "Heat Index" most weather apps show you. Heat Index only accounts for air temperature and humidity. WBGT also accounts for solar radiation and wind, which matter enormously to a body generating heat outdoors — it's the metric actually used in sport and occupational heat-safety guidelines, for good reason.

```mermaid
flowchart TD
    GPS[GPS: pace + elevation] --> CORE[Mechanical core temperature estimator]
    COORD[GPS coordinates] --> API[Open-Meteo API] --> WBGT[WBGT ambient stress index]
    WBGT --> CORE
    HR[Heart rate sensor] --> DRIFT[Cardiovascular drift detector]
    WBGT --> DRIFT
    CORE --> ENGINE[Risk decision engine]
    DRIFT --> ENGINE
    WRIST[Wrist skin temperature] -. secondary confirmation only .-> ENGINE
    ENGINE --> HYST[Hysteresis: event / persistent-state filter]
    HYST --> DISPLAY[Watch display: GREEN / YELLOW / RED]
The engine is built so that heat alone, without any internal physiological response, never triggers an alarm — a hot, humid day with a calm heart rate stays green. That was a hard requirement from day one, specifically to avoid punishing well-acclimatized athletes with false alarms.

The Engineering Journey
This project was built iteratively with AI pair-programming assistance — used to accelerate implementation, challenge assumptions, and explore alternatives quickly. What I actually own, and what I think is worth describing here, is the physiological reasoning behind each decision, several of which meant rejecting a more "impressive-sounding" approach in favor of one I could actually defend. A few examples:

The humidity bug
The first version of the WBGT formula used relative humidity (0–100%) directly where the formula actually calls for vapor pressure (a physically different quantity, in hPa, derived from both humidity and air temperature via the Magnus-Tetens equation). The bug silently understated the contribution of humidity to heat stress — precisely the variable that matters most in humid climates. Fixed by computing saturation vapor pressure properly before applying the BOM formula.

A more sophisticated dead end, chosen and then discarded
My first attempt at estimating core temperature used a Kalman-filter-style correction: predict core temperature from workload, then correct it using how far the athlete's heart rate deviated from an "expected heart rate curve" for that effort. This is architecturally similar to published HR-based core temperature models used in military and sports-science research.

I discarded it. That "expected HR curve" needs to be calibrated per athlete, with real field data I don't have. Keeping it would have meant the model looked more sophisticated while actually being less honest — precision it hadn't earned. I replaced it with a purely mechanical estimator (pace + elevation + WBGT only, no heart rate), which is fully traceable to a published equation and doesn't pretend to know anything about an individual athlete it hasn't been calibrated against.

Isolating heat-driven heart rate from effort-driven heart rate
This was the hardest single piece of physiological reasoning in the project, and the one I'm proudest of getting right. Cardiovascular drift — heart rate creeping upward over time at a constant workload, well documented in exercise physiology (Coyle & González-Alonso, 2001) — happens because the body is redirecting cardiac output toward the skin to dissipate heat, on top of the output already going to working muscle.

To detect this without confusing it with normal effort:

Heart rate trend is only evaluated while pace and elevation stay within a stable window — if the athlete is simply running harder, that's not drift, that's effort.

The first ~90 seconds of any stable-load window are explicitly discarded, to exclude the fast sympathetic/adrenaline-driven heart rate spike that happens whenever effort changes, which has nothing to do with heat.

The remaining trend is only counted as heat-related if it's also cross-referenced against an elevated WBGT — heart rate can drift for other reasons (fatigue, dehydration, caffeine), and this system doesn't claim to explain all of them.

Alerts that don't nag
An early hysteresis design treated all three risk levels the same way: as states to be continuously reported. In practice that's wrong for how a watch should behave — nobody wants "you're fine" repeated every few seconds. The current design distinguishes persistent alert states (YELLOW/RED stay visibly active for as long as the risk lasts, without spamming repeated notifications) from a one-time event (returning to safe values fires a single "you may resume normal activity" notification, then goes silent). Escalation requires fewer consecutive confirmations than de-escalation, deliberately — the cost of a false alarm is much lower than the cost of relaxing an alert too early on noisy sensor data.

Getting real weather data without pretending it's something it isn't
Weather comes from Open-Meteo (free, no API key required), queried by exact GPS coordinate rather than city name — specifically to avoid the classic error of using a weather station's conditions when the athlete might be hundreds of meters higher in elevation. That altitude-correction path is not fully wired up yet (see Known Limitations).

A safety bug I found by trying to break my own fallback
When the weather API call fails, the code falls back to fixed default values rather than crashing — reasonable on the surface (you don't want the app to die because you lost signal on a mountain). But I stress-tested this by actually killing the connection: the fallback defaults to mild conditions. That means a connectivity failure on a genuinely dangerous, extremely hot day would silently produce false reassurance — the system staying green precisely when it has the least ability to verify real risk. This is arguably the most important thing this project has taught me: a safety system should fail toward caution, never toward comfort. It's not fixed yet, and I'd rather say that plainly than hide it.

The Simulated Heat-Stroke Case
The current demo script includes a hand-built synthetic session — nine data points shaped like a session log (minute, pace, grade, heart rate, wrist temperature), simulating a runner whose heart rate and wrist temperature climb steadily over 40 minutes under hot, humid conditions.

Running the demo script (python notebooks/termosmart_demo.py) produces this real output:

Plaintext
--- INICIANDO LECTOR DE SESIÓN Y GENERACIÓN DE GRÁFICA ---
WBGT Ambiental calculado: 38.09 ºC
Min 01 | FC: 140 lpm | Core: 37.21ºC -> Estado: VERDE
Min 05 | FC: 145 lpm | Core: 38.048ºC -> Estado: VERDE
Min 10 | FC: 165 lpm | Core: 39.269ºC -> Estado: VERDE
Min 15 | FC: 168 lpm | Core: 40.491ºC -> Estado: VERDE
Min 20 | FC: 150 lpm | Core: 41.539ºC -> Estado: ROJO
Min 25 | FC: 155 lpm | Core: 42.587ºC -> Estado: ROJO
Min 30 | FC: 162 lpm | Core: 43.635ºC -> Estado: ROJO
Min 35 | FC: 172 lpm | Core: 44.683ºC -> Estado: ROJO
Min 40 | FC: 180 lpm | Core: 45.731ºC -> Estado: ROJO

Generando gráfica de rendimiento y estrés térmico...
Gráfica guardada exitosamente como 'termosmart_dashboard.png'
Two things worth pointing out, honestly:

The alert timing is real and correct. The raw risk calculation first crosses the red threshold at minute 15; the hysteresis engine correctly waits for a second consecutive confirming reading before escalating, which lands exactly at minute 20. That's the hysteresis logic working as designed, on a real run, not a cherry-picked example.

The core temperature values after minute 20 are not physiologically meaningful, and I want to be upfront about why: at WBGT ≥ 35°C, the current dissipation model's environmental capacity term hits zero and stays there, removing all negative feedback — so core temperature climbs in a straight line for as long as the session continues, well past values incompatible with life. The direction and timing of the alert are the useful signal here; the exact peak number is a known artifact of unvalidated constants, not a claim about what would really happen to a human body.

Known Limitations
I'd rather list these clearly than have someone else find them first.

Scientific / model limitations
Physical constants are engineering placeholders, not clinically validated coefficients — heat dissipation capacity, cardiovascular drift thresholds, and window durations were chosen to be reasonable, not measured. A real deployment would need to calibrate these against real core temperature data (ingestible capsule or rectal probe) in a controlled study.

The dissipation model has no negative feedback once WBGT ≥ 35°C (see above) — a known, understood, unfixed limitation.

Wrist skin temperature is deliberately underweighted because of its weak correlation with core temperature — this is a design choice, not an oversight, but it does mean the system leans heavily on estimation rather than direct measurement.

Elevation is fetched from Open-Meteo's elevation endpoint but not yet fed back into the temperature correction for the forecast call — Open-Meteo's forecast API does support an elevation parameter that applies altitude correction, and this integration doesn't use it yet.

No real-time device integration (and why)
Termosmart does not pull live sensor data from an actual watch, and I want to be explicit about why, because it's a real architectural boundary, not a detail I glossed over:

Cloud APIs from major wearable platforms (Garmin Connect, Fitbit Web API, Strava) deliver activity data after a workout has finished and synced — not while it's in progress. Garmin's own developer documentation is explicit that activity exports are not real-time; they arrive shortly after the completed activity syncs.

Genuine live, in-workout data requires connecting directly to the device through the manufacturer's on-device SDK (e.g. Garmin's Connect IQ / Health SDK) via a companion mobile app — which typically requires a developer approval process and is a mobile/embedded engineering project in its own right, distinct from the Python decision engine in this repository.

Given that, this project deliberately scopes itself to the decision engine and data pipeline, designed so that swapping in a live data source later wouldn't require touching the core logic — the engine doesn't know or care whether a number came from a live feed, a replayed recording, or a hand-built test case.

Roadmap
[x] Refactor core library logic separate from execution code (src/termosmart.py)

[x] Implement automated test suite (tests/test_termosmart.py)

[x] Create automated demo script with Matplotlib dashboard export (notebooks/termosmart_demo.py)

[ ] Wire the fetched elevation into the WBGT temperature correction

[ ] Rework the dissipation model to behave sensibly at extreme WBGT

[ ] Replace the hand-written synthetic session with real historical data (a .gpx/.fit/.tcx export from a real run), replayed at realistic pacing — genuine recorded data, honestly labeled as replayed rather than live

[ ] Calibration protocol design for the physical constants against real core temperature reference data

Tech Stack & How to Run
Python 3.8+, requests, matplotlib.

Clone the repository and install dependencies:

Bash
pip install -r requirements.txt
Run the automated test suite to verify code integrity:

Bash
python -m unittest tests/test_termosmart.py
Run the simulation demo script (generates console output and saves termosmart_dashboard.png):

Bash
python notebooks/termosmart_demo.py
Project Structure
Plaintext
TERMOSMART/
├── src/
│   └── termosmart.py      # Core library: WBGT, core temperature estimator, 
│                           # drift detector, decision engine, and hysteresis
├── notebooks/
│   └── termosmart_demo.py  # Simulation demo script and Matplotlib dashboard generator
├── tests/
│   └── test_termosmart.py  # Automated unit testing suite
├── docs/
│   └── dashboard.png       # Example reference dashboard output
├── requirements.txt
└── LICENSE                 # MIT
References
Australian Bureau of Meteorology (BOM) WBGT approximation formula.

ACSM running economy equation (metabolic cost of running from pace and grade).

Coyle, E.F. & González-Alonso, J. (2001). Cardiovascular drift during prolonged exercise: new perspectives. Exercise and Sport Sciences Reviews.

Open-Meteo — free weather and elevation API.

About This Project
I'm training toward a career at the intersection of medical AI, wearables, and human performance — currently studying CAFYD (Sport Science) alongside IBM's Data Science certification. Termosmart is my attempt to practice the part of this field I think matters most and gets skipped most often: not writing code that works, but being able to say precisely what it doesn't yet know, and why.

This is a personal research prototype, not a medical device, and does not provide medical advice. It has not been clinically validated and should not be used as the sole basis for exercise safety decisions.
