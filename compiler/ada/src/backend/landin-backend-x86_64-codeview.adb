with Landin.Backend.X86_64.Allocation;

package body Landin.Backend.X86_64.Codeview is
   use Landin.IR;
   use type Allocation.Location_Kind;
   package CV renames Landin.Backend.Codeview;

   --  CodeView's numbers for x64's registers (cvconst.h, CV_AMD64_*).
   RBP : constant := 334;

   function Register_Code
     (Register : Allocation.General_Register) return Natural
   is (case Register is
          when Allocation.RBX => 329,
          when Allocation.RSI => 332,
          when Allocation.RDI => 333,
          when Allocation.R8 => 336,
          when Allocation.R9 => 337,
          when Allocation.R10 => 338,
          when Allocation.R11 => 339,
          when Allocation.R12 => 340,
          when Allocation.R13 => 341,
          when Allocation.R14 => 342,
          when Allocation.R15 => 343);

   --  XMM0 to XMM7 are 154 to 161, XMM8 to XMM15 252 to 259.
   function XMM_Code (Number : Natural) return Natural is
     (if Number < 8 then 154 + Number else 252 + Number - 8);

   function Files (Info : Landin.Debugging.Information) return String
     renames CV.Files;
   function Function_Id (Item : Item_Id) return String
     renames CV.Function_Id;
   function Source_Line
     (Info : Landin.Debugging.Information;
      Item : Item_Id;
      Site : Landin.Provenance.Origin) return String
     renames CV.Source_Line;

   function Frame_For
     (Of_Unit : Unit; Item : Item_Id;
      Facts : Landin.Targets.Target_Facts; Plan : Allocation.Plan;
      Options : Landin.Optimization.Options) return Frame;
   function Frame_For
     (Of_Unit : Unit; Item : Item_Id;
      Facts : Landin.Targets.Target_Facts; Plan : Allocation.Plan;
      Options : Landin.Optimization.Options) return Frame is
     (Allocation.Frame_For (Of_Unit, Item, Facts, Plan, Options));

   --  As Landin.Backend.X86_64.Dwarf's Slot_Expression, in CodeView's
   --  terms: a frame home is below RBP, the frame register.
   function Slot_Place
     (Plan : Allocation.Plan; Layout : Frame; Slot : Slot_Id;
      Indirect, Address_Only : Boolean) return CV.Place;
   function Slot_Place
     (Plan : Allocation.Plan; Layout : Frame; Slot : Slot_Id;
      Indirect, Address_Only : Boolean) return CV.Place
   is
      Where : constant Allocation.Location := Plan.Slot (Positive (Slot));
   begin
      if Where.Kind = Allocation.GP
        and then (Indirect or else not Address_Only)
      then
         return (if Indirect
                 then (CV.In_Memory, Register_Code (Where.Register), 0)
                 else (CV.In_Register, Register_Code (Where.Register), 0));
      elsif Where.Kind = Allocation.SSE
        and then not Indirect and then not Address_Only
      then
         return (CV.In_Register,
                 XMM_Code (Allocation.Number (Where.Float_Register)), 0);
      elsif Has_Slot_Home (Layout, Slot) then
         return ((if Indirect then CV.By_Reference else CV.In_Memory), RBP,
                 -Long_Long_Integer (Slot_Offset (Layout, Slot)));
      end if;
      return (others => <>);
   end Slot_Place;

   function Encode is new CV.Sections
     (Allocation.Plan, Dwarf.Plan_Access, Dwarf.Frame_Access,
      Allocation.Make, Frame_For, Slot_Place, 2, Dwarf.Narrow);

   function Sections
     (Of_Unit : Unit;
      Meanings : Landin.Resolution.Table;
      Names : Landin.Source.Names.Table;
      Facts : Landin.Targets.Target_Facts;
      Options : Landin.Optimization.Options;
      Info : Landin.Debugging.Information;
      Prefix : String;
      Symbol : not null access function (Item : Item_Id) return String;
      Exported : not null access function (Item : Item_Id) return Boolean;
      Cached_Plan : access function
        (Item : Item_Id) return Dwarf.Plan_Access := null;
      Cached_Frame : access function
        (Item : Item_Id) return Dwarf.Frame_Access := null;
      Trapped : access function
        (Item : Item_Id; Value : Value_Id) return Boolean := null;
      Stack_Switch, Stack_Start : String := "")
      return String
      renames Encode;

end Landin.Backend.X86_64.Codeview;
