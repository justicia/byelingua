(function(){
  const styleId='byelingua-shared-header-style';
  if(!document.getElementById(styleId)){
    const style=document.createElement('style');style.id=styleId;style.textContent=`
      .byelingua-compact-header{position:sticky;top:0;z-index:40;border-bottom:1px solid #d7d7ce;background:rgba(245,242,233,.97);backdrop-filter:blur(8px)}
      .byelingua-compact-inner{width:min(1120px,calc(100% - 28px));margin:auto;padding:12px 0 10px;display:flex;flex-direction:column;align-items:center;gap:4px;text-align:center}
      .byelingua-compact-brand{color:#214d3a;font:600 25px/.95 Georgia,serif;text-decoration:none;letter-spacing:-.025em}
      .byelingua-compact-tagline{color:#68716b;font-size:10px;letter-spacing:.08em}
      .byelingua-compact-subtitle{margin-top:3px;color:#214d3a}.byelingua-compact-subtitle-label{font-size:10px;font-weight:750;letter-spacing:.1em}.byelingua-compact-subtitle-text{font:13px/1.4 Georgia,serif}
      .byelingua-compact-spacer{flex:1}.byelingua-compact-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
      .byelingua-compact-actions button{font:inherit;cursor:pointer;border:1px solid #aebbb2;border-radius:4px;padding:6px 9px;background:transparent;color:#214d3a}
      .byelingua-compact-actions button.active{background:#214d3a;color:#fff;border-color:#214d3a}
      .byelingua-primary-nav{border-top:1px solid #d7d7ce}
      .byelingua-primary-inner{width:min(1120px,calc(100% - 28px));min-height:50px;margin:auto;display:flex;align-items:center;gap:20px}
      .byelingua-primary-links,.byelingua-primary-actions{display:flex;align-items:center;gap:18px}
      .byelingua-primary-links a,.byelingua-primary-links span{color:#214d3a;font-size:13px;font-weight:650;text-decoration:none;white-space:nowrap}
      .byelingua-primary-links a:hover{text-decoration:underline}
      .byelingua-primary-links a[aria-current="page"]{text-decoration:underline;text-underline-offset:5px}
      .byelingua-primary-links [aria-disabled="true"]{opacity:.65}
      .byelingua-primary-spacer{flex:1}
      .byelingua-primary-actions{gap:6px}
      .byelingua-primary-actions button{font:inherit;font-size:13px;font-weight:650;cursor:pointer;border:1px solid #aebbb2;border-radius:4px;padding:6px 9px;background:transparent;color:#214d3a;white-space:nowrap}
      .byelingua-primary-actions [data-shared-language]{font-size:11px;padding:7px 9px}
      .byelingua-primary-actions button.active{background:#214d3a;color:#fff;border-color:#214d3a}
      .schedule-site-header.byelingua-compact-header{width:100%;padding:0;border-bottom:0}.schedule-site-header.byelingua-compact-header .schedule-identity{display:flex;align-items:center;gap:14px}.schedule-site-header.byelingua-compact-header .schedule-brand{font-size:25px}.schedule-site-header.byelingua-compact-header .schedule-tagline{margin:0}.schedule-site-header.byelingua-compact-header .schedule-page-title,.schedule-site-header.byelingua-compact-header .schedule-page-description{display:none}.schedule-page-heading{width:min(1120px,calc(100% - 28px));margin:18px auto 2px}.schedule-page-heading h1{margin:0;color:#214d3a}.schedule-page-heading .hint{margin-top:3px}
      .byelingua-compact-account{color:#68716b;font-size:12px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}@media(max-width:700px){.byelingua-compact-inner{min-height:48px;gap:8px}.byelingua-compact-tagline{display:none}.byelingua-compact-brand{font-size:22px}.byelingua-primary-inner{flex-wrap:wrap;gap:8px;padding:8px 0}.byelingua-primary-links{width:100%;gap:18px;overflow-x:auto}.byelingua-primary-actions{width:100%;justify-content:flex-end;flex-wrap:wrap}.byelingua-primary-actions button{min-height:36px;padding:5px 7px}.byelingua-primary-spacer{display:none}.schedule-site-header.byelingua-compact-header .schedule-identity{width:auto}.schedule-site-header.byelingua-compact-header .schedule-tagline{display:none}}
      @media(min-width:901px){.byelingua-primary-inner{display:grid;grid-template-columns:1fr auto 1fr}.byelingua-primary-links{grid-column:2}.byelingua-primary-spacer{display:none}.byelingua-primary-actions{grid-column:3;justify-self:end}}
      @media(max-width:900px){.byelingua-primary-inner{flex-wrap:wrap;gap:8px;padding:8px 0}.byelingua-primary-links{width:100%;justify-content:center;overflow-x:auto}.byelingua-primary-actions{width:100%;justify-content:center;flex-wrap:wrap}.byelingua-primary-spacer{display:none}}
      @media(max-width:700px){.byelingua-compact-tagline{display:block}.byelingua-compact-inner{padding:10px 0}}
    `;document.head.append(style)
  }
  window.ByelinguaHeader={mount:function(target,options){
    if(!target)return;
    options=options||{};
    const i18n=window.ByelinguaI18n;
    target.classList.add('byelingua-compact-header');
    target.innerHTML='<div class="byelingua-compact-inner"><a class="byelingua-compact-brand" href="/" aria-label="Byelingua home">BYELINGUA</a><span class="byelingua-compact-tagline">SO MANY COUNTRIES. SO MANY LANGUAGES. I SIMPLY CAN’T.</span><div class="byelingua-compact-subtitle"><div class="byelingua-compact-subtitle-label" data-header-subtitle-label>全球乐评收集前线</div><div class="byelingua-compact-subtitle-text" data-header-subtitle-text>文盲也有看最新八卦资讯的权利。</div></div></div><nav class="byelingua-primary-nav" aria-label="Primary navigation"><div class="byelingua-primary-inner"><div class="byelingua-primary-links"><a href="/" data-nav-news>新闻</a><a href="/schedule.html" data-nav-schedule>日程设计</a><span data-nav-concert-reviews aria-disabled="true">音乐会 Review</span></div><span class="byelingua-primary-spacer"></span><div class="byelingua-primary-actions"><button type="button" data-shared-language="zh">CN</button><button type="button" data-shared-language="en">EN</button><span id="accountLabel" hidden></span><button id="accountButton" type="button" data-shared-account>用户中心</button><button type="button" data-shared-register>注册</button><button id="logoutButton" type="button" data-shared-signout hidden>退出登录</button></div></div></nav>';
    const render=()=>{
      const language=i18n?i18n.getUiLanguage():(localStorage.getItem('byelinguaUiLanguage')||'zh');
      const english=language==='en';
      target.querySelector('[data-header-subtitle-label]').textContent=english?'GLOBAL MUSIC CRITICISM FRONTLINE':'全球乐评收集前线';
      target.querySelector('[data-header-subtitle-text]').textContent=english?'EVEN THE LINGUISTICALLY CHALLENGED DESERVE THE LATEST GOSSIP.':'文盲也有看最新八卦资讯的权利。';
      target.querySelector('[data-nav-news]').textContent=english?'News':'新闻';
      target.querySelector('[data-nav-schedule]').textContent=english?'Schedule Builder':'日程设计';
      target.querySelector('[data-nav-concert-reviews]').textContent=english?'Concert Reviews':'音乐会 Review';
      target.querySelector('[data-shared-account]').textContent=english?'User Center':'用户中心';
      target.querySelector('[data-shared-register]').textContent=english?'Register':'注册';
      target.querySelector('[data-shared-signout]').textContent=english?'Sign out':'退出登录';
      target.querySelector('.byelingua-primary-nav').setAttribute('aria-label',english?'Primary navigation':'主导航');
      target.querySelectorAll('[data-shared-language]').forEach(button=>button.classList.toggle('active',button.dataset.sharedLanguage===language));
      document.documentElement.lang=english?'en-GB':'zh-CN';
    };
    const path=location.pathname;
    if(path==='/'||path==='/index.html')target.querySelector('[data-nav-news]').setAttribute('aria-current','page');
    if(path.startsWith('/schedule'))target.querySelector('[data-nav-schedule]').setAttribute('aria-current','page');
    const hasSession=()=>[...Object.keys(localStorage)].some(key=>key.startsWith('sb-')&&key.endsWith('-auth-token'));
    const renderAuth=()=>{
      const signedIn=hasSession();
      target.querySelector('[data-shared-register]').hidden=signedIn;
      target.querySelector('[data-shared-signout]').hidden=!signedIn;
    };
    target.querySelectorAll('[data-shared-language]').forEach(button=>button.onclick=()=>{
      localStorage.setItem('byelinguaUiLanguage',button.dataset.sharedLanguage);
      window.dispatchEvent(new CustomEvent('byelingua-language-change',{detail:button.dataset.sharedLanguage}));
      render();
    });
    target.querySelector('[data-shared-account]').onclick=()=>location.href=hasSession()?'/account.html':'/?login=1';
    target.querySelector('[data-shared-register]').onclick=()=>location.href='/?register=1';
    target.querySelector('[data-shared-signout]').onclick=async()=>{
      try{
        if(window.supabase){
          const cfg=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'get_auth_config'})}).then(r=>r.json());
          await window.supabase.createClient(cfg.url,cfg.publishable_key).auth.signOut();
        }else for(const key of Object.keys(localStorage))if(key.startsWith('sb-')&&key.endsWith('-auth-token'))localStorage.removeItem(key);
      }finally{location.href='/'}
    };
    render();renderAuth();
    window.addEventListener('byelingua-language-change',render);
    window.addEventListener('storage',renderAuth);
    const updateHeight=()=>document.documentElement.style.setProperty('--byelingua-header-height',`${Math.ceil(target.getBoundingClientRect().height)}px`);
    updateHeight();if(window.ResizeObserver)new ResizeObserver(updateHeight).observe(target);
    return target;
  }};

  window.addEventListener('load',()=>{
    // Compact event pagination on Schedule.
    if(document.getElementById('eventPagination')&&typeof renderEventPagination==='function'){
      renderEventPagination=function(){
        const totalPages=Math.max(1,Math.ceil(events.length/eventPageSize));
        eventPage=Math.min(Math.max(1,eventPage),totalPages);
        if(events.length<=eventPageSize){eventPagination.innerHTML='';return}
        const pages=[];
        if(totalPages<=7){for(let page=1;page<=totalPages;page++)pages.push(page)}
        else if(eventPage<=3)pages.push(1,2,3,'ellipsis',totalPages);
        else if(eventPage>=totalPages-2)pages.push(1,'ellipsis',totalPages-2,totalPages-1,totalPages);
        else pages.push(1,'ellipsis',eventPage-1,eventPage,eventPage+1,'ellipsis',totalPages);
        const pageHtml=pages.map(page=>page==='ellipsis'?'<span class="pagination-ellipsis" aria-hidden="true">…</span>':`<button type="button" class="secondary ${eventPage===page?'active':''}" data-page-number="${page}" ${eventPage===page?'aria-current="page"':''}>${page}</button>`).join('');
        eventPagination.innerHTML=`<button type="button" class="secondary" data-page-prev ${eventPage===1?'disabled':''}>Previous</button>${pageHtml}<button type="button" class="secondary" data-page-next ${eventPage===totalPages?'disabled':''}>Next</button>`;
        eventPagination.querySelector('[data-page-prev]')?.addEventListener('click',()=>{eventPage--;renderEvents()});
        eventPagination.querySelector('[data-page-next]')?.addEventListener('click',()=>{eventPage++;renderEvents()});
        eventPagination.querySelectorAll('[data-page-number]').forEach(button=>button.addEventListener('click',()=>{eventPage=Number(button.dataset.pageNumber);renderEvents()}));
      };
      const compactStyle=document.createElement('style');compactStyle.textContent='.event-pagination .pagination-ellipsis{display:inline-flex;align-items:center;justify-content:center;min-width:24px;color:#68716b}';document.head.appendChild(compactStyle);renderEventPagination();
    }

    // Schedule drawers/panels must remain below the sticky global header and closable after scrolling.
    if(document.querySelector('.my-schedule-panel,.persistent-event-pane,#artistSidePanel')){
      const drawerFix=document.createElement('style');drawerFix.textContent=`
        @media(min-width:761px){
          .my-schedule-panel,.persistent-event-pane{top:64px!important;height:calc(100vh - 78px)!important}
          #artistSidePanel{top:52px!important;height:calc(100vh - 52px)!important}
        }
        @media(max-width:760px){
          .my-schedule-panel.mobile-open,.persistent-event-pane,#artistSidePanel.open{top:48px!important;bottom:0!important;height:calc(100dvh - 48px)!important;z-index:45!important}
          .my-schedule-header,.persistent-event-header,.artist-drawer-head{position:sticky!important;top:0!important;z-index:3!important}
        }
      `;document.head.appendChild(drawerFix);
      document.addEventListener('keydown',event=>{if(event.key!=='Escape')return;document.querySelector('.my-schedule-panel.mobile-open')?.classList.remove('mobile-open');const pane=document.getElementById('persistentEventDetail');if(pane&&!pane.hidden){pane.querySelector('[data-close-persistent]')?.click()}const artist=document.getElementById('artistSidePanel');if(artist?.classList.contains('open'))artist.querySelector('.artist-drawer-close')?.click();document.body.style.overflow=''});
    }

    // One global credit renderer for every venue, organization and Event Detail surface.
    // The authoritative implementation lives in shared-i18n.js / ByelinguaCredits.
    if(window.ByelinguaCredits?.install){
      window.ByelinguaCredits.install();
      if(typeof activeEventId!=='undefined'&&activeEventId&&typeof showDetail==='function')showDetail(activeEventId);
    }

    // Geography hotfix for Italy: Milan/Milano must be included alongside Rome/Roma.
    const locationSuggestions=document.getElementById('locationSuggestions');
    const locationInput=document.getElementById('locationSearch');
    if(locationSuggestions&&locationInput&&typeof selectedCities!=='undefined'){
      locationSuggestions.addEventListener('click',event=>{
        const button=event.target.closest('.location-suggestion');if(!button||button.textContent.trim().toLowerCase().indexOf('italy')!==0)return;
        event.preventDefault();event.stopImmediatePropagation();
        selectedCities.clear();
        const italyCities=(options?.cities||[]).filter(city=>['rome','roma','milan','milano'].includes(String(city).trim().toLowerCase()));
        italyCities.forEach(city=>selectedCities.add(city));
        if(typeof selectedOrganizations!=='undefined')selectedOrganizations.clear();
        if(typeof selectedVenues!=='undefined')selectedVenues.clear();
        locationInput.value='Italy';locationSuggestions.hidden=true;locationSuggestions.innerHTML='';
        if(typeof scheduleProgressiveRefresh==='function')scheduleProgressiveRefresh();
      },true);
    }
  });
})();
