# Shape checks

Run the check that matches the choice. Each prevents one failure.

## Exhaust the design space
Failure: the first shape that works ships. For a new interaction or architecture with no precedent in the code, require two or three structurally different candidates (whole shapes, not point fixes). Compare them on the caller's experience, depth (small interface, much behavior behind it), and what each forecloses. For feel, compare prototypes side by side.

## Redesign from first principles
Failure: a requirement is bolted on and the design carries a patch. Read every affected file. Ask what you would build if the requirement had been a day-one assumption. Carry the change through types, docs, examples and rationale. Design the whole, deliver it in steps. When the same shape of workaround repeats across unrelated code, the design is wrong: scrap it, do not patch it.

## Model the domain
Failure: one more branch on an if/else chain, or a second boolean that must stay in step with the first. Encode the domain in a structure that makes invalid states unrepresentable: a state machine, a discriminated union, a lookup table, a reducer, one module per body of domain knowledge (never one module per execution step). Add nothing when the current shape is clear, local and stable. Reject an abstraction that adds indirection without removing branches, duplicate rules or invalid states.

## Experience first
Failure: implementation ease wins over the person who uses the result. The user is whoever consumes the work: the end user, the colleague who imports the API, the next maintainer. When ease and their experience conflict, choose their experience. Justify every control and option. Ship fewer features, finished. Serve the core loop or leave it out. Prototype in throwaway form before committing.
