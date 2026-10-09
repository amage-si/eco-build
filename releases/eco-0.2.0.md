# AMAGE Eco 0.2.0 (2026-10-09): motion

Eco gains animation: smooth on a 120 Hz screen, cheap (only the moving
control is redrawn), and back to 0 frames and 0 main-thread wakeups as soon
as nothing moves.

| Library | Tag | Commit |
|---|---|---|
| [Ankra](https://github.com/amage-si/ankra/tree/v0.2.0) | v0.2.0 | `f0c7e7fc4047` |
| [Voltra](https://github.com/amage-si/voltra/tree/v0.1.2) | v0.1.2 | `8900b07e14b8` |
| [Chromi](https://github.com/amage-si/chromi/tree/v0.2.0) | v0.2.0 | `70555a40a809` |
| [Runika](https://github.com/amage-si/runika/tree/v0.1.0) | v0.1.0 | `603597c9de38` |
| [Syllo](https://github.com/amage-si/syllo/tree/v0.1.0) | v0.1.0 | `c7298874764f` |
| [Dithra](https://github.com/amage-si/dithra/tree/v0.1.0) | v0.1.0 | `e8db3d044d98` |
| [Tessra](https://github.com/amage-si/tessra/tree/v0.1.0) | v0.1.0 | `bd3a632966f1` |
| [Kairo](https://github.com/amage-si/kairo/tree/v0.1.0) | v0.1.0 | `6dec79c70883` |
| [Mokko](https://github.com/amage-si/mokko/tree/v0.2.0) | v0.2.0 | `705e9987ed01` |
| [Ocula](https://github.com/amage-si/ocula/tree/v0.1.0) | v0.1.0 | `c9f44b1bad7d` |
| [Splina](https://github.com/amage-si/splina/tree/v0.1.0) | v0.1.0 | `e3a5d394263f` |
| [Auvia](https://github.com/amage-si/auvia/tree/v0.1.1) | v0.1.1 | `ba48b71d8f25` |
| [Kinera](https://github.com/amage-si/kinera/tree/v0.1.0) (new) | v0.1.0 | `8d695e8724be` |

Toolchain: Bend 2.0.36 (official), Linux, X11/XWayland, Vulkan.

## What is new

- **Kinera 0.1.0** (new library) is pure motion math:
  - CSS easings and `cubic-bezier`;
  - springs evaluated in closed form, in any regime, so they are frame-rate
    independent;
  - motion values that retarget from their current value and velocity;
  - an energy-based settle test and reduce-motion;
  - 4–30 ns per value.
- **Ankra 0.2.0** adds an animation mode to the loop:
  - one frame per refresh, on a grid of the monitor's period;
  - `frame_time` and `refresh`, with the monitor's rate read through RandR.
  `Win` gained fields and `Loop.next` became `updated`/`drew`.
- **Chromi 0.2.0** adds:
  - colour interpolation in OKLab, linear light and sRGB (`mix.bend`);
  - partial frames with no damage are no longer presented;
  - an animated integrated demo.
- **Mokko 0.2.0** animates its controls (`anim.bend`):
  - the button's hover and press colours fade in OKLab;
  - the press sinks;
  - focus rings grow in;
  - the field border fades;
  - the caret blinks with a fade and stops after ten cycles.
  Springs rest as soon as no byte of what they draw can change.
- **Voltra 0.1.2:** a motion example and pacing measurements; no API change.

## Tested together

- **Test suites:** all 23 `./eco test` targets pass, among them Ankra 75,
  Chromi 82, Kinera 52, Mokko 14 + 5 + 26 + 24 anim, Kairo 56/46/11/27 and
  Auvia 121. The reference frames are byte-identical to 0.1.x at rest.
- **Demo in a real window:** the window was not focused and was driven by
  events sent to it only.
  - A hover takes 24 frames, 20 of them presented. The interval is 8 ms
    p50 and 10 ms p99, with 0 dropped frames out of 520.
  - About 0.6 ms of main-thread CPU per frame.
  - Each frame damages the button only (3,510 px).
  - It returns to 0 frames and 0 wakeups after every motion and after the
    caret stops blinking.
  - The AT-SPI probe passes.
