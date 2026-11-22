--  Deterministic compiler evidence, not source diagnostics.  Producers append
--  actual outcomes in increasing stable identity order, independently for
--  each section.  Counts of instructions are not assembled object bytes.
private with Ada.Containers.Indefinite_Vectors;
private with Ada.Containers.Vectors;
with Landin.IR;
with Landin.Layouts;
with Landin.Optimization;
with Landin.Provenance;
with Landin.Targets;
with Landin.Targets.Levels;
with Landin.Targets.Layouts;

package Landin.Build_Reports is

   type Specialization_Action is (Declined, Specialized);
   type Decision_Reason is
     (Disabled, No_Static_Dispatch, Unknown_Evidence, Address_Exposed,
      Single_Instance, Forced, Profitable, Cost_Threshold, Unsupported_Proof);

   type Specialization_Decision is record
      Item              : Landin.IR.Item_Id := Landin.IR.No_Item;
      Template          : Landin.IR.Declaration_Id := Landin.IR.No_Declaration;
      Instance_Position : Natural := 0;
      Action            : Specialization_Action := Declined;
      Reason            : Decision_Reason := No_Static_Dispatch;
      Entry_Calls       : Natural := 0;
      Loop_Depth        : Natural := 0;
      Represented_Bytes : Landin.Targets.Byte_Count := 0;
      Benefit           : Natural := 0;
      Estimated_Growth  : Natural := 0;
      Direct_Calls_Made : Natural := 0;
      Retains_Evidence_ABI : Boolean := True;
      --  Indirect calls remaining in this item after specialization,
      --  including erased dispatch and ordinary function-value calls.
      Retains_Fallback  : Boolean := True;
   end record;

   --  What D339 did with one direct call at `--optimize speed` on a hosted
   --  target, and the rule that decided it.  The reasons a call stays one,
   --  in the order the inliner asks them:
   --  No_Body           the callee has no body here: an import or external;
   --  Address_Exposed   its address is taken, or it is an entry or export;
   --  Callee_Shape      its convention, transport, result, placement,
   --                    parameters or slots are not a copyable routine's,
   --                    or it never returns, or it is a received copy's;
   --  Assembly          it holds an assembly block;
   --  Weight            it weighs more than Body_Bound as D2100 counts it;
   --  Recursive         it is the routine making the call;
   --  Arguments         an argument cannot be handed to the copy exactly:
   --                    a result's storage, an addressed or aggregate
   --                    parameter given something other than its place;
   --  Failure_Shape     it can fail and the call is not lowering's failure
   --                    test with nothing else reading its status;
   --  Crossing          a value made before the call that cannot travel
   --                    through a slot is read after it;
   --  Budget            the caller's growth bound was spent on calls
   --                    planned before it.
   type Copy_Reason is
     (Copied, No_Body, Address_Exposed, Callee_Shape, Assembly, Weight,
      Recursive, Arguments, Failure_Shape, Crossing, Budget);

   type Copy_Decision is record
      Caller : Landin.IR.Item_Id := Landin.IR.No_Item;
      Callee : Landin.IR.Item_Id := Landin.IR.No_Item;
      Site   : Landin.Provenance.Origin;
      Reason : Copy_Reason := Copied;
      --  The callee's weight in Landin.IR.Effects' operations as far as
      --  the inliner measured it: past Body_Bound it stops counting.
      Weight : Natural := 0;
      --  Loop depth of the call; deeper calls are planned first.
      Depth  : Natural := 0;
   end record;

   type Routine_Statistics is record
      Item              : Landin.IR.Item_Id := Landin.IR.No_Item;
      --  No_Item means an independently emitted body; otherwise this is
      --  the earlier stable body identity actually shared by the symbol.
      Shared_With       : Landin.IR.Item_Id := Landin.IR.No_Item;
      --  Every backend fills every field below for every routine it emits.
      --  The frame: what the prologue reserves below the frame record and
      --  the registers it pushes, for the routine's cells, spill and save
      --  homes and incoming register homes.  It is not the routine's
      --  stack, which Stack_Bytes is.
      Frame_Bytes       : Landin.Targets.Byte_Count := 0;
      Spill_Bytes       : Landin.Targets.Byte_Count := 0;
      --  The callee-saved registers the routine saves, in its frame or
      --  pushed beside its frame record; never the frame record itself.
      Save_Bytes        : Landin.Targets.Byte_Count := 0;
      --  The distinct registers the allocation holds a value or slot in,
      --  saved or not; zero on a backend that gives each one a home.
      Register_Count    : Natural := 0;
      Spill_Count       : Natural := 0;
      --  Static sites in the routine's final text, as
      --  Landin.Backend.Site_Counts counts them.
      Instructions      : Natural := 0;
      Stack_Loads       : Natural := 0;
      Stack_Stores      : Natural := 0;
      Direct_Calls      : Natural := 0;
      Indirect_Calls    : Natural := 0;
      --  D447's depth report (D467).  The deepest this routine's own code
      --  takes the stack pointer below where its caller's stood before the
      --  call: a return address the call pushes, the frame record, the
      --  frame, and the largest area it reserves around one call or pushes
      --  for a moment.  No callee's frame is in it.  Zero for a naked
      --  routine, whose text owns the stack.
      Stack_Bytes       : Landin.Targets.Byte_Count := 0;
      --  A failed check here calls the selected handler or D361's report
      --  on this stack, rather than ending at a trap instruction.
      Calls_Panic       : Boolean := False;
      --  Calls into a runtime helper the target's toolchain supplies, such
      --  as Cortex-M0's __aeabi_* division, whose stack is not known here.
      Helper_Calls      : Natural := 0;
      Naked             : Boolean := False;
      --  D2108: a recorded-writes allocation (D1503, D1567) planned
      --  registers, but its second emission wrote one of them at a
      --  position the plan holds it at, so the routine kept its first
      --  emission, every value in its home.  Refused_Register is the
      --  register's name as the target's assembly spells it, padded with
      --  spaces; Refused_Position the position of the write in layout
      --  order, which is the IR value it emitted.
      Kept_Homes        : Boolean := False;
      Refused_Register  : String (1 .. 4) := [others => ' '];
      Refused_Position  : Natural := 0;
   end record;

   type Report is tagged private;
   procedure Clear (Into : in out Report);
   procedure Append
     (Into : in out Report; Decision : Specialization_Decision);
   procedure Append
     (Into : in out Report; Statistics : Routine_Statistics);
   --  In increasing caller order, a caller's calls in its value order.
   procedure Append (Into : in out Report; Decision : Copy_Decision);
   procedure Append_Layout
     (Into : in out Report; Nominal_Position : Positive;
      Policy : Landin.Layouts.Policy; Placement : Landin.Targets.Layouts.Plan);

   function Specialization_Count (Of_Report : Report) return Natural;
   function Nth_Specialization
     (Of_Report : Report; Index : Positive) return Specialization_Decision;
   function Copy_Count (Of_Report : Report) return Natural;
   function Nth_Copy
     (Of_Report : Report; Index : Positive) return Copy_Decision;
   function Routine_Count (Of_Report : Report) return Natural;
   function Nth_Routine
     (Of_Report : Report; Index : Positive) return Routine_Statistics;
   function Layout_Count (Of_Report : Report) return Natural;
   function Layout_Position
     (Of_Report : Report; Index : Positive) return Positive;
   function Layout_Policy
     (Of_Report : Report; Index : Positive) return Landin.Layouts.Policy;
   function Layout_Plan
     (Of_Report : Report; Index : Positive) return Landin.Targets.Layouts.Plan;

   function Spelling (Value : Specialization_Action) return String;
   function Spelling (Value : Decision_Reason) return String;
   function Spelling (Value : Copy_Reason) return String;

   --  Pure renderer.  No paths, clocks, addresses or hash iteration.  Source
   --  filename/origin adapters may be added by integration without changing
   --  the producer record contracts or mistaking estimates for measurements.
   function JSON
     (Of_Report : Report;
      Facts : Landin.Targets.Target_Facts;
      Options : Landin.Optimization.Options) return String;

   --  The same, naming the CPU feature level the build assumed beside its
   --  target; the one above names the target's default level.
   function JSON
     (Of_Report : Report;
      Facts : Landin.Targets.Target_Facts;
      Level : Landin.Targets.Levels.Feature_Level;
      Options : Landin.Optimization.Options) return String;

private

   package Decision_Vectors is new Ada.Containers.Vectors
     (Index_Type => Positive, Element_Type => Specialization_Decision);
   package Copy_Vectors is new Ada.Containers.Vectors
     (Index_Type => Positive, Element_Type => Copy_Decision);
   package Statistics_Vectors is new Ada.Containers.Vectors
     (Index_Type => Positive, Element_Type => Routine_Statistics);
   type Layout_Record (Count : Natural) is record
      Position : Positive;
      Policy : Landin.Layouts.Policy;
      Placement : Landin.Targets.Layouts.Plan (Count);
   end record;
   package Layout_Vectors is new Ada.Containers.Indefinite_Vectors
     (Index_Type => Positive, Element_Type => Layout_Record);

   type Report is tagged record
      Decisions : Decision_Vectors.Vector;
      Copies : Copy_Vectors.Vector;
      Routines : Statistics_Vectors.Vector;
      Layouts : Layout_Vectors.Vector;
   end record;

end Landin.Build_Reports;
