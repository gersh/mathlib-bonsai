import Lean

/-!
Trusted affected-file complexity measurement for Mathlib Bonsai.

The Python driver supplies a comment-masked copy of one Mathlib source file. This executable parses
and elaborates it with async elaboration disabled, then reports raw syntax-tree nodes, kernel
expression nodes in declarations produced by the file, and Lean's internal heartbeat counter.
-/

open Lean

namespace MathlibBonsai.Measure

private partial def syntaxNodes : Syntax → Nat
  | .missing => 1
  | .atom .. => 1
  | .ident .. => 1
  | .node _ kind children =>
      if kind == ``Parser.Command.docComment || kind == ``Parser.Command.moduleDoc then
        0
      else
        children.foldl (fun total child => total + syntaxNodes child) 1

private partial def expressionNodes : Expr → Nat
  | .bvar _ | .fvar _ | .mvar _ | .sort _ | .const .. | .lit _ => 1
  | .app function argument => 1 + expressionNodes function + expressionNodes argument
  | .lam _ type body _ | .forallE _ type body _ =>
      1 + expressionNodes type + expressionNodes body
  | .letE _ type value body _ =>
      1 + expressionNodes type + expressionNodes value + expressionNodes body
  | .mdata _ expression | .proj _ _ expression => 1 + expressionNodes expression

private def declarationNodes (info : ConstantInfo) : Nat :=
  expressionNodes info.type + match info.value? (allowOpaque := true) with
    | some value => expressionNodes value
    | none => 0

private def failOnMessages (messages : MessageLog) : IO Unit := do
  if messages.hasErrors then
    for message in messages.toList do
      if message.severity == .error then
        IO.eprintln (← message.data.toString)
    throw <| IO.userError "target source did not elaborate"

private def measure (path : System.FilePath) : IO Json := do
  let input ← IO.FS.readFile path
  let fileName := path.toString
  let inputContext := Parser.mkInputContext input fileName
  let (header, parserState, headerMessages) ← Parser.parseHeader inputContext
  failOnMessages headerMessages
  let options := Elab.async.set {} false
  let (initialEnvironment, importMessages) ← Elab.processHeader
    header options headerMessages inputContext (mainModule := `MathlibBonsaiMeasuredTarget)
  failOnMessages importMessages
  let commandState := Elab.Command.mkState initialEnvironment importMessages options
  let state ← Elab.IO.processCommands inputContext parserState commandState
  failOnMessages state.commandState.messages

  let syntaxTotal := state.commands.foldl (fun total command => total + syntaxNodes command)
    (syntaxNodes header.raw)
  let mut kernelTotal := 0
  for (_, info) in state.commandState.env.constants.map₂ do
    kernelTotal := kernelTotal + declarationNodes info
  return json% {
    schema : 1,
    syntaxNodes : $syntaxTotal,
    kernelExpressionNodes : $kernelTotal
  }

end MathlibBonsai.Measure

unsafe def main (arguments : List String) : IO UInt32 := do
  Lean.initSearchPath (← Lean.findSysroot)
  Lean.enableInitializersExecution
  let [path] := arguments | do
    IO.eprintln "usage: bonsai-measure FILE"
    return 2
  try
    let result ← MathlibBonsai.Measure.measure path
    IO.println s!"BONSAI_METRICS={result.compress}"
    return 0
  catch error =>
    IO.eprintln s!"measurement error: {error}"
    return 1
