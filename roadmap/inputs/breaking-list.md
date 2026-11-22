# R20's breaking list

*The input of R20.60, which applies it on `r20-integration` in one promotion. Each of R20.20, R20.30, R20.40 and R20.50 adds its own section; an entry gives the old form, the new one, the decision behind it and whether `refine fix` rewrites it mechanically (D1847). It is not edited once R20.60 is complete.*

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
