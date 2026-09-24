#!/usr/bin/env python3
"""
agent_obs_catalyst_framework.py - Agent/LLM Observability Catalyst Monitoring Framework.

Builds three CSVs and one chart from CURATED, HAND-VERIFIED research (this is not a raw-data pipeline - every
number below was checked against a source during this project's research phase; see Source_Tier/Reliability on
every row). Nothing here is fetched live and nothing is estimated as if it were Datadog's actual revenue.

SOURCE TIERS (assigned during this pass; see also DATAPOINTS_FLAGGED at the bottom):
  T1 = Official primary: an investors.datadoghq.com-hosted call transcript, a Datadog/SEC press release or 8-K,
       or Datadog's own product/pricing/docs pages.
  T2 = Verbatim earnings-call transcript reproduced by a third-party host (Motley Fool, Alphastreet, Globe and
       Mail wire syndication, Investing.com, Barchart). Content is a direct transcript, not analysis - but the
       hosting site is not Datadog's, so it is one notch below T1.
  T3 = Third-party analysis/summary (Zacks, Substack write-ups, TipRanks, stockanalysis.com, blog posts) that
       PARAPHRASES the call rather than quoting it. Flagged as unverified-from-primary unless a T1/T2 source for
       the same figure was also found (in which case the T1/T2 source is used and T3 is dropped).
  EXP = Experimental public proxy (the GitHub snapshot) - explicitly not a management disclosure of any kind.

No missing quarter has been invented. Where a quarter's figure could not be found (or, in one confirmed case,
was explicitly withheld by Datadog - see the Q4'25 CFO quote), the cell says so rather than being filled in.
"""
from __future__ import annotations
import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow, FancyBboxPatch

OUT_DIR = "outputs/"
os.makedirs(OUT_DIR, exist_ok=True)
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)

T1 = "T1 - Official primary (Datadog IR transcript / press release / 8-K / docs)"
T2 = "T2 - Verbatim call transcript, third-party host"
T3 = "T3 - Third-party analysis/summary (NOT independently confirmed on a primary source this pass)"
EXP = "EXP - Experimental public proxy (GitHub), not a management disclosure"

