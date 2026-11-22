with Landin.Optimization;
with Landin.Targets;

--  D2096's block order for a hosted target, under size and speed.  Every
--  native backend lays a routine's blocks out in the IR's order, falling
--  from one block into the next where a jump would only reach the block
--  after it; lowering's order is the order it made the blocks in, which
--  leaves a loop's test at its head and its step after the code that
--  follows the loop.  This pass changes which block comes after which,
--  and nothing a block does.
--
--  First a jump or branch to a block that holds nothing but a jump goes
--  straight to where that jump leads, following a chain of them; a
--  branch whose two edges would then reach one block keeps both as they
--  were.  Nothing reaches a block jumped past any longer, and
--  Rewriting.Compact drops it, so no backend emits a block that only
--  jumps on.
--
--  Then a loop whose head ends in a branch with one edge out of the loop
--  is tested at its foot.  A loop is a back edge's natural loop: its head
--  and every block that reaches a block jumping back to the head without
--  passing the head.  The loop's blocks other than the head keep their
--  order, except that the last of them to jump straight back to the head,
--  the step of a `for`, comes after the rest; the head follows it, then
--  the block the head leaves the loop for, then the other blocks that
--  stood among the loop's but are not in it.  So the body falls into the
--  step, the step into the test, and the test branches back to the
--  body's top while the loop runs and falls out of it when it ends: one
--  taken branch an iteration where there were two, and one instruction
--  fewer.  Entering the loop costs one jump to the test.  Inner loops are
--  placed before the loops around them, and a loop's blocks stay
--  together, so an inlined copy's blocks do too.  A head that is the
--  routine's entry, a loop whose blocks do not all follow its head, and
--  one with no block that jumps straight back stay as they were.
--
--  Firmware targets, Cortex-M, RV32 and Xtensa, are left alone, and so is
--  `--optimize none`.  The work is linear in the routine for threading
--  and, for placing loops, the blocks each loop spans summed over its
--  loops, so a routine's blocks times its deepest nesting at worst.
package Landin.IR.Layout is
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
end Landin.IR.Layout;
