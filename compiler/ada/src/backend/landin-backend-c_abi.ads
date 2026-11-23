--  System V AMD64's native C boundary, derived only from target facts and
--  neutral IR shapes.  Classification and register exhaustion are one plan
--  shared by calls, routine entry and results; no placement is stored in IR.
--
--  The Windows x64 convention is planned here too, in the same terms.  An
--  argument takes the position it has in the call: the first four go in
--  RCX, RDX, R8 and R9, or in XMM0 to XMM3 when they are floats, so GP
--  and SSE register N are the Nth position whichever bank it uses, and
--  each later one takes an eight-byte stack slot above the 32-byte shadow
--  area every call reserves.  An aggregate of one, two, four or eight bytes
--  travels as an integer; any other is copied by the caller and passed by
--  its address, Indirect, and returned through a hidden first pointer.
with Landin.IR;
with Landin.Targets;

package Landin.Backend.C_ABI is

   type Eightbyte_Class is (No_Class, Integer_Class, SSE_Class);
   type Class_Run is array (Positive range 1 .. 2) of Eightbyte_Class;
   type Register_Run is array (Positive range 1 .. 2) of Natural;

   type Classification is record
      Size      : Landin.Targets.Byte_Count := 0;
      Alignment : Landin.Targets.Byte_Alignment := 1;
      Aggregate : Boolean := False;
      Memory    : Boolean := False;
      Count     : Natural range 0 .. 2 := 0;
      Classes   : Class_Run := [others => No_Class];
   end record;

   function Classify
     (Of_Unit : Landin.IR.Unit;
      Part    : Landin.IR.Signature_Part;
      Facts   : Landin.Targets.Target_Facts) return Classification;

   type Location is record
      Shape     : Classification;
      On_Stack  : Boolean := False;
      Stack_At  : Landin.Targets.Byte_Count := 0;
      --  Windows x64: the argument is the address of a copy the caller
      --  makes at Copy_At in its outgoing area, passed in the register or
      --  the stack slot the position names.
      Indirect  : Boolean := False;
      Copy_At   : Landin.Targets.Byte_Count := 0;
      --  One-based within each independent bank.  Results use the same
      --  indices, with two GP and two SSE registers instead of six/eight.
      Registers : Register_Run := [others => 0];
   end record;
   type Location_Array is array (Positive range <>) of Location;

   type Plan (Count : Natural) is record
      Result      : Location;
      Arguments   : Location_Array (1 .. Count);
      --  The banks' used prefixes: on Windows x64 the highest position
      --  that bank holds, so a position the other bank took is a gap.
      GP_Used     : Natural range 0 .. 6 := 0;
      SSE_Used    : Natural range 0 .. 8 := 0;
      Stack_Bytes : Landin.Targets.Byte_Count := 0;
   end record;

   function Assign
     (Of_Unit    : Landin.IR.Unit;
      Parameters : Landin.IR.Signature_Part_Array;
      Result     : Landin.IR.Signature_Part;
      Facts      : Landin.Targets.Target_Facts;
      Maximum : Landin.Targets.Byte_Count :=
        Landin.Targets.Byte_Count'Last) return Plan;

   --  Lowering keeps the original fixed signature and promotes scalar tail
   --  actuals.  The logical aggregate destination is not a C argument.
   function Call_Plan
     (Of_Unit : Landin.IR.Unit;
      Item    : Landin.IR.Item_Id;
      Call    : Landin.IR.Value_Id;
      Facts   : Landin.Targets.Target_Facts;
      Maximum : Landin.Targets.Byte_Count :=
        Landin.Targets.Byte_Count'Last) return Plan;

   function Signature_Plan
     (Of_Unit   : Landin.IR.Unit;
      Signature : Landin.IR.Signature_Id;
      Facts     : Landin.Targets.Target_Facts;
      Maximum : Landin.Targets.Byte_Count :=
        Landin.Targets.Byte_Count'Last) return Plan;

end Landin.Backend.C_ABI;
