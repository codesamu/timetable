from datetime import date, timedelta
from functools import wraps
import json
import os
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "timetable.json"
app.secret_key = os.getenv("TIMETABLE_SECRET_KEY", "change-this-in-production")
SHARED_PASSWORD = os.getenv("TIMETABLE_PASSWORD", "timetable123")
DEFAULT_WORKERS = ["Alice", "Bruno", "Carla", "David", "Emma"]
DEFAULT_COLORS = ["#3B82F6", "#EF4444", "#10B981", "#8B5CF6", "#F59E0B"]


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def load_state():
    if not DATA_FILE.exists():
        return {
            "workers": DEFAULT_WORKERS.copy(),
            "entries": {},
            "week_workers": {},
            "worker_colors": DEFAULT_COLORS.copy(),
            "week_worker_colors": {},
        }
    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "workers": DEFAULT_WORKERS.copy(),
            "entries": {},
            "week_workers": {},
            "worker_colors": DEFAULT_COLORS.copy(),
            "week_worker_colors": {},
        }

    # Backward compatibility with older file format: {"entries": {...}}
    if "workers" not in raw and "entries" in raw:
        return {
            "workers": DEFAULT_WORKERS.copy(),
            "entries": raw.get("entries", {}),
            "week_workers": {},
            "worker_colors": DEFAULT_COLORS.copy(),
            "week_worker_colors": {},
        }

    workers = raw.get("workers") or DEFAULT_WORKERS.copy()
    if not isinstance(workers, list) or not workers:
        workers = DEFAULT_WORKERS.copy()
    entries = raw.get("entries", {})
    if not isinstance(entries, dict):
        entries = {}
    week_workers = raw.get("week_workers", {})
    if not isinstance(week_workers, dict):
        week_workers = {}
    worker_colors = raw.get("worker_colors", [])
    if not isinstance(worker_colors, list):
        worker_colors = []

    for idx in range(len(workers)):
        if idx >= len(worker_colors) or not isinstance(worker_colors[idx], str):
            worker_colors.append(DEFAULT_COLORS[idx % len(DEFAULT_COLORS)])
    worker_colors = worker_colors[: len(workers)]

    week_worker_colors = raw.get("week_worker_colors", {})
    if not isinstance(week_worker_colors, dict):
        week_worker_colors = {}

    return {
        "workers": workers,
        "entries": entries,
        "week_workers": week_workers,
        "worker_colors": worker_colors,
        "week_worker_colors": week_worker_colors,
    }


