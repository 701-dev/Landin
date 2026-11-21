--  `refine fix`: a program's sources with the exact fixes of its report
--  applied (D1847).
--
--  The program is checked as `refine check` checks it, with the same
--  arguments, and every diagnostic's first exact fix is applied to the
--  bytes the check read.  The result is checked again, because a stage
--  that refused stops the stages after it and their fixes appear only
--  once the refusal is mended, and so on until a check offers no exact
--  fix that can be applied.  Every pass reads the sources through an
--  overlay holding the bytes the passes before it wrote, so nothing
--  reaches a file until the last pass, and with Check_Only nothing does.
--
--  A Likely fix is never applied: it is a guess at what was meant, which
--  an editor offers and a person accepts.  Of two exact fixes whose edits
--  clash, the first in the report is applied and the second is left to
--  the next pass, which offers it again if the program still needs it.

with Landin.Diagnostics.Warning_Policy;
with Landin.Driver;
with Landin.Platform;

private package Landin.Commands.Fixing is

   --  More passes than any program needs: each pass applies at least one
   --  fix, and a fix only mends.  Reaching it means two fixes undo each
   --  other, a defect in the stages that offered them, which is reported
   --  rather than looped on.
   Pass_Limit : constant := 64;

   --  Arguments is the check request as the driver reads it, without the
   --  command's own `--check`.  Output lists each fix applied, one line
   --  each, `PATH:LINE:COLUMN: CODE: what the fix does`, at the place its
   --  diagnostic had in the bytes of the pass that applied it.  The report
   --  and status are the last check's: what is left once the fixes are in.
   --  With Check_Only the files are left as they are, the report and the
   --  status are the first check's, and a fix that would be applied makes
   --  the status Status_Reported.
   function Execute
     (Arguments  : Landin.Platform.Path_List;
      Host       : Landin.Platform.Filesystem'Class;
      Tools      : Landin.Platform.Tool_Runner'Class;
      Meter      : Landin.Platform.Resource_Meter'Class;
      Built_For  : String;
      Warnings   : Landin.Diagnostics.Warning_Policy.Policy;
      Protected_Inputs : Landin.Platform.Path_List;
      Protected_Identities : Landin.Platform.Identity_List;
      Check_Only : Boolean) return Landin.Driver.Outcome;

end Landin.Commands.Fixing;
