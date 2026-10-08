(function(){
  const english=()=>localStorage.getItem('byelinguaUiLanguage')==='en';
  const launcher=document.createElement('button');launcher.type='button';launcher.className='planner-launcher';launcher.setAttribute('aria-expanded','false');launcher.setAttribute('aria-controls','floatingPlanner');
  const panel=document.createElement('section');panel.id='floatingPlanner';panel.className='floating-planner';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.tabIndex=-1;
  panel.innerHTML='<div class="floating-planner-head"><h2></h2><button type="button" data-floating-selected></button><a href="/schedule.html" data-full-planner></a><button type="button" data-floating-close aria-label="Close">×</button></div><iframe title="Schedule Planner" data-floating-frame></iframe>';
  let frameLoaded=false;
  function labels(){launcher.textContent=(english()?'Go to performances':'去看演出')+' · '+window.ByelinguaPlannerState.read().selected.length;panel.setAttribute('aria-label',english()?'Performance planner':'演出规划');panel.querySelector('h2').textContent=english()?'Planner':'去看演出';panel.querySelector('[data-floating-selected]').textContent=english()?'Selected':'已选演出';panel.querySelector('[data-full-planner]').textContent=english()?'Full Planner ↗':'打开完整 Planner ↗';panel.querySelector('[data-floating-close]').setAttribute('aria-label',english()?'Close planner':'收起 Planner')}
  function close(){panel.hidden=true;launcher.setAttribute('aria-expanded','false');document.body.classList.remove('floating-planner-open');launcher.focus()}
  launcher.onclick=()=>{if(!panel.hidden){close();return}panel.hidden=false;launcher.setAttribute('aria-expanded','true');document.body.classList.add('floating-planner-open');if(!frameLoaded){panel.querySelector('iframe').src='/schedule.html?embed=1';frameLoaded=true}labels();panel.focus()};
  panel.querySelector('[data-floating-close]').onclick=close;
  panel.querySelector('[data-floating-selected]').onclick=()=>{panel.querySelector('iframe').contentWindow?.postMessage({type:'byelingua-show-selected'},location.origin)};
  panel.addEventListener('keydown',event=>{if(event.key==='Escape')close();if(event.key==='Tab'){const controls=[...panel.querySelectorAll('button,a,iframe')];if(event.shiftKey&&document.activeElement===controls[0]){event.preventDefault();controls.at(-1).focus()}else if(!event.shiftKey&&document.activeElement===controls.at(-1)){event.preventDefault();controls[0].focus()}}});
  window.addEventListener('message',event=>{if(event.origin===location.origin&&event.source===panel.querySelector('iframe').contentWindow&&event.data?.type==='byelingua-close-planner')close()});
  document.body.append(launcher,panel);window.ByelinguaPlannerState.subscribe(labels);window.addEventListener('byelingua-language-change',labels);new MutationObserver(labels).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});labels();
})();
