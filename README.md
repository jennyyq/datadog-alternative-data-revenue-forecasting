# Datadog Alternative-Data Revenue Forecasting

A reproducible research workflow for evaluating whether alternative data provide useful signals for Datadog's quarterly revenue growth, comparing historical out-of-sample forecasts, producing a **2026 Q3 revenue forecast**, and separately monitoring **LLM / Agent Observability** as a potential future revenue catalyst.

The project combines:

- Datadog reported fundamentals;
- hyperscaler cloud-growth data;
- Google Trends search-interest data;
- historical lead/lag analysis;
- expanding-window out-of-sample forecasting;
- exploratory regularization analysis;
- screened but excluded alternative-data candidates;
- LLM / Agent Observability disclosure monitoring; and
- an interactive HTML research dashboard.

The core research principle is to keep four types of evidence distinct:

1. **Historical operating relationships** — e.g. cloud-workload and search-interest lead/lag relationships;
2. **Historical out-of-sample forecasting evidence** — expanding-window forecasts evaluated against subsequently observed quarters;
3. **Exploratory robustness analysis** — including Ridge regularization used to test coefficient stability, but not used to redefine the final six-model framework;
4. **Forward-looking catalyst monitoring** — LLM / Agent Observability adoption evidence that is not mechanically converted into an unsupported revenue uplift.

> **Scope:** This README documents the final project structure and the verified final-stage forecasting/dashboard workflow. It does not imply that every earlier exploratory data-collection script can be reproduced using only the final-stage packages listed in `requirements.txt`.

---

## 1. Research Question

The project asks:

> **Can observable alternative-data signals provide useful information about Datadog's quarterly revenue-growth trajectory, and what do those signals currently imply for the next reported quarter?**

The final quantitative forecasting framework focuses on two retained alternative-data signals:

- **Cloud workload growth**, represented by an equal-weight composite of AWS, Azure and Google Cloud YoY growth; and
- **Google Trends search interest for "Datadog"**, transformed into quarterly YoY growth.

Other candidate signals were investigated but excluded where historical reconstruction was infeasible or the empirical relationship was too weak or unstable.

LLM / Agent Observability is treated separately as a **catalyst-monitoring framework**, rather than being assigned an unsupported dollar revenue contribution.

---

## 2. Project Structure

Place `README.md` and `requirements.txt` directly in `Datadog_Project/`, at the same level as `src/`, `outputs/`, and `dashboard/`.

```text
Datadog_Project/
├── README.md
├── requirements.txt
├── data/                           # Raw and processed research data
├── out/                            # Other intermediate / exploratory outputs, if used
├── outputs/                        # Research inputs + model/backtest outputs
├── dashboard/                      # Generated final presentation files
└── src/
    ├── 01_ddog_q_fundamentals/
    ├── 02_cloud_workload_Index/
    ├── 03_developer_adoption_index_f/
    ├── 04_github_external_adoption_f/
    ├── 05_googlet_job_integeco_screen/
    ├── 06_integration_ecosystem/
    ├── 07_google_trends_collection/
    ├── 08_google_trends_analysis/
    ├── 09_walk_forward_revenue_forecasting/
    │   └── walkforward_forecast.py
    ├── 10_LLM_observability_catalyst/
    ├── 11_agent_observability_catalyst_monitoring/
    ├── 12_six_exhibits/
    └── 13_html_dashboard/
        └── build_dashboard.py
```

Earlier-stage folder names follow the existing project structure. Preserve the existing spelling, including abbreviated folder names.

The exact entry-point scripts for every exploratory folder are not claimed here because this README documents the verified final workflow rather than implying end-to-end executability of every historical experiment.

`out/` is a separate workspace folder. The verified final-stage scripts use:

```text
outputs/
```

for model/research data and:

```text
dashboard/
```

for final presentation deliverables.

---

## 3. Research Pipeline

