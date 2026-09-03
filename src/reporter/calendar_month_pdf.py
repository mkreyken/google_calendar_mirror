import calendar
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import datetime,timedelta
from pathlib import Path
from typing import Optional, List, Dict, Union

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import getAscent, getDescent, stringWidth
from reportlab.pdfgen import canvas

from src.api.calendar_events_for_period import EventsReader
from src.api.calendar_source_info import CalendarMappingApi
from src.clients.google_calendar_client import GoogleCalendarClient
from src.clients.mirror_key_store import TokenStoreValue
from src.clients.settings_on_disk import SETTINGS, MAXIMUM_MULTI_DAY_EVENT
from src.services.env import LOCAL_TZ
from src.util.date_util import google_to_datetime
from src.util.filesystem import get_log_directory


# -----------------------------
# Dataclasses
# -----------------------------
@dataclass(frozen=True)
class DayEvent:
    timeframe: str
    summary: str


@dataclass(frozen=True)
class MonthEvents:
    year: int
    month: int
    days: Dict[int, List[DayEvent]]


@dataclass
class CalendarPageInfo:
    page_title: str
    venue: Optional[str] = None
    subtitle: Optional[str] = None
    notes: List[str] = field(default_factory=list)


def month_bounds(year: int, month: int):
    # 1) Start of month — timezone-aware
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=LOCAL_TZ)

    # 2) Compute last day of month
    last_day = monthrange(year, month)[1]

    # 3) End of month — last microsecond before next month
    #    This avoids DST pitfalls at midnight boundaries.
    end = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=LOCAL_TZ)

    return start, end


def _line_height(font_name: str, font_size: int) -> float | int:
    ascent = getAscent(font_name) * font_size / 1000.0
    descent = abs(getDescent(font_name)) * font_size / 1000.0
    return ascent + descent


line_height_cache: Dict[str, int | float] = {}


def get_line_heights_cache(font_name: str, font_size: int, multiplier: float | int) -> float | int:
    font_name_size = font_name + ":" + str(font_size)
    if line_height_cache.get(font_name_size):
        return line_height_cache[font_name_size] * multiplier
    value = _line_height(font_name, font_size)
    line_height_cache[font_name_size] = value
    return value


# -----------------------------
# PDF Renderer
# -----------------------------
def render_month_pdf(events: MonthEvents, page_info: CalendarPageInfo, output_path: Union[Path | str]):
    c = canvas.Canvas(str(output_path), pagesize=landscape(letter))
    page_width, page_height = landscape(letter)
    margin = .25 * inch
    frame_margin = .3 * inch
    ## 0,0 is bottom left of page

    # -----------------------------
    # Header
    # -----------------------------
    c.setFont("Helvetica-Bold", 20)
    line_height = get_line_heights_cache("Helvetica-Bold", 20, 1.2)
    y = page_height - frame_margin - line_height
    c.drawString(0.75 * inch, y, page_info.page_title)
    top = y

    c.setFont("Helvetica", 14)
    line_height = get_line_heights_cache("Helvetica", 14, 1.1)

    if page_info.venue:
        width = stringWidth(page_info.venue, "Helvetica", 14)
        c.drawRightString(page_width - margin - width, y, page_info.venue)

    if page_info.subtitle:
        c.drawString(0.75 * inch, top - line_height, page_info.subtitle)
        top = top - line_height * 1.1  # below margin

    # -----------------------------
    # Footer section
    # -----------------------------
    bottom = frame_margin
    if page_info.notes:
        c.setFont("Times-Roman", 10)
        line_height = get_line_heights_cache("Times-Roman", 10, 1.1)
        bottom = 2 * margin + len(page_info.notes) * line_height
        y_notes = bottom - margin
        for note in page_info.notes:
            c.drawString(0.75 * inch, y_notes, f"- {note}")
            y_notes += line_height

    # -----------------------------
    # Calendar grid layout
    # -----------------------------
    cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
    month_matrix = cal.monthdayscalendar(events.year, events.month)

    col_width = (page_width - frame_margin * 2) / 7  # 7 days
    row_height = (top - bottom) / 6  # 6 weeks maximum

    y_start = top

    # -----------------------------
    # Draw grid + events
    # -----------------------------
    for row_index, week in enumerate(month_matrix):
        for col_index, day_number in enumerate(week):
            x = frame_margin + col_index * col_width
            y = y_start - row_index * row_height

            # Draw cell border
            c.rect(x, y - row_height, col_width, row_height)

            if day_number == 0:
                continue  # empty cell

            # Day number
            c.setFont("Helvetica-Bold", 12)
            # corner for number
            c.drawString(x + 4, y - 16, str(day_number))

            # Events
            c.setFont("Times-Roman", 8)
            event_y = y - 25

            day_events = events.days.get(day_number)
            line_height = get_line_heights_cache("Times-Roman", 8, 1.1)
            if day_events:
                for item in day_events:
                    c.drawString(x + 10, event_y, item.timeframe)
                    event_y -= line_height
                    c.drawString(x + 14, event_y, item.summary)
                    event_y -= line_height

    c.save()


