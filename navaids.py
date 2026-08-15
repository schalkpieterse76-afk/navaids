import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json, os, datetime, calendar, threading, subprocess

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, PageBreak, HRFlowable)
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    RL_OK = True
except ImportError:
    RL_OK = False


DATA_FILE           = "navaids_data.json"
NOTAM_FILE          = "navaids_notams.json"
MAINT_SCHEDULE_FILE = "navaids_maint_schedule.json"

MAINT_WORK_HOURS = {
    "Scheduled Maintenance":   4.0,
    "Unscheduled Maintenance": 2.0,
    "Inspection":              1.5,
    "Calibration":             3.0,
    "NOTAM":                   0.5,
    "Other":                   1.0,
}

NOTAM_TYPES      = list(MAINT_WORK_HOURS.keys())
NOTAM_PRIORITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
NOTAM_STATUSES   = ["Open", "In Progress", "Closed"]

NOTAM_COLUMNS = [
    ("ID",          60),
    ("Station",     80),
    ("NAVAID",      90),
    ("Type",       110),
    ("Priority",    70),
    ("Due Date",    90),
    ("Status",      80),
    ("Technician", 100),
    ("Est Hours",   70),
    ("Work Order",  90),
]


class BinaryPatcher:
    @classmethod
    def create_patch(cls, original: bytes, modified: bytes) -> bytes:
        """Return a simple XOR-delta patch: 4-byte len_orig + 4-byte len_mod + xor-bytes (up to min length) + tail."""
        len_orig = len(original)
        len_mod = len(modified)
        min_len = min(len_orig, len_mod)
        header = len_orig.to_bytes(4, "big") + len_mod.to_bytes(4, "big")
        delta = bytes(original[i] ^ modified[i] for i in range(min_len))
        tail = modified[min_len:]
        return header + delta + tail

    @classmethod
    def apply_patch(cls, original: bytes, patch: bytes) -> bytes:
        """Apply patch produced by create_patch and return modified bytes."""
        if len(patch) < 8:
            raise ValueError("invalid patch")
        len_orig = int.from_bytes(patch[0:4], "big")
        len_mod = int.from_bytes(patch[4:8], "big")
        if len(original) != len_orig:
            raise ValueError("original length mismatch")
        min_len = min(len_orig, len_mod)
        if len(patch) < 8 + min_len:
            raise ValueError("patch data incomplete")
        xor_bytes = patch[8:8 + min_len]
        tail = patch[8 + min_len:]
        rebuilt = bytearray()
        for i in range(min_len):
            rebuilt.append(original[i] ^ xor_bytes[i])
        if len_mod > min_len:
            expected_tail = len_mod - min_len
            if len(tail) != expected_tail:
                raise ValueError("patch tail length mismatch")
            rebuilt.extend(tail)
        return bytes(rebuilt[:len_mod])


