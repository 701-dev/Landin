--  The import a qualified name that resolved to nothing was missing.
--
--  A prefix that names nothing in its file is a misspelling, unless the
--  module it would name is one the file could import (D2174).  Two such
--  modules are known without asking the host: the one another file of
--  the same module imports under that name, since [1450] gives every file
--  its own imports, and the one library module the program reaches whose
--  last segment is that name, or, when the program reaches none, the one
--  library module the driver listed with that name (D2994), since only
--  the driver reads the library's directories.  The resolver asks for a
--  prefix in a value position and the checker for one in a type position;
--  both say what this answers, and the first such prefix in the file
--  carries the import as an exact fix, so that the fixes of one file never
--  add it twice.

with Ada.Strings.Unbounded;

with Landin.Diagnostics;
with Landin.Source;
with Landin.Source.Names;
with Landin.Syntax;

package Landin.Stages.Wanted_Imports is

   type Answer is record
      --  The import the file is missing, `core/mem` or `x as mem`, or
      --  empty when neither rule names one.
      Import  : Ada.Strings.Unbounded.Unbounded_String;
      --  The other file of the module that imports the name, or No_Source
      --  when the module is a library module the file could import.
      Sibling : Landin.Source.Source_Id := Landin.Source.No_Source;
   end record;

   function Found (Item : Answer) return Boolean
     is (Ada.Strings.Unbounded.Length (Item.Import) > 0);

   function Import_Of (Item : Answer) return String
     is (Ada.Strings.Unbounded.To_String (Item.Import));

   --  What Node, a name that resolved to nothing, was missing.  Only a
   --  name written as the prefix of a qualified name is asked, since a
   --  module name is used only that way.
   function Wanted
     (Context : aliased in out Compilation;
      Of_Tree : Landin.Syntax.Tree;
      Node    : Landin.Syntax.Node_Id) return Answer;

   --  The file name a note shows for Sibling: its last path segment.
   function File_Name
     (Context : aliased in out Compilation;
      Sibling : Landin.Source.Source_Id) return String;

   --  The note an unresolved prefix Name gets when Item was found: the
   --  sibling file that imports it, or the library module it names.
   function Note
     (Context : aliased in out Compilation;
      Name    : String;
      Item    : Answer) return String
     with Pre => Found (Item);

   --  The import as an exact fix when Node is the first prefix spelled
   --  Named in its file among Kinds, and none otherwise.  After the
   --  file's last import, or at its start when it has none.
   type Prefix_Kinds is array (Landin.Syntax.Node_Kind) of Boolean;

   function Import_Fixes
     (Of_Tree : Landin.Syntax.Tree;
      Node    : Landin.Syntax.Node_Id;
      Named   : Landin.Source.Names.Name_Id;
      Kinds   : Prefix_Kinds;
      Item    : Answer) return Landin.Diagnostics.Fix_List;

end Landin.Stages.Wanted_Imports;
