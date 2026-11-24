"""Round 2 without sorting folders by hand: one page where a person says whose picture is whose.

usage (through rv):
  inserts page [inbox]        inbox = a folder of loose pictures/clips the team dropped in (default inserts/_inbox).
                              Reads <inbox>/pairing.json (the AI writes it: groups of files, what is visible, a guess,
                              questions for the reviewer). Without one, a starter file is written (one group per file).
                              -> จับคู่-insert.html : clips that already carry inserts, the questions, the people of the
                              tape, every group with "who is this / what kind / how may it be used", and a prompt that
                              follows the choices. The reviewer saves the page and sends it back.
  inserts apply <saved.html>  copy every confirmed group into inserts/<person>/<kind>/ and print the answers.

The AI never decides who a person is from a face: it may only propose a match from what the picture itself says
(a name, an age, a caption, a product in the frame) and the reviewer confirms on the page."""
import os, re, sys, json, html, shutil
import common
import inserts as INS
from common import PROJ, BUILD, INSERTS

PAGE = "จับคู่-insert.html"
MEDIA = INS.MEDIA
KINDS = [c[0] for c in INS.CATS]


def inbox_dir(arg=None):
    d = arg or os.path.join(INSERTS, "_inbox")
    return d if os.path.isabs(d) else os.path.join(PROJ, d)


def load_pairing(inbox):
    f = os.path.join(inbox, "pairing.json")
    files = sorted(n for n in os.listdir(inbox) if n.lower().endswith(MEDIA))
    if not files: sys.exit(f"ไม่มีภาพหรือคลิปใน {os.path.relpath(inbox, PROJ)}")
    if not os.path.exists(f):
        data = dict(title="", verdict=[], questions=[], sets=[dict(id=f"{i + 1:02d}", files=[n], desc="", guess="", note="") for i, n in enumerate(files)])
        json.dump(data, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"สร้าง {os.path.relpath(f, PROJ)} แล้ว (1 ไฟล์ = 1 ชุด) ให้ AI เปิดดูภาพ รวมไฟล์ของคนเดียวกันเป็นชุดเดียว เขียน desc จากสิ่งที่เห็นในภาพ แล้วสั่ง rv inserts page อีกครั้ง")
    data = json.load(open(f, encoding="utf-8"))
    listed = {n for s in data["sets"] for n in s["files"]}
    missing = [n for n in listed if not os.path.exists(os.path.join(inbox, n))]
    if missing: sys.exit("pairing.json อ้างไฟล์ที่ไม่มี: " + ", ".join(missing))
    left = [n for n in files if n not in listed and n not in data.get("duplicates", [])]
    if left: print("เตือน: ไฟล์ที่ยังไม่อยู่ในชุดไหน:", ", ".join(left))
    return data


def insert_clips():
    """clips that already carry inserts: (name, title, note, [seconds])"""
    out = []
    for c in common.load_edl().CLIPS:
        f = os.path.join(BUILD, c["name"], "timeline.json")
        if not os.path.exists(f) or not os.path.exists(os.path.join(common.EXPORTS, c["name"] + ".mp4")): continue
        ins = json.load(open(f, encoding="utf-8")).get("inserts") or []
        if ins: out.append(dict(name=c["name"], title=c.get("title", ""), check=c.get("check", ""), at=[round(i["t0"], 1) for i in ins]))
    return out


