from datetime import date


def parse_report_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def require_mutable_report_date(value: str) -> str:
    report_date = parse_report_date(value)
    if report_date < date.today():
        raise ValueError("Only today and future dates can be generated")
    return report_date.isoformat()
