--  D2129: the library names a breaking list removed, each with what
--  replaces it.  R20's list (roadmap/inputs/breaking-list.md, D1948 to
--  D2051) renamed, merged and reshaped library declarations; a program
--  that still writes an old name is refused naming the new one, and
--  where the rewrite is mechanical the refusal carries it as one exact
--  fix (D1847).  The library declares only the new forms, so the old
--  ones are known here and nowhere else.
--
--  A row is looked up only once a qualified name, a field or an entry has
--  failed to resolve, so a name the library still declares never reaches
--  it, and a program's own declaration of an old name is its own.

package Landin.Modules.Removed is

   --  How a use of the old name becomes the new one.
   type Rewrite is
     (Rename,        --  the name is replaced, its module's import added
      Swap_First,    --  renamed, and the call's first two arguments swap
      Leaves_Of,     --  `count_leaves(v, id)`: `leaves(get(v, id))`
      By_Hand);      --  the use changes shape; the note says how

   type Row is private;
   No_Row : constant Row;

   --  The row for the public declaration Name of the module whose logical
   --  path is Module, or No_Row when no list removed it.
   function Member (Module, Name : String) return Row;

   --  The row for the field or concept entry Name of the type or concept
   --  Owner declared by Module, or No_Row.
   function Field (Module, Owner, Name : String) return Row;

   function Found (Item : Row) return Boolean;

   --  Where the replacement is declared: a logical module path, and the
   --  name.  Empty for By_Hand.
   function New_Module (Item : Row) return String
     with Pre => Found (Item);
   function New_Name (Item : Row) return String
     with Pre => Found (Item);

   function How (Item : Row) return Rewrite
     with Pre => Found (Item);

   --  The decision that removed it and what to write, as a note's text:
   --  "D2032: `mem.free` is `mem.release`".  For By_Hand, what to do.
   function Note (Item : Row) return String
     with Pre => Found (Item);

private

   type Row is record
      Index : Natural := 0;
      Field : Boolean := False;
   end record;

   No_Row : constant Row := (Index => 0, Field => False);

end Landin.Modules.Removed;
