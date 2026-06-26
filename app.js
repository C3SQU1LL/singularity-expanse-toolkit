const el = (id) => document.getElementById(id);
let currentSystem = null;

const dropZone = el('dropZone');
['dragenter','dragover'].forEach(evt => dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.add('drag'); }));
['dragleave','drop'].forEach(evt => dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.remove('drag'); }));
dropZone.addEventListener('drop', e => { const file = e.dataTransfer.files[0]; if(file) readFile(file); });
el('fileInput').addEventListener('change', e => { const file = e.target.files[0]; if(file) readFile(file); });
el('parsePaste').addEventListener('click', () => parseText(el('pasteInput').value, 'pasted text'));
el('clearAll').addEventListener('click', reset);
el('downloadReport').addEventListener('click', downloadReport);
el('downloadCsv').addEventListener('click', downloadCsvPack);

function readFile(file){
  const reader = new FileReader();
  reader.onload = () => parseText(reader.result, file.name);
  reader.onerror = () => setStatus('Could not read file', true);
  reader.readAsText(file);
}

function parseText(text, source){
  try{
    if(!text || !text.trim()) throw new Error('No text found.');
    const cleaned = text.trim().replace(/^```(?:json)?/,'').replace(/```$/,'').trim();
    const system = JSON.parse(cleaned);
    validateSystem(system);
    currentSystem = normalizeSystem(system, source);
    render(currentSystem);
    setStatus('Preview loaded');
  }catch(err){
    setStatus('Parse failed', true);
    el('logBox').textContent = `Could not parse this as a .solar/JSON system.\n\n${err.message}`;
    el('previewCard').classList.remove('hidden');
  }
}

function validateSystem(system){
  if(!system || typeof system !== 'object') throw new Error('File is not an object.');
  if(!system.isStar) throw new Error('Top-level object is not marked as a star.');
  if(!Array.isArray(system.planets)) throw new Error('No planets array found.');
}

function normalizeSystem(s, source){
  const planets = s.planets || [];
  const moons = planets.flatMap(p => (p.moons || []).map(m => ({...m, parentPlanetName:p.name})));
  return {
    source,
    name: s.name || 'Unnamed Star',
    luma: num(s.luma), trueLuma: num(s.trueLuma), temp: num(s.temp), age: num(s.age), wd: !!s.WD, primary: !!s.isPrimary,
    planets, moons,
    lifeWorlds: [...planets, ...moons].filter(x => Number(x.life || 0) > 0),
  };
}
function num(v){ return Number.isFinite(Number(v)) ? Number(v) : null; }
function fmt(v, d=2){ return v === null || v === undefined || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d); }
function lifeLabel(v){ return Number(v)===2?'Complex life':Number(v)===1?'Primitive life':'No life'; }
function geoLabel(v){ return ['Inactive','Mild','Active','Extreme'][Number(v)] || 'Unknown'; }
function classPlanet(p){
  if((p.gas||0) > .5) return 'Gas giant';
  if((p.ice||0) > .45) return 'Ice-rich world';
  if((p.rock||0) > .55 && Number(p.mass||0) > 2) return 'Rocky super-Earth';
  if((p.rock||0) > .55) return 'Rocky planet';
  return 'Mixed body';
}
function habitability(system){
  const complex = system.lifeWorlds.filter(x => Number(x.life) === 2).length;
  const primitive = system.lifeWorlds.filter(x => Number(x.life) === 1).length;
  if(complex) return `High: ${complex} complex-life world${complex>1?'s':''}`;
  if(primitive) return `Medium: ${primitive} primitive-life world${primitive>1?'s':''}`;
  return 'Low: no detected life';
}

