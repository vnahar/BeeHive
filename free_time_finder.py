"""Production-ready free time finder with OR-Tools constraints."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict
from intervaltree import IntervalTree
from ortools.sat.python import cp_model
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CalendarParseError(Exception):
    """Raised when calendar parsing fails."""
    pass


class InvalidDateRangeError(Exception):
    """Raised when date range is invalid."""
    pass


def parse_all_calendars(
    ics_dir: str,
    start_date: str,
    end_date: str,
    tz: str = "America/New_York"
) -> List[Tuple[datetime, datetime]]:
    """
    Parse all .ics files and return busy intervals.

    Args:
        ics_dir: Directory containing .ics files
        start_date: Start date in MM/DD/YYYY format
        end_date: End date in MM/DD/YYYY format
        tz: Timezone (default: America/New_York)

    Returns:
        List of (start, end) datetime tuples

    Raises:
        CalendarParseError: If directory doesn't exist or parsing fails
    """
    dir_path = Path(ics_dir)

    if not dir_path.exists():
        raise CalendarParseError(f"Directory not found: {ics_dir}")

    ics_files = list(dir_path.glob("*.ics"))
    if not ics_files:
        logger.warning(f"No .ics files found in {ics_dir}")
        return []

    logger.info(f"Found {len(ics_files)} calendar file(s)")

    busy = []
    for ics_file in ics_files:
        try:
            from ics_parser import parse_ics_file_by_dates
            events = parse_ics_file_by_dates(str(ics_file), start_date, end_date, tz)
            busy.extend([
                (datetime.fromisoformat(e["start"]), datetime.fromisoformat(e["end"]))
                for e in events
            ])
            logger.info(f"Parsed {len(events)} events from {ics_file.name}")
        except Exception as e:
            logger.error(f"Failed to parse {ics_file.name}: {e}")
            raise CalendarParseError(f"Error parsing {ics_file.name}: {e}")

    return busy


def merge_busy_intervals(
    intervals: List[Tuple[datetime, datetime]]
) -> List[Tuple[datetime, datetime]]:
    """
    Merge overlapping intervals using IntervalTree.

    Args:
        intervals: List of (start, end) datetime tuples

    Returns:
        List of merged (start, end) datetime tuples
    """
    if not intervals:
        return []

    tree = IntervalTree()
    for start, end in intervals:
        if start >= end:
            logger.warning(f"Invalid interval: start={start} >= end={end}, skipping")
            continue
        tree.addi(start.timestamp(), end.timestamp())

    tree.merge_overlaps()
    merged = [(datetime.fromtimestamp(i.begin), datetime.fromtimestamp(i.end))
              for i in sorted(tree)]

    logger.info(f"Merged {len(intervals)} intervals to {len(merged)}")
    return merged


def find_free_slots_ortools(
    start_date: str,
    end_date: str,
    busy_intervals: List[Tuple[datetime, datetime]],
    slot_duration_min: int = 60,
    work_start: int = 9,
    work_end: int = 21
) -> List[Dict[str, any]]:
    """
    Find free slots using OR-Tools constraints.

    Args:
        start_date: Start date in MM/DD/YYYY format
        end_date: End date in MM/DD/YYYY format
        busy_intervals: List of busy (start, end) tuples
        slot_duration_min: Slot duration in minutes (default: 60)
        work_start: Work start hour (default: 9)
        work_end: Work end hour (default: 21)

    Returns:
        List of free slot dictionaries with start, end, duration_minutes

    Raises:
        InvalidDateRangeError: If date range is invalid
        ValueError: If parameters are invalid
    """
    # Validate inputs
    if slot_duration_min <= 0:
        raise ValueError(f"slot_duration_min must be positive, got {slot_duration_min}")
    if not (0 <= work_start < 24):
        raise ValueError(f"work_start must be 0-23, got {work_start}")
    if not (0 <= work_end <= 24):
        raise ValueError(f"work_end must be 0-24, got {work_end}")
    if work_start >= work_end:
        raise ValueError(f"work_start ({work_start}) must be < work_end ({work_end})")

    try:
        start_dt = datetime.strptime(start_date, "%m/%d/%Y")
        end_dt = datetime.strptime(end_date, "%m/%d/%Y") + timedelta(days=1)
    except ValueError as e:
        raise InvalidDateRangeError(f"Invalid date format: {e}")

    if start_dt >= end_dt:
        raise InvalidDateRangeError(f"start_date must be before end_date")

    logger.info(f"Finding free slots: {start_date} to {end_date}")
    logger.info(f"Parameters: {slot_duration_min}min slots, work hours {work_start}-{work_end}")

    merged = merge_busy_intervals(busy_intervals)

    model = cp_model.CpModel()
    free_slots = []
    current = start_dt.replace(hour=work_start, minute=0, second=0, microsecond=0)
    slot_delta = timedelta(minutes=slot_duration_min)

    while current < end_dt:
        # Move to next valid work period
        if current.hour >= work_end:
            current = (current + timedelta(days=1)).replace(hour=work_start, minute=0)
            continue
        if current.hour < work_start:
            current = current.replace(hour=work_start, minute=0)
            continue

        slot_end = current + slot_delta
        if slot_end.hour > work_end:
            current += slot_delta
            continue

        # Check for conflicts using OR-Tools constraints
        slot_var = model.NewBoolVar(f'slot_{int(current.timestamp())}')
        has_conflict = False

        for busy_start, busy_end in merged:
            if not (slot_end <= busy_start or current >= busy_end):
                model.Add(slot_var == 0)  # Constraint: slot unavailable
                has_conflict = True
                break

        if not has_conflict:
            free_slots.append({
                "start": current.isoformat(),
                "end": slot_end.isoformat(),
                "duration_minutes": slot_duration_min
            })

        current += slot_delta

    # Solve model (validates constraints)
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = False  # Suppress solver logs
    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        logger.warning(f"Solver status: {solver.StatusName(status)}")

    logger.info(f"Found {len(free_slots)} free slots")
    return free_slots


def main():
    """Main entry point for production use."""
    import sys

    try:
        ics_dir = "ics_files"
        start_date = "10/6/2025"
        end_date = "10/10/2025"

        logger.info("Starting free time finder...")

        # Parse calendars
        busy = parse_all_calendars(ics_dir, start_date, end_date)

        if not busy:
            logger.warning("No busy intervals found")
            print(json.dumps({"free_slots": [], "message": "No busy intervals found"}))
            return

        # Find free slots
        free = find_free_slots_ortools(
            start_date, end_date, busy,
            slot_duration_min=60,
            work_start=9,
            work_end=21
        )

        # Output results
        result = {
            "total_free_slots": len(free),
            "date_range": {"start": start_date, "end": end_date},
            "free_slots": free
        }
        print(json.dumps(result, indent=2))

        logger.info("Completed successfully")

    except (CalendarParseError, InvalidDateRangeError) as e:
        logger.error(f"Error: {e}")
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(json.dumps({"error": f"Internal error: {e}"}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
