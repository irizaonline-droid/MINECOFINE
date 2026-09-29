from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from minicofin_pm.config import PROCESSED_DIR, RAW_DIR, RISK_COLORS
from minicofin_pm.data import completeness_by_column, load_demo_bundle, normalize_uploaded_frame
from minicofin_pm.pipeline import load_outputs, run_pipeline
from minicofin_pm.ui import empty_state, footer, page_header, render_sidebar_brand, risk_badge, setup_page


setup_page()


@st.cache_data(show_spinner=False)
def get_outputs() -> tuple[pd.DataFrame, dict[str, object]]:
    return load_outputs()


@st.cache_data(show_spinner=False)
def get_bundle():
    return load_demo_bundle()


def format_date(value) -> str:
    if pd.isna(value):
        return "Not available"
    return pd.Timestamp(value).strftime("%d %b %Y")


def plot_style(fig, height: int = 320):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=38, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, Arial, sans-serif", color="#30445C"),
        legend_title_text="",
    )
    return fig


def refresh_pipeline() -> None:
    with st.spinner("Validating records and refreshing risk scores…"):
        run_pipeline()
        get_outputs.clear()
        get_bundle.clear()
    st.toast("Risk scores refreshed from the frozen demo input.", icon="✅")


def open_asset(asset_id: str) -> None:
    st.session_state["selected_asset"] = asset_id
    st.session_state["screen"] = "Asset detail"


