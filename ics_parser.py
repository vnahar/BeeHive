from datetime import datetime, timedelta, date, time
from zoneinfo import ZoneInfo
from icalendar import Calendar
import recurring_ical_events as rie
import json

def parse_ics_file_by_dates(path, start_date, end_date, tz="America/New_York"):
    z = ZoneInfo(tz)
    ws = datetime.strptime(start_date, "%m/%d/%Y").replace(tzinfo=z)
    we = (datetime.strptime(end_date, "%m/%d/%Y") + timedelta(days=1)).replace(tzinfo=z)

    with open(path, "rb") as f:
        cal = Calendar.from_ical(f.read())

    def to_local(dt):
        if isinstance(dt, date) and not isinstance(dt, datetime):
            return datetime.combine(dt, time.min, z), True
        d = dt if isinstance(dt, datetime) else datetime.combine(dt, time.min)
        if d.tzinfo is None:
            d = d.replace(tzinfo=z)
        return d.astimezone(z), False

    events = []
    for e in rie.of(cal).between(ws, we):
        s, all_day = to_local(e.get("dtstart").dt)
        ep = e.get("dtend")
        e_time = to_local(ep.dt)[0] if ep else s + (timedelta(days=1) if all_day else timedelta(hours=1))
        events.append({
            "uid": str(e.get("uid") or ""),
            "summary": str(e.get("summary") or ""),
            "start": s.isoformat(),
            "end": e_time.isoformat(),
            "all_day": all_day,
            "location": str(e.get("location")) if e.get("location") else None
        })

    events.sort(key=lambda x: x["start"])
    return events

if __name__ == "__main__":
    path = "ics_files/vedant.nahar@gmail.com.ics"
    start_date, end_date = "10/6/2025", "10/10/2025"
    print(json.dumps(parse_ics_file_by_dates(path, start_date, end_date), indent=2))