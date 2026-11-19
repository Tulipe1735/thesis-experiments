---- MODULE RunLifecycle ----
\* Run lifecycle of experiments/grow_up_harness_v2/calibration/tabletop.py after prepare:
\* kernel(), negative(), start_physical(), report(), and the first line of harness/kernel.py
\* execute(), out.mkdir(exist_ok=False). One action is one step of that code; the process
\* can be interrupted between any two steps, and the operator may rerun `kernel` or run
\* `report` whenever no command is running. Every row is ready (initial fixture valid).
\* The row loop runs every registered arm of a row in config order (engineering, then agent);
\* one loop step is one (row, arm) episode. A brain session opens before the row loop.
EXTENDS Naturals, Sequences

CONSTANTS Small, Cap

Tmpl == IF Small THEN <<"A">> ELSE <<"A", "A", "B">>   \* template of each row of tasks.json
TSeq == IF Small THEN <<"A">> ELSE <<"A", "B">>        \* templates in first-row order
N == Len(Tmpl)
FirstRow(t) == CHOOSE i \in 1..N : Tmpl[i] = t /\ \A j \in 1..(i - 1) : Tmpl[j] # t
TIdx(t) == CHOOSE k \in 1..Len(TSeq) : TSeq[k] = t
Neg(k) == <<FirstRow(TSeq[k]), "negative">>
Arms == <<"engineering", "agent">>                   \* config arms, in order
M == N * Len(Arms)                                   \* episodes of the row loop
RowOf(e) == (e - 1) \div Len(Arms) + 1
ArmOf(e) == Arms[((e - 1) % Len(Arms)) + 1]
Ep(e) == <<RowOf(e), ArmOf(e)>>
EpKeys == {Ep(e) : e \in 1..M}

