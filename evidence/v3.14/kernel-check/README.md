# Kernel check: does PAIR change when the experiments run on K1 instead of K2?

K2 = SharedOS 3aa07e3 (every PAIR experiment loaded it). K1 = SharedOS c74461c (the kernel of the conformance
tables). Scripts: `scripts/kernel_check/`. Status: feasibility done; the K1 arm needs a SharedEval port beyond the
pin, which changes the evidence-validity checks, so the behavioral run waits for the authors. Option B, the kernel decision replay below, was chosen. No model call, $0 spent.

## Files

| Path | Script | What it is |
|---|---|---|
| `samples.json` | `draw_samples.py` | The pre-registered samples, seed 20261005: PAIR I 60 tasks stratified by (kind, category), PAIR II 20 of the ladder grid's 50 groups (60 tasks). |
| `feasibility/kernels.jsonl` | `build_kernels.sh`, `kernel_digests.sh` | K2 (rebuilt fresh), K1 and v1.0.0-preview: commit, tree, package versions, clean tree, and the runtime digest computed with SharedEval's own `digestSharedOsRuntimeV1`. The fresh K2 build reproduces the pinned digest. |
| `feasibility/build-logs/` | `build_kernels.sh` | Build logs (pnpm 9.15.0, `--frozen-lockfile`, the repository's `pnpm build`). |
| `feasibility/patches/e{1,3}-{k1,v1p}-pin.patch` | `setup_sharedeval.sh` | The pin patch for SharedEval 58829fe (e1) and 8081e7e (e3): runtime revision and digest in `load-sharedos.ts`, the same two values in its loader test, the image pin in `build-image.sh`. |
| `feasibility/patches/probe/` | `probe_port.sh` | Scoping probe only, never used for a measured run: step 1 accepts K1's new audit fields, step 2 switches off the tool-catalog check (a stub, not a port). |
| `feasibility/logs/test-sharedos-*.txt` | `feasibility_runs.sh` | SharedEval's real-kernel tests (`test:sharedos`) for every arm. |
| `feasibility/logs/feas-*.txt`, `feasibility/scripted_audit_counts.jsonl`, `feasibility/scripted-simple-32.yaml` | `feasibility_runs.sh`, `audit_counts.py` | End-to-end runs with SharedEval's scripted PAIR runner (no model call) on K2, K1 with the pin, K1 with probe step 1 and K1 with probe step 2; kernel audit records counted by type and outcome. |
| `feasibility/full-tests/` | `compat_tests.sh` | SharedEval's whole test list on K2 (8081e7e) and on K1 (probe steps 1 and 2). |
| `feasibility/original_configs.json` | `original_configs.py` | What produced the originals, read-only on the VM: the four PAIR I DeepSeek cells' config and image provenance, the 80 ladder-grid configs of the sampled groups (Azure endpoint host redacted) and the 40 same-route D2 control configs of the header ladder. |
| `feasibility/cost_reference.json` | `cost_reference.sh` | Provider-reported spend per PAIR II session on the gateway-to-Relace route in two earlier runs, and the kernel-check key's spend (0). |
| `feasibility/divergence.txt` | `evaluator_divergence.sh` | Lines changed between 58829fe and 8081e7e in the files a K1 port touches, and the K2-to-K1 divergence in the four loaded packages split into test and non-test files. |

`python3 scripts/kernel_check/feasibility_report.py` prints every number of the feasibility memo from these files.

## Option B: kernel decision replay (2026-10-05)

Every `authorization.checked` record in the K2 runs' audit trails is asked again of K2 and of K1 through the public
`SharedOSKernel.authorize`, over the run's recorded grants and the usage at that point (`replay_decisions.mjs`;
v1 498f11b, v2 5d585e6 adds deferred responder grants, v3 57c303b adds the sensitivity mutations). Gate: K2's
replay must reproduce the recorded decision first. No model call.

| Path | Script | What it is |
|---|---|---|
| `replay/lane-<lane>.jsonl` | `replay_lanes.sh` (v2) | One line per run folder (all attempts) of t3simple (ladder grid, the scope), pair2id2 (header comparison), pair2told (header ladder), grid600 (probing grid), pack1 and pack10 (packing): questions, recorded allowed/denied, K2 = recorded, K1 = recorded, K1 = K2, usage check, every differing question. |
| `replay/lanes.txt` | `replay_lanes.sh` | Folder and result counts per lane. |
| `replay/report.txt`, `replay/report.json` | `replay_report.py` | The gate and the comparison per study, the 80 sampled ladder sessions, and all studies together. |
| `replay/sensitivity/` | `replay_sensitivity.sh` (v3) | On the 80 sampled sessions: v3 without mutation equals v2 line for line (determinism); with K1's matched grant removed, or every bounded grant reported used up, K1 stops agreeing on every allowed question. The mutation outputs are xz-compressed. |
| `replay/tool_definitions_k2_vs_k1.json` | `compare_tool_definitions.mjs` | The kernel-supplied tool definitions SharedEval offers the model (12 file tools, messages.request), compared byte for byte. |
| `replay/denial_messages_k2_vs_k1.json` | `compare_denial_messages.py` | The code and message literals of every call to the kernel's tool and resource result builders (and `protocolError`) in each built `core/dist/kernel.js`, and the builders' own bodies, compared. |
| `replay/v1/` | `replay_ladder.py` (v1) | The first pass, over the folder analyze_s4.py chose for each ladder slot (1,346 runs). Superseded by `lane-t3simple.jsonl`; kept because it ran first. |
| `feasibility/model_view_k2_vs_k1step2.json` | `compare_model_view.py` | The scripted session on K2 and on K1 (probe step 2): every actor-context record, normalized for run-derived ids, compared. |

PAIR I's run folders are readable only by their owner on the VM, so PAIR I is not replayed.

Logs are stored as `.txt` because the repository ignores `*.log` and `build/`. Paths on the experiment VM: `<vm>/kernel-check/` (kernels, SharedEval worktrees, scripted runs).
