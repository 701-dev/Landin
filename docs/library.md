# Library reference

Landin's library is ordinary Landin source that ships with the compiler.
Its modules are in three namespaces, and the namespace says where a module
is available:

| Namespace | Available on |
|---|---|
| `core` | Every enabled target, firmware included. |
| `hosted` | A hosted system only. |
| `platform` | The narrower target scope each module declares. |

Some `platform` modules serve the hosted POSIX systems, which are Linux,
macOS and FreeBSD. None of these modules is available on firmware:

- `platform/posix` serves all three systems.
- `platform/linux` and `platform/libc` are each system's own interface
  beneath it.
- `platform/kqueue` is the event interface of macOS and FreeBSD.

Being available does not promise that every composition fits a particular
firmware image. Every memory lifetime and every handle lifetime remains an
explicit obligation of the caller.

Two kinds of reference appear on this page. A number in brackets, such as
[1300], is a numbered paragraph of [the tour](../tour.md) or `spec.md`. A
name such as `D503` is a decision recorded in `spec.md`. `refine explain`
prints either one, as in `refine explain D503`.

## Common tasks

Find the task in this table. Each row gives the calls to write and the
module whose page describes them. The program after the table does
several of the tasks together.

| Task | Calls | Module |
|---|---|---|
| Get the handle every hosted call takes | `host := blocking.new()` | [hosted/blocking](../hosted/blocking) |
| Print a formatted line | `io.write_format(host, io.out(host), "{} lines\n", [any(addr count)])` | [core/io](../core/io) |
| Print many lines | `io.buffered_over(host, io.out(host), storage)` once, then `io.format(out, "{} lines\n", [any(addr count)])` for each line, and `io.flush(out)`, checked, before reporting success | [core/io](../core/io) |
| Get a command-line argument | `io.argument(host, 0)`, and `io.arguments_length(host)` | [core/io](../core/io) |
| Get the name the program was run by, `argv[0]` | `io.program_name(host)` | [core/io](../core/io) |
| Find a program on the search path, as a shell does | `io.variable_named(host, text.os_string_over("PATH"))`, then `io.find_program(host, name, search, buffer)` | [core/io](../core/io) |
| Run a program in another directory | `io.spawn_in(host, directory, path, arguments, variables, io.inheriting)`, then `io.wait(host, child)` | [core/io](../core/io) |
| Keep a copy of bytes you were only lent | `mem.allocate_copy(memory, bytes)`, and `mem.release_copy(memory, copied)` when done | [core/mem](../core/mem) |
| Give a shorter lifetime inside a region its own memory | `zone.over(space, parent)` over the region's parent, and `zone.reset(scratch)` after each round | [core/zone](../core/zone) |
| Measure the program's own memory | `heap.in_use(memory)`, `heap.peak_in_use(memory)` and `heap.peak_resident(memory)` | [hosted/heap](../hosted/heap) |
| Read a file line by line | `io.open_read(host, path)`, `io.lines_over(host, file, buffer)`, then `io.read_line(lines)` until `item.at_end`, and `io.close(host, file)` | [core/io](../core/io) |
| Read a whole file into memory | `io.open_read(host, path)`, then `io.read(host, file, chunk)` until it gives 0, adding each piece to a builder with `text.append(whole, chunk[0..<got])`, and `io.close(host, file)`. The two kinds of builder are compared after this table | [core/io](../core/io), [core/text](../core/text) |
| Write straight to standard error | `io.write(host, io.err(host), bytes)` | [core/io](../core/io) |
| Turn a failure into words for a person | `failure.words(problem)` | [core/failure](../core/failure) |
| Turn an errno from `platform/posix` into words | `posix.words(problem)` for an errno alone; `system.words(problem)` for a `system.reason`, an errno or one of the library's failures | [platform/posix](../platform/posix), [hosted/system](../hosted/system) |
| Right-align a number in a column | `io.format(out, "{:8}\n", [any(addr value)])`: a number goes to the right of its width, text to the left, and `{:<8}`, `{:>8}` and `{:^8}` say otherwise | [core/text](../core/text) |
| Print a float with two decimals | `io.format(out, "{:.2}\n", [any(addr value)])`, or `text.append_f64_fixed(line, value, 2)`: the exact value rounded once, as C's `printf("%.2f")` writes it | [core/text](../core/text) |
| Read a float from text | `text.parse_f64(bytes)`, rounded once to the nearest `f64`; it reads back everything the library writes | [core/text](../core/text) |
| Change the case of text | `text.utf8_over(buffer)` makes a builder, `unicode.append_upper(into, source)`, `append_lower` or `append_title` writes the text, and `text.utf8_used(into)` lends it | [core/unicode](../core/unicode) |
| Count characters as a reader does | `for cluster in unicode.graphemes(source) do`, counting the items | [core/unicode](../core/unicode) |
| Compare text ignoring case | `unicode.append_folded(into, source)` for each text, `unicode.append_nfc` over each result where accents may be spelled apart, then `text.equal` | [core/unicode](../core/unicode) |

A program that reads a whole file into memory chooses between two
builders:

- A builder that `text.over(storage)` makes fails with `mem.out_of_memory`
  once the file outgrows `storage`.
- A builder that `text.growing(any(addr heap))` makes grows from the
  allocator until `text.release` gives its storage back. It fails with
  `mem.out_of_memory` too, when the allocator refuses.

[This program](../compiler/tests/fixtures/runtime/library-read-whole-file/main.ldn)
reads a file both ways. Its runs over
[a file larger than 64 bytes](../compiler/tests/fixtures/runtime/library-read-whole-file/output.txt),
[a smaller one](../compiler/tests/fixtures/runtime/library-read-whole-file-fits/output.txt)
and
[a missing one](../compiler/tests/fixtures/runtime/library-read-whole-file-missing/output.txt)
are the compiler's own tests. The `read_all` function of
[reverse-complement](../examples.md#benchmark-game-reverse-complement) is
the same loop over standard input.

The next program does the common tasks of a small tool in one place. It
numbers the lines of the file named on the command line, as `cat -n`
does. When it cannot read the file, it says why on standard error:

```landin
--  Number the lines of the file named on the command line, as `cat -n`
--  does, and say in words why when it cannot be read.
import core/failure
import core/io
import core/text
import hosted/blocking

--- Write each line of the file at `path` to `out` after its number.
numbered: (inout out: io.buffered_writer(blocking.host), host: blocking.host,
           path: text.os_string) -> none ! ... =
    file := try io.open_read(host, path)
    defer io.close(host, file) else none
    mut buffer: [4096]u8 = zeroed
    mut lines := io.lines_over(host, file, buffer)
    mut number: u64 = 0
    loop do
        item := try io.read_line(lines)
        break when item.at_end
        inc number
        try io.format(out, "{}: {}\n", [any(addr number), any(addr item.bytes)])
    end loop
end numbered

public main: () -> (code: i32) =
    host := blocking.new()
    mut storage: [256]u8 = zeroed
    mut out := io.buffered_over(host, io.out(host), storage)
    defer io.flush(out) else none
    code = 1
    path := io.argument(host, 0) else begin
        io.write(host, io.err(host), "usage: number FILE\n") else none
        return
    end
    numbered(out, host, path) else (problem)
        io.write(host, io.err(host), text.os_string_bytes(path)) else none
        io.write(host, io.err(host), ": ") else none
        io.write(host, io.err(host), failure.words(problem)) else none
        io.write(host, io.err(host), "\n") else none
        return
    end
    io.flush(out) else (problem)
        io.write(host, io.err(host), "standard output: ") else none
        io.write(host, io.err(host), failure.words(problem)) else none
        io.write(host, io.err(host), "\n") else none
        return
    end
    code = 0
end main
```

Three points about it:

- `numbered` can fail, so its signature ends in `!`. Writing `! ...` asks
  the compiler to work out the set from the `try`s in the body. A function
  that is not `public` may do that [0960].
- `main` cannot fail, so it handles each failure with `else` [1030].
  `else (problem)` names the atom, and `failure.words(problem)` turns the
  atom into words for a person, such as `not found`.
- The output goes through a buffered writer over a buffer that `main`
  declares. The last of the output therefore reaches standard output only
  when the writer is flushed. `main` flushes the writer before it reports
  success, so a write that fails at that point is reported rather than
  lost. On the earlier ways out, the deferred `io.flush` still writes what
  is waiting. The deferred `io.close` closes the file however `numbered`
  ends.

Compile the program and run it over a four-line file:

```sh
refine compile main.ldn -o number && ./number input.txt
```

```text
1: first line
2: second line
3: 
4: last, without a newline
```

When the file it is given is not there, the program says why on standard
error and exits with 1:

```sh
./number missing.conf
```

```text
missing.conf: not found
```

Both runs are the compiler's own tests:
[the program](../compiler/tests/fixtures/runtime/library-common-tasks/main.ldn)
and [its failing run](../compiler/tests/fixtures/runtime/library-common-tasks-missing/fixture.meta).

## Reading a signature

On the site, [the library reference](https://www.701.dev/library.html)
gives each module a page that shows the full signature of every call. The
signature of `io.argument`, for example, is
`(provider: type is process, host: provider, index: usize) -> (value: text.os_string from host) ! no_argument`.
A call writes far less: `io.argument(host, 0)`.

This table says what each part of a signature means:

| In a signature | What it means |
|---|---|
| `provider: type is process`, first | A type parameter. The compiler deduces it from the arguments, so a call usually leaves it out [1300]. A call may name it instead, and then it names every type parameter. `vec.new(item: i32)` must name its type parameter, because no argument has that type. |
| `provider: type` | A type parameter with no requirement: any type will do. |
| `is process` | The type must conform to the concept `process`. A concept is a named set of operations [1230] [1240]. |
| `host: provider` | The provider, which is the handle a call works through. Here it is the handle that `blocking.new()` made. An allocator is passed the same way, usually as `memory: provider` beside its own `provider: type is mem.allocator`. |
| evidence | The table that tells generic code how a type does a concept's operations [1240] [1310]. A conformance such as `u32 is formattable (...)` supplies it. |
| `world` | The concept `core/io` has for an ordinary program's provider: a `reader`, `writer`, `files` and `process` in one. The `host` that `blocking.new()` made is one. In `core/io`, `memory` is the memory world, a provider over the caller's storage. |
| `buffered_writer(provider)` | A generic type applied to a type: a buffered writer over whichever provider the call deduces [1250]. |
| `public builder: type = builder_value` | A public name for a type whose fields are the module's own. You hold a value of the type and pass it to the module's calls. Reading a field is refused. |
| `[]mut u8` | A slice the call may write through [0570]. The call only reads a plain `[]u8`. |
| `[]any text.formattable` | A slice of values of any type that conforms to `formattable` [1370]. A call writes it as an array literal, `[any(addr count), any(addr name)]`. |
| `-> none` | The call returns nothing. |
| `-> (lines: line_reader(provider) from buffer, host)` | A named result. `from buffer, host` says that the result borrows from both and must not outlive either [0790]. |
| `-> (name: []u8, value: []u8)` | Several named results. The caller reads them as fields of the call's result or takes them apart by name [0990]. |
| `! no_argument` | What the call can fail with [0940]. The caller passes the failure on with `try` or handles it with `else`. |
| `! ...` | A function that is not `public` may let the compiler work its set out from its body [0960]. The library's public calls always write theirs. |
| `inout` | The call may change the argument in place [0900]. |
| `sink` | The call consumes the argument [0910]. |

## About this reference

This page is the overview. For each module it has an introduction, the
main calls and an executable example. Other places hold the rest:

| To find | Read |
|---|---|
| Exact signatures, source links, module browsing and local search | The site's [module pages](https://www.701.dev/library.html) |
| The shared conventions and evidence | The [library guide](../core/README.md) |
| The language itself | The [tour](../tour.md) |

The module pages are generated from this page and from the public
declarations in `core`, `hosted` and `platform` with their `---` doc
comments. An editor shows the same comments on hover.

Each module below opens with what it is for, then gives its main calls,
then says how it behaves. The module's page lists the items and ends with
a complete program that uses the module. The compiler's own tests run
that program. Where the program prints, the page also gives the command
and its output.

## What the library does not cover yet

This section first says what is covered. Then it lists what is missing,
with the route to take until then.

The library covers:

- memory, containers and text;
- files, directories, standard input and output, process arguments and
  the environment;
- running programs, clocks, sleeping, the system's entropy and a
  deterministic generator;
- bit operations, integers in a stated byte order and LEB128 over the
  caller's bytes, and sets of flags, `core/bits`;
- the elementary mathematical functions of `f32` and `f64`, `core/math`;
- Unicode's properties, case mapping, normalization and the boundaries
  of characters, words and sentences, `core/unicode`;
- regular expressions over `utf8`, matched in linear time,
  `core/regex`;
- complex numbers over `f32` and `f64`, `core/complex`;
- blocking TCP and UDP sockets over IPv4 and IPv6;
- threads started as a group the function joins, `hosted/thread`;
- the rest of the file system: opening with options, renaming, a file's
  status, read-only files, synchronizing, truncation, reading and writing
  at an offset, temporary files, the working directory's path and
  terminals.

`platform/posix` gives POSIX's own facilities in Landin types, in the same
way on Linux, Darwin and FreeBSD:

- files, directories and memory mappings;
- `poll`, pipes, children and waiting;
- clocks and random bytes;
- sockets, Unix-domain ones among them;
- links, permission bits, owners, file times and locks;
- terminals and their raw mode, and pseudo-terminals;
- the user and group databases.

`platform/posix` also loads shared objects with the system's own loader,
wherever a C runtime started the program. That is the case on Darwin and
FreeBSD, and on Linux under `--link=libc`.

A program that needs something neither of the two covers yet reaches the
operating system itself. The route differs between Linux and the C
library's systems:

| Need | Planned | Route until then |
|---|---|---|
| Calendars, time zones and formatting a date | the locale record in the register | `time.wall_now` gives the wall clock's seconds since 1970. Turning them into a date is the program's work. |
| Resolving a host name to an address | the resolver record in the register | Under the C library, which means on Darwin, on FreeBSD and on Linux under `--link=libc`, declare `getaddrinfo` as `extern(c)`. A static Linux program has none. `net.parse_address` reads an address that is already written as one. |
| Changing the working directory | Not offered. The working directory is the whole process's, and beside threads a change would move every relative path at once. | Use a path built from `io.current_directory`, or a call relative to a directory open as `at` in `platform/posix`; `chdir` by its number through `linux.system_call` on Linux, or declared `extern(c)` on Darwin and FreeBSD, where a program must. |
| Extended attributes, access control lists, file flags | not yet planned | On Linux, pass the call's number from `platform/linux/numbers` to `linux.system_call`. On Darwin and FreeBSD, declare the C function as `extern(c)`. |
| Accounts kept outside /etc/passwd and /etc/group on Linux, those of a directory service or of the Name Service Switch (NSS) | `--link=libc` | A static Linux program reads the two files itself. In a program linked with `--link=libc`, `platform/posix` asks the C library, which asks NSS. |

Every Linux system call is reachable through `linux.system_call`:

- `platform/linux/numbers` names each call's number. The module is
  generated from a pinned kernel release.
- `linux.system_call` makes the call with six integer arguments. It
  returns the kernel's result, which on a failure is the errno negated.

Nothing checks those arguments. A pointer goes as `i64(usize(p))`, and
getting a flag or a record right for each architecture is the program's
work. Prefer a typed wrapper where `platform/linux` has one, and prefer
`platform/posix` where it gives the call.

## core/mem

Memory providers and typed storage: the foundation for allocation, initialized prefixes and caller-owned backing.

| Call | What it does |
|---|---|
| `mem.allocate`, `mem.release` | Take a block from a provider, and give it back through the same provider with the same extent. |
| `mem.allocate_copy`, `mem.release_copy` | Copy lent bytes into a block from a provider, returning the copy as a `[]mut u8` that outlives its source, and give that copy back. |
| `mem.resize` | Give a block a new extent, larger or smaller, in place or by moving it. |
| `mem.storage_over` | Make typed storage over the caller's bytes. |
| `mem.copy`, `mem.fill`, `mem.find` | Copy, set and search byte blocks. |

Supply storage explicitly, through `allocator` evidence. A provider is a
handle passed by value, named `memory` in every signature, so several
containers share one provider without locking it. Two things live in
other modules: the arena is in `core/arena`, and `core/fault` injects
deterministic failures over any provider.

`resize` keeps the bytes that the two extents share. When a resize is
refused, the block stays as it was. A provider that cannot resize in
place answers with `relocate`, which allocates, copies and frees. A bump
provider of your own needs the arithmetic in `aligned_offset`.

`storage_over` does not establish ownership or prove alias lifetimes.

`allocate_copy` is how a program keeps bytes past their lender when it
was only lent them, such as a line a reader refills or an argument. The
copy borrows nothing. An empty copy asks the provider for nothing, and a
refusal is `out_of_memory` with nothing taken. `allocate_bytes` is
different: its `byte_buffer`'s view is lent from the binding, so it is
for bytes used where they were made.

Byte blocks are slices, with their lengths checked:

- `copy` puts every byte of a source at the start of a destination. It
  follows the rule of `memmove`, so the two may overlap in either
  direction. When the destination is shorter, it reports `out_of_bounds`
  before it writes anything.
- `fill` sets every byte.
- `find` gives the index of a byte's first occurrence, or the slice's
  length when there is none. So `source[0..<find(source, v)]` is always
  the part before the byte.
- To compare two byte strings, use `cmp.compare`.

On hosted targets `copy`, `fill` and `find` move a `usize` word at a
time. How they do it depends on the target and the direction:

| Where | How the words move |
|---|---|
| x86-64 and arm64 | Copying up and searching load and store words at any address, from the first byte, and move bytes only in the tail. |
| Other hosted targets, and copying down or filling anywhere | Words move only at a multiple of the word. A head before them and a tail after them move a byte at a time. |
| Firmware | Plain byte loops, whose code is smaller. |

[Executable example](../compiler/tests/fixtures/runtime/library-shared-mem/main.ldn)

## core/vec

A growable contiguous list with explicit allocation and rollback on failed growth.

| Call | What it does |
|---|---|
| `vec.new` | Start an empty list; nothing is allocated. |
| `vec.reserve`, `vec.push` | Grow the list, through the provider's handle. |
| `vec.get`, `vec.last`, `vec.pop` | Copy an item out; what it refers to is what the list held, not a view of the list. |
| `vec.at` | Lend a writable pointer to an item. |
| `vec.used` | Lend the initialized slice. |

End views before relocation or release. Clearing or releasing a container
never frees the resources that its items refer to. So an item copied out
of a list is no view of it: a pointer read with `vec.last` goes back in
with `vec.push` while nothing else views the list (D1369).

A list of bytes is the growable byte container:

- `append_bytes` copies a slice in after the list's bytes. The slice may
  be the list's own bytes, `vec.used(list)` or a part of it: what is
  appended is what it held when the call began, though the list moved.
- `spare_bytes` lends the spare capacity, which a read fills.
- `extend_bytes` counts what was written there.

They move a word at a time where `mem.copy` moves words. A list's items
move the same way when the list grows into a new block.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-vec/main.ldn)

## core/spill

A list that keeps an inline prefix and spills into allocated storage when it fills.

Queries use a pointer, so they do not copy the inline array.

Popping from spilled storage keeps that allocation. `release` returns the
list to an empty inline representation.

Items need no zero image: the list stores pointers and atom-bearing
records like any other item.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-spill/main.ldn)

## core/cmp

Equality, hashing and ordering evidence, apart from the containers and algorithms that consume it.

The three concepts ship for these types:

| Type | `equatable` | `hashable` | `ordered` |
|---|---|---|---|
| the ten integer scalars | yes | yes | yes |
| `bool` | yes | yes | no |
| `[]u8` | yes | yes | yes, by `compare` |
| `utf8`, from `core/text` | yes | yes | yes |
| `time.duration` and `time.instant`, from `core/time` | yes | yes | yes, by their counts |
| `net.address`, from `core/net` | yes, as `same_address`, zone included | yes | no |
| `f32` and `f64` | no | no | yes, by IEEE 754's totalOrder |

Every hash is keyed by a `cmp.hash_seed`, made by `cmp.seed_from` from
two `u64` words:

| Call | What it does |
|---|---|
| `cmp.seed_from` | Make a seed from two words, SipHash's k0 and k1. |
| `cmp.hash_bytes` | SipHash-1-3 of a byte slice under a seed. |
| `cmp.hash_word` | The same of a `u64`'s eight bytes, least significant first. |

The shipped hashes are these two. An integer hashes as `hash_word` of its
bits widened to 64, a `bool` as the word 0 or 1, and `[]u8`, `utf8` and
`net.address` as `hash_bytes` of the bytes their equality compares. They
give the same result for a seed on every target, Cortex-M0 included.
Whoever does not know the seed cannot tell which keys will collide. A key
type of your own builds its hash from these with the seed it is given.
SipHash is a keyed hash, not a cryptographic digest.

`compare` orders two byte strings as `less`, `equal` or `greater`. The
first differing byte decides, and a proper prefix comes first. This is
C's `memcmp` with the lengths taken into account, and it is the order
`ls` gives names in the C locale. The `ordered` evidence of `[]u8` is the
`less` of this order.

The `ordered` evidence of `f32` and `f64` is IEEE 754's totalOrder:
negative numbers from negative infinity up, then -0.0, +0.0 and the
positive numbers up to infinity. It agrees with `<` on every pair of
numbers except the two zeros, so `sort.sort` sorts floats as it sorts
integers. A NaN sorts to an end by its sign: the negative ones before
negative infinity, larger payload first, and the positive ones after
infinity, larger payload last. Floats have no `equatable` or `hashable`
evidence.

There is one register and no override. To read a shipped type another
way, put it in a `distinct` wrapper that has its own evidence. A
`hashable` key declares its `equatable` conformance as well.

The compiler does not prove the laws:

- equality must be an equivalence;
- equal keys must hash alike under one seed;
- `less` must be a strict weak ordering.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-cmp/main.ldn)

## core/iter

The concept a `for` loop walks a value through.

`for x in s` over a struct or an `any C` uses `s`'s conformance to
`iter.iterable`. A concept named `iterable` declared anywhere else is not
used. A conformance names a
cursor type and an item type and supplies `first`, `at_end`, `item` and
`next`, each given a read-only pointer to the loop's own copy of the
source; `item` hands out a value of its own, never a view of the source.
`core/map` and `core/tree` conform.

[Executable example](../compiler/tests/fixtures/runtime/for-over-map-and-tree/main.ldn)

## core/map

An insertion-ordered hash map with explicit entry walks.

| Call | What it does |
|---|---|
| `map.new` | Start an empty map that hashes its keys under a seed. |
| `map.insert` | Add a key and its item, through the provider's handle. |
| `map.get`, `map.at`, `map.contains` | Copy an item, lend a pointer to it, or ask whether a key is there. |
| `map.remove` | Remove a key. |
| `map.entries`, `map.next_entry` | Walk the entries in insertion order. |
| `for each in m` | The same walk through `core/iter`'s `iterable`, each entry a copy of its key and item. |

Keys are constrained on the `hashable` concept of `core/cmp`, whose table
lists the types `hashable` ships for. An alternative policy uses a
`distinct` wrapper. Floating-point keys need an explicit equality and hashing
policy.

Keep keys and their backing stable while the map stores them, and
restart positions after any mutation.

A map hashes every key under the seed `map.new` is given, and keeps it
through `release` and `clear`. A seed the key's chooser does not know
keeps keys from being chosen to share one probe chain, where each
insertion and lookup would take time in proportion to the map's size:

- a hosted program keyed by outside data draws its seed with
  `random.hash_seed` from its entropy provider;
- firmware without entropy builds one with `cmp.seed_from` from two words
  of its own: a hardware random number or a unique device ID where it has
  one, and otherwise a constant chosen for the build, which protects the
  map only while the image stays secret;
- a test uses a constant, so that every run probes alike.

The seed changes nothing a lookup finds and not the order of a walk. It
changes which slots the keys take, and so the number of probes. After
removals it also decides whether a new key reuses a removed entry's slot
or rebuilds the table, which `slots`, `removed` and `capacity` report.
A constant seed makes all of this the same on every run.

[Keys chosen against a known seed](../compiler/tests/fixtures/runtime/map-seed-spreads-chosen-keys/main.ldn)
share one probe chain and spread under another seed;
[a hosted map](../compiler/tests/fixtures/runtime/map-seeded-from-entropy/main.ldn)
draws its seed from the system's entropy, and
[a firmware map](../compiler/tests/fixtures/runtime/map-firmware-seed/main.ldn)
is given two words.

There are two ways to walk a map. One starts at `map.entries()` and
asks `map.at_end` before each `map.next_entry`, which never fails;
the executable example below walks this way. The other is a `for` loop
over the map,
[as this program does](../compiler/tests/fixtures/runtime/for-over-map-and-tree/main.ldn). The
[derived container program](../examples/derived_containers/workload/workload.ldn)
also walks after removing keys.

Three counts describe the table:

| Call | What it counts |
|---|---|
| `capacity` | How many entries fit before the next new key rebuilds the table. Removed entries count against the capacity until a rebuild. |
| `slots` | The table's size. |
| `removed` | The dead entries, which hold their slots until a rebuild. |

The representation is the module's own. Hashes are spread before they
choose a slot, so keys that share a stride do not share a probe chain.

A complete map workload can exceed the Cortex-M0 test profile of 32 KiB
flash. The
[Cortex-M0 example](../compiler/tests/fixtures/runtime/library-shared-map/main.ldn)
therefore checks only the empty-map surface. It does not show that a
populated map fits that profile.

[Executable example](../compiler/tests/fixtures/runtime/library-builtin-keys/main.ldn)

The program keeps three maps over one arena, keyed by `i32`, `[]u8` and
`utf8`. It inserts keys, replaces one key's item and reads each item
back. It finds a `[]u8` key through equal bytes at another address. It
walks the `utf8` map's entries in insertion order until
`map.at_end`, and it releases every map.

## core/sort

Allocation-free in-place heapsort and selection sort using ordering evidence, and heapsort by a comparison given a context.

| Call | What it does |
|---|---|
| `sort.sort` | Heapsort by the items' `ordered` evidence. |
| `sort.sort_selection` | Selection sort by the same evidence. |
| `sort.sort_by` | Heapsort by a comparison you pass, with a context. |

None of the three allocates, and none promises stability.

Items are constrained on the `ordered` concept of `core/cmp`, whose table
lists the types `ordered` ships for. Custom `ordered` evidence must obey a
strict weak ordering.

`sort_by` takes the order as a comparison, `less(by, left, right)`. On
every call it passes the comparison the context `by` that the caller
gave, unchanged. Records that refer into shared storage, such as offsets
into one pool of names, are therefore ordered by what they refer to. The
context may also be a pointer that the comparison counts through. The
comparison must be a strict weak ordering while it runs.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-sort/main.ldn)

## core/text

Byte cursors, validated UTF-8 views, positions and searches inside them, a scalar encoder, two text builders, formatting and parsing numbers.

