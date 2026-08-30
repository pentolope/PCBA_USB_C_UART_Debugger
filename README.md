# USB-C UART Debug Adapter

USB-C to 3.3 V UART debug adapter: bus-powered USB 2.0 Full-Speed device breaking out TX/RX/GND/3V3 and optional RTS/CTS.

This repository holds the design problem for a **USB-C to 3.3 V UART debug adapter**. The brief fixes the function and the interface contract: a bus-powered USB 2.0 Full-Speed device with a correct USB-C device-side CC network, USB ESD protection close to the connector, local decoupling, and a target-side header carrying TX, RX, GND, a 3V3 reference and optional RTS/CTS on a 0.1-inch or compact locking header. It also fixes process intent: pick a commonly available USB-UART bridge, prefer two layers, route D+/D- as a deliberate differential pair, and document whatever impedance approximation is used. The brief's own modality is carried across unchanged: RTS/CTS is offered as an option, two layers is a preference, and the benchmark-intent clauses say what the repository *should* do rather than what it must.

Everything else is the design agent's to decide. The brief names no bridge IC, no connector part, no ESD device, no board outline, no stackup numbers and no impedance target — those belong in `open_decisions`, not in this README. Where a choice is made during design it must be made and justified against cited evidence, not back-filled into the brief as if the user had asked for it.

> **This board has not been designed.** There is no schematic, no layout and no
> part selection here — only the brief, a reading of the brief, and the
> scaffolding a design run needs. That is the intended state of this repository,
> not a gap in it.

## What the brief fixes, and what it leaves open

The brief pins down 16 requirements and deliberately leaves
17 decisions to whoever designs the board. The `Source` column says
which is which: `brief` is quoted from [BRIEF.md](BRIEF.md), `metadata` comes
from the benchmark catalogue, and `open` means the brief does not fix it.

| Aspect | Value | Source |
|---|---|---|
| Product function | USB-C to 3.3 V UART debug adapter | brief |
| UART signalling level | 3.3 V | brief |
| USB interface class | USB 2.0 Full-Speed device | brief |
| Power source | Bus-powered (no separate supply input stated) | brief |
| Target-side signal set | TX, RX, GND, 3V3 reference, plus RTS/CTS as an option | brief |
| Target-side header style | 0.1-inch header or a compact locking header (the brief permits either; which one is not fixed) | brief |
| USB-C CC network | Correct device-side CC network required; no topology, value or tolerance stated | brief |
| ESD protection | USB ESD protection, placed close to the connector | brief |
| Decoupling | Local decoupling required | brief |
| Connector placement | USB and target-side connectors clearly separated | brief |
| USB-UART bridge | A commonly available bridge; no specific part named by the brief | brief |
| D+/D- routing | Deliberate differential pair; any impedance approximation must be documented | brief |
| Likely layer count | 2 (stated as a preference, not a mandate) | metadata |
| Primary stressors | USB 2.0 differential routing, ESD, USB-C CC resistors, small QFN | metadata |
| Board outline, size and mounting | Not fixed by the brief — design agent's choice | open |

The full split, with the verbatim brief text substantiating every fixed
requirement, is in [board/requirements.md](board/requirements.md) and
machine-readably in [board/requirements.json](board/requirements.json).

**Missing details are design freedom, not permission to fabricate unstated user
requirements.** A choice the brief left open is recorded as a decision, with its
reasoning — never promoted into a requirement.

## Benchmark position

| | |
|---|---|
| Benchmark id | 5 of 32 |
| Category | high-speed-lite |
| Difficulty | 2 / 5 |
| Brief detail | 3 / 5 |
| Likely layer count | 2 |
| Primary stressors | USB 2.0 differential routing, ESD, USB-C CC resistors, small QFN |

Board 05 sits in the `high-speed-lite` category at difficulty 2/5 with brief detail 3/5: an adapter of modest scope whose difficulty concentrates in doing four specific things correctly at once — USB 2.0 differential routing, ESD, the USB-C CC resistors, and a small QFN. The brief is deliberately mid-detail: it pins down the interface contract (speed class, power source, signal set, header style, protection placement) while naming no part, no dimension and no impedance number. The interesting test is the "Prefer two layers, but route D+/D- as a deliberate differential pair and document any impedance approximation" clause — it invites a controlled-impedance claim on a stackup that may not be able to guarantee one, and rewards an agent that documents the approximation honestly rather than asserting a number.

This repository is one of thirty-two. The suite, the protocol and the results
live in [PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench).

## Repository layout

| Path | Contents |
|---|---|
| `BRIEF.md` | the supplied brief — authoritative, preserved byte for byte, never edited |
| `board/requirements.md` | what the brief fixes, what it leaves open, and where decisions get recorded |
| `board/requirements.json` | the same split, machine-readable, each fixed requirement bound to brief text |
| `board/manifest.template.json` | the toolkit's minimum manifest, pre-filled for this board |
| `board/toolchain.json` | where this board's build finds KiCad and the router |
| `benchmark/metadata.json` | the supplied catalogue entry — category, difficulty, detail, stressors |
| `docs/architecture.md` | the decisions this board must make, as questions, unanswered |
| `docs/sources.md` | the classes of evidence the design will have to cite |
| `docs/status.md` | what exists, what does not, and what is deliberately absent |
| `candidates/` | disposable search output, ignored by Git |
| `tooling/PCBA_AutoDesignAndTest` | the shared verification/routing/release toolkit, as a pinned submodule |

## Getting the repository

The toolkit is a submodule and carries KiCad Routing Tools as a submodule of its
own, so clone recursively:

```bash
git clone --recursive https://github.com/pentolope/PCBA_USB_C_UART_Debugger.git
```

```bash
git submodule update --init --recursive
```

## Designing the board

Generic verification, routing and release logic is **not** written here. It is
consumed from `tooling/PCBA_AutoDesignAndTest`, which is board-agnostic by
construction and must stay that way; this repository owns the board and nothing
else. Start from
[the toolkit's onboarding guide](tooling/PCBA_AutoDesignAndTest/examples/onboarding.md),
and see [CLAUDE.md](CLAUDE.md) for the rules a design run works under.

```bash
python3 tooling/PCBA_AutoDesignAndTest/run.py preflight
```

## Brief integrity

`BRIEF.md` SHA-256 `0c5897542317b8fdc90d1251febe01efa33c86589f59024910c426d053b9a461`

Every quotation in `board/requirements.json` is bound to those exact bytes. If
the brief ever changes, the bindings are stale by construction — which is the
point of recording the digest.
