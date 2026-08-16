# E-011 — C4 versus C3 integrated vertical slice

## Scope

Five shared-corpus plans were implemented in both representations:

- Q001 additive metric level
- Q004 ratio-of-sums level
- Q006 period delta
- Q011 grouped contribution plus maximum absolute selection
- Q050 typed guard plus result-driven conditional drilldown

Both candidates used the same two semantic metric contracts, six executable
operator contracts, SQLite data compiler, runtime budget, normalized result
envelopes, provenance, and source snapshot.

## Result parity

Both encodings produced identical results and execution records for all five
plans. Verified values included sales level 420, loss ratio 100/400 = 0.25,
sales delta +20, offline contribution +60, and an offline category drill of
electronics 140 and food 120.

Budget exhaustion was a typed failure result. Invalid reference type and
unregistered metric dimension were rejected before SQL. C3 and C4 emitted the
same precise port/type errors after C3 lowering.

## Measured comparison

| Measure | C4 generic Call | C3 explicit nodes |
|---|---:|---:|
| Core node classes | 1 | 6 |
| Authoring serialization, five plans | 2,306 bytes | 1,768 bytes |
| Runtime serialization after lowering | 2,306 bytes | 2,306 bytes |
| Node-class lowering dispatch cases | 0 | 6 |
| Operator contracts | 6 shared | 6 shared |
| Semantic contracts | 2 shared | 2 shared |
| Result/trace parity | 5/5 | 5/5 |
| Materially better tested type errors | 0 | 0 |

C3 source plans are about 23% shorter than C4 source plans. C4 is about 30%
larger than C3 at authoring serialization. That advantage disappears at the
runtime boundary because C3 compiles to the same Call representation.

## Qualitative comparison

### C4 strengths

- one stable wire/runtime grammar;
- adding an operator adds a registry entry, not an IR class and compiler case;
- plans are naturally serializable, replayable, and language-neutral;
- type/law complexity stays in one executable operator registry.

### C4 costs

- raw plans are more verbose;
- hand-authored generic maps have weaker IDE completion;
- cross-port semantic validators must be first-class registry contracts or
  complexity will become hidden runtime logic.

### C3 strengths

- concise Python authoring and discoverable constructors;
- node-specific documentation and IDE completion;
- potentially clearer public SDK ergonomics.

### C3 costs

- every operator shape creates or maintains a node class and lowering case;
- runtime still needs the generic representation for persistence/replay;
- tested static errors were not better because semantic/operator laws remain in
  the shared registry.

## Decision

C4 wins as canonical wire and runtime IR. C3 should not be a second logical
architecture. If developer ergonomics require it, generate typed C3-style
builders from the executable registry and immediately lower them to C4. This
keeps one source of truth while retaining IDE assistance.

No production route was changed in E-011.

