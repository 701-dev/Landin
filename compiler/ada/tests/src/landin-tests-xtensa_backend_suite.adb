with Ada.Strings.Fixed;
with Ada.Strings.Unbounded;
with Landin.Backend.Xtensa;
with Landin.Backend.Xtensa_Machine;
with Landin.Backend.Site_Counts;
with Landin.Build_Reports;
with Landin.Optimization;
with Landin.Source;
with Landin.Stages.Checking;
with Landin.Stages.Configuration;
with Landin.Stages.Lowering;
with Landin.Stages.Resolution;
with Landin.Stages.Syntax;
with Landin.Targets;

package body Landin.Tests.Xtensa_Backend_Suite is
   package U renames Ada.Strings.Unbounded;
   LF : constant Character := ASCII.LF;
   use type Landin.Source.Source_Id;

   Frontend : aliased Landin.Stages.Syntax.Instance;
   Configurer : aliased Landin.Stages.Configuration.Instance;
   Resolver : aliased Landin.Stages.Resolution.Instance;
   Checker : aliased Landin.Stages.Checking.Instance;
   Lowerer : aliased Landin.Stages.Lowering.Instance;

   function Contains (Text, Part : String) return Boolean
     is (Ada.Strings.Fixed.Index (Text, Part) > 0);

   --  The build report of the source Emitted last wrote.
   Last_Report : Landin.Build_Reports.Report;

   function Emitted
     (Item : in out Landin.Testing.Context; Source : String;
      Options : Landin.Optimization.Options :=
        Landin.Optimization.Reference_Options) return String;
   function Emitted
     (Item : in out Landin.Testing.Context; Source : String;
      Options : Landin.Optimization.Options :=
        Landin.Optimization.Reference_Options) return String
   is
      Work : Landin.Stages.Compilation :=
        Landin.Stages.Create (Landin.Targets.Xtensa);
      Order : Landin.Stages.Pipeline;
      Written : constant Landin.Source.Source_Id :=
        Landin.Stages.Add_Source (Work, "xtensa.ldn", Source);
      Text : U.Unbounded_String;
      Report : Landin.Build_Reports.Report;
      Ran : Natural;
   begin
      pragma Assert (Written /= Landin.Source.No_Source);
      Landin.Stages.Append (Order, Frontend'Access);
      Landin.Stages.Append (Order, Configurer'Access);
      Landin.Stages.Append (Order, Resolver'Access);
      Landin.Stages.Append (Order, Checker'Access);
      Landin.Stages.Append (Order, Lowerer'Access);
      Ran := Landin.Stages.Run (Order, Work);
      Landin.Testing.Check_Equal (Item, Ran, 5, "five stages ran");
      Landin.Testing.Check
        (Item, not Landin.Stages.Failed (Work), "Xtensa source checks");
      if Landin.Stages.Failed (Work) then return ""; end if;
      Landin.Backend.Xtensa.Emit
        (Landin.Stages.Code (Work).all,
         Landin.Stages.Meanings (Work).all,
         Landin.Stages.Identities (Work).all,
         Landin.Stages.Target (Work),
         Options, Text, Report);
      Last_Report := Report;
      return U.To_String (Text);
   end Emitted;

   --  End-to-end selection, including helper ABI boundaries. Execution of
   --  these operations belongs to both chips' freestanding corpus lanes.
   procedure Windowed_Pairs (Item : in out Landin.Testing.Context);
   procedure Windowed_Pairs (Item : in out Landin.Testing.Context) is
      Text : constant String := Emitted
        (Item,
         "wide: (a: u64, b: u64) -> (r: u64) =" & LF
         & "    r = (a * b) / b" & LF
         & "end wide" & LF
         & "float_add: (a: f64, b: f64) -> (r: f64) =" & LF
         & "    r = a + b" & LF
         & "end float_add" & LF
         & "caller: () -> (r: u64) =" & LF
         & "    r = wide(12, 3)" & LF
         & "end caller" & LF);
   begin
      Landin.Testing.Check
        (Item, Contains (Text, "entry a1, ")
           and then Contains (Text, "retw")
           and then Contains (Text, "mov a7, a1"),
         "all framed routines use the windowed convention and fixed base");
      Landin.Testing.Check
        (Item, Contains (Text, "muluh ")
           and then Contains (Text, "call8 __udivdi3")
           and then Contains (Text, "call8 __adddf3"),
         "wide integer and software float operations retain native helpers");
      Landin.Testing.Check
        (Item, not Contains (Text, "call0")
           and then not Contains (Text, "(sp)")
           and then not Contains (Text, ".option "),
         "the assembler receives only Xtensa instructions and directives");
   end Windowed_Pairs;

   procedure Assembly_Snapshots (Item : in out Landin.Testing.Context);
   procedure Assembly_Snapshots (Item : in out Landin.Testing.Context) is
      Text : constant String := Emitted
        (Item,
         "f: (v: u32) -> (r: u32) =" & LF
         & "    r = assembler.block(""add {r}, {v}, {v}""," & LF
         & "        in v: u32 at a10 = v, out r: u32 at a8," & LF
         & "        out _ at a9)" & LF
         & "end f" & LF);
   begin
      Landin.Testing.Check
        (Item, Contains (Text, "add a8, a10, a10")
           and then Contains (Text, "s32i a8, a7, 160")
           and then Contains (Text, "l32i a10, a7, 168"),
         "input assignment and output capture protect fixed scratch operands");
   end Assembly_Snapshots;

   procedure Native_Word_Accounting (Item : in out Landin.Testing.Context);
   procedure Native_Word_Accounting (Item : in out Landin.Testing.Context) is
      Text : U.Unbounded_String;
      Serial : Natural := 0;
      Counter : Landin.Backend.Site_Counts.Counter
        (Landin.Backend.Site_Counts.Xtensa);
      Stats : Landin.Build_Reports.Routine_Statistics;
   begin
      Landin.Backend.Xtensa_Machine.Select_Word
        ("lw x5, -48(x8)" & LF & "call callee" & LF
         & "sw x5, -48(x8)", Text, Serial);
      Landin.Backend.Site_Counts.Add_Lines (Counter, U.To_String (Text));
      Landin.Backend.Site_Counts.Fill (Counter, Stats);
      Landin.Testing.Check_Equal
        (Item, Stats.Direct_Calls, 1, "windowed calls are counted");
      Landin.Testing.Check
        (Item, Stats.Stack_Loads >= 8 and then Stats.Stack_Stores >= 4,
         "native frame traffic includes scratch homes and ABI carriers");
   end Native_Word_Accounting;

   procedure Frame_Offsets (Item : in out Landin.Testing.Context);
   procedure Frame_Offsets (Item : in out Landin.Testing.Context) is
      Text : U.Unbounded_String;
      Serial : Natural := 0;
   begin
      Landin.Backend.Xtensa_Machine.Select_Word
        ("lw x5, -48(x8)" & LF & "sw x5, -52(x8)" & LF
         & "lw x6, 1020(x8)" & LF & "lw x7, -47(x8)",
         Text, Serial, Frame_Bytes => 256);
      Landin.Testing.Check
        (Item, Contains (U.To_String (Text), "l32i a10, a7, 208")
           and then Contains (U.To_String (Text), "s32i a8, a7, 204"),
         "encodable CFA homes address the fixed base directly");
      Landin.Testing.Check
        (Item, Contains (U.To_String (Text), "movi a11, 1020")
           and then Contains (U.To_String (Text), "movi a11, -47"),
         "out-of-range and unaligned offsets retain computed addresses");
   end Frame_Offsets;

   procedure Register_Homes (Item : in out Landin.Testing.Context);
   procedure Register_Homes (Item : in out Landin.Testing.Context) is
      Text : U.Unbounded_String;
      Serial : Natural := 0;
   begin
      Landin.Backend.Xtensa_Machine.Select_Word
        ("lw x5, -48(x8)" & LF & "call __udivdi3" & LF
         & "sw x5, -52(x8)", Text, Serial,
         Frame_Bytes => 256, Scratch_Registers => True);
      Landin.Testing.Check
        (Item, Contains (U.To_String (Text), "l32i a2, a7, 208")
           and then Contains (U.To_String (Text), "call8 __udivdi3")
           and then Contains (U.To_String (Text), "s32i a2, a7, 204"),
         "scratch stays in the caller window across a helper call");
   end Register_Homes;

   procedure Compact_Homes (Item : in out Landin.Testing.Context);
   procedure Compact_Homes (Item : in out Landin.Testing.Context) is
      Text : U.Unbounded_String;
      Serial : Natural := 0;
      Refused : Boolean := False;
   begin
      Landin.Backend.Xtensa_Machine.Select_Word
        ("mv x10, x8" & LF & "li x18, 73" & LF & "call callee"
         & LF & "mv x28, x18" & LF & "mv x28, x31"
         & LF & "addi sp, sp, -32", Text, Serial,
         Frame_Bytes => 256, Scratch_Registers => True);
      Landin.Testing.Check
        (Item, Contains (U.To_String (Text), "add a8, a7, a8")
           and then Contains (U.To_String (Text), "s32i a8, a7, 0")
           and then Contains (U.To_String (Text), "l32i a10, a7, 0")
           and then Contains (U.To_String (Text), "s32i a14, a7, 76")
           and then Contains (U.To_String (Text), "l32i a8, a7, 76")
           and then Contains (U.To_String (Text), "add a11, a7, a11")
           and then Contains (U.To_String (Text), "mov a8, a6"),
         "CFA, call carriers, fifth result and outgoing backchain share"
         & " the compact home map without aliasing each other");
      begin
         Landin.Backend.Xtensa_Machine.Select_Word
           ("mv x26, x10", Text, Serial, Scratch_Registers => True);
      exception
         when Landin.Compiler_Defect => Refused := True;
      end;
      Landin.Testing.Check
        (Item, Refused, "an omitted logical word cannot alias a live home");
      Refused := False;
      begin
         Landin.Backend.Xtensa_Machine.Select_Word
           ("mv x8, x10", Text, Serial, Scratch_Registers => True);
      exception
         when Landin.Compiler_Defect => Refused := True;
      end;
      Landin.Testing.Check
        (Item, Refused, "a compact CFA write cannot alias an argument");
      Text := U.Null_Unbounded_String;
      Landin.Backend.Xtensa_Machine.Select_Word
        ("mv x3, x10" & LF & "mv x10, x8", Text, Serial);
      Landin.Testing.Check
        (Item, Contains (U.To_String (Text), "s32i a8, a7, 12")
           and then Contains (U.To_String (Text), "l32i a8, a7, 32")
           and then Contains (U.To_String (Text), "s32i a8, a7, 40"),
         "opaque assembly retains the complete original home map");
   end Compact_Homes;

   procedure Jump_Ranges (Item : in out Landin.Testing.Context);
   procedure Jump_Ranges (Item : in out Landin.Testing.Context) is
      Text : U.Unbounded_String;
      Serial : Natural := 0;
   begin
      Landin.Backend.Xtensa_Machine.Select_Word
        ("j .Lnear", Text, Serial);
      U.Append (Text, ".Lnear:" & LF);
      Landin.Backend.Xtensa_Machine.Select_Word
        ("j .Lfar", Text, Serial);
      for Index in 1 .. 11_000 loop
         U.Append (Text, ASCII.HT & "nop" & LF);
      end loop;
      U.Append (Text, ".Lfar:" & LF);
      Landin.Backend.Xtensa_Machine.Compact_Jumps (Text, 1);
      Landin.Testing.Check
        (Item, Contains (U.To_String (Text), ASCII.HT & "j .Lnear"),
         "a proved local distance uses native J");
      Landin.Testing.Check
        (Item, Contains (U.To_String (Text), "movi a10, .Lfar")
           and then Contains (U.To_String (Text), "jx a10"),
         "an unproved distance retains an arbitrary-range jump");
   end Jump_Ranges;

   procedure Assembly_Ranges (Item : in out Landin.Testing.Context);
   procedure Assembly_Ranges (Item : in out Landin.Testing.Context) is
      Text : constant String := Emitted
        (Item,
         "f: (v: u32) -> (r: u32) =" & LF
         & "    assembler.block(""nop"")" & LF
         & "    r = if v == 0 then 1 else 2 end if" & LF
         & "end f" & LF);
   begin
      Landin.Testing.Check
        (Item, Contains (Text, "jx a10")
           and then not Contains (Text, ASCII.HT & "j .L"),
         "any opaque source assembly disables distance-based compaction");
      Landin.Testing.Check
        (Item, Contains (Text, "s32i a10, a7, 20"),
         "opaque source assembly retains all logical scratch homes");
   end Assembly_Ranges;

   --  [1640]: a placement's alignment follows the section directive of
   --  its item, a zeroed datum's, an initialized one's, an immutable
   --  one's and a routine's, as one more directive line the native
   --  translation passes through at every profile; that line once
   --  reached the translator indented and was refused as an operation.
   procedure Placement_Alignment (Item : in out Landin.Testing.Context);
   procedure Placement_Alignment (Item : in out Landin.Testing.Context) is
      package Opt renames Landin.Optimization;
      HT : constant Character := ASCII.HT;
      Source : constant String :=
        "link(align: 256)" & LF & "mut zero_cell: [3]u8 = zeroed" & LF
        & "link(align: 64)" & LF & "mut data_cell: u32 = 5" & LF
        & "link(align: 32)" & LF & "table: [3]u8 = [1, 2, 3]" & LF
        & "link(align: 16)" & LF
        & "twice: (x: u32) -> (r: u32) =" & LF & "    r = x + x" & LF
        & "end twice" & LF
        & "use: () -> (r: u32) =" & LF
        & "    data_cell = data_cell + u32(table[2]) + u32(zero_cell[1])"
        & LF & "    r = twice(data_cell)" & LF & "end use" & LF;
      type Profile_List is array (Positive range <>) of Opt.Options;
      Profiles : constant Profile_List :=
        [(Opt.None, Opt.Off), (Opt.Size, Opt.Off), (Opt.Size, Opt.Auto),
         (Opt.Speed, Opt.Auto)];
   begin
      for Options of Profiles loop
         declare
            Text : constant String := Emitted (Item, Source, Options);
            Where : constant String :=
              " at " & Opt.Spelling (Options.Optimize) & "/"
              & Opt.Spelling (Options.Specialize);
         begin
            Landin.Testing.Check
              (Item, Contains (Text, """aw"",@nobits" & LF & HT
                               & ".balign 256" & LF)
                 and then Contains (Text, """aw"",@progbits" & LF & HT
                                    & ".balign 64" & LF)
                 and then Contains (Text, """a"",@progbits" & LF & HT
                                    & ".balign 32" & LF)
                 and then Contains (Text, """ax"",@progbits" & LF & HT
                                    & ".balign 16" & LF),
               "each placed item's section is followed by its alignment"
               & Where & LF & Text);
         end;
      end loop;
   end Placement_Alignment;

   --  D1110.  The window handlers store a caller's a0 to a3 below the
   --  callee's SP when the caller's window is taken and read them from
   --  below it at RETW, so SP stays where the prologue left it: a
   --  routine's largest outgoing area is the lowest bytes of its frame.
   --  Execution is the window-arguments control of both chips' lanes.
   procedure Outgoing_Area_In_Frame (Item : in out Landin.Testing.Context);
   procedure Outgoing_Area_In_Frame (Item : in out Landin.Testing.Context)
   is
      HT : constant Character := ASCII.HT;
      Text : constant String := Emitted
        (Item,
         "sum4: (a: u64, b: u64, c: u64, d: u64) -> (r: u64) =" & LF
         & "    r = a + b + c + d" & LF
         & "end sum4" & LF
         & "sum3: (a: u64, b: u64, c: u64) -> (r: u64) =" & LF
         & "    r = a + b + c" & LF
         & "end sum3" & LF
         & "report: (seed: u64) -> (r: u64) =" & LF
         & "    r = sum4(seed, 2, 3, 4) + sum3(seed, 2, 3)" & LF
         & "end report" & LF);
      Report_At : constant Natural :=
        Ada.Strings.Fixed.Index (Text, LF & "report:" & LF);
      --  The fourth u64 is the one stack word pair: sixteen bytes at SP,
      --  with the base of the word homes above them.  The incoming a7 is
      --  stored there only when the routine reads it (D2116).
      Above : constant String :=
        HT & "sub a1, a1, a8" & LF
        & HT & "movi a8, 16" & LF
        & HT & "add a8, a1, a8" & LF;
      Based : constant String := HT & "mov a7, a8" & LF;
      Above_At : constant Natural :=
        (if Report_At = 0 then 0
         else Ada.Strings.Fixed.Index (Text, Above, Report_At));
      Call_At : constant Natural :=
        Ada.Strings.Fixed.Index (Text, "call8 sum4");
   begin
      Landin.Testing.Check
        (Item, Report_At > 0 and then Above_At > Report_At
           and then Call_At > Above_At
           and then Ada.Strings.Fixed.Count (Text, Above) = 1
           and then Ada.Strings.Fixed.Count (Text, Based) = 1,
         "the routine whose call takes stack words lays their area below"
         & " its word homes, and no other routine has one" & LF & Text);
      Landin.Testing.Check
        (Item, Ada.Strings.Fixed.Count (Text, HT & "sub a1, a1, a8" & LF) = 3
           and then Ada.Strings.Fixed.Count (Text, HT & "mov a1, ") = 0
           and then Ada.Strings.Fixed.Count (Text, HT & "addi a1, ") = 0
           and then Ada.Strings.Fixed.Count (Text, HT & "add a1, ") = 0
           and then Ada.Strings.Fixed.Count (Text, HT & "movsp ") = 0,
         "SP is written by each prologue once and by nothing after it");
      Landin.Testing.Check
        (Item, Ada.Strings.Fixed.Count (Text, HT & "s32e ") = 3
           and then Ada.Strings.Fixed.Count (Text, HT & "l32e ") = 0,
         "no base save is copied: only each prologue's backchain word is"
         & " written below SP");
      Landin.Testing.Check
        (Item, Call_At > 0
           and then Ada.Strings.Fixed.Index
             (Text (Above_At .. Call_At), ", a1, 0" & LF) > 0
           and then Ada.Strings.Fixed.Index
             (Text (Above_At .. Call_At), ", a1, 4" & LF) > 0,
         "the stack words are addressed from SP");
      --  The report's figures count the area: the homes' extent is the
      --  figure the prologue adds to their base for the frame address.
      declare
         use type Landin.Targets.Byte_Count;
         Homes_At : constant Natural :=
           (if Above_At = 0 then 0
            else Ada.Strings.Fixed.Index
              (Text, LF & HT & "add a8, a7, a8" & LF, Above_At));
         Figure_At : constant Natural :=
           (if Homes_At = 0 then 0
            else Ada.Strings.Fixed.Index
              (Text (Above_At .. Homes_At), HT & "movi a8, ",
               Going => Ada.Strings.Backward));
         Homes : constant Landin.Targets.Byte_Count :=
           (if Figure_At = 0 then 0
            else Landin.Targets.Byte_Count'Value
              (Text (Figure_At + 10 .. Homes_At - 1)));
         Counted : Natural := 0;
      begin
         for Index in 1 .. Landin.Build_Reports.Routine_Count (Last_Report)
         loop
            declare
               Row : constant Landin.Build_Reports.Routine_Statistics :=
                 Landin.Build_Reports.Nth_Routine (Last_Report, Index);
            begin
               if Row.Frame_Bytes = Homes + 16
                 and then Row.Stack_Bytes = Homes + 32
               then
                  Counted := Counted + 1;
               end if;
            end;
         end loop;
         --  At least the 48 bytes below the CFA the window keeps.
         Landin.Testing.Check
           (Item, Homes >= 48 and then Homes mod 16 = 0 and then Counted >= 1,
            "the build report's frame and stack figures of that routine"
            & " count the sixteen bytes of its area:"
            & Homes'Image & Counted'Image);
      end;
   end Outgoing_Area_In_Frame;

   --  D1627: the text of routine Name, from its label to its size.
   function Routine_Text (Text, Name : String) return String;
   function Routine_Text (Text, Name : String) return String is
      Start : constant Natural :=
        Ada.Strings.Fixed.Index (Text, LF & Name & ":" & LF);
      Stop : constant Natural :=
        (if Start = 0 then 0
         else Ada.Strings.Fixed.Index (Text, ".size " & Name & ",", Start));
   begin
      return (if Start = 0 or else Stop = 0 then ""
              else Text (Start .. Stop));
   end Routine_Text;

   --  D1627: whether Text moves a word through the homes at a7 after the
   --  prologue's backchain word, the last line the prologue writes.
   function Homes_Traffic (Text : String) return Boolean;
   function Homes_Traffic (Text : String) return Boolean is
      Body_At : constant Natural :=
        Ada.Strings.Fixed.Index (Text, "s32e a8, a1, -12");
   begin
      return Body_At = 0
        or else Ada.Strings.Fixed.Index (Text (Body_At .. Text'Last), ", a7, ")
          > 0;
   end Homes_Traffic;

   --  D1627: a loop's words, the values and slots among them, are placed
   --  in registers, and nothing goes through the homes.
   procedure Placed_Loop (Item : in out Landin.Testing.Context);
   procedure Placed_Loop (Item : in out Landin.Testing.Context) is
      Text : constant String := Routine_Text (Emitted
        (Item,
         "total: (n: u32) -> (r: u32) =" & LF
         & "    mut sum: u32 = 0" & LF
         & "    mut index: u32 = 0" & LF
         & "    while index < n do" & LF
         & "        sum = sum +% index" & LF
         & "        inc index" & LF
         & "    end while" & LF
         & "    r = sum" & LF
         & "end total" & LF), "total");
      Placed : Natural := 0;
   begin
      for Index in 1 .. Landin.Build_Reports.Routine_Count (Last_Report) loop
         Placed := Natural'Max
           (Placed, Landin.Build_Reports.Nth_Routine
                      (Last_Report, Index).Register_Count);
      end loop;
      Landin.Testing.Check
        (Item, Text /= "" and then not Homes_Traffic (Text),
         "the loop's slots and values stay in registers" & LF & Text);
      Landin.Testing.Check
        (Item, Placed > 0, "the build report counts the registers placed");
   end Placed_Loop;

   --  D2116: a placed routine's frame is laid out after its words are
   --  placed.  One whose words all stay in registers reserves only the
   --  48 bytes below the CFA the window keeps, and does not store the
   --  incoming a7 it never reads; one with an array keeps the array's
   --  home, which its address reaches, and no bank beside it.
   procedure Placed_Frame (Item : in out Landin.Testing.Context);
   procedure Placed_Frame (Item : in out Landin.Testing.Context) is
      HT : constant Character := ASCII.HT;
      Whole : constant String := Emitted
        (Item,
         "total: (n: u32) -> (r: u32) =" & LF
         & "    mut sum: u32 = 0" & LF
         & "    mut index: u32 = 0" & LF
         & "    while index < n do" & LF
         & "        sum = sum +% index" & LF
         & "        inc index" & LF
         & "    end while" & LF
         & "    r = sum" & LF
         & "end total" & LF
         & "pick: (i: usize) -> (r: usize) =" & LF
         & "    mut table: [8]usize = [0, 0, 0, 0, 0, 0, 0, 0]" & LF
         & "    table[i & 7] = i" & LF
         & "    r = table[(i +% 1) & 7]" & LF
         & "end pick" & LF);
      Total : constant String := Routine_Text (Whole, "total");
      Pick : constant String := Routine_Text (Whole, "pick");
      Frames : array (1 .. 2) of Natural := [others => 0];
   begin
      for Index in 1 .. Landin.Build_Reports.Routine_Count (Last_Report) loop
         declare
            Row : constant Landin.Build_Reports.Routine_Statistics :=
              Landin.Build_Reports.Nth_Routine (Last_Report, Index);
            Frame : constant Natural := Natural (Row.Frame_Bytes);
         begin
            if Frame = 48 then
               Frames (1) := Frames (1) + 1;
            elsif Frame >= 48 + 32 and then Frame < 48 + 32 + 80 then
               Frames (2) := Frames (2) + 1;
            end if;
         end;
      end loop;
      Landin.Testing.Check
        (Item, Total /= ""
           and then Contains
             (Total, HT & "movi a8, 16" & LF & HT & "sub a1, a1, a8" & LF)
           and then not Contains (Total, "s32i a7, "),
         "a routine whose words stay in registers reserves 48 bytes and"
         & " leaves the incoming a7 unstored" & LF & Total);
      Landin.Testing.Check
        (Item, Pick /= "" and then Frames (1) >= 1 and then Frames (2) = 1,
         "the array's routine keeps its 32-byte home and no bank:"
         & Frames (1)'Image & Frames (2)'Image & LF & Pick);
   end Placed_Frame;

   --  D1627: CALL8 preserves a2-a7 alone, so a word live across a call is
   --  placed there, and the call's argument and result words are a10 on.
   procedure Placed_Across_Call (Item : in out Landin.Testing.Context);
   procedure Placed_Across_Call (Item : in out Landin.Testing.Context) is
      Text : constant String := Routine_Text (Emitted
        (Item,
         "leaf: (x: u32) -> (r: u32) =" & LF
         & "    r = x +% 1" & LF
         & "end leaf" & LF
         & "twice: (x: u32) -> (r: u32) =" & LF
         & "    once: u32 = leaf(x)" & LF
         & "    r = leaf(once) +% x" & LF
         & "end twice" & LF), "twice");
      Second : constant Natural :=
        (if Text = "" then 0
         else Ada.Strings.Fixed.Index
           (Text, "call8 leaf", Ada.Strings.Fixed.Index (Text, "call8 leaf")
                                + 1));
   begin
      Landin.Testing.Check
        (Item, Text /= "" and then not Homes_Traffic (Text)
           and then Second > 0,
         "x crosses both calls without its home" & LF & Text);
      Landin.Testing.Check
        (Item, Second > 0
           and then Ada.Strings.Fixed.Index
             (Text (Second .. Text'Last), "add a") > 0
           and then (for some Register in 2 .. 6 =>
                       Ada.Strings.Fixed.Index
                         (Text (Second .. Text'Last),
                          ", a" & Character'Val (48 + Register))
                       > 0),
         "after the second call x is read from a2-a6");
   end Placed_Across_Call;

   --  Whether no label Text defines is defined twice.  A placed
   --  routine's prologue is written after its body is placed (D2116),
   --  and its stack check's labels must still be its own.
   function Labels_Unique (Text : String) return Boolean;
   function Labels_Unique (Text : String) return Boolean is
      Start : Positive := Text'First;
   begin
      for Index in Text'Range loop
         if Text (Index) = LF then
            if Index > Start + 1 and then Text (Index - 1) = ':'
              and then Text (Start) = '.'
              and then Ada.Strings.Fixed.Count
                (Text, LF & Text (Start .. Index)) > 1
            then
               return False;
            end if;
            Start := Index + 1;
         end if;
      end loop;
      return True;
   end Labels_Unique;

   --  D1110: where a program prepares stacks, each prologue
   --  checks its whole frame against the stack's limit, so the figure it
   --  subtracts from SP counts the outgoing area too: sixteen bytes more
   --  than its homes' figure less the sixteen below SP, which is the
   --  homes' figure itself, where a routine with no area checks sixteen
   --  less than its homes.
   procedure Prepared_Stack_Area (Item : in out Landin.Testing.Context);
   procedure Prepared_Stack_Area (Item : in out Landin.Testing.Context) is
      HT : constant Character := ASCII.HT;
      Text : constant String := Emitted
        (Item,
         "mut backing: [4096]u8 = zeroed" & LF
         & "mut main_saved: usize = 0" & LF
         & "mut fibre_saved: usize = 0" & LF
         & "sum4: (a: u64, b: u64, c: u64, d: u64) -> (r: u64) =" & LF
         & "    r = a + b + c + d" & LF
         & "end sum4" & LF
         & "fibre: (argument: usize) -> noreturn =" & LF
         & "    loop do" & LF
         & "        _ = sum4(u64(argument), 2, 3, 4)" & LF
         & "        compiler.stack_switch(addr fibre_saved, main_saved)" & LF
         & "    end loop" & LF
         & "end fibre" & LF
         & "run: () -> none =" & LF
         & "    fibre_saved = compiler.stack_prepare(backing[0..<4096],"
         & " fibre, 7)" & LF
         & "    compiler.stack_switch(addr main_saved, fibre_saved)" & LF
         & "end run" & LF);

      --  The figure the prologue of Name checks against the limit, and
      --  the one it adds to the homes' base for the frame address.
      procedure Figures
        (Name : String; Checked, Homes : out Integer);
      procedure Figures
        (Name : String; Checked, Homes : out Integer)
      is
         Start : constant Natural :=
           Ada.Strings.Fixed.Index (Text, LF & Name & ":" & LF);
         Check_At : constant Natural :=
           (if Start = 0 then 0
            else Ada.Strings.Fixed.Index
              (Text, LF & HT & "sub a8, a1, a8" & LF, Start));
         Homes_At : constant Natural :=
           (if Start = 0 then 0
            else Ada.Strings.Fixed.Index
              (Text, LF & HT & "add a8, a7, a8" & LF, Start));
         function Figure_Before (At_Line : Natural) return Integer;
         function Figure_Before (At_Line : Natural) return Integer is
            Figure_At : constant Natural :=
              (if At_Line = 0 then 0
               else Ada.Strings.Fixed.Index
                 (Text (Start .. At_Line), HT & "movi a8, ",
                  Going => Ada.Strings.Backward));
         begin
            return (if Figure_At = 0 then -1
                    else Integer'Value (Text (Figure_At + 10 .. At_Line - 1)));
         end Figure_Before;
      begin
         Checked := Figure_Before (Check_At);
         Homes := Figure_Before (Homes_At);
      end Figures;

      Fibre_Checked, Fibre_Homes, Sum_Checked, Sum_Homes : Integer;
   begin
      Figures ("fibre", Fibre_Checked, Fibre_Homes);
      Figures ("sum4", Sum_Checked, Sum_Homes);
      Landin.Testing.Check
        (Item, Fibre_Homes > 0 and then Fibre_Checked = Fibre_Homes,
         "the routine whose call takes stack words checks its area too:"
         & Fibre_Checked'Image & Fibre_Homes'Image & LF & Text);
      Landin.Testing.Check
        (Item, Sum_Homes > 0 and then Sum_Checked = Sum_Homes - 16,
         "a routine without an area checks its homes alone:"
         & Sum_Checked'Image & Sum_Homes'Image);
      Landin.Testing.Check
        (Item, Labels_Unique (Text),
         "every checking prologue's labels are its own" & LF & Text);
   end Prepared_Stack_Area;

   --  An interrupt's entry and return leave the firmware's interrupt
   --  context in EXCSAVE1, so the switch masks before it names its own.
   procedure Switch_Masks_First (Item : in out Landin.Testing.Context);
   procedure Switch_Masks_First (Item : in out Landin.Testing.Context) is
      HT : constant Character := ASCII.HT;
      Text : constant String := Emitted
        (Item,
         "mut backing: [4096]u8 = zeroed" & LF
         & "mut main_saved: usize = 0" & LF
         & "mut fibre_saved: usize = 0" & LF
         & "fibre: (argument: usize) -> noreturn =" & LF
         & "    loop do" & LF
         & "        compiler.stack_switch(addr fibre_saved, main_saved)" & LF
         & "    end loop" & LF
         & "end fibre" & LF
         & "run: () -> none =" & LF
         & "    fibre_saved = compiler.stack_prepare(backing[0..<4096],"
         & " fibre, 7)" & LF
         & "    compiler.stack_switch(addr main_saved, fibre_saved)" & LF
         & "end run" & LF);
      Masked_At : constant Natural :=
        Ada.Strings.Fixed.Index (Text, HT & "rsil a0, 15" & LF);
      Named_At : constant Natural :=
        Ada.Strings.Fixed.Index (Text, HT & "wsr a1, EXCSAVE1" & LF);
   begin
      Landin.Testing.Check
        (Item, Masked_At > 0 and then Named_At > Masked_At
           and then Ada.Strings.Fixed.Count (Text, "wsr a1, EXCSAVE1") = 1,
         "interrupts are masked before EXCSAVE1 holds the switch's context"
         & LF & Text);
      Landin.Testing.Check
        (Item, Named_At > 0
           and then Ada.Strings.Fixed.Index
             (Text (Text'First .. Named_At), "rsr a0, EXCSAVE1") = 0,
         "nothing reads the context register before it is written");
      --  D471: the prologue's own check, of every ordinary routine once
      --  a program prepares a stack, tests the wrapped difference first.
      Landin.Testing.Check
        (Item, Contains (Text, HT & "sub a8, a1, a8" & LF
           & HT & "movi a9, ")
           and then Contains (Text, HT & "bltu a1, a8, ")
           and then Ada.Strings.Fixed.Index (Text, HT & "bltu a1, a8, ")
             < Ada.Strings.Fixed.Index (Text, HT & "bgeu a8, a9, "),
         "a frame larger than the stack pointer's value goes to the trap");
   end Switch_Masks_First;

   --  D1628, D2113: a comparison only its branch reads is the branch, and
   --  an edge to the block laid out next falls through rather than
   --  jumping.
   --  D3175: the branch after a call that can fail tests the status
   --  where the call left it, with no load of its failure slot between.
   procedure Status_In_Register (Item : in out Landin.Testing.Context);
   procedure Status_In_Register (Item : in out Landin.Testing.Context) is
      HT : constant Character := ASCII.HT;
      Text : constant String := Emitted
        (Item,
         "bad: atom" & LF
         & "problem: type = bad" & LF
         & "operation: type = (fails: bool) -> (value: i32) ! problem" & LF
         & "public run: (op: operation, fails: bool) -> (code: i32)"
         & " ! problem =" & LF
         & "    code = try op(fails)" & LF
         & "end run" & LF,
         (Landin.Optimization.Size, Landin.Optimization.Auto));
      Called : constant Natural :=
        Ada.Strings.Fixed.Index (Text, HT & "callx8 ");
   begin
      Landin.Testing.Check
        (Item, Called > 0
           and then Ada.Strings.Fixed.Index
             (Text, HT & "s32i a14, a7, 12" & LF & HT & "beqz a14, ", Called)
             > 0,
         "the branch after the call tests its status in the register");
   end Status_In_Register;

   procedure Branches_Fall_Through (Item : in out Landin.Testing.Context);
   procedure Branches_Fall_Through (Item : in out Landin.Testing.Context) is
      HT : constant Character := ASCII.HT;
      Text : constant String := Emitted
        (Item,
         "pick: (a: i32, b: i32) -> (r: i32) =" & LF
         & "    if a < b then" & LF
         & "        r = a" & LF
         & "    else" & LF
         & "        r = b" & LF
         & "    end if" & LF
         & "end pick" & LF
         & "count: (n: u32) -> (r: u32) =" & LF
         & "    mut i: u32 = 0" & LF
         & "    while i < n do" & LF
         & "        i = i + 1" & LF
         & "    end while" & LF
         & "    r = i" & LF
         & "end count" & LF
         & "fless: (a: f32, b: f32) -> (r: u32) =" & LF
         & "    if a < b then" & LF
         & "        r = 1" & LF
         & "    else" & LF
         & "        r = 2" & LF
         & "    end if" & LF
         & "end fless" & LF);

      --  Whether a jump in Text, near or far, goes to the label after it.
      function Jumps_To_Next return Boolean;
      function Jumps_To_Next return Boolean is
         Before, Previous : U.Unbounded_String;
         First : Positive := Text'First;
      begin
         for Index in Text'Range loop
            if Text (Index) = LF then
               declare
                  Line : constant String := Text (First .. Index - 1);
               begin
                  if Line'Length > 1 and then Line (Line'Last) = ':' then
                     declare
                        Name : constant String :=
                          Line (Line'First .. Line'Last - 1);
                     begin
                        if U.To_String (Previous) = HT & "j " & Name
                          or else (U.To_String (Previous) = HT & "jx a10"
                                   and then U.To_String (Before)
                                     = HT & "movi a10, " & Name)
                        then
                           return True;
                        end if;
                     end;
                  end if;
                  Before := Previous;
                  Previous := U.To_Unbounded_String (Line);
               end;
               First := Index + 1;
            end if;
         end loop;
         return False;
      end Jumps_To_Next;
   begin
      Landin.Testing.Check
        (Item, Contains (Text, HT & "bge ")
           or else Contains (Text, HT & "blt "),
         "a signed comparison is the branch on its operands" & LF & Text);
      Landin.Testing.Check
        (Item, not Jumps_To_Next,
         "no jump goes to the label after it" & LF & Text);
   end Branches_Fall_Through;

   procedure Register (Into : in out Landin.Testing.Registry) is
   begin
      Landin.Testing.Register
        (Into, "xtensa backend", "a branch falls through to the next block",
         Branches_Fall_Through'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "a call's status is tested in its register",
         Status_In_Register'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "an outgoing area is part of the frame",
         Outgoing_Area_In_Frame'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "placed words keep a loop in registers",
         Placed_Loop'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "a word across a call keeps a2-a6",
         Placed_Across_Call'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "a placed frame holds only what it spills",
         Placed_Frame'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "a prepared stack's check counts the area",
         Prepared_Stack_Area'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "the stack switch masks before its context",
         Switch_Masks_First'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "a placement's alignment is emitted",
         Placement_Alignment'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "windowed routines carry paired scalars",
         Windowed_Pairs'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "assembly captures scratch register outputs",
         Assembly_Snapshots'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "native word traffic and calls are counted",
         Native_Word_Accounting'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "fixed frame offsets retain range fallback",
         Frame_Offsets'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "scratch survives a helper window",
         Register_Homes'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "compact homes preserve native boundaries",
         Compact_Homes'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "local jumps retain arbitrary range fallback",
         Jump_Ranges'Access);
      Landin.Testing.Register
        (Into, "xtensa backend", "opaque assembly retains range and homes",
         Assembly_Ranges'Access);
   end Register;
end Landin.Tests.Xtensa_Backend_Suite;
