--  D2129: the library names a breaking list removed, each with what
--  replaces it.  R20's breaking list (D1948 to D2051) renamed, merged
--  and reshaped library declarations; a program that still writes an old
--  name is refused naming the new one, and where the rewrite is
--  mechanical the refusal carries it as one exact fix (D1847).  The
--  library declares only the new forms, so the old ones are known here
--  and nowhere else.
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

   --  The row for the label Label of a call of the routine Name of
   --  Module, where the list renamed that parameter, or No_Row.
   function Label (Module, Name, Label : String) return Row;

   --  The row for Name of Module written where a type belongs, where the
   --  list moved the type away and Name now means something else
   --  (`io.variable`, now a routine), or No_Row.
   function Type_Member (Module, Name : String) return Row;

   --  The row for the routine Name of Module given an argument wider than
   --  it now takes, where the list moved the wider form to another
   --  routine (`posix.words` of a library atom), or No_Row.
   function Narrowed (Module, Name : String) return Row;

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

   --  D2180: a routine or concept entry the list reordered under its own
   --  name (D1954).  A call in the old order is told apart by the kind of
   --  value at each position, which is all a refusal before the call's
   --  own matching can see.
   type Order is private;
   No_Order : constant Order;

   --  The reordered routine Name of Module when Owner is "", else the
   --  entry Name of the concept Owner that Module declares; or No_Order.
   function Reordered (Module, Owner, Name : String) return Order;

   --  The reordered entry Name of a concept Module declares, whichever
   --  concept: a call through a provider names the entry and not its
   --  concept.  No_Order when there is none.
   function Reordered_Entry (Module, Name : String) return Order;

   function Found (Item : Order) return Boolean;

   --  The kinds of value a reordered position holds.
   type Shape is (Struct_Shape, Slice_Shape, Erased_Shape, Integer_Shape);

   --  How many of the call's last arguments the reorder moves; any before
   --  them, an entry's provider, keep their places.
   function Moved (Item : Order) return Positive
     with Pre => Found (Item);

   --  What the old order puts at Position among the moved arguments.
   function Old_Shape (Item : Order; Position : Positive) return Shape
     with Pre => Found (Item) and then Position <= Moved (Item);

   --  What the new order puts there.
   function New_Shape (Item : Order; Position : Positive) return Shape
     with Pre => Found (Item) and then Position <= Moved (Item);

   --  Where the argument the old order puts at Position goes.
   function Goes_To (Item : Order; Position : Positive) return Positive
     with Pre => Found (Item) and then Position <= Moved (Item);

   --  The decision and the new order, as a note's text.
   function Note (Item : Order) return String
     with Pre => Found (Item);

private

   type Table_Kind is (Members_Table, Fields_Table, Labels_Table,
                       Types_Table, Narrowed_Table);

   type Row is record
      Index : Natural := 0;
      Table : Table_Kind := Members_Table;
   end record;

   No_Row : constant Row := (Index => 0, Table => Members_Table);

   type Order is record
      Index : Natural := 0;
   end record;

   No_Order : constant Order := (Index => 0);

end Landin.Modules.Removed;