| Stage | Role | Final status |
| --- | --- | --- |
| `01_ddog_q_fundamentals` | SEC / IR quarterly revenue and customer fundamentals | Retained |
| `02_cloud_workload_Index` | AWS / Azure / Google Cloud growth and composite | Retained predictor |
| `03_developer_adoption_index_f` | Developer-adoption feasibility research | Screened / not retained |
| `04_github_external_adoption_f` | External GitHub adoption feasibility | Screened / not retained |
| `05_googlet_job_integeco_screen` | Job-posting / ecosystem feasibility | Screened / not retained |
| `06_integration_ecosystem` | Historical integration ecosystem | Context / screened out of final forecast |
| `07_google_trends_collection` | Google Trends collection | Retained |
| `08_google_trends_analysis` | Quarterly transformation and lead/lag analysis | Retained predictor |
| `09_walk_forward_revenue_forecasting` | Historical OOS comparison + 2026 Q3 forecast | Final quantitative model |
| `10_LLM_observability_catalyst` | Initial catalyst research | Catalyst only |
| `11_agent_observability_catalyst_monitoring` | Verified catalyst timeline | Dashboard catalyst module |
| `12_six_exhibits` | Static research exhibits | Presentation |
| `13_html_dashboard` | Interactive final research dashboard | Final presentation |

---

# 4. Data and Signal Construction

## 4.1 Datadog Fundamentals

The core company dataset contains quarterly Datadog operating and financial information, including:

- quarterly revenue;
- Revenue YoY growth;
- total customers;
- customers generating `$100k+` ARR;
- `$100k+` customer YoY growth;
- RPO where available; and
- NRR disclosures where available.

The primary forecasting target is:

```text
Datadog quarterly Revenue YoY growth (%)
```

The model forecasts the growth rate rather than revenue dollars directly.

---

## 4.2 Cloud Workload Index

The Cloud Workload Index combines quarterly YoY growth from:

- AWS;
- Microsoft Azure; and
- Google Cloud.

The retained composite is:

```text
Cloud_Index_Raw
    = equal-weight mean of
      AWS_YoY,
      Azure_YoY,
      GoogleCloud_YoY
```

The economic hypothesis is that Datadog usage should be related to underlying cloud and compute workloads.

Historical lead/lag analysis identified a useful relationship when cloud growth is observed approximately two quarters before Datadog revenue growth.

The final revenue model therefore uses:

```text
Cloud_Index_Raw(t-2)
```

This is a proxy rather than a direct measurement of Datadog-addressable workload growth.

---

## 4.3 Google Trends

Google Trends search interest for:

```text
"Datadog"
```

is collected at monthly frequency and aggregated to quarterly frequency.

The final transformed predictor is:

```text
Trend_YoY
```

representing year-over-year growth in quarterly search interest.

The revenue forecasting framework uses:

```text
Trend_YoY(t-1)
```

as a potential leading commercial-interest signal.

A separate mechanism check evaluates:

```text
Trend_YoY(t-2)
        ↓
$100k+ Customer YoY(t)
```

This customer-growth relationship is **not** substituted for the `t-1` Trends input used in the revenue model.

---

# 5. Final Six-Model Forecasting Framework

The final historical comparison contains exactly six models.

| Model | Inputs |
| --- | --- |
| `Naive` | Previous-quarter Revenue YoY |
| `AR1` | `Revenue_YoY(t-1)` |
| `Cloud` | `Cloud_Index_Raw(t-2)` |
| `Trends` | `Trend_YoY(t-1)` |
| `Cloud+Trends` | `Cloud_Index_Raw(t-2)` + `Trend_YoY(t-1)` |
| `AR+Cloud+Trends` | `Revenue_YoY(t-1)` + `Cloud_Index_Raw(t-2)` + `Trend_YoY(t-1)` |

The multivariate models use ordinary least squares in the official six-model framework.

Experimental Ridge specifications are discussed separately below and are **not part of this final comparison**.

---

# 6. Historical Walk-Forward Validation

## 6.1 Expanding-Window Design

The main historical evaluation uses an **expanding-window out-of-sample procedure**.

