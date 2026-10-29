# Repair after review

Load when the review returns findings.

1. Check each finding against the code before any change. A finding is a claim to test, not an order. Reject it, with evidence, when it is wrong for this code, breaks other behavior, asks for an unused path, or rests on missing context; list rejected findings in the final message.
2. Fix blocking findings first (broken behavior, security, data loss), then simple ones, then the rest. One finding at a time; for a defect, a failing test first.
3. Fix where the bad state starts. When the same fault exists elsewhere, fix every site the finding lists and grep for more; put every hit in the repair brief, because a builder edits only the sites its brief names.
4. Hand repairs to one builder per disjoint group of files, with the finding text, the failing scenario and the files.
5. Re-review only the files the repair touched and only the raised findings. Repeat repair and re-review until CLEAN, at most 3 rounds. A finding that survives 3 rounds goes to one repair by Opus, then one last re-review. Anything still open goes in the final message with its options and your recommendation.
6. A repair that failed once gets a different approach, not the same one again: more context in the brief, or a stronger model for a hard reasoning problem.
