# R20's breaking list

*The input of R20.60, which applies it on `r20-integration` in one promotion. Each of R20.20, R20.30, R20.40 and R20.50 adds its own section; an entry gives the old form, the new one, the decision behind it and whether `refine fix` rewrites it mechanically (D1847). It is not edited once R20.60 is complete.*

## How a capability is received (R20.20)

The library routines and concept entries that depart from how
`core/README.md`'s conventions say a capability is received: by
`type is C` unless the value keeps it (D1948), and in the order subject,
capabilities, inputs, `caller` (D1954), read as D1988 says. The first four
are the departures `check.py`'s library conventions check finds, and its
table `LIBRARY_CONVENTION_DEPARTURES` names them until they are applied.
The last three are departures from the subject rule, which the check cannot
see. Found over every public routine and the 29 concepts of `core`, `hosted`
and `platform` at `065886126`.

| Old form | New form | Decision | `refine fix` |
|---|---|---|---|
| `text.format_onto(store: []mut u8, onto: any outlet, template: utf8, values: []any formattable)` | `text.format_onto(provider: type is outlet, store: []mut u8, onto: provider, template: utf8, values: []any formattable)` | D1948: it hands text to `onto` during the call and keeps nothing | nothing to rewrite: an `any text.outlet` argument passes to the generic unchanged and the type is inferred, so every call stays as it is |
| `stacks.round_over(inout state: round_space, entries: []mut usize, when_idle: any idler)` | `stacks.round_over(inout state: round_space, when_idle: any idler, entries: []mut usize)` | D1954: the capability before the backing; R20.50's section then renames `entries` | mechanical: swap the second and third arguments |
| `fake.network_over_turns(inout state: network_space, sockets: []mut network_socket, runs: any fibre.turns)` | `fake.network_over_turns(inout state: network_space, runs: any fibre.turns, sockets: []mut network_socket)` | D1954: the capability before the backing | mechanical: swap the second and third arguments |
| `io.file_system`'s entry `make_temporary(self: provider, directory: text.host_string, names: any entropy, into: []mut u8)` | `make_temporary(self: provider, names: any entropy, directory: text.host_string, into: []mut u8)` | D1954, as the public `io.make_temporary` already orders it; the entry keeps `any entropy` (D1988) | mechanical: swap the second and third arguments of each call through the entry and of each conformance's parameter list, `hosted/system`'s and `fake.volume`'s among them |
| `mem.transfer(source: storage(item), index: usize, inout target: storage(item))` | `mem.transfer(inout target: storage(item), source: storage(item), index: usize)` | D1954 by D1988: the target is the subject, as `mem.copy` takes `into` first | mechanical: move the third argument first |
| `mem.transfer_prefix(source: storage(item), inout target: storage(item), count: usize)` | `mem.transfer_prefix(inout target: storage(item), source: storage(item), count: usize)` | D1954 by D1988, as for `mem.transfer` | mechanical: swap the first two arguments; but the old order still checks, both being `storage(item)`, so an unrewritten call would copy the wrong way without a refusal: R20.60 refuses the old form by pairing the reorder with a new name or by another means it chooses |
| `random.shuffle(inout source: generator, values: []mut item)` | `random.shuffle(values: []mut item, inout source: generator)` | D1954 by D1988: the values are the subject and the generator stands where a capability stands | mechanical: swap the two arguments |

## The concepts (R20.30)

## Layers (R20.40)

## Names (R20.50)