def page(arg=None):
    inbox = inbox_dir(arg); data = load_pairing(inbox); P = INS.people()
    people = [dict(key=k, name=p["name"], role=p.get("role", ""), folder=INS.folder_of(k, p), pic=os.path.exists(os.path.join(common.EXPORTS, "people", k + ".jpg"))) for k, p in P.items()]
    cfg = dict(dir=os.path.relpath(inbox, PROJ).replace(os.sep, "/") + "/", people=people, sets=data["sets"], questions=data.get("questions", []),
               kinds=KINDS, clips=insert_clips(), shared=INS.SHARED, project=common.config().get("title") or os.path.basename(PROJ))
    verdict = "".join(f"<li>{v}</li>" for v in data.get("verdict", []))
    out = TEMPLATE.replace("/*CFG*/", json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/")).replace("<!--VERDICT-->", verdict) \
                  .replace("<!--TITLE-->", html.escape(data.get("title") or f"Insert รอบ 2 · จับคู่ภาพกับคน · {cfg['project']}"))
    open(os.path.join(PROJ, PAGE), "w", encoding="utf-8").write(out)
    print(f"เขียน {PAGE}: {len(data['sets'])} ชุด · {len(people)} คน · {len(cfg['clips'])} ตอนที่มี insert · {len(cfg['questions'])} คำถาม")


def read_state(path):
    s = open(path, encoding="utf-8").read()
    if path.endswith(".json"): return json.loads(s)
    m = re.search(r'<script id="rv2-saved" type="application/json">(.*?)</script>', s, re.S)
    if not m or not m.group(1).strip() or m.group(1).strip() == "{}": sys.exit("ไฟล์นี้ยังไม่มีคำตอบที่บันทึกไว้ (ต้องกด 'บันทึกหน้านี้ลงเครื่อง' ในหน้า HTML ก่อน)")
    return json.loads(m.group(1))


def apply(path, arg=None):
    st = read_state(path); inbox = inbox_dir(arg or st.get("_dir")); data = load_pairing(inbox); P = INS.people(); done = []
    for s in data["sets"]:
        who = st.get("set-" + s["id"]) or ""; use = st.get("use-" + s["id"]) or ""; kind = st.get("kind-" + s["id"]) or KINDS[3]
        if who not in P and who != INS.SHARED: print(f"ชุด {s['id']}: ข้าม ({ {'': 'ยังไม่เลือก', 'none': 'ไม่ใช่คนในเทปนี้', 'unsure': 'ไม่แน่ใจ'}.get(who, who)})"); continue
        if use == "no": print(f"ชุด {s['id']}: ผู้ตรวจเลือกไม่ใช้"); continue
        dest = os.path.join(INSERTS, INS.SHARED if who == INS.SHARED else INS.folder_of(who, P[who]), kind); os.makedirs(dest, exist_ok=True)
        for n in s["files"]: shutil.copy2(os.path.join(inbox, n), os.path.join(dest, f"{s['id']}_{n}"))
        done.append(dict(set=s["id"], person=who, kind=kind, use=use or "ยังไม่เลือก", files=[f"{s['id']}_{n}" for n in s["files"]], note=st.get("note-" + s["id"], "")))
        print(f"ชุด {s['id']}: {len(s['files'])} ไฟล์ → {os.path.relpath(dest, PROJ)}  [{ {'single': 'ใช้ได้เฉพาะภาพเดี่ยวปัจจุบัน', 'ba': 'ใช้ภาพก่อน–หลังได้'}.get(use, 'ยังไม่ได้เลือกวิธีใช้')}]" + (f" โน้ต: {st['note-' + s['id']]}" if st.get("note-" + s["id"]) else ""))
    for i, q in enumerate(data.get("questions", [])): print(f"คำถาม {i + 1}: {q}\n   ตอบ: {st.get('q' + str(i + 1)) or '(ยังไม่ตอบ)'}")
    if st.get("overall"): print("ความเห็นรวม:", st["overall"], "· ผู้ตรวจ:", st.get("reviewer", "-"))
    json.dump(dict(applied=done, answers={k: v for k, v in st.items() if re.match(r"q\d+$|overall|reviewer", k)}), open(os.path.join(INSERTS, "pairing-applied.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nจัดลงโฟลเดอร์แล้ว {len(done)} ชุด · บันทึกที่ inserts/pairing-applied.json · ขั้นต่อไป: วาง ins= ใน edl.py เฉพาะช็อตของคนนั้น แล้ว rv make → rv qa → rv risk → rv inserts page")


TEMPLATE = r"""<!doctype html>
<html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title><!--TITLE--></title>
<link href="https://fonts.googleapis.com/css2?family=Kanit:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#f5f3ee;--card:#fff;--ink:#1d2329;--mute:#68707a;--line:#e3dfd6;--red:#b3261e;--redbg:#fbe9e7;--amber:#8a5a00;--amberbg:#fdf1d8;--green:#1e6b3a;--greenbg:#e4f3e8;--accent:#1f2b5c;--on:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#15181c;--card:#1e2328;--ink:#eceae4;--mute:#9aa2ac;--line:#30363d;--redbg:#3a1a17;--red:#ff8a80;--amberbg:#3a2c0c;--amber:#ffcf70;--greenbg:#143021;--green:#8fd6a6;--accent:#a9b8ff;--on:#15181c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Kanit,system-ui,sans-serif;font-size:16px;line-height:1.55}
main{max-width:1080px;margin:0 auto;padding:24px 16px 90px}h1{font-size:26px;margin:0 0 4px;font-weight:600}h2{font-size:20px;margin:36px 0 10px;font-weight:600}h3{font-size:16px;margin:0 0 6px;font-weight:600}p{margin:6px 0}
.mute{color:var(--mute);font-size:14px}.box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}.verdict{border-left:6px solid var(--red)}ul{margin:6px 0;padding-left:20px}
.tag{display:inline-block;border-radius:999px;padding:1px 10px;font-size:13px;font-weight:500}.red{background:var(--redbg);color:var(--red)}.amber{background:var(--amberbg);color:var(--amber)}.green{background:var(--greenbg);color:var(--green)}
.clips{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}video{width:100%;border-radius:10px;background:#000;aspect-ratio:9/16}
.sets{display:grid;gap:12px}.set{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:14px;align-items:start}@media (max-width:720px){.set{grid-template-columns:1fr}}
.thumbs{display:flex;gap:8px;flex-wrap:wrap}.thumbs img,.thumbs video{height:170px;width:auto;aspect-ratio:auto;border-radius:8px;border:1px solid var(--line);display:block}
select,textarea,input[type=text]{width:100%;font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:8px}textarea{min-height:60px;resize:vertical}
label{font-size:14px;color:var(--mute);display:block;margin:8px 0 2px}
.people{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px}.people figure{margin:0;text-align:center;font-size:13px}.people img{width:100%;border-radius:10px;aspect-ratio:1;object-fit:cover}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;flex-wrap:wrap;justify-content:center}
button{font:inherit;font-weight:500;border:0;border-radius:10px;padding:10px 16px;background:var(--accent);color:var(--on);cursor:pointer}button.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
#prompt{min-height:320px;font-family:ui-monospace,Menlo,monospace;font-size:13px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
</style></head><body><main>
<h1><!--TITLE--></h1>
<p class="mute">เลือกว่าภาพแต่ละชุดเป็นของใคร ตอบคำถาม แล้วกด "บันทึกหน้านี้ลงเครื่อง" ส่งไฟล์กลับ หรือคัดลอก prompt ไปวางใน Claude Code · ไม่ต้องแบ่งโฟลเดอร์เอง</p>
<section class="box verdict" id="verdict"><h3>สิ่งที่ AI พบ</h3><ul><!--VERDICT--></ul></section>
<h2 id="h-clips">ตอนที่ใส่ insert แล้ว</h2><div class="clips" id="clips"></div>
<h2 id="h-q">คำถามที่ต้องให้คนตอบ</h2><div class="box" id="qbox"><table id="qs"></table></div>
<h2>คนในเทป</h2><div class="people" id="people"></div>
<h2>จับคู่ภาพกับคน</h2><p class="mute">กดที่ภาพเพื่อดูขนาดเต็ม · AI เสนอได้จากข้อความหรือของในภาพเท่านั้น ไม่เดาจากใบหน้า</p><div class="sets" id="sets"></div>
<h2>Prompt สำหรับทำต่อ</h2><p class="mute">เปลี่ยนตามที่เลือกด้านบน</p><textarea id="prompt" readonly></textarea>
<h2>ความเห็นรวม</h2><label>ชื่อผู้ตรวจ</label><input type="text" data-k="reviewer"><label>ความเห็น</label><textarea data-k="overall"></textarea>
</main><div class="bar"><button id="copy">คัดลอก prompt</button><button id="save" class="ghost">บันทึกหน้านี้ลงเครื่อง</button></div>
<script id="rv2-saved" type="application/json">{}</script>
<script>
const C = /*CFG*/;
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const KEY = 'rv2-' + C.project + '-' + C.dir;
let state = Object.assign({}, JSON.parse(document.getElementById('rv2-saved').textContent || '{}'));
try { Object.assign(state, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) {}
state._dir = C.dir;
const keep = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} };
const name = Object.fromEntries(C.people.map(p => [p.key, p.name + (p.role ? ' · ' + p.role : '')]));
const folder = Object.fromEntries(C.people.map(p => [p.key, p.folder])); folder[C.shared] = C.shared; name[C.shared] = 'ของกลาง ใช้ได้ทุกคน';
const isVid = f => /\.(mp4|mov|m4v|webm)$/i.test(f);
if (!document.querySelector('#verdict li')) document.getElementById('verdict').remove();
if (!C.clips.length) { document.getElementById('h-clips').remove(); document.getElementById('clips').remove(); }
else document.getElementById('clips').innerHTML = C.clips.map(c => `<div class="box"><h3>${esc(c.name)}</h3><video controls preload="metadata" src="exports/${esc(c.name)}.mp4"></video><p class="mute">${esc(c.title)} · insert ที่วินาที ${c.at.join(', ')}${c.check ? '<br>' + esc(c.check) : ''}</p><label>ความเห็นต่อตอนนี้</label><textarea data-k="clip-${esc(c.name)}"></textarea></div>`).join('');
if (!C.questions.length) { document.getElementById('h-q').remove(); document.getElementById('qbox').remove(); }
else document.getElementById('qs').innerHTML = '<tr><th>#</th><th>คำถาม</th><th>คำตอบ</th></tr>' + C.questions.map((q, i) => `<tr><td>${i + 1}</td><td>${esc(q)}</td><td><input type="text" data-k="q${i + 1}"></td></tr>`).join('');
document.getElementById('people').innerHTML = C.people.map(p => `<figure>${p.pic ? `<img src="exports/people/${p.key}.jpg" alt="">` : ''}<figcaption><b>${esc(p.key)}</b><br>${esc(p.name)}<br><span class="mute">${esc(p.role)}</span></figcaption></figure>`).join('');
document.getElementById('sets').innerHTML = C.sets.map(s => {
  const g = s.guess, badge = name[g] ? `<span class="tag green">AI เสนอ: ${esc(name[g])} (รอยืนยัน)</span>` : g === 'none' ? '<span class="tag amber">น่าจะไม่ใช่คนในเทป</span>' : '<span class="tag red">ยังไม่รู้ว่าใคร</span>';
  return `<div class="box set"><div><h3>ชุด ${esc(s.id)} ${badge}</h3><p class="mute">${esc(s.desc)}${s.note ? ' · ' + esc(s.note) : ''}</p><div class="thumbs">${s.files.map(f => `<a href="${C.dir}${encodeURI(f)}" target="_blank">${isVid(f) ? `<video muted preload="metadata" src="${C.dir}${encodeURI(f)}"></video>` : `<img loading="lazy" src="${C.dir}${encodeURI(f)}" alt="${esc(f)}">`}</a>`).join('')}</div></div>
  <div><label>ชุดนี้คือใคร</label><select data-k="set-${esc(s.id)}"><option value="">ยังไม่เลือก</option>${C.people.map(p => `<option value="${p.key}">${esc(p.key)} · ${esc(p.name)}</option>`).join('')}<option value="${C.shared}">ของกลาง (สินค้า การใช้ แอป) ใช้ได้ทุกคน</option><option value="none">ไม่ใช่คนในเทปนี้</option><option value="unsure">ไม่แน่ใจ</option></select>
  <label>เป็นภาพชนิดไหน</label><select data-k="kind-${esc(s.id)}">${C.kinds.map(k => `<option value="${k}">${esc(k)}</option>`).join('')}</select>
  <label>ใช้แบบไหนได้</label><select data-k="use-${esc(s.id)}"><option value="">ยังไม่เลือก</option><option value="single">ใช้ได้เฉพาะภาพเดี่ยวปัจจุบัน</option><option value="ba">ใช้ภาพก่อน–หลังได้</option><option value="no">ไม่ใช้</option></select>
  <label>โน้ต</label><textarea data-k="note-${esc(s.id)}"></textarea></div></div>`; }).join('');
C.sets.forEach(s => { if (!(('set-' + s.id) in state) && s.guess) state['set-' + s.id] = s.guess; if (!(('kind-' + s.id) in state)) state['kind-' + s.id] = s.kind || C.kinds[3]; if (!(('use-' + s.id) in state) && s.use) state['use-' + s.id] = s.use; });
function prompt() {
  const ok = C.sets.filter(s => folder[state['set-' + s.id]] && state['use-' + s.id] !== 'no');
  const open = C.sets.filter(s => !state['set-' + s.id] || state['set-' + s.id] === 'unsure').map(s => s.id);
  const use = u => u === 'ba' ? 'ใช้ภาพก่อน–หลังได้' : u === 'single' ? 'ใช้เฉพาะภาพเดี่ยวปัจจุบัน ห้ามวางภาพก่อนต่อภาพหลัง' : 'ผู้ตรวจยังไม่ได้เลือกวิธีใช้: ใช้เฉพาะภาพเดี่ยวไปก่อน';
  return `ใช้สกิล customer-review-cuts ทำ insert รอบ 2 ต่อในโปรเจกต์ ${C.project} (สูตร DK-04)

ผู้ตรวจจับคู่ภาพกับคนในหน้า จับคู่-insert.html แล้ว (ภาพอยู่ใน ${C.dir}):
${ok.map(s => `- ชุด ${s.id} = ${name[state['set-' + s.id]]} (รหัส ${state['set-' + s.id]}) · ${state['kind-' + s.id]} · ${use(state['use-' + s.id])}${state['note-' + s.id] ? ' · โน้ต: ' + state['note-' + s.id] : ''}`).join('\n') || '- (ยังไม่มีชุดที่ยืนยัน)'}

ชุดที่ยังไม่รู้ว่าใคร ห้ามใช้: ${open.join(', ') || '-'}

คำตอบของผู้ตรวจ:
${C.questions.map((q, i) => `${i + 1}) ${q}\n   ${state['q' + (i + 1)] || '(ยังไม่ตอบ)'}`).join('\n') || '-'}
ความเห็นต่อตอนที่ทำแล้ว: ${C.clips.filter(c => state['clip-' + c.name]).map(c => c.name + ': ' + state['clip-' + c.name]).join(' | ') || '-'}
ความเห็นรวม: ${state.overall || '-'}${state.reviewer ? ' (ผู้ตรวจ: ' + state.reviewer + ')' : ''}

สิ่งที่ต้องทำ:
1. ถ้ามีไฟล์หน้าที่บันทึกไว้ ให้รัน rv inserts apply <ไฟล์ที่บันทึก> เพื่อจัดภาพลงโฟลเดอร์ของแต่ละคน ถ้าไม่มี ให้คัดลอกไฟล์ของชุดที่ยืนยันแล้วไปที่ inserts/<โฟลเดอร์คน>/<ชนิด>/ ตามรายการด้านบน
2. ไม่ต้องตัดคลิปใหม่ ใช้ตอนเดิมใน edl.py เพิ่มตอนชื่อเดิมต่อท้ายด้วย i ใส่ ins= เฉพาะช็อตของคนที่ยืนยันแล้ว ตรงคำที่พูดถึงเรื่องนั้น ซับและหัวเรื่องอยู่ชั้นบน ทำทั้งตอนรายคนและฉบับรวม (มอนทาจ)
3. กติกา: ไม่ทับ 1.5 วินาทีแรก รวมไม่เกิน 1 ใน 3 ของคลิป ไม่ใช้ไฟล์ของคนหนึ่งในช็อตของอีกคน ภาพที่หัวเรื่องบังหน้าใช้ fit="below"
4. ภาพก่อน–หลังและภาพที่มีตัวเลขน้ำหนัก ไขมัน หรือจำนวนวัน เป็นระดับแดงตามกติกา RL-06: ใช้ได้เฉพาะชุดที่ผู้ตรวจเลือก "ใช้ภาพก่อน–หลังได้" และต้องเขียนใน check= ของตอนนั้นว่าเป็นระดับแดง AI ไม่อนุมัติการเผยแพร่แทนคน
5. เสร็จแล้ว rv make ตอนที่เปลี่ยน → rv qa → rv risk → rv inserts page แล้วรายงานตามจริงว่าตอนไหนทำแล้ว ตอนไหนยังไม่ได้ทำ`;
}
const render = () => { document.getElementById('prompt').value = prompt(); };
document.querySelectorAll('[data-k]').forEach(el => { if (state[el.dataset.k] != null) el.value = state[el.dataset.k]; el.addEventListener('input', () => { state[el.dataset.k] = el.value; keep(); render(); }); });
render();
document.getElementById('copy').onclick = async () => { const t = document.getElementById('prompt'); try { await navigator.clipboard.writeText(t.value); } catch (e) { t.select(); document.execCommand('copy'); } const b = document.getElementById('copy'); b.textContent = 'คัดลอกแล้ว'; setTimeout(() => b.textContent = 'คัดลอก prompt', 1500); };
document.getElementById('save').onclick = () => {
  const doc = document.documentElement.cloneNode(true); doc.querySelector('#rv2-saved').textContent = JSON.stringify(state).replace(/</g, '\\u003c');
  doc.querySelectorAll('[data-k]').forEach(el => { const v = state[el.dataset.k]; if (v == null) return; if (el.tagName === 'TEXTAREA') el.textContent = v; else if (el.tagName === 'INPUT') el.setAttribute('value', v); });
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['<!doctype html>\n' + doc.outerHTML], { type: 'text/html' })); a.download = 'จับคู่-insert-ตรวจแล้ว.html'; a.click();
};
</script></body></html>
"""

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["page"]: page(a[1] if len(a) > 1 else None)
    elif a[:1] == ["apply"] and len(a) > 1: apply(a[1], a[2] if len(a) > 2 else None)
    else: sys.exit("ใช้: rv inserts page [โฟลเดอร์ภาพ] | rv inserts apply <ไฟล์หน้าที่บันทึก>")
