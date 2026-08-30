# Benchmark entry — board 5 of 32

[metadata.json](metadata.json) is the supplied catalogue entry for this board,
preserved byte for byte from the seed pack. It is the same record that appears
in `boards_index.json` in
[PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench), and the two must agree.

| | |
|---|---|
| Repository | `PCBA_USB_C_UART_Debugger` |
| Board id | `usb_c_uart_debugger` |
| Category | high-speed-lite |
| Difficulty | 2 / 5 |
| Brief detail | 3 / 5 |
| Likely layer count | 2 |
| Primary stressors | USB 2.0 differential routing, ESD, USB-C CC resistors, small QFN |

`difficulty` is how hard the board is. `detail` is how much of it the brief
states — and a low `detail` is not a low bar. A detail-1 brief leaves the
architecture open on purpose, and an agent that fills the silence with invented
user requirements has failed the board more thoroughly than one that designs it
badly.

Board 05 sits in the `high-speed-lite` category at difficulty 2/5 with brief detail 3/5: an adapter of modest scope whose difficulty concentrates in doing four specific things correctly at once — USB 2.0 differential routing, ESD, the USB-C CC resistors, and a small QFN. The brief is deliberately mid-detail: it pins down the interface contract (speed class, power source, signal set, header style, protection placement) while naming no part, no dimension and no impedance number. The interesting test is the "Prefer two layers, but route D+/D- as a deliberate differential pair and document any impedance approximation" clause — it invites a controlled-impedance claim on a stackup that may not be able to guarantee one, and rewards an agent that documents the approximation honestly rather than asserting a number.

## What goes here

Compact results only: metrics, verdicts, and the commit each was measured at.
The evidence for a result is the artefact the toolkit recomputes, not a summary
of it.

Routing search output, candidate pools, build trees and field-solver dumps do
**not** go here. They are ignored by [.gitignore](../.gitignore) and are
regenerated from what is committed. Thirty-two repositories share one benchmark
clone; weight here is paid thirty-two times.

## Protocol

The attempt protocol is defined once, in the umbrella repository, so that
thirty-two boards cannot drift into thirty-two protocols. See
[PCBA_AutoDesignAndTest_Bench/BENCHMARK.md](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench/blob/main/BENCHMARK.md).
