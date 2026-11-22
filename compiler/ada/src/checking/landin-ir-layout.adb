with Landin.IR.Control_Flow;
with Landin.IR.Rewriting;
with Landin.IR.Scratch_Arrays;
with Landin.IR.Verifier;

package body Landin.IR.Layout is
   use type Landin.Optimization.Objective;

   package Block_Arrays is new Scratch_Arrays (Block_Id, No_Block);
   package Counts is new Scratch_Arrays (Natural, 0);
   package Flags is new Scratch_Arrays (Boolean, False);

   --  The index in Into.Code of Item's Value.
   function Code_Index
     (Into : Unit; Item : Item_Id; Value : Value_Id) return Positive
   is (Into.Items (Positive (Item)).Values.First + Positive (Value));

   function Ending
     (Into : Unit; Item : Item_Id; Block : Block_Id) return Value_Id
   is (Nth_Value (Into, Item, Block, Length (Into, Item, Block)));

   --  A block that holds nothing but a jump.
   function Forwards
     (Into : Unit; Item : Item_Id; Block : Block_Id) return Boolean
   is (Length (Into, Item, Block) = 1
       and then Op_Of (Into, Item, Ending (Into, Item, Block)) = Jump);

   procedure Retarget
     (Into : in out Unit; Item : Item_Id; Value : Value_Id;
      Target, Alternative : Block_Id);

   procedure Retarget
     (Into : in out Unit; Item : Item_Id; Value : Value_Id;
      Target, Alternative : Block_Id)
   is
      Index : constant Positive := Code_Index (Into, Item, Value);
      Now : Instruction := Into.Code (Index);
   begin
      Now.Target := Target;
      if Now.Op = Branch then
         Now.Alternative := Alternative;
      end if;
      Into.Code.Replace_Element (Index, Now);
   end Retarget;

   --  Sends Item's jumps and branches past forwarding blocks.  True when
   --  any target changed.
   function Thread (Into : in out Unit; Item : Item_Id) return Boolean;

   function Thread (Into : in out Unit; Item : Item_Id) return Boolean is
      Total : constant Natural := Block_Count (Into, Item);
      Final_Owner : constant Block_Arrays.Owner :=
        Block_Arrays.Create (Total);
      Final : Block_Arrays.Elements renames Final_Owner.Data.all;
      Walk_Owner : constant Block_Arrays.Owner := Block_Arrays.Create (Total);
      Walk : Block_Arrays.Elements renames Walk_Owner.Data.all;
      On_Walk_Owner : constant Flags.Owner := Flags.Create (Total);
      On_Walk : Flags.Elements renames On_Walk_Owner.Data.all;
      Changed : Boolean := False;

      --  Where a jump to Block ends up.  A cycle of forwarding blocks,
      --  an empty endless loop, ends at the block the walk met twice.
      function Resolve (Block : Block_Id) return Block_Id;

      function Resolve (Block : Block_Id) return Block_Id is
         Height : Natural := 0;
         At_Block : Block_Id := Block;
         Answer : Block_Id;
      begin
         loop
            if Final (Positive (At_Block)) /= No_Block then
               Answer := Final (Positive (At_Block));
               exit;
            elsif not Forwards (Into, Item, At_Block)
              or else On_Walk (Positive (At_Block))
            then
               Answer := At_Block;
               exit;
            end if;
            On_Walk (Positive (At_Block)) := True;
            Height := Height + 1;
            Walk (Height) := At_Block;
            At_Block := Target_Of
              (Into, Item, Ending (Into, Item, At_Block));
         end loop;
         for Index in 1 .. Height loop
            Final (Positive (Walk (Index))) := Answer;
            On_Walk (Positive (Walk (Index))) := False;
         end loop;
         return Answer;
      end Resolve;
   begin
      for B in 1 .. Total loop
         declare
            Last : constant Value_Id := Ending (Into, Item, Block_Id (B));
         begin
            case Op_Of (Into, Item, Last) is
               when Jump =>
                  declare
                     Was : constant Block_Id := Target_Of (Into, Item, Last);
                     Now : constant Block_Id := Resolve (Was);
                  begin
                     if Now /= Was then
                        Retarget (Into, Item, Last, Now, No_Block);
                        Changed := True;
                     end if;
                  end;
               when Branch =>
                  declare
                     Was_Target : constant Block_Id :=
                       Target_Of (Into, Item, Last);
                     Was_Alternative : constant Block_Id :=
                       Alternative_Of (Into, Item, Last);
                     Target : constant Block_Id := Resolve (Was_Target);
                     Alternative : constant Block_Id :=
                       Resolve (Was_Alternative);
                  begin
                     if Target /= Alternative
                       and then (Target /= Was_Target
                                 or else Alternative /= Was_Alternative)
                     then
                        Retarget (Into, Item, Last, Target, Alternative);
                        Changed := True;
                     end if;
                  end;
               when others =>
                  null;
            end case;
         end;
      end loop;
      return Changed;
   end Thread;

   --  Places Item's loops as the package comment says.  True when any
   --  block moved.
   function Place_Loops (Into : in out Unit; Item : Item_Id) return Boolean;

   function Place_Loops (Into : in out Unit; Item : Item_Id) return Boolean
   is
      Total : constant Natural := Block_Count (Into, Item);
      Graph : constant Control_Flow.Graph := Control_Flow.Make (Into, Item);
      --  The depth-first walk: each block's preorder number, how many of
      --  its successors it has tried, whether it is on the walk's path,
      --  and the path itself.
      Order_Owner : constant Counts.Owner := Counts.Create (Total);
      Order : Counts.Elements renames Order_Owner.Data.all;
      Tried_Owner : constant Counts.Owner := Counts.Create (Total);
      Tried : Counts.Elements renames Tried_Owner.Data.all;
      On_Path_Owner : constant Flags.Owner := Flags.Create (Total);
      On_Path : Flags.Elements renames On_Path_Owner.Data.all;
      Path_Owner : constant Block_Arrays.Owner := Block_Arrays.Create (Total);
      Path : Block_Arrays.Elements renames Path_Owner.Data.all;
      --  Heads in the order the walk finished them, inner loops first;
      --  and the blocks that jump back to each, as lists through Next.
      Heads_Owner : constant Block_Arrays.Owner := Block_Arrays.Create (Total);
      Heads : Block_Arrays.Elements renames Heads_Owner.Data.all;
      Head_Total : Natural := 0;
      First_Back_Owner : constant Counts.Owner := Counts.Create (Total);
      First_Back : Counts.Elements renames First_Back_Owner.Data.all;
      Back_Source_Owner : constant Block_Arrays.Owner :=
        Block_Arrays.Create (2 * Total);
      Back_Source : Block_Arrays.Elements renames Back_Source_Owner.Data.all;
      Back_Next_Owner : constant Counts.Owner := Counts.Create (2 * Total);
      Back_Next : Counts.Elements renames Back_Next_Owner.Data.all;
      Back_Total : Natural := 0;
      --  The layout: the block at each position and each block's position.
      Sequence_Owner : constant Block_Arrays.Owner :=
        Block_Arrays.Create (Total);
      Sequence : Block_Arrays.Elements renames Sequence_Owner.Data.all;
      Position_Owner : constant Counts.Owner := Counts.Create (Total);
      Position : Counts.Elements renames Position_Owner.Data.all;
      --  The head whose loop a block was last found in, the loop's
      --  blocks, and a segment being rebuilt.
      Stamp_Owner : constant Block_Arrays.Owner := Block_Arrays.Create (Total);
      Stamp : Block_Arrays.Elements renames Stamp_Owner.Data.all;
      Members_Owner : constant Block_Arrays.Owner :=
        Block_Arrays.Create (Total);
      Members : Block_Arrays.Elements renames Members_Owner.Data.all;
      Segment_Owner : constant Block_Arrays.Owner :=
        Block_Arrays.Create (Total);
      Segment : Block_Arrays.Elements renames Segment_Owner.Data.all;
      Height : Natural := 0;
      Clock : Natural := 0;
      Moved : Boolean := False;

      procedure Place (Head : Block_Id);

      procedure Place (Head : Block_Id) is
         Test : constant Value_Id := Ending (Into, Item, Head);
         Member_Total : Natural := 0;
         Read_At : Positive := 1;
         Edge : Natural;
         Escaped : Boolean := False;
         Last : Natural := Position (Positive (Head));
         Step : Block_Id := No_Block;
         Exit_Block : Block_Id;
         Filled : Natural := 0;

         procedure Join (Block : Block_Id);
         procedure Join (Block : Block_Id) is
         begin
            if Stamp (Positive (Block)) /= Head then
               Stamp (Positive (Block)) := Head;
               Member_Total := Member_Total + 1;
               Members (Member_Total) := Block;
            end if;
         end Join;

         procedure Append (Block : Block_Id);
         procedure Append (Block : Block_Id) is
         begin
            Filled := Filled + 1;
            Segment (Filled) := Block;
         end Append;
      begin
         if Head = First_Block or else Op_Of (Into, Item, Test) /= Branch then
            return;
         end if;
         --  The natural loop, found backward from the blocks jumping back.
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
                  --  Only a loop the head does not dominate reaches the
                  --  entry; lowering makes none, and it is left alone.
                  Escaped := Escaped or else Source = First_Block;
                  Join (Source);
               end;
               Edge := Control_Flow.Next_Predecessor (Graph, Edge);
            end loop;
            Read_At := Read_At + 1;
         end loop;
         if Escaped or else Member_Total < 2
           or else (Stamp (Positive (Target_Of (Into, Item, Test))) = Head)
             = (Stamp (Positive (Alternative_Of (Into, Item, Test))) = Head)
         then
            return;
         end if;
         Exit_Block :=
           (if Stamp (Positive (Target_Of (Into, Item, Test))) = Head
            then Alternative_Of (Into, Item, Test)
            else Target_Of (Into, Item, Test));
         for Index in 1 .. Member_Total loop
            declare
               Block : constant Block_Id := Members (Index);
               At_Position : constant Positive := Position (Positive (Block));
               Final : constant Value_Id := Ending (Into, Item, Block);
            begin
               if At_Position < Position (Positive (Head)) then
                  return;
               end if;
               Last := Natural'Max (Last, At_Position);
               if Op_Of (Into, Item, Final) = Jump
                 and then Target_Of (Into, Item, Final) = Head
                 and then (Step = No_Block
                           or else At_Position > Position (Positive (Step)))
               then
                  Step := Block;
               end if;
            end;
         end loop;
         if Step = No_Block then
            return;
         end if;
         for At_Position in Position (Positive (Head)) .. Last loop
            declare
               Block : constant Block_Id := Sequence (At_Position);
            begin
               if Stamp (Positive (Block)) = Head
                 and then Block not in Head | Step
               then
                  Append (Block);
               end if;
            end;
         end loop;
         Append (Step);
         Append (Head);
         if Position (Positive (Exit_Block)) in
           Position (Positive (Head)) .. Last
         then
            Append (Exit_Block);
         end if;
         for At_Position in Position (Positive (Head)) .. Last loop
            declare
               Block : constant Block_Id := Sequence (At_Position);
            begin
               if Stamp (Positive (Block)) /= Head
                 and then Block /= Exit_Block
               then
                  Append (Block);
               end if;
            end;
         end loop;
         for Index in 1 .. Filled loop
            declare
               At_Position : constant Positive :=
                 Position (Positive (Head)) + Index - 1;
            begin
               if Sequence (At_Position) /= Segment (Index) then
                  Moved := True;
               end if;
            end;
         end loop;
         declare
            Start : constant Positive := Position (Positive (Head));
         begin
            for Index in 1 .. Filled loop
               Sequence (Start + Index - 1) := Segment (Index);
               Position (Positive (Segment (Index))) := Start + Index - 1;
            end loop;
         end;
      end Place;
   begin
      for B in 1 .. Total loop
         Sequence (B) := Block_Id (B);
         Position (B) := B;
      end loop;
      --  The walk from the entry: an edge to a block still on the path
      --  closes a loop there.
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
                     Back_Next (Back_Total) := First_Back (Positive (Target));
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
         Place (Heads (Index));
      end loop;
      if not Moved then
         return False;
      end if;
      --  Renumber: a block's identity is its place in the layout.
      declare
         Held : constant Item_Record := Into.Items (Positive (Item));
         Old_Blocks : Block_Vectors.Vector;
      begin
         for B in 1 .. Total loop
            Old_Blocks.Append (Into.Blocks (Held.Blocks.First + B));
         end loop;
         for B in 1 .. Total loop
            Into.Blocks.Replace_Element
              (Held.Blocks.First + B,
               Old_Blocks (Positive (Sequence (B))));
         end loop;
         for V in 1 .. Held.Values.Count loop
            declare
               Index : constant Positive := Held.Values.First + V;
               Now : Instruction := Into.Code (Index);
            begin
               Now.In_Block := Block_Id (Position (Positive (Now.In_Block)));
               if Now.Op in Jump | Branch then
                  Now.Target := Block_Id (Position (Positive (Now.Target)));
                  if Now.Op = Branch then
                     Now.Alternative :=
                       Block_Id (Position (Positive (Now.Alternative)));
                  end if;
               end if;
               Into.Code.Replace_Element (Index, Now);
            end;
         end loop;
      end;
      return True;
   end Place_Loops;

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
      Threaded : Boolean := False;
      Placed : Boolean := False;
   begin
      if Objective = Landin.Optimization.None
        or else Landin.Targets.Is_Firmware (Facts)
      then
         return;
      end if;
      for I in 1 .. Item_Count (Into) loop
         if Block_Count (Into, Item_Id (I)) > 1 then
            Threaded := Thread (Into, Item_Id (I)) or else Threaded;
         end if;
      end loop;
      if Threaded then
         --  Nothing reaches a block jumped past any longer.
         Rewriting.Compact
           (Into, Rewriting.Keep_Vectors.To_Vector (True, Into.Code.Length));
      end if;
      for I in 1 .. Item_Count (Into) loop
         if Block_Count (Into, Item_Id (I)) > 2 then
            Placed := Place_Loops (Into, Item_Id (I)) or else Placed;
         end if;
      end loop;
      if Threaded or else Placed then
         Verifier.Verify (Into, Facts);
      end if;
   end Run_On_Verified;
end Landin.IR.Layout;