function render(system){
  el('previewCard').classList.remove('hidden');
  el('systemTitle').textContent = system.name;
  el('starCount').textContent = '1';
  el('planetCount').textContent = system.planets.length;
  el('moonCount').textContent = system.moons.length;
  el('lifeCount').textContent = system.lifeWorlds.length;
  el('habitabilityBadge').textContent = habitability(system);
  el('downloadReport').disabled = false;
  el('downloadCsv').disabled = false;
  el('starPanel').innerHTML = [
    metric('Luminosity', `${fmt(system.luma,3)} L☉`),
    metric('Temperature', `${fmt(system.temp,0)} K`),
    metric('Age', `${fmt(system.age/1000,2)} billion yrs`),
    metric('Primary Star', system.primary ? 'Yes' : 'No')
  ].join('');
  el('planetList').innerHTML = system.planets.map((p, i) => planetCard(p, i)).join('');
  el('logBox').textContent = buildLog(system);
}
function metric(label, value){ return `<div class="metric"><b>${value}</b><span>${label}</span></div>`; }
function planetCard(p, i){
  const moons = p.moons || [];
  const tags = [classPlanet(p), `${fmt(p.mass,3)} Earth masses`, `${fmt(p.distanceFromParent,3)} AU`, lifeLabel(p.life), geoLabel(p.geoactive), p.rings?'Rings':'No rings', p.magneticField?'Magnetic field':'No magnetic field'];
  return `<article class="planet"><div class="planet-head"><div class="planet-title">${i+1}. ${escapeHtml(p.name||'Unnamed')}</div><div class="badge">${moons.length} moon${moons.length!==1?'s':''}</div></div><div class="tags">${tags.map(t=>`<span class="tag ${t.includes('life')&&!t.startsWith('No')?'good':''}">${escapeHtml(t)}</span>`).join('')}</div>${moons.length?`<div class="moons">Moons: ${moons.map(m=>escapeHtml(m.name||'Unnamed')).join(', ')}</div>`:''}</article>`;
}
function buildLog(s){
  return [`Loaded source: ${s.source}`,`Star created in preview: ${s.name}`,`Planets detected: ${s.planets.length}`,`Moons detected: ${s.moons.length}`,`Life-bearing objects: ${s.lifeWorlds.length}`,'','Notion import status: preview-only in this version.','Next milestone: secure GitHub Actions import using your private NOTION_TOKEN secret.'].join('\n');
}
function setStatus(msg, error=false){ const pill=el('statusPill'); pill.textContent=msg; pill.style.color=error?'#ff8f9b':'var(--accent)'; }
function reset(){ currentSystem=null; el('pasteInput').value=''; el('fileInput').value=''; el('previewCard').classList.add('hidden'); ['starCount','planetCount','moonCount','lifeCount'].forEach(id=>el(id).textContent='0'); el('downloadReport').disabled=true; el('downloadCsv').disabled=true; setStatus('Ready'); }
function escapeHtml(s){ return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }

function downloadReport(){
  if(!currentSystem) return;
  const report = { generatedAt: new Date().toISOString(), system: currentSystem.name, summary: {stars:1, planets:currentSystem.planets.length, moons:currentSystem.moons.length, lifeWorlds:currentSystem.lifeWorlds.length}, star:{name:currentSystem.name, luminosity:currentSystem.luma, temperatureK:currentSystem.temp, age:currentSystem.age}, planets: currentSystem.planets.map(p=>({name:p.name, class:classPlanet(p), mass:p.mass, distanceAU:p.distanceFromParent, moons:(p.moons||[]).length, life:lifeLabel(p.life)})) };
  download(`${currentSystem.name}-report.json`, JSON.stringify(report,null,2), 'application/json');
}
function downloadCsvPack(){
  if(!currentSystem) return;
  const stars = csv([['Name','Luminosity','Temperature K','Age','White Dwarf','Primary'],[currentSystem.name,currentSystem.luma,currentSystem.temp,currentSystem.age,currentSystem.wd,currentSystem.primary]]);
  const planets = csv([['Name','Parent Star','Mass','Distance AU','Rock','Ice','Gas','Metal','Atmosphere','Rings','Life','Moons'],...currentSystem.planets.map(p=>[p.name,currentSystem.name,p.mass,p.distanceFromParent,p.rock,p.ice,p.gas,p.metal,p.atmobasegas,p.rings,lifeLabel(p.life),(p.moons||[]).length])]);
  const moons = csv([['Name','Parent Planet','Mass','Distance From Parent','Rock','Ice','Gas','Metal','Atmosphere','Tidal Lock','Life'],...currentSystem.moons.map(m=>[m.name,m.parentPlanetName,m.mass,m.distanceFromParent,m.rock,m.ice,m.gas,m.metal,m.atmobasegas,m.tidalLock,lifeLabel(m.life)])]);
  download(`${currentSystem.name}-csv-pack.txt`, `--- stars.csv ---\n${stars}\n\n--- planets.csv ---\n${planets}\n\n--- moons.csv ---\n${moons}`, 'text/plain');
}
function csv(rows){ return rows.map(r=>r.map(v=>`"${String(v??'').replace(/"/g,'""')}"`).join(',')).join('\n'); }
function download(name, content, type){ const blob=new Blob([content],{type}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name; a.click(); URL.revokeObjectURL(a.href); }
