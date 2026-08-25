from src.reporter.calendar_month_pdf import MonthEvents, DayEvent, render_month_pdf, \
    CalendarPageInfo, get_page_for
from src.util.filesystem import get_log_directory


# --- sample usage ---
def t1() -> None:
    d_e = DayEvent("17:00-22:30", "Legion of Mary")
    events = MonthEvents(
        year=2026,
        month=8,
        days={
            5: [d_e,d_e,d_e,d_e],
            12: [d_e],
            23: [d_e]
        }
    )
    output_dir = get_log_directory()
    page_info = CalendarPageInfo(
        page_title="Community Events Calendar",
        venue="St. Andrew’s Church Hall",
        subtitle="September 2026",
        notes=[
            "All events subject to change.",
            "Contact office for accessibility accommodations."
        ]
    )

    render_month_pdf(events, page_info, output_path=output_dir / "september.pdf")

def main() -> None:
    get_page_for("Gathering Area",2026,9)

if __name__ == "__main__":
    main()
