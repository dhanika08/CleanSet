"""web.py - the single web page. Plain HTML, CSS and a little JavaScript, no frameworks."""

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CleanSet - check export paperwork before the bank does</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#14213d;--muted:#5b6475;--line:#dfe3ea;--red:#b42318;--redbg:#fef3f2;--green:#067647;--greenbg:#ecfdf3;--blue:#1d4ed8;--amber:#b54708;--amberbg:#fffaeb}
@media (prefers-color-scheme:dark){:root{--bg:#10131a;--card:#181c25;--ink:#eef1f6;--muted:#9aa4b5;--line:#2a3140;--red:#fda29b;--redbg:#3a1714;--green:#75e0a7;--greenbg:#0f2a1d;--blue:#8fb3ff;--amber:#fec84b;--amberbg:#2e2208}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.5}
main{max-width:860px;margin:0 auto;padding:28px 18px 60px}
h1{font-size:30px;margin:0 0 4px}.tag{color:var(--muted);margin:0 0 22px;font-size:17px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin:14px 0}
button{font:inherit;border:0;border-radius:8px;padding:10px 16px;cursor:pointer;font-weight:600}
.primary{background:var(--blue);color:#fff}.ghost{background:transparent;color:var(--blue);border:1px solid var(--blue)}
button:disabled{opacity:.5;cursor:wait}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input[type=file]{max-width:100%}
.banner{border-radius:12px;padding:18px 20px;font-size:24px;font-weight:700;margin:16px 0}
.bad{background:var(--redbg);color:var(--red);border:1px solid var(--red)}.good{background:var(--greenbg);color:var(--green);border:1px solid var(--green)}
.finding{border-left:5px solid var(--red)}.accepted{border-left:5px solid var(--green)}
.pill{display:inline-block;font-size:12px;font-weight:700;padding:2px 8px;border-radius:99px;border:1px solid var(--line);color:var(--muted);margin-left:6px}
.pill.rule{color:var(--blue);border-color:var(--blue)}.pill.judge{color:var(--amber);border-color:var(--amber)}
.muted{color:var(--muted);font-size:14px}.fix{background:var(--amberbg);border-radius:8px;padding:8px 12px;margin-top:8px}
.ev{font-size:13px;color:var(--muted);margin-top:6px}code{background:var(--bg);padding:1px 5px;border-radius:4px}
details summary{cursor:pointer;color:var(--blue)}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left}
.spin{display:none}.spin.on{display:block}
</style></head><body><main>
<h1>CleanSet</h1>
<p class="tag">A spell-checker for export paperwork, run the way the bank checks it.</p>

<div class="card">
  <p><b>How it works.</b> Upload a letter of credit and the shipping documents (PDFs or photos). CleanSet reads them with Gemini,
  checks them against the credit the way a bank checker would, and tells you what the bank would refuse, in plain words, with a fix for each problem.</p>
  <div class="row">
    <button class="primary" id="demoBtn">Try the demo deal</button>
    <span class="muted">or upload your own:</span>
    <input type="file" id="files" multiple accept=".pdf,.png,.jpg,.jpeg,.txt">
    <button class="ghost" id="goBtn">Check my documents</button>
  </div>
  <p class="muted">Use sample or fictional documents only. Files are analysed in memory and not stored.</p>
</div>

<div id="spin" class="card spin"><b>Reading and checking the documents...</b><br><span class="muted">Gemini reads each document, then the rules run. This takes about a minute.</span></div>
<div id="out"></div>
</main>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function busy(on){$('spin').classList.toggle('on',on);$('demoBtn').disabled=on;$('goBtn').disabled=on;if(on)$('out').innerHTML='';}
async function call(url,opts){
  busy(true);
  try{const r=await fetch(url,opts);const j=await r.json();if(!r.ok)throw new Error(j.detail||'Something went wrong');show(j);}
  catch(e){$('out').innerHTML='<div class="card finding"><b>Could not finish.</b><br>'+esc(e.message)+'</div>';}
  busy(false);
}
$('demoBtn').onclick=()=>call('/api/demo',{method:'POST'});
$('goBtn').onclick=()=>{
  const f=$('files').files; if(!f.length){alert('Choose the documents first.');return;}
  const fd=new FormData(); for(const x of f)fd.append('files',x);
  call('/api/analyze',{method:'POST',body:fd});
};
function show(j){
  const r=j.result; let h='';
  if(r.verdict==='discrepant') h+='<div class="banner bad">Bank would REFUSE: '+r.problem_count+' problem'+(r.problem_count>1?'s':'')+'</div>';
  else h+='<div class="banner good">Ready to submit: no problems found</div>';
  if(j.cached)h+='<p class="muted">Demo result shown from a recent run (kept for a few minutes to save quota).</p>';
  for(const f of r.findings){
    h+='<div class="card finding"><b>'+esc(f.title)+'</b><span class="pill '+(f.type==='Rule'?'rule':'judge')+'">'+esc(f.type)+'</span><span class="pill">'+esc(f.rule_id)+'</span>'
     +'<p>'+esc(f.explanation)+'</p>'
     +(f.article?'<div class="muted">Basis: '+esc(f.article)+'</div>':'')
     +'<div class="fix"><b>Fix:</b> '+esc(f.fix)+'</div>'
     +'<div class="ev">Evidence: '+f.evidence.map(e=>'<code>'+esc(e.field)+'</code> = '+esc(e.value)+(e.source?' (read from: "'+esc(e.source)+'")':'')).join('<br>')+'</div></div>';
  }
  if(r.accepted.length){
    h+='<h3>Looked wrong, but a bank would accept it</h3>';
    for(const a of r.accepted) h+='<div class="card accepted"><span class="pill">'+esc(a.rule_id)+'</span><span class="pill judge">Judgement</span><p>'+esc(a.reason)+'</p>'+(a.article?'<div class="muted">Basis: '+esc(a.article)+'</div>':'')+'</div>';
  }
  if(r.unchecked.length)h+='<p class="muted">Could not check: '+esc(r.unchecked.join(', '))+' (a needed fact was not found in the documents).</p>';
  h+='<div class="card"><details><summary>What Gemini read, and how much work it did</summary><table><tr><th>File</th><th>Read as</th><th>Facts</th></tr>'
   +j.read_log.map(l=>'<tr><td>'+esc(l.filename)+'</td><td>'+esc(l.document_type||('failed: '+(l.error||'')))+'</td><td>'+esc(l.facts_read)+'</td></tr>').join('')
   +'</table><p class="muted">Findings removed by the verifier because they pointed at facts that were not actually read: '+r.dropped.length+'</p>'
   +'<p class="muted">Time: '+j.seconds+' s</p></details></div>';
  $('out').innerHTML=h;
}
</script></body></html>
"""
