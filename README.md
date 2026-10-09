# eco-build

Fast builds of [AMAGE Eco](https://github.com/amage-si) programs (our UI
toolkit in Bend 2): one command per target, with the official `bend`.
A demo build takes about 40 s instead of 84 s, almost all of it bend's
C emission (38 s). The units are compiled in parallel and cached, so the
memory peak stays under 2 GiB instead of 4.6 GiB, and the binary is as
fast as the release build. The upstream patches in review
(bendlang/bend#1386, #1387) cut the C emission about 2.5x; the opt-in
fork (`--fork`, below) previews them at about 15 s.

```sh
./eco build demo            # dev build of Chromi/examples/eco/main.bend (official bend)
./eco test chromi-tests     # build and run a suite
./eco build demo --release  # what `bend main.bend -o eco` produces
./eco targets               # the targets in targets.toml
```

`eco` lives beside the libraries (`amage-eco/build/`); targets name a
library directory, a source and an output, so `./eco build demo` writes
`Chromi/build/eco`, the path the Chromi README runs.

## Where the time and the memory went

Bend 2.0.35 builds a native program in three steps, all inside one
`bend file.bend -o bin`:

| Step | AMAGE Eco demo | What it is |
|---|---|---|
| parse, imports, check | ~1 s, 0.4 GiB | `book_read`: fast |
| emit C | ~19 s, grows to 3+ GiB | `compile_book` in `comp.ts`: the whole program re-emitted until a fixpoint, 8 passes |
| clang | ~61 s, 1.5 GiB | one 7.9 MB C file, one unit, `-O3`, one core; while bend's 3 GiB heap stays resident |

Two facts drive the clang cost. The generated C is one translation unit,
so 8 cores sit idle. And every segment function (2,572 in the demo) has the
same signature, as wide as the widest value in the whole program: the
demo's 122-word UI model and Ankra's loop state made every segment take
206 parameters (`WL_SIG`) and every return save 122 words (`WL_RESW`).

## What eco does

1. **Emit C apart from clang.** `bend src -o out.c` exits before clang
   starts, so bend's heap is gone when clang runs. bend runs with
   `BUN_JSC_forceRAMSize` (default 2.4 GiB of "RAM" for JavaScriptCore's
   heap sizing): the same C, the peak drops from ~3 GiB to ~1.2–1.3 GiB,
   about 2 s slower with the official binary. It steers the collector; it
   is not a hard limit (one official build of the demo peaked at 2.2 GiB).
2. **Split the C into units** (`ecobuild/csplit.py`). On the host every
   segment is already its own function, entered by `musttail`; unit 0
   gets the runtime (its globals defined once), the static image, the
   effects and `main`; the other units get the shared head (globals
   `extern`), the spins they reach (static inline) and a share of the
   segments, by a hash of their def's name. Segment functions get hidden
   external linkage. Programs with GPU calls are built as one unit.
   With stable names (the default for dev builds), an edit stays in the
   units that hold the edited code. bend numbers segments across the
   whole program (`def$k<count>`), spins in emission order and FIDs by
   position, so adding one segment anywhere used to change every unit.
   The splitter renames a def's continuation segments by their order
   inside the def, names spins by a hash of their text (their locals
   renumbered), and takes FID numbers out of the units: each unit declares
   the FIDs it uses as link-time constants (`extern eco_FID_x`, numbers
   given to the linker with `--defsym`, linked without PIE so they end up
   as immediates), and `FID_T`, `wl_tab` and the static image live in a
   small tables unit. Constructor ids, static offsets and match tables
   are still positional: an edit that adds a constructor or changes
   static data (a string) rebuilds more units.
3. **Compile the units in parallel with a cache.** Objects are cached in
   `~/.cache/eco-build/objs` by the unit's text, the flags and the clang
   version, so only the units whose text changed are compiled. At most
   `--mem-budget` MiB (default 1536) of clang processes run at once,
   estimated from each unit's size.
4. **Link** (`-lpthread -lm`, plus X11/ALSA when the C includes them).

Dev builds compile the units at `-O3` (`-O 1` saves ~0.3 s per edit and
paints ~25% slower; `-O 0` is unusable, see below). `--release` builds the
unsplit C in one unit at `-O3`, bend's own command line, so it matches
`bend src -o out`.

### The compiler fork

Every build uses the installed, official `bend` by default: the libraries
must build with it, and improvements to the compiler go upstream as pull
requests. `--fork` uses a local fork of bendlang/bend v2.0.35 instead
(`../bend-fork/src`, not published), through `bun bend2/main.ts`, as a lab
for those patches; no library may depend on it. In its default mode the fork emits the same C
as the official 2.0.35, byte for byte (checked on every runnable upstream
test and on the Eco programs; see `bend-fork/UPSTREAM.md`), three times
faster. Dev builds also set `BEND_FLAT_MAX=32`, which boxes datatypes wider
than 32 words: the C changes (every segment takes 61 parameters instead of
206) and clang's work halves; the Eco suites and the demo's reference
frames give the same output. `--flat-max 0` turns it off.

## Commands

```
eco build <target>... [--release] [--official|--fork] [-O N] [-j N]
                      [--units N] [--no-stable] [--mem-budget MiB]
                      [--heap-cap MiB] [--flat-max N] [--root DIR]
                      [--json FILE]
eco test <target>...   same options; runs the binary with the target's
                       `run` arguments and prints its last lines
eco targets
eco cache [--clean]
```

Every build takes the shared Eco build lock
(`/tmp/amage-eco-bend-build.lock`) and runs at `nice 10`; a wait for the
lock is printed apart from the build's own time. While another session
holds the bench lock (`/tmp/amage-eco-bench.lock`, taken while a running
program is measured), eco compiles one unit at a time instead of in
parallel, so its load does not spoil the measurement.

`--root` builds a copy of the libraries (e.g. a snapshot) instead of the
working trees beside this repo.

## Results

Measured on Ian's laptop (Ryzen 7 5800H, 8 cores / 16 threads, 32 GB),
clang 22.1.8, bend 2.0.35 (Bun 1.4.0) and the fork on Bun 1.4.2; each
row's load average is in `results/`. Wall times include bend's startup.

The AMAGE Eco demo (`Chromi/examples/eco/main.bend`), libraries at fixed
commits (`.work/snap0`), one build per row:

| Demo build | `bend main.bend -o eco` (before) | `eco`, official bend, -O1 | `eco` (fork), -O1 | `eco` (fork), -O3 (default) |
|---|---|---|---|---|
| cold (empty cache) | 83.6 s, 4.6 GiB | 40.6 s, 1.32 GiB | 14.1 s, 1.21 GiB | **14.6 s, 1.23 GiB** |
| no change | 83.6 s | 25.3 s | 9.4 s | — |
| one-line value edit (a Mokko theme color) | 83.6 s | 31.8 s | 11.8 s, 1.26 GiB | **10.6 s, 1.12 GiB** |
| logic edit (a new Mokko def, called) | 83.6 s | 34.1 s | 10.9 s, 1.35 GiB | **10.4 s, 1.26 GiB** |
| release (`--release`: one unit, -O3, official) | 83.6 s, 4.6 GiB | 92.9 s, 1.73 GiB | — | — |

Every edit row recompiled one unit of 18. Without stable names (the
first round, `--no-stable`) the logic edit recompiled all units: 38.9 s
official, 15.6 s with the fork. Where the fork's time goes in an edit:
bend → C 7.5–9 s, split 0.6 s, one unit 1.7–2.1 s, link 0.1 s. The -O3
column ran at a lower load (2) than the -O1 rounds (3.5–5.5).

Test suites (`eco test`; cold cache, then again with no change):

| Suite | `bend tests.bend -o tests` (before) | `eco`, official bend, -O1 | `eco` (fork), -O3 (default) |
|---|---|---|---|
| Runika (51 checks) | 6.6 s, 0.53 GiB | 3.3 s → 1.0 s | 2.9 s → 0.9 s |
| Chromi (60 checks) | 3.8 s, 0.51 GiB | 3.3 s → 1.2 s | 3.2 s → 1.1 s |
| Voltra (71 checks) | 4.2 s, 0.60 GiB | 3.3 s → 1.2 s | 3.1 s → 1.0 s |

Small programs gain less: bend takes ~1 s on them and clang's largest
unit ~2 s. Their C has no record wider than 32 words, so the fork emits
the same C as bend for them and both columns share cached objects. Their
peak rises from 0.5–0.6 GiB to 0.7–0.9 GiB, because the units compile in
parallel (`--mem-budget` bounds it).

On 2026-10-09 the default became the official bend. With the libraries at
AMAGE Eco 0.1.0 the reference frames (900x560, 640x760) were the same bytes
from both compilers. The whole reference run took a median of 144 ms official
against 143 ms with the fork (7 interleaved runs each): the libraries now box
their wide records themselves, so the fork's boxing no longer changes the
runtime. The table below is from 2026-10-07, before that.

Running the result (the demo's CPU reference renderer, `reference 900
560`, five runs each; the frame is the same bytes in every build):

| Build | paint | whole run (decode PNG/SVG/font + paint) |
|---|---|---|
| `--release` (official, one unit, -O3) | 71–76 ms | 312–333 ms |
| fork with `BEND_FLAT_MAX=32`, one unit, -O3 | 70–73 ms | 220–242 ms |
| dev default (fork, flat 32, stable units, -O3) | 71–75 ms | 236–247 ms |
| dev at `-O 1` (fork, flat 32) | 91–102 ms | 246–266 ms |
| dev with the official bend (-O1) | 90–96 ms | 327–344 ms |
| dev at `-O 0` | ~6,000 ms | ~7,200 ms |

Split units at `-O3` run as fast as the single-unit release; `-O1`
paints about 25% slower; `-O0` is unusable (the segments lose
`preserve_none` and pass their 61–206 words through memory). Boxing the wide records makes the whole run ~28%
faster at the same optimization level, which matches the 30–35% the text
session measured for the same width at runtime.

Correctness: `tools/validate.sh` builds the five suites (including the
offscreen GPU ones) and the reference renderer with eco and compares them
with the official build's output (`tools/refs.sh`). Identical at the
measured commits with the default dev build and with `--official`, and
again with the default dev build at the libraries' HEADs of 2026-10-07
00:17 (Chromi 95d6274, Runika 131874b, Syllo 51b948a, Voltra c8baef5; by
then 58, 74 and 76 checks plus 20 and 13 GPU checks).

Peaks are the whole process tree's RSS, sampled every 50 ms. Loads were
3–6 (other sessions were working); raw rows in `results/round1.jsonl`
and `results/round2.jsonl`.

## Layout

```
eco                 the command
ecobuild/cli.py     build driver: compiler, split, parallel cached clang, link
ecobuild/csplit.py  the C splitter
targets.toml        targets
tools/              measurement: treemon (process-tree RSS), locked.sh
                    (under the build lock), par, cpuprof (Bun .cpuprofile
                    summary), ctrace (clang -ftime-trace summary), corpus
                    (fork against bend), validate.sh (suites and frames
                    against the official build), round.sh, round2.sh,
                    runtime.sh, jsc.sh, table.py, sanitize.py
results/            raw measurements (JSON), paths shown as <eco>
```

## License

MIT OR Apache-2.0.
