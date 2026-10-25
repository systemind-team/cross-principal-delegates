# Datasheet: the PAIR and NET benchmark data

This datasheet follows the questions of "Datasheets for Datasets" (Gebru et al., 2021), in its seven sections. Every fact comes from a file in this archive or from a decision the authors recorded; the file is named where it matters. The funding field is left for the authors to fill.

## 1. Motivation

- **Purpose.** To measure how an agent that answers for its owner (the delegate) treats requests from agents acting for other people. A good delegate gives each requester what that requester may have and withholds the rest. The benchmark scores leak and false refusal per requester and checks requested actions against the workspace state.
- **Design.** The data pair one owner's workspace with requesters in several relationships. The same question can therefore be permitted for one requester and protected for another, and leak and false refusal can both be scored.
- **Creators.** The authors of the paper.
- **Funding.** `[AUTHORS: funding]`

## 2. Composition

**PAIR** (one owner, five requester personas; `evidence/v3.14/pair-dataset/`, README there):
- **Owner workspace** (`alex_data_store.json`): a fictional co-founder and CTO with 100 notes and 150 to-dos (the store defines 11 note folders and 8 to-do folders), spanning work and personal life.
- **Questions** (`questions.json`, data version 6): 400. Questions 1–200 are answered from notes, 201–400 from to-dos. Each has gold facts (1 to 6, 1,109 in all) and a minimum-correct rule.
  - Categories: work_public 200, sensitive_work 60, personal_relationships 51, personal_finance 49, personal_health 40.
- **Actions** (same file): 200, half on notes and half on to-dos (112 edits, 79 creations, 9 completions).
  - 100 are authorized (expected verdict execute).
  - 100 are refused for every requester.
  - Each has a state check on the workspace.
- **Requesters**: five personas.
  - R0 a stranger, R1 a colleague, R2 the CEO's executive assistant, R3 a close friend, R4 an investor.
  - Every experiment uses R0–R3; R4 is labeled but enters no experiment.
- **Two label sets.**
  - Category labels: the category of each question in `questions.json`, the same for every requester.
  - Relationship labels: `evidence/v3.1/.../relationship_label_matrix_v2.json`, version 2.0.0-rc1. Each question is protected (P) or legitimate (L) for each of R0–R4, and each action is execute or refuse for each of them.
- **Policies** (`policies/`): the 31 frozen policy texts the runs used.
  - PAIR I: D0–D6 for R0–R3, 28 files.
  - PAIR II: the ladder's D1 and D2, and the principles text of the identity runs.

**NET** (a 60-agent world; `evidence/v3.14/net-world/`, README and `counts.json` there):
- **Agents and contacts**: 60 agents and 402 directed contact links (6.7 per holder).
- **Access matrix**: 2,010 cells, labeled L 504, P 1,331 and B 175.
- **Tasks**: 166, with 3.93 seated agents on average and never fewer than 3.
- **Forbidden edges**: 136 fact-level edges. 81 name an agent and 55 an audience class.
- **The reported pilot**: 24 paired edges, each with a forbidden and a permitted requester (`paired_edges_24.json`).
- **Files shipped**: the 105 world files these counts come from (tasks, access matrix, contact graph, each agent's `systems.json`, the holders' `data.json`).

**Data-quality notes:**
- **Instances**: all are synthetic. Each instance is a question or action with its gold, or a NET edge with its holder and requesters.
- **Missing information**: every question has gold facts and every action a state check. In NET, one fact holder ships no `data.json` (`net-world/README.md`).
- **Splits**: none. Every study uses the full task set, or a subset the paper states.
- **Label issues**: these are reported in the paper, not fixed in the data.
  - The annotators saw each item's category.
  - Some public material is labeled protected for some requesters. A public relabel (S3) is analyzed beside the original labels (`evidence/v3.14/labels/README.md`).
  - Agreement is low for some requester and category cells (Section 4).
- **Self-contained**: yes. Using the data needs no external resource.
- **Sensitive content**: everything sensitive is synthetic. That includes health, financial and family details, HR and compensation records, and in NET a patient with a medical record number.
- **Real people**: no record describes a real person. The person names in NET's notes are invented (authors' decision).
- **Real organizations**: a few real organization names appear as scenery in the synthetic workspace, and every fact attached to them is invented. The authors kept the names (2026-10-05), so the released text is the text the models saw.

## 3. Collection process

- **How the data were written.** The authors wrote the synthetic workspace, personas, tasks and NET world by hand and with Claude Opus (Anthropic), and reviewed them. The paper's AI-use statement discloses this.
- **Sampling.** None. The data are constructed; nothing was collected from people.
- **Who was involved.** Only the authors. There were no external participants, no recruitment and no payment. No external human subjects were involved, so no ethics-board review was needed.
- **Timeframe.** The relationship labels come from an annotation campaign in 2026-08. The frozen files record the revisions they were copied from (`pair-dataset/README.md`, `net-world/sources.json`).

