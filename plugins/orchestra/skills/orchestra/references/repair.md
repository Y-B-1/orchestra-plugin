# Repair after review

Load when the review returns findings.

1. Check each finding against the code before any change. A finding is a claim to test, not an order. Reject it, with evidence, when it is wrong for this code, breaks other behavior, asks for an unused path, or rests on missing context; list rejected findings in the final message.
2. Fix blocking findings first (broken behavior, security, data loss), then simple ones, then the rest. One finding at a time; for a defect, a failing test first.
3. Fix where the bad state starts. When the same fault exists elsewhere, fix every site the finding lists and grep for more.
4. Hand repairs to one builder per disjoint group of files, with the finding text, the failing scenario and the files.
5. One re-review of only the repair diff and only the raised findings. Whatever it says, review ends there. A finding that survives the repair goes in the final message with its options and your recommendation; never a third round.
6. A repair that failed once gets a different approach, not the same one again: more context in the brief, or a stronger model for a hard reasoning problem.