VARIABLES
    pc,          \* "idle" | "open" (kernel() reads events) | "neg" | "session" | "eng" | "final" (kernel cmd's report)
    sub,         \* step inside the current negative() or row
    cur,         \* template index in the negative loop, episode index (row, arm) in the row loop
    snap,        \* `done` read from events.jsonl when kernel() starts
    dirs,        \* episodes/<id>/<arm> folders on disk
    results,     \* episodes/<id>/<arm>/result.json on disk
    started,     \* physical_started events
    completed,   \* physical_completed events
    invalid,     \* a batch_invalid event exists
    charges,     \* number of physical_started events
    reportOut,   \* report.json exists
    reportBody,  \* episodes report.json counted
    finished,    \* the kernel command returned normally
    startedTwice, blocked, afterInvalid, engBeforeNeg, reportRejected   \* rule witnesses

vars == <<pc, sub, cur, snap, dirs, results, started, completed, invalid, charges, reportOut, reportBody,
          finished, startedTwice, blocked, afterInvalid, engBeforeNeg, reportRejected>>
disk == <<dirs, results, started, completed, invalid, charges, reportOut, reportBody>>
witnesses == <<startedTwice, blocked, afterInvalid, engBeforeNeg, reportRejected>>

Init ==
    /\ pc = "idle" /\ sub = "none" /\ cur = 0 /\ snap = {}
    /\ dirs = {} /\ results = {} /\ started = {} /\ completed = {} /\ invalid = FALSE /\ charges = 0
    /\ reportOut = FALSE /\ reportBody = {} /\ finished = FALSE
    /\ startedTwice = FALSE /\ blocked = FALSE /\ afterInvalid = FALSE /\ engBeforeNeg = FALSE
    /\ reportRejected = FALSE

Raise == pc' = "idle" /\ sub' = "none" /\ UNCHANGED <<cur, snap>>

\* `tabletop.py kernel RUN`.
OperatorRunsKernel ==
    /\ pc = "idle" /\ ~finished
    /\ pc' = "open" /\ sub' = "none" /\ cur' = 0 /\ snap' = completed
    /\ UNCHANGED <<disk, finished, witnesses>>

\* `tabletop.py report RUN` by hand. It writes only once the batch has ended (void, or every
\* row completed); before that it prints PARTIAL, and with report.json present it is a no-op or
\* an error, so neither changes state.
OperatorRunsReport ==
    /\ pc = "idle" /\ ~reportOut /\ (invalid \/ EpKeys \subseteq completed)
    /\ reportOut' = TRUE /\ reportBody' = results \cap EpKeys
    /\ UNCHANGED <<pc, sub, cur, snap, dirs, results, started, completed, invalid, charges, finished, witnesses>>

Interrupted ==
    /\ pc # "idle"
    /\ Raise
    /\ UNCHANGED <<disk, finished, witnesses>>

\* kernel() start: a void batch stops; a started-but-not-completed episode voids the batch.
BatchAlreadyVoid ==
    /\ pc = "open" /\ invalid
    /\ Raise
    /\ UNCHANGED <<disk, finished, witnesses>>
InterruptedEpisodeVoids ==
    /\ pc = "open" /\ ~invalid /\ ~(started \subseteq completed)
    /\ invalid' = TRUE /\ Raise
    /\ UNCHANGED <<dirs, results, started, completed, charges, reportOut, reportBody, finished, witnesses>>
LogIsClean ==
    /\ pc = "open" /\ ~invalid /\ started \subseteq completed
    /\ pc' = "neg" /\ sub' = "next" /\ cur' = 1
    /\ UNCHANGED <<snap, disk, finished, witnesses>>

\* negative(): start_physical(); out.mkdir(exist_ok=False); 10 waits; verdict.
NegSkip ==
    /\ pc = "neg" /\ sub = "next" /\ cur <= Len(TSeq) /\ Neg(cur) \in snap
    /\ cur' = cur + 1
    /\ UNCHANGED <<pc, sub, snap, disk, finished, witnesses>>
NegBegins ==
    /\ pc = "neg" /\ sub = "next" /\ cur <= Len(TSeq) /\ Neg(cur) \notin snap
    /\ sub' = "start"
    /\ UNCHANGED <<pc, cur, snap, disk, finished, witnesses>>
NegLoopDone ==
    /\ pc = "neg" /\ sub = "next" /\ cur > Len(TSeq)
    /\ pc' = "session" /\ sub' = "none"
    /\ UNCHANGED <<cur, snap, disk, finished, witnesses>>

\* brain_session(): a fresh numbered folder and workspace, then the private server; it can fail to start.
SessionOpens ==
    /\ pc = "session"
    /\ pc' = "eng" /\ sub' = "check" /\ cur' = 1
    /\ UNCHANGED <<snap, disk, finished, witnesses>>
SessionFails ==
    /\ pc = "session"
    /\ Raise
    /\ UNCHANGED <<disk, finished, witnesses>>
NegDirCreated ==
    /\ pc = "neg" /\ sub = "mkdir" /\ Neg(cur) \notin dirs
    /\ dirs' = dirs \cup {Neg(cur)} /\ sub' = "wait"
    /\ UNCHANGED <<pc, cur, snap, results, started, completed, invalid, charges, reportOut, reportBody,
                   finished, witnesses>>
NegDirExists ==
    /\ pc = "neg" /\ sub = "mkdir" /\ Neg(cur) \in dirs
    /\ blocked' = TRUE /\ Raise
    /\ UNCHANGED <<disk, finished, startedTwice, afterInvalid, engBeforeNeg, reportRejected>>

\* start_physical(): raise on spent budget, else log physical_started.
Key == IF pc = "neg" THEN Neg(cur) ELSE Ep(cur)
BudgetSpent ==
    /\ pc \in {"neg", "eng"} /\ sub = "start" /\ charges >= Cap
    /\ Raise
    /\ UNCHANGED <<disk, finished, witnesses>>
PhysicalStarted ==
    /\ pc \in {"neg", "eng"} /\ sub = "start" /\ charges < Cap
    /\ charges' = charges + 1
    /\ started' = started \cup {Key}
    /\ startedTwice' = (startedTwice \/ Key \in started)
    /\ afterInvalid' = (afterInvalid \/ invalid)
    /\ engBeforeNeg' = (engBeforeNeg \/ (pc = "eng" /\ Neg(TIdx(Tmpl[RowOf(cur)])) \notin completed))
    /\ sub' = IF pc = "neg" THEN "mkdir" ELSE "exec"
    /\ UNCHANGED <<pc, cur, snap, dirs, results, completed, invalid, reportOut, reportBody, finished,
                   blocked, reportRejected>>

WaitRejected ==
    /\ pc = "neg" /\ sub = "wait"
    /\ invalid' = TRUE /\ Raise
    /\ UNCHANGED <<dirs, results, started, completed, charges, reportOut, reportBody, finished, witnesses>>
WaitDone ==
    /\ pc = "neg" /\ sub = "wait"
    /\ sub' = "verdict"
    /\ UNCHANGED <<pc, cur, snap, disk, finished, witnesses>>
NegativeSatisfiesGoal ==
    /\ pc = "neg" /\ sub = "verdict"
    /\ invalid' = TRUE /\ Raise
    /\ UNCHANGED <<dirs, results, started, completed, charges, reportOut, reportBody, finished, witnesses>>
NegativePasses ==
    /\ pc = "neg" /\ sub = "verdict"
    /\ completed' = completed \cup {Neg(cur)} /\ cur' = cur + 1 /\ sub' = "next"
    /\ UNCHANGED <<pc, snap, dirs, results, started, invalid, charges, reportOut, reportBody, finished, witnesses>>

\* Row loop over (row, arm): skip done, start_physical(), execute(), checks.
RowsDone ==
    /\ pc = "eng" /\ sub = "check" /\ cur > M
    /\ pc' = "final" /\ sub' = "none"
    /\ UNCHANGED <<cur, snap, disk, finished, witnesses>>
RowSkip ==
    /\ pc = "eng" /\ sub = "check" /\ cur <= M /\ Ep(cur) \in snap
    /\ cur' = cur + 1
    /\ UNCHANGED <<pc, sub, snap, disk, finished, witnesses>>
RowBegins ==
    /\ pc = "eng" /\ sub = "check" /\ cur <= M /\ Ep(cur) \notin snap
    /\ sub' = "start"
    /\ UNCHANGED <<pc, cur, snap, disk, finished, witnesses>>
ExecDirExists ==
    /\ pc = "eng" /\ sub = "exec" /\ Ep(cur) \in dirs
    /\ blocked' = TRUE /\ Raise
    /\ UNCHANGED <<disk, finished, startedTwice, afterInvalid, engBeforeNeg, reportRejected>>
EpisodeRuns ==
    /\ pc = "eng" /\ sub = "exec" /\ Ep(cur) \notin dirs
    /\ dirs' = dirs \cup {Ep(cur)} /\ sub' = "saved"
    /\ UNCHANGED <<pc, cur, snap, results, started, completed, invalid, charges, reportOut, reportBody,
                   finished, witnesses>>
ResultSaved ==
    /\ pc = "eng" /\ sub = "saved"
    /\ results' = results \cup {Ep(cur)} /\ sub' = "log"
    /\ UNCHANGED <<pc, cur, snap, dirs, started, completed, invalid, charges, reportOut, reportBody,
                   finished, witnesses>>
InitialStateMismatch ==
    /\ pc = "eng" /\ sub = "log"
    /\ invalid' = TRUE /\ Raise
    /\ UNCHANGED <<dirs, results, started, completed, charges, reportOut, reportBody, finished, witnesses>>
EpisodeLogged ==
    /\ pc = "eng" /\ sub = "log"
    /\ completed' = completed \cup {Ep(cur)} /\ sub' = "syserr"
    /\ UNCHANGED <<pc, cur, snap, dirs, results, started, invalid, charges, reportOut, reportBody,
                   finished, witnesses>>
SystemExecutionFailure ==
    /\ pc = "eng" /\ sub = "syserr"
    /\ invalid' = TRUE /\ Raise
    /\ UNCHANGED <<dirs, results, started, completed, charges, reportOut, reportBody, finished, witnesses>>
NextRow ==
    /\ pc = "eng" /\ sub = "syserr"
    /\ cur' = cur + 1 /\ sub' = "check"
    /\ UNCHANGED <<pc, snap, disk, finished, witnesses>>

\* The kernel command's report(run) after kernel(run) returns.
FinalReportWritten ==
    /\ pc = "final"
    /\ \/ ~reportOut /\ reportOut' = TRUE /\ reportBody' = results \cap EpKeys
       \/ reportOut /\ reportBody = results \cap EpKeys /\ UNCHANGED <<reportOut, reportBody>>
    /\ finished' = TRUE /\ Raise
    /\ UNCHANGED <<dirs, results, started, completed, invalid, charges, witnesses>>
FinalReportRefused ==
    /\ pc = "final" /\ reportOut /\ reportBody # results \cap EpKeys
    /\ reportRejected' = TRUE /\ Raise
    /\ UNCHANGED <<disk, finished, startedTwice, blocked, afterInvalid, engBeforeNeg>>

Done == finished /\ pc = "idle" /\ UNCHANGED vars

Next ==
    \/ OperatorRunsKernel \/ OperatorRunsReport \/ Interrupted
    \/ BatchAlreadyVoid \/ InterruptedEpisodeVoids \/ LogIsClean
    \/ NegSkip \/ NegBegins \/ NegLoopDone \/ NegDirCreated \/ NegDirExists \/ SessionOpens \/ SessionFails
    \/ BudgetSpent \/ PhysicalStarted
    \/ WaitRejected \/ WaitDone \/ NegativeSatisfiesGoal \/ NegativePasses
    \/ RowsDone \/ RowSkip \/ RowBegins
    \/ ExecDirExists \/ EpisodeRuns \/ ResultSaved \/ InitialStateMismatch \/ EpisodeLogged
    \/ SystemExecutionFailure \/ NextRow
    \/ FinalReportWritten \/ FinalReportRefused
    \/ Done

Spec == Init /\ [][Next]_vars

\* Rules the operator relies on (AGENTS.md, run prompts, 2026-11-15 interruption policy).
WithinBudget == charges <= Cap
NoPhysicsAfterVoid == ~afterInvalid               \* no physical_started once batch_invalid exists
NegativeControlFirst == ~engBeforeNeg             \* any arm's episode only after its template's negative passed
NoEpisodeStartedTwice == ~startedTwice            \* an interrupted episode is never rerun
RerunNeverStuck == ~blocked                       \* a rerun never fails on an existing episode folder
FinishedBatchIsClean == finished => started = completed   \* a finished batch lost no started episode
FinalReportAlwaysWritten == ~reportRejected       \* a finished batch always gets its report
FinishedReportCoversAllRows == finished => reportBody = EpKeys   \* every row, every arm
====