At each forecast origin:

1. only observations available up to that point are used for estimation;
2. the model is fitted on the expanding historical training sample;
3. the immediately following quarter is predicted;
4. the realized Revenue YoY is recorded;
5. the training window expands by one quarter; and
6. the process repeats.

The main panel contains:

```text
8 historical out-of-sample quarters
2024 Q3 – 2026 Q2
```

with a minimum initial training window of eight observations.

A separate post-2022 panel is retained as a robustness check and should not be confused with the primary eight-quarter historical OOS comparison.

---

## 6.2 No-Lookahead Alignment

Lagged features are constructed so that a forecast for quarter `t` uses the intended prior observations:

```text
Revenue_YoY(t-1)
Cloud_Index_Raw(t-2)
Trend_YoY(t-1)
```

The forward 2026 Q3 forecast similarly uses information available through 2026 Q2 under the final model specification.

Historical OOS results and the 2026 Q3 forward forecast are therefore different objects:

```text
Historical walk-forward
    ↓
Past forecast
    ↓
Subsequently observed actual
    ↓
Measurable forecast error


2026 Q3 forward forecast
    ↓
Current information set
    ↓
Future quarter
    ↓
Actual not yet available
```

No realized 2026 Q3 forecast accuracy is claimed.

---

# 7. Evaluation Metrics

The historical models are compared using four metrics.

## 7.1 MAE

```text
Mean Absolute Error
```

Average absolute error in predicted Revenue YoY.

Units:

```text
Revenue-YoY percentage points
```

---

## 7.2 RMSE

```text
Root Mean Squared Error
```

Also measured in Revenue-YoY percentage points.

RMSE places greater weight on relatively large forecast misses.

---

## 7.3 MAPE

```text
Mean Absolute Percentage Error
```

Relative forecast error expressed as a percentage.

---

## 7.4 Directional Accuracy

Directional accuracy asks whether the model correctly predicts **acceleration versus deceleration in Revenue YoY**.

For quarter `t`:

```text
Actual direction
    = sign[
        Revenue_YoY(t)
        - Revenue_YoY(t-1)
      ]

Predicted direction
    = sign[
        Predicted_Revenue_YoY(t)
        - Revenue_YoY(t-1)
      ]
```

A correct directional call occurs when the two signs match.

For example:

```text
5 correct calls / 8 OOS quarters
    = 62.5% directional accuracy
```

This means five of eight historical acceleration/deceleration calls were correct.

It does **not** mean that the revenue amount was predicted with 62.5% accuracy.

The dashboard therefore keeps:

```text
Point-forecast error
```

and:

```text
Directional accuracy
```

as separate evaluation criteria rather than combining them into a single model score.

---

# 8. Exploratory Ridge Regularization Check

Because the quarterly sample is small relative to the number of predictors in the multivariate specifications, an exploratory Ridge-regularization exercise was conducted as a model-stability check.

The purpose was to test whether coefficient shrinkage could reduce the instability of the two multivariate specifications:

```text
Cloud+Trends
AR+Cloud+Trends
```

The exploratory implementation:

- preserves the same predictor lags;
- preserves the same historical forecast origins;
- standardizes predictors using the training window;
- does not penalize the intercept; and
- uses a fixed regularization parameter:

```text
alpha = 10
```

## 8.1 Main-Window Results

For the main eight-quarter historical OOS window:

| Specification | OLS MAE | Ridge MAE | OLS RMSE | Ridge RMSE |
| --- | ---: | ---: | ---: | ---: |
| `Cloud+Trends` | 5.57 | 2.67 | 6.80 | 3.29 |
| `AR+Cloud+Trends` | 3.08 | 1.92 | 4.19 | 2.21 |

Regularization substantially reduced the main-window point-forecast errors of the two multivariate specifications.

However, this improvement did not generalize consistently to the separate post-2022 robustness panel.

For example:

```text
Post-2022 MAE

Naive persistence                ≈ 1.78
Ridge AR+Cloud+Trends            ≈ 2.72
```

