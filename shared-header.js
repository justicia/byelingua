(function(){
  if(!document.querySelector('link[href="/shared-ui.css"]')){
    const stylesheet=document.createElement('link');stylesheet.rel='stylesheet';stylesheet.href='/shared-ui.css';document.head.appendChild(stylesheet);
  }
  if(!document.querySelector('link[data-byelingua-fonts]')){
    const fonts=document.createElement('link');fonts.rel='stylesheet';fonts.dataset.byelinguaFonts='';fonts.href='https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@400;700;900&family=Noto+Sans+SC:wght@400;500;600;700&family=Poppins:wght@400;500;600;700&display=swap';document.head.appendChild(fonts);
  }
  const overlayState={count:0,overflow:'',position:'',top:'',width:'',scrollY:0};
  window.ByelinguaOverlay=window.ByelinguaOverlay||{
    lock(){
      if(overlayState.count++>0)return;
      overlayState.overflow=document.body.style.overflow;
      overlayState.position=document.body.style.position;
      overlayState.top=document.body.style.top;
      overlayState.width=document.body.style.width;
      overlayState.scrollY=window.scrollY;
      document.body.style.overflow='hidden';
    },
    unlock(){
      if(!overlayState.count)return;
      if(--overlayState.count>0)return;
      document.body.style.overflow=overlayState.overflow;
      document.body.style.position=overlayState.position;
      document.body.style.top=overlayState.top;
      document.body.style.width=overlayState.width;
      window.scrollTo(0,overlayState.scrollY);
    }
  };
  const tokenPresent=()=>{
    try{
      for(let i=0;i<localStorage.length;i++){
        const key=localStorage.key(i)||'';
        if(!key.startsWith('sb-')||!key.endsWith('-auth-token'))continue;
        const value=JSON.parse(localStorage.getItem(key)||'{}');
        if(value.access_token)return true;
      }
    }catch(_){/* Page-specific auth state remains authoritative. */}
    return false;
  };
  function activeNav(path){
    if(path==='/schedule.html'||path==='/schedule-editor.html'||path==='/schedule-summary.html')return 'schedule';
    if(path==='/reviews.html')return 'reviews';
    return 'reading';
  }
  window.ByelinguaHeader={mount:function(target,options){
    if(!target)return;
    options=options||{};
    const i18n=window.ByelinguaI18n;
    target.classList.add('byelingua-compact-header');
    target.innerHTML=`
      <div class="byelingua-compact-inner">
        <a class="byelingua-compact-brand" href="/" aria-label="Byelingua home">BYELINGUA</a>
        <nav class="byelingua-primary-nav" aria-label="Primary navigation">
          <a data-nav="reading" href="/">Reading</a>
          <a data-nav="schedule" href="/schedule.html">Schedule</a>
          <a data-nav="reviews" href="/reviews.html">Reviews</a>
        </nav>
        <div class="byelingua-compact-spacer"></div>
        <div class="byelingua-compact-actions">
          <a class="byelingua-search-link" data-shared-search href="/?focus=search">Search</a>
          <div class="byelingua-language-switch" role="group" aria-label="Language">
            <button type="button" data-shared-language="zh">中文</button>
            <button type="button" data-shared-language="en">English</button>
          </div>
          <span id="accountLabel" class="byelingua-compact-account" hidden></span>
          <button id="accountButton" type="button" data-shared-account></button>
          <button id="logoutButton" type="button" data-shared-signout hidden></button>
          <button class="byelingua-menu-toggle" type="button" aria-expanded="false" aria-controls="byelinguaMobileMenu">Menu</button>
        </div>
      </div>
      <nav id="byelinguaMobileMenu" class="byelingua-mobile-menu" aria-label="Mobile navigation" hidden>
        <a data-nav="reading" href="/">Reading</a>
        <a data-nav="schedule" href="/schedule.html">Schedule</a>
        <a data-nav="reviews" href="/reviews.html">Reviews</a>
        <a data-shared-search href="/?focus=search">Search</a>
        <button type="button" data-mobile-account>Account</button>
        <div class="byelingua-mobile-languages" role="group" aria-label="Language">
          <button type="button" data-shared-language="zh">中文</button>
          <button type="button" data-shared-language="en">English</button>
        </div>
      </nav>`;
    const menu=target.querySelector('.byelingua-mobile-menu');
    const menuToggle=target.querySelector('.byelingua-menu-toggle');
    const closeMenu=()=>{
      if(menu.hidden)return;
      menu.hidden=true;
      menuToggle.setAttribute('aria-expanded','false');
      window.ByelinguaOverlay.unlock();
    };
    const openMenu=()=>{
      menu.hidden=false;
      menuToggle.setAttribute('aria-expanded','true');
      window.ByelinguaOverlay.lock();
    };
    menuToggle.onclick=()=>menu.hidden?openMenu():closeMenu();
    menu.querySelectorAll('a').forEach(link=>link.addEventListener('click',closeMenu));
    document.addEventListener('keydown',event=>{if(event.key==='Escape')closeMenu()});
    const syncHeight=()=>document.documentElement.style.setProperty('--byelingua-header-height',`${target.getBoundingClientRect().height}px`);
    const render=()=>{
      const language=i18n?i18n.getUiLanguage():(localStorage.getItem('byelinguaUiLanguage')||'zh');
      const authenticated=options.isAuthenticated?Boolean(options.isAuthenticated()):tokenPresent();
      const account=target.querySelector('[data-shared-account]');
      const signout=target.querySelector('[data-shared-signout]');
      account.textContent=authenticated?(language==='en'?'Account':'账户'):(language==='en'?'Sign in':'登录');
      signout.textContent=language==='en'?'Sign out':'退出登录';
      signout.hidden=!authenticated;
      target.querySelectorAll('[data-shared-language]').forEach(button=>button.classList.toggle('active',button.dataset.sharedLanguage===language));
      target.querySelectorAll('[data-nav]').forEach(link=>link.classList.toggle('active',link.dataset.nav===activeNav(location.pathname)));
      document.documentElement.lang=language==='en'?'en-GB':'zh-CN';
      syncHeight();
    };
    target.querySelectorAll('[data-shared-language]').forEach(button=>button.onclick=()=>{
      localStorage.setItem('byelinguaUiLanguage',button.dataset.sharedLanguage);
      window.dispatchEvent(new CustomEvent('byelingua-language-change',{detail:button.dataset.sharedLanguage}));
      render();
    });
    target.querySelector('[data-shared-account]').onclick=()=>options.onAccount?options.onAccount():(location.href='/account.html');
    target.querySelector('[data-mobile-account]').onclick=()=>{
      closeMenu();
      if(options.onAccount)options.onAccount();else location.href='/account.html';
    };
    target.querySelector('[data-shared-signout]').onclick=async()=>{
      try{
        const cfg=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'get_auth_config'})}).then(r=>r.json());
        if(window.supabase&&cfg.url&&cfg.publishable_key){
          const client=window.supabase.createClient(cfg.url,cfg.publishable_key);
          await client.auth.signOut();
        }
      }finally{location.href='/'}
    };
    window.addEventListener('byelingua-language-change',render);
    window.addEventListener('byelingua-auth-state',render);
    if(window.ResizeObserver)new ResizeObserver(syncHeight).observe(target);
    render();
    return target;
  }};
  function autoMountLegacyPage(){
    if(document.getElementById('sharedHeader'))return;
    const legacy=document.querySelector('.site-header');
    const side=document.querySelector('.side');
    if(!legacy&&!side)return;
    if(side)document.body.classList.add('phase1-legacy-home');
    const target=document.createElement('header');
    target.id='sharedHeader';
    target.className='legacy-shared-header';
    (legacy||document.body.firstElementChild)?.before(target);
    if(legacy)legacy.hidden=true;
    window.ByelinguaHeader.mount(target);
    enhanceReadingHome();
  }
  function enhanceReadingHome(){
    const main=document.querySelector('main.layout,.layout > main');
    const countryNav=document.getElementById('countryNav');
    if(!main||!countryNav||document.getElementById('readingSection'))return;
    const reading=document.createElement('section');
    reading.id='readingSection';
    reading.className='home-section reading-section';
    reading.innerHTML='<div class="section-kicker">Reading</div><h2>Latest Reading</h2><p class="hint">Browse public Chinese and English articles by country, category and author.</p>';
    if(!main.contains(countryNav)){
      const anchor=main.querySelector('#searchForm,.toolbar,#articles')||main.firstElementChild;
      if(anchor)anchor.before(countryNav);
    }
    countryNav.before(reading);
    countryNav.classList.add('reading-filters');
    const scheduleLink=main.querySelector('a[href="/schedule.html"]')||document.createElement('a');
    if(!scheduleLink.href){scheduleLink.href='/schedule.html';scheduleLink.className='btn secondary';scheduleLink.textContent='Open Schedule';}
    if(!document.getElementById('performanceSearch')){
      const performance=document.createElement('section');
      performance.id='performanceSearch';
      performance.className='home-section performance-search';
      performance.innerHTML='<div class="section-kicker">Plan</div><h2>Performance Search</h2><p class="hint">Find performances by date, city, venue, organization, artist or work.</p>';
      if(scheduleLink.parentElement&&scheduleLink.parentElement!==main)scheduleLink.parentElement.replaceWith(performance);
      else main.appendChild(performance);
      performance.appendChild(scheduleLink);
    }
    if(!document.getElementById('recentReviews')){
      const reviews=document.createElement('section');
      reviews.id='recentReviews';
      reviews.className='home-section reviews-placeholder phase1-empty-state';
      reviews.innerHTML='<h2>Recent Reviews</h2><p>Reviews are read-only in this phase. Browse the Reviews page when editorial entries are available.</p><a href="/reviews.html">Open Reviews</a>';
      main.appendChild(reviews);
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',autoMountLegacyPage,{once:true});
  else autoMountLegacyPage();
})();