def get_page_for(calendar_name: str, year: int, month: int) -> Path:
    maximum_multi_day_event: int = SETTINGS.get(MAXIMUM_MULTI_DAY_EVENT)
    gclient = GoogleCalendarClient()
    calendars: Dict[str, TokenStoreValue] = CalendarMappingApi.read_calendar_sources()
    calendar_id: Optional[str] = None

    # Find the calendar whose name matches the requested name
    for cal_id, cal_data in calendars.items():
        if cal_data.name == calendar_name:
            calendar_id = cal_id

    if not calendar_id:
        raise KeyError(f"No calendar found with name '{calendar_name}'")

    page_info = CalendarPageInfo(
        page_title="Events Calendar",
        venue=calendar_name,
        subtitle=calendar.month_name[month] + " " + str(year),
        notes=[
            "All events subject to change.",
            "Contact office for accessibility accommodations."
        ])

    name = f"{calendar_name}"
    output_pdf_name =  (get_log_directory() / name).with_suffix(".pdf")
    min_date, max_date = month_bounds(year, month)
    reader = EventsReader(gclient, calendar_id)
    fetch_start = min_date - timedelta(days=maximum_multi_day_event)
    fetch_end   = max_date + timedelta(days=maximum_multi_day_event)

    events = reader.get_events(fetch_start, fetch_end)

    days: Dict[int, List[DayEvent]] = {}

    for evt in events:
        start_dt = google_to_datetime(evt.start)
        end_dt = google_to_datetime(evt.end)

        # Clamp to the month window
        current_start = max(start_dt, min_date)
        current_end = min(end_dt, max_date)

        # Iterate day-by-day inside the month
        day_cursor = current_start.date()
        end_date = current_end.date()

        while day_cursor <= end_date:
            day_num = day_cursor.day

            # Determine timeframe for this day
            if day_cursor == start_dt.date() and day_cursor == end_dt.date():
                # Single-day event (within month)
                timeframe = f"{start_dt:%H:%M}-{end_dt:%H:%M}"

            elif day_cursor == start_dt.date():
                # First day of event (starts today)
                timeframe = f"{start_dt:%H:%M}--:--"

            elif day_cursor == end_dt.date():
                # Last day of event (ends today)
                timeframe = f"--:--{end_dt:%H:%M}"

            else:
                # Middle day OR start/end outside this month
                # If event started before this month → no start time
                # If event ends after this month → no end time
                timeframe = "--:----:--"

            # Add event
            days.setdefault(day_num, []).append(
                DayEvent(timeframe=timeframe, summary=evt.summary)
            )

            # Move to next day
            day_cursor += timedelta(days=1)


    month_events = MonthEvents(
        year=year,
        month=month,
        days=days
    )
    render_month_pdf(month_events, page_info, output_pdf_name)
    return output_pdf_name

if __name__ == "__main__":
    get_page_for("Gathering Area",2026,9)
