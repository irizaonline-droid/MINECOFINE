"""Build the synchronized GuideMe PDF for the AssetCare AI rapid MVP."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "pdf"
OUT_FILE = OUT_DIR / "GuideMe-MINECOFIN-Predictive-Maintenance.pdf"

NAVY = colors.HexColor("#10233A")
NAVY_2 = colors.HexColor("#173A5E")
AMBER = colors.HexColor("#F59E0B")
TEAL = colors.HexColor("#0F8C7C")
PAPER = colors.HexColor("#F6F8FB")
MUTED = colors.HexColor("#607187")
LINE = colors.HexColor("#DCE4EC")
RED = colors.HexColor("#DC4C64")
WHITE = colors.white


def styles():
    base = getSampleStyleSheet()
    return {
        "cover_kicker": ParagraphStyle(
            "CoverKicker", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12,
            textColor=AMBER, spaceAfter=9, tracking=1.5,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName="Times-Bold", fontSize=30, leading=32,
            textColor=WHITE, alignment=TA_LEFT, spaceAfter=12,
        ),
        "cover_sub": ParagraphStyle(
            "CoverSub", parent=base["BodyText"], fontName="Helvetica", fontSize=11, leading=16,
            textColor=colors.HexColor("#C9D7E2"), spaceAfter=12,
        ),
        "kicker": ParagraphStyle(
            "Kicker", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10,
            textColor=colors.HexColor("#B96B00"), spaceAfter=5, tracking=1.3,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName="Times-Bold", fontSize=23, leading=26,
            textColor=NAVY, spaceAfter=7,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15,
            textColor=NAVY, spaceBefore=7, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9, leading=13,
            textColor=colors.HexColor("#30445C"), spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.5, leading=10.5,
            textColor=MUTED,
        ),
        "card_title": ParagraphStyle(
            "CardTitle", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=9.5, leading=12,
            textColor=NAVY, spaceAfter=3,
        ),
        "card_body": ParagraphStyle(
            "CardBody", parent=base["BodyText"], fontName="Helvetica", fontSize=8, leading=11,
            textColor=colors.HexColor("#42556B"),
        ),
        "code": ParagraphStyle(
            "Code", parent=base["Code"], fontName="Courier", fontSize=8, leading=11,
            textColor=WHITE, backColor=NAVY, borderPadding=9, spaceAfter=7,
        ),
        "center": ParagraphStyle(
            "Center", parent=base["BodyText"], alignment=TA_CENTER, fontName="Helvetica-Bold",
            fontSize=8, leading=10, textColor=NAVY,
        ),
    }


S = styles()


def header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    if doc.page == 1:
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
    else:
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, height - 15 * mm, width - 18 * mm, height - 15 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, height - 11 * mm, "ASSETCARE AI - MINECOFIN RAPID MVP")
        canvas.drawRightString(width - 18 * mm, 10 * mm, f"GUIDEME - {doc.page:02d}")
    canvas.restoreState()


def title(kicker: str, heading: str, intro: str):
    return [
        Paragraph(kicker.upper(), S["kicker"]),
        Paragraph(heading, S["h1"]),
        Paragraph(intro, S["body"]),
        HRFlowable(width="100%", thickness=0.7, color=LINE, spaceBefore=4, spaceAfter=10),
    ]


def bullets(items: list[str]):
    return [Paragraph(f"- {item}", S["body"]) for item in items]


def card(heading: str, body: str, accent=TEAL):
    table = Table([[Paragraph(heading, S["card_title"]), Paragraph(body, S["card_body"])]], colWidths=[42 * mm, 125 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LINEBEFORE", (0, 0), (0, 0), 3, accent),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def data_table(rows, widths=None, header=True):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#30445C")),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [WHITE, PAPER]),
    ]
    if header:
        style.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    table.setStyle(TableStyle(style))
    return table


def metric_cards(metrics):
    selected = next(item for item in metrics["metrics"] if item["model"] == metrics["selected_model"])
    data = [
        ["SELECTED", "RECALL", "PRECISION", "PR-AUC"],
        [metrics["selected_model"], f"{selected['recall']:.1%}", f"{selected['precision']:.1%}", f"{selected['pr_auc']:.3f}"],
    ]
    table = Table(data, colWidths=[42 * mm] * 4)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7),
                ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 12),
                ("TEXTCOLOR", (0, 1), (-1, 1), NAVY),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def build_story(metrics: dict, scores: pd.DataFrame, quality: pd.DataFrame):
    story = []
    cover_image = ROOT / "assets" / "assetcare-banner.png"
    if cover_image.exists():
        img = Image(str(cover_image), width=174 * mm, height=98 * mm, kind="proportional")
        story.extend([Spacer(1, 8 * mm), img, Spacer(1, 10 * mm)])
    story.extend(
        [
            Paragraph("RAPID MVP OPERATING GUIDE", S["cover_kicker"]),
            Paragraph("AssetCare AI", S["cover_title"]),
            Paragraph("Explainable predictive maintenance for government vehicles and assets", S["cover_sub"]),
            Paragraph("GuideMe edition 1.0 - synchronized 29 September 2026", S["small"]),
            PageBreak(),
        ]
    )

    story += title(
        "01 - Project at a glance",
        "One complete decision loop, kept deliberately small",
        "The prototype converts frozen asset, maintenance, and inspection records into a ranked, explained inspection queue. It supports a human decision; it does not replace one.",
    )
    story.append(
        data_table(
            [
                ["INPUT", "PROCESS", "OUTPUT", "ACTION"],
                ["CSV / Excel records", "Validate and create time-aware features", "0-100 risk score and three reasons", "Inspect, monitor, verify, or record disposition"],
            ],
            [39 * mm, 48 * mm, 46 * mm, 41 * mm],
        )
    )
    story += [Spacer(1, 8), Paragraph("What is complete", S["h2"])]
    story += bullets(
        [
            "180-asset deterministic demo dataset with maintenance and inspection history.",
            "Blocking data checks, model comparison, risk bands, explanations, and action recommendations.",
            "Overview, priority queue, asset detail, model evidence, data quality, and handoff screens.",
            "Manual-review safeguard, local disposition log, upload schema validation, and automated tests.",
        ]
    )
    story.append(Spacer(1, 6))
    story.append(card("Important data notice", "All shipped records and metrics are simulated demo evidence. Do not present them as MINECOFIN or institutional performance results.", AMBER))
    story.append(PageBreak())

    story += title(
        "02 - Run locally",
        "Start from a clean machine in two commands",
        "The project is packaged for Windows PowerShell and runs offline after the initial dependency installation.",
    )
    story.append(Paragraph("Recommended setup", S["h2"]))
    story.append(Paragraph("powershell -ExecutionPolicy Bypass -File .\\setup.ps1<br/>.\\run.ps1", S["code"]))
    story.append(Paragraph("Open http://localhost:8501 if the browser does not open automatically.", S["body"]))
    story.append(card("What setup does", "Creates .venv, installs dependencies, regenerates deterministic demo records, validates them, trains the candidate models, and publishes fresh scores.", TEAL))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Useful maintenance commands", S["h2"]))
    story.append(
        data_table(
            [
                ["TASK", "COMMAND"],
                ["Regenerate demo data", ".\\.venv\\Scripts\\python.exe scripts\\generate_demo_data.py"],
                ["Rebuild scores", ".\\.venv\\Scripts\\python.exe scripts\\run_pipeline.py"],
                ["Run tests", ".\\.venv\\Scripts\\python.exe -m pytest"],
                ["Rebuild this guide", ".\\.venv\\Scripts\\python.exe scripts\\build_guide.py"],
            ],
            [55 * mm, 119 * mm],
        )
    )
    story.append(PageBreak())

    story += title(
        "03 - User experience",
        "Reach the highest-risk asset and understand it quickly",
        "The primary path is visible immediately. Secondary evidence and data controls stay available without crowding the maintenance decision.",
    )
    screen_rows = [
        ["SCREEN", "DECISION ANSWERED", "KEY CONTENT"],
        ["Overview", "Where should attention go first?", "Fleet risk profile, top assets, urgent actions"],
        ["Priority queue", "Which assets match today's review capacity?", "Class/band/score filters, reason, last service, action"],
        ["Asset detail", "Why is this asset flagged and what should happen?", "Reasons, feature values, timeline, disposition"],
        ["Model evidence", "How was the ranking checked?", "Recall, precision, PR-AUC, alert rate, guardrails"],
        ["Data quality", "Can these records be trusted for scoring?", "Schema, linkage, plausibility, completeness, upload check"],
    ]
    story.append(data_table(screen_rows, [30 * mm, 63 * mm, 81 * mm]))
    story.append(Spacer(1, 9))
    story.append(card("Human-in-the-loop rule", "The system recommends inspection priority. Authorized staff confirm the action and record a disposition. Repairs are never authorized automatically.", TEAL))
    story.append(PageBreak())

    story += title(
        "04 - Data contract",
        "Validate identity, labels, and plausibility before modeling",
        "A smaller trustworthy table is better than a large inconsistent one. The pipeline stops on blocking schema, linkage, duplicate-ID, codebook, or plausibility failures.",
    )
    story.append(
        data_table(
            [
                ["SOURCE", "REQUIRED FIELDS"],
                ["assets.csv", "asset_id, asset_class, make_model, acquisition_date, usage_value"],
                ["maintenance_events.csv", "event_id, asset_id, event_date, event_type, fault_or_defect, severity, maintenance_cost, downtime_hours"],
                ["inspections.csv", "inspection_id, asset_id, inspection_date, defect, severity, outcome"],
            ],
            [42 * mm, 132 * mm],
        )
    )
    story.append(Spacer(1, 9))
    quality_rows = [["CHECK", "STATUS", "DETAIL"]] + quality[["check", "status", "detail"]].astype(str).values.tolist()
    story.append(Paragraph("Current frozen-input checks", S["h2"]))
    story.append(data_table(quality_rows, [48 * mm, 24 * mm, 102 * mm]))
    story.append(PageBreak())

    story += title(
        "05 - Features and model",
        "Simple, comparable, and explainable",
        "Monthly snapshots use only information known at each scoring date. A future corrective or breakdown event within 60 days is the supervised target.",
    )
    story.append(
        data_table(
            [
                ["FEATURE FAMILY", "EXAMPLES"],
                ["Recency", "Days since service, corrective repair, and inspection"],
                ["Frequency", "Repairs in 90/180 days and repeated fault count"],
                ["Severity", "Maximum recent inspection or corrective-event severity"],
                ["Usage", "Class-aware usage since last service and missing flag"],
                ["Cost / impact", "Recent corrective cost and downtime hours"],
                ["Context", "Asset age, class, and stale-inspection flag"],
            ],
            [45 * mm, 129 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph("Current simulated holdout evidence", S["h2"]))
    story.append(metric_cards(metrics))
    story.append(Spacer(1, 7))
    model_rows = [["MODEL", "RECALL", "PRECISION", "PR-AUC", "ALERT RATE"]]
    for row in metrics["metrics"]:
        model_rows.append([row["model"], f"{row['recall']:.1%}", f"{row['precision']:.1%}", f"{row['pr_auc']:.3f}", f"{row['alert_rate']:.1%}"])
    story.append(data_table(model_rows, [50 * mm, 28 * mm, 32 * mm, 28 * mm, 36 * mm]))
    story.append(PageBreak())

    story += title(
        "06 - Risk, reasons, and actions",
        "A score must lead to an understandable next step",
        "The displayed 0-100 value is an operational ranking score, not a calibrated probability of failure. Fixed bands keep the demo deterministic.",
    )
    story.append(
        data_table(
            [
                ["BAND", "SCORE", "DEFAULT ACTION"],
                ["Critical", "80-100", "Inspect within 24 hours; restrict use if a safety defect is confirmed"],
                ["High", "60-79.9", "Inspect within 48 hours and verify the reported signal"],
                ["Watch", "35-59.9", "Review within seven days and monitor the next cycle"],
                ["Normal", "0-34.9", "Continue scheduled maintenance and monitor monthly"],
                ["Manual review", "No score", "Verify identity and missing records before scoring"],
            ],
            [35 * mm, 30 * mm, 109 * mm],
        )
    )
    story.append(Spacer(1, 8))
    top = scores.dropna(subset=["risk_score"]).head(5)
    top_rows = [["ASSET", "CLASS", "SCORE", "TOP REASON"]]
    for row in top.itertuples(index=False):
        top_rows.append([row.asset_id, row.asset_class, f"{row.risk_score:.1f}", row.reason_1])
    story.append(Paragraph("Current top five demo assets", S["h2"]))
    story.append(data_table(top_rows, [31 * mm, 32 * mm, 24 * mm, 87 * mm]))
    story.append(PageBreak())

    story += title(
        "07 - Quality and release",
        "Break the demo before the judges do",
        "Release checks focus on broken joins, future leakage, impossible scores, contradictory reasons, empty results, and application crashes.",
    )
    story.append(
        data_table(
            [
                ["AREA", "MINIMUM EVIDENCE"],
                ["Data", "No duplicate IDs; valid linkage, dates, usage, costs, and event codes"],
                ["Model", "Fixed feature order, time-based split, bounded output, baseline comparison"],
                ["App", "Clean launch, working filters, sorted queue, matching asset detail"],
                ["Explanations", "Reason text agrees with underlying values"],
                ["Fallbacks", "Sparse assets show manual review; empty filters show a helpful state"],
                ["Reproducibility", "One setup command, one run command, frozen input, regenerated scores"],
            ],
            [38 * mm, 136 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(card("Automated evidence", "The current suite covers blocking data gates, future-event exclusion, sparse history, band boundaries, explanation consistency, score bounds, queue ordering, and manual review.", TEAL))
    story.append(PageBreak())

    story += title(
        "08 - Five-minute live demo",
        "Move from public-sector pain to a visible action",
        "Keep the interaction deterministic and use one high-risk example with readable evidence.",
    )
    steps = [
        ("1", "Problem", "Fixed schedules underuse historical maintenance and inspection records."),
        ("2", "Data", "Show the simulated-data badge, required fields, and passed data gates."),
        ("3", "Overview", "Point out the risk distribution and the highest-priority assets."),
        ("4", "Asset", "Open a Critical asset and explain the score with two or three signals."),
        ("5", "Action", "Record an inspection request and reinforce human authorization."),
        ("6", "Evidence", "Compare rules, Logistic Regression, and Random Forest."),
        ("7", "Close", "Describe the approved-data validation sprint and controlled pilot."),
    ]
    for number, name, detail in steps:
        story.append(card(f"{number}. {name}", detail, AMBER if number in {"1", "7"} else TEAL))
        story.append(Spacer(1, 4))
    story.append(PageBreak())

    story += title(
        "09 - Team and change discipline",
        "Work in parallel without integration chaos",
        "The score-output schema is the shared contract. Material changes must update the code, tests, README, status, changelog, and this PDF together.",
    )
    story.append(
        data_table(
            [
                ["ROLE", "ACCOUNTABILITY"],
                ["Lead / PM", "Scope, issues, integration, decision log, presentation story"],
                ["Data / ML", "Data contract, cleaning, labels, features, models, metrics"],
                ["App / UX", "Screens, filters, queue, asset detail, disposition flow"],
                ["Domain / QA", "Maintenance logic, explanations, action wording, release evidence"],
            ],
            [45 * mm, 129 * mm],
        )
    )
    story.append(Spacer(1, 9))
    story.append(Paragraph("Project structure", S["h2"]))
    story.append(Paragraph("app.py<br/>src/minicofin_pm/{data,pipeline,scoring,ui}.py<br/>scripts/{generate_demo_data,run_pipeline,build_guide}.py<br/>data/{raw/demo,processed}/<br/>models/risk_model.joblib<br/>tests/<br/>output/pdf/", S["code"]))
    story.append(PageBreak())

    story += title(
        "10 - Boundaries and next step",
        "A credible prototype ends with an honest handoff",
        "Operational impact targets require a controlled pilot. The rapid MVP proves technical feasibility and decision usefulness only.",
    )
    story.append(
        data_table(
            [
                ["IN THIS MVP", "DEFERRED"],
                ["File ingestion and validation", "Live IFMIS integration"],
                ["Batch risk scoring and reasons", "Real-time telemetry or hardware retrofits"],
                ["Human inspection recommendation", "Automated repair authorization"],
                ["Local demo audit trail", "Enterprise identity, hosting, and monitoring"],
                ["Simulated model evidence", "Downtime and cost-reduction claims"],
            ],
            [87 * mm, 87 * mm],
        )
    )
    story.append(Spacer(1, 10))
    story.append(card("Next evidence", "Approved source fields, real data volume, label quality, maintenance-SME review, operational baseline, and user feedback.", TEAL))
    story.append(Spacer(1, 5))
    story.append(card("Next engineering", "Approved integration path, authentication, security, monitoring, support, and deployment only after the validation sprint.", AMBER))
    story.append(Spacer(1, 5))
    story.append(card("Definition of ready", "The team can move from a frozen input file to a visible, explained maintenance-risk decision in a repeatable local demo.", NAVY_2))
    return story


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = ROOT / "data" / "processed" / "metrics.json"
    scores_path = ROOT / "data" / "processed" / "risk_scores.csv"
    quality_path = ROOT / "data" / "processed" / "data_quality_checks.csv"
    if not (metrics_path.exists() and scores_path.exists() and quality_path.exists()):
        raise FileNotFoundError("Run scripts/run_pipeline.py before building the guide.")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    scores = pd.read_csv(scores_path)
    quality = pd.read_csv(quality_path)
    doc = SimpleDocTemplate(
        str(OUT_FILE),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
        title="GuideMe - MINECOFIN Predictive Maintenance",
        author="Tech Titans / AssetCare AI project team",
        subject="Local run, presentation, model, data, and QA guide",
    )
    doc.build(build_story(metrics, scores, quality), onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"Created {OUT_FILE}")


if __name__ == "__main__":
    main()

