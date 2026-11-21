with Ada.Strings.Unbounded;

package body Landin.Diagnostics.Applying is

   package Unbounded renames Ada.Strings.Unbounded;

   use type Landin.Source.Byte_Offset;

   function First_Exact (Item : Diagnostic) return Natural is
   begin
      for Index in 1 .. Fix_Count (Item) loop
         if Level (Nth_Fix (Item, Index)) = Exact then
            return Index;
         end if;
      end loop;
      return 0;
   end First_Exact;

   function Clash (Left, Right : Edit) return Boolean is
      A : constant Landin.Source.Span := Span_Of (Left);
      B : constant Landin.Source.Span := Span_Of (Right);
   begin
      if Landin.Source.Length (A) = 0 and then Landin.Source.Length (B) = 0
      then
         return A.First = B.First;
      end if;
      return A.First < B.Last and then B.First < A.Last;
   end Clash;

   procedure Insert_Ordered (Into : in out Edit_Lists.Vector; One : Edit) is
      Where    : constant Landin.Source.Span := Span_Of (One);
      At_Index : Positive := 1;

      --  Whether One goes after the edit at Index: an insertion at the
      --  offset a replacement starts at goes before it, so it is written
      --  in front of the replaced bytes rather than into them.
      function After (Index : Positive) return Boolean is
        (Span_Of (Into (Index)).First < Where.First
         or else (Span_Of (Into (Index)).First = Where.First
                  and then (Landin.Source.Length (Where) > 0
                            or else Landin.Source.Length
                              (Span_Of (Into (Index))) = 0)));
   begin
      while At_Index <= Natural (Into.Length) and then After (At_Index)
      loop
         At_Index := At_Index + 1;
      end loop;
      Into.Insert (At_Index, One);
   end Insert_Ordered;

   function Applied (Text : String; Ordered : Edit_Lists.Vector)
     return String
   is
      Result : Unbounded.Unbounded_String :=
        Unbounded.To_Unbounded_String (Text);
   begin
      for Index in reverse 1 .. Natural (Ordered.Length) loop
         declare
            Where : constant Landin.Source.Span := Span_Of (Ordered (Index));
         begin
            Unbounded.Replace_Slice
              (Result,
               Low  => Natural (Where.First) + 1,
               High => Natural (Where.Last),
               By   => Replacement (Ordered (Index)));
         end;
      end loop;
      return Unbounded.To_String (Result);
   end Applied;

end Landin.Diagnostics.Applying;
