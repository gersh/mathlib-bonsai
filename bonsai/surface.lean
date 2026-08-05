import Mathlib
import Lean.Util.CollectAxioms

/-!
Emit a deterministic manifest of the public declarations exposed by `import Mathlib`.

This file is trusted competition infrastructure. CI always executes the version
from the PR's base commit against both the base and candidate builds.
-/

open Lean Elab Command

namespace MathlibBonsai

private def tagged (seed tag value : UInt64) : UInt64 :=
  mixHash (mixHash seed tag) value

private partial def levelHash (seed : UInt64) (parameters : List Name) : Level → UInt64
  | .zero => tagged seed 1 0
  | .succ level => tagged seed 2 (levelHash seed parameters level)
  | .max left right =>
      tagged seed 3 (mixHash (levelHash seed parameters left) (levelHash seed parameters right))
  | .imax left right =>
      tagged seed 4 (mixHash (levelHash seed parameters left) (levelHash seed parameters right))
  | .param name => tagged seed 5 (hash ((parameters.idxOf? name).getD parameters.length))
  | .mvar _ => tagged seed 6 0

private def binderHash : BinderInfo → UInt64
  | .default => 1
  | .implicit => 2
  | .strictImplicit => 3
  | .instImplicit => 4

private partial def exprHash (seed : UInt64) (parameters : List Name) : Expr → UInt64
  | .bvar index => tagged seed 11 (hash index)
  | .fvar _ => tagged seed 12 0
  | .mvar _ => tagged seed 13 0
  | .sort level => tagged seed 14 (levelHash seed parameters level)
  | .const name levels =>
      tagged seed 15 <| levels.foldl
        (fun state level => mixHash state (levelHash seed parameters level))
        (mixHash seed (hash name.toString))
  | .app function argument =>
      tagged seed 16 (mixHash (exprHash seed parameters function) (exprHash seed parameters argument))
  | .lam name type body info =>
      tagged seed 17 <| mixHash (hash name.toString) <| mixHash (binderHash info) <|
        mixHash (exprHash seed parameters type) (exprHash seed parameters body)
  | .forallE name type body info =>
      tagged seed 18 <| mixHash (hash name.toString) <| mixHash (binderHash info) <|
        mixHash (exprHash seed parameters type) (exprHash seed parameters body)
  | .letE name type value body nondep =>
      tagged seed 19 <| mixHash (hash name.toString) <| mixHash (hash nondep) <|
        mixHash (exprHash seed parameters type) <| mixHash (exprHash seed parameters value) <|
          exprHash seed parameters body
  | .lit (.natVal value) => tagged seed 20 (hash value)
  | .lit (.strVal value) => tagged seed 21 (hash value)
  | .mdata _ expression => exprHash seed parameters expression
  | .proj typeName index expression =>
      tagged seed 22 <| mixHash (hash typeName.toString) <| mixHash (hash index) <|
        exprHash seed parameters expression

private def typeFingerprint (parameters : List Name) (type : Expr) : Array Json :=
  #[toJson (toString (hash type)),
    toJson (toString (exprHash 0x243f6a8885a308d3 parameters type))]

private def isMathlibDeclaration (environment : Environment) (name : Name) : Bool :=
  match environment.getModuleFor? name with
  | some moduleName => moduleName == `Mathlib || (`Mathlib).isPrefixOf moduleName
  | none => false

private def isChangedDeclaration (environment : Environment) (changedModules : Std.HashSet Name)
    (name : Name) : Bool :=
  match environment.getModuleFor? name with
  | some moduleName => changedModules.contains moduleName
  | none => false

private def theoremJson (name : Name) (levels : List Name) (type : Expr) : Json :=
  json% {
    name : $(name.toString),
    universeArity : $(levels.length),
    typeFingerprint : $(typeFingerprint levels type)
  }

private def implementationKind : ConstantInfo → String
  | .defnInfo _ => "definition"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _ => "quotient"
  | .inductInfo _ => "inductive"
  | .ctorInfo _ => "constructor"
  | .recInfo _ => "recursor"
  | .axiomInfo _ => "axiom"
  | .thmInfo _ => "theorem"

private def implementationJson (info : ConstantInfo) : Json :=
  let valueFingerprint : Json := match info.value? (allowOpaque := true) with
    | some value => toJson (typeFingerprint info.levelParams value)
    | none => Json.null
  json% {
    name : $(info.name.toString),
    declarationKind : $(implementationKind info),
    universeArity : $(info.levelParams.length),
    typeFingerprint : $(typeFingerprint info.levelParams info.type),
    valueFingerprint : $valueFingerprint
  }

private def permittedAxiom (name : Name) : Bool :=
  name == ``propext || name == ``Quot.sound || name == ``Classical.choice

private def writeManifest (environment : Environment) (changedModules : Std.HashSet Name)
    (output : String) : CoreM Unit := do
  let handle ← IO.FS.Handle.mk output .write
  handle.putStrLn <| (json% { schema : 1, rootModule : "Mathlib" }).compress
  let mut forbiddenAxioms : Std.HashSet Name := {}
  for (name, info) in environment.constants.map₁ do
    unless isMathlibDeclaration environment name && (privateToUserName? name).isNone &&
        !name.isInternalDetail do
      continue
    match info with
    | .thmInfo value =>
        handle.putStrLn <| (json% {
          kind : "theorem",
          declaration : $(theoremJson name value.levelParams value.type)
        }).compress
        -- Public statement fingerprints remain global. Proof dependency traversal only needs the
        -- modules this entry may alter; policy rejects every other source change.
        if isChangedDeclaration environment changedModules name then
          for axiomName in ← Lean.collectAxioms name do
            unless permittedAxiom axiomName do
              forbiddenAxioms := forbiddenAxioms.insert axiomName
    | .axiomInfo value =>
        handle.putStrLn <| (json% {
          kind : "axiom",
          declaration : $(theoremJson name value.levelParams value.type)
        }).compress
    | _ =>
        if isChangedDeclaration environment changedModules name then
          handle.putStrLn <| (json% {
            kind : "implementation",
            declaration : $(implementationJson info)
          }).compress
  let forbidden := forbiddenAxioms.toArray.qsort fun left right => left.toString < right.toString
  handle.putStrLn <| (json% {
    kind : "end",
    forbiddenAxioms : $(forbidden.map (toJson ·.toString))
  }).compress

end MathlibBonsai

run_cmd do
  let output := (← IO.getEnv "GOLF_SURFACE_OUT").getD "surface.jsonl"
  let changedModules := ((← IO.getEnv "BONSAI_CHANGED_MODULES").getD "").splitOn ";"
    |>.foldl (fun modules value => if value.isEmpty then modules else modules.insert value.toName) {}
  let environment ← getEnv
  liftCoreM <| MathlibBonsai.writeManifest environment changedModules output