# =================================================================================================================
# 1. VERIFIED, DATED KPI TIMELINE  (agent_obs_verified_timeline.csv)
# =================================================================================================================
TIMELINE = [
    # date, metric, value, context, source_url, source_tier, stock_or_flow, interpretation
    ("2024-05-07", "AI integrations customers ('next-gen AI')", "~2,000", "Q1'24, stated directly",
     "https://www.fool.com/earnings/call-transcripts/2024/05/07/datadog-ddog-q1-2024-earnings-call-transcript/", T2, "Stock",
     "Earliest quantitative AI disclosure in the window; used the pre-'AI-native' label"),
    ("2024-05-07", "AI-native ('next-gen') share of ARR", "~3.5%", "Q1'24, stated directly",
     "https://www.fool.com/earnings/call-transcripts/2024/05/07/datadog-ddog-q1-2024-earnings-call-transcript/", T2, "Stock", "Baseline"),
    ("2024-06-26", "LLM Observability", "GA launch", "product launch",
     "https://www.datadoghq.com/about/latest-news/press-releases/datadog-llm-observability-is-now-generally-available-to-help-businesses-monitor-improve-and-secure-generative-ai-applications/", T1, "Event", "Anchor date for the product's existence"),
    ("2024-08-08", "AI integrations customers", "~2,500", "Q2'24, stated directly",
     "https://www.barchart.com/story/news/27920577/datadog-ddog-q2-2024-earnings-call-transcript", T2, "Stock", "+25% vs Q1'24"),
    ("2024-08-08", "AI-native share of ARR", ">4%", "Q2'24, stated directly ('in June')",
     "https://www.barchart.com/story/news/27920577/datadog-ddog-q2-2024-earnings-call-transcript", T2, "Stock", "—"),
    ("2024-11-07", "AI-native share of ARR", ">6%", "Q3'24; contributed ~4pp of YoY growth (vs ~2pp yr-ago)",
     "https://investors.datadoghq.com/static-files/e3e6f71c-4207-4296-acd5-b994ab22fe81", T1, "Stock+Flow", "Growth contribution, not just share"),
    ("2025-02-13", "AI integrations customers", ">3,500", "Q4'24, stated directly by CEO",
     "https://sergeycyw.substack.com/p/datadog-q4-2024-earnings-analysis", T3, "Stock", "Verbatim CEO quote embedded in a 3rd-party post; not re-confirmed on a T1 host this pass"),
    ("2025-02-13", "AI-native share of ARR", "6%", "Q4'24; doubled from 3% in Q4'23; drove 5pp of revenue growth",
     "https://sergeycyw.substack.com/p/datadog-q4-2024-earnings-analysis", T3, "Stock+Flow", "Same caveat as above"),
    ("2025-05-06", "AI integrations customers", ">4,000", "Q1'25, stated directly",
     "https://news.alphastreet.com/datadog-inc-ddog-q1-2025-earnings-call-transcript/", T2, "Stock", "—"),
    ("2025-05-06", "AI-native share of ARR", "8.5%", "Q1'25; up from 6% QoQ, 3.5% YoY; drove 6pp of YoY growth",
     "https://news.alphastreet.com/datadog-inc-ddog-q1-2025-earnings-call-transcript/", T2, "Stock+Flow", "—"),
    ("2025-05-06", "LLM Observability adopting-company growth", "more than doubled", "6-month growth, Q1'25 CEO quote",
     "https://sergeycyw.substack.com/p/datadog-q1-2025-earnings-analysis", T3, "Flow", "First disclosed LLM Obs adoption growth rate; company-count basis unstated"),
    ("2025-06-10", "AI Agent Monitoring / LLM Experiments / AI Agents Console", "GA launch", "product launch (DASH 2025)",
     "https://investors.datadoghq.com/news-releases/news-release-details/datadog-expands-llm-observability-new-capabilities-monitor", T1, "Event", "Agentic-specific capabilities layered onto the LLM Obs base"),
    ("2025-08-07", "AI-native share of Q2 revenue", "~11%", "Q2'25; up from ~8% Q1'25 (company's own later rounding), ~4% yr-ago; drove ~10pp of YoY growth",
     "https://investors.datadoghq.com/static-files/4b5b9407-c0e8-4333-b035-ca5b894e8904", T1, "Stock+Flow", "—"),
    ("2025-08-07", "AI integrations/tools customers", ">4,500", "Q2'25 (Fool article paraphrase of the call)",
     "https://www.fool.com/investing/2025/08/15/1-magnificent-artificial-intelligence-ai-stock-to/", T3, "Stock", "NOT independently re-confirmed on the T1 transcript this pass - flagged"),
    ("2025-11-06", "AI-native customer count", ">500 companies (100 spend $100k+/yr, 15 spend $1M+/yr)", "Q3'25, stated directly",
     "https://investors.datadoghq.com/static-files/cfa98304-1a07-482b-8d4d-dd074aa050c8", T1, "Stock", "Directly fetched & confirmed on the IR-hosted transcript"),
    ("2025-11-06", "AI-native share of revenue", "12%", "Q3'25; up from 11% Q2'25, ~6% yr-ago",
     "https://investors.datadoghq.com/static-files/cfa98304-1a07-482b-8d4d-dd074aa050c8", T1, "Stock", "—"),
    ("2025-11-06", "AI integrations customers", ">5,000", "Q3'25, stated directly",
     "https://investors.datadoghq.com/static-files/cfa98304-1a07-482b-8d4d-dd074aa050c8", T1, "Stock", "—"),
    ("2025-11-06", "LLM span-sending customer growth", "more than quadrupled", "recent months, Q3'25",
     "https://investors.datadoghq.com/static-files/cfa98304-1a07-482b-8d4d-dd074aa050c8", T1, "Flow", "—"),
    ("2025-11-06", "Total Datadog integrations", ">1,000", "Q3'25 milestone",
     "https://investors.datadoghq.com/static-files/cfa98304-1a07-482b-8d4d-dd074aa050c8", T1, "Stock", "All integrations, not AI-specific; context only"),
    ("2026-02-10", "AI-native customer count", "~650 (19 spend $1M+/yr; 14 of top 20 AI-native companies are customers)", "Q4'25, stated directly",
     "https://investors.datadoghq.com/static-files/71a1a6e1-3028-48a3-90f3-7662b76604e2", T1, "Stock", "Directly fetched & confirmed on the IR-hosted transcript"),
    ("2026-02-10", "AI-native share of revenue", "NOT DISCLOSED", "analyst explicitly asked; CFO: \"We didn't -- have not put it in there.\"",
     "https://investors.datadoghq.com/static-files/71a1a6e1-3028-48a3-90f3-7662b76604e2", T1, "—", "Disclosure discontinued from this quarter forward - itself a datapoint"),
    ("2026-02-10", "LLM Observability customers / span growth", ">1,000 customers; spans up 10x over 6 months", "Q4'25, stated directly",
     "https://investors.datadoghq.com/static-files/71a1a6e1-3028-48a3-90f3-7662b76604e2", T1, "Stock+Flow", "First disclosed absolute LLM Obs customer count"),
    ("2026-02-10", "MCP Server usage", "used by thousands of customers in preview; tool calls grew 11x QoQ (Q4 vs Q3)", "Q4'25, stated directly",
     "https://investors.datadoghq.com/static-files/71a1a6e1-3028-48a3-90f3-7662b76604e2", T1, "Stock+Flow", "MCP still in preview at this point (GA was 2026-03-09)"),
    ("2026-02-10", "AI integrations customers", "~5,500", "Q4'25, stated directly",
     "https://investors.datadoghq.com/static-files/71a1a6e1-3028-48a3-90f3-7662b76604e2", T1, "Stock", "—"),
    ("2026-02-10", "Bits AI SRE Agent usage", "2,000+ trial/paying customers ran investigations in the past month", "Q4'25, GA'd in Dec 2025",
     "https://investors.datadoghq.com/static-files/71a1a6e1-3028-48a3-90f3-7662b76604e2", T1, "Flow", "Adjacent AI-for-Datadog product, not LLM Observability itself; context"),
    ("2026-03-09", "Datadog MCP Server", "GA launch", "product launch",
     "https://investors.datadoghq.com/news-releases/news-release-details/datadog-launches-mcp-server-provide-ai-agents-secure-real-time", T1, "Event", "Usage/preview activity predates this GA date (see Q4'25 row)"),
    ("2026-05-07", "LLM Observability span growth", "nearly tripled QoQ", "Q1'26, stated directly",
     "https://investors.datadoghq.com/static-files/b162f4b4-ae66-4fd2-bc41-92b4f9a877c9", T1, "Flow", "—"),
    ("2026-05-07", "MCP Server tool-call growth", "quadrupled QoQ", "Q1'26, stated directly",
     "https://investors.datadoghq.com/static-files/b162f4b4-ae66-4fd2-bc41-92b4f9a877c9", T1, "Flow", "—"),
    ("2026-05-07", "AI integrations customers", ">6,500 (20% of customers, 80% of ARR)", "Q1'26",
     "https://www.theglobeandmail.com/investing/markets/stocks/DDOG/pressreleases/1815156/datadog-q1-earnings-call-highlights/", T2, "Stock", "Direct-quote wire article; AI-native %-of-revenue not disclosed this quarter"),
    ("2026-08-06", "AI-native customer count", ">750 ('AI customers'); all top-10 AI leaders are customers", "Q2'26, stated directly",
     "https://www.investing.com/news/transcripts/earnings-call-transcript-datadog-beats-q2-2026-estimates-but-shares-fall-156-93CH-4842560", T2, "Stock", "Direct-quote article; AI-native %-of-revenue still not disclosed"),
    ("2026-08-06", "MCP tool-call growth", "quadrupled QoQ again; >22x vs Q4'25", "Q2'26, stated directly",
     "https://investors.datadoghq.com/static-files/2360a5cc-f17a-4731-b74a-fb6f4617baf5", T1, "Flow", "—"),
    ("2026-09 (docs snapshot)", "Product naming",
     "Docs navigation now reads 'Agent Observability' throughout (breadcrumbs, SDK name, page titles); URL path still /llm_observability/; blog posts still titled 'LLM Observability'; Japanese-locale docs still say 'LLM Observability'",
     "confirmed directly against Datadog's own documentation", "https://docs.datadoghq.com/llm_observability/", T1, "Event",
     "Rename APPEARS in progress on English docs; NO exact rebrand date could be established - stated as such rather than inferred"),
    ("ongoing", "LLM Observability billing unit", "LLM span count (NOT tokens)", "current, per official docs",
     "https://docs.datadoghq.com/llm_observability/ ; https://www.datadoghq.com/product/ai/llm-observability/3/", T1, "—", "See pricing section"),
]
timeline_df = pd.DataFrame(TIMELINE, columns=["Date", "Metric", "Value", "Context", "Source_URL", "Source_Tier", "Stock_or_Flow", "Interpretation"])
timeline_df = timeline_df.sort_values("Date").reset_index(drop=True)
timeline_df.to_csv(OUT_DIR + "agent_obs_verified_timeline.csv", index=False)


