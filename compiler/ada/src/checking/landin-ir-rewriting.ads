--  Shared arena rebuild for verified transforms.  Slot, signature, shape,
--  image and semantic instance identities remain unchanged.
with Ada.Containers.Vectors;
private package Landin.IR.Rewriting is
   package Keep_Vectors is new Ada.Containers.Vectors
     (Index_Type => Positive, Element_Type => Boolean);

   --  An instruction a rewrite makes: it comes just before the kept
   --  instruction at code position Before, in that instruction's block.
   --  Its Code.Args operands are Operands (1 .. Code.Args), values of the
   --  item that holds Before.  An item's own instructions and additions
   --  may name its additions, in the order given, as the values after the
   --  item's last: its value count plus one onward.
   type Addition is record
      Before : Positive := 1;
      Code : Instruction;
      Operands : Value_Id_Array (1 .. 2) := [others => No_Value];
   end record;
   package Addition_Vectors is new Ada.Containers.Vectors
     (Index_Type => Positive, Element_Type => Addition);

   procedure Compact (Into : in out Unit; Keep : Keep_Vectors.Vector);

   --  The same with Additions, in ascending order of Before.
   procedure Compact
     (Into : in out Unit;
      Keep : Keep_Vectors.Vector;
      Additions : Addition_Vectors.Vector);
end Landin.IR.Rewriting;
