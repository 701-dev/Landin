with Landin.IR.Effects;
with Landin.IR.Rewriting;
with Landin.IR.Scratch_Arrays;

package body Landin.IR.Identities is
   use type Landin.Types.Magnitude;
   package Counts is new Scratch_Arrays (Natural, 0);

   procedure Apply (Into : in out Unit; Facts : Landin.Targets.Target_Facts)
   is
      Keep : Rewriting.Keep_Vectors.Vector :=
        Rewriting.Keep_Vectors.To_Vector (True, Into.Code.Length);
      Additions : Rewriting.Addition_Vectors.Vector;
      Changed : Boolean := False;

      procedure Rewrite (Item : Item_Id);

      procedure Rewrite (Item : Item_Id) is
         Held : constant Item_Record := Into.Items.Element (Positive (Item));
         Last : constant Natural := Held.Values.Count;
         Uses_Owner : constant Counts.Owner := Counts.Create (Last);
         Uses : Counts.Elements renames Uses_Owner.Data.all;
         Added : Natural := 0;

         function Code_At (Value : Value_Id) return Instruction
           is (Into.Code.Element (Held.Values.First + Positive (Value)));

         function Kept (Value : Value_Id) return Boolean
           is (Value /= No_Value and then Natural (Value) <= Last
               and then Keep (Held.Values.First + Positive (Value)));

         function Operand (Value : Value_Id; Index : Positive)
           return Value_Id
           is (Into.Operands.Element (Code_At (Value).First_Arg + Index));

         function Plain (Code : Instruction) return Boolean
           is (Code.Pointee = No_Pointee
               and then Code.Signature = No_Signature
               and then Code.Atom_Set = No_Atom_Set
               and then Code.Assembly_Run.Count = 0);

         --  An integer operation of two operands this pass may read.
         function Binary (Value : Value_Id; Op : Opcode) return Boolean is
           (Kept (Value)
            and then Code_At (Value).Op = Op
            and then Code_At (Value).Args = 2
            and then Code_At (Value).Result in Landin.Types.Integer_Name
            and then Plain (Code_At (Value)));

         --  One value, or two loads of one slot part with nothing between
         --  them that could write it: no store, call, assembly block or
         --  control transfer.
         function Same (Left, Right : Value_Id) return Boolean;
         function Same (Left, Right : Value_Id) return Boolean is
         begin
            if Left = Right then
               return True;
            elsif not Kept (Left) or else not Kept (Right) then
               return False;
            end if;
            declare
               First : constant Instruction := Code_At (Left);
               Second : Instruction := Code_At (Right);
            begin
               if First.Op /= Load or else First.Args /= 0
                 or else not Plain (First)
                 or else First.In_Block /= Second.In_Block
               then
                  return False;
               end if;
               Second.Site := First.Site;
               Second.First_Arg := First.First_Arg;
               Second.Assembly_Run := First.Assembly_Run;
               if First /= Second then
                  return False;
               end if;
               for Between in Value_Id'Min (Left, Right) + 1
                 .. Value_Id'Max (Left, Right) - 1
               loop
                  if Kept (Between) then
                     declare
                        Effect : constant Effects.Effect_Set :=
                          Effects.Of_Code (Code_At (Between).Op);
                     begin
                        if Effect.Writes or else Effect.Calls
                          or else Effect.Control or else Effect.Adjacency
                          or else Code_At (Between).Assembly_Run.Count /= 0
                        then
                           return False;
                        end if;
                     end;
                  end if;
               end loop;
               return True;
            end;
         end Same;

         procedure Set (Value : Value_Id; Op : Opcode; Left, Right : Value_Id);
         procedure Set (Value : Value_Id; Op : Opcode; Left, Right : Value_Id)
         is
            Code : Instruction := Code_At (Value);
         begin
            Code.Op := Op;
            Into.Code.Replace_Element
              (Held.Values.First + Positive (Value), Code);
            Into.Operands.Replace_Element (Code.First_Arg + 1, Left);
            Into.Operands.Replace_Element (Code.First_Arg + 2, Right);
         end Set;

         procedure Count_Use (Value : Value_Id; By : Integer);
         procedure Count_Use (Value : Value_Id; By : Integer) is
         begin
            if Value /= No_Value and then Natural (Value) <= Last then
               Uses (Positive (Value)) := Uses (Positive (Value)) + By;
            end if;
         end Count_Use;

         --  Drop an instruction nothing uses any longer: one this pass
         --  freed, or a load another load of the same slot part stands
         --  for.
         procedure Drop (Value : Value_Id);
         procedure Drop (Value : Value_Id) is
         begin
            Keep (Held.Values.First + Positive (Value)) := False;
            for A in 1 .. Code_At (Value).Args loop
               Count_Use (Operand (Value, A), -1);
            end loop;
            Changed := True;
         end Drop;

         procedure Drop_Load (Value : Value_Id);
         procedure Drop_Load (Value : Value_Id) is
         begin
            if Kept (Value) and then Uses (Positive (Value)) = 0
              and then Code_At (Value).Op = Load
            then
               Drop (Value);
            end if;
         end Drop_Load;

         --  `(s & u) op (s & w)`, op `^` or `|`: the later AND becomes
         --  `u op w`, the result `s & that`, the earlier AND goes.
         function Distribute (Value : Value_Id) return Boolean;
         function Distribute (Value : Value_Id) return Boolean is
            P : constant Value_Id := Operand (Value, 1);
            Q : constant Value_Id := Operand (Value, 2);
            Op : constant Opcode := Code_At (Value).Op;
         begin
            if not Binary (P, Bitwise_And) or else not Binary (Q, Bitwise_And)
              or else Uses (Positive (P)) /= 1 or else Uses (Positive (Q)) /= 1
            then
               return False;
            end if;
            for I in 1 .. 2 loop
               for J in 1 .. 2 loop
                  if Same (Operand (P, I), Operand (Q, J)) then
                     declare
                        Later : constant Value_Id := Value_Id'Max (P, Q);
                        Earlier : constant Value_Id := Value_Id'Min (P, Q);
                        U : constant Value_Id := Operand (P, 3 - I);
                        W : constant Value_Id := Operand (Q, 3 - J);
                        Kept_S : constant Value_Id :=
                          (if Later = P then Operand (P, I)
                           else Operand (Q, J));
                        Freed_S : constant Value_Id :=
                          (if Later = P then Operand (Q, J)
                           else Operand (P, I));
                     begin
                        Drop (Earlier);
                        Count_Use (U, 1);
                        Count_Use (W, 1);
                        Count_Use (Operand (Later, 1), -1);
                        Count_Use (Operand (Later, 2), -1);
                        Set (Later, Op, U, W);
                        Count_Use (Kept_S, 1);
                        Set (Value, Bitwise_And, Kept_S, Later);
                        Drop_Load (Freed_S);
                        return True;
                     end;
                  end if;
               end loop;
            end loop;
            return False;
         end Distribute;

         --  `(x & y) ^ (~x' & z)` with x' the same as x: the later AND
         --  becomes `y ^ z`, a new `x & that` comes before the result,
         --  which becomes `new ^ z`; the earlier AND and `~x'` go.
         function Choose (Value : Value_Id) return Boolean;
         function Choose (Value : Value_Id) return Boolean is
            function Try (P, Q : Value_Id) return Boolean;
            function Try (P, Q : Value_Id) return Boolean is
            begin
               if not Binary (P, Bitwise_And)
                 or else not Binary (Q, Bitwise_And)
                 or else Uses (Positive (P)) /= 1
                 or else Uses (Positive (Q)) /= 1
               then
                  return False;
               end if;
               for J in 1 .. 2 loop
                  declare
                     N : constant Value_Id := Operand (Q, J);
                  begin
                     if Kept (N) and then Code_At (N).Op = Complement
                       and then Code_At (N).Args = 1
                       and then Plain (Code_At (N))
                       and then Code_At (N).Result = Code_At (Q).Result
                       and then Uses (Positive (N)) = 1
                     then
                        for I in 1 .. 2 loop
                           if Same (Operand (P, I), Operand (N, 1)) then
                              declare
                                 Later : constant Value_Id :=
                                   Value_Id'Max (P, Q);
                                 Earlier : constant Value_Id :=
                                   Value_Id'Min (P, Q);
                                 X : constant Value_Id := Operand (P, I);
                                 X_Copy : constant Value_Id := Operand (N, 1);
                                 Y : constant Value_Id := Operand (P, 3 - I);
                                 Z : constant Value_Id := Operand (Q, 3 - J);
                                 Made : Rewriting.Addition;
                              begin
                                 --  Every operand the earlier AND and the
                                 --  later one held is released, then the
                                 --  later one holds Y and Z, the addition
                                 --  X and the later one, and the result
                                 --  the addition and Z.
                                 Drop (Earlier);
                                 Count_Use (Operand (Later, 1), -1);
                                 Count_Use (Operand (Later, 2), -1);
                                 Set (Later, Bitwise_Xor, Y, Z);
                                 Count_Use (Y, 1);
                                 Count_Use (Z, 2);
                                 Count_Use (X, 1);
                                 Drop (N);
                                 Made.Before := Held.Values.First
                                   + Positive (Value);
                                 Made.Code := Code_At (Value);
                                 Made.Code.Op := Bitwise_And;
                                 Made.Code.Args := 2;
                                 Made.Operands := [X, Later];
                                 Additions.Append (Made);
                                 Added := Added + 1;
                                 Set (Value, Bitwise_Xor,
                                      Value_Id (Last + Added), Z);
                                 Drop_Load (X_Copy);
                                 Changed := True;
                                 return True;
                              end;
                           end if;
                        end loop;
                     end if;
                  end;
               end loop;
               return False;
            end Try;
         begin
            return Try (Operand (Value, 1), Operand (Value, 2))
              or else Try (Operand (Value, 2), Operand (Value, 1));
         end Choose;

         --  `rotl (a, m) op rotl (b, n)`: the earlier rotation turns its
         --  operand by m - n, the later one becomes `that op b` and the
         --  result turns it by n.  With m = n the earlier rotation goes.
         function Turn (Value : Value_Id) return Boolean;
         function Turn (Value : Value_Id) return Boolean is
            P : constant Value_Id := Operand (Value, 1);
            Q : constant Value_Id := Operand (Value, 2);
            Op : constant Opcode := Code_At (Value).Op;
            Width : Landin.Types.Magnitude;
         begin
            if not Binary (P, Rotate_Left) or else not Binary (Q, Rotate_Left)
              or else Uses (Positive (P)) /= 1 or else Uses (Positive (Q)) /= 1
              or else Code_At (P).Result /= Code_At (Value).Result
              or else Code_At (Q).Result /= Code_At (Value).Result
            then
               return False;
            end if;
            Width := Landin.Types.Magnitude (Landin.Types.Width
              (Landin.Types.Integer_Name (Code_At (Value).Result), Facts));
            declare
               Later : constant Value_Id := Value_Id'Max (P, Q);
               Earlier : constant Value_Id := Value_Id'Min (P, Q);
               Early_By : constant Value_Id := Operand (Earlier, 2);
               Late_By : constant Value_Id := Operand (Later, 2);
               Early_Code : Instruction;
               M, N : Landin.Types.Magnitude;
            begin
               if not Kept (Early_By) or else not Kept (Late_By)
                 or else Code_At (Early_By).Op /= Number
                 or else Code_At (Late_By).Op /= Number
                 or else Code_At (Early_By).Negated
                 or else Code_At (Late_By).Negated
               then
                  return False;
               end if;
               M := Code_At (Early_By).Number;
               N := Code_At (Late_By).Number;
               if M not in 1 .. Width - 1 or else N not in 1 .. Width - 1 then
                  return False;
               elsif M = N then
                  declare
                     A : constant Value_Id := Operand (Earlier, 1);
                     B : constant Value_Id := Operand (Later, 1);
                  begin
                     Drop (Earlier);
                     Set (Later, Op, A, B);
                     Count_Use (A, 1);
                     if Uses (Positive (Early_By)) = 0 then
                        Drop (Early_By);
                     end if;
                  end;
               elsif Uses (Positive (Early_By)) /= 1 then
                  return False;
               else
                  Early_Code := Code_At (Early_By);
                  Early_Code.Number :=
                    (if M > N then M - N else Width - N + M);
                  Into.Code.Replace_Element
                    (Held.Values.First + Positive (Early_By), Early_Code);
                  Set (Later, Op, Earlier, Operand (Later, 1));
               end if;
               Set (Value, Rotate_Left, Later, Late_By);
               Changed := True;
               return True;
            end;
         end Turn;
      begin
         for V in 1 .. Last loop
            declare
               Code : constant Instruction := Code_At (Value_Id (V));
            begin
               for A in 1 .. Code.Args loop
                  Count_Use (Into.Operands.Element (Code.First_Arg + A), 1);
               end loop;
            end;
         end loop;
         for V in 1 .. Last loop
            declare
               Value : constant Value_Id := Value_Id (V);
            begin
               if Binary (Value, Bitwise_Xor) then
                  if not Distribute (Value) and then not Choose (Value) then
                     Changed := Turn (Value) or else Changed;
                  end if;
               elsif Binary (Value, Bitwise_Or) then
                  if not Distribute (Value) then
                     Changed := Turn (Value) or else Changed;
                  end if;
               elsif Binary (Value, Bitwise_And) then
                  Changed := Turn (Value) or else Changed;
               end if;
            end;
         end loop;
      end Rewrite;
   begin
      for I in 1 .. Item_Count (Into) loop
         if Kind_Of (Into, Item_Id (I)) = Routine
           and then not Is_External (Into, Item_Id (I))
         then
            Rewrite (Item_Id (I));
         end if;
      end loop;
      if Changed then
         Rewriting.Compact (Into, Keep, Additions);
      end if;
   end Apply;
end Landin.IR.Identities;
