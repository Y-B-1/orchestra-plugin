# Correct mode

Trigger: the owner corrects one instance of a mistake. The failure to prevent: fixing that one spot while the same mistake stays elsewhere, then being corrected again.

## Steps
1. Fix the named instance.
2. Name the mistake as a class in one sentence ("handlers read the env var directly instead of config").
3. Find every instance in the repo: grep for the pattern and its variants, and read recent commits, reverts and review comments for the same class (with no named instance, mine those). A class counts once it happened twice. Fix them all in the same change set, or list the ones you could not fix with the reason.
4. Add a check so the class cannot return. Use the highest level that works:
   - Architecture: one owner for the state, one supported way to do the task, wrong imports hidden, hand-synced lists replaced by one source, dead examples deleted.
   - Types: make the bad state unwritable.
   - A lint or CI check whose error names the file, type or function to use. If the pattern is already common, fail only when a change adds more.
   - A behavior test (fix or delete any test that still passes when the behavior breaks).
   - Docs or an agent rule last, only for judgment calls nothing can check.
   - An exception to the new check sits on the offending line with a reason, an expiry and the owner's approval.
5. Prove the check: run it against a real past instance and see it fail, then pass after the fix. Run the same command locally, and in CI when CI runs on push (in a repo where CI runs only by hand, run it locally).
6. If the repo keeps a rule table, add a row pairing the rule with its check. If the rule already existed and nothing enforced it, that is a repeat: enforce it at a higher level now.

## Report
The class, the instances found and fixed, the check added and its level, and why a higher level did not work.