| Call | What it does |
|---|---|
| `text.from_bytes`, `text.valid` | Check that bytes are UTF-8, as a view or as a yes or no. |
| `text.start`, `text.step`, `text.utf8_at_end`, `text.scalar_length` | Walk text a scalar at a time, keeping each scalar's byte position. |
| `text.find`, `text.find_scalar` and their `_from` forms | Find where text or a scalar first occurs. |
| `text.encode` | Write a scalar's UTF-8 bytes into your buffer. |
| `text.utf8_over` | Make a builder that only ever holds UTF-8. |
| `text.over`, `text.growing` | Make a builder over your buffer, or one that grows from an allocator. |
| `text.append_text`, `text.append_u32` and the rest | Append a piece to a builder. |
| `text.format` | Append a template with each `{}` filled in. |
| `text.format_onto` | Format a template through a buffer, handing the text to an `outlet` as the buffer fills. |
| `text.parse_u32` and the rest | Read a number from bytes. |
| `text.os_string_over`, `text.from_os_string` | Make an OS string, and check that one is UTF-8. |

### Views and cursors

Cursors advance by bytes. Views borrow their input.

Three things check that bytes are UTF-8:

- `from_bytes` validates the bytes and reports `invalid_text` when they
  are not UTF-8.
- `valid` answers the same question without a view.
- The `utf8(bytes)` conversion validates too, but it traps on malformed
  input.

A `text.position` indexes `utf8` by byte offset, while a `usize` index
into `utf8` counts scalars. So do not index with `offset(position)`.
`text.from_offset` makes a position at any offset you give it and checks
nothing. The positions below are always on a scalar's start.

UTF-8 equality, hashing and ordering use the encoded bytes. `core/text`
never normalizes and never collates by locale; a program that needs two
spellings of one text to compare equal normalizes them first with
[core/unicode](../core/unicode).

### Positions and searches in text

The byte cursors step one byte over `[]u8`. Over `utf8`, positions step a
whole scalar, so each position is where a scalar starts, or the end:

| Call | What it does |
|---|---|
| `start(source)` | The first scalar's position, offset zero. |
| `done(source, at)` | Whether `at` is at the end. |
| `width(source, at)` | How many bytes, one to four, the scalar at `at` takes. |
| `step(source, at)` | The position after the scalar at `at`. |
| `find(source, sought)` | Where `sought` first begins, or `mem.not_found`. |
| `find_from(source, sought, at)` | The same, searching from `at`. |
| `find_scalar(source, scalar)`, `find_scalar_from` | Where a scalar first is, or `mem.not_found`. |

Read the scalar at a position as `source[at]`. Walk the text by stepping
until `utf8_at_end`. This function walks a key that way, and checks each scalar
and where it begins:

```landin
--  The key's scalars and where each begins, read by stepping.
key_steps: (key: utf8) -> (yes: bool) =
    scalars: [5]u32 = ['n', 'a', '\u{ef}', 'v', 'e']
    offsets: [5]usize = [0, 1, 2, 4, 5]
    widths: [5]usize = [1, 1, 2, 1, 1]
    yes = false
    mut at := text.start(key)
    mut index: usize = 0
    while not text.utf8_at_end(key, at) do
        return when index >= 5 or key[at] <> scalars[index]
          or text.offset(at) <> offsets[index]
          or text.scalar_length(key, at) <> widths[index]
        at = text.step(key, at)
        inc index
    end while
    yes = index == 5 and text.offset(at) == lenof key
end key_steps
```

`step` and `scalar_length` read the scalar at the position, so they trap where
`source[at]` traps: at the end and inside a scalar. A search from a
position inside a scalar traps too.

A match begins and ends where scalars do. The text before the match, the
match and the text after it are therefore each a range of the source:
`utf8` with the source's origin, and nothing copied. This function splits
a record at its first `=`:

```landin
--  The key before the first `=` and the value after it.
split: (record: utf8) -> (result: entry from record) ! mem.not_found =
    equals := try text.find_scalar(record, '=')
    value_at: usize = text.offset(text.step(record, equals))
    result = (key: record[0..<text.offset(equals)],
              value: record[value_at..<lenof record])
end split
```

[The splitter](../compiler/tests/fixtures/runtime/core-text-utf8-split/main.ldn)
goes on to take each field between arrows with `find_from`.

Three more facts about searches:

- Empty sought text is found where the search begins, as `contains` finds
  it.
- A surrogate is in no text, so `find_scalar` reports `mem.not_found` for one.
- Searches are the Two-Way search that `contains` uses. It is linear in
  the two lengths, with no table and no allocation.

### Encoding a scalar

`encode(scalar, into)` writes the scalar's UTF-8 bytes at the front of
`into` and returns how many it wrote, one to four. To write at an offset,
pass what follows the offset, `buffer[at..<lenof buffer]`.

`encode` refuses in two cases, and either refusal writes nothing:

- A surrogate, U+D800 to U+DFFF, or a value above U+10FFFF is
  `invalid_scalar`. This refusal comes first, whatever the room.
- A scalar that does not fit is `mem.out_of_memory`.

### OS strings

An OS string, `os_string`, is a path, a process argument or a
directory entry's name, in the representation its system gives and
takes. On Linux, Darwin and FreeBSD that representation is bytes, which
need not be UTF-8. An OS string is never converted on the way through,
so an argument passed on as a path reaches the system as it was given.

| Call | What it does |
|---|---|
| `from_os_string` | The checked conversion to `utf8`, reporting `invalid_text` as `from_bytes` does. |
| `os_string_bytes` | Lend its bytes. |
| `os_string_equal` | Compare it with a literal. |
| `os_string_over` | Make one over the caller's bytes: `text.os_string_over("input.txt")` for a literal path. |

An OS string lends what it was made from. The NUL a C call needs is
never the caller's: `platform/posix` adds it beneath the provider, and
refuses a path that holds one.

### The builder

A `builder` writes text into bytes a piece at a time. It is a value the
caller passes `inout`.

| Call | What it does |
|---|---|
| `over` | Make a builder over the caller's buffer, which never grows. |
| `growing` | Make a builder that takes its storage from an erased allocator, `text.growing(any(addr heap))`. It doubles what it holds, and `release` gives the storage back. |
| `used` | Lend what the builder holds, until the builder next changes. |
| `length` | The offset the next piece begins at. |
| `clear`, `truncate` | Empty the builder, or cut it back. |

An append, and `format`, may be given the builder's own bytes,
`text.used(line)` or a part of it. What is written is what they held when
the call began, though the builder grew and moved while it wrote. The
view is still not to be used after the call.

Each append writes its whole piece, or reports `mem.out_of_memory` and leaves the
builder as it was:

| Append | Writes |
|---|---|
| `append` | bytes as they are |
| `append_byte` | one byte |
| `append_text` | a `utf8` |
| `append_scalar` | a scalar's UTF-8 bytes, as `encode` writes them, or `invalid_scalar` |
| `append_os_string` | an OS string's bytes |
| `append_u32`, `append_u64`, `append_usize` | decimal |
| `append_i32`, `append_i64`, `append_isize` | decimal, with a `-` before a negative value |
| `append_hex_u32`, `append_hex_u64`, `append_hex_usize` | lower-case hexadecimal with no `0x` |

Each append takes exactly its own type, and nothing widens at the call:
passing a `u8` to `append_u32` is refused. Convert a narrower integer
explicitly, `text.append_u32(line, u32(byte))`.

Width and padding apply to whatever was written since an earlier
`length`:

- `align_right` puts a fill byte before the piece until the piece is as
  wide as the field.
- `align_left` puts the fill byte after the piece.

The fill goes before a sign too, so a zero fill suits an unsigned value.

To right-align a number in a column, note where it starts, append it and
align what was appended. The fill is a byte, so a space is `u8(' ')`:

```landin
--- Append `value` to `line` in decimal, right-aligned in a field `width`
--- bytes wide.
append_right: (inout line: text.builder, value: u64, width: usize)
              -> none ! mem.out_of_memory =
    start: usize = text.length(line)
    try text.append_u64(line, value)
    try text.align_right(line, start, width, u8(' '))
end append_right
```

A builder over `mut buffer: [64]u8 = zeroed` is `text.over(buffer)`, and
`io.put(out, text.used(line))` prints what the builder holds.

### The UTF-8 builder

A `builder` holds bytes, which need not be UTF-8, because `append` takes
any bytes. A `utf8_builder` holds only UTF-8, because it takes only text,
scalars and numbers. `utf8_over(buffer)` makes one over your buffer.

| Call | What it does |
|---|---|
| `utf8_append_text`, `utf8_append_scalar` | Append text or a scalar. |
| `utf8_append_u32` and the other number appends | Append a number, as the builder's call without `utf8_` does. |
| `utf8_used` | Lend the text written as one `utf8`, until it next changes; nothing is scanned. |
| `utf8_bytes` | Lend the same as bytes. |
| `utf8_length`, `utf8_capacity`, `utf8_clear` | As the builder's. |
| `utf8_truncate` | Cut back to a length, never inside a scalar. |

Each append writes its whole piece, or reports `mem.out_of_memory` and leaves the
builder as it was. A cut inside a scalar keeps only the scalars before
the cut. A `utf8_builder` has no byte append, no alignment and no
`format` into it, since each of those can write any bytes.

### Formatting

`format` appends a template to a builder. Each placeholder is replaced by
the next of an array of `any formattable` values, and `{{` and `}}` are
written as braces.

The values are an array literal written at the call, which lends the
array as a slice:
`text.format(line, "{} {}\n", [any(addr count), any(addr name)])`.

A placeholder is `{}`, or `{:` and a specification as Rust spells it:
`[[fill]align][+][#][0][width][.precision][kind]`, every part optional.

| Part | Means |
|---|---|
| `8`, the width | At least eight scalars: a number goes to the right, anything else to the left |
| `<`, `>`, `^` | Left, right or centred in the width; a scalar before it is the fill, `{:*^8}` |
| `+` | A `+` before a number that is not negative |
| `#` | `0x`, `0o` or `0b` before a number in that radix |
| `0` | Zeros between a number's sign or prefix and its digits, `-0042` |
| `.3`, the precision | A float to three places after the point; text to three scalars |
| `x`, `X`, `o`, `b` | An integer in hexadecimal, upper-case hexadecimal, octal or binary; a negative one as its two's complement at its width, `-1i8` as `ff` |
| `e`, `E` | A float with one digit before the point and an exponent, `6.02e23` |

A part a value does not read changes nothing: `{:.2}` of an integer is
the integer. There are no positional or named arguments, and no width or
precision taken from an argument.

`formattable` has one entry, `append`, which writes a value into a
builder through a pointer to the value. The library supplies it for
these types, and a program declares it for a type of its own:

- the ten integer types, in decimal unless the placeholder names a radix;
- `f32` and `f64`, as `append_f64` writes them unless it names a precision
  or `e`;
- `bool`, as `true` or `false`;
- `utf8`, `[]u8` and OS strings.

The template applies the width, fill and alignment to whatever a
conformance wrote, so a type of the program's own is padded without
reading anything. One that wants the precision or the radix reads the
placeholder with `text.placeholder(into)`, a `text.format_spec`, whose
`kind` is the letter or zero. Outside a format, and inside a nested
format's own placeholders, it is `text.plain`.

Nothing runs at compile time, so the template is checked against the
values when `format` runs:

- A different number of placeholders, a specification that does not
  parse, or a brace that is neither part of a placeholder nor doubled, is
  `invalid_format`, and nothing is written.
- A builder that fills partway is put back before `mem.out_of_memory` is reported.

A float has three forms, each also a typed call:

| Call | Placeholder | Writes |
|---|---|---|
| `append_f64(line, value)` | `{}` | The shortest text that reads back as the same value, as a Landin literal is written: `1.0`, `0.1`, `123.456`, and below 0.0001 or from 10^16 up `1.0e16`, `2.5e-7` |
| `append_f64_fixed(line, value, 3)` | `{:.3}` | Three places after the point, the exact value rounded once with ties to even, as C's `printf("%.3f")` writes it: `3.142`, and `-0.000` for a small negative |
| `append_f64_exponent(line, value, 3)` | `{:.3e}` | One digit before the point and three after, then the exponent, rounded as `fixed` is: `6.022e23` |

`{:e}` is the shortest digits in the exponent form, `1.0e0`. The
infinities are `inf` and `-inf`, and a NaN is `NaN`. Each has an `f32`
call, `append_f32` and the rest, which writes the `f32`'s own shortest
text, `0.1` for the `f32` nearest a tenth.

`format_onto` formats text that may be longer than its buffer. It formats
through a buffer of the caller's, and hands the text to an `outlet` each
time the buffer fills and once at the end. `io.write_format` is
`format_onto` over a file. An `outlet` has one entry, `take`, which takes
the bytes whole or reports `mem.out_of_memory`.

How a value passes through the buffer:

- A value that fits the buffer is formatted and padded whole in it, so a
  conformance's `length` and alignments see its own piece.
- A library value longer than the whole buffer is handed on in pieces as
  it is written; a width can then pad it only after it.
- The buffer must still hold the largest piece a value asks room for at
  once. Twenty bytes hold every integer the library formats, and a float
  writes its digits a run at a time. A conformance of the program's own
  that asks for more than the buffer has fails with `mem.out_of_memory`.

A conformance of the program's own may be writing a value longer than the
whole buffer, a row with a long name in it. Its offsets still hold:

- `length` counts the bytes already handed on, so an offset taken before
  a piece was handed on names the same byte after.
- `align_left` fills after its piece wherever the piece began.
- `align_right` needs the whole piece still in the buffer, and room there
  for the fill. When some of the piece has been handed on, nothing can go
  before it, and the call fails with `mem.out_of_memory`. Through
  `io.write_format` that is `io_failed`, after the text before it was
  written. A column that must hold a long value right-aligned is built in
  a builder of the program's own that is long enough, and written whole.
- `truncate` cuts what the buffer still holds. What was handed on stays
  written.

No locale is consulted anywhere. The same values give the same bytes
everywhere, on Cortex-M0 as on a hosted system.

### Parsing numbers

Parsing is the mirror of the appends. It reads a byte slice, which need
not be UTF-8:

| Parse | Reads |
|---|---|
| `parse_u8` to `parse_u64`, `parse_usize` | nonempty ASCII digits |
| `parse_i8` to `parse_i64`, `parse_isize` | an optional `-` before them, never a `+`, since no append writes one |
| `parse_hex_u32`, `parse_hex_u64`, `parse_hex_usize` | hexadecimal digits of either case, with no `0x` |
| `parse_f64`, `parse_f32` | an optional `-`, digits with an optional point and a digit beside it, `2.` and `.25` too, and an optional exponent, `e` or `E` with an optional sign; or `inf`, `infinity` or `nan` in any case |
| `to_u32` | `parse_u32` over a `utf8` view |

A parse fails in two ways. The scan goes from the left and reports
whichever it meets first:

- Any input other than what the table allows, a space included, is
  `invalid_number`.
- A value outside the type, above its maximum or below a signed minimum,
  is `number_overflow`. A float's is a finite decimal whose nearest float
  is beyond the greatest; one too small for the least subnormal is zero.

A float is read with any number of digits and rounded once to the
nearest float of its width, ties to even; an `f32` is never rounded
through an `f64`.

`usize` and `isize` are the target's, 32 bits on Cortex-M.

The builder's appends are the library's one decimal writer, and these
parses are its one parser: `core/net` reads the numbers of its addresses
through them.

[Executable example](../compiler/tests/fixtures/runtime/library-text-columns/main.ldn)

The program prints a price list: each item's name aligned left, its
count right-aligned under its heading, and its price, an `f64`, with two
decimals.

## core/unicode

What the Unicode Standard says about a scalar and about text, where
`core/text` reads and writes UTF-8 without interpreting it:
a scalar's properties, case mapping, the four normalization forms, and
where a reader's characters, words and sentences begin and end. The data
is Unicode 18.0.0, which `unicode.unicode_version` names as a
`version_number` of `major`, `minor` and `update`.

| Call | What it does |
|---|---|
| `unicode.category`, `unicode.combining_class` | A scalar's general category and its canonical combining class. |
| `unicode.is_alphabetic`, `unicode.is_white_space`, `unicode.is_uppercase`, `unicode.is_lowercase`, `unicode.is_cased`, `unicode.is_case_ignorable` | Whether a scalar has a property. |
| `unicode.simple_upper`, `unicode.simple_lower`, `unicode.simple_title`, `unicode.simple_fold` | Map one scalar to one scalar. |
| `unicode.append_upper`, `unicode.append_lower`, `unicode.append_title`, `unicode.append_folded` | Append a text in another case, or folded for a comparison that ignores case. |
| `unicode.append_nfc`, `unicode.append_nfd`, `unicode.append_nfkc`, `unicode.append_nfkd` | Append a text in a normalization form. |
| `unicode.graphemes`, `unicode.words`, `unicode.sentences` | Walk a text's characters, words or sentences in a `for` loop. |
| `unicode.grapheme_end`, `unicode.word_end`, `unicode.sentence_end` | Find the next boundary after a position. |

A scalar is a `u32`, as a `for` loop over `utf8` gives one. Every routine
that writes appends to a `text.utf8_builder`, which the caller makes over
its own buffer with `text.utf8_over`, and appends its whole result or
nothing: on `mem.out_of_memory` the builder holds what it held. Nothing
allocates and nothing keeps state. The tables are immutable data, written
by `scripts/unicode_tables.py` from a pinned copy of the Unicode Character
Database.

### Properties

| Call | What it does |
|---|---|
| `category(scalar)` | The general category, a `general_category`: one of thirty atoms named as the database's long names are, in lower case, so Lu is `unicode.uppercase_letter` and Nd is `unicode.decimal_number`. A value above U+10FFFF is `unassigned`. |
| `combining_class(scalar)` | The canonical combining class, a `u8`, which orders the marks after a base. It is zero for a base and for any scalar that is no mark. |
| `is_alphabetic(scalar)` | Whether the scalar is Alphabetic: a letter, or a mark or number that writes part of a word. |
| `is_white_space(scalar)` | Whether it is White_Space: a space, a tab, or a line or paragraph end. |
| `is_uppercase(scalar)`, `is_lowercase(scalar)` | Whether it is Uppercase, or Lowercase. |
| `is_cased(scalar)` | Whether it is Cased: upper, lower or title case. |
| `category_run_end(scalar)`, `property_run_end(scalar)` | The last scalar of the run beginning at `scalar` whose scalars all share its general category, or all answer the six `is_` properties as it does. Stepping from run to run covers every scalar in a few thousand steps, which is how `core/regex` builds its classes. |
| `is_case_ignorable(scalar)` | Whether it is Case_Ignorable, which case mapping passes over when it looks for the letters around a sigma or for a word's first letter. |

Compare a category with `==`, as in
`unicode.category(scalar) == unicode.decimal_number`.

### Case

| Call | What it does |
|---|---|
| `simple_upper(scalar)`, `simple_lower(scalar)`, `simple_title(scalar)` | The simple mapping, one scalar for one, or the scalar itself when it has none. ß has no simple uppercase, since its uppercase is two letters. |
| `simple_fold(scalar)` | The simple case folding: what two scalars that differ only in case both fold to. |
| `append_upper(into, source)` | Append the uppercase of `source`, by each scalar's full mapping: "straße" gives "STRASSE". |
| `append_lower(into, source)` | Append the lowercase. A capital sigma that ends a word becomes ς, final sigma, and one elsewhere σ. |
| `append_title(into, source)` | Append the title case. In each word, as `word_end` finds them, the first cased scalar takes its titlecase mapping and the rest of the word its lowercase: "the ǆungla" gives "The ǅungla". |
| `append_folded(into, source)` | Append the case folding, so that two texts that differ only in case fold to the same text: "Straße" and "STRASSE" both give "strasse". |

The four `append_` routines apply Unicode's default full mappings, which
are right for every language except Turkish, Azerbaijani and Lithuanian.
Those three need a locale, which a later item adds.

To compare two texts ignoring case, fold each and compare the results
with `text.equal`. Put them in NFC as well where an accent may be written
either as part of its letter or as a mark of its own:

```landin
--  Whether two texts say the same words whatever their case and however
--  their accents are spelled: each folded, then put in NFC, compares
--  equal.
same_words: (left: utf8, right: utf8) -> (yes: bool) ! mem.out_of_memory =
    mut folded: [64]u8 = zeroed
    mut left_storage: [64]u8 = zeroed
    mut right_storage: [64]u8 = zeroed
    mut scratch: text.utf8_builder = text.utf8_over(folded)
    mut left_form: text.utf8_builder = text.utf8_over(left_storage)
    try unicode.append_folded(scratch, left)
    try unicode.append_nfc(left_form, text.utf8_used(scratch))
    text.utf8_clear(scratch)
    mut right_form: text.utf8_builder = text.utf8_over(right_storage)
    try unicode.append_folded(scratch, right)
    try unicode.append_nfc(right_form, text.utf8_used(scratch))
    yes = text.equal(text.utf8_used(left_form), text.utf8_used(right_form))
end same_words
```

### Normalization

| Call | What it does |
|---|---|
| `append_nfc(into, source)` | Append the NFC form: canonically decomposed and composed again, so "e" and U+0301 give "é", U+00E9. It is the form to store and compare text in. |
| `append_nfd(into, source)` | Append the NFD form: every scalar canonically decomposed, with its marks in canonical order. |
| `append_nfkc(into, source)` | Append the NFKC form: compatibility decomposed and canonically composed again. It is the form to match identifiers and search terms in. |
| `append_nfkd(into, source)` | Append the NFKD form: decomposed by the compatibility mappings too, so "ﬁ" gives "fi" and "²" gives "2". That loses formatting a reader may have meant. |

The routines keep no buffer of their own. Each takes time linear in the
text, except over a run of combining marks that is out of canonical
order, which takes the run's length times the number of combining
classes it holds.

`core/text` never normalizes: its equality, hashing and ordering compare
the encoded bytes. A program that wants "é" to equal "e" with U+0301
normalizes both texts first.

### Segmentation

The boundaries are those of the default rules of Unicode's UAX #29.

| Call | What it does |
|---|---|
| `graphemes(source)` | The extended grapheme clusters, each what a reader takes for one character: "é" written as "e" and U+0301 is one, and so is a flag or a family emoji. |
| `words(source)` | The pieces between word boundaries: each word, and each run of spaces or single punctuation mark between words. |
| `sentences(source)` | The sentences, each with the spaces after it. |
| `grapheme_end(source, at)`, `word_end(source, at)`, `sentence_end(source, at)` | The position where the piece that begins at `at` ends, or `at` itself at the end of the text. `at` is a boundary: the text's start, or a position one of these returned. |

`graphemes`, `words` and `sentences` each give a walk for `for`. Each
item is a `unicode.segment` holding two `text.position`s, `begins` and
`ends`, and the items cover the text in order. A segment holds positions
and not the text, so slice the text to read a piece:
`source[text.offset(piece.begins)..<text.offset(piece.ends)]`.

`words` gives the spaces and punctuation as pieces too. Whether a piece
is a word is the caller's question; a piece that holds an alphabetic
scalar or a digit is one.

Counting characters as a reader does is a walk over the clusters, beside
the walk over scalars that `for` gives over `utf8` itself:

```landin
--  How many scalars and how many characters `source` holds: a character
--  is what a reader takes for one, an extended grapheme cluster.
counts: (source: utf8) -> (scalars: usize, characters: usize) =
    scalars = 0
    characters = 0
    for scalar in source do
        _ = scalar
        inc scalars
    end for
    for cluster in unicode.graphemes(source) do
        _ = cluster
        inc characters
    end for
end counts
```

### What it leaves out

- Scripts and the properties not listed above.
- Line breaking, Unicode's UAX #14.
- Collation, which is ordering text as a language's readers expect.
- Case mapping tailored to a locale.
- Encodings other than UTF-8.

Later items add encodings and locale formatting. Regular expressions
are `core/regex`, the next section.

### Conformance and size

Unicode's conformance tests for normalization and for grapheme cluster,
word and sentence boundaries pass in full on every hosted target, and
there every table is checked against the database over every
scalar, by digest. Firmware checks every Nth scalar. The checks are the
`unicode-*` fixtures under `compiler/tests/fixtures/runtime/`.

The tables are immutable, so on a microcontroller they stay in flash and
take no RAM, and an image links only the tables that the routines it
calls reach. On Cortex-M0 at `size/auto`, in bytes of flash measured from
linked images:

| What a program calls | Tables | `core/unicode` code |
|---|---:|---:|
| `category` | 12,420 | 380 |
| `combining_class` and the six `is_` properties | 12,134 | 1,190 |
| Simple and full upper, lower and folded case | 12,047 | 4,544 |
| Title case, which adds word boundaries | 19,147 | 6,226 |
| NFC and NFD | 19,817 | 7,098 |
| NFKC and NFKD, with NFC and NFD | 36,084 | 7,578 |
| Grapheme clusters | 5,388 | 2,636 |
| Words | 7,100 | 3,480 |
| Sentences | 7,964 | 2,816 |

NFKC and NFKD do not fit Cortex-M0's 32 KiB profile beside anything. Each
of the others does.

[Executable example](../compiler/tests/fixtures/runtime/example-text-as-read/main.ldn)

