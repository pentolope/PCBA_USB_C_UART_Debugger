# Toolkit request from board 05 (USB-C UART debugger)

This is a request list from one board to the toolkit it is validated by. It
was written after taking this board from a brief to a release-ready commit,
and every item below is a wall this board actually hit, quoted where the
toolkit says in its own words what it will not do.

Two rules govern the list:

1. **Nothing here may make the toolkit board-specific.** Each request states
   the general form the facility should take. Where this board is mentioned
   it is as the reporter of a wall, never as the shape of the answer. A
   request that could only be satisfied by knowing about USB, Type-C, or any
   part on this board has been rewritten until it no longer is.
2. **Nothing here asks the toolkit to be less strict.** Every facility
   requested must fail closed, refuse rather than guess, carry its model and
   its validity window in the claim, and be reachable only by an explicit
   manifest declaration. Several of these requests exist *because* the
   toolkit correctly refused, and the fix is a new model, not a relaxed one.

Priority is the order in which these would change what a board can honestly
claim, highest first.

| # | Request | Doc | Blocks today |
|---|---------|-----|--------------|
| 1 | Coupled-line model for differential pairs | §21.2 | An UNKNOWN impedance claim on any pair-carrying board |
| 2 | Reactive interconnect models for post-layout simulation | §21.1, §22 | Half of §22's own question list |
| 3 | Plane and multi-path DC, and PDN quantities | §23 | Any rail with decoupling; every poured net |
| 4 | Verification-method classification | §26 | Not expressible in the claim model |
| 5 | External and manual release dependencies | §25, §30 | Nowhere to record what is verified off-tool |
| 6 | Fabricator facts the catalog does not carry | §7, §25 | Two via gates permanently NOT_APPLICABLE |
| 7 | Component rotation as a toolkit facility | §25 | Per-board duplication; unreviewed CPL angles |
| 8 | Correlated uncertainty in matched groups | §21.1 | Undecidable skew on unavoidable geometry |
| 9 | A defined seam for full-wave extraction | §21.3 | No path from geometry to a solver |

---

## 1. A coupled-line model for differential pairs

### What stopped me

The toolkit refuses, correctly and in full:

```
REFUSED: differential solving is not implemented in this pass: the analytic
infrastructure carries no coupled-line model, and an uncoupled pair presented
as a differential answer would be wrong by construction
```

`pcbqa/transmission_line.py` implements bare microstrip, coated microstrip
and stripline, all single-ended. `run.py fab impedance` already accepts
`--mode differential`, so the interface exists and the model behind it does
not.

The consequence for this board is one claim that cannot be resolved:
`usb_pair_differential_impedance_matches_the_usb_nominal` reports UNKNOWN,
with the omission recorded as *"no coupled-line model is available"*. That is
the honest answer, and it is the only unresolved electrical question on an
otherwise fully evaluated board. Any board carrying a differential interface
will land in the same place.

Two supporting facts, both already inside the toolkit:

- `pcbqa/coupling_geometry.py` measures coupled run length and says of its
  own output: *"geometric proximity for risk ranking only; this is coupled
  run length in mm, not a crosstalk voltage, and no electrical conclusion
  follows until a sourced coupling model consumes it."* Nothing consumes it,
  and no gate reaches it, so a board cannot even obtain the inventory.
- `pcbqa/claim.py` already reserves the phenomena `characteristic_impedance`
  and `coupling` and the scope level `pair`. The vocabulary was designed for
  this; only the producer is missing.

### What I want

A coupled two-conductor model beside the existing single-ended ones, with the
same discipline: a stated form, a stated validity window on the normalised
geometry, and a refusal outside it rather than an extrapolation.

- odd- and even-mode impedance, and differential and common-mode impedance
  derived from them;
- edge-coupled microstrip (bare and mask-coated) and edge-coupled stripline,
  since those are the geometries a two-conductor pair on a fabricated board
  actually takes;
- the same effective-permittivity helpers the delay model uses, so impedance
  and delay can never disagree about the geometry — the single-ended code
  already makes that promise and the coupled code should inherit it;
- consumption of the existing coupled-run-length inventory, so the model is
  applied to the length the board really runs coupled and not to a declared
  ideal.

Second, a **fabricator-report path** for boards that can buy impedance
control. The frozen catalog already carries the fabricator's impedance model
inputs — prepreg and core Dk by thickness, soldermask Dk, the offered
differential range, and `Impedance Tolerance ±10%`. It also records that
controlled impedance is offered only at `4/6/8/10/12/14/16/18/20/.../32
layers`. That last fact is a first-class answer the toolkit should be able to
give: on a two-layer construction no fabricator impedance report can exist,
so a model is the only route to the claim, and a board should learn that from
the toolkit rather than deduce it.

