# NFL red-zone usage

This repository builds a lightweight `redzone_usage.csv` from official nflverse
play-by-play and weekly roster releases.

Every Tuesday at 12:00 UTC, and whenever it is run manually, the workflow:

1. downloads the current NFL season's compressed PBP and weekly roster CSVs;
2. finds the latest completed regular-season week in the PBP data;
3. keeps that week and the previous four weeks;
4. keeps RB, WR, and TE rush attempts and targets at `yardline_100 <= 20`;
5. adds inside-the-10 and inside-the-5 splits; and
6. aggregates by season, week, player, team, and position.

The implementation uses only Python's standard library.

## Google Sheets import



If you want Sheets to refresh automatically after GitHub updates the CSV, add an
Apps Script time-driven trigger for `updateRedzoneUsage` on Tuesdays after
12:00 UTC.

## Manual GitHub run

Open **Actions → Update red-zone usage → Run workflow**. If the generated CSV
has changed, the workflow commits the new version to the default branch.

Data source: [nflverse-data](https://github.com/nflverse/nflverse-data/releases).
