with Ada.Strings.Fixed;

package body Landin.Backend.COFF is

   function Section_Name (Name : String) return String is
      function Starts (Prefix : String) return Boolean
        is (Name'Length >= Prefix'Length
            and then Name (Name'First .. Name'First + Prefix'Length - 1)
              = Prefix);
      function After (Prefix : String) return String
        is (Name (Name'First + Prefix'Length .. Name'Last));
   begin
      if Starts (".data.rel.ro.local.") then
         return ".rdata$" & After (".data.rel.ro.local.");
      elsif Starts (".rodata.cst4.") then
         return ".rdata$" & After (".rodata.cst4.");
      elsif Starts (".rodata.cst8.") then
         return ".rdata$" & After (".rodata.cst8.");
      elsif Starts (".rodata.str1.1.") then
         return ".rdata$" & After (".rodata.str1.1.");
      elsif Starts (".rodata.") then
         return ".rdata$" & After (".rodata.");
      elsif Starts (".text.") then
         return ".text$" & After (".text.");
      elsif Starts (".data.") then
         return ".data$" & After (".data.");
      elsif Starts (".bss.") then
         return ".bss$" & After (".bss.");
      elsif Starts (".tbss.") then
         return ".tls$" & After (".tbss.");
      end if;
      raise Compiler_Defect with "no COFF section for " & Name;
   end Section_Name;

   function Section_Flags (Flags : String) return String
     is (if Ada.Strings.Fixed.Index (Flags, "x") > 0 then """xr"""
         elsif Ada.Strings.Fixed.Index (Flags, "T") > 0 then """dw"""
         elsif Ada.Strings.Fixed.Index (Flags, "nobits") > 0 then """bw"""
         elsif Ada.Strings.Fixed.Index (Flags, "w") > 0 then """dw"""
         else """dr""");

   function Directive (ELF_Directive : String) return String is
      function Opened (Keyword : String) return Boolean
        is (ELF_Directive'Length > Keyword'Length
            and then ELF_Directive
              (ELF_Directive'First
               .. ELF_Directive'First + Keyword'Length - 1) = Keyword);
      Keyword : constant String :=
        (if Opened (".section ") then ".section "
         elsif Opened (".pushsection ") then ".pushsection "
         else "");
   begin
      if Keyword = "" then
         return ELF_Directive;
      end if;
      declare
         Rest : constant String := ELF_Directive
           (ELF_Directive'First + Keyword'Length .. ELF_Directive'Last);
         Comma : constant Natural := Ada.Strings.Fixed.Index (Rest, ",");
      begin
         if Comma = 0 then
            raise Compiler_Defect with "no flags in " & ELF_Directive;
         end if;
         return Keyword & Section_Name (Rest (Rest'First .. Comma - 1))
           & "," & Section_Flags (Rest (Comma + 1 .. Rest'Last));
      end;
   end Directive;

   function Alternate_Name (Name : String; Defined : Boolean) return String
   is
      Substitute : constant String :=
        Landin.Targets.Capabilities.COFF_Substitute_Prefix & Name;
   begin
      return ".ascii "" /alternatename:"
        & (if Defined then Name & "=" & Substitute
           else Substitute & "=" & Name) & """";
   end Alternate_Name;

end Landin.Backend.COFF;