## 4. Preprocessing, cleaning and labeling

**Relationship labels** (`evidence/v3.14/labels/`, README there):
- **The passes.** Five annotation passes by co-authors (A1–A4 and E) covered 2,005 cells: 301 questions and 100 authorized actions, each for R0–R4. The annotators worked from written guidelines (`instructions_v2.md`) after a calibration round.
  - Each label is the majority of the five passes, with ties resolved to protect or refuse.
  - AI assistance drafted labels for the expanded item set and checked their consistency, including a single pre-labeling pass by Claude Fable 5. The annotating author reviewed every label.
- **Cells outside the passes.**
  - Questions 101–200 (except 125) were transcribed from an earlier matrix, version 1.1 (`pair-dataset/relationship_label_matrix_v1.1.json`). Its 39 borderline cells were resolved to protect by a rule fixed in advance.
  - The 100 actions refused for everyone are refuse for every requester.
- **Agreement** (`agreement.json`, Fleiss' κ):
  - over R0–R3, the requesters the experiments use: 0.708 on questions and 0.739 on actions;
  - with R4: 0.587 and 0.764;
  - per requester, per category, and Gwet's AC1: in the README.
- **Variants.** S1–S6 drop or change named groups of cells (for example S5, the majority of the four passes without E). The analyses report them as sensitivity checks.

**Coding of model outputs.**
- **Coders.** Two LLM coders (`claude-sonnet-5-5` and `claude-fable-5-1`) coded four things:
  - whether the policy text permits each item (`evidence/v3.14/coding-p1-3/`);
  - whether work questions are public or internal (`coding-p1-4/`);
  - whether sampled replies convey protected facts (`adjudication/`);
  - whether sampled metadata matches reveal the owner's records (`metadata/`).
- **Checks on the coders.**
  - A deterministic rule coder checks the policy match.
  - Planted items with known codes check each coder: 10, 12, 40 and 20 per task, in the order above.
  - An LLM adjudicator (Claude Haiku 4.5) settles the sampled replies whose two labels differ.
- **Author spot checks** (`evidence/v3.14/author-check/`): an author checked 50 coded items blind, across the four tasks. A second author checked 20 of them, on the policy match and the public or internal status.
- **How the paper reports them.** The coders' agreement with each other and with these spot checks, never as human annotation.

**What was changed in this copy.**
- Nothing in the frozen data files was edited.
- This public copy replaces strings and never values: paths, account and host names, network addresses, credential identifiers, e-mail addresses and the names of private repositories (`README.md`, What was changed in this copy). The system and dataset names and the source-control revisions are kept.
- **Withheld**: the coder agents' session transcripts, and the verbatim record of the author spot checks. Both name people. `scripts/author_check/score.py` scores the parsed answers (`answers.json`) and gives the same numbers.

## 5. Uses

- **Used for**: the paper's PAIR I, PAIR II and NET studies.
- **Intended**: evaluating delegates, and their policies, instructions and runtimes, on what they disclose to and do for each requester; comparing scoring instruments (string matcher, LLM judge, LLM coders).
- **Not intended**:
  - training models to extract information from agents;
  - treating the category labels as labels that depend on the requester;
  - treating either label set as a standard of what is appropriate for real people.
- **Dual use.** The prober's five follow-up strategies are fixed templates designed to elicit protected information. They are released so that defenses can be tested against a reproducible attack.
- **Limits.**
  - One synthetic workspace, with one persona per relationship, in English. NET's task file also gives each of its 166 tasks in Chinese (`ask_zh`, `freq_zh`, `why_zh`), and a few internal notes in the frozen records are in Chinese.
  - Each question is scored on its listed protected facts.
  - NET's 24 paired edges are a pilot.

## 6. Distribution

- **Public location**: https://github.com/systemind-team/cross-principal-delegates. The archive is built from the paper's repository by the authors' export script.
- **Licenses**: the code (`reproduce.sh` and `scripts/`) under the MIT License (`LICENSE`); the data under `evidence/` under CC BY 4.0 (`LICENSE-DATA`).
- **Restrictions**: no third-party restriction is known on the released files.

## 7. Maintenance

- **Maintainer and contact**: the authors, through this repository's GitHub issues (https://github.com/systemind-team/cross-principal-delegates/issues).
- **Errata and updates**: errors are reported as issues in this repository, and corrections and updates are published as tagged releases of this repository.
- **Versions**: each release can be tied to its data version (`questions.json` version 6; label matrix 2.0.0-rc1) and to the file digests in the archive's manifests.
