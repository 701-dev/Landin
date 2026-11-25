--  Optional CodeView serialization of the source, IR and allocation facts
--  the DWARF encoder reads, for COFF objects whose linker writes a PDB.
--  No format-specific fact flows back into those authorities.
--
--  The assembler's own CodeView directives carry what needs the final
--  layout: `.cv_file` and `.cv_loc` the line table, `.cv_def_range` each
--  variable's address ranges and the gaps between them.  Everything else
--  is written here: the symbol records of `.debug$S`, with label
--  differences for their lengths, and the type records of `.debug$T`,
--  whose bytes are all known before assembly.
--
--  The description presents a program as C, as the DWARF one does (D2287):
--  a debugger evaluates no Landin expression.  CodeView names no base type
--  of its own, so `i32` is presented as C's `int` and so on.
with Landin.Backend.Debug_Locations;
with Landin.Debugging;
with Landin.Optimization;
with Landin.Provenance;
with Landin.Resolution;
with Landin.Source.Names;

package Landin.Backend.Codeview is

   --  Where a slot's value is, in CodeView's terms.
   type Place_Kind is
     (Nowhere,
      --  The value is the register.
      In_Register,
      --  The value is in memory at the register's address plus Offset.
      In_Memory,
      --  The memory at the register's address plus Offset holds the
      --  value's address, which CodeView spells as a reference.
      By_Reference);

   type Place is record
      Kind     : Place_Kind := Nowhere;
      --  CodeView's register number (CV_AMD64_* or CV_ARM64_*, cvconst.h).
      Register : Natural := 0;
      Offset   : Long_Long_Integer := 0;
   end record;

   --  The `.cv_file` directive of every recorded source, by its number.
   function Files (Info : Landin.Debugging.Information) return String;

   --  The function identity `.cv_loc` names inside Item.
   function Function_Id (Item : Landin.IR.Item_Id) return String;

   --  The line Site begins, inside Item, or "" when Site is unknown.
   function Source_Line
     (Info : Landin.Debugging.Information;
      Item : Landin.IR.Item_Id;
      Site : Landin.Provenance.Origin) return String;

   generic
      type Placement (<>) is private;
      type Placement_Access is access all Placement;
      type Frame_Access is access all Frame;
      with function Make
        (Of_Unit : Landin.IR.Unit; Item : Landin.IR.Item_Id;
         Facts : Landin.Targets.Target_Facts;
         Options : Landin.Optimization.Options) return Placement;
      with function Frame_For
        (Of_Unit : Landin.IR.Unit; Item : Landin.IR.Item_Id;
         Facts : Landin.Targets.Target_Facts; Plan : Placement;
         Options : Landin.Optimization.Options) return Frame;
      --  As Landin.Backend.Dwarf's Slot_Expression: Indirect when the
      --  slot holds the address of what it presents, Address_Only when
      --  only a place in memory will do.
      with function Slot_Place
        (Plan : Placement; Layout : Frame; Slot : Landin.IR.Slot_Id;
         Indirect, Address_Only : Boolean) return Place;
      --  S_FRAMEPROC's code for the frame record's register, the base
      --  of the locals and the parameters: 2 for x64's RBP and ARM64's
      --  x29.
      Frame_Register : Natural;
      with procedure Narrow
        (Of_Unit : Landin.IR.Unit; Item : Landin.IR.Item_Id;
         Plan : Placement; Slot : Landin.IR.Slot_Id;
         Live : in out Landin.Backend.Debug_Locations.Flags.Vector;
         Overwriter : in out Landin.IR.Value_Id)
        is null;
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
        (Item : Landin.IR.Item_Id) return Placement_Access := null;
      Cached_Frame : access function
        (Item : Landin.IR.Item_Id) return Frame_Access := null;
      Trapped : access function
        (Item : Landin.IR.Item_Id; Value : Landin.IR.Value_Id)
         return Boolean := null;
      Stack_Switch, Stack_Start : String := "") return String;

   --  D2481: the label that ends Symbol, a routine of the backend's own
   --  that no item declares, which Sections describes as a procedure of
   --  that name when it is the program's stack switch or start routine.
   --  The backend places it after the routine's last instruction.
   function Routine_End (Prefix, Symbol : String) return String;

end Landin.Backend.Codeview;
