"""The desk's UI: one page, rendered from the same loaders the CLI uses.

Works in Safari on a Mac and on an iPhone today, with no build step and no
framework. It is the window, the gate and the alarm from
`HANDOFF-NATIVE.md` until the native apps exist over the same `serve` API.

Two rules that are enforced, not hoped for:

  * Every timestamp shows its age. The page must never look live when it
    is not; a dead daemon is visible from across the room.
  * The page contains exactly one request that is not a read: the confirm.
    `tests/test_boundary.py` counts the page's network calls and checks the
    one target. There are no forms, no other handlers, and no way to edit
    policy from a browser.
"""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

# The one mutating call the page may make. The boundary test reads this.
CONFIRM_ROUTE = "/confirm"

_CSS = """
:root{--bg:#0f1115;--panel:#161a22;--line:#262c38;--fg:#e6e8ee;--dim:#8a91a3;
--pass:#3fb950;--fail:#f85149;--pend:#d29922;--accent:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.45 -apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif}
header{padding:14px 16px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
header h1{font-size:17px;margin:0}header .age{color:var(--dim);font-size:13px}
main{padding:0 16px 40px;max-width:1100px;margin:0 auto}
section{margin:18px 0;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:6px 6px;border-top:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:500;border-top:0}td.num{text-align:right;font-variant-numeric:tabular-nums}
.pass{color:var(--pass)}.fail{color:var(--fail)}.pending{color:var(--pend)}.dim{color:var(--dim)}
.age-ok{color:var(--pass)}.age-warn{color:var(--pend)}.age-bad{color:var(--fail)}
.live{background:var(--fail);color:#fff;padding:2px 6px;border-radius:4px;font-weight:600}
.pill{display:inline-block;padding:1px 7px;border-radius:999px;border:1px solid var(--line);font-size:12px;color:var(--dim)}
details summary{cursor:pointer;color:var(--dim)}details ul{margin:6px 0 0 18px;padding:0}
button.confirm{appearance:none;border:1px solid var(--accent);background:transparent;color:var(--accent);
border-radius:8px;padding:8px 12px;font-size:14px;user-select:none;-webkit-user-select:none;touch-action:none}
button.confirm[disabled]{opacity:.35;border-color:var(--line);color:var(--dim)}
button.confirm.holding{background:var(--accent);color:#000}
.note{font-size:13px;color:var(--dim)}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
@media(max-width:480px){td,th{padding:6px 4px}main{padding:0 10px 40px}}
"""

_JS = """
(function(){
  var token=null;try{var q=new URLSearchParams(location.search);if(q.get('token')){localStorage.setItem('desk_token',q.get('token'));history.replaceState(null,'',location.pathname)}token=localStorage.getItem('desk_token')}catch(e){}
  var HOLD=1500;
  document.querySelectorAll('button.confirm').forEach(function(b){
    var t=null,armed=false;
    function reset(){clearTimeout(t);b.classList.remove('holding');b.textContent=b.dataset.label}
    b.addEventListener('pointerdown',function(){if(b.disabled)return;if(!token){b.textContent='not paired';return}
      b.classList.add('holding');b.textContent='hold…';
      t=setTimeout(function(){armed=true;b.textContent='confirming';
        fetch('%CONFIRM%',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
          body:JSON.stringify({ticket_id:b.dataset.ticket,stamp_sha256:b.dataset.digest,device:b.dataset.device})})
        .then(function(r){return r.json().then(function(j){return [r.status,j]})})
        .then(function(x){b.textContent=x[0]===201?'confirmed':'refused: '+(x[1].error||x[0]);b.disabled=true})
        .catch(function(){b.textContent='failed';reset()})},HOLD)});
    ['pointerup','pointerleave','pointercancel'].forEach(function(ev){b.addEventListener(ev,function(){if(!armed)reset()})});
  });
})();
""".replace("%CONFIRM%", CONFIRM_ROUTE)


def _age(then: datetime | None, now: datetime) -> str:
    if then is None:
        return '<span class="age-bad">none yet</span>'
    delta = now - then
    if delta < timedelta(hours=1):
        cls = "age-ok"
    elif delta < timedelta(hours=6):
        cls = "age-warn"
    else:
        cls = "age-bad"
    return f'<span class="{cls}" title="{html.escape(then.isoformat())}">{_human(delta)} ago</span>'


def _human(delta: timedelta) -> str:
    s = int(delta.total_seconds())
    if s < 0:
        return "0m"
    if s < 3600:
        return f"{max(1, s // 60)}m"
    if s < 86400:
        return f"{s // 3600}h {(s % 3600) // 60}m"
    return f"{s // 86400}d {(s % 86400) // 3600}h"


