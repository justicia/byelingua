(function(){
  const styleId='byelingua-shared-header-style';
  if(!document.getElementById(styleId)){
    const style=document.createElement('style');style.id=styleId;style.textContent=`
      .byelingua-compact-header{position:sticky;top:0;z-index:40;border-bottom:1px solid #d7d7ce;background:rgba(245,242,233,.97);backdrop-filter:blur(8px)}
      .byelingua-compact-inner{width:min(1120px,calc(100% - 28px));min-height:52px;margin:auto;display:flex;align-items:center;gap:16px}
      .byelingua-compact-brand{color:#214d3a;font:600 25px/.95 Georgia,serif;text-decoration:none;letter-spacing:-.025em}
      .byelingua-compact-tagline{color:#68716b;font-size:10px;letter-spacing:.08em;white-space:nowrap}
      .byelingua-compact-spacer{flex:1}.byelingua-compact-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
      .byelingua-compact-actions button{font:inherit;cursor:pointer;border:1px solid #aebbb2;border-radius:4px;padding:6px 9px;background:transparent;color:#214d3a}
      .byelingua-compact-actions button.active{background:#214d3a;color:#fff;border-color:#214d3a}
      .schedule-site-header.byelingua-compact-header{width:100%;padding:0;border-bottom:0}.schedule-site-header.byelingua-compact-header .schedule-identity{display:flex;align-items:center;gap:14px}.schedule-site-header.byelingua-compact-header .schedule-brand{font-size:25px}.schedule-site-header.byelingua-compact-header .schedule-tagline{margin:0}.schedule-site-header.byelingua-compact-header .schedule-page-title,.schedule-site-header.byelingua-compact-header .schedule-page-description{display:none}.schedule-page-heading{width:min(1120px,calc(100% - 28px));margin:18px auto 2px}.schedule-page-heading h1{margin:0;color:#214d3a}.schedule-page-heading .hint{margin-top:3px}
      .byelingua-compact-account{color:#68716b;font-size:12px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}@media(max-width:700px){.byelingua-compact-inner{min-height:48px;gap:8px}.byelingua-compact-tagline{display:none}.byelingua-compact-brand{font-size:22px}.byelingua-compact-actions button{min-height:36px;padding:5px 7px}.schedule-site-header.byelingua-compact-header .schedule-identity{width:auto}.schedule-site-header.byelingua-compact-header .schedule-tagline{display:none}}
    `;document.head.append(style)
  }
  window.ByelinguaHeader={mount:function(target,options){if(!target)return;options=options||{};const i18n=window.ByelinguaI18n;target.classList.add('byelingua-compact-header');target.innerHTML='<div class="byelingua-compact-inner"><a class="byelingua-compact-brand" href="/" aria-label="Byelingua home">BYELINGUA</a><span class="byelingua-compact-tagline">SO MANY COUNTRIES. SO MANY LANGUAGES. I SIMPLY CAN’T.</span><span class="byelingua-compact-spacer"></span><div class="byelingua-compact-actions"><span id="accountLabel" hidden></span><button id="accountButton" type="button" data-shared-account></button><button id="logoutButton" type="button" data-shared-signout></button><button type="button" data-shared-language="zh">中文</button><button type="button" data-shared-language="en">English</button></div></div>';const render=()=>{const language=i18n?i18n.getUiLanguage():(localStorage.getItem('byelinguaUiLanguage')||'zh');target.querySelector('[data-shared-account]').textContent=language==='en'?'User Center':'用户中心';target.querySelector('[data-shared-signout]').textContent=language==='en'?'Sign out':'退出登录';target.querySelectorAll('[data-shared-language]').forEach(button=>button.classList.toggle('active',button.dataset.sharedLanguage===language));document.documentElement.lang=language==='en'?'en-GB':'zh-CN'};target.querySelectorAll('[data-shared-language]').forEach(button=>button.onclick=()=>{localStorage.setItem('byelinguaUiLanguage',button.dataset.sharedLanguage);window.dispatchEvent(new CustomEvent('byelingua-language-change',{detail:button.dataset.sharedLanguage}));render()});target.querySelector('[data-shared-account]').onclick=()=>location.href='/account.html';target.querySelector('[data-shared-signout]').onclick=async()=>{try{const cfg=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'get_auth_config'})}).then(r=>r.json());if(window.supabase){const client=window.supabase.createClient(cfg.url,cfg.publishable_key);await client.auth.signOut()}}finally{location.href='/'}};render();window.addEventListener('byelingua-language-change',render);return target}};

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

    // Opera presentation: explicit character credits are Cast; production roles are Artistic Team; ensembles stay separate.
    if(typeof renderPresentationCredits==='function'){
      renderPresentationCredits=function(event){
        const esc=window.escapeHtml||((value)=>String(value??''));
        const credits=event.credits||[],opera=['opera','operetta'].includes(String(event.event_type||'').toLowerCase());
        const roleKey=value=>String(value||'').toLowerCase().replace(/[\s-]+/g,'_');
        const ensembleRoles=new Set(['orchestra','ensemble','choir','chorus']);
        const roleLabel=value=>typeof _roleLabel==='function'?_roleLabel(value):(typeof formattedRole==='function'?formattedRole(value):String(value||''));
        const person=x=>typeof artistLink==='function'?artistLink(x):esc(x.artist_name||'');
        if(!opera){
          const artists=credits.filter(x=>!ensembleRoles.has(roleKey(x.role))).map(x=>`<li>${person(x)} · ${esc(roleLabel(x.role||'Artist'))}</li>`).join('');
          const ensembles=credits.filter(x=>ensembleRoles.has(roleKey(x.role))).map(x=>`<li>${person(x)}</li>`).join('');
          return `<h4>Artists / Artistic Team</h4><ul>${artists||'<li class="hint">暂无 artists</li>'}</ul><h4>Ensembles</h4><ul>${ensembles||'<li class="hint">暂无 ensembles</li>'}</ul>`;
        }
        const cast=credits.filter(x=>x.character).map(x=>`<li><span>${esc(x.character)}</span><strong>${person(x)}</strong></li>`).join('');
        const grouped=new Map();
        credits.filter(x=>!x.character&&!ensembleRoles.has(roleKey(x.role))).forEach(x=>{const label=roleLabel(x.role||'Artistic Team');if(!grouped.has(label))grouped.set(label,[]);grouped.get(label).push(x)});
        const team=[...grouped].map(([label,rows])=>`<div class="team-group"><h5>${esc(label)}</h5><ul>${rows.map(x=>`<li>${person(x)}</li>`).join('')}</ul></div>`).join('');
        const ensembles=credits.filter(x=>!x.character&&ensembleRoles.has(roleKey(x.role))).map(x=>`<li>${person(x)}</li>`).join('');
        return `<h4>Cast</h4><ul class="cast-list">${cast||'<li class="hint">暂无 cast</li>'}</ul><h4>Artistic Team</h4>${team||'<div class="hint">暂无 artistic team</div>'}<h4>Ensembles</h4><ul>${ensembles||'<li class="hint">暂无 ensembles</li>'}</ul>`;
      };
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
