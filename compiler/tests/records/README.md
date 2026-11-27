# Records of checks too long for a gate

A check that takes hours runs on a host, never in a gate, and is recorded
here, one JSON file each (D2874). `scripts/records.py check` emits each
record's program again for each target it claims and says whether the
record is fresh, every checked routine's code what it was at the record's
commit, or stale, naming the routines and targets whose code changed
since. The gate's `compiler-checks` job runs it on every software push. A
stale record fails no push. It blocks a release, and a phase-gate claim,
that cites it, until its commands are run again and stamped.

| record | what it checked |
|---|---|
| `math-f32-exhaustive.json` | every input of `core/math`'s 30 one-argument `f32` routines against MPFR on Linux x86-64, and their 2^32 results compared bit for bit on Linux arm64 and RV64 (D2553, D2874) |

## The form

| field | what it holds |
|---|---|
| `schema` | 1 |
| `title` | the check in a line |
| `check` | what was checked and what the results mean |
| `commands` | the commands, as run from the checkout, that make the results again |
| `host` | the host they ran on: its name, system and processor |
| `date` | the day the runs ended, `YYYY-MM-DD` |
| `commit` | the commit whose code the runs checked, as a full name |
| `program` | the program compiled, from the checkout's root |
| `options` | the `refine compile` options it was compiled with |
| `targets` | each target the record claims |
| `routines` | for each routine checked, by its assembly label: `digests`, the SHA-256 of its code on each target, and any results of its own |

A record may hold further fields of its own, such as each routine's
results. `check` reads only the ones above.

A routine's code is the assembly refine emits for the program, from the
section defining the routine's label through every section reached from
it by naming a label another section defines. The assembler's local names
are renumbered in the order they are first reached, the numbers refine
gives its sections are dropped, and so is a trap message's line and column
with the length the trap's instructions pass for it. Inserting a routine
before it, editing one it does not reach or moving its lines therefore
leaves the digest alone; a change to its instructions, a constant or a
callee's code, inlining included, moves it. Code the assembly does not
hold, a C library's or libgcc's, is not in the digest; a record on a
target that calls it names that in its `check`.

## Making or renewing a record

Run the commands on a host, with `nix develop` and this checkout's
`refine`, then write the results into the record and stamp it with the
same `refine` and tree:

```sh
python3 scripts/records.py stamp compiler/tests/records/NAME.json --commit REV
python3 scripts/records.py check compiler/tests/records/NAME.json
```

`stamp` writes each routine's digest on each target and the commit; the
routines and targets come from the record itself, so a new record is
written first with zero digests. `digest PROGRAM --target T --symbol S`
prints one routine's.
