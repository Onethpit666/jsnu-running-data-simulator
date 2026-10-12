const $ = id => document.getElementById(id);
const timeList = $('times');
const status = $('status');
let busy = false;

function beijingNow() {
  return new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 19);
}
function addTime() {
  if (timeList.children.length >= 20) return message('最多添加 20 条记录。', true);
  const row = document.createElement('div'); row.className = 'time-row';
  const label = document.createElement('label'); label.textContent = '开始时间 / 北京时间';
  const input = document.createElement('input'); input.type = 'datetime-local'; input.step = '1';
  input.required = true; input.min = '2000-01-01T00:00'; input.max = '2100-12-31T23:59:59';
  input.value = beijingNow(); label.append(input); row.append(label);
  const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'remove';
  remove.textContent = '删除'; remove.onclick = () => {row.remove(); updateButtons(); invalidate();}; row.append(remove);
  timeList.append(row); updateButtons(); invalidate();
}
function updateButtons() {
  const count = timeList.children.length;
  $('generate').textContent = count > 1 ? `下载 ZIP · ${count} 条` : `下载 ${$('export-format').value.toUpperCase()}`;
  timeList.querySelectorAll('.remove').forEach(button => button.disabled = count === 1 || busy);
  $('add-time').disabled = count >= 20 || busy;
}
function message(text, error = false) {status.textContent = text; status.classList.toggle('error', error);}
function invalidate() {
  if (!$('empty').hidden) return;
  $('summary-note').textContent = '参数已修改，请重新预览；下载时会使用当前参数。';
}
function payload(firstOnly = false) {
  if (!$('settings').reportValidity()) throw new Error('请检查输入范围和时间。');
  const pace = $('pace').value.trim().match(/^(\d+):([0-5]\d)$/);
  if (!pace) throw new Error('配速请填写分:秒，例如 6:00。');
  const paceSeconds = Number(pace[1]) * 60 + Number(pace[2]);
  if (paceSeconds < 180 || paceSeconds > 1200) throw new Error('配速范围为 3:00 到 20:00 / 公里。');
  const options = {
    distance_m: Number($('distance').value), pace_seconds_per_km: paceSeconds,
    sample_interval: Number($('interval').value), center_lat: Number($('lat').value),
    center_lon: Number($('lon').value), straight_m: Number($('straight').value),
    radius_m: Number($('radius').value), rotation_deg: Number($('rotation').value),
    simulate_hr: $('simulate-hr').checked, hr_min: Number($('hr-min').value), hr_max: Number($('hr-max').value),
    pace_variation_percent: Number($('pace-variation').value),
    lane_variation_m: Number($('lane-variation').value), random_seed: Number($('random-seed').value)
  };
  Object.assign(options, {simulate_metrics:$('simulate-metrics').checked});
  for (const [key,id] of Object.entries({pause_seconds:'pause-seconds',weight_kg:'weight',cadence_spm:'cadence',power_w:'power',base_altitude_m:'altitude',ascent_m:'ascent',rpe:'rpe',hr_target:'hr-target',hr_variation_bpm:'hr-variation',hr_response_s:'hr-response',hr_warmup_s:'hr-warmup'})) options[key]=Number($(id).value);
  let times = [...timeList.querySelectorAll('input')].map(input => input.value + '+08:00');
  if (firstOnly) times = times.slice(0, 1);
  return {times, options, export_format:$('export-format').value};
}
async function post(path, body) {
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body), signal:controller.signal});
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || `请求失败（${response.status}）`);
    }
    return response;
  } finally {clearTimeout(timer);}
}
async function action(task) {
  if (busy) return;
  busy = true; $('preview').disabled = $('generate').disabled = $('reshuffle').disabled = true; updateButtons();
  // Prevent edits during an in-flight operation, keeping preview and form in sync.
  const inputs = [...$('settings').querySelectorAll('input,select')];
  inputs.forEach(input => input.disabled = true);
  message('正在处理，请稍候…');
  try {await task();} catch(error) {
    message(error.name === 'AbortError' ? '处理超时，请减少批量数量后重试。' : error.message, true);
  } finally {
    busy = false; inputs.forEach(input => input.disabled = false);
    $('preview').disabled = $('generate').disabled = $('reshuffle').disabled = false; updateButtons();
  }
}
function duration(seconds) {
  seconds = Math.round(seconds); const h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = seconds % 60;
  return `${h ? h + '时 ' : ''}${m}分 ${s}秒`;
}
function render(data) {
  const s = data.summary;
  const values = $('stats').querySelectorAll('dd');
  values[0].textContent = `${(s.distance_m / 1000).toFixed(3)} km`;
  values[1].textContent = duration(s.duration_s);
  const pace = Math.round(s.pace_seconds_per_km);
  values[2].textContent = `${Math.floor(pace/60)}:${String(pace%60).padStart(2,'0')} / km`;
  values[3].textContent = String(s.point_count);
  $('summary-note').textContent = `目标 ${s.requested_distance_m} 米 · 单圈 ${s.lap_length_m.toFixed(2)} 米 · ${s.laps} 圈。所有新增指标为模拟或估算值。`;
  $('extra-stats').replaceChildren();
  const extra=[['总时长',duration(s.elapsed_duration_s)],['暂停',`${s.pause_seconds} 秒`],['运动消耗',s.calories_kcal==null?'—':`${s.calories_kcal} 千卡`],['本地负荷估算',s.training_load_estimate??'—'],['爬升高度',s.ascent_m==null?'—':`${s.ascent_m} 米`],['平均步频',s.average_cadence_spm==null?'—':`${s.average_cadence_spm} 步/分`],['平均功率',s.average_power_w==null?'—':`${s.average_power_w} 瓦`],['平均步幅',s.average_stride_m==null?'—':`${s.average_stride_m.toFixed(2)} 米`]];
  for(const [label,value] of extra){const row=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;row.append(dt,dd);$('extra-stats').append(row);}
  $('empty').hidden = true;
  const canvas = $('track'), ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height;
  const lat0 = data.options.center_lat, lon0 = data.options.center_lon;
  const pts = data.points.map(p => [(p.lon-lon0)*Math.PI/180*6371008.8*Math.cos(lat0*Math.PI/180), (p.lat-lat0)*Math.PI/180*6371008.8]);
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const scale = Math.min((w-160)/(maxX-minX || 1), (h-150)/(maxY-minY || 1));
  const project = p => [w/2+(p[0]-(minX+maxX)/2)*scale, h/2-(p[1]-(minY+maxY)/2)*scale];
  ctx.clearRect(0,0,w,h); ctx.strokeStyle='#d5ddd1'; ctx.lineWidth=1;
  for(let x=0;x<w;x+=60){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}
  for(let y=0;y<h;y+=60){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
  ctx.beginPath(); pts.forEach((p,i)=>{const [x,y]=project(p); i?ctx.lineTo(x,y):ctx.moveTo(x,y);});
  ctx.strokeStyle='rgba(36,102,78,.6)';ctx.lineWidth=2;ctx.lineJoin='round';ctx.stroke();
  [0,pts.length-1].forEach((index,i)=>{const [x,y]=project(pts[index]);ctx.beginPath();ctx.arc(x,y,i?6:12,0,2*Math.PI);ctx.fillStyle=i?'#d05b31':'#24664e';ctx.fill();});
  ctx.fillStyle='#6b786f';ctx.font='20px sans-serif';ctx.fillText(`横向范围 ${(maxX-minX).toFixed(1)} m · 纵向范围 ${(maxY-minY).toFixed(1)} m`,28,h-24);
  $('splits').replaceChildren();
  s.kilometer_splits.forEach((split,i)=>{
    const row=document.createElement('div');
    const label=document.createElement('span'), value=document.createElement('strong');
    label.textContent=split.distance_m>=999.99?`第 ${i+1} 公里`:`第 ${i+1} 段 · ${split.distance_m.toFixed(1)} 米`;
    const seconds=Math.round(split.pace_seconds_per_km);
    value.textContent=`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')} / km`;
    row.append(label,value);$('splits').append(row);
  });
  const paceCanvas=$('pace-chart');paceCanvas.hidden=false;
  const cpace=paceCanvas.getContext('2d'), paces=data.points.map(p=>p.pace_seconds_per_km);
  const low=Math.min(...paces)-5,high=Math.max(...paces)+5;
  cpace.clearRect(0,0,900,220);cpace.strokeStyle='#24664e';cpace.lineWidth=3;cpace.beginPath();
  data.points.forEach((p,i)=>{const x=30+p.distance_m/s.distance_m*840,y=70+(p.pace_seconds_per_km-low)/(high-low)*110;i?cpace.lineTo(x,y):cpace.moveTo(x,y);});cpace.stroke();
  cpace.fillStyle='#6b786f';cpace.font='20px sans-serif';cpace.fillText('模拟配速 · 越靠上越快 · 全程平均保持设定值',30,30);
  const heart = $('heart'); heart.hidden = s.average_hr === null;
  if (!heart.hidden) {
    const c = heart.getContext('2d');c.clearRect(0,0,heart.width,heart.height);c.strokeStyle='#d05b31';c.lineWidth=3;c.beginPath();
    data.points.forEach((p,i)=>{const x=30+i/(data.points.length-1)*840,y=180-(p.hr-Math.min(...data.points.map(p=>p.hr))+5)/(Math.max(...data.points.map(p=>p.hr))-Math.min(...data.points.map(p=>p.hr))+10)*120;i?c.lineTo(x,y):c.moveTo(x,y);});c.stroke();
    c.fillStyle='#6b786f';c.font='20px sans-serif';c.fillText(`模拟心率 · 平均 ${s.average_hr} · 最高 ${s.max_hr} bpm`,30,30);
  }
}
$('preview').onclick = () => {let body;try{body=payload(true);}catch(e){return message(e.message,true);}action(async()=>{render(await (await post('/preview',body)).json());message('预览完成。请核对轨迹与统计。');});};
$('settings').onsubmit = event => {
  event.preventDefault();let body;try{body=payload();}catch(e){return message(e.message,true);}
  action(async()=>{
    const response = await post('/generate',body), blob = await response.blob();
    const header = response.headers.get('Content-Disposition') || '';
    const match = header.match(/filename="?([^";]+)"?/i);
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href=url;link.download=match?match[1]:(body.times.length>1?'synthetic_runs.zip':`synthetic_run.${body.export_format}`);
    document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
    message('文件已下载。传到手机后，在 Keep「数据文件导入」中选择；首次先测试单条。');
  });
};
$('add-time').onclick=addTime;
$('reshuffle').onclick=()=>{$('random-seed').value=String(crypto.getRandomValues(new Uint32Array(1))[0]%2147483648);invalidate();message('已更换变化编号，请重新预览。');};
$('simulate-hr').onchange=()=>{$('hr-fields').hidden=!$('simulate-hr').checked;invalidate();};
$('settings').addEventListener('input',invalidate);
addTime();

$('simulate-metrics').onchange=()=>{$('metric-fields').hidden=!$('simulate-metrics').checked;invalidate();};
$('export-format').onchange=updateButtons;