The program is [Text as a reader sees it](../examples.md#text-as-a-reader-sees-it):
it counts the characters of a name and of two flags, lists the words of a
sentence, changes case, and compares two texts ignoring case.

## core/regex

Regular expressions over `utf8`: a pattern is compiled when the program
runs, with the caller's allocator, and then searched for in texts. Use it
where the thing to find is a shape and not a fixed text; for a fixed
text, `core/text`'s searches are smaller and need no allocator.

The syntax and the meaning of a pattern are those of Rust's `regex`
crate, without backreferences and look-around. Every search takes time
linear in the text, whatever the pattern, which is why those two are
left out.

| Call | What it does |
|---|---|
| `regex.compile`, `regex.compile_with` | Compile a pattern, with the default options or with given ones. |
| `regex.release` | Give a compiled pattern's storage back. |
| `regex.defaults`, `regex.lean`, `regex.with_size_limit`, `regex.with_cache_size`, `regex.with_anchored`, `regex.with_engine` | Make and change options. |
| `regex.is_match`, `regex.find`, `regex.find_at` | Whether a text has a match, and where the first one is. |
| `regex.captures`, `regex.captures_at`, `regex.group`, `regex.group_count`, `regex.group_named` | Find a match with what each group matched. |
| `regex.walk_start`, `regex.next_match`, `regex.matches` | Walk every match of a text. |
| `regex.replace_all` | Append a text with every match replaced from a template. |
| `regex.words` | A short phrase for a failure of `compile`. |
| `regex.work`, `regex.fallbacks`, `regex.prepared`, `regex.program_size` | Measure a compiled pattern and its searches. |

A match is a `regex.span` holding two `text.position`s, `begins` and
`ends`, into the text searched. It holds positions and not the text, so
slice the text to read it:
`source[text.offset(found.begins)..<text.offset(found.ends)]`.

Nothing is allocated after the pattern is compiled. The compiled pattern
holds the storage its searches use, so every search takes it `inout`,
and one compiled pattern serves one search at a time.

### Compiling

| Call | What it does |
|---|---|
| `compile(memory, pattern)` | Compile `pattern` with the options `defaults()` gives. |
| `compile_with(memory, pattern, settings)` | Compile `pattern` with `settings`. |
| `release(expression, memory)` | Give the storage back to `memory`, the allocator the pattern was compiled with. The pattern is empty afterwards and matches nothing. |

`memory` is any `mem.allocator`: a heap on a hosted target, an arena
over a static buffer in firmware. Both calls give a `regex.regex`, which
the program holds in a `mut` binding, and fail with a
`regex.compile_failure`:

| Failure | When |
|---|---|
| `regex.invalid_pattern` | The pattern is not one the syntax reads: an unclosed group or bracket, a repetition of nothing, a range out of order such as `[z-a]`, an unknown escape or flag, or a class that could match bytes that are not UTF-8, such as `(?-u:\W)`. |
| `regex.unsupported_pattern` | The pattern writes a backreference such as `(a)\1` or a look-around such as `a(?=b)`, or names a Unicode property that `core/unicode` holds no table for, such as the script in `\p{Greek}`. |
| `regex.pattern_too_large` | The pattern compiles to more than the options' size limit, or nests groups or brackets more than 64 deep, or counts a repetition past 100,000, as `a{100001}` does. |
| `regex.unicode_unavailable` | The pattern needs Unicode's tables and was compiled with `lean` options. |
| `mem.out_of_memory` | The allocator could not give the storage. |

### Options

A `regex.options` value says how a pattern is compiled. Start from one
of two, and change it with the `with_` calls, each of which returns the
changed options:

| Call | What it does |
|---|---|
| `defaults()` | The usual options. They use `core/unicode`'s tables for `\w`, `\d`, `\s`, `\b`, `\p` and `(?i)`. |
| `lean()` | The same without Unicode's tables, so a program that compiles only with these links none of them. A pattern that needs them fails with `unicode_unavailable`. |
| `with_size_limit(settings, limit)` | Set the size limit, counted in the instructions and edges of the compiled program. It bounds a compiled pattern's storage, and so the time a search takes for each byte of text. The limit is 250,000 unless set. |
| `with_cache_size(settings, bytes)` | Set the bound on the lazy DFA's caches, in bytes, which `compile_with` allocates. It is 512 KiB unless set. Below a few kilobytes the DFA is not used at all. |
| `with_anchored(settings)` | Anchor every search: a match must begin where the search does, at the text's start or at `find_at`'s position, and in a walk each match must begin where the one before it ended. |
| `with_engine(settings, which)` | Ask for one engine, for tests and measurement. See [Engines and linear time](#engines-and-linear-time). |

Under `lean()` a pattern can still use the classes by asking for their
ASCII meanings with the flag `(?-u)`: `(?-u)\w\d\s\b(?i)k` compiles with
no tables. Firmware usually wants `lean()` and a small cache, as the
first example below has them.

### The syntax

A pattern means what it means to Rust's `regex` crate:

- A match is leftmost-first: of the matches that begin earliest, the one
  the pattern prefers, an alternation's earlier branch before a later
  one.
- Patterns are in Unicode mode unless they say otherwise: `.` and a
  class match whole scalars, and `\w`, `\d`, `\s`, `\b` and `(?i)` have
  their Unicode meanings.
- The flags are `i`, `m`, `s`, `U`, `u`, `x` and `R`, written `(?i)` or
  around a group as `(?i:...)`, and turned off after a `-`.
- A group is named as `(?P<name>...)` or as `(?<name>...)`.
- A bracketed class takes the set operations `&&`, `--` and `~~`, and
  the POSIX classes such as `[[:alpha:]]`.
- `\p{...}` names a general category or a group of them, by short or
  long name, or one of the binary properties `core/unicode` has:
  Alphabetic, White_Space, Uppercase, Lowercase, Cased and
  Case_Ignorable. Case, spaces, underscores and hyphens in the name are
  ignored, so `\p{L}`, `\p{Letter}` and `\p{letter}` are one.
- The word looks are `\b`, `\B`, `\b{start}` or `\<`, `\b{end}` or
  `\>`, `\b{start-half}` and `\b{end-half}`.

A failure has its words from `regex.words(problem)`, a short phrase as
`failure.words` gives for the rest of the library, whose `failure.reason`
does not hold these atoms.

### Searching and groups

| Call | What it does |
|---|---|
| `is_match(expression, haystack)` | Whether the pattern matches anywhere in `haystack`. |
| `find(expression, haystack)` | The leftmost-first match, or `mem.not_found`. |
| `find_at(expression, haystack, start_at)` | The leftmost-first match that begins at or after `start_at`, a scalar's start in `haystack`, or `mem.not_found`. The text before `start_at` still counts for the looks: `\b` and `^` see it. |
| `captures(expression, haystack)` | As `find`, keeping what each group matched for `group`. |
| `captures_at(expression, haystack, start_at)` | As `find_at`, keeping the groups. |
| `group(expression, index)` | What group `index` matched in the last search that kept groups, as a `span`. Group 0 is the whole match. It fails with `mem.not_found` when the group took no part in the match, when there was no match, and when the pattern has no such group. |
| `group_count(expression)` | How many groups the pattern has, counting group 0: one more than its capturing groups. |
| `group_named(expression, name)` | The number of the group that `name` names, or `mem.not_found`. |

The groups `group` gives are those of the last search, so read them
before searching with the same pattern again. `find` and `find_at` keep
none.

### Walking every match

| Call | What it does |
|---|---|
| `walk_start()` | A `regex.cursor` before a text's first match. |
| `next_match(expression, haystack, at, groups)` | The match after the cursor `at`, moving `at` past it, or `mem.not_found` when there are no more. With `groups` true the match's groups are kept for `group`. |
| `matches(addr expression, haystack)` | Every match in order, as `next_match` finds them, for a `for` loop. |

Matches do not overlap. An empty match right where the previous match
ended is passed over, so `a*` over "aab" gives "aa" and then the empty
match at the end, and nothing between them.

The `for` form is the short one:
`for found in regex.matches(addr pattern, haystack) do`, where each
`found` is a `span`. The walk searches through the pointer as it goes,
so do not use the pattern for anything else inside the loop. It keeps no
groups; a loop that wants them calls `next_match` with `groups` true.

### Replacing

`replace_all(expression, haystack, template, into)` appends `haystack`
to the `text.builder` `into` with every match replaced by `template`,
and returns how many matches there were. The matches are those a walk
finds. It appends the whole result or nothing: on `mem.out_of_memory`,
its only failure, `into` holds what it held before.

In the template:

| Written | Stands for |
|---|---|
| `$1`, `${1}` | What group 1 matched, and so for each number. `$0` is the whole match. |
| `$name`, `${name}` | What the group of that name matched. |
| `$$` | A `$`. |

Without braces the name is the longest run of letters, digits and `_`
after the `$`, so `$1a` names a group called `1a`, where `${1}a` is
group 1 and then an `a`. A group that took no part in the match, or that
the pattern does not have, is empty. A `$` before anything else stands
for itself.

### What it leaves out

- Backreferences and look-around, which no engine matches in linear
  time. They fail with `unsupported_pattern`.
- Scripts, such as `\p{Greek}`, and every other property `core/unicode`
  holds no table for: the Emoji properties, Math, and the grapheme, word
  and sentence break properties as classes. They fail with
  `unsupported_pattern` too.
- Texts that are not UTF-8, and classes that could match part of a
  scalar.
- Several patterns searched as one set, match kinds other than
  leftmost-first, a search that stops before the text's end, and a line
  terminator other than `\n`, or `\r\n` under the flag `R`.
- Patterns compiled when the program is built. Landin runs nothing at
  compile time, so a pattern is compiled each time the program runs.

### Engines and linear time

A compiled pattern is a program over the text's bytes, and several
engines can run it. `compile` prepares those that suit the pattern, and
each search uses the cheapest that can answer it, as RE2 and Rust's
`regex` do:

| Engine | `regex.engine` | What it does |
|---|---|---|
| Pike VM | `pike_vm` | Runs every thread of the program in step over the text. It answers every search and finds the groups, and is the slowest. |
| Lazy DFA | `lazy_dfa` | Finds where a match ends, and run backward over the reversed pattern, where it begins. It builds its states as a search needs them, in a cache of bounded size. |
| One-pass DFA | `one_pass_dfa` | Finds the groups of a match in one pass, for a pattern in which the next byte always decides the one way on, as in `a[bc]d`, and not where one branch's text begins another's, as `a` begins `ab`. |
| Literal prefilter | `literal_prefilter` | Skips to where a match can begin, for a pattern whose every match begins with one of a few fixed texts, as `(?i)hello` does. |

The lazy DFA clears its cache when it fills. It gives a search up to the
Pike VM when that happens too often, and when a Unicode word boundary
meets a byte past ASCII. The answer is the same either way; only the
time differs.

The options' engine is `regex.automatic` unless `with_engine` sets one
of the four above. An engine that was asked for and cannot answer a
search leaves it to the Pike VM.

A search takes time linear in the text: at most the text's length times
the compiled program's size, which the size limit bounds. That holds for
patterns such as `(a*)*b` that take a backtracking engine exponential
time.

The bound is for one search. Walking every match of a text, with
`next_match`, `matches` or `replace_all`, can take time quadratic in the
text for some patterns, as it can in RE2 and in Rust's `regex`. With
`a+b|a` over a long run of "a", each match is one "a", and each search
first reads to the end of the text looking for a `b`.

Four calls measure a compiled pattern, for tests and tuning:

| Call | What it gives |
|---|---|
| `program_size(expression)` | The size of the compiled program, in the instructions and edges the size limit counts. |
| `prepared(expression)` | Three `bool`s, `lazy`, `one_pass` and `literals`: which engines were prepared beside the Pike VM. |
| `work(expression)` | A count of the work the pattern's searches have done since it was compiled: the threads the Pike VM stepped, the bytes the DFAs and the prefilter read, and the instructions the lazy DFA's new states reached. |
| `fallbacks(expression)` | How many searches the lazy DFA has left to the Pike VM since the pattern was compiled. |

### Conformance and size

The fixtures are the `regex-*` ones under
`compiler/tests/fixtures/runtime/`, and they run on every hosted target:

- `regex-rust-suite` runs the cases of the test suite of Rust's `regex`
  crate, release 1.12.2, that this module can state, comparing every
  match and its groups. `scripts/regex_tests.py` writes them from the
  pinned crate archive, and the header of the fixture's `cases.ldn`
  counts those taken and those left out of the suite's 1,184. The ones
  left out are sets of patterns, other match and search kinds, bounds,
  line terminators, texts that are not UTF-8, the cases of `regex-lite`,
  and the properties listed above as left out.
- `regex-engines-agree` checks the lazy DFA, the one-pass DFA and the
  literal prefilter against the Pike VM, every match and group, over
  patterns and texts from a seeded generator.
- `regex-linear-time` searches patterns that are exponential for a
  backtracking engine, or for a DFA built in full, over a text and over
  one twice as long, and holds the work `regex.work` counts to linear
  growth.

A program that compiles a pattern links the parser, the compiler and
every engine: about 140 KB of Thumb code at `size/auto`, even under
`lean()`. That is past the 32 KiB Cortex-M0 profile, which records it as
a size limit, so firmware runs `regex-linear-time`, over shorter texts,
and the first example below on the Cortex-M7 corpus lane, whose map has
4 MiB. Both compile with `lean()` into an arena over a static buffer.

`core/unicode` gives a class its scalars a run at a time, through
`unicode.category_run_end` and `unicode.property_run_end`, so compiling
`\p{L}` or `\w` takes a few thousand steps and not one for each scalar.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-regex/main.ldn)

The program compiles `(?<key>[a-z]+)=([0-9]+)` with `lean()` options and
a 2 KiB cache into an arena, reads a match and its numbered and named
groups, counts the matches with `for`, and replaces each from the
template `$2:${key}`. It runs on the Cortex-M7 corpus lane as on the
hosted targets.

[Executable example](../compiler/tests/fixtures/runtime/regex-api/main.ldn)

The program runs over a hosted heap. It shows a pattern for each failure
of `compile`, the forms of a replacement template and what a missing
group gives, a walk's empty matches, a search from a position, an
anchored walk, and Unicode classes and case.

## core/io

Concepts for reading, writing, files and the process, and `world`, which composes them; beside them directories, running programs, entropy, terminals and the rest of the file system; the memory world, a formatted write, a buffered writer and a line reader. Time is `core/time`, the network `core/net`, and fakes of a system's providers `core/io/fake`.

The capabilities are concepts, and a program names only the ones it uses:

| Concept | What it gives | Part of `world` |
|---|---|---|
| `reader`, `writer` | `read`, `write`, `write_some` | yes |
| `files` | `open_read`, `open_write`, `same_file`, `close` | yes |
| `process` | the standard streams `input`, `out` and `err`, the arguments and the program's name | yes |
| `directories` | listing, making and removing directories | no |
| `environment` | the process's variables | no |
| `programs` | running other programs | no |
| `file_system` | opening with options, renaming, status, temporary files and the rest | no |
| `terminals` | asking whether a stream is a terminal, and its size | no |
| `entropy` | `fill_random` | no |

The table below shows typical use, as in the tour's first program:

- Every call takes `host`, the handle `blocking.new()` makes in
  [hosted/blocking](../hosted/blocking). A hosted program imports that
  module beside `core/io`.
- A call written with `try` is in a function that can fail. `main` cannot
  fail, so it handles each failure with `else` instead, as the program at
  the end of the page does.

| Task | Calls |
|---|---|
| Print a formatted line | `try io.write_format(host, io.out(host), "{} of {}\n", [any(addr done), any(addr total)])` fills each `{}` with a value and writes the line. |
| Print many lines | `mut out := io.buffered_over(host, io.out(host), storage)` makes a buffered writer over your buffer, an array such as `mut storage: [4096]u8 = zeroed`. `defer io.flush(out) else none` writes what waits on the way out. `try io.format(out, "{} of {}\n", [any(addr done), any(addr total)])` fills each `{}` with a value. |
| Print bytes as they are | `try io.put(out, "done\n")`, through the same writer. |
| Write straight to a stream | `io.write(host, io.err(host), bytes)` writes all the bytes, or fails with `io_failed`. |
| Get an argument | `path := try io.argument(host, 0)` lends the first argument after the program's name as an OS string, or fails with `mem.not_found`. `io.arguments_length(host)` counts the arguments. |
| Read a file line by line | `file := try io.open_read(host, path)` opens it. `mut lines := io.lines_over(host, file, buffer)` makes a line reader over your buffer. `item := try io.read_line(lines)` gives each line in `item.bytes` until `item.at_end`. `try io.close(host, file)` closes the file. |

### Providers

Use the smallest concept a consumer needs.

A provider is a handle passed by value, `host` in every signature. Using
a handle locks nothing, so a program and its logger write through one
handle, and two lent arguments and a query are live at once.

An erased capability is built from the address of a handle binding:
`any(addr host)`.

- It is itself a provider of its concept and of every concept that
  concept builds on (D492). So an `any io.world` or an `any net.network`
  goes as it is, with no adapter, to `io.buffered_over`, `io.lines_over`
  or any function generic over a writer or a reader.
- It converts to an `any` of each concept its own builds on (D1949), so
  an `any io.world` is passed where an `any io.writer` is wanted. It
  converts to no other `any`.

Providers retain authority over files and arguments.

`process` lends the three standard streams, `input`, `out` and `err`, and
the argument table, as in `io.out(host)`. `io.program_name(host)` lends
the name the program was run by, C's `argv[0]`, which no argument index
reaches. It is often the path the program was started by, but it is
whatever the parent chose. So it is the name for a usage line, or for
starting the program again through `find_program`, and not proof of
where its file is. Standard input is read through
`reader` like any file, and a read of zero bytes into a nonempty buffer
is its end.

A path and an argument are both OS strings, `text.os_string`, so an
argument passed on as a path is never converted.

### The memory world

`memory_over` makes the memory world, firmware's own:

- It takes each argument as its bytes and lends it back as an OS string,
  so an argument table can be static data.
- It fills the caller's `memory_space`, whose limits and counters stay
  readable and settable.
- All storage stays with the caller, the bytes its standard input reads
  among them.

Its directories are its slots' names before a `/`, so it lists them and
reports their sizes but changes nothing.

It behaves so that a test gets the same answer every run:

- Files must already be in its table. Opening one for writing truncates
  it, and reads stop at a file's initialized length.
- `write` and `write_some` keep the blocking provider's contract, which
  [hosted/blocking](../hosted/blocking) describes.
- The read and write limits cut each transfer into chunks.
- `fail_read_at`, `fail_write_at` and `fail_close_at` fail the call with
  that one-based count: 1 is the first read, and 0 never fails. Together
  with the limits, they make short reads, partial writes and failed
  cleanup reproducible.
- A zero read limit with data still unread is an error, not the end of
  the input.
- `written` and `written_errors` lend what was written to standard output
  and standard error.
- Its arguments, like the system provider's, never include the program's
  own name, `argv[0]`. It has no name unless `memory_named(world, name)`
  gives it one, which `program_name` then lends.

### Directories

`directories` is a fifth concept beside the four, and not part of
`world`: a program that lists, makes or removes directories names it as
well.

`open_directory` takes a buffer from the caller and returns an open
`directory`. The caller passes that value `inout` to `read_entry`, which
refills the buffer as entries are read.

- Each entry's name is an OS string that need not be UTF-8, lent from
  the directory until the next read. The compiler refuses a name kept
  past that read [0800], so a program copies the names it keeps.
- The entry read after the last one has `at_end` true, and its name is
  empty.
- `.` and `..` are never listed, and the order is the system's.
- `entry_size` asks the open directory for an entry's size by name, as a
  `u64`. It does not follow a symbolic link.

`make_directory`, `remove_file` and `remove_directory` change the tree:

- A missing path is `mem.not_found`, and so is a path through or to something
  that is not a directory.
- A name already taken is `already_exists`.

Close a directory through the provider that opened it. A directory
dropped unclosed keeps what its provider holds for it until the process
ends.

### The environment

The environment is a concept of its own, `environment`, outside `world`.
So a provider without an environment carries none of it, and neither does
a firmware image that never asks for one.

- `variables_length` counts its variables.
- `variable` lends the one at an index, a `text.os_variable` of a name and
  a value.
- `variable_named` lends the value of the first variable with a name,
  compared as bytes, or reports `mem.not_found`.

Names and values are OS strings that need not be UTF-8, lent from the
provider for as long as the process lives.

The environment is read-only. A process does not change its own
environment, which is not safe beside threads. It gives a child the
environment it builds instead.

`variables_over` makes a `memory_variables`: an environment provider over
a table of `NAME=value` byte strings, which firmware can declare as data.

### Running programs

`programs` is a seventh concept, outside `world`, for running other
programs.

`spawn` starts the program at a path, an OS string:

- The path is never looked up on a search path or handed to a shell.
  `find_program`, below, looks a name up.
- The program sees the arguments after its own name, and gets exactly the
  variables the caller builds.
- A missing program is `mem.not_found`, and one the caller may not run is
  `no_access`. On any failure no child exists.

Each of the program's three standard streams is connected as
`child_streams` says:

| Choice | The child's stream is |
|---|---|
| `inherited` | the parent's own, and closed when the parent has it closed |
| `discarded` | connected to nothing |
| `piped` | a pipe whose other end the parent holds |

`inheriting`, `capturing` and `discarding` are the common three
combinations.

`spawn_in` is `spawn` with one more argument before the path, a working
directory for the child:

- The child changes to the directory before its program runs, so a
  relative path is found from there, as `env -C` finds one.
- The parent's own directory never changes.
- A missing directory is `mem.not_found`. So is an empty one, which names
  none. One the caller may not enter is `no_access`.

`find_program(host, name, search, buffer)` finds a program by name as a
shell does, without starting it, and puts its path in the buffer for
`spawn`:

- `search` is a `PATH` value, which `variable_named` reads. Its entries
  divide at `:`, or `;` on Windows.
- The first entry holding an executable regular file of that name wins.
  `executable` is the `status` flag below.
- An empty entry is passed over, never read as the current directory.
- A name holding a `/`, or on Windows a `\` or a drive, is checked where
  it is, not searched for.
- On Windows a name whose last part has no extension is looked for with
  `.exe` after it, as `CreateProcessW` looks for it.
- Nothing found is `mem.not_found`; a path too long for the buffer is
  `io_failed`.

It works over `file_system`, so the volume fake's executable nodes are
what it finds in a test.

`spawn` returns a `child`: a value the caller keeps, whose fields are the
provider's. These calls take it:

- `write_child` writes to its piped input, and `close_input` closes that
  input, so that the child reads to its end.
- `read_child` reads its piped output and errors together. It waits until
  either has something and says which it read, so a child that writes
  more than a pipe holds to both never waits on a full one.
- `wait` closes every pipe the child still has, waits for the child, and
  reports how it ended. The `ending`'s variant part is `exited` with a
  code, or `signalled`, ended from outside, whose detail is the
  provider's. `wait` consumes the child.

A child never waited for keeps what its provider holds for it until the
process ends. Close a child's pipes only through `close_input` and
`wait`, never through `files`.

`write_child`, `read_child` and `wait` wait, while `spawn` and
`close_input` do not. So, like reading and writing, `programs` comes from
a provider that waits: `hosted/blocking` or `hosted/events`, not
`hosted/system`.

Such a provider's pipes are its own files, which its `reader` and
`writer` also take, a line reader over a child's output among them. The
memory world's are not.

`scripted_over` makes `scripted_programs`: a programs provider beside a
memory world, over the caller's `scripted_program` records. It is a
provider of its own, so a world that runs no program carries none of its
code. A scripted program at a given path and in a given directory, which
is its record's `directory` and is empty for the parent's own:

- writes the given output and errors when it starts, as each stream
  says, an inherited one into the world's own standard output or error;
- keeps what its parent writes to its piped input with `write_child`;
- records how many arguments and variables it was given and how often it
  started;
- ends as it is told.

### The rest of the file system

The rest of the file system is `file_system`, a concept of its own beside
`files` and `directories` and outside `world`, so an image that never
renames or truncates carries none of it.

`open_file` opens a path as an `open_options` record says:

| Option | Meaning |
|---|---|
| `read`, `write` | open to read, to write, or both |
| `append` | every write goes at the end |
| `create` | create the file when it is missing |
| `exclusive` | with `create`, refuse a name that is taken, with `already_exists` |
| `truncate` | cut the file to nothing |

`updating`, `appending` and `creating` are the common three.
`valid_options` says whether an open can have the options at all, and
`io_failed` answers one that cannot.

The concept's other calls:

| Call | What it does |
|---|---|
| `rename` | Give a file a new name in one step, replacing a file already called that. |
| `status_of`, `status_of_file` | A path's or an open file's `status`. |
| `set_read_only` | Make a file read-only, or writable by its owner again. |
| `synchronize` | Have what the provider holds of a file written where it lasts, its data alone when asked. |
| `truncate` | Give a file a size, cutting it or extending it with zeros. |
| `read_at`, `write_at` | Read and write at an offset. |
| `make_temporary` | Make and open a new file under a fresh name. |
| `current_directory` | Put the working directory's path in the caller's buffer. |

`rename` is how a whole file is replaced: write a `make_temporary` file
beside it, `synchronize` it, close it and rename it onto the old one.

- A missing name is `mem.not_found`.
- A rename across file systems is `io_failed`, and so is a rename of a
  directory onto a file or of a file onto a directory.

A `status` holds the size, its `entry_kind`, the last modification as a
`wall_time`, whether it is `read_only`, and whether it is `executable`.
An executable entry is a regular file that some permission bit lets
someone run. Windows has no such bit, so there it is a regular file
whose name ends in `.exe` or `.com`. `status_of` follows a final
symbolic link or not, as asked.

`platform/posix` uses the name differently: its `status_of` takes an open
descriptor, as `status_of_file` does here, and its call for a path is
`status_at`.

A read-only file refuses an open for writing with `no_access`. The
exception is a process the system lets past every permission, as POSIX's
root.

`read_at` and `write_at` do not move the position `read` and `write` use.

- A read at or past the end reads nothing.
- A write past the end leaves zeros between, a hole a file system may
  keep without storing it.
- Never write at an offset to a file opened to append.

`make_temporary` creates the file in a directory under a name no other
file has: `.tmp-` and sixteen hexadecimal digits, drawn from an `entropy`
the caller passes. In an ordinary program that is the hosted provider
itself: `io.make_temporary(host, host, directory, buffer)`.

- The file is created exclusively, readable and writable by its owner
  alone.
- A name already taken is tried again with fresh bytes, up to
  `temporary_tries` times.
- Nothing removes it: rename it into place or remove it.
- `temporary_path` is the name it tries, for a provider in another
  module.

Nothing here changes the working directory, since it is the whole
process's.

### Terminals

Terminals are `terminals`, one more concept outside `world`.

- `is_terminal` says whether a stream is one.
- `window_size` gives its `window`, rows and columns, or
  `not_a_terminal`.

### Entropy

`entropy` is another concept outside `world`, with one entry:
`fill_random` fills all of a buffer with unpredictable bytes or fails
`io_failed`.

Its fake is `fake.entropy`, made by `entropy_over` over the caller's
bytes. It gives those bytes in order, and a request for more than is left
fails, so a program that seeds itself from entropy runs the same in every
test. It runs on Cortex-M0.

### A formatted write

`write_format` writes a template and its values to a file in one call:

`io.write_format(host, io.out(host), "{} of {}\n", [any(addr done), any(addr total)])`

- Each `{}` takes the next value, as `text.format`'s does.
- The template is checked against the values before anything is written,
  so a mismatch is `text.invalid_format` and writes nothing.
- The text is formatted into `format_store` bytes on the stack, 128, and
  written whenever they fill and at the end. A line that fits is one
  write, and a value of any length goes out in pieces, so it never
  reports `mem.out_of_memory`.
- A failed write is `io_failed` and may follow partial output, as
  `write`'s may.
- It needs no buffer or flush of the caller's, and works on every target
  that has a writer.

### The buffered writer

A program that writes many pieces to one file gathers them in a buffered
writer, which makes fewer, larger writes. A `buffered_writer` gathers the
writes to one file in a buffer the caller supplies, and hands them to a
writer when the buffer fills or the program flushes it.

| Call | What it does |
|---|---|
| `buffered_over` | Make one from a writer's handle, the file and the buffer. |
| `put` | Write bytes through it, flushing first when they do not fit. Bytes as large as the buffer go straight to the writer. |
| `format` | Format a template straight into its buffer, flushing first when the text does not fit after what waits. |
| `flush` | Write what waits. |
| `buffered_length` | Say how many bytes wait. |

A failed flush reports the writer's `io_failed` and keeps every byte the
writer did not take, so the next flush writes each byte once.

`format` refuses a text larger than the whole buffer with
`mem.out_of_memory`. Its values are `text.formattable`'s types, as
`text.format`'s are: integers, floats, `bool`, `utf8`, `[]u8` and OS
strings, and its placeholders take `text.format`'s specifications.

There are no destructors: bytes still waiting when the program ends are
never written. So flush in two places:

- before every way out, `defer io.flush(out) else ...` being the idiom;
- where the bytes must be out before something else happens.

### The line reader

A `line_reader` reads a file through a buffer the caller supplies and
lends it back a line at a time, as a directory lends its names.

- `lines_over` makes one from a reader's handle, the file and the buffer.
- `read_line` gives the next `line`, its bytes lent from the reader until
  the next read.

What counts as a line:

- A line ends at `\n`, and a `\r` just before it is part of the ending,
  so text written with `\r\n` reads as text written with `\n`.
- A lone `\r` is an ordinary byte, and the last line need not end.
- The end of input is a line that has `at_end`, every time it is asked
  again; an empty line has not.
- A line that does not fit the buffer with its ending is
  `mem.out_of_memory`, and the rest of it is skipped, so the next read gives
  the line after it.

[Executable example](../compiler/tests/fixtures/runtime/library-common-tasks/main.ldn)

The program numbers the lines of the file named on the command line,
reading it through a line reader and printing through a buffered writer.
When the file cannot be read it says why on standard error, in
`failure.words`' phrase, and exits with 1.

## core/io/fake

Fakes of a system's providers for tests that must give the same answer every run and on every target: a file system, a network, a clock, entropy, terminals and signals, each over the caller's records.

Each fake is named one way:

| Part | Name | Example |
|---|---|---|
| its provider type, for what it fakes | the name | `fake.volume` |
| its caller-owned state, declared `zeroed` | the name with `_space` | `fake.volume_space` |
| its constructor, which fills the state and returns the handle | the name with `_over` | `fake.volume_over` |

The fakes are `fake.volume`, `fake.network`, `fake.clock`, `fake.entropy`,
`fake.terminals` and `fake.signals`. `fake.terminals` is the one without a
`_space`: its state is the caller's `screen` records, which
`terminals_over` takes directly. Four of the fakes are described
elsewhere:

| Fake | Described with |
|---|---|
| the clock | `core/time` |
| entropy | `core/io` |
| the network | `core/net` |
| the signals | `core/io/signal` |

The memory world is firmware's own world rather than a fake of a
system's, so it stays in `core/io` as `io.memory`.

### The volume

`volume_over` makes a `fake.volume`: the fake of `file_system`, and of
`reader`, `writer`, `files` and `directories` over the same files. It is
a file system in memory over two things the caller supplies:

- `volume_node` records, each a path, a kind, room for a file's bytes or
  a link's target, and whether a regular file is `executable`;
- a `volume_space` the caller declares `zeroed`.

How it behaves:

- The space time-stamps each change.
- Its `fail_at` fails a chosen call, counting every call of the volume,
  each `read_entry`, `entry_size` and `same_file` among them.
- A node with no path is free for a new file.
- A file grows only into its node's room, and a write that finds none is
  `io_failed`, as a full device is.
- A symbolic link is a node the caller makes, followed where a path is
  followed.
- A node a file is open on cannot be removed or renamed over, where POSIX
  would keep the open file without its name.

The whole volume, which links every entry of its conformances, does not
fit a Cortex-M0 image. Its temporary names and the memory terminals run
there.

### Terminals

`terminals_over` makes `fake.terminals` over the caller's `screen`
records, each a file of a size. Every other file is no terminal.

[Executable example](../compiler/tests/fixtures/runtime/volume-memory/main.ldn)

## core/io/signal

Signals as events: the concept a provider that takes turns supplies when it delivers the system's signals to a fibre that waits for them.

| Call | What it does |
|---|---|
| `signal.watch(host, which)` | Take a signal from the system's default disposition and deliver it as an event from then on. |
| `signal.next_signal(host)` | Wait, taking turns, for the next arrival of a watched signal: a `signal.event`. |
| `signal.stop_watching(host)` | Give every watched signal back to its default disposition, and wake every waiting fibre, whose wait fails `io_failed`. |

A `signal.kind` names a signal portably. An arrival says which kind came
and the number the system gave it:

| Kind | Signal |
|---|---|
| `signal.interrupt` | SIGINT, the terminal's Ctrl-C |
| `signal.terminate` | SIGTERM, a request to end |
| `signal.hangup` | SIGHUP, the terminal gone, or a daemon's cue to reload |
| `signal.child` | SIGCHLD, a child ended, stopped or went on |
| `signal.user1`, `signal.user2` | SIGUSR1 and SIGUSR2 |

How signals are delivered:

- A signal never runs a handler of Landin code. The provider reads it as
  it reads any other event, through signalfd on Linux and kqueue's
  signal filter on Darwin and FreeBSD, and wakes the fibre that waits.
- `signals` refines `fibre.turns`: only a provider whose fibres take
  turns supplies it, so a fibre waiting for a signal lets the others run.
  `hosted/events` supplies it. Over `hosted/blocking` a program cannot
  ask for it, and a signal there keeps the system's default disposition:
  SIGTERM ends the process.
- Each arrival is read once, by one waiter. Two arrivals of one signal
  before it is read may be one event, as the systems keep them.
- A fibre waiting for a signal is stopped as any waiting fibre is, by
  failing its wait: `stop_watching` does that.
- On Linux, watch in the process's first thread. `hosted/events` takes a
  signal there by blocking it in the calling thread, and the first thread
  of a program whose event loop runs on a `hosted/thread` thread would
  still be given the signal and ended by it. `watch` in any other thread
  fails with `io_failed`, and `events.last_errno` reads `EPERM`. On Darwin
  and FreeBSD a watch is the process's, and any thread may make it.

### The fake

`signals_over` makes a `fake.signals` over the caller's `signals_space`
and a `fibre.turns` it waits on. It passes on that provider's `start`,
`finished`, `wait` and `yield`, so it is a provider of turns as the
concept asks.

A test raises a signal into it with `fake.raise(host, which)`, and the
fibre waiting in `next_signal` receives it after its next turn.

- A raised signal nobody watches is counted in `ignored` and dropped,
  where a system would act on it.
- A signal raised again while it waits to be read is one event.
- The fake numbers each signal as Linux does on x86-64 and arm64.
- `raised`, `delivered` and `turns`, the turns its waits took, count the
  rest.

The fake runs on Cortex-M0, over a round of turns.

[Executable example](../compiler/tests/fixtures/runtime/signals-fake-firmware/main.ldn)

## core/time

Spans and instants of time counted in nanoseconds, the wall clock's time, and the monotonic and wall clock concepts.

| Call | What it does |
|---|---|
| `time.now(host)` | Read the monotonic clock: an `instant`. |
| `time.elapsed(earlier, later)` | The span between two readings taken in order. |
| `time.sleep(host, span)` | Sleep for at least a span. |
| `time.milliseconds(n)` | Make a span; `nanoseconds`, `microseconds` and `seconds` too. |
| `time.wall_now(host)` | Read the wall clock: a `wall_time`. |

### Clocks

Time is two concepts outside `world`, so an image that never asks the time
carries neither.

| Concept | Call | Reads |
|---|---|---|
| `clock` | `now`, `sleep` | a monotonic clock, which never goes back |
| `wall_clock` | `wall_now` | the system's UTC time, a `wall_time` of seconds since 1970 and the nanoseconds after them |

`sleep` returns once at least the span asked has passed on that clock,
never sooner.

The system may set the wall clock, so it may go back. Time a task with
`clock`.

### Spans and instants

A reading is an `instant` and a span is a `duration`. Each is a distinct
`u64` of nanoseconds, which holds 584 years.

- `u64(at)` is the count.
- Two of a kind compare with `==`, `<>`, `<`, `<=`, `>` and `>=`, as
  their counts do. Each is `cmp.equatable`, `cmp.hashable` and
  `cmp.ordered` the same way, so a sort orders spans and a map keys by
  instants with no evidence of the program's.
- Neither has arithmetic of its own. `elapsed` is the span between two
  readings taken in order, trapping if the second is the earlier, and
  `later` gives a deadline.
- `nanoseconds`, `microseconds`, `milliseconds` and `seconds` make a span,
  trapping past 584 years, and `in_milliseconds` rounds one down.

There is no floating point, and the arithmetic is the same on every
target. Calendars, time zones and formatting a date are not here.

### The fake clock

`fake.clock` is made by `clock_over`, over the caller's `clock_space`, or
by `clock_over_beside`, beside a fake network.

- It moves only when a test says: `advance` moves both its clocks, and a
  `sleep` advances them by exactly what it asks and returns at once.
- Made by `clock_over_beside` beside a network that takes turns, a
  `sleep` takes turns instead and the clock moves only while every other
  fibre waits.
- The test may set either reading through the state, and the state
  counts readings, sleeps and the time slept.

It runs on Cortex-M0.

[Executable example](../compiler/tests/fixtures/runtime/clock-manual/main.ldn)

## core/net

The network concept, whose connections are readers and writers, and internet addresses with their text.

| Call | What it does |
|---|---|
| `net.connect`, `net.connect_within` | Connect to an address, the second within a limit. |
| `net.listen`, `net.accept` | Listen at an address and take the next connection. |
| `net.send`, `net.receive` | Send and receive on a connection. |
| `net.open_datagram`, `net.send_to`, `net.receive_from` | A UDP socket and its datagrams. |
| `net.parse_address`, `net.append_address` | Read and write `192.0.2.1:80`, `[2001:db8::1]:80` and `[fe80::1%eth0]:80`. |
| `net.close` | Close a socket. |

### Sockets

The network is one more concept outside `world`, `network`, so an image
that never connects carries none of it.

It is a reader and a writer of its own sockets as well:

- A connection is read and written through `read` and `write`, a line
  reader and a buffered writer among them, whose failures are
  `io_failed`.
- `send` and `receive` say more: `timed_out` when a limit has passed and
  `disconnected` when the peer has gone.
- A `receive` or `read` of zero is the end of what the peer sends.

| Call | Behaviour |
|---|---|
| `listen` | Takes an address and returns a listener. Port 0 asks for a free port, which `local_address` then gives. It may take an address its own closed connections still hold, never one another socket listens at, which is `address_in_use`. |
| `accept` | Takes the next connection. |
| `connect` | Makes one: `refused` where nothing listens and `unreachable` where no route leads. |
| `connect_within` | Makes one as `connect` does, or fails `timed_out` once its limit has passed with no answer, as from a peer that never answers; zero is no limit. |
| `open_datagram` | Binds a UDP socket. |
| `send_to` | Sends a datagram whole. |
| `receive_from` | Gives the next datagram with its `sender`, cutting one longer than the buffer. |
| `shutdown` | Stops `receiving`, `sending` or `both_directions`. |
| `peer_address` | Names a connection's other end. |
| `set_timeouts` | Limits how long a receive, an accept and a send wait; zero for no limit. |
| `set_no_delay` | Turns Nagle's algorithm off. |
| `close` | Closes a socket. |

An address the system does not have, a zone that names none of its
interfaces, or a family it lacks, is `address_unavailable`.

Every call waits as a blocking socket does. `connect` waits as long as
the system does, which is over a minute on Linux; `connect_within` gives
a connection a limit of its own.

One thread can connect to its own listener and send before it accepts,
since the system completes the handshake, but a receive waits for its
peer.

### Addresses

An `address` is a family, `ipv4` or `ipv6`, sixteen bytes, a port and an
IPv6 address's zone.

- `loopback`, `unspecified`, `ipv4_address`, `ipv6_address` and
  `with_port` make one, and `with_zone` gives an IPv6 one a zone.
- `same_address` and `is_unspecified` compare. An address is
  `cmp.equatable` as `same_address` compares, zone included, and
  `cmp.hashable`, so a map keys by addresses.
- `parse_ip` reads `192.0.2.1`, `2001:db8::1` or `fe80::1%eth0`, and
  `parse_address` reads `192.0.2.1:80`, `[2001:db8::1]:80` or
  `[fe80::1%eth0]:80`. Both refuse a leading zero, an empty zone, one
  longer than `zone_room`'s 15 bytes, a zone after an IPv4 address and
  anything else with `invalid_address`.
- `append_ip` and `append_address` write them back as RFC 5952 does: lower
  case, the longest run of zero groups shortened, and an IPv4-mapped
  address in dotted decimal, with the zone as it was written.
- An address is `text.formattable`.

A zone names the interface a link-local address is reached through: its
name, `eth0`, or its number in decimal, `2`.

- The address keeps the zone as text, `zone`'s bytes before the first
  zero, `zone_length` of them, so reading and writing an address needs no
  system.
- The hosted provider looks a name up when the address is used. It names
  the interface again in an address it reads back, a peer's among them.

Nothing here resolves a name.

### The fake network

`network_over` makes a `fake.network` over two things the caller
supplies:

- `network_socket` records, each made by `socket_over` from a buffer that
  is its receive buffer;
- a `network_space` whose counters a test reads.

It is a machine of loopback addresses:

- a connection and a datagram arrive at once, whole and in order;
- a datagram no socket takes is lost and counted;
- a call that would wait answers `timed_out` at once, since in one thread
  with no scheduler nothing else runs that could end the wait.

`network_over_turns` makes the same network over a `fibre.turns` the
caller gives it, for a test whose client and server are fibres:

- a call that would wait takes a turn instead, so the other fibres run,
  and looks again;
- it answers `timed_out` only after a whole round in which nothing moved
  anywhere in the network, so nothing it waits for arrived, and never
  while a fibre sleeps on a clock `clock_over_beside` made beside it;
- a call whose socket another fibre closed, or shut for what it waits
  for, while it waited fails `io_failed` when it wakes.

`accept`, `send`, `receive`, `receive_from`, `read`, `write` and
`write_some` are its calls that may wait, and so switch; the others never
do.

`moves` counts what changed something a call may wait for, `turns` the
turns its calls took and `sleepers` the fibres sleeping beside it.

`clock_over_beside` makes a `fake.clock` whose `sleep`, beside a network
that takes turns, takes the network's turns. The clock moves only after a
whole round in which nothing in the network moved, a millisecond at a
time, so sleepers wake in the order of their deadlines while the other
fibres run first (D493).

A test may take IPv6 away with `without_ipv6` and fail a call with
`fail_at`.

[Executable example](../compiler/tests/fixtures/runtime/network-fake-turns-exchange/main.ldn)

Addresses are read and written on Cortex-M0 as on a hosted system.

[Executable example](../compiler/tests/fixtures/runtime/network-addresses/main.ldn)

## core/diag

Bounded diagnostic storage and streaming diagnostics through a writer capability.

Severity is the atom set `warning | error`, so a `match` over it is
checked for both.

| Log | Made by | Behaviour |
|---|---|---|
| bounded | `diag.new` | Stores at most its fixed number of entries, and drops messages exceeding 256 bytes. It counts dropped entries and remembers error diagnostics even when they are dropped. |
| streaming | `diag.stream` | Holds a copy of an erased writer and a file. Writes each note as `W:` or `E:`, the decimal byte offset, `:` and the message, and propagates I/O failure. |

[Executable example](../compiler/tests/fixtures/runtime/library-shared-diag/main.ldn)

## core/failure

Words for a person for every failure atom a `core` module raises: a short English phrase each.

`failure.words(problem)` gives the phrase for any of the 29 atoms in
`failure.reason`, every atom a `core` module fails with. So a call's
`else (problem)` passes its failure straight on, whatever subset it
declares.

A phrase is lower case with no final stop, and reads after a subject and
a colon: `settings: not found`. It is static text, borrows nothing and
never changes with a locale.

A set that also holds an atom of the program's own does not widen to
`failure.reason`, and a `match` arm of `_` does not narrow it. So such a
program names each library atom it passes on.

`platform/posix`'s errnos have words of their own in `posix.words`, which
takes an errno and nothing else. `hosted/system` has `system.reason`, an
errno or one of the library's failures, and `system.words`, which passes
each to its own `words`, so a program over both layers words either with
one call.

Nothing is linked into a program that never calls `words`. One that does
carries every phrase, about 2 KB of code and text on Cortex-M0: 1,852
bytes at the default `size` objective (D1950).

[Executable example](../compiler/tests/fixtures/runtime/failure-words-report/main.ldn)

## core/tree

An append-only store of named leaves and branches addressed by node identifiers.

- A branch names a contiguous range of previously published nodes.
- Leaf totals are precomputed, so queries use constant stack and time.
- Shared children count once for each incoming path.
- Names borrow their UTF-8 backing; releasing the tree frees node
  storage, not names.
- `for id in t` walks every node's identifier in the order the nodes were
  added, so each branch comes after its children.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-tree/main.ldn)

## core/arena

A monotonic allocator over caller-supplied bytes.

| Call | What it does |
|---|---|
| `arena.over` | Fill the caller's `arena.space`, declared `zeroed` beside the backing, and return the handle, an `arena.arena`, `from` it. |
| `arena.over_unchecked` | The same over local backing, with an explicit lifetime opt-out. |
| `arena.release` | Give every allocation back at once. |
| `arena.length` | Count the bytes handed out, padding included. |

With `over_unchecked`, the caller ends every allocation before that
backing ends.

An individual free reclaims nothing. The arena resizes its latest block
in place and moves any other. It allocates no backing of its own.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-arena/main.ldn)

## core/pool

A reclaiming allocator over fixed-size slots and caller-supplied bookkeeping.

`over` fills the caller's `pool.space` and returns the pool's handle. The
pool allocates no backing storage of its own. Keep both payload backing
and metadata alive while allocations exist.

- It reuses the lowest free slot.
- It rejects malformed frees without reclaiming a slot.
- A zero-byte allocation still occupies one slot.
- A growth and a resize keep the block in its slot, to any extent the
  slot holds, and refuse a larger one, since no slot is larger. So a list
  over a pool grows in place until its slot is full.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-pool/main.ldn)

## core/region

An allocator scope that records allocations through a parent and releases them together.

`over` makes a region's handle over the caller's ledger,
`space(capacity)`, and a copy of the parent's handle:

| Capacity | Ledger |
|---|---|
| zero | grows through the parent; `growing_space` names it |
| positive | a fixed caller ledger |

Individual frees do nothing, and nothing says so at the call. Every
allocation consumes a ledger entry until release, whether or not its
payload is still live. So:

- Code moved from the heap onto a region runs unchanged, but keeps every
  temporary it frees until the region ends. What a `vec.release` frees is
  one, and a list made afresh each round of a loop is another.
- A region over a region reclaims nothing before the outer one is
  released.

For a shorter lifetime inside a region, make a [zone](../core/zone) over
the region's parent instead, and reset it at the end of each round.

A resize of the newest allocation goes to the parent, and its entry
follows the block. A resize of any other block moves it into a new entry,
and the old one is freed at release.

`release` takes the ledger and the same parent and frees payloads in
reverse order. It is refused while the region's handle is still used.
End all payload uses before releasing the region.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-region/main.ldn)

## core/zone

A bump allocator that grows by taking blocks from a parent allocator.

| Call | What it does |
|---|---|
| `zone.over` | Fill the caller's `zone.space`, declared `zeroed`, and return the handle, a `zone.zone(provider)`, `from` it. The handle holds a copy of the parent's handle. Nothing is allocated. |
| `zone.reset` | Give every allocation back at once, through the handle. Every block except the newest goes back to the parent. |
| `zone.release` | Take the space and the same parent and return every block. It is refused while the handle is still used. |

The zone hands out the newest block's bytes in address order. When they
run out, it takes a new block from the parent, twice as large as the
last. A request too large for that block, or a parent that refuses it,
gets a block just large enough. If the parent refuses that too, the
allocation fails with `out_of_memory` and the zone is unchanged.

An individual free reclaims nothing. Only the latest allocation grows
in place or gives back its tail; growing any other moves it.

The newest block is the largest, and `reset` keeps it. So a loop that
resets the zone after each round settles on one block that holds a
whole round.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-zone/main.ldn)

## core/fault

Deterministic allocation-failure injection over any allocator, with cumulative counters.

`over` wraps a copy of a provider's handle in an `injector` over the
caller's `space`. `permit` replaces the budget without resetting
evidence.

The budget counts delegated attempts, including attempts the inner
provider refuses. So wrapping an arena counts both injected failures and
the arena's own.

- Free calls delegate to the parent.
- An allocation, a resize and a growth in place are each an attempt: each
  spends the budget, and once it is spent the injector refuses without
  asking the parent.
- A refused growth, the injector's or the parent's, leaves the block as it
  was, and the container moves it instead. So a container tested through
  an injector takes the in-place path its provider offers.
- `successes` counts the blocks a delegated allocation or resize gave. A
  growth in place gives none and is counted by `growths`.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-fault/main.ldn)

## core/panic

The compiler's five panic atoms and their shared panic-kind domain.

Checked range, arithmetic and conversion faults, and an unreachable path,
use these atoms.

An entry-module panic handler has the language-specified nonreturning
signature. A panic is distinct from a recoverable allocator or I/O error.

`panic.require(holds)` is C's `assert`: when `holds` is false it stops
the program as a failed check does, and the stop is reported at the line
that called `require`. The compiler fills its `caller` parameter, a
`panic.call_site`, with the place of the call. A check of your own takes
a `caller` parameter of that type too and passes it on,
`panic.require(holds, where: where)`.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-panic/main.ldn)

## core/random

A deterministic generator of pseudorandom numbers, the same sequence for a seed on every target.

| Call | What it does |
|---|---|
| `random.new` | Seed a generator from a `u64`, through splitmix64, as its authors suggest. |
| `random.from_entropy` | Seed one from 32 bytes of any `io.entropy` provider, the hosted system's or a test's scripted bytes. |
| `random.hash_seed` | Draw a map's `cmp.hash_seed` from 16 bytes of an `io.entropy` provider, with no generator involved. |
| `random.next` | Draw 64 bits. |
| `random.next_u32` | Draw the upper 32. |
| `random.below` | Draw a value under a bound, each equally likely. |
| `random.shuffle` | Put a slice in a uniformly drawn order. |

`generator` is xoshiro256** 1.0, Blackman and Vigna's: 256 bits of state
that each draw advances. It is a value the caller keeps and passes
`inout`.

`below` masks to the bound's width and draws again when the value is too
large, so no division is made and no value is favoured. It traps for a
bound of zero.

The generator uses shifts, exclusive ors and additions on `u64`, so a
Cortex-M0 draws what a 64-bit host draws. Its sequences are the reference
implementation's on every target.

It is not cryptographic: its outputs reveal its state. A key, a token or
a password comes from `io.fill_random` directly.

[Executable example](../compiler/tests/fixtures/runtime/random-sequence/main.ldn)

## core/bits

The bit operations of the unsigned integers, integers read from and
written to the caller's bytes in a stated byte order, and the operations
of a set of flags. Nothing allocates.

| Call | What it does |
|---|---|
| `bits.ones`, `bits.leading_zeros`, `bits.trailing_zeros`, `bits.bit_length` | How many bits are set, how many zero bits stand above the highest set bit or below the lowest, and how many bits the value needs. The zero counts are the width for zero, and `bit_length` is 0. |
| `bits.rotate_left`, `bits.rotate_right` | The value rotated by a count of bits, which is taken modulo the width. |
| `bits.reverse_bytes`, `bits.reverse_bits` | The bytes or the bits in the opposite order. |
| `bits.multiply_wide` | The full product of two values as its `high` and `low` halves. |
| `bits.add_carry`, `bits.subtract_borrow` | A sum with a carry in and out, and a difference with a borrow in and out, each a `bool`. |
| `bits.read_u8`, `bits.read_i8` | The next byte, as it is or as two's complement. |
| `bits.read_u16`, `bits.read_i16`, `bits.read_u32`, `bits.read_i32`, `bits.read_u64`, `bits.read_i64` | The next two, four or eight bytes as an integer in a `bits.byte_order`, which is `bits.little` or `bits.big`. |
| `bits.write_u8`, `bits.write_i8`, `bits.write_u16`, `bits.write_i16`, `bits.write_u32`, `bits.write_i32`, `bits.write_u64`, `bits.write_i64` | The same integers written into a `[]mut u8`. |
| `bits.skip`, `bits.take` | Pass over a count of bytes, or take them as a view of the bytes. |
| `bits.read_uleb128`, `bits.read_sleb128`, `bits.write_uleb128`, `bits.write_sleb128` | An unsigned or signed LEB128 integer of up to 64 bits, as DWARF, WebAssembly and protocol buffers write them. A write uses the fewest bytes, from one to ten. |
| `bits.union`, `bits.intersection`, `bits.difference`, `bits.is_empty` | Two whole sets combined, and whether a set has no member. |

The bit operations are generic over the concept `bits.unsigned`, which
`u8`, `u16`, `u32` and `u64` meet. A count is a `u32`. Each operation is
written from shifts and masks, so it gives the same answer on every
target, Cortex-M0 included.

A read or a write takes the caller's bytes and `at`, the offset of the
next byte, and moves `at` past what it read or wrote. Only `at` is passed
`inout`, so a view from `bits.take` is of the bytes themselves and lasts
while reading goes on.

A read with too few bytes left fails `mem.out_of_bounds`, and a write
with too little room left fails `mem.out_of_memory`. A LEB128 integer
with an eleventh byte, or with bits past the 64th, fails
`bits.invalid_varint`; padding up to ten bytes is accepted. A call that
fails moves nothing, so a program may try another reading of the same
bytes.

A set is a packed struct of `bool` [0730], and its type says so with
`is bits.flags ()`. `bits.is_empty` counts the bits no field claims too,
so an image read from a device with a reserved bit set is not empty.

[Executable example](../compiler/tests/fixtures/runtime/bits-byte-order/main.ldn)

## core/math

The functions of C's `<math.h>` that most programs use, over `f32` and
`f64`, written in Landin so that a result is the same on every target,
Cortex-M0's soft float included: the same bits, save which NaN a NaN
result is, which is the target's own.

| Call | What it does |
|---|---|
| `math.sqrt`, `math.cbrt`, `math.hypot` | Square and cube roots, and the hypotenuse without overflow on the way. |
| `math.fma` | `x * y + z` rounded once. |
| `math.exp`, `math.exp2`, `math.expm1` | e or 2 to a power; `expm1` is `exp(x) - 1`, accurate near zero. |
| `math.log`, `math.log2`, `math.log10`, `math.log1p` | Logarithms; `log1p` is `log(1 + x)`, accurate near zero. |
| `math.pow` | A power, with C's special cases. |
| `math.sin`, `math.cos`, `math.tan` | The trigonometric functions of radians, accurate for every argument. |
| `math.asin`, `math.acos`, `math.atan`, `math.atan2` | Their inverses; `atan2(y, x)` is the angle of the point (x, y). |
| `math.sinh`, `math.cosh`, `math.tanh`, `math.asinh`, `math.acosh`, `math.atanh` | The hyperbolic functions and their inverses. |
| `math.erf`, `math.erfc`, `math.gamma`, `math.log_gamma` | The error function and its complement, the gamma function, and the logarithm of its magnitude. |
| `math.floor`, `math.ceil`, `math.trunc`, `math.round`, `math.round_even` | Rounding to an integer; `round` takes a half away from zero, `round_even` to the even neighbour. |
| `math.remainder`, `math.remainder_nearest` | `x - n * y` for `n` the quotient truncated, as integer `%` does, or rounded to nearest, IEEE's remainder. |
| `math.classify`, `math.is_nan`, `math.is_infinite`, `math.is_finite`, `math.is_normal`, `math.is_negative` | What kind of value a float holds, and its sign bit. |
| `math.abs`, `math.copy_sign`, `math.next_after`, `math.scale`, `math.split`, `math.whole_and_fraction`, `math.min`, `math.max` | The representation: magnitude, sign, the next float, a power of two, the fraction and exponent, the whole and fractional parts, and the lesser or greater, NaN ignored. |
| `math.pi`, `math.tau`, `math.e`, `math.ln_2`, `math.ln_10`, `math.log2_e`, `math.log10_e`, `math.sqrt_2`, `math.sqrt_half` | The constants, as `f64`. |

Every call takes either width: `math.sin(x)` is the `f32` sine when `x`
is an `f32`. A float literal alone is an `f32` [0210], so `math.sqrt(2.0)`
is the `f32` root; write `math.sqrt(f64(2.0))` or pass a typed value for
the `f64` one. A constant converts with `f32()` to the `f32` nearest the
real number.

Each routine's error is stated in its doc comment in units in the last
place of the exact result: zero for the exact routines, the square root
and `fma`, which are correctly rounded; below one for most of the others;
and up to 4.2 for the hyperbolic functions, `erfc`, `log_gamma`, `atan2`
and `hypot` at `f32`, whose methods are msun's and carry its error.
`log_gamma` loses its relative accuracy near the points below -2 where it
is zero. The `math-*` fixtures check each bound on every target against
MPFR's correctly rounded values, and
[the measurements](../compiler/tests/math/README.md) give each routine's
largest error.

The square root and `fma` are the float unit's own instructions where the
target has one, and are computed from the bits where it has none, with the
same results. Results are rounded to nearest; the float unit's other
rounding modes and exception flags are neither read nor set. Nothing keeps
state, and nothing allocates.

On Cortex-M0, a program takes only the routines it calls, beside libgcc's
soft float, which every float program there takes. A routine at both widths
takes from 2.5 KiB at `size/auto` for a root to 13 KiB for a hyperbolic or
error function with the exponentials it calls, and 15 KiB for a
trigonometric function, whose argument reduction is exact for every
argument; [the measurements](../compiler/tests/math/README.md#size-on-cortex-m0)
give each fixture's figures.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-math/main.ldn)

## core/complex

Complex numbers over `f32` and `f64`: a number with a real and an
imaginary part, its arithmetic and its elementary functions, built on
`core/math`. Landin has no operator overloading, so the arithmetic is
named routines.

| Call | What it does |
|---|---|
| `complex.add`, `complex.subtract`, `complex.multiply`, `complex.divide`, `complex.negate` | The arithmetic. |
| `complex.conjugate`, `complex.project` | The conjugate, C's `conj`, and the projection onto the Riemann sphere, C's `cproj`: every infinity becomes +∞ with a signed imaginary zero. |
| `complex.abs`, `complex.arg`, `complex.polar` | The magnitude, by `math.hypot`; the angle in [-π, π], by `math.atan2`; and both together. |
| `complex.from_polar` | The number with a given magnitude and angle. |
| `complex.exp`, `complex.log` | The exponential and the principal logarithm, cut along the negative real axis. |
| `complex.pow` | `pow(z, w)` is exp(w·log z), and 1 when `w` is 0. |
| `complex.sqrt` | The principal square root, whose real part is not negative. |
| `complex.sin`, `complex.cos`, `complex.tan` | The trigonometric functions. |
| `complex.sinh`, `complex.cosh`, `complex.tanh` | The hyperbolic functions. |
| `complex.asin`, `complex.acos`, `complex.atan`, `complex.asinh`, `complex.acosh`, `complex.atanh` | Their inverses. |

A `complex.number(f32)` or `complex.number(f64)` is a struct with the
fields `real` and `imaginary`, made with a struct literal:
`z: complex.number(f64) = (real: 1.0, imaginary: -2.0)`. Every routine
takes either width, as `core/math`'s do. A float literal alone is an `f32`
[0210], so pass a typed value for the `f64` routine. A name is C's where
it is the mathematics' own, and a word for the rest.

Infinities, NaN, signed zeros and branch cuts follow C's Annex G. An
infinite operand of `multiply` gives an infinity where plain IEEE
arithmetic would give NaN. Dividing a nonzero number by zero gives an
infinity. On a branch cut, the sign of a zero picks the side. Where
Annex G leaves a sign unspecified, nearly always that of a zero or an
infinity beside a NaN part, a routine gives whatever its arithmetic gives.

Each routine's error is stated in its doc comment for each part, in units
in the last place of that part of the exact result: zero for `add` and
`subtract`, which round each part once, and for the exact `negate`,
`conjugate` and `project`; about 1 for `multiply`; 1.5 or less for `abs`,
`arg`, `log` and `from_polar`; 2 for `exp` and `sqrt`; up to 3.6 for
`divide`, `sin`, `cos`, `sinh`, `cosh` and the inverse functions; and
about 6 for `tan` and `tanh`. `pow`'s error grows with |w·log z|: it is
within about 19 units of the larger part for parts of `z` up to 4 and of
`w` up to 2. The `complex-*` fixtures check each bound against MPC's
correctly rounded values on every target the gate runs, and
[the measurements](../compiler/tests/math/README.md) give the figures.

Nothing is ported. Every routine is written from the mathematics and from
published methods: Kahan's square root, hyperbolic tangent and inverse
hyperbolic tangent, and Hull, Fairgrieve and Tang's arcsine and arccosine.
msun's complex code is under a licence whose notice a program would have
to carry. Results are rounded to nearest. Nothing keeps state, and nothing
allocates.

Cortex-M0 has 32 KiB of flash and soft float. At `f32`, `add`, `subtract`,
`multiply`, `divide`, `sqrt`, `atan` and `atanh` fit there with room for a
program, and so do `add`, `subtract` and `sqrt` at `f64`. One elementary
function at `f64`, or a trigonometric or hyperbolic one at either width,
takes a program past 32 KiB with the `core/math` routines it calls and
libgcc's soft float. Those fixtures run on the Cortex-M7 emulator lane
instead, and on the hosted targets.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-complex/main.ldn)

## core/big

Integers and rationals of any size, for a number no machine integer
holds. A `big.integer` is a signed integer, a handle to limbs taken from
the caller's allocator; a `big.rational` is a numerator over a positive
denominator, always in lowest terms. Both are written in Landin over
`core/big/limbs`, whose limb is 32 bits on every target, so a result is
the same limbs everywhere, Cortex-M0 included.

Each routine writes a destination passed `inout` as its first argument,
grows it through `memory`, an allocator, and takes its operands after:
`try big.multiply(product, memory, left, right)`. It fails only
`mem.out_of_memory` unless the table names another failure.

| Call | What it does |
|---|---|
| `big.new`, `big.release` | Zero, which allocates nothing, and giving a value's block back to `memory`. |
| `big.set`, `big.set_i64`, `big.set_u64`, `big.set_limbs`, `big.limbs_of` | A copy of another integer, a machine integer, or a magnitude in limbs with a sign; `limbs_of` is a `[]u32` view of the magnitude, for `core/big/limbs`. |
| `big.to_i64`, `big.to_u64` | The machine integer, failing `text.number_overflow` when the value is outside the type. |
| `big.to_f64`, `big.to_f32`, `big.set_f64`, `big.set_f32` | The nearest float, ties to even, rounded once, and infinity beyond the float's range; `set_f64` and `set_f32` take a float's integer part, rounded toward zero, and fail `big.not_finite`. |
| `big.sign`, `big.compare`, `big.negate`, `big.absolute` | The sign as -1, 0 or 1, the order as a `cmp.order`, and the negation and magnitude in place. |
| `big.add`, `big.subtract`, `big.multiply` | The sum, difference and product. |
| `big.divide_truncating`, `big.divide_floor` | A quotient and a remainder: rounded toward zero, the remainder with the numerator's sign, as `/` and `%` do, or rounded down, the remainder with the divisor's sign. The remainder's destination follows `memory`: `big.divide_floor(quotient, memory, remainder, numerator, divisor)`. |
| `big.power`, `big.root` | A power by a `u64` exponent, and the root of a `u32` degree, rounded toward zero. |
| `big.gcd`, `big.inverse_modulo`, `big.power_modulo` | The greatest common divisor, never negative; the inverse for a modulus, failing `big.not_invertible`; and a power for a modulus, from 0 to the modulus less one. |
| `big.and_bits`, `big.or_bits`, `big.xor_bits`, `big.complement`, `big.shift_left`, `big.shift_right`, `big.bit`, `big.bit_length` | The bits of the two's complement form, its sign repeated without end, as Python and GMP read it: `complement` is `-x - 1`, and `shift_right` rounds down. `and` and `or` are keywords, hence the names. |
| `big.append_decimal`, `big.append_hex`, `big.parse_decimal`, `big.parse_hex` | Text appended to a `text.builder`, and read from bytes: `-` before a negative value, lower-case hex digits with no `0x`. Parsing takes an optional `-` and no `+`, fails `text.invalid_number`, and then leaves its destination as it was. |
| `big.rational_new`, `big.rational_release` | Zero, and giving a rational's blocks back. |
| `big.rational_set_ratio`, `big.rational_set_integer`, `big.rational_set` | A rational from a numerator and a denominator, from an integer, or a copy of another. |
| `big.rational_numerator`, `big.rational_denominator` | Copies of the two parts, as integers. |
| `big.rational_sign`, `big.rational_negate`, `big.rational_compare` | The sign, the negation in place, and the order, which needs `memory`: `big.rational_compare(left, memory, right)`. |
| `big.rational_add`, `big.rational_subtract`, `big.rational_multiply`, `big.rational_divide`, `big.rational_power` | The arithmetic, each result in lowest terms; the power takes an `i64` exponent, and a negative one raises the reciprocal. |
| `big.rational_floor`, `big.rational_truncate` | The integer below, or the integer toward zero. |
| `big.rational_to_f64`, `big.rational_to_f32`, `big.rational_set_f64`, `big.rational_set_f32` | The nearest float, ties to even, rounded once from the exact quotient, subnormals included; `rational_set_f64` and `rational_set_f32` take exactly the float's value, and fail `big.not_finite`. |
| `big.rational_append`, `big.rational_parse` | The text `-3/4`, or `7` for a whole number, and reading it back, failing `text.invalid_number`; a zero or signed denominator is refused. |

A destination may be one of the operands: `big.add(x, memory, x, y)`.
Assigning an integer copies its handle, not its number, so two bindings
would share one block; `big.set` makes a copy. The routines that loop,
`power`, `root`, `gcd`, `inverse_modulo` and `power_modulo`, keep their
temporaries from step to step, so an arena, which frees nothing, holds a
call however many steps it takes. A result of at most 64 limbs written
over one of its operands is worked out on the stack. The rational
routines carry the prefix `rational_` because the module's principal type
is the integer, as `text.utf8_*` do.

What a caller can foresee is a failure: no memory, a value outside `i64`,
text that is not a number, a float that is not finite, a value with no
inverse. A mistake in the program stops it, as `/` by zero does: a zero
divisor or denominator, an even root of a negative value, a root of degree
0, a modulus that is not positive, a negative exponent for a modulus. A
float is rounded once: `to_f32` never goes through an `f64`.

Multiplication is schoolbook, Karatsuba and Toom-3 by size; division and
decimal text are quadratic. On x86-64, a product of two million-bit
numbers takes about 65 ms, and a division of two million bits by one
million about 2.1 s;
[the measurements](../compiler/tests/big/README.md#timing) have the table. The
module has no floating point of any precision, which the layers leave
room for, no FFT or Toom variant above three, no primality test or
factoring, and no constant-time operation: Landin writes no cryptography.

On Cortex-M0's 32 KiB reference, a program that adds and compares
integers fits with room, and one that multiplies or divides fits. One
that needs both, as roots, the modular inverse and power, and every
rational routine do, takes 36 to 51 KiB and needs a larger part.

The `big-*` fixtures check every routine against Python's integers and
fractions on every target;
[their description](../compiler/tests/big/README.md#the-fixtures) says how they are
written.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-big/main.ldn)

## core/big/limbs

Natural numbers in slices of `u32` limbs the caller supplies, least
significant limb first, as GMP's `mpn` layer has them. Nothing allocates,
and nothing is kept between calls. `core/big` is built on it, and
`big.limbs_of` and `big.set_limbs` pass between the two. A limb is 32
bits on every target, so a result is the same limbs everywhere.

| Call | What it does |
|---|---|
| `limbs.significant`, `limbs.compare` | The count of limbs without the high zero ones, and the order of two numbers by value, whatever their lengths. |
| `limbs.clear`, `limbs.copy` | Zero, and a copy. |
| `limbs.add`, `limbs.add_limb`, `limbs.subtract`, `limbs.subtract_limb` | The sum or difference with a number or one limb, returning the carry or the borrow; the left operand is at least as long as the right. |
| `limbs.multiply_limb`, `limbs.add_multiply_limb`, `limbs.subtract_multiply_limb` | A number times one limb, written, added to or subtracted from the destination, returning the high limb; the last two are GMP's `addmul_1` and `submul_1`. |
| `limbs.shift_left`, `limbs.shift_right` | A shift by a count below 32, returning the bits shifted out. |
| `limbs.divide_limb`, `limbs.remainder_limb` | Division by one limb, returning the remainder, with or without the quotient. |
| `limbs.multiply`, `limbs.multiply_scratch` | The product, of `lenof left + lenof right` limbs: schoolbook below 48 limbs, Karatsuba below 150 and Toom-3 above. `multiply_scratch` is the scratch length it needs. |
| `limbs.divide`, `limbs.divide_scratch` | The quotient and remainder by Knuth's Algorithm D, for a divisor whose top limb is not zero and which is no longer than the numerator. `divide_scratch` is the scratch length it needs. |
| `limbs.write_decimal`, `limbs.decimal_length`, `limbs.write_hex`, `limbs.hex_length` | Digits written to bytes, returning their count; the hex is lower case, with no leading zero, and `0` for zero. The lengths are what the bytes must hold: 10 a limb and one for decimal, 8 a limb and one for hex. |
| `limbs.read_decimal`, `limbs.decimal_limbs`, `limbs.read_hex`, `limbs.hex_limbs` | Digits read into limbs, returning the limb count and failing `text.invalid_number`. The lengths are what the limbs must hold: for decimal, one limb for every nine digits and one more. |

Each routine says how long its destination must be. `limbs.multiply`
writes `lenof left + lenof right` limbs; `limbs.divide` writes a quotient
of `lenof numerator - lenof divisor + 1` limbs and a remainder as long as
the divisor, with scratch of the two lengths and one more;
`limbs.write_decimal` takes scratch as long as the value. A requirement
not met stops the program, as `panic.require` does.

A destination may be an operand's own slice for `add`, `add_limb`,
`subtract`, `subtract_limb`, `multiply_limb`, `shift_left`, `shift_right`
and `divide_limb`. For every other routine it must not overlap an
operand. Reading digits is the layer's only failure.

On Cortex-M0, a program takes only the routines it calls. The whole layer
is 20,310 bytes at `size/auto`: multiplication through Toom-3 is about
9.5 KiB of it, and division 1.9 KiB.

The `big-limbs` fixtures check the routines against Python's integers on
every target; [their description](../compiler/tests/big/README.md#the-fixtures) says
how they are written.

[Executable example](../compiler/tests/fixtures/runtime/big-limbs/main.ldn)

## core/dense

Dense vectors and matrices over `f32` and `f64`, as linear algebra sees
them: a vector or a matrix is a view over the caller's storage, and every
routine computes on views without allocating. On the views are the
element-wise operations, reductions and norms, and the products of the
BLAS's three levels.

| Call | What it does |
|---|---|
| `dense.vector_over`, `dense.strided_over` | A vector of a whole slice, or of every `step`-th element of one. |
| `dense.rows_over`, `dense.columns_over`, `dense.matrix_over` | A matrix laid out by rows, by columns as the BLAS lays it out, or with any steps, such as a leading dimension larger than its rows. |
| `dense.transposed`, `dense.block`, `dense.segment` | The transpose, a block of a matrix and a stretch of a vector, over the same storage. |
| `dense.row`, `dense.column`, `dense.diagonal`, `dense.as_row`, `dense.as_column` | A matrix's row, column or diagonal as a vector, and a vector as a matrix of one row or column. |
| `dense.get`, `dense.set`, `dense.element`, `dense.set_element` | One element of a vector, or of a matrix by row and column. |
| `dense.fill`, `dense.copy`, `dense.swap`, `dense.scale`, `dense.add_scaled` | Element-wise operations on vectors; `add_scaled` is the BLAS's `axpy`. |
| `dense.add`, `dense.subtract`, `dense.multiply_elements`, `dense.divide_elements` | Element by element, into a third vector. |
| `dense.fill_matrix`, `dense.set_identity`, `dense.copy_matrix`, `dense.scale_matrix`, `dense.add_matrices` | The same for matrices; `add_matrices` is `α·A + β·B`. |
| `dense.sum`, `dense.sum_magnitudes`, `dense.dot`, `dense.largest_magnitude` | Reductions: `asum`, `dot` and `iamax`. |
| `dense.norm_two`, `dense.norm_infinity` | A vector's Euclidean norm, which overflows only when the norm does, and its greatest magnitude. |
| `dense.matrix_norm_one`, `dense.matrix_norm_infinity`, `dense.matrix_norm_frobenius`, `dense.matrix_norm_max` | A matrix's norms. |
| `dense.rotation`, `dense.rotate`, `dense.modified_rotation`, `dense.rotate_modified` | Plane rotations: `rotg`, `rot`, `rotmg` and `rotm`. |
| `dense.multiply_vector`, `dense.add_outer` | `y ← α·A·x + β·y`, `gemv`, and `A ← α·x·yᵀ + A`, `ger`. |
| `dense.multiply_symmetric_vector`, `dense.add_symmetric_outer`, `dense.add_symmetric_outers` | `symv`, `syr` and `syr2`, on one triangle. |
| `dense.multiply_triangular_vector`, `dense.solve_triangular_vector` | `x ← A·x` and `x ← A⁻¹·x` in place for a triangular `A`: `trmv` and `trsv`. |
| `dense.multiply`, `dense.product_scratch` | `C ← α·A·B + β·C`, `gemm`, packed for the cache into a scratch `product_scratch` long. |
| `dense.multiply_symmetric`, `dense.add_symmetric_product`, `dense.add_symmetric_products` | `symm`, `syrk` and `syr2k`. |
| `dense.multiply_triangular`, `dense.solve_triangular` | `trmm` and `trsm`: a triangular product or solve with many right-hand sides, in place. |

A `dense.vector(f64)` is a slice, a length and a step; a
`dense.matrix(f64)` is a slice, its rows and columns, and a step for
each, so the element in row `i` and column `j` is
`values[i * row_step + j * column_step]`. A matrix laid out by rows and
one laid out by columns are read alike, and a transposed operand is a
transposed view: no routine takes the BLAS's `TRANS` flag. A triangle,
`dense.upper` or `dense.lower`, is the view's own, so the upper triangle
of a transposed view is the lower triangle of its storage. The diagonal
of a triangular matrix is `dense.stored` or `dense.unit`, and a square
operand multiplies on the `dense.left` or `dense.right`.

```landin
    --  A is 2 by 3 laid out by rows; Aᵀ·(1, 1) sums its columns.
    mut a_values: [6]f32 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    a := dense.rows_over(a_values[0..<6], 2, 3)
    mut ones_values: [2]f32 = [1.0, 1.0]
    ones := dense.vector_over(ones_values[0..<2])
    dense.multiply_vector(y, 1.0, dense.transposed(a), ones, 0.0)
```

A view holds a writable slice, so storage that is only readable, a
constant table, is copied into writable storage first. A routine writes
only the view its signature names `into`. Views that one routine writes
and another reads must not overlap, as in the BLAS, unless the routine
says it works in place. A view whose extent passes its storage, or
operands whose shapes disagree, is a mistake in the program: it stops the
program, and the report names the call. When `beta` is 0 the output is
not read, so a NaN there does not survive, and when `alpha` is 0 the
operands are not read. An empty product is the mathematics' zero: a
product with no columns gives `β·y`, where the reference BLAS returns
early and leaves `y` as it was. A step is never negative, so the BLAS's
negative increments have no counterpart.

`dense.multiply` packs its operands into `scratch`, storage the caller
gives, as Goto and van de Geijn describe: a panel of `B` in slivers two
columns wide, kept in the outer cache, and blocks of `A` in slivers four
rows high, kept in the inner one, multiplied by a kernel that holds its
eight sums in registers. `dense.product_scratch(rows, columns, depth)` is
the length it is fastest with, at most 294,912 elements. A shorter scratch
cuts smaller blocks, and one that holds less than eight elements per row
of the depth, an empty slice included, multiplies without packing. On one
core of an AMD EPYC 7302 the `f64` product of two 1000 by 1000 matrices
takes 0.41 seconds, 4.9 GFLOP/s at `--optimize speed`. OpenBLAS 0.3.33
takes 0.049 seconds, an eighth of that, with the vector instructions
refine does not emit yet. [The timing](../compiler/tests/dense/README.md) says how it is
measured.

The other third-level routines are loops over the second level's and the
vectors', not blocked. Every routine is written from the mathematics:
`norm_two` and `rotation` by Blue's scaling in Anderson's form, which
neither overflows nor underflows unless the result does. The `dense-blas-*`
fixtures translate the reference BLAS's own test programs and hold every
test ratio under their threshold of 16 at both widths, on every hosted
target and on the Cortex-M7 and Xtensa emulators. They are past the
32 KiB of Cortex-M0 and of the RV32 lanes, which run the small consumer
and record the rest as image limits.
Banded and packed storage, complex elements, extended-precision
accumulation and arrays of more than two dimensions are not here.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-dense/main.ldn)

## core/line

Serial line settings: a UART's rate and frame, the divisor its baud-rate generator is set to, and the refusals every driver shares.

| Call | What it does |
|---|---|
| `line.settings` | A line: its `rate` in bits per second, `data_bits`, `parity` and `stop_bits`. |
| `line.default_settings` | 115,200 bits per second, 8N1. |
| `line.check` | Refuse a rate of zero and data bits outside 5 to 9. |
| `line.divisor` | The divisor nearest a rate, as a register holds it, or a refusal. |
| `line.frame_bits` | The bits of one frame, start and stop bits included. |
| `line.data_mask` | The bits of a received byte that hold the frame's data. |

`parity` is `no_parity`, `even_parity` or `odd_parity`, and `stop_bits`
is `one_stop_bit` or `two_stop_bits`.

Nothing in the module reads or writes a register, so it serves every
target. A driver computes each register image with it and encodes its
device's own bits, refuses what its peripheral cannot carry, and only
then writes. A refusal leaves the line as it was.

`divisor(clock, rate, oversampling, fraction_bits, least, most)` gives the
integer nearest `clock * 2^fraction_bits / (oversampling * rate)`, halves
up. It refuses two results with `line.unsupported_rate`:

- a value outside `least` to `most`, the register's range;
- a value whose rate misses by more than `line.tolerance`, two percent.
  That is half of what a receiver sampling 16 times a bit allows over an
  eleven-bit frame, leaving the rest to the other end.

Three peripherals as examples:

- An Arm PL011 is oversampling 16 with 6 fraction bits, its IBRD
  `value >> 6` and FBRD `value & 63`.
- An STM32 USART's BRR is oversampling 16 with 4.
- An Espressif UART's CLKDIV is oversampling 1 with 4, FRAG the low four
  bits.

The arithmetic is integer only, on `u64`, which a Cortex-M0 links
libgcc's helpers for: the derived driver's image grew by about 3.8 KB at
size/auto.

`line.unsupported_format` is a frame the peripheral cannot carry. `check`
gives it for data bits outside 5 to 9, and each driver gives it for what
its own peripheral lacks, nine data bits on every port in this
repository. Both atoms have words in `failure.words`.

A UART may leave other bits above the data bits it receives: an STM32
USART keeps the parity bit at the word's top, bit 7 of seven data bits.
Every port's `read` returns a byte ANDed with `data_mask`, so a byte read
is its frame's data and nothing else.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-line/main.ldn)

## core/atomic

A cell holding one `u8`, `u16`, `u32` or `u64`, read and written only
atomically, its operations' orderings in their names.

| Call | What it does |
|---|---|
| `atomic.new` | Make a cell holding a value, for a local or a field; module storage starts one `zeroed`. |
| `atomic.load`, `atomic.store` | Read with acquire ordering, write with release ordering. |
| `atomic.load_relaxed`, `atomic.store_relaxed` | The same, ordering nothing else: for a cache or a count. |
| `atomic.sole_add` | Add as the cell's one writer, wrapping, and return what it held: a relaxed load and a release store. |
| `atomic.exchange` | Store a value and return what the cell held, in one step that acquires and releases. |
| `atomic.add`, `atomic.add_relaxed` | Add, wrapping, and return what the cell held, in one step; the relaxed form orders nothing else. |
| `atomic.compare_exchange` | Store a value if the cell holds the one expected, and return what it held: equal to the expected exactly when it stored. |

Every operation takes the cell's address, `addr cell`. So a cell lives in
module storage or a field others reach by pointer, and is never copied
while another context uses it.

Sequential consistency is not offered; the compiler's builtins have it
([1620]).

`sole_add` is correct only while one context alone writes the cell, an
interrupt handler or one thread, since a second writer's store between
its load and its store is lost. It needs no read-modify-write, so every target has
it. Prototype 5's tick is one: the handler counts with it and any reader
loads.

```landin
mut ticks: atomic.cell(u32) = zeroed

count_tick: () -> none =
    _ = atomic.sole_add(addr ticks, 1)
end count_tick

now_ticks: () -> (count: u32) =
    count = atomic.load(addr ticks)
end now_ticks
```

Cortex-M0 has no atomic read-modify-write and no eight-byte atomic
access. There a `u64` cell, `exchange`, `add`, `add_relaxed` and
`compare_exchange` are refused with L0344 where the program writes them.
The error names what to use instead:

- `sole_add`;
- for state several contexts write, `platform/cortex_m`'s critical
  section, `disable_interrupts` to `restore_interrupts`.

A cell of any other type is refused on every target.

[Executable example](../compiler/tests/fixtures/runtime/atomic-tick-firmware/main.ldn)

## core/cache

Cache maintenance for memory a device reads or writes behind the CPU's
caches: handing a DMA buffer between CPU and device as one concept,
`maintenance`, over ranges of whole lines (D227).

| Call | What it does |
|---|---|
| `cache.line` | The bytes in one of the provider's lines. |
| `cache.clean` | Write the range's dirty lines to memory and keep them: before a device reads what the CPU wrote, as a transmit does. |
| `cache.invalidate` | Discard the range's lines, so the next read is memory's: once a device has written it, as a receive completes. |
| `cache.clean_invalidate` | Both: before a device writes the range, as a receive is armed. |
| `cache.lines` | How many lines a range is, refusing one that is not whole lines. |
| `cache.cacheless` | The provider for memory no cache stands in front of: the barriers alone, on every target. |

A range must begin on a line and be a whole number of lines. One that is
not is refused with `cache.misaligned`, and nothing is maintained.

A range is never rounded out, because a rounded line can hold bytes the
caller does not own: an invalidate would lose their dirty copy, and a
clean would write their stale copy over what a device wrote. Align a DMA
buffer to the line and size it in lines, `link(align: 32)` on the
STM32H753, and no line it occupies holds anything else.

Every operation ends with the completion barrier, so it has reached the
point a device observes when it returns.

The order is the driver's, as D227 states it:

- clean and invalidate the receive buffer before the stream is armed;
- invalidate it once a count or completion says the bytes are written and
  before reading them;
- clean a transmit buffer before the stream is enabled.

The device barrier before each enable stays the driver's own.

`cache.cacheless(line)` takes the line a cached provider would have and
refuses the same ranges. So a driver tested on a cacheless core, or a
hosted one, takes the refusals it would take on a cached profile. A line
that is not a nonzero power of two is `cache.bad_line`.

The Cortex-M7's provider is `platform/cortex_m/l1`, on a cached profile
alone.

[Executable example](../compiler/tests/fixtures/runtime/library-shared-cache/main.ldn)

## core/fibre

Fibres: tasks a function starts as a group and waits for before it goes on.

| Call | What it does |
|---|---|
| `fibre.group_over` | Cut a backing the caller lends into equal stacks, run by any `fibre.scheduler`, and return the group `from` both. |
| `fibre.turns_over` | The same over a `fibre.turns`, for tasks that must take turns. |
| `fibre.admit` | Wait for a free stack, copy a state onto it and start a task that calls a function with the copy. |
| `fibre.join` | Wait until every task has ended, and fail with the first failure any had. |
| `fibre.yield` | Let the provider's other fibres run, through `turns` evidence. |

A task is an ordinary function, `(inout state: T) -> none !
failure.reason`. Its state is a value copied onto its own stack, so one
group holds tasks of different state types. `admit` wraps the function
and the state in a `fibre.bridge`. That bridge is a `fibre.task`, which
is what a provider starts; `hosted/thread`'s groups run the same task.

The state is kept until the task ends, `escaping into` the group: what it
refers to must outlive the group, as the function's own parameters and the
locals declared before the group do.

Two concepts say what runs the tasks:

| Concept | What it promises | Providers |
|---|---|---|
| `scheduler` | `start`, `finished` and `wait`; it may run each task to its end as it is admitted | `fibre.whole`, `blocking.host`, and every provider of `turns` |
| `turns` | a `scheduler` with `yield`: a task that yields lets every other unfinished one run first | `stacks.round`, `events.host`, `fake.signals` |

- A program written against `scheduler` must be right when every task
  runs to its end. One that needs turns asks `turns_over`, and is
  refused there for a provider of `scheduler` alone.
- Fibres are cooperative: a fibre gives the core away only inside a call
  to its provider, and the fibres of one provider are one execution
  context.
- The first failure is kept and the rest are dropped. Nothing cancels a
  fibre, so `join` returns only once every task has ended.
- A group must be joined before its backing goes. Nothing but the
  program's `defer fibre.join(group) else none` makes sure it is.
- Each stack is at least 512 bytes after its record; a smaller backing
  fails `mem.out_of_memory`.

### Which calls may switch

A fibre loses the core only inside a call to an entry of the provider
that runs it, and a provider says which of its entries may switch. A
program reads the first table below to know where another fibre may have
run; between two calls that may switch, nothing else of the provider's
has.

A provider of `turns`, the event-driven host among them, may switch in
the entries that wait, and only in those:

| Concept | May switch | Never switch |
|---|---|---|
| `fibre.scheduler`, `fibre.turns` | `wait`, `yield`, and `start` where the provider runs a new fibre at once | `finished` |
| `io.reader`, `io.writer` | `read`, `write`, `write_some`, which wait for input or for room | none |
| `io.programs` | `wait`, for a child to end, and the child's `read_child` and `write_child` | `spawn`, `close_input` |
| `time.clock` | `sleep` | `now` |
| `net.network` | `connect`, `connect_within`, `accept`, `send`, `receive`, `send_to`, `receive_from` | `listen`, `open_datagram`, `shutdown`, `local_address`, `peer_address`, `set_timeouts`, `set_no_delay`, `close` |
| `signal.signals` | `next_signal` | `watch`, `stop_watching` |

Every other entry of `core/io`, `core/time` and `core/net` never
switches:

- `files`, `process`, `environment`, `directories`, `file_system`,
  `terminals`, `entropy` and `wall_clock`, whose calls do not wait for
  another fibre;
- a provider's own queries, its last errno among them.

Shutting or closing a socket wakes the fibres waiting on it, whose calls
fail `io_failed`, and does not itself switch.

The library's own providers of turns switch in fewer:

| Provider | Switches in |
|---|---|
| `stacks.round` | `yield` and `wait`; its `start` prepares the fibre and returns |
| `fake.network` over turns | `accept`, `send`, `receive`, `receive_from`, `read`, `write` and `write_some`, and only where the call would wait |
| `fake.signals` | `next_signal` when nothing waits to be read, and its round's `yield` and `wait` |
| `events.host` | `yield` and `wait`; `read`, `write` and `write_some` when the file is not ready; `read_child` and `write_child` when the pipe is not; the programs' `wait`, for the child's end; `sleep` until its deadline; `accept`, `connect`, `connect_within`, `send`, `receive`, `send_to` and `receive_from` where the socket would wait; and `next_signal` when no arrival waits to be read. Its `start` prepares the fibre and returns, and `close`, of a file or a socket, `shutdown`, `close_input` and `stop_watching` wake the fibres waiting on what they end without switching |

Where a fake clock switches depends on how it was made:

- A `fake.clock` made by `clock_over` advances the clock in its `sleep`
  and returns, and switches nowhere.
- One `clock_over_beside` made beside a network that takes turns switches
  in `sleep`, taking the network's turns until the clock reaches its
  deadline.

A test with no fake network gives its fibres a clock that yields, as the
example below does.

[Executable example](../compiler/tests/fixtures/runtime/fibre-same-source-any-provider/main.ldn)

## core/fibre/stacks

The switch between stacks, and a round of fixed turns built on it.

| Call | What it does |
|---|---|
| `stacks.round_over` | Fill the caller's `stacks.round_space` and return a `stacks.round`, a provider of `fibre.turns` over the caller's table of records. |
| `stacks.prepare` | Lay out a fibre's first frame on a stack, for a provider of its own. |
| `stacks.switch` | Save the leaving fibre's registers and resume another's. |

How a round runs:

- Its entry 0 is the stack it was made on. Its other entries are the
  fibres it started, in the order they were started.
- `start` prepares and returns, and the fibre runs at its first turn.
- The table holds one entry more than the fibres that may be unfinished
  at once. It needs no initial value: the round reads only the entries it
  has written, and a `start` it refuses writes none.
- A fibre that ends hands its turn to the entry after it, so a fibre that
  yields resumes only when every other unfinished one has run, whichever
  of them ended meanwhile.
- When every unfinished fibre has yielded since anything last started or
  ended, the round calls its `stacks.idler` before it goes on: a device
  waits for an interrupt there, and `stacks.spin` returns at once.

In a program that prepares a stack, every function checks its frame
against the stack it runs on before it reserves the frame. It traps
`stack_exhausted` at its own site when the frame would go below the
stack's limit. So a task that goes too deep stops at the call that would
have overflowed, between switches as at them.

The limit stands a margin above the stack's lowest byte, room for a
failed check's handler. `--stack-report` gives the margin as
`margin_bytes`:

| Target | Margin in bytes |
|---|---|
| x86-64 and arm64 | 640 |
| RV64 and RV32 | 768 |
| Xtensa | 1024 |
| Cortex-M | 384, and 528 with a float unit |

A switch carries each stack's limit with the registers it saves.

A prepared stack is at least 128 words, or 176 with a Cortex-M float unit,
beside the few words its first frame keeps at its top.

Size a stack from two figures of `--stack-report`: the margin, and the
`depth_bytes` of the `routines` row named
`core.fibre.stacks.first_frame`. That routine is the first frame every
fibre starts in, and it calls the task, so its depth is what a stack must
hold below its top. No task has a row of its own. The depth is a bound
over every task the program can start, with the deepest provider of each
concept counted, and not the depth of the one task a group admits.

Every target with a native backend admits this module, and synthetic-32
does not. A program over `fibre.whole` or the blocking host does not
import it, and runs on every target.

[Executable example](../compiler/tests/fixtures/runtime/fibre-turns-interleave/main.ldn)

## hosted/heap

An explicit allocator over the host runtime heap.

`new` returns a `heap`: a handle that borrows nothing, because the heap
belongs to the process. Allocations remain manual obligations. Nothing
installs an ambient allocator, and containers still receive the provider
explicitly.

The provider is written once for every hosted system. It keeps eight size
classes, of 32 to 4096 bytes, over chunks it maps through
`platform/posix`, or on Windows through `platform/windows`'s
`VirtualAlloc`:

- A freed slot goes back on its class's list and is the next one handed
  out.
- A larger request gets a mapping of its own, rounded to the system's
  page and unmapped when it is freed.

A resize takes the first of these that applies:

- The block grows or shrinks in place while its slot or mapping holds it.
- A mapping grows in place where the pages after it are free.
- On Linux, `mremap` moves a mapping's pages.
- Anything else is copied.

On Windows a mapping reserves whole 64 KiB units of address space and
commits the pages it holds. It grows in place into the rest of its
reservation, and past that it is copied, since Windows moves no pages.

The heap honours every `usize` alignment: it over-allocates and keeps a
header before the block.

Threads share the heap:

- Once the program has started a thread, the size classes are behind one
  lock of `hosted/thread/lock`. A program that has started none never
  takes it.
- A mapping of its own is made and unmapped without the lock. The heap
  takes the lock only to count the mapping's bytes.
- A C thread calling in under `--link=libc` is none of the program's, and
  two of them may not use the heap at once.

When the heap refuses a request, it refuses before any state changes.

A program measures its own memory with three calls on the handle:

| Call | What it gives |
|---|---|
| `heap.in_use(memory)` | The bytes the heap holds for blocks not yet freed. Each block counts as its size class, or as the pages of its own mapping, so the total is at least what was asked for. |
| `heap.peak_in_use(memory)` | The most `in_use` has been since the program started. |
| `heap.peak_resident(memory)` | The process's peak resident size in bytes as the system counts it, which is every page it touched. This is `getrusage`'s maximum resident set, or Windows' peak working set. It is zero when the system does not say. FreeBSD reads it at its statistics clock, so a program that ends within a few milliseconds may not be seen at its largest. |

To test that repeated work keeps nothing, read `in_use` before and after
the work, [as this program does](../compiler/tests/fixtures/runtime/heap-in-use/main.ldn).
Blocks a C library allocated are not in the heap's counts.

[Executable example](../compiler/tests/fixtures/runtime/hosted-heap-provider/main.ldn)

## hosted/thread/lock

A lock that threads share state behind, and the record that a thread has
started.

| Call | What it does |
|---|---|
| `lock.new` | Make a free lock for a local or a field; module storage starts one `zeroed`. |
| `lock.take` | Take the lock, waiting while another thread holds it. |
| `lock.take_if_free` | Take it if it is free, and say whether it did, without waiting. |
| `lock.give` | Give back a lock this thread took, waking one thread that waits for it. |
| `lock.note_start` | Record that the program is about to start a thread. The thread facility calls it. |
| `lock.threads_started` | Whether `note_start` has been called. |

A lock is one `u32` cell of `core/atomic`:

- Taking a free lock is one read-modify-write, and so is giving one
  nobody waits for.
- A thread that finds the lock held sleeps in the system's wait on the
  cell's address, `platform/posix`'s `wait_on` or on Windows
  `WaitOnAddress`, and the give wakes it.
- What the thread that gave the lock did while it held it is visible to
  the thread that takes it next.

The lock is not reentrant and keeps no owner: a thread that takes a lock
it holds waits for ever. A fibre that holds a lock across a switch holds
up the whole thread, and every other fibre of its round that wants the
lock.

The lock is a module beneath `hosted/thread` so that `hosted/heap` can
take a lock without the thread facility, which never imports the heap.
On Cortex-M0 there is no lock: `platform/cortex_m`'s critical section is
one.

[Executable example](../compiler/tests/fixtures/runtime/thread-lock-one-thread/main.ldn)

## hosted/blocking

The hosted provider whose waiting operations block the thread: what an
ordinary hosted program imports.

The provider is `host`, made by `new`. The module is written over
`platform/posix`, and on Windows over `platform/windows`, and is imported
as `blocking`, with no alias.

| Call | What it does |
|---|---|
| `blocking.new()` | The process's provider: a `host` handle that borrows nothing. |
| `blocking.over(space)` | A provider that keeps its last errno in a `space` the caller declares. |
| `blocking.last_errno(host)` | The errno number of the last failing call; on Windows its Win32 or Windows Sockets error code. |
| `blocking.last_signal(host)` | The signal that ended the last child waited for; always zero on Windows. |

`host` supplies every concept of `core/io`, `core/time` and `core/net`:
the shared I/O concepts and so `world`, `directories`, `environment`,
`programs`, `network`, `file_system`, `terminals`, `clock`, `wall_clock`
and `entropy`.

It is also a `fibre.scheduler`. It runs each task to its end before
`admit` returns, as `fibre.whole` does, and so is no provider of
`fibre.turns`: its calls block the thread.

`new` makes a `hosted/system` handle and builds the provider over it.
The two share the work by whether a call waits:

| Work | Whose it is |
|---|---|
| Everything that does not wait: opening and closing files, the standard streams' descriptors and the arguments, the environment, directories, the rest of the file system, terminals, entropy and the wall clock | The system handle's; the provider hands it over. |
| What waits: `read`, `write` and `write_some`, running programs, the network, and the monotonic clock with its `sleep` | The provider's own. |

Running a program takes both. The system handle's `start` starts the
child and does not wait; reading and writing the child's pipes and
waiting for the child are this provider's.

Both report through the system handle's one last-error cell, so
`last_errno` says the same whichever of them failed.

The provider's files are the system's: `hosted/system`'s
`descriptor_of`, `file_of` and `socket_of` convert them, and on Windows,
where a file is a handle, `handle_of` does.

### What the provider promises

| Call | Promise |
|---|---|
| `write` | Writes the whole slice, or fails. Bytes written before a failure stay written. |
| `write_some` | Makes one attempt and returns a positive count, which may be short. A failed attempt writes nothing. |
| either, on an empty slice | Succeeds without asking the system; `write_some` returns zero. |
| open, `read`, `write` | Retried after a signal interrupts them only when the system guarantees the attempt made no progress: completed progress is never repeated. |
| `close` | Consumes the file once, even when it fails, and is never retried blindly. |
| `same_file(left, right)` | Follows symbolic links and recognises hard links. The left path must exist; a missing right path gives false, and any other failure is an error. The check is not atomic: the names must stay put until the open that follows. |
| the arguments | Begin after the program's name: neither this provider nor the memory world includes `argv[0]`. |

### The network

`network` runs over `platform/posix`'s sockets. A socket is a descriptor
and a file of the provider like any other, so `read` and `write` take a
connection.

- A write to a socket the provider made is a send. On every system a
  send raises no SIGPIPE, even beside a C handler.
- A listener reuses its address.
- An IPv6 socket takes IPv6 alone on every system. BSD does that from
  the start and Linux does not.
- Up to 128 connections wait to be accepted.

The provider handles interruptions and partial results for you:

- It makes an interrupted call again.
- It waits out a connection a signal interrupted with `poll`, and reads
  the outcome from the socket.
- It makes a connection within a limit on a socket that does not block,
  and waits for it with `poll` until the limit has passed. The socket
  blocks again once the connection is made.
- When an accept is refused because its connection was reset before it
  was taken, it accepts the next.
- After a short send it goes on until every byte is sent.

When the peer has gone, the call fails:

| Call | Fails with | Last errno |
|---|---|---|
| a send | `disconnected` | EPIPE or ECONNRESET |
| a `write` | `io_failed` | EPIPE |

The process ignores SIGPIPE, so neither ends it.

On Windows `network` runs over Windows Sockets, and a socket is a handle:

- A listener is bound with no option: Windows refuses an address
  another socket listens at without being asked.
- A limit `set_timeouts` gave is waited out with `select` before the
  accept, receive or send, which then finds the socket ready. A call
  whose limit passes fails `timed_out`, keeping `WSAETIMEDOUT`.

### The clock

| Call | On the hosted provider |
|---|---|
| `now` | `platform/posix`'s monotonic clock, or on Windows the performance counter, in nanoseconds since the system started. |
| `sleep` | Takes its deadline from the monotonic clock, and asks the system to sleep for what is left until that clock has reached it. |

No hosted system fails to read its clock, so a clock the system cannot
read ends the program.

`sleep` never returns before its deadline as `now` reads it. When a
signal interrupts the sleep, or the system ends it early, it sleeps on.

A signal reaches a sleep only through a handler, and only C installs
one, since a Landin program waits for signals as events.
`runtime/sleep-signal-sleeps-on` installs a handler through the C
library and shows a sleep that ended with EINTR going on.

[Executable example](../compiler/tests/fixtures/runtime/library-system-arguments/main.ldn)

The program prints the arguments `blocking.new()`'s provider lends, one to
a line after its index. It then looks for a settings file that is not
there and prints why it could not be opened, in `failure.words`' phrase
and by `blocking.last_errno`'s number, before going on with its defaults.

## hosted/events

The hosted provider whose waiting operations switch fibres: what a
program that serves several things at once, or waits for a signal, mints
instead of `blocking.new()`.

The provider is `host`, made by `over`. The module is written once over
`platform/posix`, `platform/linux`'s epoll and signalfd and
`platform/kqueue`, and is imported as `events`, with no alias.

| Call | What it does |
|---|---|
| `events.over(state, fibres)` | Fill an `events.space` the caller declares `zeroed` and return a `host` over it and over `fibres`, the table of fibres that may be unfinished at once, one more than a group's count. |
| `events.last_errno(host)` | The errno of the provider's last failing call, kept in the provider's own `space`. |
| `events.last_signal(host)` | The signal that ended the last child waited for. |

`host` supplies every concept `hosted/blocking` does: `world`,
`programs`, `network`, `clock` and the system's. Beside them it is a
`fibre.turns` and a `signal.signals`.
[core/fibre](../core/fibre) lists the entries that may switch, under
"Which calls may switch".

### The loop

The provider's fibres take turns on a `stacks.round` over the caller's
table. When every fibre has taken a turn since anything last started or
ended, the round waits for events: epoll on Linux and kqueue on Darwin
and FreeBSD.

- The earliest deadline any fibre waits for limits the wait.
- When a fibre yielded of its own accord, the round does not wait at
  all.
- With nothing waiting, the wait returns at once.

A call that would wait submits a record on its fibre's own stack and
takes turns until the loop answers it: the descriptor is ready, the
deadline passed, or what it waited on was closed. A completion interface
could answer the same records with the call's result.

The event queue is closed on exec and stays open until the process ends.

### Files, pipes and terminals

The provider's sockets and a child's pipes are non-blocking.

A file the provider did not make is polled first, and read or written
once it is ready. So a regular file is read at once, and a terminal or a
pipe a fibre waits for lets the others run.

The provider never makes such a file non-blocking, since other processes
share its mode. What a write to one that is still blocking does depends
on what it is, which the provider asks at each write:

- A regular file never waits for a reader, and is written whole.
- A pipe is handed at most `PIPE_BUF` bytes at a time: 4096 on Linux and
  512 on Darwin and FreeBSD. A pipe ready to write takes that many
  without waiting (D1045).
- Anything else, a terminal, a socket the program made itself or a
  device, is refused. It can report room for less than a write hands it,
  and the write would then hold the thread, and every fibre on it, until
  the other end reads. `write` and `write_some` fail with `io_failed`
  before the system is asked, nothing is written, and
  `events.last_errno` reads EAGAIN, the errno of a call that would wait
  (D1278).

A program that meets the refusal makes the descriptor non-blocking,
`posix.set_non_blocking(system.descriptor_of(file), true)`, and the
provider then waits for it as it does for its own sockets; or it writes
through `hosted/blocking`, whose writes wait by design. Standard output
and standard error that are a terminal are such descriptors: a program
over `hosted/events` that prints for a person sets them non-blocking, or
prints through a `blocking.host` beside its event provider. Setting a
terminal non-blocking changes the open file its shell shares, so set it
back before the program ends.

Closing a file or a socket, or shutting a socket's side, through the
provider wakes every fibre waiting on it. The woken fibre's call fails
with `io_failed`.

### Sockets, sleeping, children and signals

- A socket's limits from `set_timeouts` bound each wait, and a wait that
  passes its limit fails with `timed_out`. A `connect` has no limit; a
  `connect_within` waits with its limit as the deadline.
- `sleep` waits for its deadline in the loop, never early. No timer or
  descriptor is made for it.
- A child's end is waited for on a pidfd on Linux and with kqueue's
  process filter on Darwin and FreeBSD. The child is then reaped.
- `watch` blocks the signal and reads it through a signalfd on Linux. On
  Darwin and FreeBSD it ignores the signal and reports it through
  kqueue, and SIGCHLD keeps its default there. Every child started
  afterwards gets the signal's default back.
- `stop_watching` reads what arrived, gives each signal its default back
  and wakes every fibre in `next_signal`.

[Executable example](../compiler/tests/fixtures/runtime/events-tcp-exchange/main.ldn)

The program runs a server fibre and a client fibre over one loopback
connection; each waits in `receive` while the other runs, so their lines
interleave.

## hosted/system

What a hosted program needs that does not wait, the same under either
waiting provider.

The provider is `host`, made by `new`. The module is written over
`platform/posix`, and on Windows over `platform/windows`, and is imported
as `system`.

`hosted/blocking` and `hosted/events` are each built over it and supply
what waits, the one by blocking the thread and the other by switching
fibres. `host` itself reads and writes no stream, so it is not a `world`.
A program that never reads, writes or sleeps may use it alone.

| Call | What it does |
|---|---|
| `system.new()` | The process's services: a `host` handle that borrows nothing. |
| `system.over(space)` | A handle that keeps its last errno in a `space` the caller declares. |
| `system.last_errno(host)` | The errno number of the last failing call; on Windows its Win32 or Windows Sockets error code. |
| `system.last_signal(host)` | The signal that ended the last child waited for; always zero on Windows. |
| `system.descriptor_of(file)`, `system.file_of(descriptor)` | Convert between a provider's file and a `platform/posix` descriptor. On Windows `system.handle_of(file)` and `system.file_of(handle)` convert between a file and a `platform/windows` handle. |
| `system.socket_of(descriptor)`, `system.is_socket(file)` | A provider's socket from a socket of `platform/posix`'s, and whether a file is one. |
| `system.clear_errno(host)`, `system.record_errno(host, errno)` | Clear the last-error cell, or keep an errno in it, for a provider built over this one. |
| `system.start(host, path, arguments, environment, streams)` | Start a child as `io.spawn` does, for a provider built over this one that supplies `io.programs`. |
| `system.process_of(child)`, `system.ended(host, status)` | The child's `platform/posix` process ID, and the `io.ending` of the status a provider waited for, keeping its signal for `last_signal`. |

`host` supplies `files`, `process`, `environment`, `directories`,
`file_system`, `terminals`, `entropy` and `wall_clock`.

It is no provider of `programs`, because reading a child's pipes and
waiting for the child both wait. A provider built over it supplies
`programs` over its `start`.

### The provider

`new` makes a handle exposing process arguments, lent as OS strings,
and standard streams. They come from the root the hosted entry
establishes through `platform/posix`'s
`_landin_host_initialize_arguments`. A C `main` that drives Landin's
exported functions calls that initializer itself, as "A C `main` that
calls Landin" below describes. On Windows the entry keeps the root
itself, from the vectors it made from the command line and the
environment block, and defines no initializer, so a program may define
its own.

The handle borrows nothing, since the root and the descriptors belong to
the process. Where it keeps its last errno depends on how it was made:

| Made by | Keeps its last errno in |
|---|---|
| `new` | The last-error cell of whichever thread calls through it, a `link(thread)` binding (D503). |
| `over` | A `space` the caller declares, for a library that keeps its detail apart from the rest of its thread's. |

`last_errno` captures the terminal failing call as provider-specific
detail: the number of the errno `platform/posix` failed with, or on
Windows the Win32 or Windows Sockets error code. It is not a portable
error type. Windows' codes have no atoms, so `system.reason` there is
`failure.reason` alone.

- A call that succeeds clears it.
- A failure the provider reports itself, without asking the system, sets
  none.

`last_signal` is the number of the signal that ended the child last
waited for, beside `io.ending`'s `signalled`. After a child that exited
it is zero, and on Windows, which ends a process with a code and no
signal, it is always zero.

### A C `main` that calls Landin

A Landin entry point sets up the arguments before its body runs. A program
whose `main` is C's, calling public Landin functions, does it itself, by
calling `_landin_host_initialize_arguments(argc, argv, envp)` from
`platform/posix`:

- Call it before the first `system.new()` or `blocking.new()`, and before
  starting any thread that may make one. Both trap when they run before
  it. The trap is `unreachable` at a line of
  `platform/posix/processes.ldn`, and the line before it on standard
  error names the call: `landin: the host was not initialized: a C main
  calls _landin_host_initialize_arguments(argc, argv, envp) first`
  (D1281).
- Importing `core/io` does not initialize anything. Files, streams and
  the heap work without the call.
- The first call needs a nonnegative `argc` and a non-null `argv`, and
  keeps that exact `argc`, `argv` and `envp` as the process's root. A null
  `envp` is an empty environment.
- A later call with the identical three values is harmless. A negative
  count, a null table, or a call that would replace any of the three,
  traps.
- Nothing is copied: C keeps the tables and every string they name
  readable for as long as anything Landin made from them is used.
- The arguments a program sees begin at `argv[1]`, and there are
  `argc - 1` of them, or none. Looking up a null entry within that count
  traps.

### Files and directories

- Standard input, output and error are descriptors 0, 1 and 2.
- Open-write creates or truncates regular files.
- A path that names nothing fails with `mem.not_found`, whether a component
  is missing (ENOENT) or one before the last is not a directory
  (ENOTDIR). `same_file` answers false for such an output path.
- A path that names a directory where a file is opened fails with
  `is_a_directory`, keeping EISDIR, from `open_read`, `open_write` and
  `open_file` alike. The system opens a directory to read and fails each
  read of it, so an open to read alone asks what it opened and closes a
  directory again (D1276). `failure.words` says "is a directory".
- A path that holds a NUL fails with `io_failed` and EINVAL, and one
  longer than the system's PATH_MAX fails with `io_failed` and
  ENAMETOOLONG, as `platform/posix` refuses them.

A directory's buffer must hold at least `io.directory_buffer`, 1024
bytes, so that every entry a hosted system gives fits. With a smaller
buffer, opening the directory fails with `io_failed` before anything is
opened.

On Windows a file is the handle the system gives, and the standard
streams are `GetStdHandle`'s. The same failures come from Win32 codes: a
missing file, path or drive is `mem.not_found`, and denied access, a
sharing or lock violation and write protection are `io.no_access`. A
path, an argument and a variable are host strings in WTF-8, converted to
the system's 16-bit units at each call.

The provider reads a directory through `platform/posix`'s directory
streams and leaves out `.` and `..`. Where the file system does not
record an entry's type, the provider asks for it with a status call
relative to the directory.

`make_directory` gives a new directory 0777, which the process umask
filters. The provider does not retry it when interrupted, because a
directory made before the interruption would then report
`already_exists`.

### The environment and starting programs

The environment is the one the process's entry was given. The provider
reads it where the entry left it, and never copies or changes it.

`start` runs over `platform/posix`'s `spawn`:

- A discarded stream is the system's `/dev/null`.
- A piped stream is a pipe whose child end is closed in the parent once
  the child has it.
- A child receives only its three streams, since every descriptor the
  provider makes is closed on exec and the spawn closes any other.
- A child starts with no signal blocked.
- An interrupted spawn is made again.

The pipes `start` answers are files of this provider. The provider built
over it reads, writes and closes them as its own:

| Provider | How it handles the child's pipes |
|---|---|
| `hosted/blocking` | `read_child` polls both pipes when both are open, and reads the output first when both have something. `wait` closes the child's pipes before it waits, so a child still writing to one meets a closed pipe rather than a parent that never reads. An interrupted poll, read or wait is made again. |
| `hosted/events` | Sets the parent's ends non-blocking and waits on them, and on the child's end, in its loop. |

On Windows `start` calls `CreateProcessW`:

- The path is the program itself, never searched for and given no
  extension.
- A discarded stream is the `NUL` device.
- A piped stream is a named pipe whose parent end is overlapped.
- A child inherits exactly its three streams, which an attribute list
  names, and no other handle.
- A child's exit code is its whole 32 bits as `exited`.

### The rest of the file system and terminals

`file_system` and `terminals` run over `platform/posix`:

| Call | On the hosted provider |
|---|---|
| `open_file` | Creates a file 0666, which the process umask filters. Refuses options no open can have with `io_failed`, keeping EINVAL, before it asks the system. A taken name `exclusive` meets is `already_exists`. |
| `rename` | `renameat`: ENOENT is `mem.not_found` and the rest `io_failed` with the errno kept. Not retried when interrupted. |
| `read_only` status | A file is read-only when no permission bit lets anyone write it. |
| `set_read_only` | Clears every write bit, or sets the owner's again, reading the bits and setting them in two calls. |
| `synchronize` | `fsync`, or `fdatasync` for the data alone; on Darwin `F_FULLFSYNC` either way. |
| `make_temporary` | Created exclusively with 0600; when every try finds its name taken, the last errno is EEXIST. |
| `window_size` | Of anything but a terminal is `not_a_terminal`, keeping ENOTTY. |

`descriptor_of` gives the `platform/posix` descriptor a file of this
provider is. Use it for a call the portable concepts do not make: a
permission bit, a lock or a terminal's raw mode. `file_of` gives the file
a descriptor is.

### The wall clock and entropy

| Call | On the hosted provider |
|---|---|
| `wall_now` | `platform/posix`'s realtime clock. |
| `fill_random` | `platform/posix`'s `random_bytes` until the buffer is full, asked again after an interruption: `getrandom` on Linux, which waits at boot until the kernel's pool is ready, and `arc4random_buf` on Darwin and FreeBSD. |

No hosted system fails to read its clock, so a clock the system cannot
read ends the program.

[Executable example](../compiler/tests/fixtures/runtime/hosted-system-alone/main.ldn)

The program uses `hosted/system` alone: it counts its arguments, finds a
variable of its environment, makes and removes a directory, and asks for
random bytes and the time, answering with its exit status since it has
nothing to write with.

## hosted/thread

Threads: tasks a function starts as a group and waits for before it goes
on, each on a thread of its own, written over `platform/posix` and, on
Windows, over `platform/windows`.

| Call | What it does |
|---|---|
| `thread.group_over(host, backing, count)` | Cut a backing the caller lends into `count` equal stacks, over a `hosted/system` handle, and return the group `from` both. |
| `thread.admit` | Wait for a free stack, copy a state onto it and start a thread that calls a function with the copy. |
| `thread.join` | Wait until every thread has ended, and fail with the first failure any task had. |
| `thread.least_stack()` | The least bytes one stack takes on this system. |

The module is `core/fibre`'s group over threads:

- A task is an ordinary function,
  `(inout state: T) -> none ! failure.reason`.
- Its state is copied onto its own stack and kept `escaping into` the
  group.
- A function making a group defers `thread.join(group) else none`, as it
  would a region's release.

Threads are no provider of `core/fibre`'s concepts. A thread runs beside
the one that started it, so what they share between `admit` and `join`
is the atomic wrapper's or a lock's.

### How a group behaves

- Everything the function did before `admit` happens before the task's
  first action, and everything the task did happens before `join`
  returns. Nothing else orders the two.
- `join` blocks the calling thread, so a fibre that joins holds its
  round. A thread may run a round of fibres of its own; a fibre never
  moves between threads.
- A thread starts with every asynchronous signal blocked. So a signal
  the process is sent reaches the provider that reads it, through a
  signalfd or kqueue, and never a thread's default disposition.
- Every stack is prepared as a fibre's is, so a task that goes too deep
  traps `stack_exhausted` at the function whose frame would not fit.
  Nothing is allocated and no guard page is mapped.
- The first failure is kept and the rest are dropped; nothing cancels a
  thread.
- A start the system refuses fails `admit` with `mem.out_of_memory` and
  starts nothing. Its errno is kept in the group's handle for
  `system.last_errno`.
- `admit` waits for a free stack by joining a thread whose task has
  ended, or else the one that started first.

### Stacks

Each stack holds three things: its record, at least 4 KiB for the task's
own stack and, at its top, the area its thread starts on. That start
area is the system's:

| System | Start area | Least stack |
|---|---|---|
| Linux, static | 2 KiB and the thread's own storage | about 6 KiB |
| Linux, `--link=libc` | glibc's least: 16 KiB, 128 KiB on arm64 | about 20 KiB, 132 KiB on arm64 |
| Darwin | 16 KiB, in whole 16 KiB pages | 32 KiB |
| FreeBSD | 16 KiB | about 20 KiB |
| Windows | none: the thread starts on a 64 KiB stack the system reserves and switches to its own | about 4 KiB |

A smaller backing fails `group_over` with `mem.out_of_memory`, before
any thread starts.

How a thread starts and how it is waited for also follow the system:

| Program | Starts each thread | Waits for it |
|---|---|---|
| Linux, static | with `clone` | on the word the kernel clears when the thread ends |
| Linux under `--link=libc`, Darwin, FreeBSD | the C library, with `pthread_create` on the area | with `pthread_join` |
| Windows | with `CreateThread` | with `WaitForSingleObject` |

A FreeBSD program that starts a thread links libthr.

[Executable example](../compiler/tests/fixtures/runtime/thread-creation-and-join-order-writes/main.ldn)

The program writes ordinary data, starts two threads that each read half
of it and write their results, and reads every result after `join`, with
no other synchronization of its own.

## platform/posix

POSIX's facilities in Landin types, on Linux, Darwin and FreeBSD alike.

The calls are POSIX's own, not policy. This module is what `hosted/system`,
`hosted/blocking` and `hosted/events` are written over, and what a program
uses when it needs a call the portable concepts do not make.

Beneath its interface the module is written twice: over
`platform/linux`'s system calls, and over `platform/libc`. Windows is
not POSIX: a Windows program may import the module, which declares
nothing there, and a call to it is refused with L0201.

### Descriptors, failures and paths

A `descriptor` is a handle type, not a number to count with, so
descriptors compare with `==` and nothing else.

| Value | Is |
|---|---|
| `standard_input`, `standard_output`, `standard_error` | 0, 1 and 2 |
| `working_directory` | the directory an `*_at` call's relative path starts from |

A failure is the errno as an atom of `errno`. There is one atom for each
errno the three systems define, named after its C macro in lower case,
`enoent` and `eintr` among them.

| Name | What it gives |
|---|---|
| `number` | The number this system uses for an atom. |
| `errno_of` | The atom for a number. |
| `unlisted` | A failure with no errno this module names. |
| `words` | A phrase for a person for every errno, as `failure.words` does for the library's atoms. |

`words`' phrases are C's `strerror` text as glibc gives it, and the BSDs'
own for errnos only they define. They are in lower case with no final
stop, and the same on every system. `words` takes `reason`: an errno, or
one of `failure.reason`'s atoms, which it words as `failure.words` does.
So it words `settings: no such file or directory` and
`settings: not found` alike.

Two things the module leaves as the system reports them:

- An interrupted call fails with `eintr` and is not retried here.
- A short transfer is returned as it came.

A path or an argument is an OS string. The module copies it into a
buffer of the system's PATH_MAX with the NUL a C call needs. It refuses
one that holds a NUL with `einval`, and one too long with
`enametoolong`.

Every descriptor the module makes is closed when the process executes a
program; `closed_on_exec` says whether a descriptor is. No open makes a
terminal the process's controlling terminal, `O_NOCTTY`.

`duplicate_above(opened, lowest)` duplicates a descriptor at the lowest
free number that is `lowest` or above, closed on exec. A process started
with a standard stream closed is given that stream's number by its next
`pipe` or open; `duplicate_above(made, 3)` moves such a descriptor clear
of the three, as `hosted/system` does with every one it makes for a child.

### Files and directories

| Call | What it does |
|---|---|
| `open_at` | Open with `open_options`; `reading` and `writing` are the two the hosted provider uses. |
| `read`, `write`, `close` | As POSIX's. |
| `read_at`, `write_at` | `pread` and `pwrite`, refusing an offset C's `off_t` cannot hold with `einval`. |
| `truncate` | `ftruncate`. |
| `synchronize` | `fsync`, or `fdatasync` with `data_only`. |
| `status_at`, `status_of` | A structured `status` of a path, or of an open file. |
| `open_directory`, `read_directory`, `close_directory` | Read a directory over a caller's buffer, listing `.` and `..` as POSIX does. |
| `make_directory_at`, `unlink_at`, `remove_directory_at` | Change the tree. |
| `rename_at` | Rename in one step, replacing a file already at the new name. |
| `link_at` | Give a file a second name, without following a final link of the old one. |
| `symbolic_link_at`, `read_link_at` | Make a link, and read its target into the caller's buffer, `erange` when the target fills it. |
| `change_mode_at`, `change_mode` | Set permission bits; `einval` beyond `0o7777`. |
| `change_owner_at`, `change_owner` | Set an owner and group; `unchanged_user` and `unchanged_group` keep either, and a link's own with `follow` false. |
| `set_times_at`, `set_times` | Set when a file was last read and written, to the nanosecond; a link's own with `follow` false. |
| `current_directory` | `getcwd`; nothing here changes the working directory. |

A `status` gives:

- device, inode, kind and size;
- the file's permission bits and its links;
- its owner and group, as a `user_id` and a `group_id`;
- when it was last read, written and changed.

Its names and flags differ from `core/io`'s for the same things:

| | `platform/posix` | `core/io` |
|---|---|---|
| the status of a path | `status_at` | `status_of` |
| the status of an open file | `status_of`, over a descriptor | `status_of_file` |
| whether a final symbolic link is followed | `follow`, a `bool` | `following` or `not_following`, atoms |
| what `synchronize` writes | `data_only`, a `bool` | `data_and_status` or `data_only`, atoms |

### Locks

The module gives two kinds of advisory lock, as every one of the systems
has both:

| | `lock`, `unlock` | `lock_range`, `unlock_range` |
|---|---|---|
| Is | BSD's `flock`, a whole-file lock | POSIX's record locks, `fcntl`'s `F_SETLK` and `F_SETLKW` |
| Kind | a `lock_kind`, `shared_lock` or `exclusive_lock` | the same |
| Belongs to | the open file, so a second open of the file in the same process stands in its way | the process, so the process never stands in its own way, and a child does not inherit them |
| Lasts until | every descriptor of that open file is closed | any descriptor of the file is closed, even one opened elsewhere for a moment, which gives every one of them up |
| A refused attempt | `eagain` | `eagain`, or `eacces` where the system says so |

Use one kind on a file, since the systems differ in how the two see each
other.

### Memory and polling

| Call | What it does |
|---|---|
| `map`, `unmap` | Make and release anonymous memory. |
| `page_size` | Give the page size. |
| `extend` | Grow a mapping in place. |
| `remap` | Grow a mapping in place or by moving its pages. |

`poll` runs over entries made by `watch` and read by `happened`. Its
`poll_events` is a distinct flag set, combined with `|` and tested with
`&` against `poll_no_events`:

| Flags | Use |
|---|---|
| `poll_input`, `poll_output`, `poll_urgent` | asked about |
| `poll_error`, `poll_hung_up`, `poll_invalid` | only reported |

`set_non_blocking` sets `O_NONBLOCK`: a call on the descriptor that
would wait fails with `eagain` instead. `non_blocking` reads the mode
back. The mode belongs to the open file, so every duplicate of the
descriptor shares it.

A program that waits for readiness sets the mode and then waits with
`poll`, or with epoll or kqueue for many descriptors.

### Waiting on an address

| Call | What it does |
|---|---|
| `wait_on` | Sleep while a `core/atomic` cell of a `u32` holds a value. |
| `wait_on_within` | The same for at most a span, failing with `etimedout`. |
| `wake_one`, `wake_all` | Wake the cell's waiters. |

A wait returns at once when the cell differs, and may return unwoken, so
a waiter reads the cell again. It is the futex, `_umtx_op` and
`os_sync_wait_on_address`.

### Processes

| Call | What it does |
|---|---|
| `pipe` | Make a pipe's two ends. |
| `spawn` | Start a program by its path. |
| `default_in_children` | Give every child a signal's default disposition. |
| `wait` | `waitpid`, reporting a `child_status`. |
| `kill` | Send a signal, by its number, to a process: a child `spawn` started, or this one. |
| `current_process` | This process's own ID, `getpid`. |
| `signal_hangup`, `signal_interrupt`, `signal_kill`, `signal_terminate`, `signal_user1`, `signal_user2` | The numbers of SIGHUP, SIGINT, SIGKILL, SIGTERM, SIGUSR1 and SIGUSR2 on this system. |
| `exit` | End the process. |
| `arguments`, `argument` | The process's arguments. |
| `environment`, `variable` | The process's environment. |
| `program_name` | `argv[0]`. |

What `spawn` gives the program:

- its arguments after `argv[0]`, which is the path;
- an environment of `core/io`'s `variable` records;
- standard streams duplicated from three descriptors,
  `standard_streams`, of which `inherited_streams` are the parent's own.

Every other descriptor is closed in the child. A failure starts nothing:
`enoent` for a missing program, and `einval` for a NUL in an argument or
a bad name.

A `child_status`'s variant part is `exited` with a code, or `signalled`
with the signal's number, which each system numbers its own way.

The process's arguments and environment are its root, established by
`_landin_host_initialize_arguments` from C's `argc`, `argv` and `envp`.

How SIGPIPE is handled:

- The argument initializer ignores SIGPIPE when it finds the default, so
  a write to a pipe or a socket nobody reads is `epipe` and not the end
  of the process.
- A handler a C `main` installed first is kept.
- `broken_pipe_ignored` says whether SIGPIPE is ignored.
- `spawn` gives every child SIGPIPE's default back.
- A program that imports no part of the POSIX layer keeps the system's
  default.

How SIGCHLD is handled:

- A process whose starter ignored SIGCHLD inherits the ignore, and the
  system then discards how each of its children ended: `wait` would fail
  with `echild`.
- The argument initializer therefore gives SIGCHLD its default back when
  it finds it ignored. A handler is kept.
- A program that wants its children discarded ignores SIGCHLD itself
  after the initializer has run.

How signals reach a child:

- A child starts with no signal blocked, whatever the parent's mask. So
  a provider that blocks a signal to read it through a signalfd starts
  no child with it blocked.
- `default_in_children` names a signal a provider took from its
  disposition, ignoring it to read it through kqueue. Every child
  `spawn` starts from then on gets that signal's default back too.
- A signal nobody named keeps the parent's disposition in the child, an
  ignore included, as a shell's background job and `nohup` expect.
- `default_in_children` refuses with `einval` a number that is no
  signal, one past 64, or past 31 on Darwin, and SIGKILL and SIGSTOP.

`kill` is how a parent stops a child, how a process signals itself, and
how a group of processes is signalled at once (D1279, D1356). It takes a
`process_id`: `system.process_of(child)` gives the ID of a child
`io.spawn` started, and `current_process()` this process's own.

- A process group is named as C's `kill` names it: `process_id(0)` is
  every process in this process's own group, this one among them, and
  `process_id(-i32(leader))` every process in the group `leader` leads.
- The number zero sends nothing and asks whether the process or the
  group is there.
- It fails with `esrch` for a process or a group that is gone, a child
  already waited for among them, `eperm` for one this process may not
  signal, and `einval` for a number that is no signal's.
- An ID of -1, which C's `kill` takes for every process the caller may
  signal, is refused with `einval`: it names no group.
- It is Linux's `kill` system call and the C library's `kill` on Darwin
  and FreeBSD, so it needs no `--link=libc`.

A handler for a signal is the C library's to install, with
`platform/libc`'s `sigaction` (D1344): for an `extern(c)` function
`on_interrupt: (number: i32) -> none`, the program writes
`action: libc.signal_action = libc.handling(on_interrupt, 0)` and then
`libc.sigaction(libc.sigint, addr action, libc.no_address)`, which gives
0 when the system took it.

- `libc.signal_handler` is the handler's type, C's `void (*)(int)`, and
  `libc.handling(handler, flags)` makes the `signal_action` that calls
  it, with no further signal blocked while it runs.
- `signal_action.handler` is the word C's member holds, a `usize`: the
  dispositions `sig_dfl` and `sig_ign`, or a handler's address,
  `usize(on_interrupt)`, which is how `handling` writes it (D1343). A
  previous action read back is compared with `sig_dfl` and `sig_ign` as
  that word.
- A Linux program that installs a handler links the C library,
  `--link=libc`: a static one has no `sigaction`. `hosted/events`'
  `signal.watch` reads signals with no handler and no C library.

### Threads

| Call | What it does |
|---|---|
| `start_thread` | Start a thread that calls a C function with an argument, on a stack area the caller lends. |
| `join_thread` | Wait until it has ended. |
| `thread_start_bytes`, `thread_start_alignment` | What the area takes on this system. |

`hosted/thread` is written over these.

| Program | Starts the thread | Waits for it |
|---|---|---|
| Linux, static | with `platform/linux`'s `clone_thread` | on the word the kernel clears when the thread ends |
| elsewhere, and under `--link=libc` | the C library, with `pthread_create` | with `pthread_join` |

The thread begins with every asynchronous signal blocked, and the
caller's mask is as it was.

A start the system refuses fails with its errno, `eagain` when it lacks
what another thread needs, and starts nothing.

### Clocks and random bytes

| Call | What it does |
|---|---|
| `clock_time` | Read the `monotonic_clock` or the `realtime_clock` as a `time_value` of seconds and nanoseconds: POSIX's `clock_gettime`. |
| `sleep` | `nanosleep`, failing with `eintr` with part of the span unslept. |
| `random_bytes` | Fill a buffer with the system's random bytes. |

### Sockets

The sockets are POSIX's too.

| Call | What it does |
|---|---|
| `socket` | Make a socket of a `socket_family`, `internet`, `internet6` or `local` for Unix-domain sockets, and a `socket_kind`, `stream` or `datagram`. |
| `socket_pair` | Two connected Unix-domain sockets. |
| `bind`, `listen`, `accept`, `connect` | As POSIX's. A non-blocking `connect` fails with `einprogress` and goes on: `poll` for `poll_output`, then `pending_error`, says how it ended. |
| `accept_non_blocking` | `accept` for a program that waits for readiness: the new socket is non-blocking whatever the listener's mode, and no receive limit bounds it, so a non-blocking listener with no connection waiting fails with `eagain` at once. |
| `send`, `receive`, `send_to`, `receive_from` | As POSIX's. |
| `shutdown` | With a `shutdown_side`. |
| `socket_name`, `peer_name` | The two ends' addresses. |
| `set_reuse_address`, `set_no_delay`, `set_ipv6_only` | Options. |
| `set_receive_timeout`, `set_send_timeout`, `receive_timeout`, `send_timeout` | Time limits, set and read back. |
| `pending_error` | Fails with the error pending on a socket. |

The receive limit bounds an `accept` on every system, and the `accept`
fails with `eagain` when the limit passes.

A send to a peer that has gone fails with `epipe` without raising
SIGPIPE.

A `socket_address` is the system's own record, laid out here for each
system, Darwin's and FreeBSD's length byte included.

| Call | What it does |
|---|---|
| `internet_address` | Make one from a `net.address`, its zone the interface `interface_index` finds, `enodev` when there is none. |
| `interface_index`, `interface_name` | Turn an interface's name into its number and back, as C's `if_nametoindex` and `if_indextoname` do. |
| `unix_address` | Make one from a path, refusing one too long for the system. |
| `family_of`, `address_of`, `unix_path` | Read one back. |

### Terminals

| Call | What it does |
|---|---|
| `is_terminal` | Say whether a descriptor is a terminal. |
| `window_size_of`, `set_window_size` | A `window_size` of rows, columns and pixels. |
| `terminal_mode_of`, `set_terminal_mode` | Read and set a `terminal_mode`, the system's own record; a change applies `immediately`, `after_output` or `discarding_input`. |
| `raw_mode` | Make a mode raw, as `cfmakeraw` does. |
| `reads_lines` | Say whether a mode reads a line at a time, with echo. |
| `same_terminal_mode` | Say whether two modes are the same. |
| `open_pseudo_terminal` | Open a `pseudo_terminal`: a `controller` and its `terminal`, both closed on exec. |

There are no destructors, so a program that changes a terminal gives it
back the settings it found with a `defer`.

### Users and groups

| Call | What it does |
|---|---|
| `real_user`, `effective_user`, `real_group`, `effective_group` | The process's IDs. |
| `account_with_id`, `account_named` | Read an `account` into the caller's buffer. |
| `group_with_id`, `group_named` | Read a `group_entry` into the caller's buffer. |
| `parse_account`, `parse_group` | Read one line of /etc/passwd's or /etc/group's form. |
| `member_count`, `member` | Read a group's members. |

A lookup reports `mem.not_found` when there is none, and `erange` when the
buffer is too small. Where it looks is told apart by `compiler.c_runtime`
when the program is compiled; the table under "How each system does it"
says which.

A static Linux program reads /etc/passwd and /etc/group a line at a
time:

- The first entry that matches is taken.
- Every line that is not an entry is skipped.
- `erange` is reported when a line too long for the buffer might have
  been the one.

`parse_account` and `parse_group` refuse these with `malformed_entry`:

- a comment;
- an NIS line;
- a field missing or too many;
- an empty name;
- an ID that is not a decimal below `0xFFFFFFFF`.

`member` skips an empty name between commas.

### Shared objects

| Call | What it does |
|---|---|
| `open_library` | Load a shared object by its path, or by the system's search for a name with no slash. |
| `find_symbol` | A symbol's address, never zero, as a `usize`. |
| `close_library` | Give one use back. |
| `library_failure` | Copy the loader's own words for the last failure on this thread into the caller's buffer. |

`open_library` binds every symbol the object needs at once, POSIX's
`RTLD_NOW`. A call always says the scope of the object's symbols, because
Darwin's default is not the other systems':

| Scope | The object's symbols resolve |
|---|---|
| `local_symbols` | no other object's references |
| `global_symbols` | those of every object loaded after it |

A `library` is a handle that counts one use of the object. Loading it
again gives the same object and counts another.

A C function type applied to an address, `adder(address)`, makes the
function a value. Nothing can check that type, as nothing checks a C
cast.

A function found in a library is the program's to call only while a use
of it is open, which no check of the language follows.

A failure is `no_library` or `mem.not_found`. Call `library_failure` at once,
since asking clears the words and the next call may replace them.

It is the C library's `dlopen`, `dlsym`, `dlclose` and `dlerror` on every
system. So a static Linux program that loads a library is refused before
it links, naming the function and `--link=libc`. What is loaded is C, or
another language's code reached through its C entry points.

### How each system does it

| Call or fact | Linux | Darwin | FreeBSD |
|---|---|---|---|
| beneath the interface | `platform/linux`'s system calls | `platform/libc` | `platform/libc` |
| `pipe` | `pipe2` | `pipe` and `fcntl` | `pipe2` |
| `spawn` | copies the process with `clone`, as `fork` does; the child moves its streams into place and executes the program, reporting a failure through a pipe closed on exec | the C library's `posix_spawn` | the C library's `posix_spawn` |
| SIGPIPE's default in a child, and each signal's `default_in_children` named | restored in the child before it executes the program | `posix_spawnattr_setsigdefault` | `posix_spawnattr_setsigdefault` |
| a child's empty signal mask | `rt_sigprocmask` in the child before it executes the program | `posix_spawnattr_setsigmask` | `posix_spawnattr_setsigmask` |
| `clock_time` | the vDSO's `clock_gettime` when the auxiliary vector names a vDSO that has one, found once and kept, under `--link=libc` as under a static link; the system call otherwise | the C library | the C library |
| `sleep` | `clock_nanosleep` on the monotonic clock | `nanosleep` | `nanosleep` |
| `random_bytes` | `getrandom` without `GRND_NONBLOCK`, which may fill a request over 256 bytes short and fail `eintr` | `arc4random_buf`, which fills it all and never fails | `arc4random_buf`, likewise |
| `synchronize` | `fsync`, or `fdatasync` | `F_FULLFSYNC`, falling back to `fsync` | `fsync`, or `fdatasync` |
| `extend` | `mremap` without `MREMAP_MAYMOVE` | asks for the pages after the mapping, kept only when the system puts them there | as Darwin |
| `remap` | `mremap` with `MREMAP_MAYMOVE`, moving pages rather than copying bytes | cannot move a mapping: `extend` | as Darwin |
| a socket closed on exec | SOCK_CLOEXEC | `fcntl` just after | SOCK_CLOEXEC |
| a send without SIGPIPE | MSG_NOSIGNAL | SO_NOSIGPIPE set on each socket | SO_NOSIGPIPE set on each socket |
| `accept`'s time limit | the kernel limits it | `accept` polls for a connection for as long as the limit first | as Darwin |
| `accept_non_blocking` | `accept4` with SOCK_NONBLOCK | `accept`, then `fcntl` | `accept4` with SOCK_NONBLOCK |
| a socket `accept` takes from a non-blocking listener | blocking | non-blocking, as the listener is | blocking |
| `unix_address`'s longest path | 108 bytes | 104 bytes | 104 bytes |
| `open_pseudo_terminal` | /dev/ptmx and `TIOCGPTPEER`, or the terminal's /dev/pts path where a kernel or an emulator lacks it | `posix_openpt` | `posix_openpt` |
| accounts and groups | from /etc/passwd and /etc/group in a static program; through the C library under `--link=libc` | the C library, which asks every database the system is set to | as Darwin |
| shared objects | under `--link=libc` only | the C library | the C library |

On Linux `_landin_host_initialize_arguments` hands `platform/linux` the
tables it is given, so a program the C runtime started finds the
auxiliary vector after the initial stack's `envp` too.

[Executable example](../compiler/tests/fixtures/runtime/posix-files/main.ldn)

## platform/libc

The C library's declarations, as ordinary `extern(c)` imports, raw.

Its declarations are for the systems with a C library: Linux, Darwin
and FreeBSD. Every hosted system may import it, and on Windows it
declares nothing.

| System | Who uses this module |
|---|---|
| Darwin, FreeBSD | `platform/posix` reaches the operating system only through it, since their C library is their system interface. |
| Linux | `platform/posix` makes `platform/linux`'s system calls; this module serves a program linked with `--link=libc`. |

Every declaration is bodyless. So a program that names none of them
needs no C library, and a static Linux program that names one is refused
before it links.

A program that declares one of these C functions itself must declare it
with the same types. Otherwise the two declarations of one C symbol are
refused with L0347.

### Conventions

How a call is declared:

- `open` and `openat` are declared variadic, as C declares them, and take
  the mode as the one unnamed argument.
- Facts that differ between systems are chosen by `compiler.os`; the
  table under "How each system differs" lists them. `stat`'s record
  follows the system and the C ABI.

How a call reports a failure:

- Read the errno cell immediately after a failing call.
- The `pthread` calls return their errno, and set no errno cell. FreeBSD's
  are libthr's, which a program that starts a thread links.
- `posix_spawn` reports its failure as its result, not in errno.
- `mmap`'s failure is `map_failed`.
- `readdir`'s and `fdopendir`'s null pointer is `no_directory`;
  `dlopen`'s is `not_loaded` and the other loader calls' `no_address`. An
  optional pointer is the `no_address` union.

### What it declares

| Area | Declarations |
|---|---|
| processes | `pipe`, `pipe2` where it exists, the variadic `fcntl`, `waitpid` and `posix_spawn` with its file actions and attributes, each a C-library pointer in a `spawn_object` cell |
| directories | `fdopendir`, `readdir`, `closedir`, `fstatat`, `mkdirat` and `unlinkat`, with each system's `struct dirent` as `directory_record`, its `at_fdcwd`, `o_directory`, `at_symlink_nofollow` and `at_removedir`, and the `d_type` and mode bits |
| clocks and randomness | `clock_gettime` with a `clock_realtime` or a `clock_monotonic`, `nanosleep` with a `timespec`, and `arc4random_buf` |
| sockets | `socket`, `socketpair`, `bind`, `listen`, `accept`, `accept4`, `connect`, `send`, `recv`, `sendto`, `recvfrom`, `shutdown`, `setsockopt`, `getsockopt`, `getsockname` and `getpeername`, with each system's `af_inet6`, `sol_socket` and option numbers, `sock_cloexec` and `msg_nosignal` where they exist, `so_nosigpipe`, the address records' sizes and its `time_limit`, C's `struct timeval` |
| signals | `sigaction` with each system's `signal_action`, which `handling` makes from a `signal_handler`, and `signal_set`, `sigprocmask` with each system's `sig_block`, `sig_unblock` and `sig_setmask`, `getpid` and `kill`, the signals `sighup`, `sigint` and `sigterm` and each system's `sigusr1` and `sigusr2`, `posix_spawnattr_setsigdefault` with `posix_spawn_setsigdef`, and `posix_spawnattr_setsigmask` with `posix_spawn_setsigmask` |
| descriptors that do not block | `fcntl`'s `f_getfl` and `f_setfl`, each system's `o_nonblock`, and `sock_nonblock` where it exists |
| the rest of the file system | `pread`, `pwrite`, `ftruncate`, `fsync`, `fdatasync`, `getcwd`, `renameat`, `linkat`, `symlinkat`, `readlinkat`, `fchmodat`, `fchmod`, `fchownat`, `fchown`, `utimensat`, `futimens`, `fstat`, `flock` with its `lock_sh`, `lock_ex`, `lock_nb` and `lock_un`, and `fcntl`'s record locks with each system's `f_getlk`, `f_setlk`, `f_setlkw`, lock types and `lock_record`, C's `struct flock` |
| users and groups | `getuid`, `geteuid`, `getgid` and `getegid` for the process's IDs, and `getpwuid_r`, `getpwnam_r`, `getgrgid_r` and `getgrnam_r` over each system's `account_record`, C's `struct passwd`, and the shared `group_record` |
| shared objects | `dlopen`, `dlsym`, `dlclose` and `dlerror`, with `rtld_now` and each system's `rtld_local` and `rtld_global`; glibc keeps them in its libc since 2.34 |
| terminals, as Darwin and FreeBSD use them | `isatty`, the variadic `ioctl` with `tiocgwinsz` and `tiocswinsz` over a `window_record`, `tcgetattr` and `tcsetattr` with `tcsanow`, `tcsadrain` and `tcsaflush` over each system's `terminal_record`, its mode bits and `vmin` and `vtime`, and `posix_openpt`, `grantpt`, `unlockpt` and `ptsname_r`; `o_noctty` and `at_symlink_follow` are each system's |

### How each system differs

| Fact | Linux | Darwin | FreeBSD |
|---|---|---|---|
| the errno accessor `errno_cell` | `__errno_location` | `__error` | `__error` |
| `open` and `mmap` flags, `poll`'s count type | Linux's | Darwin's | FreeBSD's |
| `mkdirat`'s mode, as `mode_t` | 32 bits | 16 bits | 16 bits |
| `fchmodat`'s and `fchmod`'s mode | as `mode_t` | a `u16` | a `u16` |
| `clock_monotonic` | 1 | 6 | 4 |
| `arc4random_buf` | not declared | declared | declared |
| `accept4` | declared | not declared | declared |
| `sig_block`, `sig_unblock`, `sig_setmask` | 0, 1, 2 | 1, 2, 3 | 1, 2, 3 |
| `sigusr1`, `sigusr2` | 10, 12 | 30, 31 | 30, 31 |
| `o_nonblock` | 2048 | 4 | 4 |
| `sock_nonblock` | 2048 | none | its own |
| `fdatasync` | declared | not declared; `f_fullfsync` instead | declared |
| `so_nosigpipe` | none | yes | yes |
| `time_limit`'s microseconds | an `i64` | an `int` | an `i64` |
| `posix_spawnattr_setsigdefault`, `posix_spawnattr_setsigmask` | not declared | declared | declared |
| `posix_spawn` extras | none | `posix_spawn_cloexec_default` | `addclosefrom_np` |
| `rtld_local`, `rtld_global` | as FreeBSD's | numbered its own way | as Linux's |

[Executable example](../compiler/tests/fixtures/abi/r440-native-hosted/program.ldn)

## platform/linux

Linux's system calls with no C library beneath them, and the process
entry of a static Linux executable, raw.

Every declaration is Linux-only. Landin has no conditional import, so
`platform/posix` imports this module on every system, and the module's
scope is every hosted system. On Darwin, FreeBSD and Windows it declares
nothing.

| Call | What it does |
|---|---|
| `linux.system_call` | The raw route to every Linux call: six `i64` arguments, unused ones zero, and the kernel's result. |
| the typed wrappers | The calls the library makes, listed below. |
| `_landin_start` | Where a static executable starts. |
| `adopt_start` | Take the tables from a C runtime's `main`, under `--link=libc`. |
| `environment`, `auxiliary` | What the entry found. |
| `level`, `read_cpu_words`, `missing_feature` | The CPU feature check. |
| `clone_thread`, `exit_thread`, `wait_until_cleared` | Start a thread with `clone`, end it alone, and wait for the word the kernel clears at its end. |

### Calls

- Each call is one assembly block on x86-64, arm64 and RV64.
- A failure comes back in its result as minus the errno; there is no
  errno cell.
- `platform/linux/numbers` names each call's number for `system_call`,
  and the wrappers' numbers come from the same generated tables.
- The `*at` calls take `at_fdcwd` for a path relative to the working
  directory.
- `statx`'s `file_status` is the kernel's one record on every
  architecture, and `statx_basic_stats` and `at_empty_path` ask `statx`
  for every field of an open file.
- `ppoll` is the poll call every architecture has.

The typed wrappers are the calls the library makes:

| Area | Wrappers |
|---|---|
| files and directories | `getdents64`, `mkdirat`, `unlinkat`, `pread64`, `pwrite64`, `ftruncate`, `fsync`, `fdatasync`, `getcwd`, `renameat2` (every architecture's rename), `linkat`, `symlinkat`, `readlinkat`, `fchmodat`, `fchmod`, `fchownat`, `fchown`, `utimensat` (whose path may be `no_path`), `flock` |
| descriptors | `ppoll`, `pipe2`, `dup3`, `fcntl`, `close_range`, `ioctl` |
| events | `epoll_create1`, `epoll_ctl`, `epoll_pwait` (every architecture's epoll wait), `signalfd4` and `rt_sigprocmask` |
| processes | `fork` (a `clone` with SIGCHLD and nothing shared), `execve`, `wait4`, `getpid`, `kill`, `rt_sigaction` and the four ID calls |
| time and randomness | `clock_gettime`, `clock_nanosleep`, `getrandom` |
| sockets | the socket calls from `socket` to `getpeername`, with `accept4`, `sendto` and `recvfrom` standing for the calls arm64 and x86-64 lack |

`rt_sigaction` takes the kernel's `signal_action`, which RV64 lays out
without a restorer.

No function but `_landin_start` and `_landin_start_main` is a global
symbol, so none of them replaces the C library's function of the same
name under `--link=libc`.

### Events

epoll waits until any of many descriptors is ready, and a signalfd reads
signals as records from a descriptor epoll can watch:

| Name | What it is |
|---|---|
| `epoll_record` | `struct epoll_event`: the events and a 64-bit word handed back with each report. Twelve bytes and packed on x86-64, as the kernel packs it there alone; sixteen on arm64 and RV64. |
| `epollin`, `epollout`, `epollpri`, `epollrdhup`, `epollerr`, `epollhup` | Events; the last two are reported whether asked or not. |
| `epolloneshot`, `epollet` | One report until asked again; a change of readiness rather than readiness. |
| `epoll_ctl_add`, `epoll_ctl_mod`, `epoll_ctl_del` | `epoll_ctl`'s operations. |
| `signalfd_record` | `struct signalfd_siginfo`, 128 bytes on every architecture: the signal, its sender and its code. |
| `signal_bit`, `sig_block`, `sig_unblock`, `sig_setmask` | A signal's bit in the kernel's eight-byte mask, and `rt_sigprocmask`'s operations. |
| `sighup`, `sigint`, `sigusr1`, `sigusr2`, `sigterm` | The signals, numbered alike on all three architectures. |
| `epoll_cloexec`, `sfd_cloexec`, `sfd_nonblock`, `o_nonblock`, `sock_nonblock`, `f_getfl`, `f_setfl` | The flags. |

A signalfd reads only pending signals, so the signals it reads are blocked
with `rt_sigprocmask` first. The mask is the thread's, and a child and a
program it executes keep it.

There is no eventfd or timerfd: a loop sleeps in its wait's time limit
and nothing else wakes it (D480).

### Terminals and record locks

A terminal is the kernel's own `terminal_record`, `struct termios`,
smaller than the C library's. `ioctl` reads and sets it with `tcgets`,
`tcsets`, `tcsetsw` and `tcsetsf`.

These are the generic architecture's, which x86-64, arm64 and RV64
share:

- the `terminal_record`'s mode bits, `vmin` and `vtime`;
- `window_record`, `tiocgwinsz` and `tiocswinsz`;
- the pseudo-terminal requests `tiocsptlck`, `tiocgptpeer` and
  `tiocgptn`.

`lock_record` is the kernel's `struct flock` on a 64-bit architecture.

### The static entry

`_landin_start` reads `argc`, `argv`, the environment and the auxiliary
vector from the initial stack, and calls `main` as C's runtime would. No
C library initialisation runs and there is no thread-local storage.
`environment` and `auxiliary` report what that entry found.

Before `main` it holds the processor to the executable's CPU feature
level, as a loader holds an x86-64 executable to its ISA note:

| Architecture | Checked with |
|---|---|
| x86-64 | `cpuid` and the operating system's enabled state |
| arm64 | AT_HWCAP |
| RV64 | `riscv_hwprobe` |

A processor without a feature of the level ends the process with status
127 and one line on standard error naming the level and the missing
feature. The baseline checks nothing. `level`, `read_cpu_words` and
`missing_feature` expose the check.

### Started by the C runtime

When the C runtime started the program instead, under `--link=libc`,
`adopt_start` takes the environment and the auxiliary vector from the
`argc`, `argv` and `envp` C's `main` was given, which `platform/posix`'s
argument initializer passes it.

It takes them only when they are laid out as the kernel lays out the
initial stack:

- `argv` above the calling frame;
- `envp` right after `argv`'s null;
- every string above the tables;
- a vector ending in AT_NULL within 64 entries and before the lowest
  string;
- AT_PAGESZ a power of two of at least 4096;
- AT_RANDOM's bytes between the vector and the strings.

Nothing above the lowest string is read.

Tables a C `main` built itself, or C's `environ` after it changed, are
not taken. Then `environment` and `auxiliary` find nothing, and
`page_size` is 4096, as before.

[Executable example](../compiler/tests/fixtures/runtime/linux-system-calls/main.ldn)

## platform/linux/numbers

Every Linux system call's number on x86-64, arm64 and RV64, generated
from a pinned kernel release.

Each number is its call's name in the kernel's table followed by
`_number`, `numbers.getpid_number` for one, so no number can take a
reserved word's spelling. Give it to `linux.system_call`. A call the
running kernel lacks returns minus ENOSYS.

It is a module of its own, apart from `platform/linux`, so that a program
making no raw call does not compile a thousand declarations. Its scope is
`platform/linux`'s, and on Darwin, FreeBSD and Windows it declares
nothing.

The numbers are the kernel's own. `scripts/linux_syscalls.py` reads them
from each architecture's table, with the ABIs that architecture's 64-bit
build selects, x32's excluded. The file's header names the release and
its SHA-256, and nothing in it is written by hand.

A new typed wrapper in `platform/linux` needs no download:

- `scripts/linux_syscalls.py` with no release named holds this file to
  being its own rendering, and writes the wrappers' numbers from it;
- `--check` says whether they are current;
- the release is needed only to change the pin.

[Executable example](../compiler/tests/fixtures/runtime/linux-system-calls/main.ldn)

## platform/linux/vdso

The vDSO, the small shared object Linux maps into every process, and the
functions found in it, raw.

It is a submodule of `platform/linux`, so a program that never reads a
clock this way does not carry it. It declares nothing on Darwin and
FreeBSD.

The kernel's vDSO is found through the auxiliary vector's
AT_SYSINFO_EHDR.

| Call | What it does |
|---|---|
| `vdso.kernel_image` | The vDSO's bytes as far as its first load segment reaches: the image the kernel mapped. |
| `vdso.find` | Find a global or weak function by name and version in any image of a 64-bit little-endian ELF object, through its program headers, dynamic table, DT_HASH or DT_GNU_HASH, symbols and version definitions. |
| `vdso.symbol` | The function's address. |
| `vdso.clock_symbol`, `vdso.clock_version` | The name and version of its `clock_gettime`. |
| `vdso.clock_gettime` | That function's C type. |

| Architecture | `clock_gettime` in the vDSO |
|---|---|
| x86-64 | `__vdso_clock_gettime` of `LINUX_2.6` |
| arm64 | `__kernel_clock_gettime` of `LINUX_2.6.39` |
| RV64 | `__vdso_clock_gettime` of `LINUX_4.15` |

Every offset is held to lie within the image before a byte is read, so a
malformed, truncated or foreign image finds nothing and never traps.
A copy of the real one, damaged byte by byte, shows it.

### What the parser costs

The parser has a size. On Linux x86-64 its functions are 9.5 KB of a
static program at `--optimize size` and 12.1 KB at `speed`.

Reading a clock through `platform/posix` brings them with the clock
path, the errno table and the auxiliary-vector lookup. That grows the
program's text by 16.7 KB and 19.9 KB, against 5.9 KB for a program that
reads none.

A size-bound Linux program that needs a clock and not that speed can
call `linux.clock_gettime`, the system call, itself, and carry none of
it.

[Executable example](../compiler/tests/fixtures/runtime/linux-vdso/main.ldn)

## platform/kqueue

kqueue, the event interface Darwin and FreeBSD share, through their C
libraries, raw: a failure is -1 with the reason in `libc.errno_cell`.

Every declaration is Darwin's and FreeBSD's. The module's scope is every
hosted system, as `platform/linux`'s is, so a provider written once
imports both. On Linux and Windows it declares nothing (D481, D2267).

| Name | What it is |
|---|---|
| `kqueue` | Make a queue. It is not inherited by a child `fork` makes; set `libc.fd_cloexec` with `libc.fcntl` so a program executed does not keep it. |
| `kevent` | Make the changes given, then wait for events or a `libc.timespec` limit; `none_given` for no changes, no room or no limit. A change that fails comes back as an event with `ev_error` and the errno in its datum. |
| `change` | A change record: an identifier, a filter, flags, filter flags and a datum. |
| `event_record` | `struct kevent`: what is watched, the filter, the flags, the filter's flags, its datum and a word handed back with each event. |
| `evfilt_read`, `evfilt_write`, `evfilt_signal`, `evfilt_proc`, `evfilt_timer` | Filters: readiness, a signal, a process's end with `note_exit`, a timer. |
| `ev_add`, `ev_delete`, `ev_enable`, `ev_disable`, `ev_oneshot`, `ev_clear` | Change flags. |
| `ev_eof`, `ev_error` | Reported flags. |
| `note_seconds`, `note_useconds`, `note_nseconds`, and FreeBSD's `note_mseconds` | A timer's unit; with none it is milliseconds. |

The queue records a signal it watches even when the signal is ignored or
blocked. The signal is still delivered as its disposition says, so a
program ignores or blocks it.

Facts that differ between the two systems:

| Fact | Darwin | FreeBSD |
|---|---|---|
| `event_record` | 32 bytes | 64 bytes, with four extension words |
| `note_useconds`, `note_nseconds` | 2, 4 | 4, 8 |

[Executable example](../compiler/tests/fixtures/runtime/kqueue-events/main.ldn)

## platform/windows

Windows' own interface under the Windows x64 C convention, raw: a call
that fails returns the system's failure value and leaves the reason for
`last_error`. It is what the hosted providers are written over on
Windows, as they are over `platform/posix` elsewhere.

The module holds the process entry every Windows executable starts at,
which refine links into each one whether or not the program imports the
module. No C runtime is linked. Every hosted system may import the
module, and off Windows it declares nothing.

Each facility has a file of its own, which names the library it links
with `linker.library`:

| File | What it holds | Links |
|---|---|---|
| `windows.ldn` | The entry, the argument and environment root, handles, the error codes, `VirtualAlloc` and `VirtualFree`. | kernel32 |
| `level.ldn` | The CPU feature level the entry holds the processor to: `level`, `read_cpu_words` and `missing_feature`. | |
| `wide.ldn` | The conversion between a host string and the system's 16-bit units, and `terminate`, which makes the terminated wide string a call takes. | |
| `files.ldn` | Files, directories and the console. | |
| `processes.ldn` | Child processes, pipes, events and waiting on them. | |
| `time.ldn` | The wall clock, the performance counter, sleeping and `BCryptGenRandom`. | bcrypt |
| `threads.ldn` | Threads, and `WaitOnAddress` with its wakes. | synchronization |
| `memory.ldn` | What `VirtualQuery` says of a region, the page and the 64 KiB unit of reservation. | |
| `completion.ldn` | I/O completion ports, the job a child's end is learned through, and the console's control events. | |

Windows Sockets is the module `platform/windows/sockets`, below.

A Windows host string, a `text.os_string`, is WTF-8: UTF-8 for every
well-formed name, with a lone surrogate as the three bytes UTF-8 would
give its value. So every name the system gives survives the trip to
bytes and back.

| Name | What it is |
|---|---|
| `_landin_start` | The process entry. It holds the processor to the image's level, reads `GetCommandLineW` and the environment block, splits the command line as Microsoft's C runtime does, keeps the vectors as the process's argument root, calls the program's `main` and ends the process with `ExitProcess`, main's result the exit code's 32 bits. |
| `arguments`, `environment` | What the entry found, read as `platform/posix`'s are. |
| `level`, `read_cpu_words`, `missing_feature` | The CPU feature check, as `platform/linux`'s. |

An image built above its family's baseline level checks the processor
before anything else. One without a feature of the level writes
`landin: this executable needs LEVEL, and the processor lacks FEATURE`
to standard error and ends with status 127, as a static Linux executable
does. On x86-64 the check reads `cpuid` through `platform/x86_64`. On
arm64 `IsProcessorFeaturePresent` answers for LSE and CRC32; nothing
Windows documents reports RDM, armv8.1-a's third feature, so it is not
checked.

Every program of the Windows corpus starts at the entry, the first
example among them, which imports nothing and ends with its status. The
second starts the command processor `ComSpec` names, with pipes for its
three streams.

[Executable example](../compiler/tests/fixtures/runtime/add-exits-with-its-sum/main.ldn)

[Running programs on Windows](../compiler/tests/fixtures/runtime/windows-run-programs/main.ldn)

## platform/windows/sockets

Windows Sockets, ws2_32's calls, and iphlpapi's interface names, raw,
under the Windows x64 C convention: making, binding, connecting and
closing sockets, sending and receiving, their options, `select`, and the
overlapped calls `WSARecv`, `WSASend`, `WSARecvFrom` and `WSASendTo`,
with `ConnectEx` and `AcceptEx` reached through `WSAIoctl`. A call that
fails returns `socket_error` or `invalid_socket` and leaves the reason for
`socket_last_error`; `started` makes the one `WSAStartup` call a process
needs before its first socket.

It is a module of its own because refine links `platform/windows` into
every Windows program. Its calls' C names are `send`, `connect` and
`bind`, which a program may give its own C code, so only a program that
imports this module, as the hosted network providers do, has them
declared (D2281). Every hosted system may import it, and off Windows it
declares nothing.

[Executable example](../compiler/tests/fixtures/runtime/network-echo/main.ldn)

## platform/c

C scalar spellings for the target's C ABI, on every target whose C ABI is
enabled: the four LP64 ones and Cortex-M's ILP32 AAPCS32.

LP64 and ILP32 are data models, not architectures:

- Under LP64, C `int` is 32 bits while `long` and pointers are 64, as on
  every 64-bit Unix.
- Under Cortex-M's ILP32, all three are 32 bits.
- Windows' LLP64 keeps `long` at 32 bits with 64-bit pointers. It is not
  admitted here.
- RV32's and Xtensa's ILP32 ABIs are not admitted either: the compiler
  describes them but does not enable them.

The C ABI, the application binary interface, depends on the operating
system as well as the architecture. So the compiler names it with one
fact per ABI rather than reading it from `compiler.arch` or the pointer
width:

| Target | ABI fact | Plain `char` |
|---|---|---|
| `linux-x86-64`, `freebsd-x86-64` | `compiler.c_sysv_lp64`: the System V AMD64 ABI | `i8` |
| `darwin-arm64` | `compiler.c_darwin_lp64`: Apple's arm64 variant of AAPCS64 | `i8` |
| `linux-arm64`, `freebsd-arm64` | `compiler.c_aapcs64_lp64`: the standard AAPCS64 | `u8` |
| `linux-rv64` | `compiler.c_riscv_lp64d`: RISC-V LP64D, LP64 with double-precision float registers | `u8` |
| `cortex-m0`, every level | `compiler.c_aapcs32`: AAPCS32, its VFP variant when the device description has a float unit | `u8` |
| `windows-x86-64` | `compiler.c_win64_llp64`: the Windows x64 convention, LLP64 | `i8` |
| `windows-arm64` | `compiler.c_windows_arm64_llp64`: Microsoft's arm64 variant of AAPCS64, LLP64 | `i8` |

Darwin and Linux share `compiler.arch == arm64` and still disagree on
`char`, which is why the fact names the ABI.

The other aliases differ only in `long`:

| Alias | LP64 | AAPCS32 | Windows' LLP64 |
|---|---|---|---|
| `c_int` | `i32` | `i32` | `i32` |
| `c_long` | `i64` | `i32` | `i32` |
| `c_longlong` | `i64` | `i64` | `i64` |
| `c_size` | `usize`, 64 bits | `usize`, 32 bits | `usize`, 64 bits |

The aliases keep ordinary Landin scalar identity; `c_char` is a numeric
byte and never a Unicode scalar.

On Cortex-M a variadic C function is not called; import a fixed-arity C
function that calls it instead.

[Executable example](../compiler/tests/fixtures/runtime/r440-c-aliases/main.ldn)

## platform/cortex_m

M-profile interrupt masking, waiting and memory barriers.

- Save the mask from `disable_interrupts` and restore it, including on
  early returns.
- NMI (the non-maskable interrupt) and HardFault are not masked.
- Waiting can wake spuriously.
- Barriers do not prove completion of a device protocol or supply a
  lifetime discipline for DMA (direct memory access).

[Executable example](../environments/cortex-m/probes/core-cpu.ldn)

## platform/cortex_m/l1

The Cortex-M7's level 1 caches as `core/cache`'s provider, on a cached
profile.

A cached profile is one whose description declares
`compiler.cache("armv7-m-l1", 32)`, the STM32H753's
`descriptions/stm32h753_cached` among the chips refine supports. Reset
has enabled the caches and the entry's return disables them; a program
does neither.

| Call | What it gives |
|---|---|
| `l1.new()` | The handle, its line the description's, 32 bytes. |
| `l1.geometry()` | CCSIDR, the data cache's sets, ways and line. |

Each operation writes every line's address to the System Control Block's
by-address register between two completion barriers, then issues ISB.

Elsewhere on an M-profile target the module declares nothing, and a call
says it is a cached profile's. A program that maintains no cache does not
import it, and its image carries none of `core/cache`.

[Executable example](../compiler/tests/board/stm32h753_cached/app/main.ldn)

## platform/riscv

RV32 machine-mode interrupt masking, the core's own interrupt lines,
waiting and memory barriers, declared on `rv32` alone.

- Save the state from `disable_interrupts` and restore it, including on
  early returns: `restore_interrupts` sets mstatus.MIE again only if it
  was set.
- `enable_lines` and `disable_lines` write `mie`, the machine software,
  timer and external interrupts on the cores that have them. An ESP32's
  CPU lines are enabled through its interrupt matrix or CLIC, which are
  the chip's generated modules.
- Waiting can wake spuriously.
- Barriers do not prove completion of a device protocol or supply a
  lifetime discipline for DMA (direct memory access).

[Executable example](../compiler/tests/fixtures/runtime/library-platform-riscv/main.ldn)

## platform/xtensa

Windowed Xtensa interrupt masking, enabled and pending CPU lines, the
cycle counter, waiting and memory barriers, declared on `xtensa` alone.

Masking:

- Save the PS from `disable_interrupts` or `mask_level_one` and restore
  it in reverse order, including on early returns.
- `mask_level_one` leaves higher-priority interrupts enabled; it may
  only raise the current level from zero or one.
- Masking does not stop exceptions, NMI (the non-maskable interrupt) or
  the debugger.

Device descriptions route peripheral sources through the interrupt matrix
to the CPU lines that `set_enabled_lines` selects.

Waiting and barriers:

- `wait_for_interrupt` enables ordinary interrupts and may wake
  spuriously. Recheck the condition after waking.
- Barriers order accesses; they do not prove a peripheral operation
  completed.

[Executable example](../compiler/tests/fixtures/runtime/library-platform-xtensa/main.ldn)

## platform/x86_64

What an x86-64 processor says of itself, `cpuid` and `xgetbv`, and each
CPU feature level's features, declared on `x86_64` alone. The Linux and
Windows process entries hold the processor to the executable's level
with it, and each gives the same names itself.

| Name | What it is |
|---|---|
| `cpu_words` | `cpuid` leaf 1's ecx, leaf 7's ebx and leaf 0x80000001's ecx, and XCR0's low half when the level needs AVX state. |
| `read_cpu_words` | The words this processor gives. |
| `level` | The level the executable was built for: `x86-64-v1` to `x86-64-v4`. |
| `missing_feature` | The first of the level's features the words lack, or `""`. |

[Executable example](../compiler/tests/fixtures/runtime/linux-level-check/main.ldn)

## platform/riscv/hazard3

Hazard3's external interrupt controller, the RP2350's RISC-V cores'.

| Calls | What they do |
|---|---|
| `enable_irq`, `disable_irq` | Write meiea. |
| `force_irq`, `clear_forced_irq` | Write meifa, which makes an IRQ pending as if its source had asserted it. |

The compiler's dispatch reads meinext and calls slot 16 + IRQ. Enabling
the IRQ, and `mie`'s external line through `platform/riscv`, is the
program's.

[Executable example](../compiler/tests/fixtures/positive/library-platform-riscv-hazard3/main.ldn)
