# Ethics and Cultural Note

Please read this first.

This repository is a critique of **AI image-generation systems**, not a source of cultural material
about the Haida Nation. Every image this software produces is **synthetic, a machine's guess from a
deliberately underspecified prompt**, and exists only to document how AI models misrepresent,
stereotype, and erase a specific living Indigenous Nation. **These images are not authentic Haida
imagery, are not endorsed by or produced with the Haida Nation, and must not be used as a reference
for Haida people, culture, or art.**

## Why this project can be extractive if done carelessly

OCAP (Ownership, Control, Access, Possession) and the CARE Principles for Indigenous Data Governance
exist to prevent outsiders from producing and circulating representations of a Nation without its
authority. Synthetic images are arguably the sharpest case: there is no authentic signal in them at
all, only a model's priors rendered photorealistically. This project treats the model output as the
object of study, never as a representation of the Nation.

## The safeguards built into the code

- **Every surfaced image carries a burned-in banner** ("AI-GENERATED, not authentic Haida imagery")
  and is recorded with `provenance: synthetic` and `not_authentic: true`.
- **Generated images are never committed.** `runs/` is gitignored and a test fails the build if any
  image file is tracked under it. The public deliverable is the analysis: prompts, scores, and tables.
- **Findings language describes the model output** ("the model rendered X"), never what "the Haida
  are" or "wear".
- **Sacred and ceremonial content is excluded from generation**: no potlatch or ceremony scenes, no
  ceremonial regalia, no specific clan crests, no named individuals or artists, no spiritual-practice
  imagery. A guard agent checks the finalized prompt and records `cultural_flags`.
- **The temporal-erasure harm is measured, not reproduced.** One probe uses "traditional past"
  framing to test for the "frozen in time" stereotype; a paired present-day probe is included
  specifically to surface that harm.
- **The sourced research mode grounds in Haida-authored and custodial sources** (see
  `docs/sources.md`), with the Nation's own voice first.

## Honest limitations of benefit

Under the CARE principle of Collective Benefit, this study benefits its author and the AI-ethics
field, not the Haida Nation. We state that asymmetry plainly, we offer the findings back as a
plain-language summary that a community could use to demand better model behavior, and we invite
takedown and correction. This project has **not** been reviewed or endorsed by the Council of the
Haida Nation. It speaks only about AI systems, and any errors of framing are ours.

## Acknowledgement

We acknowledge the Haida Nation and their relationship to the lands and waters of Haida Gwaii.

Note to maintainers: verify this acknowledgement wording with a Haida source before publishing.
Do not trust a model-generated phrase for it.