### Interface

- `pcbqa.transmission_line.coupled_microstrip_zdiff(...)` and the stripline
  equivalent, returning odd/even mode plus effective permittivity, refusing
  outside the window.
- `run.py fab impedance --mode differential` stops refusing where the
  construction and geometry are inside the model's window; keeps refusing,
  with the reason, where they are not.
- A gate, opt-in like every other: `SI.PAIR_IMPEDANCE`, driven by a
  `differential` block under an existing `timing.interfaces.<name>` —
  conductor width, edge-to-edge gap, reference layers, target impedance and
  tolerance. It measures the realised geometry off the board, not the
  declared geometry, exactly as the delay gate does.

### How it must refuse

- Outside the validity window of the form: refuse, naming the geometry ratio
  and the window.
- Where the two conductors are not uniformly coupled over the measured run
  (fan-out, launch, via transitions): report the uncoupled portion as an
  explicit omission, in the same shape the delay gate uses for unreferenced
  length, and let the board declare a budget for it.
- Where the reference structure under the pair is interrupted beyond that
  budget: refuse, because an impedance stated over a broken reference
  describes a structure the board does not have.

### Done when

A board can declare a differential interface and receive PASS, FAIL or a
stated refusal — never silence — and the claim carries the model name, the
validity window, and the coupled length it was evaluated over.

---

## 2. Reactive interconnect models for post-layout simulation

### What stopped me

The extracted interconnect model is a resistor. Literally:

```python
"spice": ".subckt {identity} a b\nR1 a b {value}\n.ends"
```

and the geometry baseline says of itself: *"geometry-derived quantities only;
no inductance or capacitance is claimed anywhere in this report."*

§22 lists the questions post-layout simulation exists to answer. With an
R-only model, these are unanswerable on any board: *did via inductance create
ringing?*, *did the decoupling-loop geometry degrade transient behaviour?*,
*did a switching loop become too inductive?*, *did the routed impedance
invalidate the nominal termination?* The rail-drop questions are answerable
and the reactive ones are not, which quietly limits post-layout simulation to
DC.

### What I want

Per-unit-length capacitance and inductance from the same geometry and
stackup the propagation model already uses, and via barrel inductance beside
the via *delay* model that already exists, emitted as a richer subcircuit
under the same alias mechanism that makes extracted models usable from a
stored scenario.

- a distributed or lumped-segment RLC subckt, segment count chosen from the
  path's own electrical length so the model is not finer or coarser than the
  question deserves;
- the R-only model kept and still selectable, because for a pure DC drop it
  is the honest minimum and costs nothing;
- the choice declared by the board, not inferred: a scenario asks for the
  model it wants and the toolkit refuses if it cannot build it.

### How it must refuse

The reactive model must inherit the delay model's reference discipline: if a
portion of the path runs with its reference interrupted beyond the board's
declared budget, refuse rather than emit an inductance computed from a loop
that is not there. This is the same rule that already governs delay, and it
is the reason the delay numbers on this board can be trusted.

### Done when

A board can substitute a routed path into a pre-layout scenario and see a
transient that differs from the ideal one for reasons the model can name.

---

## 3. Plane and multi-path DC, and the power-integrity quantities

### What stopped me

`extract.path_resistance` refuses two situations that are not exceptional —
they are what supply distribution normally looks like:

```
net 'GND' carries filled zone copper; plane current paths are not modelled by
path-scoped DC extraction
```

```
traversal element 32 on net '+3V3' begins and ends in one electrical node;
its series resistance would be fictitious, and the path-scoped model refuses
```

Both refusals are right. Their combined effect on this board is that the
regulator output rail — the one with the decoupling on it — cannot be
measured at all, and neither can any return path, because the return is a
pour. What can be measured is only what happens to be a bridge in the graph.
On this board that left the receptacle-to-regulator run (36.3 mΩ over
21.4 mm, two vias), the switched supply to the target header (24.5 mΩ), and
the series-terminated signal runs. The decoupled rail and the ground return
are invisible.

§23 asks for source-to-load DC resistance, distribution voltage drop,
via/current bottlenecks, plane spreading resistance, decoupling-loop
inductance, plane inductance, local supply impedance, PDN impedance versus
frequency, anti-resonances and transient droop. Today a board can obtain the
first of those only when the copper happens to be a single series chain.

### What I want

1. **A network DC solve.** Where parallel copper exists, return the network
   resistance between the named terminals instead of refusing. Parallel
   copper divides current, which is a solvable fact, not an ambiguity. Keep
   the refusal for the case it was written for — a *series* model asserted
   over a parallel network — by making the network solve a different,
   explicitly requested answer with its own claim shape.
