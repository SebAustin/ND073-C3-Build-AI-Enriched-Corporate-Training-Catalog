# Normalise Duration to hours using 40 hours per Udacity month

Each Source states Duration differently: MS Learn in minutes (`44`), Udacity as free text in months (`"4 months "`), and Company Moodle as small integers we treat as hours. We store one numeric `duration` in hours (`Edm.Double`) so "courses under N hours" means the same thing for every Source, and keep the original wording in `duration_text`. A Udacity month counts as 40 hours, based on Udacity's guidance of about 10 hours a week; this is an estimate, so Nanodegree durations should be read as order-of-magnitude.

## Consequences

- Changing the conversion means re-running `scripts/prepare_courses.py upload` and resetting the courses indexer.
- Moodle durations being hours is an assumption; if they turn out to be days, multiply them before upload.
