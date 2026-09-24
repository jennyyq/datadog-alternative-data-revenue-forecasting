"""
Tests for agent_obs_catalyst_framework.py - the tiered pricing calculator and the catalyst-state rule.
Run: python test_agent_obs_catalyst_framework.py
"""
import agent_obs_catalyst_framework as F

# ---------------------------------------------------------------- tiered pricing calculator
def test_free_tier_is_zero_cost_and_no_overage():
    b = F.tiered_monthly_bill(10_000)
    assert b["known_monthly_usd"] == 0.0 and b["spans_in_unpriced_overage"] == 0.0
    b2 = F.tiered_monthly_bill(40_000)          # exactly at the free boundary
    assert b2["known_monthly_usd"] == 0.0

def test_pro_flat_fee_up_to_included_cap_regardless_of_exact_usage():
    """Datadog's Pro plan is a FLAT fee up to 100K spans - 50K and 100K customers pay the same $160, and this
    must never be computed as if price scaled linearly with usage within the included volume."""
    b_low = F.tiered_monthly_bill(50_000)
    b_high = F.tiered_monthly_bill(100_000)
    assert b_low["known_monthly_usd"] == b_high["known_monthly_usd"] == 160.0
    assert b_low["spans_in_unpriced_overage"] == 0.0 and b_high["spans_in_unpriced_overage"] == 0.0

def test_overage_spans_are_flagged_unpriced_not_multiplied_by_a_rate():
    b = F.tiered_monthly_bill(300_000)
    assert b["known_monthly_usd"] == 160.0                    # still just the Pro base fee
    assert b["spans_in_unpriced_overage"] == 200_000           # the excess, reported as a COUNT, never priced
    assert "NOT public" in b["plan"] or "overage" in b["plan"].lower()

def test_scenario_table_never_invents_an_overage_dollar_figure():
    import pandas as pd
    sens = pd.read_csv("outputs/agent_obs_sensitivity.csv")
    over_rows = sens[sens.Additional_spans_per_year_in_unpriced_overage_zone > 0]
    assert len(over_rows) > 0                                  # at least one scenario does cross into overage
    assert (over_rows.Overage_revenue_USD.str.contains("UNKNOWABLE")).all()   # and none of them price it

def test_scenario_A_and_B_known_annual_matches_hand_calc():
    import pandas as pd
    sens = pd.read_csv("outputs/agent_obs_sensitivity.csv")
    a = sens.iloc[0]; b = sens.iloc[1]
    assert a.Known_illustrative_annual_revenue_USD == 1000 * 160 * 12     # 1,000 customers x $160 x 12
    assert b.Known_illustrative_annual_revenue_USD == 1000 * 160 * 12     # same: flat fee, both within/at the cap
    assert a.Additional_spans_per_year_in_unpriced_overage_zone == 0
    assert b.Additional_spans_per_year_in_unpriced_overage_zone == 0

def test_scenario_D_overage_span_count_matches_hand_calc():
    import pandas as pd
    sens = pd.read_csv("outputs/agent_obs_sensitivity.csv")
    d = sens.iloc[3]                                            # scenario D: 1,000 customers, 500K spans/mo
    expected_overage_per_year = (500_000 - 100_000) * 12 * 1000
    assert d.Additional_spans_per_year_in_unpriced_overage_zone == expected_overage_per_year


# ---------------------------------------------------------------- catalyst-state classification
def test_ahead_requires_all_three_dimensions_positive():
    state, reason = F.classify_state("accelerating", "accelerating", "accelerating")
    assert state == "AHEAD"
    state2, _ = F.classify_state("accelerating", "strong_stable", "strong_stable")
    assert state2 == "AHEAD"                                    # strong_stable also qualifies, per the rule

def test_behind_triggers_on_any_single_decelerating_dimension():
    assert F.classify_state("decelerating", "accelerating", "accelerating")[0] == "BEHIND"
    assert F.classify_state("accelerating", "decelerating", "accelerating")[0] == "BEHIND"
    assert F.classify_state("accelerating", "accelerating", "decelerating")[0] == "BEHIND"

def test_in_line_when_a_dimension_is_unknown_rather_than_decelerating():
    state, reason = F.classify_state("accelerating", "accelerating", "unknown")
    assert state == "IN LINE"                                   # NOT "AHEAD" - unknown must not be treated as positive
    assert "unknown" in reason.lower() or "undisclosed" in reason.lower()

def test_decelerating_outranks_unknown_elsewhere():
    state, _ = F.classify_state("decelerating", "unknown", "accelerating")
    assert state == "BEHIND"                                    # decelerating is decisive regardless of other dims

def test_real_quarterly_reads_table_has_no_gaps_and_matches_classifier():
    for _, row in F.reads_df.iterrows():
        s, r = F.classify_state(row.Customer_adoption_trend, row.Usage_growth_trend, row.AI_penetration_trend)
        assert s == row.State, (row.Quarter, s, row.State)
    assert F.CURRENT_STATE in ("AHEAD", "IN LINE", "BEHIND")


# ---------------------------------------------------------------- output files sanity
def test_timeline_csv_has_no_fabricated_quarters_and_correct_columns():
    import pandas as pd
    t = pd.read_csv("outputs/agent_obs_verified_timeline.csv")
    assert list(t.columns) == ["Date", "Metric", "Value", "Context", "Source_URL", "Source_Tier", "Stock_or_Flow", "Interpretation"]
    assert (t.Source_Tier.str.startswith(("T1", "T2", "T3"))).all()
    assert (t.Date != "").all() and t.Date.notna().all()

def test_scorecard_csv_has_four_layers_and_descriptive_reliability_only():
    import pandas as pd
    s = pd.read_csv("outputs/agent_obs_catalyst_scorecard.csv")
    layers = set(s.Layer.str[0])
    assert layers == {"A", "B", "C", "D"}
    assert set(s.Reliability.unique()) <= {"Management-disclosed", "Official product data", "Experimental public proxy"}
    assert not any(s.columns.str.contains("score", case=False))    # no arbitrary numerical score column, per the brief


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests: t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed.")