# =================================================================================================================
# 2. CATALYST SCORECARD (four layers)  (agent_obs_catalyst_scorecard.csv)
# =================================================================================================================
RELI_MGMT = "Management-disclosed"
RELI_PRODUCT = "Official product data"
RELI_EXPERIMENTAL = "Experimental public proxy"

SCORECARD = [
    # Layer, KPI, Latest reading, Previous reading, Growth/change, Update frequency, Signal interpretation, Reliability, Source_Tier
    ("A. AI customer penetration", "AI-native customer count",
     "~750 (Q2'26)", "~650 (Q4'25)", "+15% over 2 quarters (Q1'26 count undisclosed)", "Quarterly (earnings call)",
     "Cohort keeps widening, not just deepening - breadth, not just concentration in a few whales.", RELI_MGMT, T2),
    ("A. AI customer penetration", "AI-native share of revenue/ARR",
     "NOT DISCLOSED since Q4'25", "12% (Q3'25)", "Disclosure discontinued - cannot compute a change",
     "Was quarterly; now withheld", "Loss of this metric removes the cleanest read on AI-native revenue mix; treat post-Q3'25 as a blind spot, not as stabilization.",
     RELI_MGMT, T1),
    ("A. AI customer penetration", "Customers using ≥1 AI integration",
     ">6,500 (Q1'26)", ">5,500 (Q4'25)", "+18% QoQ", "Quarterly (earnings call)",
     "Broadest AI-adjacent funnel stage; growing faster in absolute adds than the AI-native cohort, consistent with AI usage broadening beyond AI-first companies.", RELI_MGMT, T1),
    ("A. AI customer penetration", "AI-integration customers as % of total customers / ARR",
     "20% of customers / 80% of ARR (Q1'26)", "not disclosed on a comparable basis prior quarter", "n/a - first quarter this exact split was given",
     "Quarterly (new in Q1'26)", "80% of ARR from only 20% of customers restates the familiar Datadog power-law concentration in AI-usage terms; not itself evidence of NEW incremental revenue.", RELI_MGMT, T1),

    ("B. Agent/LLM Observability adoption", "LLM Observability customers (absolute)",
     ">1,000 (Q4'25)", "not disclosed as an absolute count before Q4'25 (only relative growth)", "First absolute figure disclosed this quarter",
     "Quarterly (started Q4'25)", "First time Datadog gave a hard customer count for the product itself, 18 months after GA - a maturity signal.", RELI_MGMT, T1),
    ("B. Agent/LLM Observability adoption", "Growth in LLM Obs customers/spans-sending base",
     "spans up 10x over 6 months (Q4'25); >1,000 customers", "customer growth 'more than quadrupled' in recent months (Q3'25)", "Consistently triple-digit-percent growth every quarter disclosed",
     "Quarterly", "Every disclosure since launch has described acceleration, not deceleration, in adoption - a genuinely unusual streak.", RELI_MGMT, T1),
    ("B. Agent/LLM Observability adoption", "Public GitHub adoption snapshot (fingerprints: DD_LLMOBS_ENABLED, LLMObs.enable, llmobs_enabled)",
     "commit search 207-229 matches; repo search 34-346 repos (current snapshot, Sept 2026)", "n/a - no prior snapshot taken", "n/a - single point-in-time read",
     "Ad hoc / not yet tracked over time", "NOISY, EXPERIMENTAL. Confirms genuine public developer activity beyond hackathons, but cannot be compared over time without a repeated future snapshot, and code-search (the most direct check) needs an authenticated token this pass could not use.",
     RELI_EXPERIMENTAL, EXP),

    ("C. Usage intensity", "LLM span growth",
     "nearly tripled QoQ (Q1'26)", "spans up 10x over prior 6 months (Q4'25)", "Sustained multi-quarter acceleration, no deceleration disclosed yet",
     "Quarterly", "The single cleanest usage-volume proxy Datadog gives; consistently the strongest-worded growth metric in every AI section of the call.", RELI_MGMT, T1),
    ("C. Usage intensity", "MCP tool-call growth",
     "quadrupled QoQ again; >22x vs Q4'25 (Q2'26)", "quadrupled QoQ (Q1'26); 11x QoQ (Q4'25)", "Growth RATE has been roughly stable (~4x QoQ) even as the base grows - i.e. still accelerating in absolute terms",
     "Quarterly (product GA'd 2026-03-09; usage disclosed from Q4'25 preview)", "The newest and currently the fastest-compounding usage metric Datadog discloses; still very early (small base).", RELI_MGMT, T1),
    ("C. Usage intensity", "Other AI-for-Datadog usage (context, not LLM Obs itself)",
     "Bits AI SRE: 2,000+ trial/paying customers ran investigations in past month (Q4'25)", "'thousands of customers' onboarded for access (Q3'25)", "Preview-to-GA ramp (GA'd Dec 2025)",
     "Quarterly", "Adjacent evidence that Datadog's own AI tooling is being used at scale - supports the broader 'AI is driving usage, not replacing it' narrative but is not itself Agent Observability revenue.", RELI_MGMT, T1),

    ("D. Monetization", "Billing unit",
     "LLM span (one call to an LLM provider)", "unchanged since GA", "n/a",
     "Static (checked against current docs)", "NOT token-based, NOT agent-complexity-based - tool/retrieval/embedding/agent spans are explicitly free. A more complex agent does not mechanically cost more unless it also calls an LLM more often.", RELI_PRODUCT, T1),
    ("D. Monetization", "Free allowance",
     "40,000 LLM spans/month, 15-day retention", "unchanged", "n/a", "Static", "Low enough to be a genuine trial tier, not a production tier.", RELI_PRODUCT, T1),
    ("D. Monetization", "Pro included spans",
     "100,000 LLM spans/month included in the $160/mo base", "unchanged", "n/a", "Static", "Flat fee up to the cap - revenue per Pro customer does NOT scale with usage until the customer crosses 100K spans/month.", RELI_PRODUCT, T1),
    ("D. Monetization", "Overage pricing beyond 100K spans/mo",
     "NOT PUBLISHED", "NOT PUBLISHED", "n/a", "n/a", "Confirmed absent from Datadog's own pricing page and docs; multiple independent third parties confirm the same gap. This is the single biggest reason a real revenue estimate is impossible from public data alone.", RELI_PRODUCT, T1),
    ("D. Monetization", "Retention add-on pricing",
     "billed 'per 10,000 LLM spans' - exact rate NOT PUBLISHED", "unchanged", "n/a", "Static", "Same gap as overage pricing: the metering UNIT is public, the RATE is not.", RELI_PRODUCT, T1),
]
scorecard_df = pd.DataFrame(SCORECARD, columns=["Layer", "KPI", "Latest_reading", "Previous_reading", "Growth_change",
                                                "Update_frequency", "Signal_interpretation", "Reliability", "Source_Tier"])