2. **Poured nets included.** A nodal solve over the filled zone polygons,
   with the vias as the connections between layers, giving source-to-load
   resistance including plane spreading. This is the only route to a return
   path number on any board that uses a plane, which is nearly all of them.
3. **Decoupling-loop inductance from geometry.** The claim vocabulary already
   reserves `loop_inductance` and nothing produces it. The loop is
   measurable: pad, via, plane, via, pad, all present in the board file.
4. **Current bottlenecks.** Given a rail and a current, report the narrowest
   cross-section and the via count carrying it, which is a geometry question
   the toolkit can already answer and nobody can currently ask.

### Interface

A `power` block in the manifest, opt-in, listing rails: a source terminal,
load terminals, the current each draws, and the drop each tolerates. Gates
`PDN.DC_DROP` and `PDN.RETURN_PATH`, reporting measured drop against the
declared limit, and the return path's resistance against its own.

### How it must refuse

State the solver, the mesh resolution and the convergence criterion in the
claim. Refuse when the pour is unfilled, when a zone's fill is stale with
respect to the copper, or when a declared terminal is not on the net.

---

## 4. Verification-method classification

### What stopped me

§26 asks that every significant requirement identify the strongest
verification method currently available, from a stated vocabulary. No claim
in this board — or in any board in this bench — carries one. The nearest
thing is `evidence_class`, which is free text and describes the evidence
rather than the method that established it.

The gap matters most where a requirement is *satisfied by argument*. This
board's ESD claims establish that every entering conductor is clamped, which
is a structural fact, not a compliance result. Nothing in the artifact says
that the compliance claim itself requires physical test. §26 explicitly wants
that distinction, and there is nowhere to write it.

### What I want

A closed vocabulary as a first-class claim field — `STATIC`, `GEOMETRY`,
`ANALYTIC`, `CIRCUIT_SIM`, `DIGITAL_SIM`, `EXTRACTED`, `EM_SIM`,
`THERMAL_SIM`, `MANUFACTURING_CHECK`, `PHYSICAL_TEST`, `DOCUMENTATION` — with
a claim able to name more than one, and able to name a method it does *not*
have as the one that would be required to close it.

A gate, `PROV.VERIFICATION_METHOD`, that checks every requirement-bearing
claim names a method, and lets a board declare a minimum method per
significance class, so a board can say that its safety-relevant requirements
may not rest on `DOCUMENTATION` alone.

### How it stays board-agnostic

The vocabulary is fixed by the toolkit; which method a claim carries is the
producer's statement; which minimum a board demands is the board's policy.
Nothing about any particular requirement is encoded in the toolkit.

---

## 5. External and manual release dependencies

### What stopped me

§25 says of steps that cannot be validated locally that they *"should be
recorded as external/manual release dependencies rather than silently
assumed"*, and §26 says the agent should be rewarded for correctly saying
physical validation is still required.

There is nowhere to record either. `release-check` prints RELEASE READY or a
list of failures; a board with an open dependency on a fabricator's assembly
preview, a physical ESD test, or a bench measurement of a quantity no model
can establish has no way to carry that in the artifact. The absence reads as
"nothing is outstanding", which is exactly the silent assumption the document
warns against.

### What I want

An `external_dependencies` block in the manifest, and a gate over it. Each
entry: an id, the statement it would establish, the verification method from
§26's vocabulary, who owns it, its status, the evidence that closes it, and
whether it blocks release. The gate checks the shape and the evidence;
`release-check` prints open dependencies as part of its verdict and refuses
release-ready while a blocking one is open.

Alongside it, §30's policy states — `analysis-only`,
`provisional-layout-allowed`, `fabrication-ready`, `release-ready`,
`requires-human-review`, `blocked` — as an explicit output of validation
rather than something a reader infers from a gate table. A positive result at
one stage should not read as authorisation for the next, and today it does.

---

## 6. Fabricator facts the catalog does not carry

### What stopped me

`fab/selection.json` states its own limits precisely: *"feasible means
feasible against the checked requirements only; the properties under
not_in_vocabulary were NOT inspected and must be judged separately"*, and the
uninspected list includes solder-mask constraints, via covering (tented /
plugged / filled), annular ring, edge-to-copper clearance and assembly
constraints.

The frozen catalog carries soldermask *thickness* — base, on copper, between
traces — but no mask expansion, registration or minimum dam. So
`via_mask.process.limit_mm` cannot be sourced from evidence, and
`VIA.MASK_CLEARANCE_PROCESS` and `VIA.NATIVE_GERBER_AGREEMENT` are
NOT_APPLICABLE on every board in this bench. The gates exist and nothing can
legitimately turn them on.