def _verdict_cls(v: str) -> str:
    return {"pass": "pass", "fail": "fail", "pending": "pending"}.get(v, "dim")


def render(data: Mapping[str, Any], *, now: datetime, device: str = "mac") -> str:
    """Render the whole page from the JSON the API also serves."""
    mode = data.get("mode") or {}
    book = data.get("stamp") or {}
    reports = data.get("reports") or {}
    assignments = data.get("assignments") or {}
    sources = data.get("sources") or {}
    ledger = data.get("ledger") or {}
    confirms = data.get("confirmations") or {}
    windows = data.get("event_windows") or []
    generated = _parse(data.get("generated_at"))
    stamped = _parse(book.get("stamped_at"))

    out: list[str] = []
    out.append("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    out.append("<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>")
    out.append("<meta name='color-scheme' content='dark'>")
    out.append("<title>Markets Desk</title>")
    out.append(f"<style>{_CSS}</style></head><body>")

    live = [v for v, spec in (mode.get("venues") or {}).items() if spec.get("live")]
    out.append("<header><h1>Markets Desk</h1>")
    out.append(f"<span class='pill'>{html.escape(str(mode.get('mode','?')))}</span>")
    out.append(f"<span class='pill'>{html.escape(str(mode.get('execution','?')))}</span>")
    if live:
        out.append(f"<span class='live'>LIVE: {html.escape(', '.join(live))}</span>")
    out.append(f"<span class='age'>page {_age(generated, now)} · stamp {_age(stamped, now)}</span>")
    out.append("</header><main>")

    # --- Book ---
    out.append("<section><h2>Book</h2>")
    out.append(
        f"<div class='note'>allocated {book.get('portfolio_allowed_pct', 0):.2f}% of a "
        f"{book.get('portfolio_cap_pct', 0):.2f}% heat cap</div>"
    )
    out.append("<table><tr><th>ticket</th><th>verdict</th><th>Jev</th><th class='num'>allowed</th><th>binding</th><th></th></tr>")
    for s in book.get("stamps", []):
        v = s.get("verdict", "")
        can = v == "pass" and float(s.get("allowed_pct", 0)) > 0
        held = confirms.get(s["ticket_id"])
        if held and held.get("usable"):
            action = f"<span class='pass'>confirmed · {html.escape(held.get('device',''))}</span>"
        else:
            label = "hold to confirm" if can else "—"
            action = (
                f"<button class='confirm' data-label='{label}' data-ticket='{html.escape(s['ticket_id'])}' "
                f"data-digest='{html.escape(s.get('stamp_sha256',''))}' data-device='{html.escape(device)}'"
                f"{'' if can else ' disabled'}>{label}</button>"
            )
        reasons = "".join(f"<li>{html.escape(r)}</li>" for r in s.get("reasons", []) + [f"stale: {x}" for x in s.get("stale_evidence", [])])
        detail = f"<details><summary>why</summary><ul>{reasons}</ul></details>" if reasons else ""
        out.append(
            f"<tr><td>{html.escape(s['ticket_id'])}{detail}</td>"
            f"<td class='{_verdict_cls(v)}'>{html.escape(v.upper())}</td>"
            f"<td class='dim'>{html.escape(s.get('challenge_verdict') or '—')}</td>"
            f"<td class='num'><b>{float(s.get('allowed_pct',0)):.2f}%</b></td>"
            f"<td class='dim'>{html.escape(s.get('binding_constraint',''))}</td>"
            f"<td>{action}</td></tr>"
        )
    out.append("</table></section>")

    # --- Seats ---
    out.append("<section><h2>Seats</h2><table><tr><th>seat</th><th>read</th><th>headline</th><th>filed</th></tr>")
    required = set(mode.get("required_seats") or [])
    seen = set()
    for seat, r in sorted(reports.items()):
        seen.add(seat)
        filed = _parse(r.get("produced_at"))
        out.append(
            f"<tr><td>{html.escape(seat)}</td><td class='dim'>{html.escape(r.get('read',''))}</td>"
            f"<td>{html.escape(r.get('headline',''))}</td><td>{_age(filed, now)}</td></tr>"
        )
    for seat in sorted(required - seen):
        out.append(f"<tr><td>{html.escape(seat)}</td><td class='fail'>required · dark</td><td></td><td>{_age(None, now)}</td></tr>")
    if not reports and not required:
        out.append("<tr><td colspan=4 class='dim'>none yet</td></tr>")
    out.append("</table></section>")

    # --- Assignments ---
    out.append("<section><h2>Assignments</h2>")
    if assignments:
        out.append("<table><tr><th>seat</th><th>issued</th><th class='num'>at stake</th><th>answered</th><th>unanswered</th></tr>")
        for seat, a in sorted(assignments.items()):
            cov = a.get("coverage") or {}
            out.append(
                f"<tr><td>{html.escape(seat)}</td><td>{_age(_parse(a.get('issued_at')), now)}</td>"
                f"<td class='num'>{float(a.get('at_stake_pct',0)):.2f}%</td>"
                f"<td>{len(cov.get('answered',[]))}/{cov.get('assigned',0)}</td>"
                f"<td class='dim'>{html.escape(', '.join(cov.get('unanswered',[])) or '—')}</td></tr>"
            )
        out.append("</table>")
    else:
        out.append("<div class='dim'>none yet</div>")
    out.append("</section>")

    # --- Sources ---
    out.append("<section><h2>Sources</h2>")
    probed = _parse(sources.get("generated_at"))
    out.append(f"<div class='note'>last probe {_age(probed, now)}</div>")
    rows = sources.get("sources") or []
    if rows:
        out.append("<table><tr><th>source</th><th>state</th><th class='num'>ms</th><th>detail</th></tr>")
        for r in rows:
            st = r.get("state", "")
            cls = "pass" if st == "ok" else ("pending" if st in ("degraded", "no_auth", "geo_blocked") else "fail")
            out.append(
                f"<tr><td>{html.escape(r.get('source_id',''))}</td><td class='{cls}'>{html.escape(st)}</td>"
                f"<td class='num dim'>{'' if r.get('latency_ms') is None else int(r['latency_ms'])}</td>"
                f"<td class='dim'>{html.escape(str(r.get('detail') or ''))[:80]}</td></tr>"
            )
        out.append("</table>")
    else:
        out.append("<div class='dim'>no preflight on file — run <span class='mono'>desk preflight</span></div>")
    out.append("</section>")

    # --- Ledger ---
    out.append("<section><h2>Ledger</h2>")
    tables = ledger.get("tables") or {}
    if tables:
        for dim, entries in tables.items():
            out.append(f"<div class='note'>by {html.escape(dim)}</div><table><tr><th>key</th><th class='num'>prop</th><th class='num'>res</th><th class='num'>hit</th><th class='num'>E[R]</th><th class='num'>ΣR</th></tr>")
            for e in entries:
                out.append(
                    f"<tr><td>{html.escape(str(e.get('key','')))}</td><td class='num'>{e.get('proposed','')}</td>"
                    f"<td class='num'>{e.get('resolved','')}</td><td class='num'>{e.get('hit_rate','') or '—'}</td>"
                    f"<td class='num'>{e.get('expectancy_r','') or '—'}</td><td class='num'>{e.get('total_r','')}</td></tr>"
                )
            out.append("</table>")
        for line in ledger.get("lines") or []:
            out.append(f"<div class='note'>{html.escape(line)}</div>")
    else:
        out.append("<div class='dim'>no outcomes yet — the ledger scores forward only</div>")
    out.append("</section>")

    # --- Event windows ---
    out.append("<section><h2>Event windows</h2>")
    if windows:
        out.append("<table><tr><th>window</th><th>from</th><th>to</th><th>binds</th></tr>")
        for w in windows:
            out.append(
                f"<tr><td>{html.escape(w.get('id',''))}</td><td class='dim'>{html.escape(str(w.get('starts_at','')))}</td>"
                f"<td class='dim'>{html.escape(str(w.get('ends_at','')))}</td><td class='dim'>{html.escape(', '.join(w.get('applies_to_kinds') or ['all']))}</td></tr>"
            )
        out.append("</table>")
    else:
        out.append("<div class='dim'>none</div>")
    out.append("</section>")

    # --- Mode / venues ---
    out.append("<section><h2>Mode</h2><table><tr><th>venue</th><th>enabled</th><th>live</th><th>note</th></tr>")
    for v, spec in sorted((mode.get("venues") or {}).items()):
        live_cell = "<span class='live'>TRUE</span>" if spec.get("live") else "<span class='pass'>false</span>"
        out.append(
            f"<tr><td>{html.escape(v)}</td><td class='dim'>{str(spec.get('enabled', False)).lower()}</td>"
            f"<td>{live_cell}</td><td class='dim'>{html.escape(str(spec.get('note') or ''))[:90]}</td></tr>"
        )
    out.append("</table>")
    out.append("<div class='note'>Every allowance is a ceiling, not an instruction. Max gates each order. This page cannot edit policy.</div>")
    out.append("</section>")

    out.append(f"</main><script>{_JS}</script></body></html>")
    return "".join(out)


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)