class MaintenanceSchedulePDF:
    """
    Generates a printable A4 maintenance schedule PDF from open NOTAM records.
    """

    COLOURS = {}

    @classmethod
    def generate(cls, path: str, notam_records: list,
                 org_name: str = "NAVAIDS Operations",
                 prepared_by: str = "",
                 date_from: str = "",
                 date_to:   str = "",
                 include_closed: bool = False,
                 include_calendar: bool = True,
                 include_detail: bool = True,
                 progress_cb=None) -> dict:
        if not RL_OK:
            raise RuntimeError("reportlab not installed")

        def progress(pct, msg):
            if callable(progress_cb):
                progress_cb(pct, msg)

        start_date = cls._parse_date(date_from) or datetime.date.today()
        end_date = cls._parse_date(date_to) or (start_date + datetime.timedelta(days=90))
        if end_date < start_date:
            start_date, end_date = end_date, start_date

        filtered = []
        for rec in notam_records or []:
            due = cls._parse_date(rec.get("due_date", ""))
            if due is None:
                continue
            if not include_closed and rec.get("status") == "Closed":
                continue
            if start_date <= due <= end_date:
                filtered.append(dict(rec))

        by_priority = {p: 0 for p in NOTAM_PRIORITIES}
        by_type = {t: 0 for t in NOTAM_TYPES}
        by_tech = {}
        total_hours = 0.0
        for rec in filtered:
            priority = rec.get("priority", "")
            ntype = rec.get("type", "")
            tech = (rec.get("technician", "") or "UNASSIGNED").strip() or "UNASSIGNED"
            hours = cls._safe_float(rec.get("est_hours", 0.0), 0.0)
            total_hours += hours
            by_priority[priority] = by_priority.get(priority, 0) + 1
            by_type[ntype] = by_type.get(ntype, 0) + 1
            by_tech[tech] = by_tech.get(tech, 0.0) + hours

        month_keys = set()
        cursor = datetime.date(start_date.year, start_date.month, 1)
        limit = datetime.date(end_date.year, end_date.month, 1)
        while cursor <= limit:
            month_keys.add((cursor.year, cursor.month))
            if cursor.month == 12:
                cursor = datetime.date(cursor.year + 1, 1, 1)
            else:
                cursor = datetime.date(cursor.year, cursor.month + 1, 1)

        summary = {
            "total_open": len(filtered),
            "total_hours": total_hours,
            "by_priority": by_priority,
            "by_type": by_type,
            "by_tech": by_tech,
            "months": len(month_keys),
            "path": path,
        }

        progress(10, "Building cover page…")
        doc = SimpleDocTemplate(
            path,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )
        styles = cls._build_styles()
        story = []
        cls._cover_page(
            story, styles, summary, filtered, org_name, prepared_by,
            start_date.isoformat(), end_date.isoformat()
        )

        if include_calendar:
            progress(30, "Building calendar pages…")
            cls._calendar_pages(story, styles, filtered, start_date, end_date)

        if include_detail:
            progress(70, "Building detail table…")
            cls._detail_table(story, styles, filtered)

        progress(90, "Finalising…")

        def first_page(canvas, doc_obj):
            return None

        def later_pages(canvas, doc_obj):
            cls._draw_header_footer(canvas, doc_obj, org_name)

        doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
        progress(100, "Done.")
        return summary

    @classmethod
    def _build_styles(cls):
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="CoverOrg",
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            textColor=HexColor("#00408C"),
            spaceAfter=6,
        ))
        styles.add(ParagraphStyle(
            name="CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            textColor=black,
            spaceAfter=4,
        ))
        styles.add(ParagraphStyle(
            name="CoverSub",
            fontName="Helvetica",
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.grey,
        ))
        styles.add(ParagraphStyle(
            name="CenterNormal",
            fontName="Helvetica",
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            textColor=black,
        ))
        styles.add(ParagraphStyle(
            name="SectionTitle",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            alignment=TA_LEFT,
            textColor=HexColor("#00408C"),
            spaceAfter=4,
            spaceBefore=6,
        ))
        styles.add(ParagraphStyle(
            name="MonthTitle",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
            alignment=TA_CENTER,
            textColor=HexColor("#00408C"),
            spaceAfter=8,
        ))
        styles.add(ParagraphStyle(
            name="CalendarCell",
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            alignment=TA_LEFT,
        ))
        styles.add(ParagraphStyle(
            name="CalendarDay",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9,
            alignment=TA_LEFT,
            textColor=colors.grey,
        ))
        styles.add(ParagraphStyle(
            name="Tiny",
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            alignment=TA_LEFT,
        ))
        styles.add(ParagraphStyle(
            name="TinyCenter",
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            alignment=TA_CENTER,
        ))
        return styles

    @classmethod
    def _cover_page(cls, story, styles, summary, records, org_name, prepared_by, date_from, date_to):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        story.append(Spacer(1, 20 * mm))
        story.append(Paragraph(org_name or "NAVAIDS Operations", styles["CoverOrg"]))
        story.append(Paragraph("NAVAID MAINTENANCE SCHEDULE", styles["CoverTitle"]))
        subtitle = "Generated: {0}  |  Prepared by: {1}".format(timestamp, prepared_by or "")
        story.append(Paragraph(subtitle, styles["CoverSub"]))
        story.append(Spacer(1, 3 * mm))
        story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#00408C")))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            "Schedule Period: {0} to {1}".format(date_from, date_to),
            styles["CenterNormal"]
        ))
        story.append(Spacer(1, 6 * mm))

        alt_bg = cls.COLOURS.get("ALT", (HexColor("#F0F4F8"), black))[0]
        header_bg, header_fg = cls.COLOURS.get("HEADER", (HexColor("#00408C"), white))
        stat_rows = [
            ["Metric", "Value"],
            ["Total Open Items", str(summary["total_open"])],
            ["Total Estimated Hours", "{0:.1f} h".format(summary["total_hours"])],
            ["Critical Items", str(summary["by_priority"].get("CRITICAL", 0))],
            ["High Priority Items", str(summary["by_priority"].get("HIGH", 0))],
            ["Medium Priority Items", str(summary["by_priority"].get("MEDIUM", 0))],
            ["Low Priority Items", str(summary["by_priority"].get("LOW", 0))],
        ]
        stat_table = Table(stat_rows, colWidths=[80 * mm, 40 * mm], hAlign="CENTER")
        stat_style = [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), header_fg),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        for row_idx in range(1, len(stat_rows)):
            if row_idx % 2 == 1:
                stat_style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), alt_bg))
        stat_table.setStyle(TableStyle(stat_style))
        story.append(stat_table)
        story.append(Spacer(1, 6 * mm))
        story.append(HRFlowable(width="100%", thickness=0.8, color=colors.grey))
        story.append(Spacer(1, 3 * mm))

        story.append(Paragraph("Workload by Technician", styles["SectionTitle"]))
        tech_rows = [["Technician", "Assigned Items", "Est. Hours", "Item Types"]]
        tech_details = []
        for tech, hours in summary["by_tech"].items():
            tech_records = [r for r in records if ((r.get("technician", "") or "UNASSIGNED").strip() or "UNASSIGNED") == tech]
            type_counts = {}
            for rec in tech_records:
                type_name = rec.get("type", "Other") or "Other"
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
            type_text = ", ".join(
                "{0}({1})".format(name, count)
                for name, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
            ) or "-"
            tech_details.append((tech, len(tech_records), hours, type_text))
        tech_details.sort(key=lambda item: (-item[1], item[0]))
        if not tech_details:
            tech_rows.append(["UNASSIGNED", "0", "0.0", "-"])
        else:
            for tech, items, hours, type_text in tech_details:
                tech_rows.append([tech, str(items), "{0:.1f}".format(hours), type_text])

        tech_table = Table(tech_rows, colWidths=[42 * mm, 28 * mm, 24 * mm, 86 * mm])
        tech_style = [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), header_fg),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 1), (2, -1), "CENTER"),
        ]
        for row_idx in range(1, len(tech_rows)):
            if row_idx % 2 == 1:
                tech_style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), alt_bg))
        tech_table.setStyle(TableStyle(tech_style))
        story.append(tech_table)
        story.append(Spacer(1, 5 * mm))

        story.append(Paragraph("Workload by NAVAID Type", styles["SectionTitle"]))
        navaid_groups = {}
        for rec in records:
            name = rec.get("navaid", "") or "UNKNOWN"
            navaid_groups.setdefault(name, {"items": 0, "hours": 0.0})
            navaid_groups[name]["items"] += 1
            navaid_groups[name]["hours"] += cls._safe_float(rec.get("est_hours", 0.0), 0.0)
        navaid_rows = [["NAVAID", "Items", "Hours"]]
        ordered_navaids = sorted(navaid_groups.items(), key=lambda item: (-item[1]["items"], item[0]))
        if not ordered_navaids:
            navaid_rows.append(["-", "0", "0.0"])
        else:
            for name, data in ordered_navaids:
                navaid_rows.append([name, str(data["items"]), "{0:.1f}".format(data["hours"])])
        navaid_table = Table(navaid_rows, colWidths=[90 * mm, 25 * mm, 25 * mm], hAlign="LEFT")
        navaid_style = [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), header_fg),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ]
        for row_idx in range(1, len(navaid_rows)):
            if row_idx % 2 == 1:
                navaid_style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), alt_bg))
        navaid_table.setStyle(TableStyle(navaid_style))
        story.append(navaid_table)

    @classmethod
    def _calendar_pages(cls, story, styles, records, start_date, end_date):
        cell_width = (A4[0] - 30 * mm) / 7.0
        cursor = datetime.date(start_date.year, start_date.month, 1)
        last_month = datetime.date(end_date.year, end_date.month, 1)
        today = datetime.date.today()
        day_map = {}
        for rec in records:
            due = cls._parse_date(rec.get("due_date", ""))
            if due is not None:
                day_map.setdefault(due.isoformat(), []).append(rec)

        while cursor <= last_month:
            story.append(PageBreak())
            story.append(Paragraph(cursor.strftime("%B %Y"), styles["MonthTitle"]))
            rows = [["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]]
            table_style = [
                ("BACKGROUND", (0, 0), (-1, 0), cls.COLOURS.get("HEADER", (HexColor("#00408C"), white))[0]),
                ("TEXTCOLOR", (0, 0), (-1, 0), cls.COLOURS.get("HEADER", (HexColor("#00408C"), white))[1]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
            weeks = calendar.monthcalendar(cursor.year, cursor.month)
            row_heights = [14 * mm]
            for week_index, week in enumerate(weeks, start=1):
                row_heights.append(20 * mm)
                row_cells = []
                for day_index, day in enumerate(week):
                    if day == 0:
                        row_cells.append("")
                        continue
                    current_date = datetime.date(cursor.year, cursor.month, day)
                    day_key = current_date.isoformat()
                    items = day_map.get(day_key, [])
                    parts = ['<font color="#777777"><b>{0}</b></font>'.format(day)]
                    display_items = items
                    overflow = 0
                    if len(items) > 3:
                        display_items = items[:2]
                        overflow = len(items) - 2
                    for rec in display_items:
                        _, stroke = cls._priority_colour(rec.get("priority", "LOW"))
                        if stroke is not None and hasattr(stroke, "red"):
                            colour_hex = "#{0:02X}{1:02X}{2:02X}".format(
                                int(stroke.red * 255),
                                int(stroke.green * 255),
                                int(stroke.blue * 255),
                            )
                        else:
                            colour_hex = "#000000"
                        line = "[{0}] {1} {2} {3:.1f}h".format(
                            rec.get("work_order", "") or rec.get("id", ""),
                            rec.get("station", ""),
                            rec.get("navaid", ""),
                            cls._safe_float(rec.get("est_hours", 0.0), 0.0),
                        )
                        parts.append('<font color="{0}">{1}</font>'.format(colour_hex, cls._xml(line)))
                    if overflow > 0:
                        parts.append('<font color="#555555">+{0} more</font>'.format(overflow))
                    row_cells.append(Paragraph("<br/>".join(parts), styles["CalendarCell"]))

                    if current_date == today:
                        table_style.append(("BACKGROUND", (day_index, week_index), (day_index, week_index), HexColor("#CCE5FF")))
                    elif current_date < today:
                        has_open = any((rec.get("status") != "Closed") for rec in items)
                        if has_open:
                            table_style.append(("BACKGROUND", (day_index, week_index), (day_index, week_index), HexColor("#FFCCCC")))
                rows.append(row_cells)

            cal_table = Table(rows, colWidths=[cell_width] * 7, rowHeights=row_heights)
            cal_table.setStyle(TableStyle(table_style))
            story.append(cal_table)
            if cursor.month == 12:
                cursor = datetime.date(cursor.year + 1, 1, 1)
            else:
                cursor = datetime.date(cursor.year, cursor.month + 1, 1)

    @classmethod
    def _detail_table(cls, story, styles, records):
        story.append(PageBreak())
        story.append(Paragraph("NOTAM Detail Schedule", styles["MonthTitle"]))
        priority_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        ordered = sorted(
            records,
            key=lambda rec: (
                cls._parse_date(rec.get("due_date", "")) or datetime.date.max,
                priority_rank.get(rec.get("priority", ""), 9),
                rec.get("station", ""),
            ),
        )

        base_widths = [15, 18, 15, 28, 12, 22, 12, 24, 30, 14]
        scale = (A4[0] - 30 * mm) / (190.0 * mm)
        col_widths = [width * mm * scale for width in base_widths]
        rows = [[
            "WO#", "Station", "NAVAID", "Type", "Pri", "Due", "Hrs", "Tech", "Description", "Status"
        ]]
        row_kinds = ["header"]

        tech_totals = {}
        tech_last_idx = {}
        for idx, rec in enumerate(ordered):
            tech = (rec.get("technician", "") or "UNASSIGNED").strip() or "UNASSIGNED"
            tech_totals.setdefault(tech, {"count": 0, "hours": 0.0})
            tech_totals[tech]["count"] += 1
            tech_totals[tech]["hours"] += cls._safe_float(rec.get("est_hours", 0.0), 0.0)
            tech_last_idx[tech] = idx

        total_hours = 0.0
        for idx, rec in enumerate(ordered):
            tech = (rec.get("technician", "") or "UNASSIGNED").strip() or "UNASSIGNED"
            hours = cls._safe_float(rec.get("est_hours", 0.0), 0.0)
            total_hours += hours
            rows.append([
                rec.get("work_order", "") or rec.get("id", ""),
                rec.get("station", ""),
                rec.get("navaid", ""),
                rec.get("type", ""),
                rec.get("priority", ""),
                rec.get("due_date", ""),
                "{0:.1f}".format(hours),
                tech,
                rec.get("description", ""),
                rec.get("status", ""),
            ])
            row_kinds.append("record")
            if tech_last_idx.get(tech) == idx:
                subtotal = tech_totals[tech]
                rows.append([
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "{0:.1f}".format(subtotal["hours"]),
                    "{0} subtotal".format(tech),
                    "{0} items".format(subtotal["count"]),
                    "",
                ])
                row_kinds.append("subtotal")

        rows.append([
            "",
            "",
            "",
            "",
            "",
            "TOTAL",
            "{0:.1f}".format(total_hours),
            "",
            "{0} items".format(len(ordered)),
            "",
        ])
        row_kinds.append("grand")

        detail_table = Table(rows, colWidths=col_widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), cls.COLOURS.get("HEADER", (HexColor("#00408C"), white))[0]),
            ("TEXTCOLOR", (0, 0), (-1, 0), cls.COLOURS.get("HEADER", (HexColor("#00408C"), white))[1]),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (6, 1), (6, -1), "CENTER"),
            ("ALIGN", (4, 1), (5, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for row_idx in range(1, len(rows)):
            kind = row_kinds[row_idx]
            if kind == "record":
                priority = rows[row_idx][4]
                bg, fg = cls._priority_colour(priority)
                if bg is not None:
                    style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg))
                if fg is not None:
                    style.append(("TEXTCOLOR", (0, row_idx), (-1, row_idx), fg))
            elif kind == "subtotal":
                style.extend([
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), HexColor("#DDDDDD")),
                    ("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
                ])
            elif kind == "grand":
                style.extend([
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), HexColor("#00408C")),
                    ("TEXTCOLOR", (0, row_idx), (-1, row_idx), white),
                    ("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
                ])
        detail_table.setStyle(TableStyle(style))
        story.append(detail_table)

    @classmethod
    def _priority_colour(cls, priority: str):
        return cls.COLOURS.get(priority, cls.COLOURS.get("LOW", (None, None)))

    @classmethod
    def _parse_date(cls, value):
        if isinstance(value, datetime.date):
            return value
        if not value:
            return None
        try:
            return datetime.datetime.strptime(str(value), "%Y-%m-%d").date()
        except Exception:
            return None

    @classmethod
    def _safe_float(cls, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    @classmethod
    def _xml(cls, text):
        text = str(text)
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @classmethod
    def _draw_header_footer(cls, canvas, doc, org_name):
        page_num = canvas.getPageNumber()
        if page_num <= 1:
            return
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(HexColor("#00408C"))
        canvas.drawString(doc.leftMargin, A4[1] - 10 * mm, org_name or "NAVAIDS Operations")
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(A4[0] - doc.rightMargin, 8 * mm, "Page {0}".format(page_num))
        canvas.restoreState()


if RL_OK:
    MaintenanceSchedulePDF.COLOURS = {
        "CRITICAL": (HexColor("#FFCCCC"), HexColor("#CC0000")),
        "HIGH":     (HexColor("#FFE5CC"), HexColor("#CC6600")),
        "MEDIUM":   (HexColor("#FFFACC"), HexColor("#888800")),
        "LOW":      (HexColor("#CCFFCC"), HexColor("#006600")),
        "CLOSED":   (HexColor("#EEEEEE"), HexColor("#888888")),
        "HEADER":   (HexColor("#00408C"), white),
        "ALT":      (HexColor("#F0F4F8"), black),
    }


class NAVAIDSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NAVAIDS Maintenance System")
        self.root.geometry("1200x700")

        self.config_data = self._load_json(DATA_FILE, {})
        self.notam_records = self._load_json(NOTAM_FILE, [])
        if not isinstance(self.notam_records, list):
            self.notam_records = []

        self._notam_counter = self._calc_notam_counter()

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)
        notam_tab = ttk.Frame(notebook)
        notebook.add(notam_tab, text="NOTAMs")
        self._tab_notam(notam_tab)

    def _load_json(self, path, default):
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return default

    def _save_config(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as handle:
                json.dump(self.config_data, handle, indent=2)
        except Exception as exc:
            messagebox.showerror("Save Error", "Could not save configuration:\n{0}".format(exc))

    def _calc_notam_counter(self):
        max_num = 0
        for rec in self.notam_records:
            rid = str(rec.get("id", ""))
            if rid.startswith("NTM-"):
                try:
                    max_num = max(max_num, int(rid.split("-", 1)[1]))
                except Exception:
                    pass
        return max_num + 1

    def _tab_notam(self, parent):
        top = ttk.LabelFrame(parent, text="NOTAM Details")
        top.pack(fill="x", padx=10, pady=10)

        today = datetime.date.today().isoformat()
        self.ntm = {
            "Station": tk.StringVar(),
            "NAVAID": tk.StringVar(),
            "Type": tk.StringVar(),
            "Priority": tk.StringVar(),
            "Due Date": tk.StringVar(value=today),
            "Status": tk.StringVar(value="Open"),
            "Technician": tk.StringVar(),
            "Description": tk.StringVar(),
            "Est. Hours": tk.StringVar(value="1.0"),
            "Work Order": tk.StringVar(),
        }

        fields_row0 = [
            ("Station", 0),
            ("NAVAID", 1),
            ("Type", 2),
            ("Priority", 3),
        ]
        for label, col in fields_row0:
            ttk.Label(top, text=label).grid(row=0, column=col * 2, padx=5, pady=5, sticky="w")
        ttk.Entry(top, textvariable=self.ntm["Station"]).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Entry(top, textvariable=self.ntm["NAVAID"]).grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        ttk.Combobox(top, textvariable=self.ntm["Type"], values=NOTAM_TYPES, state="readonly").grid(row=0, column=5, padx=5, pady=5, sticky="ew")
        ttk.Combobox(top, textvariable=self.ntm["Priority"], values=NOTAM_PRIORITIES, state="readonly").grid(row=0, column=7, padx=5, pady=5, sticky="ew")

        fields_row1 = [
            ("Due Date", 0),
            ("Status", 1),
            ("Technician", 2),
            ("Est. Hours", 3),
            ("Work Order", 4),
        ]
        for label, col in fields_row1:
            ttk.Label(top, text=label).grid(row=1, column=col * 2, padx=5, pady=5, sticky="w")
        ttk.Entry(top, textvariable=self.ntm["Due Date"]).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Combobox(top, textvariable=self.ntm["Status"], values=NOTAM_STATUSES, state="readonly").grid(row=1, column=3, padx=5, pady=5, sticky="ew")
        ttk.Entry(top, textvariable=self.ntm["Technician"]).grid(row=1, column=5, padx=5, pady=5, sticky="ew")
        ttk.Entry(top, textvariable=self.ntm["Est. Hours"]).grid(row=1, column=7, padx=5, pady=5, sticky="ew")
        ttk.Entry(top, textvariable=self.ntm["Work Order"]).grid(row=1, column=9, padx=5, pady=5, sticky="ew")

        ttk.Label(top, text="Description").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(top, textvariable=self.ntm["Description"]).grid(row=2, column=1, columnspan=9, padx=5, pady=5, sticky="ew")

        for col in range(10):
            top.columnconfigure(col, weight=1 if col % 2 == 1 else 0)

        self.ntm["Type"].trace_add("write", self._notam_type_changed)

        bf = ttk.Frame(parent)
        bf.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bf, text="➕ Add", command=self._notam_add).pack(side="left", padx=4)
        ttk.Button(bf, text="✏️ Update", command=self._notam_update).pack(side="left", padx=4)
        ttk.Button(bf, text="🗑️ Delete", command=self._notam_delete).pack(side="left", padx=4)
        ttk.Button(bf, text="🔄 Clear", command=self._notam_clear).pack(side="left", padx=4)
        ttk.Button(bf, text="📅 Print Schedule PDF", command=self._notam_print_schedule).pack(side="left", padx=4)

        tvf = ttk.Frame(parent)
        tvf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        columns = [name for name, _ in NOTAM_COLUMNS]
        self.notam_tree = ttk.Treeview(tvf, columns=columns, show="headings", selectmode="browse")
        for name, width in NOTAM_COLUMNS:
            self.notam_tree.heading(name, text=name)
            self.notam_tree.column(name, width=width, anchor="w")
        yscroll = ttk.Scrollbar(tvf, orient="vertical", command=self.notam_tree.yview)
        xscroll = ttk.Scrollbar(tvf, orient="horizontal", command=self.notam_tree.xview)
        self.notam_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.notam_tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        self.notam_tree.bind("<<TreeviewSelect>>", self._notam_on_select)
        self._notam_refresh()

    def _notam_add(self):
        values = self._notam_vals()
        missing = [name for name in ("Station", "NAVAID", "Type", "Priority", "Due Date") if not values.get(name)]
        if missing:
            messagebox.showwarning("Validation", "Please complete: {0}".format(", ".join(missing)))
            return
        if not MaintenanceSchedulePDF._parse_date(values["Due Date"]):
            messagebox.showwarning("Validation", "Due Date must be YYYY-MM-DD.")
            return
        est_hours = MaintenanceSchedulePDF._safe_float(values.get("Est. Hours"), 1.0)
        record = {
            "id": "NTM-{0:04d}".format(self._notam_counter),
            "station": values["Station"],
            "navaid": values["NAVAID"],
            "type": values["Type"],
            "priority": values["Priority"],
            "due_date": values["Due Date"],
            "status": values["Status"] or "Open",
            "technician": values["Technician"],
            "description": values["Description"],
            "est_hours": est_hours,
            "work_order": values["Work Order"],
        }
        self.notam_records.append(record)
        self._notam_counter += 1
        self._notam_save()
        self._notam_refresh()
        self._notam_clear()

    def _notam_update(self):
        selected = self.notam_tree.selection()
        if not selected:
            messagebox.showwarning("Update NOTAM", "Please select a NOTAM to update.")
            return
        values = self._notam_vals()
        missing = [name for name in ("Station", "NAVAID", "Type", "Priority", "Due Date") if not values.get(name)]
        if missing:
            messagebox.showwarning("Validation", "Please complete: {0}".format(", ".join(missing)))
            return
        if not MaintenanceSchedulePDF._parse_date(values["Due Date"]):
            messagebox.showwarning("Validation", "Due Date must be YYYY-MM-DD.")
            return
        item_id = selected[0]
        record_id = self.notam_tree.item(item_id, "values")[0]
        for rec in self.notam_records:
            if rec.get("id") == record_id:
                rec["station"] = values["Station"]
                rec["navaid"] = values["NAVAID"]
                rec["type"] = values["Type"]
                rec["priority"] = values["Priority"]
                rec["due_date"] = values["Due Date"]
                rec["status"] = values["Status"] or "Open"
                rec["technician"] = values["Technician"]
                rec["description"] = values["Description"]
                rec["est_hours"] = MaintenanceSchedulePDF._safe_float(values.get("Est. Hours"), 1.0)
                rec["work_order"] = values["Work Order"]
                break
        self._notam_save()
        self._notam_refresh()

    def _notam_delete(self):
        selected = self.notam_tree.selection()
        if not selected:
            messagebox.showwarning("Delete NOTAM", "Please select a NOTAM to delete.")
            return
        item_id = selected[0]
        values = self.notam_tree.item(item_id, "values")
        record_id = values[0]
        if not messagebox.askyesno("Confirm Delete", "Delete NOTAM {0}?".format(record_id)):
            return
        self.notam_records = [rec for rec in self.notam_records if rec.get("id") != record_id]
        self._notam_save()
        self._notam_refresh()
        self._notam_clear()

    def _notam_clear(self):
        self.ntm["Station"].set("")
        self.ntm["NAVAID"].set("")
        self.ntm["Type"].set("")
        self.ntm["Priority"].set("")
        self.ntm["Due Date"].set(datetime.date.today().isoformat())
        self.ntm["Status"].set("Open")
        self.ntm["Technician"].set("")
        self.ntm["Description"].set("")
        self.ntm["Est. Hours"].set("1.0")
        self.ntm["Work Order"].set("")
        for item in self.notam_tree.selection():
            self.notam_tree.selection_remove(item)

    def _notam_vals(self):
        return {key: var.get().strip() for key, var in self.ntm.items()}

    def _notam_on_select(self, event=None):
        del event
        selected = self.notam_tree.selection()
        if not selected:
            return
        item = self.notam_tree.item(selected[0], "values")
        if not item:
            return
        record_id = item[0]
        for rec in self.notam_records:
            if rec.get("id") == record_id:
                self.ntm["Station"].set(rec.get("station", ""))
                self.ntm["NAVAID"].set(rec.get("navaid", ""))
                self.ntm["Type"].set(rec.get("type", ""))
                self.ntm["Priority"].set(rec.get("priority", ""))
                self.ntm["Due Date"].set(rec.get("due_date", ""))
                self.ntm["Status"].set(rec.get("status", "Open"))
                self.ntm["Technician"].set(rec.get("technician", ""))
                self.ntm["Description"].set(rec.get("description", ""))
                self.ntm["Est. Hours"].set("{0:.1f}".format(MaintenanceSchedulePDF._safe_float(rec.get("est_hours", 1.0), 1.0)))
                self.ntm["Work Order"].set(rec.get("work_order", ""))
                break

    def _notam_refresh(self):
        for item in self.notam_tree.get_children():
            self.notam_tree.delete(item)
        for rec in self.notam_records:
            self.notam_tree.insert("", "end", values=(
                rec.get("id", ""),
                rec.get("station", ""),
                rec.get("navaid", ""),
                rec.get("type", ""),
                rec.get("priority", ""),
                rec.get("due_date", ""),
                rec.get("status", ""),
                rec.get("technician", ""),
                "{0:.1f}".format(MaintenanceSchedulePDF._safe_float(rec.get("est_hours", 0.0), 0.0)),
                rec.get("work_order", ""),
            ))

    def _notam_save(self):
        try:
            with open(NOTAM_FILE, "w", encoding="utf-8") as handle:
                json.dump(self.notam_records, handle, indent=2)
        except Exception as exc:
            messagebox.showerror("Save Error", "Could not save NOTAM data:\n{0}".format(exc))

    def _notam_type_changed(self, *args):
        del args
        notam_type = self.ntm["Type"].get().strip()
        if not notam_type:
            return
        hours = MAINT_WORK_HOURS.get(notam_type)
        if hours is not None:
            self.ntm["Est. Hours"].set("{0:.1f}".format(hours))

    def _notam_print_schedule(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Generate Maintenance Schedule PDF")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        today = datetime.date.today()
        cfg = self._load_json(MAINT_SCHEDULE_FILE, {})
        vars_map = {
            "org_name": tk.StringVar(value=cfg.get("org_name") or self.config_data.get("org_name", "NAVAIDS Operations")),
            "prepared_by": tk.StringVar(value=cfg.get("prepared_by") or self.config_data.get("prepared_by", "")),
            "date_from": tk.StringVar(value=cfg.get("date_from", today.isoformat())),
            "date_to": tk.StringVar(value=cfg.get("date_to", (today + datetime.timedelta(days=90)).isoformat())),
            "include_closed": tk.BooleanVar(value=cfg.get("include_closed", False)),
            "include_calendar": tk.BooleanVar(value=cfg.get("include_calendar", True)),
            "include_detail": tk.BooleanVar(value=cfg.get("include_detail", True)),
        }

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Organisation Name").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(frame, textvariable=vars_map["org_name"], width=40).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(frame, text="Prepared By").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(frame, textvariable=vars_map["prepared_by"], width=40).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(frame, text="Date From").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(frame, textvariable=vars_map["date_from"], width=20).grid(row=2, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(frame, text="Date To").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(frame, textvariable=vars_map["date_to"], width=20).grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ttk.Checkbutton(frame, text="Include CLOSED items", variable=vars_map["include_closed"]).grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(frame, text="Include calendar pages", variable=vars_map["include_calendar"]).grid(row=5, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(frame, text="Include detail table", variable=vars_map["include_detail"]).grid(row=6, column=0, columnspan=2, sticky="w", padx=4, pady=2)

        status_var = tk.StringVar(value="Ready.")
        progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(frame, variable=progress_var, maximum=100, length=360).grid(row=7, column=0, columnspan=2, sticky="ew", padx=4, pady=(10, 4))
        ttk.Label(frame, textvariable=status_var).grid(row=8, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 8))

        frame.columnconfigure(1, weight=1)

        def update_progress(pct, msg):
            self.root.after(0, lambda: (progress_var.set(pct), status_var.set(msg)))

        def open_file(path):
            try:
                if hasattr(os, "startfile"):
                    os.startfile(path)
                else:
                    subprocess.Popen(["xdg-open", path])
            except Exception:
                pass

        def run_generate(output_path):
            try:
                summary = MaintenanceSchedulePDF.generate(
                    output_path,
                    self.notam_records,
                    org_name=vars_map["org_name"].get().strip() or "NAVAIDS Operations",
                    prepared_by=vars_map["prepared_by"].get().strip(),
                    date_from=vars_map["date_from"].get().strip(),
                    date_to=vars_map["date_to"].get().strip(),
                    include_closed=vars_map["include_closed"].get(),
                    include_calendar=vars_map["include_calendar"].get(),
                    include_detail=vars_map["include_detail"].get(),
                    progress_cb=update_progress,
                )

                def done():
                    status_var.set("Done.")
                    progress_var.set(100)
                    summary_text = (
                        "PDF saved to:\n{0}\n\n"
                        "Open items: {1}\n"
                        "Estimated hours: {2:.1f}\n"
                        "Months covered: {3}"
                    ).format(
                        summary["path"],
                        summary["total_open"],
                        summary["total_hours"],
                        summary["months"],
                    )
                    if messagebox.askyesno("Schedule Generated", summary_text + "\n\nOpen the PDF now?", parent=dialog):
                        open_file(summary["path"])
                    dialog.destroy()

                self.root.after(0, done)
            except Exception as exc:
                self.root.after(0, lambda: (
                    status_var.set("Failed."),
                    messagebox.showerror("PDF Error", str(exc), parent=dialog)
                ))

        def on_generate():
            if not RL_OK:
                messagebox.showerror("Missing Dependency", "reportlab is not installed.", parent=dialog)
                return
            if not MaintenanceSchedulePDF._parse_date(vars_map["date_from"].get().strip()):
                messagebox.showerror("Validation", "Date From must be YYYY-MM-DD.", parent=dialog)
                return
            if not MaintenanceSchedulePDF._parse_date(vars_map["date_to"].get().strip()):
                messagebox.showerror("Validation", "Date To must be YYYY-MM-DD.", parent=dialog)
                return
            output_path = filedialog.asksaveasfilename(
                parent=dialog,
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Save Maintenance Schedule PDF"
            )
            if not output_path:
                return

            self.config_data["org_name"] = vars_map["org_name"].get().strip()
            self.config_data["prepared_by"] = vars_map["prepared_by"].get().strip()
            self._save_config()
            try:
                with open(MAINT_SCHEDULE_FILE, "w", encoding="utf-8") as handle:
                    json.dump({
                        "org_name": vars_map["org_name"].get().strip(),
                        "prepared_by": vars_map["prepared_by"].get().strip(),
                        "date_from": vars_map["date_from"].get().strip(),
                        "date_to": vars_map["date_to"].get().strip(),
                        "include_closed": vars_map["include_closed"].get(),
                        "include_calendar": vars_map["include_calendar"].get(),
                        "include_detail": vars_map["include_detail"].get(),
                    }, handle, indent=2)
            except Exception:
                pass

            status_var.set("Starting…")
            progress_var.set(0)
            worker = threading.Thread(target=run_generate, args=(output_path,), daemon=True)
            worker.start()

        btns = ttk.Frame(frame)
        btns.grid(row=9, column=0, columnspan=2, sticky="e", pady=(6, 0))
        ttk.Button(btns, text="📅 Generate & Save PDF", command=on_generate).pack(side="left", padx=4)
        ttk.Button(btns, text="✖ Cancel", command=dialog.destroy).pack(side="left", padx=4)


def main():
    root = tk.Tk()
    app = NAVAIDSApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
