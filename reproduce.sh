#!/usr/bin/env bash
# Regenerate the paper's figures and generated tables from the frozen inputs under evidence/.
#
# No model is called. Every input is a frozen output of a model run, and the README next to it
# says how it was produced. The scripts that produced those inputs from the raw run artifacts
# are included for reference; the raw artifacts are not.
#
# Usage:
#   bash reproduce.sh          run every generator in dependency order
#   bash reproduce.sh --list   print "<generator><TAB><output>" for every registered output
#
# Requirements: Python 3.10 or later with matplotlib, numpy and scipy (scripts/p13/render_tables.py and
# scripts/pair_multi/ablation/table33.py need scipy).
# Exit status: 0 if every generator ran and wrote its registered outputs, 1 otherwise.
set -euo pipefail
cd "$(dirname "$0")"
export MPLBACKEND=Agg PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
# Fixed PDF dates in matplotlib output; set your own value to override.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-0}"

# One line per generator: "<script> | <outputs it must write>", in dependency order.
# Outputs are the files the paper uses; generators may write more (PNG/SVG previews).
REGISTRY=(
  "scripts/render_figures.py | figures/delegation_overview.pdf"
  "scripts/render_pair_design.py | figures/pair_multiturn/design_axes.pdf"
  "scripts/render_pair_multiturn.py | figures/pair_multiturn/context.pdf"
  "scripts/render_infra_table.py | appendix/infrastructure_cases.tex"
  "scripts/render_live_conformance.py | tables/conformance.tex"
  "scripts/single_grid/stats.py | evidence/v3.13/single-grid/stats.json"
  "scripts/single_grid/pools.py | evidence/v3.13/single-grid/pools.json"
  "scripts/single_grid/tables.py | tables/single_ladder.tex tables/single_variants.tex tables/single_crossmodel.tex tables/single_grid_deepseek.tex tables/single_grid_glm.tex tables/single_grid_gpt56.tex tables/single_grid_cross.tex tables/single_grid_delivery.tex tables/single_action_split.tex tables/single_pools_deepseek.tex tables/single_pools_glm.tex tables/single_pools_gpt56.tex tables/single_pools_ladder.tex tables/single_policy_pooled.tex"
  "scripts/single_grid/figures.py | figures/single_grid/single_delivery.pdf figures/single_grid/single_operating_points.pdf figures/single_grid/single_responder_side.pdf"
  "scripts/single_grid/ladder_combined.py | figures/single_grid/single_ladder_combined.pdf"
  "scripts/net_rerun/analyse.py | evidence/v3.13/net-rerun/net_summary.json"
  "scripts/net_world/policy_check.py | evidence/v3.14/net-world/policies/policy_check.json"
  "scripts/net_rerun/empty_policy.py | evidence/v3.14/net-rerun-audit/empty_policy.json"
  "scripts/net_rerun/render_tables.py | tables/net_results.tex tables/net_results_full.tex tables/net_strata_results.tex tables/net_delivery.tex"
  "scripts/net_rerun/render_audit_macros.py | tables/net_audit_numbers.tex"
  "scripts/pair_multi/ladder/render_tables.py | tables/pair_multi_ladder.tex tables/pair_multi_full.tex"
  "scripts/pair_multi/ablation/table33.py | tables/pair_kernel_policy.tex"
  "scripts/p13/render_tables.py | tables/p13_crossed_pooled.tex tables/p13_crossed_all.tex tables/p13_tests.tex tables/pair2_rescore.tex tables/p13_numbers.tex"
  "scripts/pair_multi/spoof/render_tables.py | tables/pair_spoof.tex tables/pair_spoof_delivery.tex tables/pair_spoof_numbers.tex tables/pair_spoof_tests.tex"
  "scripts/adjudication/render_frame_table.py | tables/adjudication_frame.tex"
  "scripts/adjudication/render_p12.py | tables/adjudication_results.tex tables/adjudication_numbers.tex"
  "scripts/p11/render_metadata.py | tables/single_metadata.tex tables/p11_numbers.tex"
  "scripts/overview/three_ladders.py | figures/overview/three_ladders.pdf"
  "scripts/pair_multi/told_ladder/render_table.py | tables/pair_told_ladder.tex"
  "scripts/pair_multi/identity_rerun/render_table.py | tables/pair_identity.tex"
  "scripts/p14/render_macros.py | tables/p14_numbers.tex"
  "scripts/author_check/score.py | tables/author_check_numbers.tex"
  "scripts/p14/agreement.py | tables/label_agreement.tex tables/label_agreement_numbers.tex"
  "scripts/single_grid/grok/table4_measure.py | evidence/v3.14/single-grid-grok/table4_measure.json"
  "scripts/single_grid/grok/render_tex.py | tables/single_grok.tex tables/grok_numbers.tex"
  "scripts/p13/sensitivity_family.py | tables/p13_sensitivity_numbers.tex"
  "scripts/pair_multi/probing_order/strategy_order.py | evidence/v3.14/probing-strategy-order/order.json"
  "scripts/pair_multi/counts.py | tables/pair_multi_numbers.tex"
  "scripts/single_grid/counts.py | tables/single_grid_numbers.tex"
  "scripts/p17/render_macros.py | tables/p17_numbers.tex"
)

trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; printf '%s' "${s%"${s##*[![:space:]]}"}"; }

if [[ "${1:-}" == "--list" ]]; then
  for entry in "${REGISTRY[@]}"; do
    gen="$(trim "${entry%%|*}")"
    for out in ${entry#*|}; do printf '%s\t%s\n' "$gen" "$out"; done
  done
  exit 0
fi

failed=0
for entry in "${REGISTRY[@]}"; do
  gen="$(trim "${entry%%|*}")"
  for out in ${entry#*|}; do mkdir -p "$(dirname "$out")"; done
  if python3 "$gen" > /dev/null; then status="ok"; else status="FAILED"; failed=1; fi
  for out in ${entry#*|}; do
    if [[ ! -s "$out" ]]; then status="FAILED (missing $out)"; failed=1; fi
  done
  printf '%-48s %s\n' "$gen" "$status"
done
exit "$failed"
