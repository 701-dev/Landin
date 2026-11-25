with Ada.Strings.Fixed;
with Ada.Strings.Unbounded;

with Landin.Backend.Toolchain;
with Landin.Platform.Native.Tools;
with Landin.Targets.Selection;

package body Landin.Testing.Lanes is

   package Unbounded renames Ada.Strings.Unbounded;

   use type Landin.Targets.Target_Facts;

   Chosen        : Landin.Targets.Target_Facts := Landin.Targets.Synthetic_32;
   Chosen_Is_Set : Boolean := False;
   Runner_Name   : Unbounded.Unbounded_String;
   Driver_Name   : Unbounded.Unbounded_String;

   --  The label a product target's fixtures carry, which is its own name:
   --  `targets:` spells a target as `--target` does.  synthetic-32 has no
   --  corpus to execute, so it is no lane.
   function Label_Of (Name : String) return String
     is (if Name in "linux-x86-64" | "linux-arm64" | "linux-rv64"
                  | "darwin-arm64" | "freebsd-x86-64" | "freebsd-arm64"
                  | "cortex-m0"
         then Name
         else "");

   function Select_Target (Name : String) return Boolean is
   begin
      if not Landin.Targets.Selection.Is_Described (Name)
        or else Label_Of (Name) = ""
      then
         return False;
      end if;
      Chosen := Landin.Targets.Selection.Described (Name);
      Chosen_Is_Set := True;
      return True;
   end Select_Target;

   procedure Select_Runner (Program : String) is
   begin
      Runner_Name := Unbounded.To_Unbounded_String (Program);
   end Select_Runner;

   procedure Select_Toolchain (Driver : String) is
   begin
      Driver_Name := Unbounded.To_Unbounded_String (Driver);
   end Select_Toolchain;

   function Host_Has_Default return Boolean
     is (Landin.Targets.Selection.Has_Host_Default
           (Landin.Targets.Selection.Build_Triplet));

   function Has_Target return Boolean
     is (Chosen_Is_Set or else Host_Has_Default);

   function Target return Landin.Targets.Target_Facts is
   begin
      if Chosen_Is_Set then
         return Chosen;
      elsif Host_Has_Default then
         return Landin.Targets.Selection.Host_Default
           (Landin.Targets.Selection.Build_Triplet);
      else
         raise Compiler_Defect
           with "no lane: this host has no description; name --target=";
      end if;
   end Target;

   function Target_Name return String is (Landin.Targets.Name (Target));

   function Fixture_Label return String is (Label_Of (Target_Name));

   function Applies (Targets : String) return Boolean is
      Wanted : constant String := Fixture_Label;
      First  : Integer := Targets'First;
   begin
      for Index in Targets'First .. Targets'Last + 1 loop
         if Index > Targets'Last or else Targets (Index) = ',' then
            if Ada.Strings.Fixed.Trim
                 (Targets (First .. Index - 1), Ada.Strings.Both) = Wanted
            then
               return True;
            end if;
            First := Index + 1;
         end if;
      end loop;
      return False;
   end Applies;

   function Is_Native return Boolean
     is (Host_Has_Default
         and then Target = Landin.Targets.Selection.Host_Default
                             (Landin.Targets.Selection.Build_Triplet));

   function Runner return String is (Unbounded.To_String (Runner_Name));

   --  Asked once: whether the native lane's own driver is installed, and
   --  if it is not, the first of refine's other candidates that is.
   Native_Driver_Asked : Boolean := False;
   Native_Driver       : Unbounded.Unbounded_String;

   function Toolchain return String is
   begin
      if Unbounded.Length (Driver_Name) > 0 or else not Is_Native then
         return Unbounded.To_String (Driver_Name);
      end if;
      if not Native_Driver_Asked then
         Native_Driver_Asked := True;
         declare
            Host : Landin.Platform.Native.Tools.Native_Tool_Runner;
            Preferred : constant String :=
              Landin.Backend.Toolchain.Driver_For (Target, "");
         begin
            for Name of Landin.Backend.Toolchain.Driver_Candidates
              (Target, "", Native => True)
            loop
               if Host.Available (Name) then
                  if Name /= Preferred then
                     Native_Driver := Unbounded.To_Unbounded_String (Name);
                  end if;
                  exit;
               end if;
            end loop;
         end;
      end if;
      return Unbounded.To_String (Native_Driver);
   end Toolchain;

   function Target_Arguments return Landin.Platform.Path_List is
      Result : Landin.Platform.Path_List;
   begin
      if not Is_Native then
         Result.Append ("--target=" & Target_Name);
      end if;
      return Result;
   end Target_Arguments;

   function Describe return String is
     ((if Is_Native then "NATIVE " else "CROSS ") & Target_Name
      & (if Runner = "" then "" else ", run by " & Runner)
      & (if Toolchain = "" then "" else ", linked by " & Toolchain));

end Landin.Testing.Lanes;
