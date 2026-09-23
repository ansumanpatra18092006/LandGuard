from __future__ import annotations

from io import BytesIO
from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.security import require_roles
from app.core.access import OPERATIONAL_ROLES
from app.schemas.route_analysis import RouteAnalysisRequest, RouteAnalysisResponse, RouteReportRequest
from app.services.route_analysis_service import RouteAnalysisError, analyze_route

router = APIRouter(prefix="/route-analysis", tags=["route-analysis"])


@router.post("/analyze", response_model=RouteAnalysisResponse)
def analyze_route_endpoint(
    payload: RouteAnalysisRequest,
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    try:
        # Use the signed-in officer's assigned scope to disambiguate short place names.
        # Example: "Padmapur" exists in multiple Odisha districts; a Rayagada district
        # officer should resolve to Padmapur, Rayagada without manually typing the district.
        return analyze_route(payload, state=user.get("state"), district=user.get("district"))
    except RouteAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _report_pdf(analysis: RouteAnalysisResponse) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="LandGuard Route Feasibility Analysis",
        author="LandGuard AI",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="LGTitle", parent=styles["Title"], fontSize=19, leading=23, spaceAfter=6, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="LGSub", parent=styles["Normal"], fontSize=9.5, leading=13, textColor=colors.HexColor("#475467"), spaceAfter=10))
    styles.add(ParagraphStyle(name="LGH2", parent=styles["Heading2"], fontSize=12.5, leading=16, spaceBefore=9, spaceAfter=5, textColor=colors.HexColor("#12372f")))
    styles.add(ParagraphStyle(name="LGBody", parent=styles["BodyText"], fontSize=9.5, leading=14, spaceAfter=5))
    styles.add(ParagraphStyle(name="LGSmall", parent=styles["BodyText"], fontSize=8.5, leading=12, textColor=colors.HexColor("#667085")))

    def mapped_value(candidate, value):
        return "Not verified" if candidate.data_coverage_percent < 55 else str(value)

    story = [
        Paragraph("LandGuard AI - Route Feasibility & Obstacle Screening", styles["LGTitle"]),
        Paragraph(
            "Pre-feasibility decision-support report. AI recommends; authorized officials and engineers decide.",
            styles["LGSub"],
        ),
    ]

    meta = [
        ["Origin", analysis.origin.label],
        ["Destination", analysis.destination.label],
        ["Construction type", analysis.construction_type.replace("_", " ").title()],
        ["Planning mode", analysis.alignment_mode.replace("_", " ").title()],
        ["Screening / ROW width", f"{analysis.corridor_width_m:.0f} m"],
        ["Analysis confidence", analysis.analysis_confidence],
        ["Recommended candidate", analysis.recommended_route_id.replace("_", " ").title()],
    ]
    if analysis.base_cost_crore_per_km is not None:
        meta.append(["Officer-entered base cost", f"Rs {analysis.base_cost_crore_per_km:.2f} crore/km"])
    table = Table(meta, colWidths=[48 * mm, 118 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef7f4")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1d2939")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d0d5dd")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [table, Spacer(1, 5 * mm), Paragraph("Executive summary", styles["LGH2"]), Paragraph(escape(analysis.executive_summary), styles["LGBody"])]

    if analysis.official_road_reference is not None:
        ref = analysis.official_road_reference
        story.append(Paragraph("Official road reference", styles["LGH2"]))
        story.append(Paragraph(escape(
            f"{ref.road_name} | {ref.category} | official listed length {ref.official_length_km:.3f} km | "
            f"{ref.authority}. Candidate-length difference: {ref.route_length_difference_percent:.1f}% if available."
        ), styles["LGBody"]))
        if ref.note:
            story.append(Paragraph(escape(ref.note), styles["LGSmall"]))
        story.append(Paragraph(escape("Source: " + ref.source_url), styles["LGSmall"]))

    story.append(Paragraph("Route comparison", styles["LGH2"]))
    comparison = [["Route", "Distance", "Burden", "Cost index", "Structures", "Sensitive", "Water"]]
    for candidate in analysis.candidates:
        obs = candidate.obstacle_summary
        sensitive = obs.schools + obs.healthcare + obs.religious
        comparison.append([
            candidate.label,
            f"{candidate.distance_km:.2f} km",
            (f"{candidate.route_burden_score:.1f}/100" if candidate.route_burden_score is not None else "Not scored"),
            f"{candidate.comparative_cost_index:.1f}",
            mapped_value(candidate, obs.mapped_buildings),
            mapped_value(candidate, sensitive),
            mapped_value(candidate, obs.water_crossings),
        ])
    comp = Table(comparison, repeatRows=1, colWidths=[26*mm, 24*mm, 24*mm, 24*mm, 24*mm, 22*mm, 18*mm])
    comp.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f5c4f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d0d5dd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(comp)

    for candidate in analysis.candidates:
        obs = candidate.obstacle_summary
        recommended = candidate.route_id == analysis.recommended_route_id
        story.append(Paragraph(f"{candidate.label}{' - Recommended' if recommended else ''}", styles["LGH2"]))
        detail = [
            ["Distance", f"{candidate.distance_km:.2f} km"],
            ["Network travel time", (f"{candidate.duration_min:.1f} min" if candidate.duration_min is not None else "Concept alignment - not a travel-time route")],
            ["Route burden score", (f"{candidate.route_burden_score:.1f}/100 (lower is better)" if candidate.route_burden_score is not None else "Not scored")],
            ["Evidence-adjusted screening score", f"{candidate.feasibility_score:.1f}/100 - {candidate.feasibility_label}" if candidate.feasibility_score is not None else candidate.feasibility_label],
            ["Live-data coverage", f"{candidate.data_coverage_percent:.0f}% of screening layers available"],
            ["Comparative cost index", f"{candidate.comparative_cost_index:.1f} (best screened route ~= 100)"],
            ["Mapped buildings", mapped_value(candidate, obs.mapped_buildings)],
            ["Residential / commercial", ("Not verified" if candidate.data_coverage_percent < 55 else f"{obs.residential} / {obs.commercial}")],
            ["Government/public / institutional", ("Not verified" if candidate.data_coverage_percent < 55 else f"{obs.government_public} / {obs.institutional}")],
            ["Shops/businesses", mapped_value(candidate, obs.shops_businesses)],
            ["Education / healthcare / religious", ("Not verified" if candidate.data_coverage_percent < 55 else f"{obs.schools} / {obs.healthcare} / {obs.religious}")],
            ["Mapped water crossings/features", mapped_value(candidate, obs.water_crossings)],
            ["Rail / power-line crossings", ("Not verified" if candidate.data_coverage_percent < 55 else f"{obs.railway_crossings} / {obs.powerline_crossings}")],
            ["Forest/protected / settlements", ("Not verified" if candidate.data_coverage_percent < 55 else f"{obs.forest_protected_hits} / {obs.settlements}")],
            ["Farmland / residential land-use", ("Not verified" if candidate.data_coverage_percent < 55 else f"{obs.farmland_hits} / {obs.residential_landuse_hits}")],
            ["Terrain elevation range", (f"{candidate.terrain_summary.elevation_range_m:.1f} m" if candidate.terrain_summary.available else "Not verified")],
            ["Mean / max sampled grade", (f"{candidate.terrain_summary.mean_abs_grade_percent:.2f}% / {candidate.terrain_summary.max_grade_percent:.2f}%" if candidate.terrain_summary.available else "Not verified")],
            ["Indicative screening footprint", f"{candidate.screening_area_ha:.2f} ha"],
            ["Mapped-data coverage", f"{candidate.data_coverage_percent:.0f}% - {candidate.mapped_data_status.replace("_", " " ).title()}"],
            ["Route basis", candidate.route_basis],
        ]
        if candidate.indicative_cost_crore is not None:
            detail.append(["Indicative comparative cost", f"Rs {candidate.indicative_cost_crore:.2f} crore"])
        t = Table(detail, colWidths=[58*mm, 108*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#eaecf0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(escape("Strengths: " + "; ".join(candidate.strengths)), styles["LGSmall"]))
        story.append(Paragraph(escape("Concerns: " + "; ".join(candidate.concerns)), styles["LGSmall"]))
        story.append(Paragraph(escape("Google Maps endpoint/reference: " + candidate.google_maps_url), styles["LGSmall"]))
        story.append(Paragraph(escape(candidate.google_maps_note), styles["LGSmall"]))

    story.append(Paragraph("Key findings", styles["LGH2"]))
    for item in analysis.key_findings:
        story.append(Paragraph(escape("- " + item), styles["LGBody"]))

    story.append(Paragraph("Data sources", styles["LGH2"]))
    for item in analysis.data_sources:
        story.append(Paragraph(escape("- " + item), styles["LGBody"]))
    story.append(Paragraph(escape("Provider status: " + analysis.provider_status), styles["LGSmall"]))

    story.append(Paragraph("Land-acquisition data readiness", styles["LGH2"]))
    for item in analysis.acquisition_data_readiness:
        story.append(Paragraph(escape("- " + item), styles["LGBody"]))

    story.append(Paragraph("Limitations and decision boundary", styles["LGH2"]))
    for item in analysis.limitations:
        story.append(Paragraph(escape("- " + item), styles["LGBody"]))

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "LandGuard route analysis is an early screening aid. It does not replace DPR preparation, cadastral survey, utility detection, environmental appraisal, geotechnical investigation, valuation, statutory acquisition procedure or competent-authority approval.",
        styles["LGSmall"],
    ))

    doc.build(story)
    return buffer.getvalue()


@router.post("/report")
def route_report(
    payload: RouteReportRequest,
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    pdf = _report_pdf(payload.analysis)
    filename = "LandGuard_Route_Feasibility_Analysis.pdf"
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
