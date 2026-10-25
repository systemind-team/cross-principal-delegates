#!/usr/bin/env python3
"""Route-name normalization test (host, pilot round). The pinned upstream is an OpenRouter provider slug; the
served name SharedEval records is OpenRouter's display name. delivery_adaptive.py and extract_adaptive_vm.py
must normalize identically, or a session could pass one check and fail the other. No model calls.

Usage: python3 scripts/pair_multi/spoof/adaptive/test_route_names.py
"""
import ast
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import delivery_adaptive as da # noqa: E402


def extractor_table():
    tree = ast.parse((HERE / "extract_adaptive_vm.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "PROVIDER_ALIASES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit("extract_adaptive_vm.py has no PROVIDER_ALIASES")


def main():
    ex = extractor_table()
    assert ex == da.PROVIDER_ALIASES, ("alias tables differ", ex, da.PROVIDER_ALIASES)
    cases = [("Google AI Studio", "google-ai-studio", True), ("google-ai-studio/flex", "google-ai-studio", True),
             ("Google", "google-ai-studio", False), ("Google Vertex", "google-ai-studio", False),
             ("Relace", "Relace", True), (None, "Relace", False), ("Baidu", "Relace", False)]
    for rec, pin, want in cases:
        assert da.on_pin(rec, pin) is want, (rec, pin, want)
    print(f"route-name ok: the two alias tables are identical; {len(cases)} display-name/slug cases behave as pinned")


if __name__ == "__main__":
    main()
