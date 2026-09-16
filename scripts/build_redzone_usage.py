#!/usr/bin/env python3
"""Build five-week player red-zone usage from nflverse data."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import shutil
import tempfile
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
ROSTER_URL = "https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_{season}.csv"
ALLOWED_POSITIONS = {"RB", "WR", "TE"}
OUTPUT_FIELDS = [
    "season",
    "week",
    "player_id",
    "player_name",
    "team",
    "position",
    "rush_attempts",
    "targets",
    "opportunities",
    "inside_10_rush_attempts",
    "inside_10_targets",
    "inside_10_opportunities",
    "inside_5_rush_attempts",
    "inside_5_targets",
    "inside_5_opportunities",
]


def nfl_season(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return now.year if now.month >= 8 else now.year - 1


def download(url: str, destination: Path, attempts: int = 3) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "NFL-Usage GitHub Action"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                with destination.open("wb") as output:
                    shutil.copyfileobj(response, output)
            return
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(2**attempt)


def as_int(value: str | None) -> int | None:
    try:
        return int(float(value or ""))
    except ValueError:
        return None


def is_one(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "1.0", "true"}


def load_rosters(path: Path):
    exact = {}
    by_week = {}
    by_player = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            player_id = (row.get("gsis_id") or "").strip()
            team = (row.get("team") or "").strip()
            week = as_int(row.get("week"))
            position = (row.get("position") or row.get("depth_chart_position") or "").strip().upper()
            name = (row.get("full_name") or row.get("football_name") or "").strip()
            if not player_id or week is None:
                continue
            value = (position, name)
            exact[(week, team, player_id)] = value
            by_week[(week, player_id)] = value
            by_player[player_id] = value
    return exact, by_week, by_player


def roster_value(rosters, week: int, team: str, player_id: str):
    exact, by_week, by_player = rosters
    return (
        exact.get((week, team, player_id))
        or by_week.get((week, player_id))
        or by_player.get(player_id)
    )


def build(pbp_path: Path, roster_path: Path, season: int) -> tuple[list[dict], int, int]:
    rosters = load_rosters(roster_path)
    totals = defaultdict(lambda: [0] * 6)
    latest_week = 0
    unmatched_ids = set()

    with gzip.open(pbp_path, "rb") as compressed:
        with io.TextIOWrapper(compressed, encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if (row.get("season_type") or row.get("game_type") or "").upper() != "REG":
                    continue
                week = as_int(row.get("week"))
                if week is None:
                    continue
                latest_week = max(latest_week, week)
                try:
                    yardline = float(row.get("yardline_100") or "")
                except ValueError:
                    continue
                if yardline > 20:
                    continue

                events = []
                if is_one(row.get("rush_attempt")):
                    events.append(("rush", row.get("rusher_player_id"), row.get("rusher_player_name")))
                if is_one(row.get("pass_attempt")) and (row.get("receiver_player_id") or "").strip():
                    events.append(("target", row.get("receiver_player_id"), row.get("receiver_player_name")))

                team = (row.get("posteam") or "").strip()
                for event, raw_id, raw_name in events:
                    player_id = (raw_id or "").strip()
                    if not player_id:
                        continue
                    player_roster = roster_value(rosters, week, team, player_id)
                    if not player_roster:
                        unmatched_ids.add(player_id)
                        continue
                    position, full_name = player_roster
                    if position not in ALLOWED_POSITIONS:
                        continue
                    player_name = full_name or (raw_name or "").strip()
                    key = (season, week, player_id, player_name, team, position)
                    counts = totals[key]
                    offset = 0 if event == "rush" else 1
                    counts[offset] += 1
                    if yardline <= 10:
                        counts[2 + offset] += 1
                    if yardline <= 5:
                        counts[4 + offset] += 1

    if latest_week == 0:
        raise RuntimeError("No regular-season weeks were found in the nflverse PBP file")

    first_week = max(1, latest_week - 4)
    rows = []
    for key, counts in totals.items():
        row_season, week, player_id, player_name, team, position = key
        if week < first_week:
            continue
        rushes, targets, i10_rushes, i10_targets, i5_rushes, i5_targets = counts
        rows.append({
            "season": row_season,
            "week": week,
            "player_id": player_id,
            "player_name": player_name,
            "team": team,
            "position": position,
            "rush_attempts": rushes,
            "targets": targets,
            "opportunities": rushes + targets,
            "inside_10_rush_attempts": i10_rushes,
            "inside_10_targets": i10_targets,
            "inside_10_opportunities": i10_rushes + i10_targets,
            "inside_5_rush_attempts": i5_rushes,
            "inside_5_targets": i5_targets,
            "inside_5_opportunities": i5_rushes + i5_targets,
        })
    rows.sort(key=lambda row: (row["season"], row["week"], row["team"], row["position"], row["player_name"], row["player_id"]))
    if not rows:
        raise RuntimeError("No RB/WR/TE red-zone opportunities matched the weekly roster data")
    return rows, first_week, latest_week


def write_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=nfl_season())
    parser.add_argument("--output", type=Path, default=Path("redzone_usage.csv"))
    parser.add_argument("--pbp-url")
    parser.add_argument("--roster-url")
    args = parser.parse_args()

    pbp_url = args.pbp_url or PBP_URL.format(season=args.season)
    roster_url = args.roster_url or ROSTER_URL.format(season=args.season)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        pbp_path = temp / "pbp.csv.gz"
        roster_path = temp / "roster.csv"
        download(pbp_url, pbp_path)
        download(roster_url, roster_path)
        rows, first_week, latest_week = build(pbp_path, roster_path, args.season)
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows for {args.season} weeks {first_week}-{latest_week} to {args.output}")


if __name__ == "__main__":
    main()
