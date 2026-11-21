--  Applying fixes to the text they were made for.
--
--  A fix's edits name byte spans of the text a compilation read.  `refine
--  fix` applies the exact ones and the test harness applies the ones a
--  fixture pins, and both need the same two answers: whether two edits can
--  be applied together, and the text once they are.  So the one routine is
--  here, beside the edits it reads, and no stage calls it: a stage builds a
--  fix and leaves applying it to whoever asked for the report.

with Ada.Containers.Indefinite_Vectors;

package Landin.Diagnostics.Applying is

   package Edit_Lists is new Ada.Containers.Indefinite_Vectors
     (Index_Type => Positive, Element_Type => Edit);

   --  The first of Item's fixes that is Exact, or 0 when none is: the fix
   --  a tool applies unasked.
   function First_Exact (Item : Diagnostic) return Natural;

   --  Whether Left and Right, two edits of one text, cannot both be
   --  applied: their spans overlap, or both insert at one offset, where
   --  neither order is the one meant.  Spans that only touch do not clash.
   function Clash (Left, Right : Edit) return Boolean;

   --  One put among Into's edits of the same source in byte order, an
   --  insertion before a replacement that starts where it does, so that
   --  applying them is defined.
   procedure Insert_Ordered (Into : in out Edit_Lists.Vector; One : Edit);

   --  Text with every one of Ordered's edits applied, from the end of the
   --  text back so each edit's offsets are those of Text.  Ordered is in
   --  byte order, every edit names the same source, and no two clash.
   function Applied (Text : String; Ordered : Edit_Lists.Vector)
     return String
     with Pre => (for all Index in 2 .. Natural (Ordered.Length) =>
                    not Clash (Ordered (Index - 1), Ordered (Index)));

end Landin.Diagnostics.Applying;
