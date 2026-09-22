# Prompts — running a seat from a web chat

A seat is anything that writes a file the contract accepts. That means a
frontier model's **web chat window** is a perfectly good seat: paste the
prompt, paste the input where it says, paste the output into the file the
prompt names. No API key, no harness, and the desk cannot tell the difference.

One file per task type, a `<PASTE … HERE>` slot, the acceptance checks
inline.

| Prompt | Paste into | Output goes to |
|---|---|---|
| `RESEARCH_SEAT_PROMPT.md` | any research seat's web chat (Wire, Ledger, Odds, Chain, Pulse, Shadow, CoS) | `reports/<date>-<time>-<seat>.report.yaml` |
| `JEV_PROMPT.md` | a **different model** from the one that wrote the ticket | `challenges/<date>-<TICKET-ID>.challenge.yaml` |
| `TICKET_PROMPT.md` | a research seat with hard evidence in hand | `tickets/<date>-<ID>-<slug>.ticket.yaml` |
| `CODEX_IMPLEMENTATION_PROMPT.md` | Codex (web or CLI) for work on the desk code | a `codex/desk-*` branch |
| `REVIEW_PROMPT.md` | any model, for a read-only review of the repo or a filing | chat, not the repo |
| `../codex-feed/BRIEF-GROK.md` | Grok, as its standing instruction | `reports/…-grok.report.yaml` |

Two rules the web path does not relax:

- **`model:` on the file must say which model you pasted into.** The
  adversary rule bites on that field. A challenge from the ticket's own model
  is self-review and `stamp` drops it.
- **Web is `hosting: api` for privacy purposes** — what you paste leaves the
  box. Do not paste the pack (CoS output) into a web chat; CoS runs local.

After pasting the output into its file, run `python -m desk validate`. The
contract will refuse anything the model got wrong, and the refusal is the
feedback to paste back.
