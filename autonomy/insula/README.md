# Insula Launch Plans

`launch_plan.py` owns the boundary between structured execution intent and the
rendered sandbox command. Active callers build launch plans, record them in
receipts, and verify new receipts by comparing the expected plan with the
receipt's `launch_plan` record.

The legacy command parser remains only for command-line-only receipts that have
no plan record. Do not use it to check new receipts or to rebuild launches from
rendered `bwrap` arguments.
