--  The CodeView description of an x86-64 COFF object: Landin.Backend.
--  Codeview's encoder over this backend's allocation plans and frames.
with Landin.Backend.X86_64.Dwarf;
with Landin.Provenance;

package Landin.Backend.X86_64.Codeview is

   function Files (Info : Landin.Debugging.Information) return String;
   function Function_Id (Item : Landin.IR.Item_Id) return String;
   function Source_Line
     (Info : Landin.Debugging.Information;
      Item : Landin.IR.Item_Id;
      Site : Landin.Provenance.Origin) return String;

   function Sections
     (Of_Unit : Landin.IR.Unit;
      Meanings : Landin.Resolution.Table;
      Names : Landin.Source.Names.Table;
      Facts : Landin.Targets.Target_Facts;
      Options : Landin.Optimization.Options;
      Info : Landin.Debugging.Information;
      Prefix : String;
      Symbol : not null access function
        (Item : Landin.IR.Item_Id) return String;
      Exported : not null access function
        (Item : Landin.IR.Item_Id) return Boolean;
      Cached_Plan : access function
        (Item : Landin.IR.Item_Id) return Dwarf.Plan_Access := null;
      Cached_Frame : access function
        (Item : Landin.IR.Item_Id) return Dwarf.Frame_Access := null;
      Trapped : access function
        (Item : Landin.IR.Item_Id; Value : Landin.IR.Value_Id)
         return Boolean := null) return String;

end Landin.Backend.X86_64.Codeview;