The Ridge exercise is therefore treated as a:

```text
Sensitivity / model-stability analysis
```

rather than as part of the final model-selection framework.

It is **not included in**:

- the official six-model historical comparison;
- Chart C of the final dashboard;
- the dashboard model-selection rule; or
- the selected 2026 Q3 forward forecast.

The official forecasting comparison remains:

```text
Naive
AR1
Cloud
Trends
Cloud+Trends
AR+Cloud+Trends
```

This distinction is important because Ridge was explored after reviewing the baseline forecasting results.

Its performance should therefore not be interpreted as independent confirmatory out-of-sample evidence.

The experiment is retained in the research record because it provides useful evidence that some of the poor multivariate OLS performance may reflect coefficient instability in a very small quarterly sample.

---

# 9. Forward 2026 Q3 Forecast

The final forecasting script also fits the candidate specifications using all eligible historical information available through 2026 Q2 and produces a next-quarter inference for:

```text
2026 Q3
```

The output is written to:

```text
outputs/next_quarter_forecast.csv
```

The dashboard expects exactly one row with:

```text
selected_for_dashboard=True
```

In the current research presentation, that specification is:

```text
Trends
```

The selection rationale is its historical **Revenue-YoY acceleration/deceleration directional accuracy** within the official six-model framework.

This should not be interpreted as evidence that the model minimizes revenue-dollar forecast error.

The generated:

```text
outputs/next_quarter_forecast.csv
```

rather than a manually typed README value, remains the source of truth for the numerical 2026 Q3 forecast.

---

## 9.1 Revenue Conversion

The forecasting model predicts:

```text
Revenue YoY (%)
```

The selected model's predicted growth rate is converted into a revenue estimate using:

```text
Predicted Revenue(2026 Q3, USD M)

    = Actual Revenue(2025 Q3, USD M)

      × [1
         + Predicted Revenue YoY(2026 Q3) / 100]
```

Therefore:

- MAE and RMSE from the historical backtest are measured in Revenue-YoY percentage points;
- they are not USD-million forecast errors; and
- the project does not present a separately validated USD-million MAE.

---

## 9.2 Interpretation of the Forward Forecast

The 2026 Q3 forecast is a genuine forward inference.

It is different from the historical walk-forward forecasts because the 2026 Q3 actual has not yet been observed.

The forecast should therefore be interpreted as an:

```text
Indicative research estimate
```

rather than a high-confidence prediction.

The historical OOS sample contains only eight quarters, which materially limits statistical confidence in model ranking and future forecast reliability.

---

# 10. LLM / Agent Observability Catalyst

LLM / Agent Observability is deliberately separated from the numerical revenue forecast.

The project tracks verified disclosures relating to areas including:

- LLM Observability customer adoption;
- LLM / agent span growth;
- AI Agent Monitoring and related product launches;
- MCP usage;
- AI-native customer growth; and
- other adjacent AI-ecosystem indicators.

The catalyst research distinguishes between two evidence categories.

---

## 10.1 Direct Evidence

Direct evidence explicitly concerns the LLM / Agent Observability product or its usage.

Examples include:

- LLM Observability customers;
- LLM Observability span growth;
- Agent / LLM monitoring capabilities; and
- product launches or naming changes directly associated with the offering.

---

## 10.2 Adjacent Evidence

Adjacent evidence captures broader AI-ecosystem activity that may provide useful demand context but is not a direct measurement of Agent Observability revenue.

Examples include:

- MCP activity;
- AI-native customer growth;
- broader AI integrations; and
- other AI-related product usage.

---

## 10.3 Monetization Treatment

No standalone dollar revenue contribution from Agent Observability is mechanically added to the 2026 Q3 forecast.

The available public disclosures provide useful adoption and usage evidence but do not support a sufficiently defensible independent dollar-revenue estimate.

The catalyst module is therefore a:

```text
Forward monitoring framework
```

rather than an additional numerical regression variable.

