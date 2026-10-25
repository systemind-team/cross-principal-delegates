# Literal-verdict coding (data key P1-3): packets, key and codes

- `PREREGISTRATION.md`: the design, the test and the decision rule, committed before any annotator saw a packet.
- `packets/{A,B}/`: the two annotators' packets (same lines and codes, different order), `INSTRUCTIONS.md`, and answer
  templates in `answers/`. `packets/MANIFEST.json`: sha256 of every packet file and of the hidden key.
- `key/key-P1-3.json`: the hidden key (code → packet, requester, task; planted answers). Not committed until both
  annotators have returned their answers.
- `rule_codes.json`: the deterministic rule coder's verdicts (`scripts/coding/rule_coder.py`; first version without the
  public flag of the public/internal task).
- `answers/{A,B}/` (after coding): the annotators' returned files, copied unchanged from their release folders.

Regenerate packets and key: `python3 scripts/coding/make_packets.py` (deterministic; `--release DIR` also copies the packets
to the coders' release folder).