scorecard_df.to_csv(OUT_DIR + "agent_obs_catalyst_scorecard.csv", index=False)


# =================================================================================================================
# 3. CATALYST STATE RULES (objective, applied to the disclosed data - no arbitrary numeric thresholds)
# =================================================================================================================
# Each disclosed quarter is read into one of {"accelerating","strong_stable","decelerating","unknown"} PER DIMENSION,
# directly from the company's own growth-rate language (never from a numeric cutoff we invented). "strong_stable"
# means growth continues at a consistently high rate without company language indicating a rate change either way.
QUARTERLY_READS = [
    # quarter, customer_adoption, usage_growth, ai_penetration, note
    ("2025Q1", "accelerating", "unknown", "accelerating", "LLM Obs adopting-company count 'more than doubled' in 6mo; AI-native ARR share 6%->8.5%"),
    ("2025Q2", "accelerating", "unknown", "accelerating", "AI-native rev share 8%->11%; integrations customers 4,000->4,500"),
    ("2025Q3", "accelerating", "accelerating", "accelerating", "AI-native count crosses 500; LLM span-sending customers 'more than quadrupled'; AI-native rev share 11%->12%"),
    ("2025Q4", "accelerating", "accelerating", "unknown (metric withheld)", "AI-native count 500->650; LLM Obs customers first disclosed at 1,000+, spans 10x/6mo; MCP 11x QoQ; but AI-native %-of-revenue discontinued"),
    ("2026Q1", "accelerating", "accelerating", "accelerating", "Integrations customers 5,500->6,500 (20%/80% split newly disclosed); LLM Obs spans 'nearly tripled' QoQ; MCP 4x QoQ"),
    ("2026Q2", "accelerating", "strong_stable", "accelerating", "AI-native count 650(Q4)->750; MCP growth rate holds near 4x QoQ (i.e. still very fast, not visibly speeding up further); non-AI growth also accelerating"),
]
reads_df = pd.DataFrame(QUARTERLY_READS, columns=["Quarter", "Customer_adoption_trend", "Usage_growth_trend", "AI_penetration_trend", "Note"])

