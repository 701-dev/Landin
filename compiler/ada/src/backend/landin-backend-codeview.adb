with Ada.Containers.Indefinite_Ordered_Maps;
with Ada.Containers.Ordered_Maps;
with Ada.Containers.Ordered_Sets;
with Ada.Containers.Vectors;
with Ada.Strings.Fixed;
with Ada.Strings.Unbounded;
with Landin.Backend.Dwarf;
with Landin.IR.Shape_Measurement;
with Landin.Layouts;
with Landin.Syntax;
with Landin.Syntax.Forest;
with Landin.Targets.Layouts;
with Landin.Types;

package body Landin.Backend.Codeview is

   package US renames Ada.Strings.Unbounded;
   use Landin.IR;
   use type Landin.Layouts.Policy;
   use type Landin.IR.Declaration_Id;
   use type Landin.IR.Nominal_Type_Id;
   use type Landin.Types.Type_Kind;
   use type Landin.Resolution.Scope_Id;
   use type Landin.Resolution.Scope_Sort;
   use type Landin.Source.Source_Id;
   use type Landin.Source.Names.Name_Id;
   use type Landin.Syntax.Node_Id;
   use type Landin.Syntax.Node_Kind;
   use type Landin.Targets.Byte_Count;

   LF : constant Character := Character'Val (10);
   HT : constant Character := Character'Val (9);

   function N (Value : Natural) return String is
     (Ada.Strings.Fixed.Trim (Natural'Image (Value), Ada.Strings.Both));
   function I (Value : Long_Long_Integer) return String is
     (Ada.Strings.Fixed.Trim (Long_Long_Integer'Image (Value),
                              Ada.Strings.Both));

   function Files (Info : Landin.Debugging.Information) return String is
      Result : US.Unbounded_String;
   begin
      for Index in 1 .. Landin.Debugging.Count (Info) loop
         US.Append (Result, HT & ".cv_file " & N (Index) & " "
           & Landin.Backend.Dwarf.Quoted (Landin.Debugging.Recorded_Name
               (Info, Landin.Source.Source_Id (Index))) & LF);
      end loop;
      return US.To_String (Result);
   end Files;

   function Function_Id (Item : Item_Id) return String is
     (HT & ".cv_func_id " & N (Natural (Item)));

   function Line_Number
     (Info : Landin.Debugging.Information;
      Site : Landin.Provenance.Origin) return Natural is
     (Natural (Landin.Source.Position_Of
        (Landin.Debugging.Source (Info, Site.Source), Site.Where.First).Line));

   --  D339: a copy's identity follows every item's own, in the order of
   --  the unit's sites, so that the assembler's table of identities is
   --  as long as the items and the copies together.
   function Copy_Identity
     (Of_Unit : Unit; Item : Item_Id; Copy : Positive) return Positive is
     (Item_Count (Of_Unit) + Inline_Site_Number (Of_Unit, Item, Copy));

   --  A copy is called from its call's line, inside Item's own identity.
   --  A call with no known site leaves the copy an identity of its own,
   --  whose lines no routine's table holds.
   function Inline_Site_Id
     (Info : Landin.Debugging.Information;
      Of_Unit : Unit;
      Item : Item_Id;
      Copy : Positive) return String
   is
      Call : constant Landin.Provenance.Origin :=
        Nth_Inline_Site (Of_Unit, Item, Copy).Call;
      Identity : constant String := N (Copy_Identity (Of_Unit, Item, Copy));
   begin
      if Landin.Provenance.Is_Known (Call) then
         return HT & ".cv_inline_site_id " & Identity & " within "
           & N (Natural (Item)) & " inlined_at " & N (Natural (Call.Source))
           & " " & N (Line_Number (Info, Call)) & " 0";
      end if;
      return HT & ".cv_func_id " & Identity;
   end Inline_Site_Id;

   --  CodeView's columns are optional and Microsoft's tools write none;
   --  a stop is a line.
   function Source_Line
     (Info : Landin.Debugging.Information;
      Item : Item_Id;
      Site : Landin.Provenance.Origin;
      Copy : Natural := 0) return String is
     (if not Landin.Provenance.Is_Known (Site) then ""
      else HT & ".cv_loc "
        & N (if Copy = 0 then Natural (Item) else Copy) & " "
        & N (Natural (Site.Source)) & " " & N (Line_Number (Info, Site))
        & " 0");

   --  Record and leaf kinds, from Microsoft's cvinfo.h.
   S_END : constant := 16#0006#;
   S_OBJNAME : constant := 16#1101#;
   S_BLOCK32 : constant := 16#1103#;
   S_UDT : constant := 16#1108#;
   S_LDATA32 : constant := 16#110C#;
   S_GDATA32 : constant := 16#110D#;
   S_LTHREAD32 : constant := 16#1112#;
   S_GTHREAD32 : constant := 16#1113#;
   S_FRAMEPROC : constant := 16#1012#;
   S_COMPILE3 : constant := 16#113C#;
   S_LOCAL : constant := 16#113E#;
   S_LPROC32_ID : constant := 16#1146#;
   S_GPROC32_ID : constant := 16#1147#;
   S_INLINESITE : constant := 16#114D#;
   S_INLINESITE_END : constant := 16#114E#;
   S_PROC_ID_END : constant := 16#114F#;
   LF_POINTER : constant := 16#1002#;
   LF_PROCEDURE : constant := 16#1008#;
   LF_ARGLIST : constant := 16#1201#;
   LF_FIELDLIST : constant := 16#1203#;
   LF_ENUMERATE : constant := 16#1502#;
   LF_ARRAY : constant := 16#1503#;
   LF_STRUCTURE : constant := 16#1505#;
   LF_UNION : constant := 16#1506#;
   LF_ENUM : constant := 16#1507#;
   LF_MEMBER : constant := 16#150D#;
   LF_FUNC_ID : constant := 16#1601#;
   T_VOID : constant := 16#0003#;
   T_64PVOID : constant := 16#0603#;
   T_UQUAD : constant := 16#0023#;
   --  `.debug$S` subsections: symbols, and the inlined routines' lines.
   DEBUG_S_SYMBOLS : constant := 16#F1#;
   DEBUG_S_INLINEELINES : constant := 16#F6#;
   --  Properties: a forward reference, and a unique name after the name.
   Forward_Reference : constant := 16#0080#;
   Unique_Name : constant := 16#0200#;
   --  S_LOCAL's flags.
   Is_Parameter_Flag : constant := 16#0001#;
   Optimized_Out : constant := 16#0100#;
   --  A public member.
   Public : constant := 3;

   function Byte (Value : Natural) return String is
     ([1 => Character'Val (Value mod 256)]);
   function U16 (Value : Natural) return String is
     (Byte (Value) & Byte (Value / 256));
   function U32 (Value : Long_Long_Integer) return String is
     (U16 (Natural (Value mod 65536)) & U16 (Natural (Value / 65536)));
   function U64 (Value : Long_Long_Integer) return String is
     (U32 (Value mod 2 ** 32) & U32 (Value / 2 ** 32));
   function Index_Of (Value : Natural) return String is
     (U32 (Long_Long_Integer (Value)));
   function Z (Text : String) return String is (Text & Character'Val (0));

   --  A numeric leaf: the value itself below LF_NUMERIC, else the
   --  smallest typed leaf that holds it.
   function Leaf (Value : Long_Long_Integer) return String is
     (if Value in 0 .. 16#7FFF# then U16 (Natural (Value))
      elsif Value in 0 .. 16#FFFF_FFFF#
      then U16 (16#8004#) & U32 (Value)
      elsif Value >= 0 then U16 (16#800A#) & U64 (Value)
      elsif Value >= -2 ** 31
      then U16 (16#8003#) & U32 (Value + 2 ** 32)
      else U16 (16#8009#) & U64 (Value));

   --  LF_PAD bytes to the next multiple of four, counting Length from an
   --  aligned start.
   function Pad (Length : Natural) return String;
   function Pad (Length : Natural) return String is
      Count : constant Natural := (4 - Length mod 4) mod 4;
      Result : String (1 .. Count);
   begin
      for Index in Result'Range loop
         Result (Index) := Character'Val (16#F0# + Count - Index + 1);
      end loop;
      return Result;
   end Pad;

   --  A type record: its length, its kind, its bytes and the padding that
   --  keeps the next record aligned.
   function Type_Record (Kind : Natural; Bytes : String) return String;
   function Type_Record (Kind : Natural; Bytes : String) return String is
      Content : constant String := U16 (Kind) & Bytes;
      Padding : constant String := Pad (Content'Length + 2);
   begin
      return U16 (Content'Length + Padding'Length) & Content & Padding;
   end Type_Record;

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
        (Item : Item_Id) return Placement_Access := null;
      Cached_Frame : access function
        (Item : Item_Id) return Frame_Access := null;
      Trapped : access function
        (Item : Item_Id; Value : Value_Id) return Boolean := null;
      Stack_Switch, Stack_Start : String := "")
      return String
   is
      Result, Symbols, Definitions : US.Unbounded_String;
      Width : constant Landin.Targets.Byte_Count :=
        Landin.Targets.Byte_Count
          (Landin.Targets.Bytes (Landin.Targets.Pointer_Size (Facts)));
      Codes : constant Atom_Codes := Ranked (Of_Unit);
      Type_Layouts : Landin.IR.Shape_Measurement.Layout_Cache;
      Labels : Natural := 0;

      procedure Put (Text : String);
      procedure Put (Text : String) is
      begin
         US.Append (Symbols, Text & LF);
      end Put;

      function L (Kind : String; Item : Item_Id; Index : Natural := 0)
         return String is (Landin.Backend.Dwarf.Label_Name
                             (Prefix, Kind, Item, Index));

      function Fresh return String;
      function Fresh return String is
      begin
         Labels := Labels + 1;
         return Prefix & "cv_" & N (Labels);
      end Fresh;

      --  A symbol record opens with its length, which counts from its
      --  kind to the end of its padding, and closes at that end.
      function Open (Kind : Natural) return String;
      function Open (Kind : Natural) return String is
         Start : constant String := Fresh;
         Finish : constant String := Fresh;
      begin
         Put (HT & ".short " & Finish & "-" & Start);
         Put (Start & ":");
         Put (HT & ".short " & N (Kind));
         return Finish;
      end Open;

      procedure Close (Finish : String);
      procedure Close (Finish : String) is
      begin
         Put (HT & ".p2align 2, 0x0");
         Put (Finish & ":");
      end Close;

      procedure Short_Record (Kind : Natural);
      procedure Short_Record (Kind : Natural) is
      begin
         Put (HT & ".short 2");
         Put (HT & ".short " & N (Kind));
      end Short_Record;

      --  A `.debug$S` subsection, of symbols unless Kind says otherwise;
      --  Close_Subsection ends it.
      function Open_Subsection (Kind : Natural := DEBUG_S_SYMBOLS)
         return String;
      function Open_Subsection (Kind : Natural := DEBUG_S_SYMBOLS)
         return String
      is
         Start : constant String := Fresh;
         Finish : constant String := Fresh;
      begin
         Put (HT & ".long " & N (Kind));
         Put (HT & ".long " & Finish & "-" & Start);
         Put (Start & ":");
         return Finish;
      end Open_Subsection;

      procedure Close_Subsection (Finish : String);
      procedure Close_Subsection (Finish : String) is
      begin
         Put (Finish & ":");
         Put (HT & ".p2align 2, 0x0");
      end Close_Subsection;

      procedure Name (Text : String);
      procedure Name (Text : String) is
      begin
         Put (HT & ".asciz " & Landin.Backend.Dwarf.Quoted (Text));
      end Name;

      ------------------------------------------------------------------
      --  Types.

      package Byte_Records is new Ada.Containers.Vectors
        (Positive, US.Unbounded_String, US."=");
      Records : Byte_Records.Vector;

      function Add (Kind : Natural; Bytes : String) return Natural;
      function Add (Kind : Natural; Bytes : String) return Natural is
      begin
         Records.Append (US.To_Unbounded_String (Type_Record (Kind, Bytes)));
         return 16#1000# + Natural (Records.Length) - 1;
      end Add;

      type Description is record
         Shape : Field_Shape;
         Source : Landin.Source.Source_Id := Landin.Source.No_Source;
         Node : Landin.Syntax.Node_Id := Landin.Syntax.No_Node;
         Item : Item_Id := No_Item;
         Slot : Slot_Id := No_Slot;
      end record;
      package Descriptions is new Ada.Containers.Vectors
        (Positive, Description);
      package Naturals is new Ada.Containers.Vectors (Positive, Natural);
      Known : Descriptions.Vector;
      Known_Index : Naturals.Vector;
      package Index_Maps is new Ada.Containers.Ordered_Maps
        (Natural, Natural);
      Forwards, References : Index_Maps.Map;
      --  Nominal aggregates a pointer reached, whose definitions follow.
      Wanted : Descriptions.Vector;
      package Name_Sets is new Ada.Containers.Ordered_Sets (Natural);
      Named_Types : Name_Sets.Set;

      function Decl_Name (Decl : Declaration_Id) return String is
        (Landin.Source.Names.Spelling
           (Names, Landin.Resolution.Name_Of (Meanings, Decl)));
      function Nominal_Name (Nominal : Nominal_Type_Id) return String is
        (Decl_Name (Template_Of (Of_Unit, Nominal)));

      --  As the DWARF encoder's: a nominal aggregate is described once,
      --  with the declaration that names its fields; a scalar has no node.
      function Normal (Input : Description) return Description;
      function Normal (Input : Description) return Description is
         Desc : Description := Input;
      begin
         if Desc.Shape.Kind = Aggregate_Field_Shape
           and then Desc.Shape.Nominal /= No_Nominal_Type
         then
            Desc := (Shape => (Kind => Aggregate_Field_Shape,
                              Nominal => Desc.Shape.Nominal, others => <>),
                     others => <>);
            declare
               Decl : constant Declaration_Id :=
                 Template_Of (Of_Unit, Desc.Shape.Nominal);
               Tree : constant access constant Landin.Syntax.Tree :=
                 Landin.Syntax.Forest.Tree_Of
                   (Info.Trees.all,
                    Landin.Resolution.Source_Of (Meanings, Decl));
               Node : constant Landin.Syntax.Node_Id :=
                 Landin.Resolution.Node_Of (Meanings, Decl);
            begin
               if Landin.Syntax.Kind (Tree.all, Node)
                 = Landin.Syntax.Type_Declaration
               then
                  Desc.Source := Landin.Syntax.Source_Of (Tree.all);
                  Desc.Node := Landin.Syntax.Declared_Type (Tree.all, Node);
               end if;
            end;
         elsif Desc.Shape.Kind = Scalar_Field_Shape then
            Desc.Source := Landin.Source.No_Source;
            Desc.Node := Landin.Syntax.No_Node;
         end if;
         return Desc;
      end Normal;

      function Index_For (Input : Description) return Natural;

      function Shape_Type
        (Shape : Field_Shape;
         Source : Landin.Source.Source_Id := Landin.Source.No_Source;
         Node : Landin.Syntax.Node_Id := Landin.Syntax.No_Node)
         return Natural is
        (Index_For ((Shape => Shape, Source => Source, Node => Node,
                   others => <>)));

      function Simple (Element : Landin.Types.Scalar_Name) return Natural is
        (case Element is
            when Landin.Types.U8 => 16#69#,
            when Landin.Types.U16 => 16#73#,
            when Landin.Types.U32 => 16#75#,
            when Landin.Types.U64 | Landin.Types.Usize => 16#77#,
            when Landin.Types.I8 => 16#68#,
            when Landin.Types.I16 => 16#72#,
            when Landin.Types.I32 => 16#74#,
            when Landin.Types.I64 | Landin.Types.Isize => 16#76#,
            when Landin.Types.F32 => 16#40#,
            when Landin.Types.F64 => 16#41#,
            when Landin.Types.Bool => 16#30#);

      --  A structure or union's kind and names, by its definition's index,
      --  and its forward reference by its unique name.
      type Record_Names is record
         Kind : Natural;
         Name, Unique : US.Unbounded_String;
      end record;
      package Record_Maps is new Ada.Containers.Ordered_Maps
        (Natural, Record_Names);
      package Unique_Maps is new Ada.Containers.Indefinite_Ordered_Maps
        (String, Natural);
      Definitions_Named : Record_Maps.Map;
      Forward_Records : Unique_Maps.Map;

      --  A record's forward reference: its kind, its names and no layout.
      function Forward_Of (Kind : Natural; Name, Unique : String)
         return Natural;
      function Forward_Of (Kind : Natural; Name, Unique : String)
         return Natural is
      begin
         if not Forward_Records.Contains (Unique) then
            Forward_Records.Insert (Unique, Add
              (Kind, U16 (0) & U16 (Forward_Reference + Unique_Name)
               & Index_Of (0)
               & (if Kind = LF_STRUCTURE then Index_Of (0) & Index_Of (0)
                  else "")
               & Leaf (0) & Z (Name) & Z (Unique)));
         end if;
         return Forward_Records.Element (Unique);
      end Forward_Of;

      --  A record by its definition and its names.
      function Define
        (Kind, Count, Fields : Natural; Size : Landin.Targets.Byte_Count;
         Name, Unique : String) return Natural;
      function Define
        (Kind, Count, Fields : Natural; Size : Landin.Targets.Byte_Count;
         Name, Unique : String) return Natural
      is
         Defined : constant Natural := Add
           (Kind, U16 (Count) & U16 (Unique_Name) & Index_Of (Fields)
            & (if Kind = LF_STRUCTURE then Index_Of (0) & Index_Of (0)
               else "")
            & Leaf (Long_Long_Integer (Size)) & Z (Name) & Z (Unique));
      begin
         Definitions_Named.Insert
           (Defined, (Kind, US.To_Unbounded_String (Name),
                      US.To_Unbounded_String (Unique)));
         return Defined;
      end Define;

      --  How a member, an element or a referent names a type: a record
      --  by its forward reference, as Microsoft's and LLVM's compilers
      --  write it, which a debugger completes from the definition.
      function Reached (Typ : Natural) return Natural is
        (if Definitions_Named.Contains (Typ)
         then Forward_Of
           (Definitions_Named (Typ).Kind,
            US.To_String (Definitions_Named (Typ).Name),
            US.To_String (Definitions_Named (Typ).Unique))
         else Typ);

      function Pointer_To (Referent : Natural; Reference : Boolean := False)
         return Natural is
        (Add (LF_POINTER, Index_Of (Reached (Referent)) & Index_Of
           (16#0C# + (if Reference then 16#20# else 0)
            + Natural (Width) * 2 ** 13)));

      function Nominal_Unique (Nominal : Nominal_Type_Id) return String is
        ("landin.type." & N (Nominal_Identities.Position (Of_Unit, Nominal)));

      --  A nominal aggregate by its forward reference, which a pointer
      --  reaches so that a type that points at itself is not a cycle.
      function Forward (Nominal : Nominal_Type_Id) return Natural;
      function Forward (Nominal : Nominal_Type_Id) return Natural is
         Key : constant Natural :=
           Nominal_Identities.Position (Of_Unit, Nominal);
      begin
         if not Forwards.Contains (Key) then
            Forwards.Insert (Key, Forward_Of
              (LF_STRUCTURE, Nominal_Name (Nominal),
               Nominal_Unique (Nominal)));
            if Has_Nominal_Shape (Of_Unit, Nominal) then
               Wanted.Append (Normal ((Shape => (Kind => Aggregate_Field_Shape,
                                                 Nominal => Nominal,
                                                 others => <>),
                                       others => <>)));
            end if;
         end if;
         return Forwards.Element (Key);
      end Forward;

      --  A field list's members, each padded to four bytes.
      procedure Member
        (Fields : in out US.Unbounded_String; Count : in out Natural;
         Name : String; Typ : Natural; Offset : Landin.Targets.Byte_Count);
      procedure Member
        (Fields : in out US.Unbounded_String; Count : in out Natural;
         Name : String; Typ : Natural; Offset : Landin.Targets.Byte_Count)
      is
         Bytes : constant String := U16 (LF_MEMBER) & U16 (Public)
           & Index_Of (Reached (Typ)) & Leaf (Long_Long_Integer (Offset))
           & Z (Name);
      begin
         US.Append (Fields, Bytes & Pad (Bytes'Length));
         Count := Count + 1;
      end Member;

      function Build (Desc : Description) return Natural;

      function Index_For (Input : Description) return Natural is
         Desc : constant Description := Normal (Input);
      begin
         for Index in 1 .. Natural (Known.Length) loop
            if Known (Index) = Desc then
               return Known_Index (Index);
            end if;
         end loop;
         declare
            Built : constant Natural := Build (Desc);
         begin
            Known.Append (Desc);
            Known_Index.Append (Built);
            return Built;
         end;
      end Index_For;

      function Build (Desc : Description) return Natural is
         Shape : constant Field_Shape := Desc.Shape;
         Size : Landin.Targets.Byte_Count := 0;
         Alignment : Landin.Targets.Byte_Alignment;
         Tree : access constant Landin.Syntax.Tree;

         function Child_Node (Position : Positive)
            return Landin.Syntax.Node_Id is
           (if Tree = null or else Desc.Node = Landin.Syntax.No_Node
              or else Landin.Syntax.Kind (Tree.all, Desc.Node)
                /= Landin.Syntax.Struct_Body
              or else Position > Landin.Syntax.Field_Count
                (Tree.all, Desc.Node)
            then Landin.Syntax.No_Node
            else Landin.Syntax.Nth_Field (Tree.all, Desc.Node, Position));

         function Node_Name
           (Node : Landin.Syntax.Node_Id; Fallback : String) return String
         is (if Tree = null or else Node = Landin.Syntax.No_Node
               or else not Landin.Syntax.Has_Name
                 (Landin.Syntax.Kind (Tree.all, Node))
             then Fallback
             else Landin.Source.Names.Spelling
               (Names, Landin.Syntax.Name (Tree.all, Node)));

         function Unique return String is
           (if Shape.Kind = Aggregate_Field_Shape
              and then Shape.Nominal /= No_Nominal_Type
              and then Desc.Item = No_Item
            then Nominal_Unique (Shape.Nominal)
            else "landin.anonymous." & N (Natural (Records.Length)));

         --  A list of fields and the structure it describes.
         function Finish
           (Fields : US.Unbounded_String; Count : Natural; Name : String;
            Unique_Name : String) return Natural is
           (Define (LF_STRUCTURE, Count,
                    Add (LF_FIELDLIST, US.To_String (Fields)), Size, Name,
                    Unique_Name));
      begin
         if Desc.Source /= Landin.Source.No_Source then
            Tree := Landin.Syntax.Forest.Tree_Of
              (Info.Trees.all, Desc.Source);
         end if;
         if Shape.Kind = Array_Field_Shape
           and then Shape.Slice_Element /= No_Pointee
         then
            --  [0570]: a slice is its base address and its length.
            declare
               Reached : constant Field_Shape :=
                 Pointee_Shape (Of_Unit, Shape.Slice_Element);
               Name : constant String :=
                 (if Reached.Kind = Scalar_Field_Shape
                    and then Reached.Pointee = No_Pointee
                    and then Reached.Signature = No_Signature
                    and then Reached.Atoms = No_Atom_Set
                  then "[]" & Landin.Types.Spelling (Reached.Element)
                  elsif Reached.Kind = Aggregate_Field_Shape
                    and then Reached.Nominal /= No_Nominal_Type
                  then "[]" & Nominal_Name (Reached.Nominal)
                  else "slice");
               Fields : US.Unbounded_String;
               Count : Natural := 0;
               Base : constant Natural := Shape_Type
                 ((Element => Landin.Types.Usize,
                   Pointee => Shape.Slice_Element, others => <>));
               Length : constant Natural := Shape_Type
                 ((Element => Landin.Types.Usize, others => <>));
            begin
               Member (Fields, Count, "ptr", Base, 0);
               Member (Fields, Count, "len", Length, Width);
               Size := 2 * Width;
               return Finish (Fields, Count, Name, Unique);
            end;
         elsif Shape.Kind = Aggregate_Field_Shape
           and then Shape.Nominal /= No_Nominal_Type
           and then not Has_Nominal_Shape (Of_Unit, Shape.Nominal)
         then
            --  An opaque pointee: a forward reference and no layout.
            return Forward (Shape.Nominal);
         elsif Desc.Item /= No_Item then
            Size := Slot_Layout (Of_Unit, Desc.Item, Desc.Slot, Facts).Size;
         elsif Shape.Kind /= Array_Field_Shape then
            Field_Extent (Of_Unit, Shape, Facts, Size, Alignment);
         end if;
         if Shape.Kind = Aggregate_Field_Shape
           and then Layout_Of (Of_Unit, Shape) = Landin.Layouts.Packed
         then
            --  A raw image: its complete carrier, as the DWARF one.
            declare
               Fields : US.Unbounded_String;
               Count : Natural := 0;
               Raw : constant Natural := Shape_Type
                 ((Element => (case Size is
                     when 1 => Landin.Types.U8,
                     when 2 => Landin.Types.U16,
                     when 4 => Landin.Types.U32,
                     when others => Landin.Types.U64), others => <>));
            begin
               Member (Fields, Count, "raw", Raw, 0);
               Named_Types.Include
                 (Nominal_Identities.Position (Of_Unit, Shape.Nominal));
               return Finish (Fields, Count, Nominal_Name (Shape.Nominal),
                              Unique);
            end;
         end if;
         case Shape.Kind is
            when Scalar_Field_Shape =>
               if Shape.Pointee /= No_Pointee then
                  declare
                     Reached : constant Field_Shape :=
                       Pointee_Shape (Of_Unit, Shape.Pointee);
                  begin
                     return Pointer_To
                       (if Reached.Kind = Aggregate_Field_Shape
                          and then Reached.Nominal /= No_Nominal_Type
                        then Forward (Reached.Nominal)
                        else Shape_Type (Reached));
                  end;
               elsif Shape.Signature /= No_Signature then
                  return T_64PVOID;
               elsif Shape.Atoms /= No_Atom_Set then
                  --  D423: an atom set is an enumeration of its atoms,
                  --  each with the code this program gives it.
                  declare
                     Fields : US.Unbounded_String;
                     Count : constant Natural :=
                       Atom_Count (Of_Unit, Shape.Atoms);
                  begin
                     for Index in 1 .. Count loop
                        declare
                           Atom : constant Declaration_Id :=
                             Nth_Atom (Of_Unit, Shape.Atoms, Index);
                           Bytes : constant String :=
                             U16 (LF_ENUMERATE) & U16 (Public)
                             & Leaf (Long_Long_Integer
                                 (Atom_Code (Codes, Atom)))
                             & Z (Decl_Name (Atom));
                        begin
                           US.Append (Fields, Bytes & Pad (Bytes'Length));
                        end;
                     end loop;
                     declare
                        Unique_Text : constant String := Unique;
                        List : constant Natural :=
                          Add (LF_FIELDLIST, US.To_String (Fields));
                     begin
                        return Add (LF_ENUM, U16 (Count) & U16 (Unique_Name)
                          & Index_Of (Simple (Shape.Element))
                          & Index_Of (List) & Z ("atoms")
                          & Z (Unique_Text));
                     end;
                  end;
               else
                  return Simple (Shape.Element);
               end if;
            when Array_Field_Shape =>
               declare
                  Element_Shape : constant Field_Shape :=
                    Array_Element_Shape (Of_Unit, Shape);
                  Element : constant Natural := Shape_Type (Element_Shape);
                  Element_Size : Landin.Targets.Byte_Count;
               begin
                  Field_Extent
                    (Of_Unit, Element_Shape, Facts, Element_Size, Alignment);
                  return Add (LF_ARRAY, Index_Of (Reached (Element))
                    & Index_Of (T_UQUAD)
                    & Leaf (Long_Long_Integer (Element_Size)
                            * Long_Long_Integer (Shape.Length))
                    & Z (""));
               end;
            when Aggregate_Field_Shape =>
               declare
                  Count : constant Natural :=
                    (if Desc.Item /= No_Item then Slot_Field_Count
                       (Of_Unit, Desc.Item, Desc.Slot)
                     else Aggregate_Field_Count (Of_Unit, Shape));
                  Shapes : Field_Shape_Array (1 .. Count);
                  Fields : US.Unbounded_String;
                  Members : Natural := 0;
               begin
                  for Field in Shapes'Range loop
                     Shapes (Field) :=
                       (if Desc.Item /= No_Item then Nth_Slot_Field_Shape
                          (Of_Unit, Desc.Item, Desc.Slot, Field)
                        else Nth_Aggregate_Field (Of_Unit, Shape, Field));
                  end loop;
                  declare
                     Placed : constant Landin.Targets.Layouts.Plan :=
                       (if Desc.Item /= No_Item then Slot_Layout
                          (Of_Unit, Desc.Item, Desc.Slot, Facts)
                        else Fields_Layout
                          (Of_Unit, Shapes, Layout_Of (Of_Unit, Shape),
                           Facts));
                  begin
                     for Field in Shapes'Range loop
                        declare
                           Node : constant Landin.Syntax.Node_Id :=
                             Child_Node (Field);
                           Result_Name : constant Landin.Source.Names.Name_Id
                             := (if Desc.Item = No_Item then
                                   Landin.Source.Names.No_Name
                                 else Landin.Debugging.Result_Name
                                   (Info, Declares
                                      (Of_Unit, Desc.Item, Desc.Slot),
                                    Field));
                           Typ : constant Natural := Shape_Type
                             (Shapes (Field), Desc.Source, Node);
                        begin
                           Member
                             (Fields, Members,
                              Node_Name (Node,
                                (if Result_Name = Landin.Source.Names.No_Name
                                 then "field_" & N (Field)
                                 else Landin.Source.Names.Spelling
                                   (Names, Result_Name))),
                              Typ, Placed.Offsets (Field));
                        end;
                     end loop;
                  end;
                  if Shape.Nominal /= No_Nominal_Type
                    and then Desc.Item = No_Item
                  then
                     Named_Types.Include
                 (Nominal_Identities.Position (Of_Unit, Shape.Nominal));
                  end if;
                  return Finish
                    (Fields, Members,
                     (if Shape.Nominal /= No_Nominal_Type then
                        Nominal_Name (Shape.Nominal)
                      else "aggregate"), Unique);
               end;
            when Variant_Field_Shape =>
               --  A tagged overlay, as the DWARF one: the zero-based tag,
               --  and each case's payload at its offsets, as a union.
               declare
                  Fields : US.Unbounded_String;
                  Members : Natural := 0;
                  Tag : constant Natural :=
                    Shape_Type ((Element => Shape.Element, others => <>));
               begin
                  Member (Fields, Members, "tag", Tag, 0);
                  for Which in 1 .. Shape.Cases loop
                     declare
                        Case_Node : constant Landin.Syntax.Node_Id :=
                          (if Tree /= null
                             and then Desc.Node /= Landin.Syntax.No_Node
                             and then Landin.Syntax.Kind (Tree.all, Desc.Node)
                               = Landin.Syntax.Variant_Part
                           then Landin.Syntax.Nth_Case
                             (Tree.all, Desc.Node, Which)
                           else Landin.Syntax.No_Node);
                        Case_Fields : US.Unbounded_String;
                        Case_Members : Natural := 0;
                        Case_Name : constant String :=
                          Node_Name (Case_Node, "case_" & N (Which - 1));
                     begin
                        for Field in 1 .. Variant_Case_Field_Count
                          (Of_Unit, Shape, Which)
                        loop
                           declare
                              Node : constant Landin.Syntax.Node_Id :=
                                (if Case_Node /= Landin.Syntax.No_Node then
                                   Landin.Syntax.Nth_Payload_Field
                                     (Tree.all, Case_Node, Field)
                                 else Landin.Syntax.No_Node);
                              Typ : constant Natural := Shape_Type
                                (Nth_Variant_Case_Field
                                   (Of_Unit, Shape, Which, Field),
                                 Desc.Source, Node);
                           begin
                              Member
                                (Case_Fields, Case_Members,
                                 Node_Name (Node, "field_" & N (Field)), Typ,
                                 Variant_Payload_Field_Offset
                                   (Of_Unit, Shape, Which, Field, Facts,
                                    Type_Layouts));
                           end;
                        end loop;
                        Member (Fields, Members, Case_Name,
                                Finish (Case_Fields, Case_Members, Case_Name,
                                        Unique), 0);
                     end;
                  end loop;
                  --  A union, whose members all begin at its start: a
                  --  structure's may not overlap.
                  declare
                     Unique_Text : constant String := Unique;
                     List : constant Natural :=
                       Add (LF_FIELDLIST, US.To_String (Fields));
                  begin
                     return Define (LF_UNION, Members, List, Size,
                                    Node_Name (Desc.Node, "variant"),
                                    Unique_Text);
                  end;
               end;
         end case;
      end Build;

      ------------------------------------------------------------------
      --  Routines.

      function Signature_Root (Item : Item_Id) return Scope_Id;
      function Signature_Root (Item : Item_Id) return Scope_Id is
         Root : Scope_Id := Scope_Of (Of_Unit, Item, First_Block);
      begin
         while Root /= Landin.Resolution.No_Scope
           and then Landin.Resolution.Sort_Of (Meanings, Root)
             /= Landin.Resolution.Signature
         loop
            Root := Landin.Resolution.Enclosing (Meanings, Root);
         end loop;
         return Root;
      end Signature_Root;

      function Routine_Name (Item : Item_Id) return String is
        (if (if Generic_Template_Of (Of_Unit, Item) /= No_Declaration
             then Generic_Template_Of (Of_Unit, Item)
             else Declares (Of_Unit, Item)) = No_Declaration
         then Symbol (Item)
         else Decl_Name
           (if Generic_Template_Of (Of_Unit, Item) /= No_Declaration
            then Generic_Template_Of (Of_Unit, Item)
            else Declares (Of_Unit, Item)));

      function Slot_Type (Item : Item_Id; Slot : Slot_Id) return Natural;
      function Slot_Type (Item : Item_Id; Slot : Slot_Id) return Natural is
         Shape : Field_Shape;
      begin
         if Is_Address (Of_Unit, Item, Slot) then
            Shape := Address_Shape (Of_Unit, Item, Slot);
         elsif Is_Array (Of_Unit, Item, Slot) then
            Shape := Whole_Slot_Array_Shape (Of_Unit, Item, Slot);
         elsif Is_Aggregate (Of_Unit, Item, Slot) then
            Shape := (Kind => Aggregate_Field_Shape,
                      Nominal => Nominal_Of (Of_Unit, Item, Slot),
                      others => <>);
         else
            Shape := (Element => Type_Of (Of_Unit, Item, Slot),
                      Pointee => Pointee_Of (Of_Unit, Item, Slot),
                      Atoms => Atom_Set_Of (Of_Unit, Item, Slot),
                      others => <>);
         end if;
         return (if Shape.Kind = Aggregate_Field_Shape
                   and then Shape.Nominal = No_Nominal_Type
                   and then not Is_Address (Of_Unit, Item, Slot)
                 then Index_For ((Shape => Shape, Item => Item,
                               Slot => Slot, others => <>))
                 else Shape_Type (Shape));
      end Slot_Type;

      --  A type a debugger reaches through a reference.
      function Reference_To (Typ : Natural) return Natural;
      function Reference_To (Typ : Natural) return Natural is
      begin
         if not References.Contains (Typ) then
            References.Insert (Typ, Pointer_To (Typ, Reference => True));
         end if;
         return References.Element (Typ);
      end Reference_To;

      package Item_Maps is new Ada.Containers.Ordered_Maps
        (Item_Id, Natural);
      Function_Types : Item_Maps.Map;

      --  A routine's LF_FUNC_ID, which its procedure names and so does
      --  each inlined copy of it (D339).
      function Function_Type_Of (Item : Item_Id) return Natural;
      function Function_Type_Of (Item : Item_Id) return Natural is
         Arguments : US.Unbounded_String;
      begin
         if Function_Types.Contains (Item) then
            return Function_Types.Element (Item);
         end if;
         for Index in 1 .. Parameter_Count (Of_Unit, Item) loop
            declare
               Slot : constant Slot_Id := Nth_Parameter (Of_Unit, Item, Index);
            begin
               US.Append (Arguments, Index_Of
                 (if Declares (Of_Unit, Item, Slot) = No_Declaration
                  then T_64PVOID else Slot_Type (Item, Slot)));
            end;
         end loop;
         declare
            Argument_List : constant Natural := Add
              (LF_ARGLIST, U32 (Long_Long_Integer
                 (Parameter_Count (Of_Unit, Item)))
               & US.To_String (Arguments));
            Procedure_Type : constant Natural := Add
              (LF_PROCEDURE, Index_Of (T_VOID) & Byte (0) & Byte (0)
               & U16 (Parameter_Count (Of_Unit, Item))
               & Index_Of (Argument_List));
            Function_Type : constant Natural := Add
              (LF_FUNC_ID, Index_Of (0) & Index_Of (Procedure_Type)
               & Z (Routine_Name (Item)));
         begin
            Function_Types.Insert (Item, Function_Type);
            return Function_Type;
         end;
      end Function_Type_Of;

      --  Each routine a copy was written for, once, with the file and
      --  line its inline sites' lines begin from, which a debugger finds
      --  a copy's declaration by.
      type Inlinee is record
         Callee : Item_Id;
         File, Line : Natural;
      end record;
      package Inlinee_Vectors is new Ada.Containers.Vectors
        (Positive, Inlinee);
      Inlinees : Inlinee_Vectors.Vector;

      function Is_Parameter_Of (Item : Item_Id; Slot : Slot_Id)
         return Boolean is
        (Slot /= No_Slot
         and then (for some Index in 1 .. Parameter_Count (Of_Unit, Item) =>
                     Nth_Parameter (Of_Unit, Item, Index) = Slot));

      package Index_Vectors is new Ada.Containers.Vectors
        (Positive, Positive);
      type Scope_Group is record
         Scope : Scope_Id;
         Slots, Aliases, Inlines, Children : Index_Vectors.Vector;
      end record;
      package Scope_Vectors is new Ada.Containers.Vectors
        (Positive, Scope_Group);
      package Scope_Maps is new Ada.Containers.Ordered_Maps
        (Scope_Id, Positive);

      --  The lexical scopes below Root that hold a slot or an alias of
      --  Item belonging to Site (zero: Item's own), and, for Item's own,
      --  the scopes its inlined copies were called from, as the DWARF
      --  encoder groups them; group 1 is Root.
      procedure Group_Scopes
        (Item : Item_Id; Site : Natural; Root : Scope_Id;
         Groups : in out Scope_Vectors.Vector;
         With_Copies : Boolean);
      procedure Group_Scopes
        (Item : Item_Id; Site : Natural; Root : Scope_Id;
         Groups : in out Scope_Vectors.Vector;
         With_Copies : Boolean)
      is
         Group_Indices : Scope_Maps.Map;

         procedure Add_Scope_Path (From : Scope_Id);
         procedure Add_Scope_Path (From : Scope_Id) is
            Scope : Scope_Id := From;
         begin
            while Scope /= Root
              and then Scope /= Landin.Resolution.No_Scope
            loop
               exit when Group_Indices.Contains (Scope);
               Groups.Append (Scope_Group'(Scope => Scope, others => <>));
               Group_Indices.Insert (Scope, Groups.Last_Index);
               Scope := Landin.Resolution.Enclosing (Meanings, Scope);
            end loop;
         end Add_Scope_Path;
      begin
         Groups.Append (Scope_Group'(Scope => Root, others => <>));
         Group_Indices.Insert (Root, 1);
         for Index in 1 .. Slot_Count (Of_Unit, Item) loop
            declare
               Binding : constant Declaration_Id :=
                 Declares (Of_Unit, Item, Slot_Id (Index));
            begin
               if Binding /= No_Declaration
                 and then Inlined_At (Of_Unit, Item, Slot_Id (Index)) = Site
               then
                  declare
                     Scope : constant Scope_Id :=
                       Landin.Resolution.Scope_Of (Meanings, Binding);
                  begin
                     Add_Scope_Path (Scope);
                     if Group_Indices.Contains (Scope) then
                        Groups.Reference
                          (Group_Indices.Element (Scope)).Slots.Append
                            (Index);
                     end if;
                  end;
               end if;
            end;
         end loop;
         for Index in 1 .. Source_Alias_Count (Of_Unit, Item) loop
            if Alias_Inlined_At (Of_Unit, Item, Index) = Site then
               declare
                  Scope : constant Scope_Id := Landin.Resolution.Scope_Of
                    (Meanings, Nth_Source_Alias
                       (Of_Unit, Item, Index).Binding);
               begin
                  Add_Scope_Path (Scope);
                  if Group_Indices.Contains (Scope) then
                     Groups.Reference
                       (Group_Indices.Element (Scope)).Aliases.Append (Index);
                  end if;
               end;
            end if;
         end loop;
         if With_Copies then
            for Copy in 1 .. Inline_Site_Count (Of_Unit, Item) loop
               declare
                  Scope : constant Scope_Id :=
                    Nth_Inline_Site (Of_Unit, Item, Copy).Scope;
               begin
                  Add_Scope_Path (Scope);
                  Groups.Reference
                    ((if Group_Indices.Contains (Scope)
                      then Group_Indices.Element (Scope) else 1)).Inlines
                    .Append (Copy);
               end;
            end loop;
         end if;
         for Index in 2 .. Natural (Groups.Length) loop
            declare
               Parent : constant Scope_Id := Landin.Resolution.Enclosing
                 (Meanings, Groups.Element (Index).Scope);
            begin
               if Group_Indices.Contains (Parent) then
                  Groups.Reference
                    (Group_Indices.Element (Parent)).Children.Append
                      (Index);
               end if;
            end;
         end loop;
      end Group_Scopes;

      package Label_Sets is new Ada.Containers.Ordered_Sets
        (US.Unbounded_String, US."<", US."=");
      Successors : Label_Sets.Set;

      type Address_Range is record
         First, Last : US.Unbounded_String;
      end record;
      package Range_Vectors is new Ada.Containers.Vectors
        (Positive, Address_Range);

      procedure Routine
        (Item : Item_Id; Plan : Placement; Frame_Plan : Frame);
      procedure Routine
        (Item : Item_Id; Plan : Placement; Frame_Plan : Frame)
      is
         Availability : Debug_Locations.Analysis :=
           Debug_Locations.Prepare (Of_Unit, Item);
         Path_Layouts : Landin.IR.Shape_Measurement.Layout_Cache;
         function Has_Trap (Value : Value_Id) return Boolean is
           (Trapped /= null and then Trapped (Item, Value));

         function Is_Parameter (Slot : Slot_Id) return Boolean is
           (for some Index in 1 .. Parameter_Count (Of_Unit, Item) =>
              Nth_Parameter (Of_Unit, Item, Index) = Slot);

         --  The label one byte into Value's first instruction, so that a
         --  range ending there covers the address a debugger stops at.
         function Successor (Value : Value_Id) return String;
         function Successor (Value : Value_Id) return String is
            Name : constant String := L ("cv_next", Item, Natural (Value));
         begin
            if not Successors.Contains (US.To_Unbounded_String (Name)) then
               Successors.Insert (US.To_Unbounded_String (Name));
               US.Append (Definitions, HT & ".set " & Name & ", "
                 & L ("value", Item, Natural (Value)) & "+1" & LF);
            end if;
            return Name;
         end Successor;

         --  The ranges where Live holds, as the DWARF encoder's location
         --  lists bound them.
         function Ranges
           (Live : Debug_Locations.Flags.Vector;
            Overwriter : Value_Id := No_Value) return Range_Vectors.Vector;
         function Ranges
           (Live : Debug_Locations.Flags.Vector;
            Overwriter : Value_Id := No_Value) return Range_Vectors.Vector
         is
            Found : Range_Vectors.Vector;
            First, Last : Value_Id := No_Value;
            procedure Flush (Entered : Boolean := False);
            procedure Flush (Entered : Boolean := False) is
            begin
               if First /= No_Value then
                  Found.Append
                    (Address_Range'(US.To_Unbounded_String
                        (L ("value", Item, Natural (First))),
                      US.To_Unbounded_String
                        (if Entered then Successor (Last)
                         else L ((if Op_Of (Of_Unit, Item, Last)
                                    in Leave | Fail
                                  then "epilogue" else "after"),
                                 Item, Natural (Last)))));
                  First := No_Value;
               end if;
            end Flush;
         begin
            for B in 1 .. Block_Count (Of_Unit, Item) loop
               for P in 1 .. Length (Of_Unit, Item, Block_Id (B)) loop
                  declare
                     Value : constant Value_Id :=
                       Nth_Value (Of_Unit, Item, Block_Id (B), P);
                  begin
                     if Live (Positive (Value)) then
                        if First = No_Value then
                           First := Value;
                        end if;
                        Last := Value;
                        if Op_Of (Of_Unit, Item, Value) in Leave | Fail then
                           Flush;
                        end if;
                     elsif Value = Overwriter then
                        if First = No_Value then
                           First := Value;
                        end if;
                        Last := Value;
                        Flush (Entered => True);
                     else
                        Flush;
                     end if;
                  end;
               end loop;
            end loop;
            Flush;
            for V in 1 .. Value_Count (Of_Unit, Item) loop
               if Live (V) and then Has_Trap (Value_Id (V)) then
                  Found.Append
                    (Address_Range'
                       (US.To_Unbounded_String (L ("trap", Item, V)),
                      US.To_Unbounded_String (L ("trapped", Item, V))));
               end if;
            end loop;
            return Found;
         end Ranges;

         --  One S_DEFRANGE record for each range.  The assembler measures
         --  the gaps between a record's ranges from the first, so ranges
         --  out of address order, which a block laid out out of its order
         --  gives, would cover what lies between them.
         procedure Def_Range
           (Found : Range_Vectors.Vector; Where : Place;
            Piece_Offset : Landin.Targets.Byte_Count := 0;
            Piece : Boolean := False);
         procedure Def_Range
           (Found : Range_Vectors.Vector; Where : Place;
            Piece_Offset : Landin.Targets.Byte_Count := 0;
            Piece : Boolean := False)
         is
            Kind : constant String :=
              (case Where.Kind is
                  when Nowhere => "",
                  when In_Register =>
                    (if Piece then ", subfield_reg, " & N (Where.Register)
                       & ", " & N (Natural (Piece_Offset))
                     else ", reg, " & N (Where.Register)),
                  when In_Memory | By_Reference =>
                    ", reg_rel, " & N (Where.Register) & ", "
                    & N (if Piece then 1 + 16 * Natural (Piece_Offset)
                         else 0)
                    & ", " & I (Where.Offset));
         begin
            if Where.Kind = Nowhere then
               return;
            end if;
            for Each of Found loop
               Put (HT & ".cv_def_range " & US.To_String (Each.First) & " "
                 & US.To_String (Each.Last) & Kind);
            end loop;
         end Def_Range;

         procedure Local
           (Name_Text : String; Typ : Natural; Flags : Natural;
            Described : Boolean);
         procedure Local
           (Name_Text : String; Typ : Natural; Flags : Natural;
            Described : Boolean)
         is
            Finish : constant String := Open (S_LOCAL);
         begin
            Put (HT & ".long " & N (Typ));
            Put (HT & ".short " & N (Flags
              + (if Described then 0 else Optimized_Out)));
            Name (Name_Text);
            Close (Finish);
         end Local;

         --  A scalar replacement split lives in its pieces, each its own
         --  range of the whole.
         procedure Pieces
           (Slot : Slot_Id; Name_Text : String; Typ, Flags : Natural);
         procedure Pieces
           (Slot : Slot_Id; Name_Text : String; Typ, Flags : Natural)
         is
            Count : constant Positive :=
              Positive (Slot_Part_Count (Of_Unit, Item, Slot));
            First : constant Slot_Id := First_Piece (Of_Unit, Item, Slot);
            Offsets : array (1 .. Count) of Landin.Targets.Byte_Count;
            Wheres : array (1 .. Count) of Place;
            Found : array (1 .. Count) of Range_Vectors.Vector;
            Any : Boolean := False;
         begin
            if Is_Array (Of_Unit, Item, Slot) then
               declare
                  Size : constant Landin.Targets.Byte_Count :=
                    Landin.Targets.Byte_Count (Landin.Targets.Bytes
                      (Size_Of (Slot_Array_Element (Of_Unit, Item, Slot),
                                Facts)));
               begin
                  for Part in 1 .. Count loop
                     Offsets (Part) :=
                       Landin.Targets.Byte_Count (Part - 1) * Size;
                  end loop;
               end;
            else
               declare
                  Layout : constant Landin.Targets.Layouts.Plan :=
                    Slot_Layout (Of_Unit, Item, Slot, Facts);
               begin
                  for Part in 1 .. Count loop
                     Offsets (Part) := Layout.Offsets (Part);
                  end loop;
               end;
            end if;
            for Part in 1 .. Count loop
               declare
                  Held : constant Slot_Id := First + Slot_Id (Part - 1);
                  Here : Debug_Locations.Flags.Vector :=
                    Debug_Locations.Available_Piece
                      (Availability, Of_Unit, Meanings, Info, Item,
                       Slot, Held);
                  Overwriter : Value_Id := No_Value;
               begin
                  Wheres (Part) :=
                    Slot_Place (Plan, Frame_Plan, Held, False, False);
                  if Wheres (Part).Kind /= Nowhere then
                     Narrow (Of_Unit, Item, Plan, Held, Here, Overwriter);
                     Found (Part) := Ranges (Here, Overwriter);
                     Any := Any or else not Found (Part).Is_Empty;
                  end if;
               end;
            end loop;
            Local (Name_Text, Typ, Flags, Any);
            for Part in 1 .. Count loop
               Def_Range (Found (Part), Wheres (Part), Offsets (Part),
                          Piece => True);
            end loop;
         end Pieces;

         --  The routine a copy is of; Item itself for Site zero.
         function Origin_Item (Site : Natural) return Item_Id is
           (if Site = 0 then Item
            else Nth_Inline_Site (Of_Unit, Item, Site).Callee);

         --  A copy's slot is a parameter where the one of the routine's
         --  own it copies is; where it is available is the caller's, in
         --  whose frame it lives.
         procedure Variables
           (Indices : Index_Vectors.Vector; Site : Natural);
         procedure Variables
           (Indices : Index_Vectors.Vector; Site : Natural) is
         begin
            for Index of Indices loop
               declare
                  Slot : constant Slot_Id := Slot_Id (Index);
                  Parameter : constant Boolean := Is_Parameter (Slot);
                  Name_Text : constant String :=
                    Decl_Name (Declares (Of_Unit, Item, Slot));
                  Flags : constant Natural :=
                    (if (if Site = 0 then Parameter
                         else Is_Parameter_Of
                           (Origin_Item (Site),
                            Inlined_Origin (Of_Unit, Item, Slot)))
                     then Is_Parameter_Flag else 0);
               begin
                  if First_Piece (Of_Unit, Item, Slot) /= No_Slot then
                     Pieces (Slot, Name_Text, Slot_Type (Item, Slot), Flags);
                  else
                     declare
                        Where : constant Place := Slot_Place
                          (Plan, Frame_Plan, Slot,
                           Is_Address (Of_Unit, Item, Slot), False);
                        Live : Debug_Locations.Flags.Vector :=
                          Debug_Locations.Available
                            (Availability, Of_Unit, Meanings, Info,
                             Item, Slot, Parameter);
                        Overwriter : Value_Id := No_Value;
                        Found : Range_Vectors.Vector;
                        Typ : Natural := Slot_Type (Item, Slot);
                     begin
                        if Where.Kind /= Nowhere then
                           Narrow (Of_Unit, Item, Plan, Slot, Live,
                                   Overwriter);
                           Found := Ranges (Live, Overwriter);
                        end if;
                        if Where.Kind = By_Reference then
                           Typ := Reference_To (Typ);
                        end if;
                        Local (Name_Text, Typ, Flags, not Found.Is_Empty);
                        Def_Range (Found, Where);
                     end;
                  end if;
               end;
            end loop;
         end Variables;

         --  A source alias: what it presents, and where, when CodeView
         --  can say so.  A module datum's part, or a part reached through
         --  an address held in memory, has no place a local can name.
         --  A copy's alias of the storage an argument was given in stands
         --  for the routine's parameter.
         procedure Alias_Variables
           (Indices : Index_Vectors.Vector; Site : Natural);
         procedure Alias_Variables
           (Indices : Index_Vectors.Vector; Site : Natural) is
         begin
            for Index of Indices loop
               declare
                  Alias : constant Source_Alias :=
                    Nth_Source_Alias (Of_Unit, Item, Index);
                  Path : constant Path_Step_Array :=
                    Source_Alias_Path (Of_Unit, Item, Index);
                  Shape : Field_Shape;
                  Offset : Landin.Targets.Byte_Count := 0;
                  Where : Place;
                  Found : Range_Vectors.Vector;
               begin
                  case Alias.Place.Kind is
                     when Module_Datum =>
                        if Result_Of (Of_Unit, Alias.Place.Datum)
                          = Landin.Types.Fixed_Array
                        then
                           Shape := Whole_Array_Shape
                             (Of_Unit, Alias.Place.Datum);
                           if Alias.Field > 0 then
                              Shape := Array_Element_Shape (Of_Unit, Shape);
                           end if;
                        else
                           Shape := Nth_Field_Shape
                             (Of_Unit, Alias.Place.Datum, Alias.Field);
                        end if;
                     when Frame_Slot =>
                        Where := Slot_Place
                          (Plan, Frame_Plan, Alias.Place.Slot, False, True);
                        if Alias.Field > 0 then
                           Shape := (if Is_Array
                             (Of_Unit, Item, Alias.Place.Slot)
                             then Slot_Array_Element_Shape
                               (Of_Unit, Item, Alias.Place.Slot)
                             else Nth_Slot_Field_Shape
                               (Of_Unit, Item, Alias.Place.Slot,
                                Alias.Field));
                           if Has_Slot_Home (Frame_Plan, Alias.Place.Slot)
                           then
                              Offset := Slot_Offset
                                (Frame_Plan, Alias.Place.Slot)
                                - Field_Offset
                                  (Of_Unit, Item, Frame_Plan,
                                   Alias.Place.Slot,
                                   Part_Position (Alias.Field), Facts);
                           end if;
                        elsif Is_Array (Of_Unit, Item, Alias.Place.Slot)
                        then
                           Shape := Whole_Slot_Array_Shape
                             (Of_Unit, Item, Alias.Place.Slot);
                        else
                           Shape := (Kind => Aggregate_Field_Shape,
                                     Nominal => Nominal_Of
                                       (Of_Unit, Item, Alias.Place.Slot),
                                     others => <>);
                        end if;
                     when Runtime_Address =>
                        Where := Slot_Place
                          (Plan, Frame_Plan, Alias.Place.Address, True, True);
                        Shape := Address_Shape
                          (Of_Unit, Item, Alias.Place.Address);
                        if Alias.Field > 0 then
                           declare
                              Base : constant Path_Step_Array :=
                                [1 => (Part_Position (Alias.Field), 0)];
                           begin
                              Offset := Landin.Backend.Path_Offset
                                (Of_Unit, Shape, Base, Facts, Path_Layouts);
                              Shape := Shape_At (Of_Unit, Shape, Base);
                           end;
                        end if;
                  end case;
                  Offset := Offset + Landin.Backend.Path_Offset
                    (Of_Unit, Shape, Path, Facts, Path_Layouts);
                  Shape := Shape_At (Of_Unit, Shape, Path);
                  if Where.Kind = By_Reference and then Offset > 0 then
                     Where := (others => <>);
                  elsif Where.Kind = In_Memory then
                     Where.Offset := Where.Offset + Long_Long_Integer (Offset);
                  end if;
                  if Where.Kind /= Nowhere then
                     Found := Ranges (Debug_Locations.Available_Alias
                       (Availability, Of_Unit, Meanings, Info, Item, Index));
                  end if;
                  declare
                     Typ : constant Natural := Shape_Type (Shape);
                  begin
                     Local (Decl_Name (Alias.Binding),
                            (if Where.Kind = By_Reference
                             then Reference_To (Typ) else Typ),
                            (if Site /= 0
                               and then Alias_Inlined_Parameter
                                 (Of_Unit, Item, Index) /= No_Slot
                             then Is_Parameter_Flag else 0),
                            not Found.Is_Empty);
                  end;
                  Def_Range (Found, Where);
               end;
            end loop;
         end Alias_Variables;

         procedure Copied_Routine (Site : Positive);

         --  A lexical block's one range: from the first of its ranges to
         --  the last, in the order the blocks are laid out.  Those of
         --  Site's blocks inside its scope, and for Item's own, those of
         --  the copies called inside it, as the DWARF encoder's are.
         procedure Lexical_Scope
           (Groups : Scope_Vectors.Vector; Group_Index : Positive;
            Site : Natural; Is_Root : Boolean := False);
         procedure Lexical_Scope
           (Groups : Scope_Vectors.Vector; Group_Index : Positive;
            Site : Natural; Is_Root : Boolean := False)
         is
            Group : constant Scope_Group := Groups.Element (Group_Index);
            First, Last : Value_Id := No_Value;
         begin
            if not Is_Root then
               for B in 1 .. Block_Count (Of_Unit, Item) loop
                  declare
                     Block : constant Block_Id := Block_Id (B);
                     Count : constant Natural :=
                       Length (Of_Unit, Item, Block);
                  begin
                     if Count > 0
                       and then
                         (if Inlined_At (Of_Unit, Item, Block) = Site
                          then Debug_Locations.Within
                            (Meanings, Scope_Of (Of_Unit, Item, Block),
                             Group.Scope)
                          else Site = 0
                            and then Debug_Locations.Within
                              (Meanings,
                               Nth_Inline_Site
                                 (Of_Unit, Item,
                                  Inlined_At (Of_Unit, Item, Block)).Scope,
                               Group.Scope))
                     then
                        if First = No_Value then
                           First := Nth_Value (Of_Unit, Item, Block, 1);
                        end if;
                        Last := Nth_Value (Of_Unit, Item, Block, Count);
                     end if;
                  end;
               end loop;
               if First = No_Value then
                  return;
               end if;
               declare
                  Finish : constant String := Open (S_BLOCK32);
                  Start : constant String :=
                    L ("value", Item, Natural (First));
               begin
                  Put (HT & ".long 0");
                  Put (HT & ".long 0");
                  Put (HT & ".long " & L ("after", Item, Natural (Last))
                    & "-" & Start);
                  Put (HT & ".secrel32 " & Start);
                  Put (HT & ".secidx " & Symbol (Item));
                  Name ("");
                  Close (Finish);
               end;
            end if;
            Variables (Group.Slots, Site);
            Alias_Variables (Group.Aliases, Site);
            for Copy of Group.Inlines loop
               Copied_Routine (Copy);
            end loop;
            for Child of Group.Children loop
               Lexical_Scope (Groups, Child, Site);
            end loop;
            if not Is_Root then
               Short_Record (S_END);
            end if;
         end Lexical_Scope;

         --  D339: one inlined copy, a frame of the routine it is of whose
         --  lines are those the backend wrote under the copy's identity,
         --  which the assembler turns into the site's annotations, with
         --  the copy's own parameters, locals and blocks.  A copy none of
         --  whose code is left, or whose call has no known site, has no
         --  frame to describe.
         procedure Copied_Routine (Site : Positive) is
            Copy : constant Inline_Site :=
              Nth_Inline_Site (Of_Unit, Item, Site);
            Declared : constant Landin.Provenance.Origin :=
              (if Landin.Provenance.Is_Known (Origin_Of (Of_Unit, Copy.Callee))
               then Origin_Of (Of_Unit, Copy.Callee) else Copy.Call);
            Groups : Scope_Vectors.Vector;
         begin
            if not Landin.Provenance.Is_Known (Copy.Call)
              or else not
                (for some B in 1 .. Block_Count (Of_Unit, Item) =>
                   Inlined_At (Of_Unit, Item, Block_Id (B)) = Site
                   and then Length (Of_Unit, Item, Block_Id (B)) > 0)
            then
               return;
            end if;
            declare
               File : constant Natural := Natural (Declared.Source);
               Line : constant Natural := Line_Number (Info, Declared);
               Finish : constant String := Open (S_INLINESITE);
            begin
               --  The parent and the end, which the linker writes.
               Put (HT & ".long 0");
               Put (HT & ".long 0");
               Put (HT & ".long " & N (Function_Type_Of (Copy.Callee)));
               Put (HT & ".cv_inline_linetable "
                 & N (Copy_Identity (Of_Unit, Item, Site)) & " " & N (File)
                 & " " & N (Line) & " " & Symbol (Item) & " "
                 & L ("end", Item));
               Close (Finish);
               if not (for some Each of Inlinees =>
                         Each.Callee = Copy.Callee)
               then
                  Inlinees.Append (Inlinee'(Copy.Callee, File, Line));
               end if;
            end;
            Group_Scopes
              (Item, Site, Signature_Root (Copy.Callee), Groups, False);
            Lexical_Scope (Groups, 1, Site, Is_Root => True);
            Short_Record (S_INLINESITE_END);
         end Copied_Routine;

         Groups : Scope_Vectors.Vector;
         Function_Type : constant Natural := Function_Type_Of (Item);
      begin
         declare
            Section : constant String := Open_Subsection;
            Finish : constant String := Open
              (if Exported (Item) then S_GPROC32_ID else S_LPROC32_ID);
         begin
            Put (HT & ".long 0");
            Put (HT & ".long 0");
            Put (HT & ".long 0");
            Put (HT & ".long " & L ("end", Item) & "-" & Symbol (Item));
            Put (HT & ".long 0");
            Put (HT & ".long 0");
            Put (HT & ".long " & N (Function_Type));
            Put (HT & ".secrel32 " & Symbol (Item));
            Put (HT & ".secidx " & Symbol (Item));
            Put (HT & ".byte 0");
            Name (Routine_Name (Item));
            Close (Finish);
            declare
               Frame_Record : constant String := Open (S_FRAMEPROC);
            begin
               Put (HT & ".long " & I (Long_Long_Integer
                 (Extent (Frame_Plan))));
               Put (HT & ".long 0");
               Put (HT & ".long 0");
               Put (HT & ".long 0");
               Put (HT & ".long 0");
               Put (HT & ".short 0");
               --  The frame register as both the locals' and the
               --  parameters' base.
               Put (HT & ".long " & N (Frame_Register * 16#4000#
                 + Frame_Register * 16#10000#));
               Close (Frame_Record);
            end;
            Group_Scopes (Item, 0, Signature_Root (Item), Groups, True);
            Lexical_Scope (Groups, 1, 0, Is_Root => True);
            Short_Record (S_PROC_ID_END);
            Close_Subsection (Section);
         end;
         Put (HT & ".cv_linetable " & N (Natural (Item)) & ", "
           & Symbol (Item) & ", " & L ("end", Item));
      end Routine;

      --  A module datum lives at its symbol for the whole run; a thread
      --  variable at its offset in each thread's block of the image's
      --  thread storage, which the same section-relative pair locates.
      procedure Module_Datum (Item : Item_Id);
      procedure Module_Datum (Item : Item_Id) is
         Typ : Natural;
         Thread : constant Boolean :=
           In_Thread_Storage (Of_Unit, Facts, Item);
      begin
         if Result_Of (Of_Unit, Item) = Landin.Types.Fixed_Array then
            Typ := Shape_Type (Whole_Array_Shape (Of_Unit, Item));
         elsif Result_Of (Of_Unit, Item) = Landin.Types.Aggregate then
            if Nominal_Of (Of_Unit, Item) = No_Nominal_Type then
               return;
            end if;
            Typ := Shape_Type
              ((Kind => Aggregate_Field_Shape,
                Nominal => Nominal_Of (Of_Unit, Item), others => <>));
         elsif Result_Of (Of_Unit, Item) in Landin.Types.Scalar_Name then
            Typ := Shape_Type
              ((Element => Result_Of (Of_Unit, Item),
                Pointee => Pointee_Of (Of_Unit, Item),
                Atoms => Atom_Set_Of (Of_Unit, Item), others => <>));
         else
            return;
         end if;
         declare
            Finish : constant String :=
              Open (if Thread then
                      (if Exported (Item) then S_GTHREAD32 else S_LTHREAD32)
                    elsif Exported (Item) then S_GDATA32 else S_LDATA32);
         begin
            Put (HT & ".long " & N (Typ));
            Put (HT & ".secrel32 " & Symbol (Item));
            Put (HT & ".secidx " & Symbol (Item));
            Name (Decl_Name (Declares (Of_Unit, Item)));
            Close (Finish);
         end;
      end Module_Datum;

      --  D2481: a routine of the backend's own, the stack switch or
      --  start routine, is a procedure of its symbol's name with no
      --  parameters, lines or variables, so that a debugger names the
      --  frames it holds.
      procedure Own_Routine (Routine_Symbol : String);
      procedure Own_Routine (Routine_Symbol : String) is
         Argument_List : constant Natural := Add (LF_ARGLIST, U32 (0));
         Procedure_Type : constant Natural := Add
           (LF_PROCEDURE, Index_Of (T_VOID) & Byte (0) & Byte (0)
            & U16 (0) & Index_Of (Argument_List));
         Function_Type : constant Natural := Add
           (LF_FUNC_ID, Index_Of (0) & Index_Of (Procedure_Type)
            & Z (Routine_Symbol));
         Section : constant String := Open_Subsection;
         Finish : constant String := Open (S_LPROC32_ID);
      begin
         Put (HT & ".long 0");
         Put (HT & ".long 0");
         Put (HT & ".long 0");
         Put (HT & ".long " & Routine_End (Prefix, Routine_Symbol) & "-"
              & Routine_Symbol);
         Put (HT & ".long 0");
         Put (HT & ".long 0");
         Put (HT & ".long " & N (Function_Type));
         Put (HT & ".secrel32 " & Routine_Symbol);
         Put (HT & ".secidx " & Routine_Symbol);
         Put (HT & ".byte 0");
         Name (Routine_Symbol);
         Close (Finish);
         Short_Record (S_PROC_ID_END);
         Close_Subsection (Section);
      end Own_Routine;

      procedure Bytes (Text : String);
      procedure Bytes (Text : String) is
         Line : US.Unbounded_String;
         Count : Natural := 0;
      begin
         for Each of Text loop
            US.Append (Line, (if Count = 0 then HT & ".byte " else ",")
              & N (Character'Pos (Each)));
            Count := Count + 1;
            if Count = 16 then
               US.Append (Result, US.To_String (Line) & LF);
               Line := US.Null_Unbounded_String;
               Count := 0;
            end if;
         end loop;
         if Count > 0 then
            US.Append (Result, US.To_String (Line) & LF);
         end if;
      end Bytes;
   begin
      --  The object's name and the compiler that wrote it.
      declare
         Section : constant String := Open_Subsection;
         Object : constant String := Open (S_OBJNAME);
      begin
         Put (HT & ".long 0");
         Name ("");
         Close (Object);
         declare
            Compiler : constant String := Open (S_COMPILE3);
         begin
            --  C, as the DWARF description says (D2287), on x64 or
            --  ARM64 (CV_CFL_X64, CV_CFL_ARM64).
            Put (HT & ".long 0");
            Put (HT & (case Landin.Targets.Architecture_Of (Facts) is
                          when Landin.Targets.Arm64 => ".short 0xf6",
                          when others => ".short 0xd0"));
            for Version in 1 .. 8 loop
               Put (HT & ".short 0");
            end loop;
            Name ("Landin refine");
            Close (Compiler);
         end;
         Close_Subsection (Section);
      end;
      for Index in 1 .. Item_Count (Of_Unit) loop
         declare
            Item : constant Item_Id := Item_Id (Index);
         begin
            if Kind_Of (Of_Unit, Item) = Landin.IR.Routine
              and then not Is_External (Of_Unit, Item)
            then
               if Cached_Plan = null then
                  declare
                     Plan : constant Placement :=
                       Make (Of_Unit, Item, Facts, Options);
                     Frame_Plan : constant Frame :=
                       Frame_For (Of_Unit, Item, Facts, Plan, Options);
                  begin
                     Routine (Item, Plan, Frame_Plan);
                  end;
               else
                  Routine
                    (Item, Cached_Plan (Item).all, Cached_Frame (Item).all);
               end if;
            end if;
         end;
      end loop;
      if Stack_Switch /= "" then
         Own_Routine (Stack_Switch);
      end if;
      if Stack_Start /= "" then
         Own_Routine (Stack_Start);
      end if;
      declare
         Section : constant String := Open_Subsection;
      begin
         for Index in 1 .. Item_Count (Of_Unit) loop
            if Kind_Of (Of_Unit, Item_Id (Index)) = Landin.IR.Datum
              and then Declares (Of_Unit, Item_Id (Index)) /= No_Declaration
              and then not Is_External (Of_Unit, Item_Id (Index))
            then
               Module_Datum (Item_Id (Index));
            end if;
         end loop;
         --  The definition of every aggregate a pointer reached, and of
         --  any it reaches in turn.
         while not Wanted.Is_Empty loop
            declare
               Next : constant Description := Wanted.Last_Element;
               Ignored : Natural;
            begin
               Wanted.Delete_Last;
               Ignored := Index_For (Next);
            end;
         end loop;
         --  A named aggregate's name, which `type lookup` finds.
         for Position of Named_Types loop
            declare
               Nominal : constant Nominal_Type_Id :=
                 Nominal_Identities.Nth (Of_Unit, Position);
               Typ : constant Natural := Shape_Type
                 ((Kind => Aggregate_Field_Shape,
                   Nominal => Nominal, others => <>));
               Finish : constant String := Open (S_UDT);
            begin
               Put (HT & ".long " & N (Typ));
               Name (Nominal_Name (Nominal));
               Close (Finish);
            end;
         end loop;
         Close_Subsection (Section);
      end;
      --  Where each routine a copy is of was declared, which a debugger
      --  reads an inline site's routine from.
      if not Inlinees.Is_Empty then
         declare
            Section : constant String :=
              Open_Subsection (DEBUG_S_INLINEELINES);
         begin
            --  CV_INLINEE_SOURCE_LINE_SIGNATURE: no extra files.
            Put (HT & ".long 0");
            for Each of Inlinees loop
               Put (HT & ".long " & N (Function_Type_Of (Each.Callee)));
               Put (HT & ".cv_filechecksumoffset " & N (Each.File));
               Put (HT & ".long " & N (Each.Line));
            end loop;
            Close_Subsection (Section);
         end;
      end if;
      Put (HT & ".cv_filechecksums");
      Put (HT & ".cv_stringtable");

      US.Append (Result, Definitions);
      US.Append (Result, HT & ".section .debug$S,""dr""" & LF
        & HT & ".p2align 2, 0x0" & LF & HT & ".long 4" & LF);
      US.Append (Result, Symbols);
      US.Append (Result, HT & ".section .debug$T,""dr""" & LF
        & HT & ".p2align 2, 0x0" & LF & HT & ".long 4" & LF);
      for Each of Records loop
         Bytes (US.To_String (Each));
      end loop;
      return US.To_String (Result);
   end Sections;

   function Routine_End (Prefix, Symbol : String) return String is
      Spelled : String := Symbol;
   begin
      for Each of Spelled loop
         if Each = '.' then
            Each := '_';
         end if;
      end loop;
      return Prefix & "cv_end_" & Spelled;
   end Routine_End;

end Landin.Backend.Codeview;
