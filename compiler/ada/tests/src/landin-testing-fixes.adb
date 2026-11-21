with Ada.Containers.Indefinite_Vectors;
with Landin.Diagnostics.Applying;

package body Landin.Testing.Fixes is

   package Diag renames Landin.Diagnostics;

   use type Landin.Source.Byte_Offset;
   use type Landin.Source.Source_Id;

   package Edit_Vectors is new Ada.Containers.Indefinite_Vectors
     (Index_Type => Positive, Element_Type => Diag.Edit,
      "=" => Diag."=");

   --  The edits of Source, in byte order, from the selected fixes.
   function Collected
     (Found  : Diag.Diagnostic_List;
      Source : Landin.Source.Source_Id;
      Choice_Diagnostic : Natural;
      Choice_Fix        : Positive) return Edit_Vectors.Vector;

   function Collected
     (Found  : Diag.Diagnostic_List;
      Source : Landin.Source.Source_Id;
      Choice_Diagnostic : Natural;
      Choice_Fix        : Positive) return Edit_Vectors.Vector
   is
      Result : Edit_Vectors.Vector;
   begin
      for Index in 1 .. Diag.Count (Found) loop
         declare
            Item : constant Diag.Diagnostic := Diag.Get (Found, Index);
         begin
            if Diag.Fix_Count (Item) > 0 then
               declare
                  Selected : constant Diag.Fix := Diag.Nth_Fix
                    (Item, (if Index = Choice_Diagnostic then Choice_Fix
                            else 1));
               begin
                  for Position in 1 .. Diag.Edit_Count (Selected) loop
                     declare
                        One : constant Diag.Edit :=
                          Diag.Nth_Edit (Selected, Position);
                        At_Index : Positive := 1;
                     begin
                        if Diag.Source_Of (One) = Source then
                           while At_Index <= Natural (Result.Length)
                             and then Diag.Span_Of
                               (Result.Element (At_Index)).First
                                 <= Diag.Span_Of (One).First
                           loop
                              At_Index := At_Index + 1;
                           end loop;
                           Result.Insert (At_Index, One);
                        end if;
                     end;
                  end loop;
               end;
            end if;
         end;
      end loop;
      return Result;
   end Collected;

   function Edits
     (Found  : Diag.Diagnostic_List;
      Source : Landin.Source.Source_Id;
      Choice_Diagnostic : Natural := 0;
      Choice_Fix        : Positive := 1) return Boolean
     is (not Collected
           (Found, Source, Choice_Diagnostic, Choice_Fix).Is_Empty);

   function Applied
     (Found   : Diag.Diagnostic_List;
      Source  : Landin.Source.Source_Id;
      Text    : String;
      Clashed : out Boolean;
      Choice_Diagnostic : Natural := 0;
      Choice_Fix        : Positive := 1) return String
   is
      Ordered : constant Edit_Vectors.Vector := Collected
        (Found, Source, Choice_Diagnostic, Choice_Fix);
      Applying : Landin.Diagnostics.Applying.Edit_Lists.Vector;
   begin
      Clashed := False;
      for One of Ordered loop
         for Other of Applying loop
            if Landin.Diagnostics.Applying.Clash (Other, One) then
               Clashed := True;
               return Text;
            end if;
         end loop;
         Landin.Diagnostics.Applying.Insert_Ordered (Applying, One);
      end loop;
      return Landin.Diagnostics.Applying.Applied (Text, Applying);
   end Applied;

end Landin.Testing.Fixes;