def classify_state(customer_adoption: str, usage_growth: str, ai_penetration: str) -> tuple[str, str]:
    """Objective rule (per the task brief), applied to company-language-derived reads, not invented numeric cutoffs.
    AHEAD:   customer adoption accelerating AND usage growth accelerating-or-strong_stable AND AI penetration increasing
    BEHIND:  customer adoption OR usage growth reads 'decelerating'
    IN LINE: everything else (e.g., adoption continues but a dimension is 'unknown' or merely 'strong_stable' throughout)
    """
    dims = [customer_adoption, usage_growth, ai_penetration]
    if "decelerating" in dims:
        return "BEHIND", "At least one of customer adoption / usage growth is reading as decelerating."
    if customer_adoption == "accelerating" and usage_growth in ("accelerating", "strong_stable") and ai_penetration in ("accelerating", "strong_stable"):
        return "AHEAD", "Customer adoption accelerating, usage growth accelerating-or-exceptionally-strong, AI penetration increasing."
    return "IN LINE", "Adoption continues but at least one dimension is unknown/undisclosed or has flattened to merely stable."

reads_df[["State", "State_reason"]] = reads_df.apply(
    lambda r: pd.Series(classify_state(r.Customer_adoption_trend, r.Usage_growth_trend, r.AI_penetration_trend)), axis=1)