---

# 11. Signals Screened but Not Retained

The broader research process investigated several additional alternative-data candidates.

These failed or excluded attempts are retained as part of the research audit trail rather than silently discarded.

---

## 11.1 Package Downloads — npm / PyPI

Historical package-download reconstruction was investigated as a possible developer-adoption signal.

A sufficiently reliable historical quarterly series was not obtained in the research environment.

Result:

```text
Not retained
```

---

## 11.2 External GitHub Adoption

Historical external GitHub adoption was investigated as a possible proxy for developer adoption.

The available GitHub interfaces did not provide a reliable method for reconstructing the required multi-quarter historical adoption series.

Result:

```text
Not retained
```

---

## 11.3 BuiltWith

BuiltWith was investigated as a possible technology-adoption signal.

The required historical/domain-level access was not available through the accessible interface.

Result:

```text
Not retained
```

---

## 11.4 Docker Hub

The available public Docker Hub endpoint exposed current cumulative pull information rather than the historical quarterly time series required for this research.

Result:

```text
Not retained
```

---

## 11.5 Job Postings

Job-posting data were investigated as a potential enterprise-adoption / demand signal.

Broad historical reconstruction did not produce a sufficiently robust final forecasting series.

Result:

```text
Not retained
```

---

## 11.6 Integration Ecosystem

Historical integration data were reconstructed and tested.

However, the observed relationship with Datadog revenue/customer growth was weak or sign-inconsistent.

Result:

```text
Context / screening only
Not retained as a revenue predictor
```

---

# 12. Final-Stage Setup

## macOS / VS Code

Open Terminal in the project root:

```bash
cd ~/Documents/Datadog_Project
```

An isolated virtual environment is optional:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the final-stage dependencies:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

> `requirements.txt` covers the final forecasting/dashboard workflow. Some earlier exploratory collection scripts may require additional packages, external APIs, or historical data access and are outside the reproducibility claim of this final-stage setup.

The final scripts use relative paths:

```text
outputs/
dashboard/
```

Run them from:

```text
Datadog_Project/
```

---

# 13. Step 1 — Run the Forecasting Pipeline

Before running the forecasting script, verify these upstream files exist:

```text
outputs/ddog_calculated_dataset.csv
outputs/cloud_calculated_data.csv
outputs/google_trends_quarterly.csv
```

## Inputs

| File | Purpose |
| --- | --- |
| `ddog_calculated_dataset.csv` | Datadog quarterly fundamentals and Revenue YoY |
| `cloud_calculated_data.csv` | AWS, Azure and Google Cloud quarterly growth |
| `google_trends_quarterly.csv` | Quarterly Google Trends data including YoY transformation |

Run:

```bash
python3 src/09_walk_forward_revenue_forecasting/walkforward_forecast.py
```

---

## 13.1 Forecasting Outputs

The final forecasting pipeline writes:

```text
outputs/walkforward_results.csv
outputs/walkforward_forecasts_main.csv
outputs/walkforward_forecasts_post2022.csv
outputs/trend_customer_mechanism_check.csv
outputs/chart_walkforward_forecasts.png
outputs/next_quarter_forecast.csv
```

| Output | Contents |
| --- | --- |
| `walkforward_results.csv` | Main and robustness-panel historical model metrics |
| `walkforward_forecasts_main.csv` | Main-panel historical OOS predictions and actuals |
| `walkforward_forecasts_post2022.csv` | Post-2022 robustness-panel predictions |
| `trend_customer_mechanism_check.csv` | Separate Trends / `$100k+` customer-growth mechanism analysis |
| `chart_walkforward_forecasts.png` | Historical actual-vs-predicted OOS chart |
| `next_quarter_forecast.csv` | 2026 Q3 forward YoY and USD-million projections |

Running the script overwrites prior versions of these final forecast outputs.

Run the forecasting pipeline **before** generating the dashboard.

---

# 14. Step 2 — Generate the Dashboard

The final dashboard consumes the completed research outputs:

