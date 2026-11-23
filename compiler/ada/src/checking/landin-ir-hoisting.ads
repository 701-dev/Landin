with Landin.Optimization;
with Landin.Targets;

--  D2149's loop-invariant values, for a hosted target at speed.  Values
--  are block-local and only slots cross a block boundary, so a loop
--  remakes in every iteration what does not change in it: a float
--  constant comes from the constant pool at each use, and arithmetic over
--  slots the loop never stores is done again each time round.
--
--  A loop is a back edge's natural loop, and a value belongs to the
--  innermost loop holding its block.  A loop qualifies when exactly one
--  block outside it reaches its head, by a jump: that block is its
--  preheader.  Within a qualifying loop an operand is invariant when it is
--  an integer, bool or atom constant, or a load of a private slot (one
--  that nothing names but its own loads and stores) that no block of the
--  loop stores.  A value is invariant when it is a float constant, or an
--  operation that cannot trap, call, read or write memory over invariant
--  operands: bitwise, wrapping and compared integers, a choice, unchecked
--  integer arithmetic, and float arithmetic, which never traps.  An
--  invariant value of a number type that something other than an
--  invariant value uses is made once at the end of the preheader, before
--  its jump, and stored in a new private slot; the loop reads that slot
--  where it made the value, and what made it in the loop and nothing else
--  needs is dropped.  Since nothing in the loop can trap or write memory
--  on account of what moved, and the preheader runs exactly when the loop
--  is entered, the program computes what it did; a loop entered and left
--  at its test computes the moved values once without using them.
--
--  An integer constant an instruction takes as its immediate is not worth
--  a register over the loop, and a comparison stays beside the branch
--  that reads its flags.  The work is linear in the routine plus, for
--  each loop, the blocks it spans, and one rebuild of the unit adds a
--  load in place of each moved value and its copy in the preheader.
--  Firmware targets and `--optimize none` and `size` are left alone.
package Landin.IR.Hoisting is
   procedure Run
     (Into : in out Unit;
      Facts : Landin.Targets.Target_Facts;
      Objective : Landin.Optimization.Objective);

   --  For the driver after the passes before it verified Into against
   --  these same Facts.  A pass that changes anything verifies its output.
   procedure Run_On_Verified
     (Into : in out Unit;
      Facts : Landin.Targets.Target_Facts;
      Objective : Landin.Optimization.Objective);
end Landin.IR.Hoisting;