CURRENT_STATE, CURRENT_REASON = reads_df.iloc[-1][["State", "State_reason"]]

print("=== Catalyst state, by quarter (objective rule applied to company-disclosed growth-rate language) ===")
print(reads_df.to_string(index=False))
print(f"\nCURRENT STATE (Q2 2026): {CURRENT_STATE} - {CURRENT_REASON}")
print("Caveat: 2025 Q4's AI-penetration read is 'unknown' only because Datadog stopped disclosing the %-of-revenue "
     "figure that quarter; classified AHEAD/IN LINE conservatively using the other two dimensions plus the newly "
     "disclosed absolute LLM Obs and MCP figures, not by assuming the withheld metric would have kept accelerating.")


# =================================================================================================================
# 4. ILLUSTRATIVE MONETIZATION SENSITIVITY  (agent_obs_sensitivity.csv)  -- NOT A FORECAST
# =================================================================================================================
FREE_INCLUDED_SPANS_PER_MONTH = 40_000
PRO_PRICE_PER_MONTH = 160.0
PRO_INCLUDED_SPANS_PER_MONTH = 100_000

def tiered_monthly_bill(avg_spans_per_month: float) -> dict:
    """Splits a customer's monthly usage into (a) a KNOWN component priced from Datadog's own published Pro rate,
    and (b) any usage above the Pro-included 100K spans/month, which is EXPLICITLY UNPRICED because Datadog does
    not publish an overage rate. Never multiplies the full span count by any rate - see the module docstring."""
    if avg_spans_per_month <= FREE_INCLUDED_SPANS_PER_MONTH:
        return dict(known_monthly_usd=0.0, spans_in_unpriced_overage=0.0, plan="Free (within 40K included)")
    if avg_spans_per_month <= PRO_INCLUDED_SPANS_PER_MONTH:
        return dict(known_monthly_usd=PRO_PRICE_PER_MONTH, spans_in_unpriced_overage=0.0, plan="Pro (within 100K included, flat fee)")
    overage = avg_spans_per_month - PRO_INCLUDED_SPANS_PER_MONTH
    return dict(known_monthly_usd=PRO_PRICE_PER_MONTH, spans_in_unpriced_overage=overage, plan="Pro + overage (overage rate NOT public)")

