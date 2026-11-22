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

## Layers (R20.40)

`platform/posix` moved below the protocol layer (D1951, D2008), and the
move is already made on `r20-integration`: the library, the fixtures and
the examples use the new forms. What R20.60 adds for each entry is the
refusal of the old form naming its replacement, and the `refine fix`
rewrite where it is mechanical. "Mechanical" means the name is replaced
in place and the module the new name is in is imported if it was not.

| old form | new form | decision | rewrite |
|---|---|---|---|
| `posix.internet_address(at)`, `at` a `net.address` | `system.internet_address(at)` | D2008 | mechanical |
| `posix.address_of(record)`, giving a `net.address` | `system.address_of(record)` | D2008 | mechanical |
| `posix.reason` | `system.reason` | D2008 | mechanical |
| `posix.words(problem)`, `problem` holding a library atom | `system.words(problem)` | D2008 | mechanical where the argument's type is wider than `posix.errno`; `posix.words` of an errno stays |
| `io.variable`, the record | `text.host_variable`; `io.variable` is an alias of it in this window and leaves when the list is applied, and R20.50's entry renames the record again | D2008, D1953 | mechanical |

`posix.internet_record`, `posix.internet_endpoint` and `posix.endpoint_of`
are new and replace nothing a program wrote. The registry of
`core/failure` stays one (D1950): nothing is on the list for it.

## Names (R20.50)

D1953 gives each idea one name and each name one meaning. Every entry
here is refused with its replacement once R20.60 applies it. "Mechanical"
means `refine fix` rewrites the use in place: a renamed name, or an atom
in a failure set or an `else`/`case` arm. A failure set that ends up
naming one atom twice after a merge loses the duplicate in the same
rewrite. "By hand" means the use changes shape, and the refusal says
how. Three spellings wait on the maintainer, Q-171 to Q-173; the entries
are written with their defaults.

### Absence (D2028, Q-171)

| old | new | rewrite |
|---|---|---|
| `map.missing` | `mem.not_found` | mechanical |
| `tree.no_such_node` | `mem.not_found` | mechanical |
| `io.not_found` | `mem.not_found` | mechanical |
| `text.not_found` | `mem.not_found` | mechanical |
| `io.no_argument` | `mem.not_found` | mechanical |
| `io.no_variable` | `mem.not_found` | mechanical |
| `posix.no_account` | `mem.not_found` | mechanical |
| `posix.no_symbol` | `mem.not_found` | mechanical |
| `text.past_end` | `mem.out_of_bounds` | mechanical |

`core/mem` declares `not_found`; `failure.reason` and `failure.words`
lose the merged atoms and keep one phrase, "not found". A module that
names the atom and does not import `core/mem` gains the import, which
`refine fix` adds.

### Running out of room (D2029, Q-172)

| old | new | rewrite |
|---|---|---|
| `mem.full` | `mem.out_of_memory` | mechanical |
| `text.no_space` | `mem.out_of_memory` | mechanical |
| `io.line_too_long` | `mem.out_of_memory` | mechanical |

Kept: `mem.grow`'s `(grown: bool)`, `tree.too_many_nodes`,
`tree.too_many_leaves`.

### The end of an iteration (D2030)

| old | new | rewrite |
|---|---|---|
| `map.next_entry` failing `map.end_of_entries` | `map.at_end(value, position)`, and `next_entry` without the failure | by hand; R20.30 adds the map's `iterable` conformance over the same entries |
| `map.end_of_entries` | removed | by hand |
| `line.finished` (field of `io.line`) | `line.at_end` | mechanical |
| an `io.entry` with an empty name at the end | `entry.at_end`, a new field | by hand |
| `io.directory.finished` (provider's field) | `io.directory.at_end` | mechanical |
| `text.done` | `text.utf8_at_end` | mechanical |

Kept: `io.read`'s zero count at the end of a stream; `text.at_end` for
bytes.

### A length (D2031)

| old | new | rewrite |
|---|---|---|
| `io.argument_count` | `io.arguments_length` | mechanical |
| `io.variable_count` | `io.variables_length` | mechanical |
| `io.pending` | `io.buffered_length` | mechanical |
| `arena.used` | `arena.length` | mechanical |
| `text.width` | `text.scalar_length` | mechanical |
| `tree.count_leaves(value, id)` | `tree.leaves(tree.get(value, id))` | mechanical, an expression rewrite |

Kept: every `length`, `diag.message_length`, `net.zone_length`, the
counters `map.slots`, `map.removed`, `tree.leaves`, `pool.live`,
`fault.live`, and `size` for a file's or a block's byte extent
(`io.entry_size`, `io.status.size`).

### Giving storage back, and closing (D2032)

| old | new | rewrite |
|---|---|---|
| `mem.free` | `mem.release` | mechanical |
| `mem.new` | `mem.allocate_item` | mechanical |
| `mem.delete` | `mem.release_item` | mechanical |
| `mem.new_bytes` | `mem.allocate_bytes` | mechanical |
| `mem.delete_bytes` | `mem.release_bytes` | mechanical |
| `mem.dispose` | `mem.detach` | mechanical |
| `arena.reset` | `arena.release` | mechanical |
| `net.close_socket` | `net.close` | mechanical |

Kept: `mem.allocate`, `mem.release_storage`, the allocator concept's
`alloc`, `grow`, `resize` and `free`, every container's `release` and
`clear`, `io.close`, `io.close_directory`, `io.close_input`, `io.wait`
and `join`.

### `host` (D2033, Q-173)

| old | new | rewrite |
|---|---|---|
| `text.host_string` | `text.os_string` | mechanical |
| `text.host_over` | `text.os_string_over` | mechanical |
| `text.host_bytes` | `text.os_string_bytes` | mechanical |
| `text.host_equal` | `text.os_string_equal` | mechanical |
| `text.from_host` | `text.from_os_string` | mechanical |
| `text.append_host` | `text.append_os_string` | mechanical |
| `text.host_variable` (R20.40's move of `io.variable`) | `text.os_variable` | mechanical, after R20.40's entry |

Kept: `host` as the provider's handle, type and parameter, and the
`hosted/` namespace.

### Names with one meaning each (D2034)

| old | new | rewrite |
|---|---|---|
| `io.argument_at` | `io.argument` | mechanical |
| `io.variable_at` | `io.variable` | mechanical, once R20.40's `io.variable` alias for the record has left |
| `fibre.space` | `fibre.record` | mechanical |
| `map.cursor` | `map.position` | mechanical |
| `text.cursor` | `text.from_offset` | mechanical |
| `io.directory.cursor` (provider's field) | `io.directory.consumed` | mechanical |
| `stacks.round_over`'s and `events.over`'s parameter `entries` | `fibres`, after R20.20's reorder | mechanical |

`mem.new`, `mem.new_bytes` and `arena.used` are renamed above. Kept:
`new` for a value made without allocating and a provider's handle; `used`
for the initialized prefix; `at` for a writable slot, and as a parameter
for a place; `space` for a provider's state; `position` for a place in a
sequence; `entry` for a record a collection holds or lends, the map's,
the directory's and the log's.
