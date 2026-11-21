with Ada.Containers.Indefinite_Ordered_Maps;
with Ada.Strings.Fixed;
with Ada.Strings.Unbounded;
with Landin.Diagnostics.Applying;
with Landin.Diagnostics.Catalogue;
with Landin.Diagnostics.Text;
with Landin.Platform.Overlays;
with Landin.Source;
with Landin.Source.Sets;

package body Landin.Commands.Fixing is

   package D renames Landin.Diagnostics;
   package A renames Landin.Diagnostics.Applying;
   package US renames Ada.Strings.Unbounded;

   use type Landin.Platform.Read_Status;
   use type Landin.Platform.Write_Status;
   use type Landin.Platform.File_Identity;
   use type Landin.Source.Source_Id;

   --  Path to bytes: what a file held when the first pass read it, and
   --  what the passes since have made of it.
   package Text_Maps is new Ada.Containers.Indefinite_Ordered_Maps
     (Key_Type => String, Element_Type => String);

   --  Path to the edits one pass applies to it.
   package Edit_Maps is new Ada.Containers.Indefinite_Ordered_Maps
     (Key_Type => String, Element_Type => A.Edit_Lists.Vector,
      "=" => A.Edit_Lists."=");

   function Image (Value : Natural) return String is
     (Ada.Strings.Fixed.Trim (Value'Image, Ada.Strings.Both));

   function Execute
     (Arguments  : Landin.Platform.Path_List;
      Host       : Landin.Platform.Filesystem'Class;
      Tools      : Landin.Platform.Tool_Runner'Class;
      Meter      : Landin.Platform.Resource_Meter'Class;
      Built_For  : String;
      Warnings   : Landin.Diagnostics.Warning_Policy.Policy;
      Protected_Inputs : Landin.Platform.Path_List;
      Protected_Identities : Landin.Platform.Identity_List;
      Check_Only : Boolean) return Landin.Driver.Outcome
   is
      Held     : Landin.Platform.Overlays.Overlay (Host'Access);
      Original : Text_Maps.Map;
      Changed  : Text_Maps.Map;
      Applied  : US.Unbounded_String;
      First    : Landin.Driver.Outcome;
      Result   : Landin.Driver.Outcome;
      Settled  : Boolean := False;
      Problems : D.Diagnostic_List;

      procedure Refuse (Message : String; Note : String := "");
      procedure Refuse (Message : String; Note : String := "") is
         Item : D.Diagnostic := D.Make
           (Code    => D.Catalogue.Code (D.Catalogue.Unwritable_Output),
            Level   => D.Error,
            Source  => Landin.Source.No_Source,
            Where   => Landin.Source.Empty_Span,
            Message => Message);
      begin
         if Note /= "" then
            D.Add_Note (Item, Note);
         end if;
         Problems.Append (Item);
      end Refuse;

      --  The edits this pass applies, chosen from Result's report; False
      --  when it offers none that can be applied.
      function Apply_Pass return Boolean;
      function Apply_Pass return Boolean is
         Chosen : Edit_Maps.Map;
         Lines  : US.Unbounded_String;

         function Path (Source : Landin.Source.Source_Id) return String is
           (if Source /= Landin.Source.No_Source
              and then Natural (Source) <= Natural (Result.Named.Length)
            then Result.Named (Positive (Source)) else "");
      begin
         for Index in 1 .. D.Count (Result.Found) loop
            declare
               Item  : constant D.Diagnostic := D.Get (Result.Found, Index);
               Which : constant Natural := A.First_Exact (Item);
            begin
               if Which /= 0 then
                  declare
                     Fix : constant D.Fix := D.Nth_Fix (Item, Which);
                     Usable : Boolean := True;
                  begin
                     --  Every edit names a source the check read, and none
                     --  clashes with an edit this pass applies already.
                     for Number in 1 .. D.Edit_Count (Fix) loop
                        declare
                           One  : constant D.Edit := D.Nth_Edit (Fix, Number);
                           Name : constant String := Path (D.Source_Of (One));
                        begin
                           if Name = "" then
                              Usable := False;
                           elsif Chosen.Contains (Name) then
                              for Other of Chosen (Name) loop
                                 if A.Clash (Other, One) then
                                    Usable := False;
                                 end if;
                              end loop;
                           end if;
                           --  Two edits of the fix itself never clash: a
                           --  fix's edits may touch and not overlap.
                        end;
                     end loop;
                     if Usable then
                        for Number in 1 .. D.Edit_Count (Fix) loop
                           declare
                              One  : constant D.Edit :=
                                D.Nth_Edit (Fix, Number);
                              Name : constant String :=
                                Path (D.Source_Of (One));
                           begin
                              if not Chosen.Contains (Name) then
                                 Chosen.Insert
                                   (Name, A.Edit_Lists.Empty_Vector);
                              end if;
                              A.Insert_Ordered (Chosen (Name), One);
                           end;
                        end loop;
                        declare
                           Name : constant String :=
                             Path (D.Source_Of (D.Primary (Item)));
                           Where : Landin.Source.Position;
                        begin
                           if Index <= Natural (Result.Positions.Length) then
                              Where := Result.Positions (Index);
                           end if;
                           US.Append (Lines,
                             (if Name = "" then ""
                              else D.Text.Escaped (Name) & ":"
                                & Image (Natural (Where.Line)) & ":"
                                & Image (Natural (Where.Column)) & ": ")
                             & D.Code (Item) & ": "
                             & D.Text.Escaped (D.Message (Fix)) & ASCII.LF);
                        end;
                     end if;
                  end;
               end if;
            end;
         end loop;
         if Chosen.Is_Empty then
            return False;
         end if;
         for Cursor in Chosen.Iterate loop
            declare
               Name    : constant String := Edit_Maps.Key (Cursor);
               Content : US.Unbounded_String;
               Read    : Landin.Platform.Read_Status;
            begin
               Held.Read_File (Name, Content, Read);
               if Read /= Landin.Platform.Read_Ok then
                  --  The check read it a moment ago; a file that has gone
                  --  since is left alone, and the fix with it.
                  return False;
               end if;
               if not Original.Contains (Name) then
                  Original.Insert (Name, US.To_String (Content));
               end if;
               declare
                  Fixed : constant String :=
                    A.Applied (US.To_String (Content), Chosen (Cursor));
               begin
                  Held.Hold (Name, Fixed);
                  Changed.Include (Name, Fixed);
               end;
            end;
         end loop;
         US.Append (Applied, Lines);
         return True;
      end Apply_Pass;

      --  Each changed file written, unless it changed underneath.
      procedure Write_Back;
      procedure Write_Back is
      begin
         for Cursor in Changed.Iterate loop
            declare
               Name    : constant String := Text_Maps.Key (Cursor);
               Content : US.Unbounded_String;
               Lease   : Landin.Platform.Update_Handle;
               Read    : Landin.Platform.Read_Status;
               Written : Landin.Platform.Write_Status;
               Reason  : US.Unbounded_String;
            begin
               if (for some Path of Protected_Inputs => Path = Name) then
                  Refuse ("cannot rewrite consumed response input " & Name
                    & "; choose another source");
               else
                  Host.Read_For_Update (Name, Content, Lease, Read, Reason);
                  if Read /= Landin.Platform.Read_Ok then
                     Refuse ("cannot rewrite " & Name
                       & (if US.Length (Reason) > 0
                          then ": " & US.To_String (Reason)
                          else ": it cannot be read again"));
                  elsif US.To_String (Content) /= Original (Name) then
                     Refuse ("cannot rewrite " & Name & ": it changed while"
                       & " refine fix read it, and is left as it is now",
                       "run refine fix again to fix it as it is now");
                  elsif (for some Identity of Protected_Identities =>
                           Identity.Valid and then
                             Host.Update_Identity (Lease) = Identity)
                  then
                     Refuse ("cannot rewrite consumed response input " & Name
                       & "; choose another source");
                  else
                     Host.Replace_Update
                       (Lease, Text_Maps.Element (Cursor), Written, Reason);
                     if Written /= Landin.Platform.Write_Ok then
                        Refuse ("cannot rewrite " & Name & ": "
                          & US.To_String (Reason));
                     end if;
                  end if;
                  Host.Close_Update (Lease);
               end if;
            exception
               when others =>
                  Host.Close_Update (Lease);
                  raise;
            end;
         end loop;
      end Write_Back;

   begin
      for Pass in 1 .. Pass_Limit loop
         Result := Landin.Driver.Execute
           (Arguments, Held, Tools, Meter, Built_For,
            Warnings => Warnings,
            Protected_Inputs => Protected_Inputs,
            Protected_Identities => Protected_Identities);
         if Pass = 1 then
            First := Result;
         end if;
         --  A request the driver refuses, or a defect, fixes nothing.
         if Result.Status in Landin.Driver.Status_Misuse
                           | Landin.Driver.Status_Defect
           or else not Apply_Pass
         then
            Settled := True;
            exit;
         end if;
      end loop;

      if not Settled then
         Refuse ("refine fix stopped after" & Pass_Limit'Image
           & " passes, each of which applied a fix: two fixes undo each"
           & " other, and nothing was written",
           "this is a compiler defect; the fixes applied are listed, and"
           & " refine check shows the ones left");
         Changed.Clear;
      end if;

      if Check_Only then
         Result := First;
         if not Changed.Is_Empty and then Result.Status = 0 then
            Result.Status := Landin.Driver.Status_Reported;
         end if;
      else
         Write_Back;
      end if;
      US.Insert (Result.Output, 1, US.To_String (Applied));
      if D.Count (Problems) > 0 then
         declare
            None : Landin.Source.Sets.Source_Set;
         begin
            for Index in 1 .. D.Count (Problems) loop
               Result.Found.Append (D.Get (Problems, Index));
               Result.Positions.Append (Landin.Source.Position'(others => <>));
            end loop;
            US.Append (Result.Report, D.Text.Render (Problems, None));
         end;
         if Result.Status not in Landin.Driver.Status_Misuse
                               | Landin.Driver.Status_Defect
         then
            Result.Status := Landin.Driver.Status_Reported;
         end if;
      end if;
      return Result;
   end Execute;

end Landin.Commands.Fixing;
