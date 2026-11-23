with Ada.Containers.Vectors;
with Landin.IR.Control_Flow;
with Landin.IR.Effects;
with Landin.IR.Scratch_Arrays;
with Landin.IR.Verifier;

package body Landin.IR.Hoisting is
   use type Landin.Optimization.Objective;
   use type Landin.Types.Magnitude;
   use type Landin.Targets.Architecture;

   package Block_Arrays is new Scratch_Arrays (Block_Id, No_Block);
   package Counts is new Scratch_Arrays (Natural, 0);
   package Flags is new Scratch_Arrays (Boolean, False);

   --  What a value in a qualifying loop is: something the loop changes;
   --  an invariant operand not worth moving on its own, a constant an
   --  instruction can take as it is or a load of a slot the loop leaves
   --  alone; or an invariant value that may move.
   type Value_Class is (Varies, Operand_Only, Invariant);
   package Classes is new Scratch_Arrays (Value_Class, Varies);

   --  One moved value: its item, the preheader it is made in, the value,
   --  and the new slot that carries it, which is the item's next.
   type Move is record
      Item : Item_Id := No_Item;
      Preheader : Block_Id := No_Block;
      Value : Value_Id := No_Value;
      Slot : Slot_Id := No_Slot;
      Carrier : Slot_Record;
      --  An address move makes Place's address, which the loop's element
      --  accesses then reach through Slot, rather than Value.
      Address : Boolean := False;
      Place : Storage;
   end record;
   package Move_Vectors is new Ada.Containers.Vectors (Positive, Move);
   package Value_Maps is new Ada.Containers.Vectors (Positive, Value_Id);
   package Block_Maps is new Ada.Containers.Vectors (Positive, Block_Id);

   function Plain (Code : Instruction) return Boolean
     is (Code.Pointee = No_Pointee
         and then Code.Signature = No_Signature
         and then Code.Atom_Set = No_Atom_Set);

   function Number_Result (Code : Instruction) return Boolean
     is (Code.Result in Landin.Types.Integer_Name
           | Landin.Types.Float_Name);

   procedure Run
     (Into : in out Unit;
      Facts : Landin.Targets.Target_Facts;
      Objective : Landin.Optimization.Objective) is
   begin
      Verifier.Verify (Into, Facts);
      Run_On_Verified (Into, Facts, Objective);
   end Run;

   procedure Run_On_Verified
     (Into : in out Unit;
      Facts : Landin.Targets.Target_Facts;
      Objective : Landin.Optimization.Objective)
   is
      --  How many registers a loop's slots and moved values may take
      --  before a move would push a slot out of its register: the slot
      --  registers each backend allocates over an interval, less a few
      --  its values use.  RV64 keeps floats in frame homes, where a slot
      --  costs one load and a pooled constant two instructions.
      Integer_Budget : constant Natural :=
        (case Landin.Targets.Architecture_Of (Facts) is
            when Landin.Targets.X86_64 => 4,
            when Landin.Targets.Arm64 => 12,
            when Landin.Targets.RV64 => 10,
            when others => 0);
      Float_Budget : constant Natural :=
        (case Landin.Targets.Architecture_Of (Facts) is
            when Landin.Targets.X86_64 => 6,
            when Landin.Targets.Arm64 => 16,
            when Landin.Targets.RV64 => 8,
            when others => 0);

      --  SysV x86-64 preserves no XMM register across a call, so a
      --  float moved out of a loop that calls would wait in memory.
      Float_Lost : constant Boolean :=
        Landin.Targets.Architecture_Of (Facts) = Landin.Targets.X86_64;

      --  RISC-V compares two registers, or one with zero, so there a
      --  constant a loop compares with is made in every iteration unless
      --  a register holds it.
      Compares_Registers : constant Boolean :=
        Landin.Targets.Architecture_Of (Facts) = Landin.Targets.RV64;

      --  Which arrays' addresses a loop holds.  arm64 forms both a
      --  frame array's and a module datum's address with instructions of
      --  their own each time; x86-64 indexes a frame array from rbp in the
      --  access itself, so only a datum's leaq is worth a register there.
      --  RV64 measured no better with either.
      Frame_Bases : constant Boolean :=
        Landin.Targets.Architecture_Of (Facts) = Landin.Targets.Arm64;
      Datum_Bases : constant Boolean :=
        Landin.Targets.Architecture_Of (Facts)
          in Landin.Targets.Arm64 | Landin.Targets.X86_64;

      procedure Hoist;
      procedure Hoist is
         Moves : Move_Vectors.Vector;
         --  By index in Into.Code: the move a value becomes a load for, and
         --  whether it is dropped.  By index in Into.Blocks: the first move
         --  a preheader makes.
         Root_Owner : constant Counts.Owner :=
           Counts.Create (Natural (Into.Code.Length));
         Drop_Owner : constant Flags.Owner :=
           Flags.Create (Natural (Into.Code.Length));
         Reach_Owner : constant Counts.Owner :=
           Counts.Create (Natural (Into.Code.Length));
         First_Move_Owner : constant Counts.Owner :=
           Counts.Create (Natural (Into.Blocks.Length));

         procedure Plan_Item (Item : Item_Id);
         procedure Plan_Item (Item : Item_Id) is
            Held : constant Item_Record :=
              Into.Items.Element (Positive (Item));
            Root : Counts.Elements renames Root_Owner.Data.all;
            Drop : Flags.Elements renames Drop_Owner.Data.all;
            Reach : Counts.Elements renames Reach_Owner.Data.all;
            First_Move : Counts.Elements renames First_Move_Owner.Data.all;
            Total : constant Natural := Held.Blocks.Count;
            Graph : constant Control_Flow.Graph :=
              Control_Flow.Make (Into, Item);
            Eligible_Owner : constant Flags.Owner :=
              Flags.Create (Held.Slots.Count);
            Eligible : Flags.Elements renames Eligible_Owner.Data.all;
            Stored_In_Owner : constant Block_Arrays.Owner :=
              Block_Arrays.Create (Held.Slots.Count);
            Stored_In : Block_Arrays.Elements renames Stored_In_Owner.Data.all;
            Class_Owner : constant Classes.Owner :=
              Classes.Create (Held.Values.Count);
            Class : Classes.Elements renames Class_Owner.Data.all;
            Live_Owner : constant Counts.Owner :=
              Counts.Create (Held.Values.Count);
            Live : Counts.Elements renames Live_Owner.Data.all;
            --  The depth-first walk, as Landin.IR.Layout's.
            Order_Owner : constant Counts.Owner := Counts.Create (Total);
            Order : Counts.Elements renames Order_Owner.Data.all;
            Tried_Owner : constant Counts.Owner := Counts.Create (Total);
            Tried : Counts.Elements renames Tried_Owner.Data.all;
            On_Path_Owner : constant Flags.Owner := Flags.Create (Total);
            On_Path : Flags.Elements renames On_Path_Owner.Data.all;
            Path_Owner : constant Block_Arrays.Owner :=
              Block_Arrays.Create (Total);
            Path : Block_Arrays.Elements renames Path_Owner.Data.all;
            Heads_Owner : constant Block_Arrays.Owner :=
              Block_Arrays.Create (Total);
            Heads : Block_Arrays.Elements renames Heads_Owner.Data.all;
            Head_Total : Natural := 0;
            First_Back_Owner : constant Counts.Owner := Counts.Create (Total);
            First_Back : Counts.Elements renames First_Back_Owner.Data.all;
            Back_Source_Owner : constant Block_Arrays.Owner :=
              Block_Arrays.Create (2 * Total);
            Back_Source : Block_Arrays.Elements renames
              Back_Source_Owner.Data.all;
            Back_Next_Owner : constant Counts.Owner :=
              Counts.Create (2 * Total);
            Back_Next : Counts.Elements renames Back_Next_Owner.Data.all;
            Back_Total : Natural := 0;
            --  The innermost loop holding each block, by its head; the head
            --  whose loop a block was last found in; that loop's blocks.
            Loop_Of_Owner : constant Block_Arrays.Owner :=
              Block_Arrays.Create (Total);
            Loop_Of : Block_Arrays.Elements renames Loop_Of_Owner.Data.all;
            Stamp_Owner : constant Block_Arrays.Owner :=
              Block_Arrays.Create (Total);
            Stamp : Block_Arrays.Elements renames Stamp_Owner.Data.all;
            Members_Owner : constant Block_Arrays.Owner :=
              Block_Arrays.Create (Total);
            Members : Block_Arrays.Elements renames Members_Owner.Data.all;
            Height : Natural := 0;
            Clock : Natural := 0;
            Added : Natural := 0;
            Seen_Owner : constant Counts.Owner :=
              Counts.Create (Held.Slots.Count);
            Seen : Counts.Elements renames Seen_Owner.Data.all;
            Scan : Natural := 0;
            Parameter_Owner : constant Flags.Owner :=
              Flags.Create (Held.Slots.Count);
            Parameter : Flags.Elements renames Parameter_Owner.Data.all;
            Compared_Owner : constant Flags.Owner :=
              Flags.Create (Held.Values.Count);
            Compared : Flags.Elements renames Compared_Owner.Data.all;
            Counted_Owner : constant Block_Arrays.Owner :=
              Block_Arrays.Create (Held.Slots.Count);
            Counted : Block_Arrays.Elements renames Counted_Owner.Data.all;

            function Code_At (Value : Value_Id) return Instruction
              is (Into.Code.Element (Held.Values.First + Positive (Value)));

            function Operand (Code : Instruction; Position : Positive)
              return Value_Id
              is (Into.Operands.Element (Code.First_Arg + Position));

            function Block_Start (Block : Block_Id) return Natural
              is (Into.Blocks.Element (Held.Blocks.First + Positive (Block))
                    .First_Value - Held.Values.First);

            function Block_Length (Block : Block_Id) return Natural
              is (Into.Blocks.Element (Held.Blocks.First + Positive (Block))
                    .Values);

            function Ending (Block : Block_Id) return Instruction
              is (Code_At (Value_Id (Block_Start (Block)
                                     + Block_Length (Block))));

            procedure Pin (Place : Storage);
            procedure Pin (Place : Storage) is
            begin
               case Place.Kind is
                  when Frame_Slot =>
                     if Place.Slot /= No_Slot then
                        Eligible (Positive (Place.Slot)) := False;
                     end if;
                  when Runtime_Address =>
                     if Place.Address /= No_Slot then
                        Eligible (Positive (Place.Address)) := False;
                     end if;
                  when Module_Datum => null;
               end case;
            end Pin;

            --  An operation that, over invariant operands, may be made
            --  before the loop: no trap, call, memory access or control.
            function Movable (Code : Instruction) return Boolean;
            function Movable (Code : Instruction) return Boolean is
            begin
               if not Plain (Code) or else Code.Args = 0 then
                  return False;
               end if;
               case Code.Op is
                  when Complement | Logical_Not | Wrapping_Multiply
                     | Wrapping_Add | Wrapping_Subtract | Bitwise_And
                     | Bitwise_Xor | Bitwise_Or | Rotate_Left
                     | Comparison_Kind | Choose =>
                     return True;
                  when Add | Subtract | Multiply | Negation =>
                     return Code.Result in Landin.Types.Float_Name
                       or else Code.Unchecked;
                  when Divide =>
                     return Code.Result in Landin.Types.Float_Name;
                  when Shift_Left | Shift_Right =>
                     --  A shift traps only on a negative amount ([1950]).
                     declare
                        Amount : constant Landin.Types.Type_Kind :=
                          Code_At (Operand (Code, 2)).Result;
                     begin
                        return Code.Unchecked
                          or else (Amount in Landin.Types.Integer_Name
                                   and then not Landin.Types.Is_Signed
                                     (Landin.Types.Integer_Name (Amount)));
                     end;
                  when others =>
                     return False;
               end case;
            end Movable;

            --  Whether Code indexes a whole array of plain scalars, a frame
            --  slot that is not a parameter or a module datum: the storage,
            --  and the shape an address slot reaching it has.
            function Array_Reached
              (Code : Instruction; Place : out Storage;
               Shape : out Field_Shape) return Boolean;
            function Array_Reached
              (Code : Instruction; Place : out Storage;
               Shape : out Field_Shape) return Boolean is
            begin
               Place := (Kind => Module_Datum, Datum => No_Item);
               Shape := (others => <>);
               if Code.Op not in Load_Element | Store_Element
                 or else Code.Element_Field /= 0 or else Code.Nested.Count /= 0
                 or else Code.Below_Element.Count /= 0
                 or else Code.Variant_Case /= 0
                 or else Code.Variant_Payload_Field /= 0
                 or else Code.Signature /= No_Signature
               then
                  return False;
               end if;
               if Code.Slot /= No_Slot then
                  declare
                     Slot : constant Slot_Record := Into.Slots.Element
                       (Held.Slots.First + Positive (Code.Slot));
                  begin
                     if not Frame_Bases or else not Slot.Array_Shape
                       or else Slot.Addressed
                       or else Parameter (Positive (Code.Slot))
                     then
                        return False;
                     end if;
                  end;
                  Place := (Kind => Frame_Slot, Slot => Code.Slot);
                  Shape := Whole_Slot_Array_Shape (Into, Item, Code.Slot);
               elsif Datum_Bases and then Code.Named /= No_Item
                 and then Result_Of (Into, Code.Named)
                   = Landin.Types.Fixed_Array
               then
                  Place := (Kind => Module_Datum, Datum => Code.Named);
                  Shape := Whole_Array_Shape (Into, Code.Named);
               else
                  return False;
               end if;
               return Shape.Kind = Array_Field_Shape
                 and then Shape.Nominal = No_Nominal_Type
                 and then Shape.Signature = No_Signature
                 and then Shape.Atoms = No_Atom_Set
                 and then Shape.Pointee = No_Pointee
                 and then Shape.Packing.Bits = 0;
            end Array_Reached;

            procedure Analyse (Head : Block_Id);
            procedure Analyse (Head : Block_Id) is
               Member_Total : Natural := 0;
               Read_At : Positive;
               Edge : Natural;
               Escaped : Boolean := False;
               Preheader : Block_Id := No_Block;
               Outside : Natural := 0;
               Integer_Held : Natural := 0;
               Float_Held : Natural := 0;
               Calls : Boolean := False;
               Loop_Moves : constant Natural := Natural (Moves.Length);

               --  Whether a move of Code may take one more register, and
               --  the move of an equal constant this loop already made.
               function Room (Code : Instruction) return Boolean
                 is (if Code.Result in Landin.Types.Float_Name
                     then Float_Held < Float_Budget
                       and then not (Calls and then Float_Lost)
                     else Integer_Held < Integer_Budget);

               function Same_Constant (Code : Instruction) return Natural;
               function Same_Constant (Code : Instruction) return Natural is
               begin
                  if Code.Op = Number then
                     for Index in Loop_Moves + 1 .. Natural (Moves.Length)
                     loop
                        declare
                           Earlier : constant Instruction :=
                             Code_At (Moves.Element (Index).Value);
                        begin
                           if Earlier.Op = Number
                             and then Earlier.Result = Code.Result
                             and then Earlier.Number = Code.Number
                             and then Earlier.Negated = Code.Negated
                           then
                              return Index;
                           end if;
                        end;
                     end loop;
                  end if;
                  return 0;
               end Same_Constant;

               procedure Join (Block : Block_Id);
               procedure Join (Block : Block_Id) is
               begin
                  if Stamp (Positive (Block)) /= Head then
                     Stamp (Positive (Block)) := Head;
                     Member_Total := Member_Total + 1;
                     Members (Member_Total) := Block;
                  end if;
               end Join;
            begin
               if Head = First_Block then
                  return;
               end if;
               Join (Head);
               Edge := First_Back (Positive (Head));
               while Edge /= 0 loop
                  Join (Back_Source (Edge));
                  Edge := Back_Next (Edge);
               end loop;
               Read_At := 2;
               while Read_At <= Member_Total and then not Escaped loop
                  Edge := Control_Flow.First_Predecessor
                    (Graph, Members (Read_At));
                  while Edge /= 0 loop
                     declare
                        Source : constant Block_Id :=
                          Control_Flow.Predecessor (Graph, Edge);
                     begin
                        Escaped := Escaped or else Source = First_Block;
                        Join (Source);
                     end;
                     Edge := Control_Flow.Next_Predecessor (Graph, Edge);
                  end loop;
                  Read_At := Read_At + 1;
               end loop;
               for Index in 1 .. Member_Total loop
                  if Loop_Of (Positive (Members (Index))) = No_Block then
                     Loop_Of (Positive (Members (Index))) := Head;
                  end if;
               end loop;
               if Escaped then
                  return;
               end if;
               --  The one block outside the loop that reaches its head.
               Edge := Control_Flow.First_Predecessor (Graph, Head);
               while Edge /= 0 loop
                  declare
                     Source : constant Block_Id :=
                       Control_Flow.Predecessor (Graph, Edge);
                  begin
                     if Stamp (Positive (Source)) /= Head then
                        Outside := Outside + 1;
                        Preheader := Source;
                     end if;
                  end;
                  Edge := Control_Flow.Next_Predecessor (Graph, Edge);
               end loop;
               if Outside /= 1 or else Ending (Preheader).Op /= Jump
                 or else First_Move (Held.Blocks.First + Positive (Preheader))
                   /= 0
               then
                  return;
               end if;
               for Index in 1 .. Member_Total loop
                  declare
                     Block : constant Block_Id := Members (Index);
                  begin
                     for V in Block_Start (Block) + 1
                       .. Block_Start (Block) + Block_Length (Block)
                     loop
                        declare
                           Code : constant Instruction :=
                             Code_At (Value_Id (V));
                        begin
                           if Code.Op = Store
                             and then Eligible (Positive (Code.Slot))
                           then
                              Stored_In (Positive (Code.Slot)) := Head;
                           end if;
                        end;
                     end loop;
                  end;
               end loop;
               --  The slots the loop needs in registers: those some block
               --  of it reads before it writes them.
               for Index in 1 .. Member_Total loop
                  declare
                     Block : constant Block_Id := Members (Index);
                  begin
                     Scan := Scan + 1;
                     for V in Block_Start (Block) + 1
                       .. Block_Start (Block) + Block_Length (Block)
                     loop
                        declare
                           Code : constant Instruction :=
                             Code_At (Value_Id (V));
                        begin
                           Calls := Calls
                             or else Effects.Of_Code (Code.Op).Calls;
                           if Code.Op in Load | Store
                             and then Seen (Positive (Code.Slot)) /= Scan
                           then
                              Seen (Positive (Code.Slot)) := Scan;
                              if Code.Op = Load
                                and then Counted (Positive (Code.Slot))
                                  /= Head
                              then
                                 Counted (Positive (Code.Slot)) := Head;
                                 if Into.Slots.Element
                                   (Held.Slots.First
                                    + Positive (Code.Slot)).Of_Type
                                   in Landin.Types.Float_Name
                                 then
                                    Float_Held := Float_Held + 1;
                                 else
                                    Integer_Held := Integer_Held + 1;
                                 end if;
                              end if;
                           end if;
                        end;
                     end loop;
                  end;
               end loop;
               for Index in 1 .. Member_Total loop
                  declare
                     Block : constant Block_Id := Members (Index);
                     First : constant Positive := Block_Start (Block) + 1;
                     Last : constant Natural :=
                       Block_Start (Block) + Block_Length (Block);
                  begin
                     if Loop_Of (Positive (Block)) = Head then
                        for V in First .. Last loop
                           declare
                              Code : constant Instruction :=
                                Code_At (Value_Id (V));
                              All_Invariant : Boolean := True;
                           begin
                              if not Plain (Code) then
                                 Class (V) := Varies;
                              elsif Code.Op = Load then
                                 Class (V) :=
                                   (if Eligible (Positive (Code.Slot))
                                      and then Stored_In (Positive (Code.Slot))
                                        /= Head
                                    then Operand_Only else Varies);
                              elsif Code.Op in Number | Truth | Atom then
                                 Class (V) :=
                                   (if Code.Result in Landin.Types.Float_Name
                                    then Invariant else Operand_Only);
                              elsif Movable (Code) then
                                 for A in 1 .. Code.Args loop
                                    All_Invariant := All_Invariant
                                      and then Class
                                        (Positive (Operand (Code, A)))
                                        /= Varies;
                                 end loop;
                                 Class (V) :=
                                   (if All_Invariant then Invariant
                                    else Varies);
                              else
                                 Class (V) := Varies;
                              end if;
                           end;
                        end loop;
                        --  Backward, what still has a reader made as itself:
                        --  an invariant nothing reads is dropped, an invariant
                        --  number something reads moves and reads nothing
                        --  here, and the rest stay and read their operands.
                        for V in reverse First .. Last loop
                           declare
                              Code : constant Instruction :=
                                Code_At (Value_Id (V));
                              At_Code : constant Positive :=
                                Held.Values.First + V;
                           begin
                              if Class (V) /= Varies and then Live (V) = 0 then
                                 Drop (At_Code) := True;
                              elsif Number_Result (Code)
                                and then (Class (V) = Invariant
                                          or else Compared (V))
                                and then Same_Constant (Code) /= 0
                              then
                                 Root (At_Code) := Same_Constant (Code);
                              elsif Number_Result (Code)
                                and then (Class (V) = Invariant
                                          or else Compared (V))
                                and then Room (Code)
                              then
                                 if Code.Result in Landin.Types.Float_Name
                                 then
                                    Float_Held := Float_Held + 1;
                                 else
                                    Integer_Held := Integer_Held + 1;
                                 end if;
                                 Added := Added + 1;
                                 Moves.Append
                                   (Move'(Item => Item, Preheader => Preheader,
                                     Value => Value_Id (V),
                                     Slot => Slot_Id
                                       (Held.Slots.Count + Added),
                                     Carrier =>
                                       (Of_Type => Code.Result,
                                        Site => Code.Site,
                                        Inlined => Into.Blocks.Element
                                          (Held.Blocks.First
                                           + Positive (Block)).Inlined,
                                        others => <>),
                                     Address => False,
                                     Place => <>));
                                 Root (At_Code) := Moves.Last_Index;
                              else
                                 for A in 1 .. Code.Args loop
                                    Live (Positive (Operand (Code, A))) :=
                                      Live (Positive (Operand (Code, A))) + 1;
                                    if Compares_Registers
                                      and then Code.Op in Comparison_Kind
                                    then
                                       declare
                                          Read : constant Instruction :=
                                            Code_At (Operand (Code, A));
                                       begin
                                          Compared
                                            (Positive (Operand (Code, A))) :=
                                            Read.Op = Number
                                            and then Read.Result
                                              in Landin.Types.Integer_Name
                                            and then Read.Number /= 0;
                                       end;
                                    end if;
                                 end loop;
                              end if;
                           end;
                        end loop;
                     end if;
                  end;
               end loop;
               --  An element access to a whole array, in the frame or a
               --  module datum, reaches it through an address made once.
               for Index in 1 .. Member_Total loop
                  declare
                     Block : constant Block_Id := Members (Index);
                  begin
                     if Loop_Of (Positive (Block)) = Head then
                        for V in Block_Start (Block) + 1
                          .. Block_Start (Block) + Block_Length (Block)
                        loop
                           declare
                              Code : constant Instruction :=
                                Code_At (Value_Id (V));
                              Place : Storage;
                              Shape : Field_Shape;
                              Found : Natural := 0;
                           begin
                              if Array_Reached (Code, Place, Shape) then
                                 for M in Loop_Moves + 1
                                   .. Natural (Moves.Length)
                                 loop
                                    if Moves.Element (M).Address
                                      and then Moves.Element (M).Place = Place
                                    then
                                       Found := M;
                                    end if;
                                 end loop;
                                 if Found = 0
                                   and then Integer_Held < Integer_Budget
                                 then
                                    Integer_Held := Integer_Held + 1;
                                    Added := Added + 1;
                                    Moves.Append
                                      (Move'(Item => Item,
                                             Preheader => Preheader,
                                             Value => Value_Id (V),
                                             Slot => Slot_Id
                                               (Held.Slots.Count + Added),
                                             Carrier =>
                                               (Of_Type => Landin.Types.Usize,
                                                Element => Shape,
                                                Addressed => True,
                                                Site => Code.Site,
                                                Inlined => Into.Blocks.Element
                                                  (Held.Blocks.First
                                                   + Positive (Block)).Inlined,
                                                others => <>),
                                             Address => True,
                                             Place => Place));
                                    Found := Moves.Last_Index;
                                 end if;
                                 Reach (Held.Values.First + V) := Found;
                              end if;
                           end;
                        end loop;
                     end if;
                  end;
               end loop;
            end Analyse;
         begin
            for P in 1 .. Parameter_Count (Into, Item) loop
               Parameter (Positive (Nth_Parameter (Into, Item, P))) := True;
            end loop;
            for S in 1 .. Held.Slots.Count loop
               declare
                  Slot : constant Slot_Record :=
                    Into.Slots.Element (Held.Slots.First + S);
               begin
                  Eligible (S) :=
                    not Slot.Aggregate and then not Slot.Array_Shape
                    and then not Slot.Addressed
                    and then Slot.Signature = No_Signature
                    and then Slot.Atom_Set = No_Atom_Set
                    and then Slot.Pointee = No_Pointee;
               end;
            end loop;
            for V in 1 .. Held.Values.Count loop
               declare
                  Code : constant Instruction := Code_At (Value_Id (V));
               begin
                  Pin (Code.Source);
                  Pin (Code.Destination);
                  if Code.Slot /= No_Slot and then Code.Op not in Load | Store
                  then
                     Eligible (Positive (Code.Slot)) := False;
                  end if;
                  for A in 1 .. Code.Assembly_Run.Count loop
                     declare
                        Output : constant Slot_Id :=
                          Into.Assembly_Operands.Element
                            (Code.Assembly_Run.First + A).Output;
                     begin
                        if Output /= No_Slot then
                           Eligible (Positive (Output)) := False;
                        end if;
                     end;
                  end loop;
               end;
            end loop;
            --  The walk from the entry: an edge to a block still on the path
            --  closes a loop there, and heads finish inner loops first.
            Height := 1;
            Clock := 1;
            Path (1) := First_Block;
            Order (1) := 1;
            On_Path (1) := True;
            while Height > 0 loop
               declare
                  Block : constant Positive := Positive (Path (Height));
               begin
                  if Tried (Block) < 2 then
                     Tried (Block) := Tried (Block) + 1;
                     declare
                        Target : constant Block_Id := Control_Flow.Successor
                          (Graph, Block_Id (Block), Tried (Block));
                     begin
                        if Target = No_Block then
                           null;
                        elsif Order (Positive (Target)) = 0 then
                           Clock := Clock + 1;
                           Order (Positive (Target)) := Clock;
                           On_Path (Positive (Target)) := True;
                           Height := Height + 1;
                           Path (Height) := Target;
                        elsif On_Path (Positive (Target)) then
                           Back_Total := Back_Total + 1;
                           Back_Source (Back_Total) := Block_Id (Block);
                           Back_Next (Back_Total) :=
                             First_Back (Positive (Target));
                           First_Back (Positive (Target)) := Back_Total;
                        end if;
                     end;
                  else
                     On_Path (Block) := False;
                     Height := Height - 1;
                     if First_Back (Block) /= 0 then
                        Head_Total := Head_Total + 1;
                        Heads (Head_Total) := Block_Id (Block);
                     end if;
                  end if;
               end;
            end loop;
            for Index in 1 .. Head_Total loop
               declare
                  Before : constant Natural := Natural (Moves.Length);
                  Head : constant Block_Id := Heads (Index);
               begin
                  Analyse (Head);
                  if Natural (Moves.Length) > Before then
                     --  Moves.Element (Before + 1).Preheader is this loop's.
                     First_Move
                       (Held.Blocks.First
                        + Positive (Moves.Element (Before + 1).Preheader)) :=
                       Before + 1;
                  end if;
               end;
            end loop;
         end Plan_Item;

         --  Copy every item into fresh slot, code and operand runs: each
         --  item's new slots after its own, each moved value made again at
         --  the end of its preheader and stored, and read where it was.
         procedure Rebuild;
         procedure Rebuild is
            Root : Counts.Elements renames Root_Owner.Data.all;
            Drop : Flags.Elements renames Drop_Owner.Data.all;
            Reach : Counts.Elements renames Reach_Owner.Data.all;
            First_Move : Counts.Elements renames First_Move_Owner.Data.all;
            Slots : Slot_Vectors.Vector;
            Code : Code_Vectors.Vector;
            Args : Value_Ref_Vectors.Vector;
            Assembled : Assembly_Operand_Vectors.Vector;
            Next_Move : Positive := 1;
         begin
            for I in 1 .. Item_Count (Into) loop
               declare
                  Old : constant Item_Record := Into.Items.Element (I);
                  Held : Item_Record := Old;
                  Map : Value_Maps.Vector;
                  Made_Map : Value_Maps.Vector;
                  Made_In : Block_Maps.Vector;

                  function Old_Code (Value : Value_Id) return Instruction
                    is (Into.Code.Element
                          (Old.Values.First + Positive (Value)));

                  function Append
                    (Made : Instruction; Operands : Value_Ref_Vectors.Vector)
                     return Value_Id;
                  function Append
                    (Made : Instruction; Operands : Value_Ref_Vectors.Vector)
                     return Value_Id
                  is
                     Now : Instruction := Made;
                     At_Block : constant Positive :=
                       Old.Blocks.First + Positive (Made.In_Block);
                  begin
                     Now.First_Arg := Natural (Args.Length);
                     Now.Args := Natural (Operands.Length);
                     for Operand of Operands loop
                        Args.Append (Operand);
                     end loop;
                     Now.Assembly_Run :=
                       (First => Natural (Assembled.Length),
                        Count => Made.Assembly_Run.Count);
                     for A in 1 .. Made.Assembly_Run.Count loop
                        Assembled.Append
                          (Into.Assembly_Operands.Element
                             (Made.Assembly_Run.First + A));
                     end loop;
                     if Into.Blocks (At_Block).Values = 0 then
                        Into.Blocks (At_Block).First_Value :=
                          Natural (Code.Length);
                     end if;
                     Into.Blocks (At_Block).Values :=
                       Into.Blocks (At_Block).Values + 1;
                     Code.Append (Now);
                     Held.Values.Count := Held.Values.Count + 1;
                     return Value_Id (Held.Values.Count);
                  end Append;

                  --  Value made again in Block from its invariant operands.
                  function Remake (Value : Value_Id; Block : Block_Id)
                    return Value_Id;
                  function Remake (Value : Value_Id; Block : Block_Id)
                    return Value_Id
                  is
                     Was : constant Instruction := Old_Code (Value);
                     Now : Instruction := Was;
                     Operands : Value_Ref_Vectors.Vector;
                  begin
                     if Made_In (Positive (Value)) = Block then
                        return Made_Map (Positive (Value));
                     end if;
                     for A in 1 .. Was.Args loop
                        Operands.Append
                          (Remake (Into.Operands.Element (Was.First_Arg + A),
                                   Block));
                     end loop;
                     Now.In_Block := Block;
                     Made_Map (Positive (Value)) := Append (Now, Operands);
                     Made_In (Positive (Value)) := Block;
                     return Made_Map (Positive (Value));
                  end Remake;
               begin
                  Held.Slots := (First => Natural (Slots.Length), Count => 0);
                  for S in 1 .. Old.Slots.Count loop
                     Slots.Append (Into.Slots.Element (Old.Slots.First + S));
                  end loop;
                  declare
                     Scan : Natural := Next_Move;
                  begin
                     while Scan <= Natural (Moves.Length)
                       and then Moves.Element (Scan).Item = Item_Id (I)
                     loop
                        Slots.Append (Moves.Element (Scan).Carrier);
                        if Slot_Id (Natural (Slots.Length) - Held.Slots.First)
                          /= Moves.Element (Scan).Slot
                        then
                           raise Landin.Compiler_Defect with
                             "hoisting misnumbered a slot";
                        end if;
                        Scan := Scan + 1;
                     end loop;
                     Next_Move := Scan;
                  end;
                  Held.Slots.Count :=
                    Natural (Slots.Length) - Held.Slots.First;

                  Held.Values := (First => Natural (Code.Length), Count => 0);
                  for B in 1 .. Old.Blocks.Count loop
                     Into.Blocks (Old.Blocks.First + B).First_Value := 0;
                     Into.Blocks (Old.Blocks.First + B).Values := 0;
                  end loop;
                  Map.Append (No_Value, Ada.Containers.Count_Type
                    (Old.Values.Count));
                  Made_Map.Append (No_Value, Ada.Containers.Count_Type
                    (Old.Values.Count));
                  Made_In.Append (No_Block, Ada.Containers.Count_Type
                    (Old.Values.Count));
                  for V in 1 .. Old.Values.Count loop
                     declare
                        At_Code : constant Positive := Old.Values.First + V;
                        Was : constant Instruction :=
                          Into.Code.Element (At_Code);
                        Operands : Value_Ref_Vectors.Vector;
                     begin
                        if Was.Op = Jump
                          and then First_Move
                            (Old.Blocks.First + Positive (Was.In_Block)) /= 0
                        then
                           declare
                              Scan : Positive := First_Move
                                (Old.Blocks.First + Positive (Was.In_Block));
                           begin
                              while Scan <= Natural (Moves.Length)
                                and then Moves.Element (Scan).Item
                                  = Item_Id (I)

                                and then Moves.Element (Scan).Preheader
                                  = Was.In_Block
                              loop
                                 declare
                                    Moved : constant Move :=
                                      Moves.Element (Scan);
                                    Made : constant Value_Id :=
                                      (if Moved.Address
                                       then Append
                                         (Instruction'
                                            (Op => Storage_Address,
                                             Result => Landin.Types.Usize,
                                             Site =>
                                               Old_Code (Moved.Value).Site,
                                             In_Block => Was.In_Block,
                                             Destination => Moved.Place,
                                             others => <>),
                                          Value_Ref_Vectors.Empty_Vector)
                                       else Remake
                                         (Moved.Value, Was.In_Block));
                                 begin
                                    if Append
                                      (Instruction'
                                         (Op => Store,
                                          Site => Old_Code (Moved.Value).Site,
                                          In_Block => Was.In_Block,
                                          Slot => Moved.Slot, others => <>),
                                       Value_Ref_Vectors.To_Vector (Made, 1))
                                      = No_Value
                                    then
                                       raise Landin.Compiler_Defect;
                                    end if;
                                 end;
                                 Scan := Scan + 1;
                              end loop;
                           end;
                        end if;
                        if Drop (At_Code) then
                           null;
                        elsif Root (At_Code) /= 0 then
                           Map (V) := Append
                             (Instruction'
                                (Op => Load, Result => Was.Result,
                                 Site => Was.Site, In_Block => Was.In_Block,
                                 Slot => Moves.Element (Root (At_Code)).Slot,
                                 others => <>),
                              Value_Ref_Vectors.Empty_Vector);
                        else
                           for A in 1 .. Was.Args loop
                              declare
                                 Before : constant Value_Id :=
                                   Into.Operands.Element (Was.First_Arg + A);
                              begin
                                 if Map (Positive (Before)) = No_Value then
                                    raise Landin.Compiler_Defect with
                                      "hoisting dropped a value still read";
                                 end if;
                                 Operands.Append (Map (Positive (Before)));
                              end;
                           end loop;
                           if Reach (At_Code) /= 0 then
                              declare
                                 Now : Instruction := Was;
                              begin
                                 Now.Slot := Moves.Element
                                   (Reach (At_Code)).Slot;
                                 Now.Named := No_Item;
                                 Map (V) := Append (Now, Operands);
                              end;
                           else
                              Map (V) := Append (Was, Operands);
                           end if;
                        end if;
                     end;
                  end loop;
                  Into.Items.Replace_Element (I, Held);
               end;
            end loop;
            Into.Slots.Move (Slots);
            Into.Code.Move (Code);
            Into.Operands.Move (Args);
            Into.Assembly_Operands.Move (Assembled);
         end Rebuild;
      begin
         for I in 1 .. Item_Count (Into) loop
            if Kind_Of (Into, Item_Id (I)) = Routine
              and then not Is_External (Into, Item_Id (I))
              and then Block_Count (Into, Item_Id (I)) > 2
            then
               Plan_Item (Item_Id (I));
            end if;
         end loop;
         if not Moves.Is_Empty then
            Rebuild;
            Verifier.Verify (Into, Facts);
         end if;
      end Hoist;
   begin
      if Objective = Landin.Optimization.Speed
        and then not Landin.Targets.Is_Firmware (Facts)
      then
         Hoist;
      end if;
   end Run_On_Verified;
end Landin.IR.Hoisting;