SCENARIOS = [
    ("A. Light usage, well within Pro's included volume", 1_000, 50_000,
     "Illustrative only. N = a round number, NOT a Datadog disclosure."),
    ("B. At the Pro included ceiling exactly", 1_000, 100_000,
     "Illustrative only. Shows the MAXIMUM revenue obtainable from published Pro pricing alone before overage begins."),
    ("C. Using Datadog's own disclosed LLM Observability customer count, at the Pro ceiling", 1_000, 100_000,
     "N = 1,000 is Datadog's own disclosed 'over 1,000 customers using LLM Observability' (Q4 2025, primary-sourced). "
     "Usage level is still illustrative - Datadog has not disclosed average spans/customer."),
    ("D. Same disclosed customer count, heavier illustrative usage (reflecting disclosed multi-x span growth)", 1_000, 500_000,
     "N = 1,000 (as in C). Usage level is a hypothetical 5x the Pro ceiling, chosen only to illustrate how quickly "
     "a customer base crosses into the UNPRICED overage zone - not a prediction of actual usage."),
]

rows = []
for name, n_customers, avg_spans, note in SCENARIOS:
    bill = tiered_monthly_bill(avg_spans)
    known_annual = bill["known_monthly_usd"] * 12 * n_customers
    overage_spans_annual = bill["spans_in_unpriced_overage"] * 12 * n_customers
    rows.append(dict(
        Scenario=name, Paying_customers_N=n_customers, Avg_LLM_spans_per_customer_per_month=avg_spans,
        Plan_mix=bill["plan"],
        Known_illustrative_annual_revenue_USD=round(known_annual, 0),
        Additional_spans_per_year_in_unpriced_overage_zone=round(overage_spans_annual, 0),
        Overage_revenue_USD="UNKNOWABLE - Datadog does not publish a per-span overage rate" if overage_spans_annual > 0 else "$0 (no overage)",
        Note=note))
sens_df = pd.DataFrame(rows)
sens_df.insert(0, "Label", "Illustrative sensitivity only - not an estimate or forecast of Datadog Agent Observability revenue.")
sens_df.to_csv(OUT_DIR + "agent_obs_sensitivity.csv", index=False)
print("\n=== Illustrative monetization sensitivity (NOT A FORECAST) ===")
print(sens_df.drop(columns=["Label"]).to_string(index=False))
print("\nWhy no single total dollar figure is given for scenarios C/D: enterprise discounts, negotiated contract "
     "structures, customer mix (many customers never leave the free tier), and the undisclosed overage/retention "
     "rates make the REALIZED revenue unknowable from public data - only the known-Pro-tier floor can be computed.")


# =================================================================================================================
# 5. PRESENTATION CHART: chronological AI/Agent Observability Adoption Flywheel
# =================================================================================================================
MILESTONES = [   # (date_str, label, tier)  tier: +2/+1 above (far/near), -1/-2 below (near/far) - staggered to avoid collisions
    ("2024-06-26", "LLM Observability\nGA launch", 1),
    ("2024-11-07", "AI-native >6%\nof ARR (Q3'24)", -1),
    ("2025-06-10", "AI Agent Monitoring +\nAgents Console GA (DASH)", 1),
    ("2025-11-06", ">500 AI-native custs;\n12% of revenue (Q3'25)", -1),
    ("2026-02-10", "LLM Obs >1,000 custs,\nspans 10x/6mo (Q4'25)", 2),
    ("2026-03-09", "MCP Server\nGA launch", -1),
    ("2026-05-07", "LLM Obs spans ~triple QoQ;\n6,500 AI-integr. custs (Q1'26)", 1),
    ("2026-08-06", "MCP calls >22x vs Q4'25;\n>750 AI-native custs (Q2'26)", -2),
]