```text
outputs/ddog_cloud_master.csv
outputs/ddog_google_trends_master.csv
outputs/walkforward_results.csv
outputs/agent_obs_verified_timeline.csv
outputs/ddog_calculated_dataset.csv
outputs/next_quarter_forecast.csv
```

Run:

```bash
python3 src/13_html_dashboard/build_dashboard.py
```

The script generates:

```text
dashboard/ddog_alternative_data_dashboard.html
dashboard/dashboard_data_dictionary.csv
```

The data dictionary is a **generated output**, not a dashboard input.

If its documentation needs correcting, modify the dictionary-generation logic in:

```text
src/13_html_dashboard/build_dashboard.py
```

and regenerate it.

Do not manually maintain the generated CSV.

---

# 15. View the Dashboard

On macOS:

```bash
open dashboard/ddog_alternative_data_dashboard.html
```

The dashboard uses Plotly through an external CDN.

An internet connection may therefore be required for interactive Plotly charts to render.

The research data themselves are embedded into the generated HTML by the Python builder.

The HTML is a generated artifact.

The source file to modify is:

```text
src/13_html_dashboard/build_dashboard.py
```

---

# 16. End-to-End Data Flow

```text
Historical research / data preparation
src/01 – src/08
        │
        ├── outputs/ddog_calculated_dataset.csv
        ├── outputs/cloud_calculated_data.csv
        └── outputs/google_trends_quarterly.csv
        │
        ▼
Historical lead / lag analysis
        │
        ├── Cloud t-2
        └── Trends t-1
        │
        ▼
src/09_walk_forward_revenue_forecasting/
walkforward_forecast.py
        │
        ├── Historical expanding-window OOS comparison
        │
        │   ├── walkforward_results.csv
        │   ├── walkforward_forecasts_main.csv
        │   └── walkforward_forecasts_post2022.csv
        │
        ├── Separate mechanism check
        │   └── trend_customer_mechanism_check.csv
        │
        ├── Historical forecast chart
        │   └── chart_walkforward_forecasts.png
        │
        └── Forward 2026 Q3 inference
            └── next_quarter_forecast.csv


Exploratory Ridge regularization
        │
        └── Sensitivity / model-stability analysis only
            NOT part of final six-model selection
        │

Other verified research inputs
        │
        ├── ddog_cloud_master.csv
        ├── ddog_google_trends_master.csv
        ├── agent_obs_verified_timeline.csv
        └── ddog_calculated_dataset.csv
        │
        ▼
src/13_html_dashboard/
build_dashboard.py
        │
        ├── dashboard/ddog_alternative_data_dashboard.html
        └── dashboard/dashboard_data_dictionary.csv
```

---

# 17. How to Interpret the Final Results

The project does **not** assume that finding a strong historical correlation automatically creates a superior forecasting model.

Instead, the research proceeds through several increasingly demanding tests.

```text
Economic hypothesis
        ↓
Alternative-data construction
        ↓
Historical lead / lag relationship
        ↓
Expanding-window OOS forecasting
        ↓
Robustness / regularization checks
        ↓
Forward forecast
        ↓
Ongoing catalyst monitoring
```

---

## 17.1 Historical Relationships

Lead/lag analysis identifies relationships that may be economically interesting.

These are useful for:

- hypothesis formation;
- feature selection; and
- subsequent forecasting tests.

They are not themselves evidence of out-of-sample forecasting superiority.

---

## 17.2 Historical Point Forecasting

The six-model walk-forward comparison tests whether the alternative-data specifications improve absolute Revenue-YoY forecasting error.

The current:

```text
outputs/walkforward_results.csv
```

is the source of truth for these metrics.

---

## 17.3 Directional Information

Directional accuracy asks a narrower question:

> Did the model correctly anticipate whether Datadog Revenue YoY would accelerate or decelerate?

This is different from predicting the exact growth rate.

Point-error metrics and directional accuracy are therefore displayed separately.

---

