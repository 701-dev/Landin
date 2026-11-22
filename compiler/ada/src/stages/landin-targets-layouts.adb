package body Landin.Targets.Layouts is

   use type Landin.Layouts.Policy;

   function Make
     (Fields  : Field_Extent_Array;
      Policy  : Landin.Layouts.Policy := Landin.Layouts.Natural;
      Maximum : Byte_Count := Byte_Count'Last) return Plan
   is
      Made : Plan (Fields'Length);
   begin
      if Policy = Landin.Layouts.Packed then
         if Fields'Length = 0 then
            raise Landin.Compiler_Defect with "an empty packed image";
         end if;
         Made.Size := Fields (Fields'First).Size;
         Made.Alignment := Fields (Fields'First).Alignment;
         for Field of Fields loop
            if Field.Size /= Made.Size
              or else Field.Alignment /= Made.Alignment
            then
               raise Landin.Compiler_Defect with
                 "packed fields disagree on their containing image";
            end if;
         end loop;
         if Made.Size > Maximum then
            raise Landin.Compiler_Defect with "packed image exceeds limit";
         end if;
         Made.Offsets := [others => 0];
         return Made;
      end if;
      declare
         Layout : Placement := Empty_Placement;
      begin
         for Position in Made.Offsets'Range loop
            declare
               --  D410: a byte-packed C record places every field at
               --  alignment one, so it has no padding and alignment one.
               Field : constant Field_Extent :=
                 (if Policy = Landin.Layouts.C_Packed
                  then (Fields (Fields'First + Position - 1).Size, 1)
                  else Fields (Fields'First + Position - 1));
            begin
               if not Can_Place
                 (Layout, Field.Size, Field.Alignment, Byte_Count'Last)
               then
                  raise Landin.Compiler_Defect with
                    "invalid or overflowing field placement";
               end if;
               Place (Layout, Field.Size, Field.Alignment,
                      Made.Offsets (Position));
            end;
         end loop;
         Made.Size := Size_Of (Layout);
         Made.Alignment := Alignment_Of (Layout);
      end;
      if Made.Size > Maximum then
         raise Landin.Compiler_Defect with
           "field placement exceeds the target object limit";
      end if;
      return Made;
   end Make;

   function Fits
     (Fields  : Field_Extent_Array;
      Policy  : Landin.Layouts.Policy := Landin.Layouts.Natural;
      Maximum : Byte_Count := Byte_Count'Last) return Boolean
   is
   begin
      declare
         Made : constant Plan := Make (Fields, Policy, Maximum);
      begin
         return Made.Size <= Maximum;
      end;
   exception
      when Landin.Compiler_Defect =>
         return False;
   end Fits;

end Landin.Targets.Layouts;
