# grape_pipeline golden model

Frozen Python reference for the scoreboard. It must **wrap** the benchmark code in
`benchmarks/bm_nbody` (import and instrument it; never re-implement the algorithm here).

This directory is hook-protected: edits are denied by the PreToolUse hook (see hw/FLOW.md);
change only on explicit user request.