## 17.4 Ridge Sensitivity

The exploratory Ridge analysis asks another separate question:

> Are poor multivariate OLS results partly caused by coefficient instability in a very small sample?

The main-window results suggest regularization can materially reduce multivariate forecast error.

However, the improvement does not remain consistently superior in the separate robustness panel.

Ridge is therefore evidence about **model stability**, not the basis for replacing the official forecasting framework.

---

## 17.5 Forward Forecast

The 2026 Q3 prediction is a true forward inference generated after the historical validation exercise.

It does not yet have a realized forecast error.

The actual numerical forecast should always be read from:

```text
outputs/next_quarter_forecast.csv
```

rather than manually copied into documentation.

---

## 17.6 Catalyst Evidence

LLM / Agent Observability disclosures provide evidence about:

- adoption;
- usage;
- product expansion; and
- potential future monetization.

They do not currently provide enough information to support a defensible standalone dollar-revenue uplift.

---

# 18. Key Methodological Limitations

## 18.1 Small Historical Sample

The primary historical walk-forward evaluation contains only:

```text
8 OOS quarters
```

Individual observations therefore have substantial influence on the results.

For example:

```text
5 / 8 = 62.5%
```

This sample is too small to support strong claims about future forecasting reliability.

---

## 18.2 Alternative-Data Proxies Are Imperfect

Cloud-provider growth captures many workloads unrelated to Datadog.

Google Trends search activity may reflect:

- customers;
- developers;
- investors;
- job seekers;
- media attention; or
- other search intent.

Neither signal should therefore be interpreted as a direct measurement of Datadog demand.

---

## 18.3 Correlation Does Not Establish Causality

Observed lead/lag relationships can motivate forecasting hypotheses.

They do not demonstrate that changes in cloud growth or search interest **cause** changes in Datadog revenue.

---

## 18.4 Model-Selection Uncertainty

With a short quarterly history, model rankings can be sensitive to individual quarters.

Historical model comparison should therefore be interpreted as evidence about the observed sample rather than proof that one specification will remain superior.

---

## 18.5 Regularization Is Exploratory

Ridge regularization was evaluated after the baseline forecasting results had been examined.

Its results should therefore be interpreted as exploratory sensitivity evidence rather than independent confirmatory OOS evidence.

It is intentionally excluded from the final six-model model-selection framework.

---

## 18.6 Forward-Forecast Uncertainty

The 2026 Q3 forecast is generated before the actual quarter is observed.

Its realized accuracy cannot be evaluated until Datadog reports the corresponding quarter.

---

## 18.7 Catalyst Monetization Uncertainty

Agent Observability has observable adoption and usage evidence.

However, public disclosures do not currently provide sufficient information to construct a defensible standalone dollar-revenue estimate.

---

# 19. Reproducibility and Audit Principles

The final workflow follows several rules:

1. **Actuals, historical backtests, and forward forecasts are separately labeled.**
2. **Historical OOS predictions are not presented as future forecasts.**
3. **The dashboard reads model metrics from generated CSV outputs rather than manually typed performance numbers.**
4. **The official model comparison contains exactly six non-Ridge specifications.**
5. **Ridge is retained only as an exploratory regularization / stability check.**
6. **Agent Observability evidence is not mechanically added to the numerical revenue forecast.**
7. **Failed or excluded alternative-data candidates remain documented as research context.**
8. **Generated dashboard artifacts are rebuilt from source rather than manually maintained.**
9. **The numerical 2026 Q3 forecast is read from `next_quarter_forecast.csv`, not hard-coded in documentation.**
10. **Historical point-forecast accuracy and directional accuracy are treated as distinct evaluation criteria.**

---

# 20. Optional Smoke Checks

Check Python syntax:

```bash
python3 -m py_compile src/09_walk_forward_revenue_forecasting/walkforward_forecast.py
python3 -m py_compile src/13_html_dashboard/build_dashboard.py
```

Then run the actual final pipeline:

