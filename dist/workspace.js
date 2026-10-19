$('#stems').innerHTML=emptyRows();
$('#choose').onclick=()=>$('#file').click();
$('#drop').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('#file').click();}};
function showTab(name){for(const tab of ['loudness','analysis']){const active=tab===name;$('#'+tab+'-tab').setAttribute('aria-selected',String(active));$('#'+tab+'-tab').tabIndex=active?0:-1;$('#'+tab+'-panel').hidden=!active;}}
for(const name of ['loudness','analysis']){const tab=$('#'+name+'-tab');tab.onclick=()=>showTab(name);tab.onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();const next=name==='analysis'?'loudness':'analysis';showTab(next);$('#'+next+'-tab').focus();}};}
window.addEventListener('recording-ready',()=>{failedTasks.clear();refreshRetry();$('#separation-progress').hidden=true;$('#graph-empty').hidden=true;$('#rms-panel').hidden=false;$('#loudness-timeline').hidden=true;showTab('loudness');queueMicrotask(()=>{if(backend){analyzeRecording();separate();}else{failedTasks.add('analysis');failedTasks.add('separation');refreshRetry();$('#upload-state').textContent='Local service unavailable. Start it, then choose Retry.';}});});
async function seekTo(value){if(!buffers.length)return;const resume=playing;stop();offset=Math.max(0,Math.min(duration,value));$('#seek').value=offset;$('#time').textContent=`${clock(offset)} / ${clock(duration)}`;updatePlayhead(offset);if(resume)await play();}
$('#stems').addEventListener('click',e=>{const wave=e.target.closest('[data-seek]');if(!wave)return;const box=wave.getBoundingClientRect();seekTo((e.clientX-box.left)/box.width*duration);});
$('#stems').addEventListener('keydown',e=>{if(!e.target.matches('[data-seek]'))return;let position=Number($('#seek').value);if(e.key==='ArrowRight')position+=5;else if(e.key==='ArrowLeft')position-=5;else if(e.key==='Home')position=0;else if(e.key==='End')position=duration;else return;e.preventDefault();seekTo(position);});

const failedTasks=new Set();
function refreshRetry(){const button=$('#retry');button.hidden=failedTasks.size===0;button.disabled=busy||analysisBusy;}
window.addEventListener('task-state',e=>{const {task,state}=e.detail;if(state==='failed')failedTasks.add(task);else failedTasks.delete(task);refreshRetry();setTimeout(refreshRetry,0);});
$('#retry').onclick=async()=>{await health();if(!backend){$('#upload-state').textContent='Local service unavailable. Start it, then try again.';return;}const pending=[...failedTasks];if(pending.includes('analysis'))analyzeRecording();if(pending.includes('separation'))separate();};
setInterval(refreshRetry,1000);

// Decorative tilt is disabled over controls and while audio is playing.
const depthPreference=matchMedia('(prefers-reduced-motion: reduce)');
const finePointer=matchMedia('(hover: hover) and (pointer: fine)');
for(const surface of [$('#player'),$('#analysis')]){
 let depthFrame=0;
 const resetDepth=()=>{cancelAnimationFrame(depthFrame);surface.style.setProperty('--tilt-x','0deg');surface.style.setProperty('--tilt-y','0deg');surface.classList.remove('depth-hover');};
 surface.addEventListener('pointermove',event=>{
  if(depthPreference.matches||!finePointer.matches||playing||event.target.closest('button,input,[role=slider],.wave-box')){resetDepth();return;}
  const box=surface.getBoundingClientRect(),x=Math.max(0,Math.min(1,(event.clientX-box.left)/box.width)),y=Math.max(0,Math.min(1,(event.clientY-box.top)/box.height));
  cancelAnimationFrame(depthFrame);depthFrame=requestAnimationFrame(()=>{surface.style.setProperty('--tilt-x',`${((.5-y)*.7).toFixed(2)}deg`);surface.style.setProperty('--tilt-y',`${((x-.5)*.9).toFixed(2)}deg`);surface.style.setProperty('--light-x',`${(x*100).toFixed(1)}%`);surface.style.setProperty('--light-y',`${(y*100).toFixed(1)}%`);surface.classList.add('depth-hover');});
 });
 surface.addEventListener('pointerleave',resetDepth);surface.addEventListener('focusin',resetDepth);surface.addEventListener('pointerdown',resetDepth);depthPreference.addEventListener('change',resetDepth);
}
