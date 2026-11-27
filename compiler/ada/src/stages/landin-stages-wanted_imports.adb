with Landin.Diagnostics.Fixes;
with Landin.Modules;
with Landin.Resolution;

package body Landin.Stages.Wanted_Imports is

   package Syn renames Landin.Syntax;
   package Res renames Landin.Resolution;
   package Unbounded renames Ada.Strings.Unbounded;

   use type Landin.Modules.Module_Id;
   use type Landin.Source.Byte_Offset;
   use type Landin.Source.Source_Id;
   use type Landin.Source.Names.Name_Id;
   use type Syn.Node_Id;
   use type Syn.Node_Kind;

   function Last_Segment (Path : String) return String;

   function Last_Segment (Path : String) return String is
   begin
      for Index in reverse Path'Range loop
         if Path (Index) = '/' then
            return Path (Index + 1 .. Path'Last);
         end if;
      end loop;
      return Path;
   end Last_Segment;

   function First_Segment (Path : String) return String;

   function First_Segment (Path : String) return String is
   begin
      for Index in Path'Range loop
         if Path (Index) = '/' then
            return Path (Path'First .. Index - 1);
         end if;
      end loop;
      return Path;
   end First_Segment;

   function Is_Prefix
     (Of_Tree : Syn.Tree; Node : Syn.Node_Id) return Boolean;

   function Is_Prefix
     (Of_Tree : Syn.Tree; Node : Syn.Node_Id) return Boolean
   is
      Outer : constant Syn.Node_Id := Syn.Enclosing (Of_Tree, Node);
   begin
      return Outer /= Syn.No_Node
        and then Syn.Kind (Of_Tree, Outer) = Syn.Member_Selection
        and then Syn.Target_Of (Of_Tree, Outer) = Node;
   end Is_Prefix;

   function Wanted
     (Context : aliased in out Compilation;
      Of_Tree : Landin.Syntax.Tree;
      Node    : Landin.Syntax.Node_Id) return Answer
   is
      Meanings : constant not null access Landin.Resolution.Table :=
        Landin.Stages.Meanings (Context);
      Graph : constant not null access Landin.Modules.Table :=
        Landin.Stages.Modules (Context);
      Here : constant Landin.Source.Source_Id := Syn.Source_Of (Of_Tree);
      Named : constant Landin.Source.Names.Name_Id :=
        Syn.Name (Of_Tree, Node);
      Spelling : constant String :=
        (if Named = Landin.Source.Names.No_Name then ""
         else Landin.Source.Names.Spelling
                (Landin.Stages.Identities (Context).all, Named));
      Module : constant Landin.Modules.Module_Id :=
        Landin.Modules.Module_Of (Graph.all, Here);
      Result : Answer;
   begin
      if Spelling = "" or else not Is_Prefix (Of_Tree, Node) then
         return Result;
      end if;

      --  D2174: another file of this module imports the name.
      for Index in 1 .. Landin.Modules.Source_Count (Graph.all) loop
         declare
            Other : constant Landin.Source.Source_Id :=
              Landin.Source.Source_Id (Index);
            Target : Landin.Modules.Module_Id;
         begin
            if Other /= Here
              and then Landin.Modules.Module_Of (Graph.all, Other) = Module
              and then Res.Has_Import (Meanings.all, Other, Named)
            then
               Target := Res.Imported_Module_Of (Meanings.all, Other, Named);
               if Target /= Landin.Modules.No_Module then
                  declare
                     Path : constant String :=
                       Landin.Modules.Logical_Path (Graph.all, Target);
                  begin
                     Result.Import := Unbounded.To_Unbounded_String
                       (if Last_Segment (Path) = Spelling then Path
                        else Path & " as " & Spelling);
                     Result.Sibling := Other;
                     return Result;
                  end;
               end if;
            end if;
         end;
      end loop;

      --  D2174: exactly one library module the program reaches has the
      --  name as its last segment, and this file imports it under no name.
      declare
         Chosen : Landin.Modules.Module_Id := Landin.Modules.No_Module;
         Count  : Natural := 0;
         Imported_Already : Boolean := False;

         procedure Visit
           (Name : Landin.Source.Names.Name_Id;
            Imported : Landin.Modules.Module_Id);

         procedure Visit
           (Name : Landin.Source.Names.Name_Id;
            Imported : Landin.Modules.Module_Id)
         is
            pragma Unreferenced (Name);
         begin
            if Imported = Chosen then
               Imported_Already := True;
            end if;
         end Visit;
      begin
         for Index in 1 .. Landin.Modules.Module_Count (Graph.all) loop
            declare
               Id : constant Landin.Modules.Module_Id :=
                 Landin.Modules.Module_Id (Index);
               Path : constant String :=
                 Landin.Modules.Logical_Path (Graph.all, Id);
            begin
               if First_Segment (Path) in "core" | "hosted" | "platform"
                 and then Last_Segment (Path) = Spelling
               then
                  Chosen := Id;
                  Count := Count + 1;
               end if;
            end;
         end loop;
         if Count = 1 then
            Res.Each_Imported_Module
              (Meanings.all, Res.File_Scope_Of (Meanings.all, Here),
               Visit'Access);
            if not Imported_Already then
               Result.Import := Unbounded.To_Unbounded_String
                 (Landin.Modules.Logical_Path (Graph.all, Chosen));
            end if;
            return Result;
         elsif Count > 1 then
            return Result;
         end if;
      end;

      --  SR-1693: no module the program reaches has the name, and exactly
      --  one module of the library the driver listed has it; nothing
      --  imports that one, since the program would reach it otherwise.
      declare
         Chosen : Unbounded.Unbounded_String;
         Count  : Natural := 0;
      begin
         for Index in 1 .. Landin.Stages.Library_Module_Count (Context) loop
            declare
               Path : constant String :=
                 Landin.Stages.Nth_Library_Module (Context, Index);
            begin
               if Last_Segment (Path) = Spelling then
                  Chosen := Unbounded.To_Unbounded_String (Path);
                  Count := Count + 1;
               end if;
            end;
         end loop;
         if Count = 1 then
            Result.Import := Chosen;
         end if;
      end;
      return Result;
   end Wanted;

   function File_Name
     (Context : aliased in out Compilation;
      Sibling : Landin.Source.Source_Id) return String is
   begin
      return Last_Segment
        (Landin.Source.Name
           (Landin.Stages.Source (Context, Sibling).Element.all));
   end File_Name;

   function Note
     (Context : aliased in out Compilation;
      Name    : String;
      Item    : Answer) return String
     is (if Item.Sibling /= Landin.Source.No_Source
         then "[1450]: each file of a module has its own imports, and `"
              & File_Name (Context, Item.Sibling) & "` imports `" & Name
              & "` where this file does not; add `import "
              & Import_Of (Item) & "` here"
         else "[1420]: `" & Name & "` is the library module `"
              & Import_Of (Item) & "`, which this file does not import;"
              & " add `import " & Import_Of (Item) & "`");

   function Import_Fixes
     (Of_Tree : Landin.Syntax.Tree;
      Node    : Landin.Syntax.Node_Id;
      Named   : Landin.Source.Names.Name_Id;
      Kinds   : Prefix_Kinds;
      Item    : Answer) return Landin.Diagnostics.Fix_List
   is
      First : Syn.Node_Id := Syn.No_Node;
      Count : constant Natural := Syn.Import_Count (Of_Tree);
   begin
      if not Found (Item) then
         return Landin.Diagnostics.No_Fixes;
      end if;
      for Each in 1 .. Syn.Last_Node (Of_Tree) loop
         if Kinds (Syn.Kind (Of_Tree, Each))
           and then Syn.Name (Of_Tree, Each) = Named
           and then Is_Prefix (Of_Tree, Each)
           and then
             (First = Syn.No_Node
              or else Syn.Where (Of_Tree, Each).First
                < Syn.Where (Of_Tree, First).First)
         then
            First := Each;
         end if;
      end loop;
      if First /= Node then
         return Landin.Diagnostics.No_Fixes;
      end if;
      if Count = 0 then
         return [1 => Landin.Diagnostics.Fixes.Add_Import
                   (Syn.Source_Of (Of_Tree), (First => 0, Last => 0),
                    "import " & Import_Of (Item) & [ASCII.LF],
                    Import_Of (Item))];
      end if;
      declare
         At_End : constant Landin.Source.Byte_Offset :=
           Syn.Where (Of_Tree, Syn.Nth_Import (Of_Tree, Count)).Last;
      begin
         return [1 => Landin.Diagnostics.Fixes.Add_Import
                   (Syn.Source_Of (Of_Tree), (First => At_End, Last => At_End),
                    [ASCII.LF] & "import " & Import_Of (Item),
                    Import_Of (Item))];
      end;
   end Import_Fixes;

end Landin.Stages.Wanted_Imports;
