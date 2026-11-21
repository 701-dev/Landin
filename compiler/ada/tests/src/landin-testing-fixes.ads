--  Applying a report's fixes, chosen as a fixture's case chooses them.
--
--  The harness applies a diagnostic's first fix, or the alternative a case
--  selects, to prove that each is what it claims; the edits themselves are
--  applied by Landin.Diagnostics.Applying, as `refine fix` applies its exact
--  ones (D1847).

with Landin.Diagnostics;
with Landin.Source;

package Landin.Testing.Fixes is

   --  Text with every edit that names Source applied.  The first fix of each
   --  diagnostic is used, except that Choice_Fix selects an alternative for
   --  Choice_Diagnostic when it is nonzero.  Edits are applied from
   --  the end of the text towards its start, so each one's offsets are the
   --  offsets of the text the compilation read.  Two edits from different
   --  diagnostics that overlap cannot both be applied, and Clashed says so.
   function Applied
     (Found   : Landin.Diagnostics.Diagnostic_List;
      Source  : Landin.Source.Source_Id;
      Text    : String;
      Clashed : out Boolean;
      Choice_Diagnostic : Natural := 0;
      Choice_Fix        : Positive := 1) return String;

   --  Whether the selected fixes edit Source.
   function Edits
     (Found  : Landin.Diagnostics.Diagnostic_List;
      Source : Landin.Source.Source_Id;
      Choice_Diagnostic : Natural := 0;
      Choice_Fix        : Positive := 1) return Boolean;

end Landin.Testing.Fixes;