def overview(scores: pd.DataFrame, metrics: dict[str, object]) -> None:
    page_header(
        "Fleet command view",
        "Know which assets need attention first.",
        "A clear, explainable view of maintenance risk—built to move from evidence to inspection action in under 20 seconds.",
    )
    st.markdown(
        """
        <div class="status-row">
          <span class="status-pill">✓ Batch scoring complete</span>
          <span class="status-pill">✓ Human decision required</span>
          <span class="status-pill">✓ Offline-ready</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    urgent = scores["risk_band"].isin(["Critical", "High"]).sum()
    manual = (scores["risk_band"] == "Manual review").sum()
    average_risk = scores["risk_score"].mean()
    completeness = 100 * (1 - scores["missing_usage_flag"].mean())
    cols = st.columns(4)
    cols[0].metric("Assets monitored", f"{len(scores):,}", help="Assets in the current scoring run")
    cols[1].metric("Need priority review", f"{urgent}", delta=f"{urgent / len(scores):.1%} of fleet", delta_color="inverse")
    cols[2].metric("Average risk", f"{average_risk:.1f}/100", help="Average explained risk score")
    cols[3].metric("Usage completeness", f"{completeness:.1f}%", delta=f"{manual} manual reviews")

    st.write("")
    left, right = st.columns([1.05, 1.45], gap="large")
    band_order = ["Critical", "High", "Watch", "Normal", "Manual review"]
    distribution = scores["risk_band"].value_counts().reindex(band_order, fill_value=0).reset_index()
    distribution.columns = ["Risk band", "Assets"]
    with left:
        st.subheader("Fleet risk profile")
        fig = px.pie(
            distribution,
            values="Assets",
            names="Risk band",
            hole=0.66,
            color="Risk band",
            color_discrete_map=RISK_COLORS,
        )
        fig.update_traces(textposition="outside", textinfo="label+value", hovertemplate="%{label}: %{value}<extra></extra>")
        fig.add_annotation(text=f"<b>{len(scores)}</b><br><span style='font-size:12px'>assets</span>", showarrow=False)
        st.plotly_chart(plot_style(fig, 340), width="stretch", config={"displayModeBar": False})

    with right:
        st.subheader("Highest-priority assets")
        top = scores.dropna(subset=["risk_score"]).head(7).copy().sort_values("risk_score")
        fig = px.bar(
            top,
            x="risk_score",
            y="asset_id",
            orientation="h",
            color="risk_band",
            color_discrete_map=RISK_COLORS,
            text="risk_score",
            labels={"risk_score": "Risk score", "asset_id": "Asset"},
        )
        fig.update_traces(textposition="outside", hovertemplate="%{y}: %{x:.1f}/100<extra></extra>")
        fig.update_xaxes(range=[0, 106], gridcolor="#E5EAF0")
        fig.update_yaxes(title=None)
        st.plotly_chart(plot_style(fig, 340), width="stretch", config={"displayModeBar": False})

    st.subheader("Act now")
    queue = scores[scores["risk_band"].isin(["Critical", "High"])].head(5).copy()
    if queue.empty:
        empty_state("No urgent assets", "No Critical or High assets are present in this scoring run.")
    else:
        display = queue[["asset_id", "asset_class", "risk_score", "risk_band", "reason_1", "recommended_action"]].rename(
            columns={
                "asset_id": "Asset",
                "asset_class": "Class",
                "risk_score": "Score",
                "risk_band": "Band",
                "reason_1": "Why it is flagged",
                "recommended_action": "Next action",
            }
        )
        st.dataframe(
            display,
            hide_index=True,
            width="stretch",
            column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f")},
        )
        chosen = st.selectbox("Open an urgent asset", queue["asset_id"].tolist(), label_visibility="collapsed")
        st.button(
            "Review selected asset",
            type="primary",
            width="content",
            on_click=open_asset,
            args=(chosen,),
        )
    footer(str(metrics.get("generated_at_utc", "Unknown")))


def priority_queue(scores: pd.DataFrame, metrics: dict[str, object]) -> None:
    page_header(
        "Risk-ranked worklist",
        "Turn risk into a manageable inspection queue.",
        "Filter by class and risk, compare explanations, and choose the next asset for maintenance review.",
    )
    filter_cols = st.columns([1.25, 1.1, 1.1, 1.5])
    classes = filter_cols[0].multiselect("Asset class", sorted(scores["asset_class"].dropna().unique()), placeholder="All classes")
    bands = filter_cols[1].multiselect(
        "Risk band", ["Critical", "High", "Watch", "Normal", "Manual review"], placeholder="All bands"
    )
    minimum_score = filter_cols[2].slider("Minimum score", 0, 100, 0, 5)
    search = filter_cols[3].text_input("Find asset", placeholder="Search ID or model")

    filtered = scores.copy()
    if classes:
        filtered = filtered[filtered["asset_class"].isin(classes)]
    if bands:
        filtered = filtered[filtered["risk_band"].isin(bands)]
    filtered = filtered[filtered["risk_score"].fillna(0) >= minimum_score]
    if search:
        mask = filtered["asset_id"].str.contains(search, case=False, na=False) | filtered["make_model"].str.contains(
            search, case=False, na=False
        )
        filtered = filtered[mask]

    st.caption(f"{len(filtered)} assets match the current filters")
    if filtered.empty:
        empty_state("No matching assets", "Adjust a filter to restore the risk queue.")
        return

    display = filtered[
        [
            "asset_id",
            "asset_class",
            "make_model",
            "risk_score",
            "risk_band",
            "reason_1",
            "last_service_date",
            "recommended_action",
        ]
    ].copy()
    display["last_service_date"] = display["last_service_date"].map(format_date)
    display = display.rename(
        columns={
            "asset_id": "Asset",
            "asset_class": "Class",
            "make_model": "Make / model",
            "risk_score": "Score",
            "risk_band": "Band",
            "reason_1": "Top reason",
            "last_service_date": "Last service",
            "recommended_action": "Recommended action",
        }
    )
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        height=470,
        column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f")},
    )
    selected = st.selectbox("Select an asset for full detail", filtered["asset_id"].tolist())
    st.button("Open asset detail", type="primary", on_click=open_asset, args=(selected,))
    footer(str(metrics.get("generated_at_utc", "Unknown")))


def asset_detail(scores: pd.DataFrame, metrics: dict[str, object]) -> None:
    page_header(
        "Explainable asset view",
        "Understand the signal before taking action.",
        "The score is paired with concrete maintenance evidence, a history timeline, and a human-controlled disposition.",
    )
    asset_ids = scores["asset_id"].tolist()
    default_asset = st.session_state.get("selected_asset", asset_ids[0])
    default_index = asset_ids.index(default_asset) if default_asset in asset_ids else 0
    selected = st.selectbox("Asset", asset_ids, index=default_index)
    st.session_state["selected_asset"] = selected
    asset = scores.loc[scores["asset_id"] == selected].iloc[0]

    score_text = "Manual" if pd.isna(asset["risk_score"]) else f"{asset['risk_score']:.1f}"
    st.markdown(
        f"""
        <div class="risk-callout">
          <div class="small">{asset['asset_class']} • {asset['make_model']}</div>
          <div class="title">{asset['asset_id']} &nbsp; {risk_badge(asset['risk_band'])}</div>
          <div style="display:flex;gap:1.4rem;align-items:flex-end;margin-top:.75rem;flex-wrap:wrap">
            <div><span style="font-size:2.4rem;font-weight:800">{score_text}</span><span style="opacity:.65"> / 100</span></div>
            <div style="opacity:.9;max-width:700px"><b>Recommended:</b> {asset['recommended_action']}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    reasons = [asset.get(f"reason_{i}", "") for i in range(1, 4)]
    reason_cols = st.columns(3)
    for index, (column, reason) in enumerate(zip(reason_cols, reasons), start=1):
        with column:
            st.markdown(
                f'<div class="reason-card"><div class="num">SIGNAL {index:02d}</div><div class="copy">{reason or "No additional signal"}</div></div>',
                unsafe_allow_html=True,
            )

    st.write("")
    metric_cols = st.columns(5)
    metric_cols[0].metric("Repairs · 90d", int(asset["repairs_90d"]))
    metric_cols[1].metric("Days since service", int(asset["days_since_service"]))
    metric_cols[2].metric("Recent downtime", f"{asset['downtime_hours_180d']:.0f} h")
    metric_cols[3].metric("Recent cost", f"RWF {asset['corrective_cost_180d']:,.0f}")
    metric_cols[4].metric("Asset age", f"{asset['asset_age_years']:.1f} y")

    bundle = get_bundle()
    history = bundle.events[bundle.events["asset_id"] == selected].copy().sort_values("event_date")
    left, right = st.columns([1.45, 1], gap="large")
    with left:
        st.subheader("Maintenance timeline")
        if history.empty:
            empty_state("No event history", "This asset requires manual record verification.")
        else:
            history["size"] = history["maintenance_cost"].clip(lower=30_000)
            fig = px.scatter(
                history,
                x="event_date",
                y="maintenance_cost",
                color="event_type",
                size="size",
                hover_data=["fault_or_defect", "severity", "downtime_hours"],
                color_discrete_map={
                    "scheduled": "#2C6E9E",
                    "corrective": "#F59E0B",
                    "breakdown": "#DC4C64",
                    "inspection": "#0F8C7C",
                },
                labels={"event_date": "Date", "maintenance_cost": "Cost (RWF)", "event_type": "Event"},
            )
            fig.update_yaxes(gridcolor="#E5EAF0")
            st.plotly_chart(plot_style(fig, 360), width="stretch", config={"displayModeBar": False})
    with right:
        st.subheader("Record disposition")
        with st.form("disposition_form", clear_on_submit=True):
            disposition = st.selectbox(
                "Decision",
                ["Inspection requested", "Monitor", "Usage reading verification", "No action", "Maintenance completed"],
            )
            owner = st.text_input("Assigned to", placeholder="Maintenance officer")
            note = st.text_area("Note", placeholder="What should the team verify?")
            submitted = st.form_submit_button("Save decision", type="primary", width="stretch")
        if submitted:
            record = pd.DataFrame(
                [
                    {
                        "recorded_at": datetime.now().isoformat(timespec="seconds"),
                        "asset_id": selected,
                        "disposition": disposition,
                        "owner": owner.strip() or "Unassigned",
                        "note": note.strip(),
                    }
                ]
            )
            path = PROCESSED_DIR / "dispositions.csv"
            record.to_csv(path, mode="a", header=not path.exists(), index=False)
            st.success("Decision recorded in the local demo audit trail.")
        st.caption("This prototype records the recommendation and human response; it never authorizes repairs automatically.")
    footer(str(metrics.get("generated_at_utc", "Unknown")))


def model_evidence(scores: pd.DataFrame, metrics: dict[str, object]) -> None:
    page_header(
        "Offline validation",
        "Show what the model can—and cannot—claim.",
        "Models are compared on a time-based holdout. Every metric below is a demo result from simulated records, not an institutional outcome.",
    )
    rows = pd.DataFrame(metrics["metrics"])
    selected_name = str(metrics["selected_model"])
    selected = rows[rows["model"] == selected_name].iloc[0]
    cols = st.columns(4)
    cols[0].metric("Selected model", selected_name)
    cols[1].metric("Recall", f"{selected['recall']:.1%}", help="Share of simulated future events surfaced")
    cols[2].metric("Precision", f"{selected['precision']:.1%}", help="Share of alerts that match a simulated future event")
    cols[3].metric("PR-AUC", f"{selected['pr_auc']:.3f}", help="Ranking quality for rare positive outcomes")

    chart_data = rows.melt(id_vars="model", value_vars=["recall", "precision", "pr_auc"], var_name="Metric", value_name="Value")
    fig = px.bar(
        chart_data,
        x="model",
        y="Value",
        color="Metric",
        barmode="group",
        color_discrete_map={"recall": "#0F8C7C", "precision": "#2C6E9E", "pr_auc": "#F59E0B"},
        labels={"model": "Model", "Value": "Score"},
    )
    fig.update_yaxes(range=[0, 1], tickformat=".0%", gridcolor="#E5EAF0")
    st.plotly_chart(plot_style(fig, 390), width="stretch", config={"displayModeBar": False})

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Validation design")
        st.markdown(
            f"""
            - **Target:** corrective or breakdown event within the next 60 days
            - **Split:** {metrics['holdout_strategy']}
            - **Training examples:** {metrics['training_rows']:,} monthly asset snapshots
            - **Positive rate:** {metrics['positive_rate']:.1%}
            - **Threshold:** chosen to seek at least 80% recall where the demo data supports it
            """
        )
    with right:
        st.subheader("Decision guardrails")
        st.markdown(
            """
            - Risk is a prioritization signal, not an automated diagnosis.
            - Plain-language reasons are derived from visible feature values.
            - Missing maintenance and inspection history triggers manual review.
            - Real pilot claims require approved data and domain-expert label review.
            """
        )
    footer(str(metrics.get("generated_at_utc", "Unknown")))


def data_quality(scores: pd.DataFrame, metrics: dict[str, object]) -> None:
    page_header(
        "Data readiness",
        "Trust the records before trusting the score.",
        "Identity linkage, event labels, completeness, and plausibility are checked before the pipeline publishes any risk ranking.",
    )
    bundle = get_bundle()
    checks = pd.read_csv(PROCESSED_DIR / "data_quality_checks.csv")
    status_counts = checks["status"].value_counts()
    cols = st.columns(4)
    cols[0].metric("Checks passed", int(status_counts.get("Pass", 0)))
    cols[1].metric("Manage", int(status_counts.get("Manage", 0)))
    cols[2].metric("Blockers", int(status_counts.get("Blocker", 0)))
    cols[3].metric("Linked events", f"{bundle.events['asset_id'].isin(bundle.assets['asset_id']).mean():.1%}")
    st.dataframe(checks, hide_index=True, width="stretch")

    completeness = completeness_by_column(bundle)
    focus = completeness[completeness["field"].isin(
        ["asset_id", "asset_class", "acquisition_date", "usage_value", "event_date", "event_type", "severity", "inspection_date"]
    )]
    fig = px.bar(
        focus,
        x="complete_pct",
        y="field",
        color="source",
        orientation="h",
        text="complete_pct",
        color_discrete_map={"Assets": "#2C6E9E", "Maintenance": "#F59E0B", "Inspections": "#0F8C7C"},
        labels={"complete_pct": "Complete (%)", "field": "Field"},
    )
    fig.update_xaxes(range=[0, 105], gridcolor="#E5EAF0")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    st.plotly_chart(plot_style(fig, 390), width="stretch", config={"displayModeBar": False})

    with st.expander("Validate a candidate CSV or Excel file"):
        expected = st.selectbox("File type", ["assets", "events", "inspections"], format_func=str.title)
        uploaded = st.file_uploader("Choose a local file", type=["csv", "xlsx", "xls"])
        if uploaded is not None:
            try:
                candidate = normalize_uploaded_frame(uploaded, expected)
                st.success(f"Schema accepted: {len(candidate):,} rows and {len(candidate.columns)} columns.")
                st.dataframe(candidate.head(10), hide_index=True, width="stretch")
            except ValueError as exc:
                st.error(str(exc))

    st.divider()
    left, right = st.columns([1, 1.5], gap="large")
    with left:
        if st.button("Refresh scores from demo files", type="primary", width="stretch"):
            refresh_pipeline()
            st.rerun()
    with right:
        st.caption("Refresh revalidates the frozen files, rebuilds monthly features, retrains the selected model, and republishes the queue.")
    footer(str(metrics.get("generated_at_utc", "Unknown")))


def guide_page(scores: pd.DataFrame, metrics: dict[str, object]) -> None:
    page_header(
        "Project handoff",
        "Run, explain, and extend the prototype with confidence.",
        "The project is packaged for a team presentation: reproducible setup, a five-minute demo path, clear limitations, and a synchronized GuideMe PDF.",
    )
    tabs = st.tabs(["Five-minute demo", "Run locally", "Project boundaries"])
    with tabs[0]:
        st.markdown(
            """
            1. **Problem:** fixed schedules do not reflect actual condition.
            2. **Data:** show the frozen, clearly labeled simulated input and readiness checks.
            3. **Overview:** point out the risk distribution and highest-priority assets.
            4. **Asset:** open a Critical or High asset and explain its three signals.
            5. **Action:** record an inspection disposition to demonstrate the human decision loop.
            6. **Evidence:** compare rules, logistic regression, and the tree model.
            7. **Close:** approved data and SME label review are the next pilot steps.
            """
        )
    with tabs[1]:
        st.code("powershell -ExecutionPolicy Bypass -File .\\setup.ps1\n.\\run.ps1", language="powershell")
        st.markdown("The dashboard opens at **http://localhost:8501**. It runs without an internet connection after setup.")
    with tabs[2]:
        st.markdown(
            """
            **In this rapid MVP:** file-based ingestion, reproducible validation, batch scoring, model comparison, risk explanations, priority queue, asset detail, and a local decision audit trail.

            **Deferred:** live IFMIS integration, real-time telemetry, automated repair authorization, enterprise identity, national rollout, and causal claims about downtime or cost savings.
            """
        )
    guide_path = PROJECT_ROOT / "output" / "pdf" / "GuideMe-MINECOFIN-Predictive-Maintenance.pdf"
    if guide_path.exists():
        st.download_button(
            "Download GuideMe PDF",
            data=guide_path.read_bytes(),
            file_name=guide_path.name,
            mime="application/pdf",
            type="primary",
        )
    else:
        st.info("The GuideMe PDF is generated during final project packaging.")
    footer(str(metrics.get("generated_at_utc", "Unknown")))


render_sidebar_brand()
if "screen" not in st.session_state:
    st.session_state["screen"] = "Overview"

screens = ["Overview", "Priority queue", "Asset detail", "Model evidence", "Data quality", "Guide & handoff"]
current = st.sidebar.radio("Workspace", screens, key="screen")
st.sidebar.divider()
st.sidebar.markdown("<div class='demo-chip'>SIMULATED DATA</div>", unsafe_allow_html=True)
st.sidebar.caption("A transparent technical demonstration. Not a production maintenance authorization system.")

try:
    scores, metrics = get_outputs()
except Exception as exc:
    st.error("The scoring pipeline could not load. Run `powershell -ExecutionPolicy Bypass -File .\\setup.ps1` and retry.")
    st.exception(exc)
    st.stop()

{
    "Overview": overview,
    "Priority queue": priority_queue,
    "Asset detail": asset_detail,
    "Model evidence": model_evidence,
    "Data quality": data_quality,
    "Guide & handoff": guide_page,
}[current](scores, metrics)

