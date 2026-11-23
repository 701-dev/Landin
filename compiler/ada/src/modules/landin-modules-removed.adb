with Ada.Strings.Fixed;
with Ada.Strings.Unbounded;

package body Landin.Modules.Removed is

   use Ada.Strings.Unbounded;

   function "+" (Item : String) return Unbounded_String
     renames To_Unbounded_String;

   type Entry_Row is record
      Module     : Unbounded_String;
      Owner      : Unbounded_String;  --  a field's type or concept
      Name       : Unbounded_String;
      New_Module : Unbounded_String;
      New_Name   : Unbounded_String;
      How        : Rewrite;
      Decision   : Unbounded_String;
      Advice     : Unbounded_String;  --  By_Hand: what to write
   end record;

   function R
     (Module, Name, New_Module, New_Name, Decision : String;
      How : Rewrite := Rename) return Entry_Row
   is (Module => +Module, Owner => Null_Unbounded_String, Name => +Name,
       New_Module => +New_Module, New_Name => +New_Name, How => How,
       Decision => +Decision, Advice => Null_Unbounded_String);

   --  A rename whose note is Advice rather than "old is new".
   function A
     (Module, Name, New_Module, New_Name, Decision, Advice : String)
      return Entry_Row
   is (Module => +Module, Owner => Null_Unbounded_String, Name => +Name,
       New_Module => +New_Module, New_Name => +New_Name, How => Rename,
       Decision => +Decision, Advice => +Advice);

   function H (Module, Name, Decision, Advice : String) return Entry_Row
   is (Module => +Module, Owner => Null_Unbounded_String, Name => +Name,
       New_Module => Null_Unbounded_String,
       New_Name => Null_Unbounded_String, How => By_Hand,
       Decision => +Decision, Advice => +Advice);

   function F
     (Module, Owner, Name, New_Name, Decision : String) return Entry_Row
   is (Module => +Module, Owner => +Owner, Name => +Name,
       New_Module => +Module, New_Name => +New_Name, How => Rename,
       Decision => +Decision, Advice => Null_Unbounded_String);

   --  R20's breaking list, by its sections, a module's members first.
   --  The first is how a capability is received (D1954): D2128 renamed
   --  the one reorder that left old calls well typed.
   Members : constant array (Positive range <>) of Entry_Row :=
     [R ("core/mem", "transfer_prefix", "core/mem", "copy_prefix",
         "D2128", Swap_First),
      --  Layers (D2008)
      R ("platform/posix", "internet_address", "hosted/system",
         "internet_address", "D2008"),
      R ("platform/posix", "address_of", "hosted/system", "address_of",
         "D2008"),
      R ("platform/posix", "reason", "hosted/system", "reason", "D2008"),
      --  Absence (D2028)
      R ("core/map", "missing", "core/mem", "not_found", "D2028"),
      R ("core/tree", "no_such_node", "core/mem", "not_found", "D2028"),
      R ("core/io", "not_found", "core/mem", "not_found", "D2028"),
      R ("core/text", "not_found", "core/mem", "not_found", "D2028"),
      R ("core/io", "no_argument", "core/mem", "not_found", "D2028"),
      R ("core/io", "no_variable", "core/mem", "not_found", "D2028"),
      R ("platform/posix", "no_account", "core/mem", "not_found", "D2028"),
      R ("platform/posix", "no_symbol", "core/mem", "not_found", "D2028"),
      R ("core/text", "past_end", "core/mem", "out_of_bounds", "D2028"),
      --  Running out of room (D2029)
      R ("core/mem", "full", "core/mem", "out_of_memory", "D2029"),
      R ("core/text", "no_space", "core/mem", "out_of_memory", "D2029"),
      R ("core/io", "line_too_long", "core/mem", "out_of_memory", "D2029"),
      --  The end of an iteration (D2030)
      H ("core/map", "end_of_entries", "D2030",
         "`map.next_entry` no longer fails at the end of the walk; ask"
         & " `map.at_end(value, position)` before taking the next entry,"
         & " or walk the map with `for entry in value`"),
      R ("core/text", "done", "core/text", "utf8_at_end", "D2030"),
      --  A length (D2031)
      R ("core/io", "argument_count", "core/io", "arguments_length",
         "D2031"),
      R ("core/io", "variable_count", "core/io", "variables_length",
         "D2031"),
      R ("core/io", "pending", "core/io", "buffered_length", "D2031"),
      R ("core/arena", "used", "core/arena", "length", "D2031"),
      R ("core/text", "width", "core/text", "scalar_length", "D2031"),
      R ("core/tree", "count_leaves", "core/tree", "leaves", "D2031",
         Leaves_Of),
      --  Giving storage back, and closing (D2032)
      R ("core/mem", "free", "core/mem", "release", "D2032"),
      R ("core/mem", "new", "core/mem", "allocate_item", "D2032"),
      R ("core/mem", "delete", "core/mem", "release_item", "D2032"),
      R ("core/mem", "new_bytes", "core/mem", "allocate_bytes", "D2032"),
      R ("core/mem", "delete_bytes", "core/mem", "release_bytes", "D2032"),
      R ("core/mem", "dispose", "core/mem", "detach", "D2032"),
      R ("core/arena", "reset", "core/arena", "release", "D2032"),
      R ("core/net", "close_socket", "core/net", "close", "D2032"),
      --  `host` (D2033)
      R ("core/text", "host_string", "core/text", "os_string", "D2033"),
      R ("core/text", "host_over", "core/text", "os_string_over", "D2033"),
      R ("core/text", "host_bytes", "core/text", "os_string_bytes",
         "D2033"),
      R ("core/text", "host_equal", "core/text", "os_string_equal",
         "D2033"),
      R ("core/text", "from_host", "core/text", "from_os_string", "D2033"),
      R ("core/text", "append_host", "core/text", "append_os_string",
         "D2033"),
      R ("core/text", "host_variable", "core/text", "os_variable", "D2033"),
      --  Names with one meaning each (D2034)
      R ("core/io", "argument_at", "core/io", "argument", "D2034"),
      R ("core/io", "variable_at", "core/io", "variable", "D2034"),
      R ("core/fibre", "space", "core/fibre", "record", "D2034"),
      R ("core/map", "cursor", "core/map", "position", "D2034"),
      R ("core/text", "cursor", "core/text", "from_offset", "D2034"),
      --  Concepts (D2050)
      H ("core/io", "writer_of", "D2050",
         "an `any io.world` converts to `any io.writer`; pass the world"
         & " itself where a writer is wanted"),
      H ("core/io", "lent_writer", "D2050",
         "an `any io.world` converts to `any io.writer`; pass the world"
         & " itself where a writer is wanted")];

   --  Fields of a library type, and entries of a library concept.
   Fields : constant array (Positive range <>) of Entry_Row :=
     [F ("core/io", "line", "finished", "at_end", "D2030"),
      F ("core/io", "directory", "finished", "at_end", "D2030"),
      F ("core/io", "directory", "cursor", "consumed", "D2034"),
      F ("core/io", "process", "argument_count", "arguments_length",
         "D2031"),
      F ("core/io", "environment", "variable_count", "variables_length",
         "D2031"),
      F ("core/io", "environment", "variable_at", "variable", "D2034"),
      F ("core/net", "network", "close_socket", "close", "D2032")];

   --  Parameters a routine kept and the list renamed, by the routine, and
   --  the label a call wrote: D2034's `entries`, now `fibres`.
   Labels : constant array (Positive range <>) of Entry_Row :=
     [F ("core/fibre/stacks", "round_over", "entries", "fibres", "D2034"),
      F ("hosted/events", "over", "entries", "fibres", "D2034")];

   --  A type the list moved whose old name now means something that is no
   --  type (D2008, D2033): the record `io.variable` was is
   --  `text.os_variable`, and `io.variable` is the routine that lends one.
   Types : constant array (Positive range <>) of Entry_Row :=
     [1 => A ("core/io", "variable", "core/text", "os_variable", "D2033",
              "the record of an environment variable is `text.os_variable`;"
              & " `io.variable` lends the variable at an index")];

   --  A routine that now takes a narrower argument, whose wider form the
   --  list moved to another (D2008): `posix.words` words an errno alone,
   --  and `system.words` a library atom as well.
   Narrowings : constant array (Positive range <>) of Entry_Row :=
     [1 => A ("platform/posix", "words", "hosted/system", "words", "D2008",
              "`system.words` of `hosted/system` words an errno or a library"
              & " atom")];

   --  D2180: the routines and the entry D1954 reordered under their own
   --  names, as R20's breaking list gives them.  Each letter is the kind
   --  of value at a moved position, in the old order: S a struct, L a
   --  slice or an array lent as one, E an erased `any` value and I an
   --  integer.  Goes gives the new place of each old position.
   type Order_Row is record
      Module   : Unbounded_String;
      Owner    : Unbounded_String;
      Name     : Unbounded_String;
      Shapes   : Unbounded_String;
      Goes     : Unbounded_String;
      Decision : Unbounded_String;
      Advice   : Unbounded_String;
   end record;

   function O (Module, Owner, Name, Shapes, Goes, Decision, Advice : String)
      return Order_Row
   is (Module => +Module, Owner => +Owner, Name => +Name,
       Shapes => +Shapes, Goes => +Goes, Decision => +Decision,
       Advice => +Advice);

   Orders : constant array (Positive range <>) of Order_Row :=
     [O ("core/mem", "", "transfer", "SIS", "231", "D1954",
         "`mem.transfer` takes the target first, then the source and the"
         & " index, as `mem.copy` takes `into` first"),
      O ("core/random", "", "shuffle", "SL", "21", "D1954",
         "`random.shuffle` takes the values first and the generator"
         & " second"),
      O ("core/fibre/stacks", "", "round_over", "LE", "21", "D1954",
         "`stacks.round_over` takes the state, then `when_idle`, then the"
         & " fibres; a capability comes before the inputs"),
      O ("core/io/fake", "", "network_over_turns", "LE", "21", "D1954",
         "`fake.network_over_turns` takes the state, then `runs`, then the"
         & " sockets; a capability comes before the inputs"),
      O ("core/io", "file_system", "make_temporary", "SEL", "213", "D1954",
         "`make_temporary` of `io.file_system` takes `names` before"
         & " `directory`, then `into`; a capability comes before the inputs")];

   function Member (Module, Name : String) return Row is
   begin
      for Index in Members'Range loop
         if To_String (Members (Index).Module) = Module
           and then To_String (Members (Index).Name) = Name
         then
            return (Index => Index, Table => Members_Table);
         end if;
      end loop;
      return No_Row;
   end Member;

   function Field (Module, Owner, Name : String) return Row is
   begin
      for Index in Fields'Range loop
         if To_String (Fields (Index).Module) = Module
           and then To_String (Fields (Index).Owner) = Owner
           and then To_String (Fields (Index).Name) = Name
         then
            return (Index => Index, Table => Fields_Table);
         end if;
      end loop;
      return No_Row;
   end Field;

   function Label (Module, Name, Label : String) return Row is
   begin
      for Index in Labels'Range loop
         if To_String (Labels (Index).Module) = Module
           and then To_String (Labels (Index).Owner) = Name
           and then To_String (Labels (Index).Name) = Label
         then
            return (Index => Index, Table => Labels_Table);
         end if;
      end loop;
      return No_Row;
   end Label;

   function Type_Member (Module, Name : String) return Row is
   begin
      for Index in Types'Range loop
         if To_String (Types (Index).Module) = Module
           and then To_String (Types (Index).Name) = Name
         then
            return (Index => Index, Table => Types_Table);
         end if;
      end loop;
      return No_Row;
   end Type_Member;

   function Narrowed (Module, Name : String) return Row is
   begin
      for Index in Narrowings'Range loop
         if To_String (Narrowings (Index).Module) = Module
           and then To_String (Narrowings (Index).Name) = Name
         then
            return (Index => Index, Table => Narrowed_Table);
         end if;
      end loop;
      return No_Row;
   end Narrowed;

   function Found (Item : Row) return Boolean is (Item.Index /= 0);

   function Get (Item : Row) return Entry_Row
   is (case Item.Table is
          when Members_Table  => Members (Item.Index),
          when Fields_Table   => Fields (Item.Index),
          when Labels_Table   => Labels (Item.Index),
          when Types_Table    => Types (Item.Index),
          when Narrowed_Table => Narrowings (Item.Index));

   function New_Module (Item : Row) return String
   is (To_String (Get (Item).New_Module));

   function New_Name (Item : Row) return String
   is (To_String (Get (Item).New_Name));

   function How (Item : Row) return Rewrite is (Get (Item).How);

   --  The last segment of a logical path: the name a plain import binds.
   function Short (Path : String) return String;
   function Short (Path : String) return String is
      Slash : constant Natural :=
        Ada.Strings.Fixed.Index (Path, "/", Ada.Strings.Backward);
   begin
      return Path (Slash + 1 .. Path'Last);
   end Short;

   function Note (Item : Row) return String is
      This : constant Entry_Row := Get (Item);
      Old  : constant String :=
        (if Item.Table in Fields_Table | Labels_Table
         then Short (To_String (This.Module)) & "." & To_String (This.Owner)
              & "'s `" & To_String (This.Name) & "`"
         else "`" & Short (To_String (This.Module)) & "."
              & To_String (This.Name) & "`");
   begin
      case This.How is
         when By_Hand =>
            return To_String (This.Decision) & ": " & Old
              & " was removed; " & To_String (This.Advice);
         when Rename =>
            case Item.Table is
               when Types_Table | Narrowed_Table =>
                  return To_String (This.Decision) & ": "
                    & To_String (This.Advice);
               when Members_Table | Fields_Table | Labels_Table =>
                  null;
            end case;
            return To_String (This.Decision) & ": " & Old & " is "
              & (if Item.Table in Fields_Table | Labels_Table
                 then "`" & To_String (This.New_Name) & "`"
                 else "`" & Short (To_String (This.New_Module)) & "."
                      & To_String (This.New_Name) & "`");
         when Swap_First =>
            return To_String (This.Decision) & ": " & Old & " is `"
              & Short (To_String (This.New_Module)) & "."
              & To_String (This.New_Name)
              & "`, which takes the target first and the source second";
         when Leaves_Of =>
            return To_String (This.Decision) & ": " & Old
              & " was removed; a node's leaves are `"
              & Short (To_String (This.New_Module)) & ".leaves("
              & Short (To_String (This.New_Module)) & ".get(value, id))`";
      end case;
   end Note;

   function Reordered (Module, Owner, Name : String) return Order is
   begin
      for Index in Orders'Range loop
         if To_String (Orders (Index).Module) = Module
           and then To_String (Orders (Index).Owner) = Owner
           and then To_String (Orders (Index).Name) = Name
         then
            return (Index => Index);
         end if;
      end loop;
      return No_Order;
   end Reordered;

   function Reordered_Entry (Module, Name : String) return Order is
   begin
      for Index in Orders'Range loop
         if To_String (Orders (Index).Module) = Module
           and then Length (Orders (Index).Owner) > 0
           and then To_String (Orders (Index).Name) = Name
         then
            return (Index => Index);
         end if;
      end loop;
      return No_Order;
   end Reordered_Entry;

   function Found (Item : Order) return Boolean is (Item.Index /= 0);

   function Moved (Item : Order) return Positive
   is (Length (Orders (Item.Index).Shapes));

   function Shape_Of (Letter : Character) return Shape
   is (case Letter is
          when 'S' => Struct_Shape,
          when 'L' => Slice_Shape,
          when 'E' => Erased_Shape,
          when others => Integer_Shape);

   function Old_Shape (Item : Order; Position : Positive) return Shape
   is (Shape_Of (Element (Orders (Item.Index).Shapes, Position)));

   function Goes_To (Item : Order; Position : Positive) return Positive
   is (Character'Pos (Element (Orders (Item.Index).Goes, Position))
       - Character'Pos ('0'));

   function New_Shape (Item : Order; Position : Positive) return Shape is
   begin
      for Old in 1 .. Moved (Item) loop
         if Goes_To (Item, Old) = Position then
            return Old_Shape (Item, Old);
         end if;
      end loop;
      raise Program_Error with "a reorder leaves a position empty";
   end New_Shape;

   function Note (Item : Order) return String
   is (To_String (Orders (Item.Index).Decision) & ": "
       & To_String (Orders (Item.Index).Advice));

end Landin.Modules.Removed;
