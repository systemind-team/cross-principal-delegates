# Cross-Principal Communication between Agent Delegates: code and data

This repository holds the code and the frozen data behind the numbers, figures and generated tables of the paper "Cross-Principal Communication between Agent Delegates":

- the frozen inputs behind every reported number, under `evidence/`;
- the generators that turn those inputs into the paper's figures and generated tables, under `scripts/`, run by `reproduce.sh`;
- the provenance scripts that produced the frozen inputs from the raw model runs, also under `scripts/`. The raw runs are not included.

The runs used two public repositories:

- SharedOS, the kernel the delegates run on: https://github.com/systemind-team/SharedOS
- SharedEval, the evaluation harness: https://github.com/systemind-team/SharedEval

The paper refers to their revisions as K1, K2 and E1–E4. `evidence/v3.14/provenance/revision_labels.json` maps each label to its commits in these repositories, and `evidence/v3.14/provenance/README.md` describes how each run was pinned to them. The commit ids in the manifests and notes refer to the same repositories.

## Reproduce the figures and tables

Requirements: Python 3.10 or later with matplotlib, NumPy and SciPy. SciPy is used by `scripts/p13/render_tables.py` and `scripts/pair_multi/ablation/table33.py`.

```bash
pip install matplotlib numpy scipy
bash reproduce.sh          # run every generator in dependency order
bash reproduce.sh --list   # print which script writes which file
```

`reproduce.sh` runs each generator in dependency order. The generators write the paper's figures to `figures/`, its generated tables to `tables/` and one appendix table to `appendix/`. A few of them recompute frozen summaries under `evidence/` (for example `evidence/v3.13/net-rerun/net_summary.json`) and overwrite them in place; `git status` shows whether any of them changed. The script sets `SOURCE_DATE_EPOCH=0` unless you set it, so the PDF figures carry a fixed date. It exits with status 0 only if every generator ran and wrote its registered outputs. No model is called.

Before release, the export script ran `reproduce.sh` on this copy and compared every registered output with the copy committed for the paper. All were byte-identical, with Python 3.14.6, matplotlib 3.10.9, NumPy 2.4.3 and SciPy 1.17.1. matplotlib records its version in each PDF, so other versions write PDF figures whose bytes differ.

The generated tables use the macro `\SharedOS`. To typeset a table outside the paper, define it, for example `\newcommand{\SharedOS}{SharedOS}`.

### What is rerun and what is not

`reproduce.sh` reruns every figure and generated table of the paper, and the summaries they read, from the frozen inputs under `evidence/`.

It does not rerun:

- The model runs. Every input under `evidence/` is a frozen output of a model run. Rerunning the runs needs provider accounts and SharedEval at the revisions recorded in the manifests.
- The LLM coders, judges and reviewers. Their outputs are frozen with the runs.
- The provenance scripts. They turned the raw run artifacts into the frozen inputs, and the raw artifacts are not included. The README or manifest in each evidence folder names the script and input behind each file.
- The paper itself. Its LaTeX sources are not part of this archive.

## Layout

| Path | What it holds |
|---|---|
| `reproduce.sh` | Runs the generators; `--list` prints each generator's outputs. |
| `scripts/` | Generators (called by `reproduce.sh`) and provenance scripts (run on the raw artifacts, which are not included). |
| `evidence/v3.13/single-grid/` | PAIR I (single-request grid): merged cells, statistics, diagnostic scans, policy texts, and the 529-trace review sample with the LLM reviewer's verdicts and the author verdicts. |
| `evidence/v3.13/multi-table3/` | PAIR II ladder grid: per-block rates, the refusal-channel rescore, provider filter losses, and the scripts that produced them. |
| `evidence/v3.13/multi-probing/`, `multi-identity/`, `multi-told/` | PAIR II probing grid, header comparison and header ladder. |
| `evidence/v3.13/net-rerun/` | NET pilot: one row per exchange and per judged reply. `scripts/net_rerun/analyse.py` recomputes every NET number from these two files. |
| `evidence/v3.14/` | Further frozen results, each folder with a README naming its script. The benchmark data are in `pair-dataset/` and `net-world/`. |
| `evidence/live_conformance/`, `evidence/kernel_conformance.source.json` | Conformance artifacts behind Appendix B. |
| `evidence/v3.1/.../relationship_label_matrix_v2.json` | PAIR's per-requester relationship labels (version 2.0.0-rc1); the manifests record its digest. |
| `evidence/v3/prompts/` | The D1 and D2 policy texts quoted in Appendix D. |
| Other files directly under `evidence/` | Source records and manifests for the runtime, the systems cost, the notes scope and the figures. |
| `DATASHEET.md` | The datasheet for the benchmark data. |
| `LICENSE`, `LICENSE-DATA` | The code and data licenses. |