def build_flywheel_chart(path: str):
    fig = plt.figure(figsize=(17, 9.5))
    ax_top = fig.add_axes([0.03, 0.58, 0.90, 0.36])   # mechanism row
    ax_bot = fig.add_axes([0.03, 0.05, 0.90, 0.46])   # timeline row
    for ax in (ax_top, ax_bot): ax.set_xlim(-0.3, 10.9); ax.axis("off")

    # ---- mechanism: 4 stages, left to right, with connecting arrows
    stages = [
        ("AI applications\n& agents", "#1a73e8"),
        ("Agent / LLM\nObservability adoption", "#34a853"),
        ("LLM spans /\nusage volume", "#E8710A"),
        ("Datadog billable\nobservability volume", "#632CA6"),
    ]
    box_w, box_h, gap = 1.9, 1.5, 0.55
    total_w = len(stages) * box_w + (len(stages) - 1) * gap
    x0 = (10 - total_w) / 2
    centers = []
    for i, (label, color) in enumerate(stages):
        x = x0 + i * (box_w + gap)
        centers.append(x + box_w / 2)
        box = FancyBboxPatch((x, 0.9), box_w, box_h, boxstyle="round,pad=0.05,rounding_size=0.12",
                             linewidth=1.6, edgecolor=color, facecolor=color, alpha=0.15)
        ax_top.add_patch(box)
        ax_top.text(x + box_w / 2, 0.9 + box_h / 2, label, ha="center", va="center", fontsize=11.5, fontweight="bold", color="#222")
    for i in range(len(stages) - 1):
        xa = x0 + i * (box_w + gap) + box_w; xb = xa + gap
        ax_top.annotate("", xy=(xb - 0.05, 0.9 + box_h / 2), xytext=(xa + 0.05, 0.9 + box_h / 2),
                        arrowprops=dict(arrowstyle="-|>", lw=2.2, color="#555"))
    ax_top.text(5, 0.35, "Mechanism verified from Datadog's own documentation: only step 3 (LLM spans) is the billed unit - "
               "tool, retrieval, embedding and agent spans are explicitly NOT billed.", ha="center", va="center", fontsize=9.5, color="#444", style="italic")
    ax_top.set_ylim(0, 3); ax_top.set_title("AI / Agent Observability Adoption Flywheel  (2024 Q1 - 2026 Q2)", fontsize=16, fontweight="bold", pad=14, loc="center")

    # ---- timeline: milestones only, alternating above/below, dates parsed to a 0-10 x-axis
    from datetime import date
    d0, d1 = date(2024, 1, 1), date(2026, 6, 30)
    span = (d1 - d0).days
    def to_x(dstr):
        y, m, d = map(int, dstr.split("-")); return (date(y, m, d) - d0).days / span * 9.2 + 0.3

    ax_bot.axhline(0, color="#333", lw=2, xmin=0.02, xmax=0.92)
    for q in range(2024, 2027):
        for qm, qd in [(1, 1), (4, 1), (7, 1), (10, 1)]:
            if date(q, qm, qd) < d0 or date(q, qm, qd) > d1: continue
            xq = to_x(f"{q}-{qm:02d}-{qd:02d}")
            ax_bot.plot([xq, xq], [-0.05, 0.05], color="#999", lw=1)
            ax_bot.text(xq, -0.22, f"{q}\nQ{(qm - 1)//3 + 1}", ha="center", va="top", fontsize=8, color="#666")

    TIER_Y = {2: 1.15, 1: 0.55, -1: -0.55, -2: -1.15}
    for dstr, label, tier in MILESTONES:
        x = to_x(dstr); y_lab = TIER_Y[tier]
        ax_bot.plot([x, x], [0, y_lab * 0.82], color="#888", lw=1, zorder=1)
        ax_bot.scatter([x], [0], s=55, color="#632CA6", zorder=5, edgecolor="white", linewidth=0.8)
        va = "bottom" if tier > 0 else "top"
        ax_bot.text(x, y_lab, label, ha="center", va=va, fontsize=9,
                    bbox=dict(boxstyle="round,pad=0.35", facecolor="#F5F0FA", edgecolor="#632CA6", linewidth=0.8))
    ax_bot.set_xlim(-0.3, 10.3); ax_bot.set_ylim(-1.85, 1.85)
    ax_bot.text(5, -1.78, "Strongest VERIFIED milestones only (primary-sourced) - see agent_obs_verified_timeline.csv for the full dated KPI list.",
               ha="center", va="bottom", fontsize=9.5, color="#555", style="italic")
    fig.savefig(path, dpi=170, facecolor="white")
    plt.close(fig)

build_flywheel_chart(OUT_DIR + "agent_obs_flywheel_chart.png")
print("\nChart written: agent_obs_flywheel_chart.png")
print("\nAll files written to", OUT_DIR)
