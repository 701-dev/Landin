with Landin.IR.Control_Flow;

package body Landin.IR.Rewriting is
   procedure Compact (Into : in out Unit; Keep : Keep_Vectors.Vector) is
   begin
      Compact (Into, Keep, Addition_Vectors.Empty_Vector);
   end Compact;

   procedure Compact
     (Into : in out Unit;
      Keep : Keep_Vectors.Vector;
      Additions : Addition_Vectors.Vector)
   is
      Code : Code_Vectors.Vector;
      Args : Value_Ref_Vectors.Vector;
      Assembled : Assembly_Operand_Vectors.Vector;
      Blocks : Block_Vectors.Vector;
      Items : Item_Vectors.Vector := Into.Items;
      Next_Addition : Positive := 1;
   begin
      if Natural (Keep.Length) /= Natural (Into.Code.Length)
      then
         raise Landin.Compiler_Defect with "invalid rewrite retention map";
      end if;
      for I in 1 .. Item_Count (Into) loop
         declare
            Item : constant Item_Id := Item_Id (I);
            Old : constant Item_Record := Into.Items (I);
            Held : Item_Record := Old;
            Graph : constant Control_Flow.Graph :=
              Control_Flow.Make (Into, Item);
            Block_Map : array (1 .. Old.Blocks.Count) of Block_Id :=
              [others => No_Block];
            Last_Code : constant Natural := Old.Values.First
              + Old.Values.Count;
            First_Addition : constant Positive := Next_Addition;
            Added : Natural := 0;
         begin
            while First_Addition + Added <= Natural (Additions.Length)
              and then Additions (First_Addition + Added).Before <= Last_Code
            loop
               if Additions (First_Addition + Added).Before
                 <= Old.Values.First
               then
                  raise Landin.Compiler_Defect with
                    "rewrite additions out of order";
               end if;
               Added := Added + 1;
            end loop;
            Next_Addition := First_Addition + Added;
            declare
               Value_Map : array (1 .. Old.Values.Count + Added) of Value_Id :=
                 [others => No_Value];
               Cursor : Positive := First_Addition;

               procedure Place (Now : in out Instruction);
               procedure Place (Now : in out Instruction) is
                  At_Block : constant Positive := Held.Blocks.First
                    + Positive (Now.In_Block);
                  Block : Block_Record := Blocks (At_Block);
               begin
                  if Block.Values = 0 then
                     Block.First_Value := Natural (Code.Length);
                  end if;
                  Block.Values := Block.Values + 1;
                  Blocks.Replace_Element (At_Block, Block);
                  Code.Append (Now);
               end Place;

               function Mapped (Before : Value_Id) return Value_Id;
               function Mapped (Before : Value_Id) return Value_Id is
                  After : constant Value_Id :=
                    (if Before = No_Value
                       or else Natural (Before) > Value_Map'Last
                     then No_Value
                     else Value_Map (Positive (Before)));
               begin
                  if After = No_Value then
                     raise Landin.Compiler_Defect with
                       "rewrite discarded a retained operand";
                  end if;
                  return After;
               end Mapped;
            begin
               Held.Blocks := (First => Natural (Blocks.Length), Count => 0);
               Held.Values := (First => Natural (Code.Length), Count => 0);
               for B in Block_Map'Range loop
                  if Control_Flow.Is_Reachable (Graph, Block_Id (B)) then
                     declare
                        Block : Block_Record := Into.Blocks
                          (Old.Blocks.First + B);
                     begin
                        Held.Blocks.Count := Held.Blocks.Count + 1;
                        Block_Map (B) := Block_Id (Held.Blocks.Count);
                        Block.First_Value := 0;
                        Block.Values := 0;
                        Blocks.Append (Block);
                     end;
                  end if;
               end loop;
               for V in 1 .. Old.Values.Count loop
                  declare
                     Was : constant Instruction := Into.Code
                       (Old.Values.First + V);
                     Now : Instruction := Was;
                  begin
                     while Cursor < First_Addition + Added
                       and then Additions (Cursor).Before
                                  = Old.Values.First + V
                     loop
                        declare
                           Made : constant Addition := Additions (Cursor);
                           Fresh : Instruction := Made.Code;
                        begin
                           if Block_Map (Positive (Was.In_Block)) = No_Block
                             or else not Keep (Old.Values.First + V)
                           then
                              raise Landin.Compiler_Defect with
                                "rewrite addition before a discarded value";
                           end if;
                           Held.Values.Count := Held.Values.Count + 1;
                           Value_Map (Old.Values.Count + 1
                                      + (Cursor - First_Addition)) :=
                             Value_Id (Held.Values.Count);
                           Fresh.In_Block :=
                             Block_Map (Positive (Was.In_Block));
                           Fresh.First_Arg := Natural (Args.Length);
                           for A in 1 .. Fresh.Args loop
                              Args.Append (Mapped (Made.Operands (A)));
                           end loop;
                           Fresh.Assembly_Run :=
                             (First => Natural (Assembled.Length), Count => 0);
                           Place (Fresh);
                        end;
                        Cursor := Cursor + 1;
                     end loop;
                     if Block_Map (Positive (Was.In_Block)) /= No_Block
                       and then Keep (Old.Values.First + V)
                     then
                        Held.Values.Count := Held.Values.Count + 1;
                        Value_Map (V) := Value_Id (Held.Values.Count);
                        Now.In_Block := Block_Map (Positive (Was.In_Block));
                        Now.First_Arg := Natural (Args.Length);
                        for A in 1 .. Was.Args loop
                           Args.Append (Mapped (Into.Operands
                             (Was.First_Arg + A)));
                        end loop;
                        Now.Assembly_Run :=
                          (First => Natural (Assembled.Length),
                           Count => Was.Assembly_Run.Count);
                        for A in 1 .. Was.Assembly_Run.Count loop
                           Assembled.Append
                             (Into.Assembly_Operands
                                (Was.Assembly_Run.First + A));
                        end loop;
                        if Was.Op in Jump | Branch then
                           Now.Target := Block_Map (Positive (Was.Target));
                           if Was.Op = Branch then
                              Now.Alternative :=
                                Block_Map (Positive (Was.Alternative));
                           end if;
                        end if;
                        Place (Now);
                     end if;
                  end;
               end loop;
               if Cursor /= First_Addition + Added then
                  raise Landin.Compiler_Defect with
                    "rewrite addition after its item's last value";
               end if;
            end;
            Items.Replace_Element (I, Held);
         end;
      end loop;
      if Next_Addition /= Natural (Additions.Length) + 1 then
         raise Landin.Compiler_Defect with "rewrite addition outside an item";
      end if;
      Into.Items.Move (Items);
      Into.Code.Move (Code);
      Into.Operands.Move (Args);
      Into.Assembly_Operands.Move (Assembled);
      Into.Blocks.Move (Blocks);
   end Compact;
end Landin.IR.Rewriting;
