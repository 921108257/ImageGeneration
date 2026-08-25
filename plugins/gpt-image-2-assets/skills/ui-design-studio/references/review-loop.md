# The review loop

The loop converges when each round changes the **design language**, not just the image
prompt. Nudging adjectives on the same prompt tends to oscillate: the model resamples rather
than moves in a direction.

## Presenting a mockup

State what you were going for so the user can react to intent rather than guess at it:

- The signature element and why it fits this subject.
- The hierarchy — what should be read first.
- The one risk you took, and the reasoning.
- Where you deliberately stayed quiet.

Then ask a direct question: is this direction right? Not "do you like it?" — that invites
taste feedback on details that will change anyway during the build.

## Turning feedback into a revision

Vague feedback costs a generation if you act on it literally. Ask one clarifying question
first, then map the objection to the layer that actually owns it:

| Feedback | Layer that owns it | Revision |
|---|---|---|
| "Too corporate / generic" | signature element | Replace it with something from the subject's own world; strengthen type contrast |
| "Too busy" | density + region count | `content_density=airy`, remove a region, widen spacing |
| "Wrong feel" | palette + material | Re-run `--design-system` with different keywords; restate the accent's role |
| "Layout is off" | composition | Rewrite the section-order description — it drives layout most |
| "Text looks broken" | expected | Raster limitation, not a design flaw. Explain it; the build uses real text |
| "Make it pop" | ambiguous | Ask: more color saturation, more contrast, or a bolder focal element? |

Note that "text looks broken" is not a defect to fix in the mockup. Say so plainly rather
than burning a generation trying to fix glyphs the model cannot render reliably.

## Versioning

Save every round to `design-system/<project-slug>/mockups/v<N>/` with the prompt and the
design-language delta that produced it. Two reasons: you can show `v1` beside `v3` when the
user wants to compare, and you avoid re-proposing a direction already rejected.

Suggested layout:

```
design-system/<project-slug>/
├── MASTER.md                # design language, source of truth for the build
├── pages/<page>.md          # page-specific overrides of MASTER
└── mockups/
    ├── v1/{mockup.png,prompt.txt,notes.md}
    └── v2/{mockup.png,prompt.txt,notes.md}
```

## When to stop

Stop and build once the user approves a direction. Do not keep polishing the mockup — it is
a review artifact, and remaining detail is decided far more precisely in code. If three
rounds have not converged, the brief itself is probably underspecified: go back and pin down
the subject, audience, and the screen's single job before generating again.