def save_state(workers, entries, week_workers, worker_colors, week_worker_colors):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(
            {
                "workers": workers,
                "entries": entries,
                "week_workers": week_workers,
                "worker_colors": worker_colors,
                "week_worker_colors": week_worker_colors,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def week_monday_for(target_date):
    return target_date - timedelta(days=target_date.weekday())


def sorted_archive_weeks(
    entries, week_workers, week_worker_colors, current_week_monday
):
    grouped = {}
    for iso_date, values in entries.items():
        try:
            day_date = date.fromisoformat(iso_date)
        except ValueError:
            continue
        week_start = week_monday_for(day_date)
        if week_start >= current_week_monday:
            continue
        key = week_start.isoformat()
        if key not in grouped:
            grouped[key] = {"week_start": week_start, "rows": {}}
        grouped[key]["rows"][iso_date] = values

    archive_weeks = []
    for item in sorted(grouped.values(), key=lambda it: it["week_start"], reverse=True):
        week_start = item["week_start"]
        week_key = week_start.isoformat()
        worker_names = week_workers.get(week_key, [])
        if not worker_names:
            max_index = -1
            for day_values in item["rows"].values():
                for key in day_values:
                    try:
                        max_index = max(max_index, int(key))
                    except ValueError:
                        continue
            worker_names = [f"Worker {idx + 1}" for idx in range(max_index + 1)]
        worker_colors = week_worker_colors.get(week_key, [])
        if not worker_colors:
            worker_colors = [
                DEFAULT_COLORS[idx % len(DEFAULT_COLORS)] for idx in range(len(worker_names))
            ]
        if len(worker_colors) < len(worker_names):
            for idx in range(len(worker_colors), len(worker_names)):
                worker_colors.append(DEFAULT_COLORS[idx % len(DEFAULT_COLORS)])
        worker_colors = worker_colors[: len(worker_names)]

        row_items = []
        for day_index, day_name in enumerate(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        ):
            current_date = week_start + timedelta(days=day_index)
            iso_date = current_date.isoformat()
            row_items.append(
                {
                    "day_name": day_name,
                    "date_label": current_date.strftime("%d %b"),
                    "iso_date": iso_date,
                    "values": item["rows"].get(iso_date, {}),
                }
            )
        archive_weeks.append(
            {
                "label": (
                    f"{week_start.strftime('%d %b')} - "
                    f"{(week_start + timedelta(days=5)).strftime('%d %b')}"
                ),
                "worker_names": worker_names,
                "worker_colors": worker_colors,
                "rows": row_items,
            }
        )
    return archive_weeks


def has_archive_entries(entries, current_week_monday):
    for iso_date in entries:
        try:
            day_date = date.fromisoformat(iso_date)
        except ValueError:
            continue
        if week_monday_for(day_date) < current_week_monday:
            return True
    return False


def seed_dummy_archive_week(
    entries,
    week_workers,
    week_worker_colors,
    workers,
    worker_colors,
    current_week_monday,
):
    if has_archive_entries(entries, current_week_monday):
        return False

    dummy_week_start = current_week_monday - timedelta(days=7)
    week_key = dummy_week_start.isoformat()
    week_workers[week_key] = workers.copy()
    week_worker_colors[week_key] = worker_colors.copy()
    sample_shifts = ["08:00-16:00", "09:00-17:00", "10:00-18:00", "OFF", "12:00-20:00"]
    for day_index in range(6):
        current_date = dummy_week_start + timedelta(days=day_index)
        iso_date = current_date.isoformat()
        values = {}
        for worker_index in range(len(workers)):
            values[str(worker_index)] = sample_shifts[(day_index + worker_index) % len(sample_shifts)]
        entries[iso_date] = values
    return True


def sync_week_worker_snapshots(
    week_workers, week_worker_colors, workers, worker_colors, current_week_monday
):
    # Keep current and future weeks aligned with the active worker list.
    changed = False
    for week_offset in range(4):
        week_start = current_week_monday + timedelta(days=week_offset * 7)
        key = week_start.isoformat()
        if week_workers.get(key) != workers:
            week_workers[key] = workers.copy()
            changed = True
        if week_worker_colors.get(key) != worker_colors:
            week_worker_colors[key] = worker_colors.copy()
            changed = True
    return changed


@app.route("/")
@login_required
def home():
    state = load_state()
    workers = state["workers"]
    worker_colors = state["worker_colors"]
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    entries = state["entries"]
    week_workers = state["week_workers"]
    week_worker_colors = state["week_worker_colors"]

    today = date.today()
    week_monday = week_monday_for(today)
    changed = seed_dummy_archive_week(
        entries, week_workers, week_worker_colors, workers, worker_colors, week_monday
    )
    changed = (
        sync_week_worker_snapshots(
            week_workers, week_worker_colors, workers, worker_colors, week_monday
        )
        or changed
    )
    if changed:
        save_state(workers, entries, week_workers, worker_colors, week_worker_colors)

    weeks = []
    for week_index in range(4):
        week_start = week_monday + timedelta(days=week_index * 7)
        rows = []
        for day_index, day_name in enumerate(day_names):
            current_date = week_start + timedelta(days=day_index)
            iso_date = current_date.isoformat()
            rows.append(
                {
                    "day_name": day_name,
                    "date_label": current_date.strftime("%d %b"),
                    "iso_date": iso_date,
                    "values": entries.get(iso_date, {}),
                }
            )

        weeks.append(
            {
                "label": (
                    f"{week_start.strftime('%d %b')} - "
                    f"{(week_start + timedelta(days=5)).strftime('%d %b')}"
                ),
                "rows": rows,
            }
        )

    archive_weeks = sorted_archive_weeks(
        entries, week_workers, week_worker_colors, week_monday
    )
    workers_with_colors = list(zip(workers, worker_colors))

    return render_template(
        "index.html",
        workers=workers,
        workers_with_colors=workers_with_colors,
        weeks=weeks,
        archive_weeks=archive_weeks,
    )


@app.post("/api/cell")
@login_required
def save_cell():
    payload = request.get_json(silent=True) or {}
    iso_date = payload.get("date")
    worker_index = payload.get("worker_index")
    value = (payload.get("value") or "").strip()

    if not iso_date or not isinstance(worker_index, int):
        return jsonify({"ok": False, "error": "Invalid payload"}), 400
    try:
        date.fromisoformat(iso_date)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid date"}), 400

    state = load_state()
    workers = state["workers"]
    entries = state["entries"]
    week_workers = state["week_workers"]
    worker_colors = state["worker_colors"]
    week_worker_colors = state["week_worker_colors"]
    if worker_index < 0 or worker_index >= len(workers):
        return jsonify({"ok": False, "error": "Invalid worker index"}), 400

    day_values = entries.get(iso_date, {})
    worker_key = str(worker_index)
    if value:
        day_values[worker_key] = value
    else:
        day_values.pop(worker_key, None)

    if day_values:
        entries[iso_date] = day_values
    else:
        entries.pop(iso_date, None)

    save_state(workers, entries, week_workers, worker_colors, week_worker_colors)
    return jsonify({"ok": True})


@app.post("/workers/add")
@login_required
def add_worker():
    state = load_state()
    workers = state["workers"]
    entries = state["entries"]
    week_workers = state["week_workers"]
    worker_colors = state["worker_colors"]
    week_worker_colors = state["week_worker_colors"]

    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(url_for("home"))

    workers.append(name)
    worker_colors.append(DEFAULT_COLORS[(len(workers) - 1) % len(DEFAULT_COLORS)])
    sync_week_worker_snapshots(
        week_workers,
        week_worker_colors,
        workers,
        worker_colors,
        week_monday_for(date.today()),
    )
    save_state(workers, entries, week_workers, worker_colors, week_worker_colors)
    return redirect(url_for("home"))


@app.post("/workers/rename")
@login_required
def rename_worker():
    state = load_state()
    workers = state["workers"]
    entries = state["entries"]
    week_workers = state["week_workers"]
    worker_colors = state["worker_colors"]
    week_worker_colors = state["week_worker_colors"]

    try:
        worker_index = int(request.form.get("worker_index", "-1"))
    except ValueError:
        return redirect(url_for("home"))

    name = (request.form.get("name") or "").strip()
    if 0 <= worker_index < len(workers) and name:
        workers[worker_index] = name
        sync_week_worker_snapshots(
            week_workers,
            week_worker_colors,
            workers,
            worker_colors,
            week_monday_for(date.today()),
        )
        save_state(workers, entries, week_workers, worker_colors, week_worker_colors)
    return redirect(url_for("home"))


@app.post("/workers/color")
@login_required
def update_worker_color():
    state = load_state()
    workers = state["workers"]
    entries = state["entries"]
    week_workers = state["week_workers"]
    worker_colors = state["worker_colors"]
    week_worker_colors = state["week_worker_colors"]

    try:
        worker_index = int(request.form.get("worker_index", "-1"))
    except ValueError:
        return redirect(url_for("home"))

    color = (request.form.get("color") or "").strip()
    valid_hex = len(color) == 7 and color.startswith("#")
    if 0 <= worker_index < len(workers) and valid_hex:
        worker_colors[worker_index] = color
        sync_week_worker_snapshots(
            week_workers,
            week_worker_colors,
            workers,
            worker_colors,
            week_monday_for(date.today()),
        )
        save_state(workers, entries, week_workers, worker_colors, week_worker_colors)
    return redirect(url_for("home"))


@app.post("/workers/delete")
@login_required
def delete_worker():
    state = load_state()
    workers = state["workers"]
    entries = state["entries"]
    week_workers = state["week_workers"]
    worker_colors = state["worker_colors"]
    week_worker_colors = state["week_worker_colors"]

    try:
        worker_index = int(request.form.get("worker_index", "-1"))
    except ValueError:
        return redirect(url_for("home"))

    if not (0 <= worker_index < len(workers)) or len(workers) <= 1:
        return redirect(url_for("home"))

    current_week_monday = week_monday_for(date.today())
    workers.pop(worker_index)
    worker_colors.pop(worker_index)
    for iso_date, day_values in entries.items():
        try:
            day_date = date.fromisoformat(iso_date)
        except ValueError:
            continue
        if week_monday_for(day_date) < current_week_monday:
            # Keep archive rows untouched for historical consistency.
            continue

        remapped = {}
        for key, value in day_values.items():
            try:
                old_index = int(key)
            except ValueError:
                continue
            if old_index == worker_index:
                continue
            new_index = old_index - 1 if old_index > worker_index else old_index
            remapped[str(new_index)] = value
        entries[iso_date] = remapped

    sync_week_worker_snapshots(
        week_workers,
        week_worker_colors,
        workers,
        worker_colors,
        current_week_monday,
    )
    save_state(workers, entries, week_workers, worker_colors, week_worker_colors)
    return redirect(url_for("home"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("home"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == SHARED_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("home"))
        error = "Wrong password. Please try again."

    return render_template("login.html", error=error)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)
