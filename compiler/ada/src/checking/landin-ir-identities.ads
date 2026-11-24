--  Bitwise identities, some of which make an instruction the source never
--  computed (D2447): `(x & y) ^ (x & z)` is `x & (y ^ z)`, and the same
--  with `|` for `^`; the choice `(x & y) ^ (~x & z)` is
--  `(x & (y ^ z)) ^ z`; and (D2448) two rotations joined by `^`, `|` or
--  `&`, `rotl (a, m) op rotl (b, n)`, are `rotl (rotl (a, m - n) op b, n)`,
--  one rotation fewer when m = n, and otherwise a chain a two-address
--  target turns without copying a or b.  Each works on every target that
--  has the operations.  Values never cross a block, so each rewrite stays
--  in the block that held the expression.
with Landin.Targets;
private package Landin.IR.Identities is
   --  On verified input; the caller verifies what it did.
   procedure Apply (Into : in out Unit; Facts : Landin.Targets.Target_Facts);
end Landin.IR.Identities;
