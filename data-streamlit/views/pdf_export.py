"""Generate a PDF scouting report for ranked teams."""
import io
import urllib.request
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether, Image,
)

from scout import pretty_name


def _build_styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(
        'PickNumber', parent=ss['Title'], fontSize=22, spaceAfter=2,
    ))
    ss.add(ParagraphStyle(
        'TeamHeader', parent=ss['Heading2'], fontSize=14, spaceAfter=4,
    ))
    ss.add(ParagraphStyle(
        'SectionLabel', parent=ss['Heading3'], fontSize=10,
        spaceBefore=6, spaceAfter=2,
    ))
    ss.add(ParagraphStyle(
        'SmallBody', parent=ss['BodyText'], fontSize=8, leading=10,
    ))
    ss.add(ParagraphStyle(
        'TinyBody', parent=ss['BodyText'], fontSize=7, leading=9,
    ))
    return ss


def _make_table(data, col_widths=None, header=True):
    """Create a styled reportlab Table from a list of rows."""
    style_cmds = [
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('LEADING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]
    if header and len(data) > 0:
        style_cmds += [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(style_cmds))
    return t


def _fetch_image(url, max_width=1.8 * inch, max_height=1.8 * inch):
    """Download an image URL and return a reportlab Image flowable, or None."""
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read()
        img_reader = ImageReader(io.BytesIO(data))
        iw, ih = img_reader.getSize()
        ratio = min(max_width / iw, max_height / ih, 1.0)
        return Image(io.BytesIO(data), width=iw * ratio, height=ih * ratio)
    except Exception:
        return None


def generate_pdf(ranked_teams, opr_data, scouted_data, pit_data_by_team, team_names):
    """Generate a PDF with one page per ranked team.

    Parameters
    ----------
    ranked_teams : list of dict
        From _get_ranked_teams(). Each has Pick, Team, Name, Notes.
    opr_data : DataFrame
        Full OPR data with teamNumber and fuel columns.
    scouted_data : DataFrame
        Full match scouting data for the event.
    pit_data_by_team : dict
        {team_number: DataFrame} of pit scouting data per team.
    team_names : dict
        {team_number: name}

    Returns
    -------
    bytes
        PDF file contents.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=0.4 * inch, bottomMargin=0.4 * inch,
    )
    styles = _build_styles()
    story = []
    page_width = letter[0] - 1.0 * inch  # usable width

    for idx, team in enumerate(ranked_teams):
        tn = team['Team']
        pick = team['Pick']
        name = team['Name']
        notes = team['Notes']

        # --- Header ---
        pick_label = f"Pick #{pick}" if isinstance(pick, int) else pick
        story.append(Paragraph(pick_label, styles['PickNumber']))
        story.append(Paragraph(f"Team {tn} &mdash; {name}", styles['TeamHeader']))
        story.append(Spacer(1, 4))

        # --- Fuel OPR Breakdown ---
        opr_row = opr_data.loc[opr_data['teamNumber'] == tn]
        if len(opr_row) > 0:
            r = opr_row.iloc[0]
            auto = r.get('hubScore_autoCount', 0)
            teleop = r.get('hubScore_teleopCount', 0)
            endgame = r.get('hubScore_endgameCount', 0)
            total = auto + teleop + endgame
            opr_table = _make_table(
                [['Auto OPR', 'Teleop OPR', 'Endgame OPR', 'Total OPR'],
                 [f'{auto:.1f}', f'{teleop:.1f}', f'{endgame:.1f}', f'{total:.1f}']],
                col_widths=[page_width / 4] * 4,
            )
            story.append(opr_table)
            story.append(Spacer(1, 6))

        # --- Our Summary Notes ---
        if notes:
            story.append(Paragraph("<b>Summary Notes</b>", styles['SectionLabel']))
            story.append(Paragraph(notes, styles['SmallBody']))
            story.append(Spacer(1, 4))

        # --- Match Notes ---
        tdf = scouted_data[scouted_data['team_number'] == tn].sort_values('match_number')
        note_cols = [c for c in ['match_notes', 'auto_notes'] if c in tdf.columns]
        note_rows = []
        for _, mrow in tdf.iterrows():
            mn = mrow.get('match_number', '?')
            scouter = str(mrow.get('scouter_name', ''))
            auto_n = str(mrow.get('auto_notes', '')).strip() if 'auto_notes' in note_cols else ''
            match_n = str(mrow.get('match_notes', '')).strip() if 'match_notes' in note_cols else ''
            if auto_n or match_n:
                # Wrap long notes in Paragraphs so they don't overflow
                note_rows.append([
                    str(mn), scouter,
                    Paragraph(auto_n, styles['TinyBody']),
                    Paragraph(match_n, styles['TinyBody']),
                ])

        if note_rows:
            story.append(Paragraph("<b>Match Notes</b>", styles['SectionLabel']))
            header = ['Match', 'Scouter', 'Auto Notes', 'Match Notes']
            notes_table = _make_table(
                [header] + note_rows,
                col_widths=[0.4 * inch, 0.8 * inch,
                            (page_width - 1.2 * inch) / 2,
                            (page_width - 1.2 * inch) / 2],
            )
            story.append(notes_table)
            story.append(Spacer(1, 6))

        # --- Pit Notes (notes-only records) ---
        pit_df = pit_data_by_team.get(tn)
        if pit_df is not None and len(pit_df) > 0:
            pit_note_rows = []
            for i in range(len(pit_df)):
                pr = pit_df.iloc[i]
                dt = pr.get('drive_train')
                if dt is not None and not (isinstance(dt, float) and pd.isna(dt)):
                    continue
                note_text = pr.get('notes', '')
                if isinstance(note_text, str) and note_text.strip():
                    pit_note_rows.append([
                        str(pr.get('scouter_name', '')),
                        Paragraph(note_text.strip(), styles['TinyBody']),
                    ])
            if pit_note_rows:
                story.append(Paragraph("<b>Pit Notes</b>", styles['SectionLabel']))
                pn_table = _make_table(
                    [['Scouter', 'Notes']] + pit_note_rows,
                    col_widths=[0.8 * inch, page_width - 0.8 * inch],
                )
                story.append(pn_table)
                story.append(Spacer(1, 6))

        # --- Pit Scouting (full records only) ---
        if pit_df is not None and len(pit_df) > 0:
            skip_fields = {
                'scouter_name', 'secret_team_key', 'event_key',
                'team_number', 'timestamp', 'image_names', 'photo_base64',
            }
            # Find the most recent full pit scout entry
            full_pit_row = None
            for i in range(len(pit_df) - 1, -1, -1):
                pr = pit_df.iloc[i]
                dt = pr.get('drive_train')
                if dt is not None and not (isinstance(dt, float) and pd.isna(dt)):
                    full_pit_row = pr
                    break

            if full_pit_row is not None:
                scouter = full_pit_row.get('scouter_name', 'Unknown')
                ts = full_pit_row.get('timestamp', '')
                story.append(Paragraph(
                    f"<b>Pit Scouting</b> &mdash; {scouter}, {ts}",
                    styles['SectionLabel'],
                ))

                pit_fields = []
                for field in pit_df.columns:
                    if field in skip_fields:
                        continue
                    val = full_pit_row.get(field)
                    if val is None or (isinstance(val, float) and pd.isna(val)):
                        continue
                    if isinstance(val, str) and not val.strip():
                        continue
                    is_bool = isinstance(val, bool) or (
                        val in (0, 1) and field not in ('fuel_capacity', 'hanging_level')
                    )
                    display_val = ('Yes' if val else 'No') if is_bool else str(val)
                    pit_fields.append([pretty_name(field), display_val])

                photo_flowable = None
                images = full_pit_row.get('image_names')
                if isinstance(images, list) and len(images) > 0:
                    photo_flowable = _fetch_image(images[0])

                if pit_fields:
                    mid = (len(pit_fields) + 1) // 2
                    left = pit_fields[:mid]
                    right = pit_fields[mid:]
                    while len(right) < len(left):
                        right.append(['', ''])
                    combined = [['Field', 'Value', 'Field', 'Value']]
                    for l_row, r_row in zip(left, right):
                        combined.append(l_row + r_row)
                    pit_table = _make_table(
                        combined,
                        col_widths=[page_width * 0.25, page_width * 0.25,
                                    page_width * 0.25, page_width * 0.25],
                    )
                    if photo_flowable:
                        story.append(photo_flowable)
                        story.append(Spacer(1, 4))
                    story.append(pit_table)

        # Page break between teams
        if idx < len(ranked_teams) - 1:
            story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()