### What I want

Extend the catalog vocabulary to the properties in that list, under the same
committed-evidence policy the rest of it follows: source, retrieval date,
excerpt, digest. Then expose them, so a board writes

    "via_mask": {"process": {"limit_mm": {"from_catalog": "soldermask_min_dam_mm"}}}

instead of inventing a number or leaving the gate dark. The same applies to
via covering: a board should be able to declare tented, plugged or open and
have the declaration checked against what the fabricator offers, because that
choice changes what the via gates mean.

---

## 7. Component rotation as a toolkit facility

### What stopped me

Rotation correctness is a per-part fact about a fabricator's library, not
about a board, and it is currently implemented per board: an earlier board in
this bench carries its own `tools/jlc_orientation.py` plus per-part frozen
library responses, and derives each offset by pairing library pads against
footprint pads. This board has neither, so its CPL ships KiCad's angles with
nothing behind them — and a wrong rotation on a fine-pitch package is a
scrapped build, not a warning.

Copying a tool between boards is exactly the duplication a board-agnostic
toolkit should absorb. The gate for it, `CPL.ORIENTATION`, is already in the
toolkit; only the means of producing evidence for it is not.

### What I want

A `fab orientation` subcommand: fetch a part's library geometry under the
same network policy that governs `fab refresh` — that is, never during
validation — derive the offset by pad pairing, require every pad to agree,
score the runner-up, and write per-part evidence with a digest. A board then
declares the registry and reviews it; the gate re-derives from the committed
evidence and compares.

The pad-pairing derivation is general: it needs a footprint and a library
geometry, and knows nothing about the part.

---

## 8. Correlated uncertainty in matched groups

### What stopped me

The skew gate treats each member's length uncertainty as independent. Before
I redrew this board's pair, all four of its paths carried exactly 0.9625 mm
of junction ambiguity — identical, because the endpoints are identical — and
the group spread came out as the interval 0 to 1.925 mm against a 0.2 mm
limit. Not a failure: undecidable, by construction, for any matched pair
whose members share their endpoint geometry.

I closed it in the board by ensuring nothing lands part-way along a
conductor, which removed the ambiguity rather than cancelling it. That fix is
not always available: a board whose group members must pass through a pad or
a via mid-run has no route to a decidable skew number, however well matched
the copper is.

### What I want

Either a way for a group to declare that its members' endpoint ambiguity is
shared — checked, not asserted, by comparing the junction identities the
extraction already computes — or a spread calculation that cancels the
ambiguity it can prove is common and reports only the residual. The gate
should still report the ambiguity it cancelled, so the reader can see what
was assumed.

---

## 9. A defined seam for full-wave extraction

§21.3 is right that the hard part is not calling a solver: it is geometry
translation, meshing, ports, references, boundaries and de-embedding. I am
not asking the toolkit to own a solver. I am asking for the seam to be
defined now, so the boundary is a decision rather than an accident.

A documented region export — an electrical path, the copper around it within
a stated distance, the stackup, and port definitions at named terminals —
written in a form a solver can consume and a claim can cite. Whatever
consumes it must refuse release-grade claims when port definition, reference
definition or de-embedding cannot be established, which is what the document
already asks for.

The candidates on a board like this one are the connector launch and the via
transitions — precisely the places the analytic model already declares
outside its validity.

---

## What I am not asking for

- Anything that names a bus, a connector family, a part or a vendor part
  number in toolkit code.
- Any relaxation of a refusal. Where the toolkit refuses today it is right to
  refuse; the request is a model that makes the refusal unnecessary, not a
  switch that suppresses it.
- Any gate that passes by default. Everything above is opt-in by manifest
  declaration and NOT_APPLICABLE until a board declares it, like every gate
  that exists now.
- Any facility that reads the network during validation.

## What this board would do with each

1. Close its differential-impedance claim, or receive a stated refusal that
   names the geometry rather than the missing model.
2. Rerun its hot-plug and edge scenarios over routed copper with reactive
   parasitics, not just resistance.
3. Measure the drop to its regulator across the decoupled rail, and the
   return path through the pour, neither of which it can measure now.
4. Mark its ESD coverage as an argument requiring physical test, in the
   artifact rather than in prose.
5. Record the assembly-preview and physical-test dependencies it currently
   cannot state at all.
6. Turn on the two via gates that are dark for want of a sourced number.
7. Ship a CPL whose angles have been derived and reviewed rather than
   inherited.
8. Keep its skew claim decidable if the pair ever has to pass through
   something mid-run.
9. Point a solver at its receptacle launch when the analytic answer is not
   enough.
