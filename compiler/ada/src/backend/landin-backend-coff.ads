--  COFF assembly spellings, for every backend whose objects are COFF.
--
--  A backend that writes ELF's spellings writes a COFF object by passing
--  its section directives through here: a COFF section's name groups by
--  `$`, so that the linker gathers `.text$NAME` into `.text` and so on, its
--  flags are COFF's letters, and a symbol has no type or size directive.
--  A read-only datum is `.rdata`, which the Windows loader relocates as it
--  relocates any section, and a thread's template is `.tls$NAME`, between
--  the `.tls` and `.tls$zzz` markers the TLS directory names.  The x86-64
--  and arm64 backends both write Windows' objects through it.
package Landin.Backend.COFF is

   --  NAME as ELF spells it, `.text.landin_x`, in COFF's spelling.
   function Section_Name (Name : String) return String;

   --  FLAGS as ELF spells them, `"ax",@progbits`, in COFF's letters.  A
   --  thread template's zeros are bytes of the image on Windows, which
   --  copies the template for every thread.
   function Section_Flags (Flags : String) return String;

   function Section (Name, Flags : String) return String
     is (".section " & Section_Name (Name) & "," & Section_Flags (Flags));

   function Push_Section (Name, Flags : String) return String
     is (".pushsection " & Section_Name (Name) & ","
         & Section_Flags (Flags));

   --  An ELF `.section NAME,FLAGS` or `.pushsection NAME,FLAGS` directive
   --  in COFF's spelling; any other directive unchanged.
   function Directive (ELF_Directive : String) return String;

end Landin.Backend.COFF;