Each evidence folder has a README or manifest that names the script and input behind each file.

Six analyses keep a short label in folder, file and data-key names (for example `evidence/v3.14/coding-p1-3/` and the task keys of `evidence/v3.14/author-check/`), and the notes and scripts use the same labels: P1-1 is the metadata-leak check, P1-2 the adjudication of sampled replies, P1-3 the policy-match coding, P1-4 the public relabel of work questions, P1-6 the impersonation runs, and P2-3 the adaptive-attacker design. They are names only.

The 529-trace review's verdict files do not record the reviewer's model. Claude Fable 5.1 is taken from the co-author line of the commit that added the verdicts; the repository history is not part of this archive.

## What is not included

- Raw run artifacts: per-session workspaces, message logs and provider responses. Some inputs are too large or hold provider metadata, so they are frozen as summaries; the single-request grid's per-task rows are frozen in `evidence/v3.14/single-grid-tasks/`. The provenance scripts document how each summary was made.
- Two records that name people: the coder agents' session transcripts and the verbatim chat record of the author spot checks. The parsed answers (`evidence/v3.14/author-check/answers.json`) stand in for the record, and `scripts/author_check/score.py` computes the same numbers from them.
- Two tests of the adaptive-attacker design, `scripts/pair_multi/spoof/adaptive/test_prompt_scrub.py` and `test_export_scrub.py`. They check the design's frozen prompts and the exported files for internal references, so they quote the strings they look for, and they reproduce no result. `pre_pilot_checks.sh` in the same folder still calls them.

## What was changed in this copy

The archive was exported from the paper's repository by the authors' export script. The system names, the dataset names, the links to SharedOS and SharedEval and their commit ids are as in the repository. Links that used the two repositories' earlier GitHub address were changed to the addresses given above, to which the earlier ones redirect.

Local paths, account names, host names, public network addresses, credential identifiers, e-mail addresses and the names of private repositories were replaced by placeholders such as `<external>`, `<vm>`, `<user>`, `<host>`, `<ip>`, `<key-id>`, `<repository>`, `<private-repository>` and `<internal>`. Notes from the authors' internal review of the analyses (who reviewed or decided what, and when) were removed from the documentation, the scripts and the metadata the scripts write; what was fixed before each run, and how, is unchanged. The same rules apply inside compressed files, which are decompressed, rewritten and recompressed. Placeholders replace strings and never values, so no number or label changed. Where a frozen file was rewritten this way, the manifests and scripts that record its checksum carry the new one.

## Licenses

The code (`reproduce.sh` and `scripts/`) is released under the MIT License (`LICENSE`). The data under `evidence/` is released under the Creative Commons Attribution 4.0 International License, CC BY 4.0 (`LICENSE-DATA`).

## Datasheet

`DATASHEET.md` documents the benchmark data: what it holds, how it was written and labeled, its intended and unintended uses, its distribution and its maintenance.

## Issues

Questions and error reports go to this repository's GitHub issues. Corrections and updates are published as tagged releases.

## Citation

```bibtex
@misc{crossprincipal2026,
  title = {Cross-Principal Communication between Agent Delegates},
  year  = {2026},
  note  = {[arXiv link to be added]}
}
```
