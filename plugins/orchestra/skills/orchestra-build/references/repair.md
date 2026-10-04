Sentinel: orchestra-build/references/repair.md
Stub: B4 skeleton; ticket S4 rewrites this file and removes this line.

# Builder: repair mode

Repair mode needs independently checked coding findings. Recheck each finding against source; show inputs/state → wrong outcome before fixing it. If a finding contradicts the spec, stop dependent changes and return it to the coordinator for design/planning. Repair only the owned defect, then rerun affected checks and return the exact artifact for fresh independent review.
