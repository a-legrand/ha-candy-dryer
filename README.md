# Candy dryer

Home Assistant integration for **Candy Simply-Fi tumble dryers**, fully local:
it talks to the dryer over your network, without the Candy cloud or account.

It reads the dryer status and can **start any program and stop** a cycle,
which the Simply-Fi app does but other integrations do not for dryers.

Programs are those of the **Candy RO H9A2TE-S** (9 kg heat pump), fetched
once from the Simply-Fi cloud: the 14 programs of the dial, the 24 "extra"
programs of the app (bed linen, duvet, backpacks…) and the durations of its
"timed" programs. Other Simply-Fi dryers share the protocol but may number
their programs differently.

## Installation

1. In HACS, add `https://github.com/a-legrand/ha-candy-dryer` as a custom
   repository of type *Integration*, then install **Candy dryer**.
2. Restart Home Assistant.
3. **Switch the dryer on**, then add the integration and enter its IP address.
   The encryption key is recovered from the dryer's answer: nothing else to
   enter. Give the dryer a fixed IP address in your router.

## Entities

| Entity | Description |
|---|---|
| State | `off`, `idle`, `running`, `paused`, `delayed_start`, `finished`, `error`… |
| Program | Position of the dial: a program, `off` or `remote` (remote control position) |
| Program to start | Program sent by Start / Pause: dial programs, then extra ones |
| Program to start: delayed start | Now, or 1 to 12 h later; back to now after each start |
| Program to start: duration | 70 to 150 min for Synthetics, 70 to 220 min for Whites |
| Program to start: dry level | Iron, hang, store or bone dry for ECO Cotton |
| Phase | `stopped`, `pre_heating`, `drying`, `end` |
| Remaining time | Minutes |
| End time | Estimated end of the running cycle |
| Dry level | `iron`, `hang`, `store`, `bone` |
| Door, Filter to clean, Water tank full | Binary sensors |
| Remote control | Whether the dryer accepts commands |
| Start / Pause | Starts the chosen program, pauses the running cycle or resumes it, like the dryer's play/pause button |
| Stop | Stops the running cycle |

Buttons are available only when the dryer's **remote control is enabled**
(dial on its remote control position) and the command applies: starting needs
the door closed and no cycle running. After a cycle, the dryer ignores remote
starts (it beeps, and still reports remote control enabled) until its dial is
turned away from the remote control position and back: one remote start per
visit. Filter to clean comes on at the end of every cycle. The program to start is ECO Cotton
until another one is chosen.

Entity and program names are translated in English and French.

## A dryer that is off most of the time

When the dryer does not answer, it is considered **switched off**: State
becomes `off`, other entities become unavailable, and it is polled every
60 s with a 5 s timeout. It is polled every 30 s when idle, and every 10 s
during a cycle and for a minute after a command. During a cycle, two missed polls in a row are tolerated so
that a Wi-Fi hiccup does not end it in Home Assistant.

## Protocol

The dryer serves `http://<ip>/http-read.json?encrypted=1` (status) and
`http://<ip>/http-write.json?encrypted=1&data=<hex>` (commands), both
XOR-encrypted with a 16-character key:

- start: `Write=1&Pa=0&Sel=0&PrNm=<position>&StSt=1&RecipeId=NULL`, plus
  `&Time=<5-20>` for a duration (70 to 220 min: the dryer then stops on time
  instead of on its humidity sensor), `&DryLev=<level>` for some extra
  programs, and `&DelMd=1&DelVl=<minutes>` for a delayed start
- stop: `Write=1&StSt=0&DelMd=0&PrNm=<position>`, which also cancels a
  delayed start
- pause / resume: `Write=1&SetPauseDryMgr=1` / `Write=1&SetRestartDryMgr=1`

All of them were tried on a RO H9A2TE-S. The app also offers 30, 45 and
59 min durations (`Rapido`): this dryer ignores them, so they are left out.

An extra program runs a dial program with fixed settings, chosen as the
Simply-Fi app does for this dryer: e.g. bed linen is Whites, bone dry.

The firmware sometimes sends invalid JSON (`"RecipeId":"NULL \"` during a
cycle), so the status is parsed field by field.

A dry level is sent as `&DryLev=<1-4>` with the start, as the app does for
standard programs. Only ECO Cotton offers the choice for now.

Not supported yet: options (`OptMsk`: hybrid 2, best ironing 4, drying
manager 8, anti-crease 16).

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
```