```bash
python3 src/09_walk_forward_revenue_forecasting/walkforward_forecast.py
python3 src/13_html_dashboard/build_dashboard.py
```

Finally:

```bash
open dashboard/ddog_alternative_data_dashboard.html
```

Syntax checks alone do not validate the underlying data or generated results.

---

# 21. Quick Troubleshooting

| Symptom | Check |
| --- | --- |
| Required input file missing | Confirm Terminal is in `Datadog_Project/` and verify the expected file exists in `outputs/` |
| `next_quarter_forecast.csv` missing | Run the final `walkforward_forecast.py` before building the dashboard |
| Zero or multiple selected forecast rows | `selected_for_dashboard` must identify exactly one forecast |
| Historical dashboard metrics look stale | Re-run the forecast script and then rebuild the dashboard |
| Dashboard forecast differs from CSV | Treat `next_quarter_forecast.csv` as the source of truth and regenerate the HTML |
| HTML charts are blank | Check access to the Plotly CDN and inspect the browser console |
| Data-dictionary edits disappear | Edit dictionary-generation logic in `build_dashboard.py`, not the generated CSV |
| Files appear in unexpected folders | Run both final scripts from the `Datadog_Project/` root |
| Ridge appears in Chart C | Remove it from the final dashboard comparison; Ridge is exploratory only |
| Old directional-accuracy values appear | Regenerate from the current `walkforward_results.csv`; do not maintain model-performance numbers manually |

---

# 22. Final Checklist


### Documentation

- [ ] `README.md` is in `Datadog_Project/`
- [ ] `requirements.txt` is in `Datadog_Project/`
- [ ] README describes the final six-model framework
- [ ] Ridge is clearly labeled exploratory
- [ ] no stale model-performance claim remains

### Forecasting

- [ ] final `walkforward_forecast.py` runs from the project root
- [ ] `walkforward_results.csv` contains the expected six-model main comparison
- [ ] historical OOS period is clearly identified
- [ ] `next_quarter_forecast.csv` exists
- [ ] exactly one next-quarter row has `selected_for_dashboard=True`
- [ ] the selected forecast uses only information available through 2026 Q2
- [ ] directional accuracy is described as acceleration/deceleration accuracy
- [ ] MAE / RMSE are not mislabeled as USD-million errors

### Research Integrity

- [ ] historical OOS results are distinguished from the 2026 Q3 forward forecast
- [ ] Ridge is excluded from final six-model model selection
- [ ] Agent Observability is not mechanically added to the numerical revenue forecast
- [ ] screened / failed signals remain documented
- [ ] limitations of the eight-quarter OOS sample are disclosed

### Dashboard

- [ ] dashboard has been regenerated after the final forecast run
- [ ] dashboard forecast matches `next_quarter_forecast.csv`
- [ ] Chart C matches `walkforward_results.csv`
- [ ] Chart C contains only the official six models
- [ ] no stale hard-coded directional-accuracy number remains
- [ ] `dashboard_data_dictionary.csv` has been regenerated
- [ ] HTML opens successfully in a browser

---

# 23. Minimal Reproduction Commands

Assuming the required upstream CSVs already exist in `outputs/`, reproduce the final deliverables from the project root with:

```bash
python3 src/09_walk_forward_revenue_forecasting/walkforward_forecast.py
python3 src/13_html_dashboard/build_dashboard.py
open dashboard/ddog_alternative_data_dashboard.html
```

The principal historical validation output is:

```text
outputs/walkforward_results.csv
```

The principal forward-model output is:

```text
outputs/next_quarter_forecast.csv
```

The two final presentation outputs are:

```text
dashboard/ddog_alternative_data_dashboard.html
dashboard/dashboard_data_dictionary.csv
```

---

# Disclaimer

This project is a research exercise in alternative-data analysis and forecasting.

The dashboard, historical model comparisons, forward forecast, and catalyst monitoring framework are intended to illustrate research methodology and the interpretation of public operating signals.

They are **not investment recommendations, stock ratings, or price targets**.