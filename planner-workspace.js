/* Presentation and shared draft integration; searches stay in Schedule's controller. */
(function(){
  const embedded=new URLSearchParams(location.search).get('embed')==='1';
  selectionStore.toggleEvent=id=>selectionStore.isSelected(id)?selectionStore.removeEvent(id):selectionStore.addEvent(id);
  const english=()=>window.ByelinguaI18n.getUiLanguage()==='en';
  const label=(zh,en)=>english()?en:zh;
  window.addEventListener('storage',event=>{if(event.key==='byelinguaUiLanguage')location.reload()});
  document.body.classList.add('planner-page');
  if(embedded)document.body.classList.add('planner-embedded');
  const filterPanel=document.getElementById('dateFrom').closest('.panel');
  const entityGrid=document.querySelector('.entity-condition-grid');
  const resultPanel=document.getElementById('events').closest('.panel');
  const sidebar=document.createElement('details');sidebar.className='planner-filters';sidebar.open=innerWidth>760;
  const heading=document.createElement('summary');heading.textContent=label('地点与筛选','Locations & filters');sidebar.append(heading,filterPanel);
  layout.insertBefore(sidebar,leftColumn);leftColumn.classList.add('planner-results');
  // Work, character and artist are filters, so keep them in the filter card.
  // The location search and unchanged calendar remain the first two controls.
  const entityPanel=entityGrid?.closest('.panel')||null;
  const searchButton=document.getElementById('entitySearchButton');
  if(resultPanel)leftColumn.append(resultPanel);
  const openSelected=()=>{rightColumn.classList.remove('schedule-hidden');rightColumn.classList.add('mobile-open');rightColumn.querySelector('[data-close-schedule]')?.focus()};
  mobileTrigger.onclick=openSelected;rightColumn.querySelector('[data-close-schedule]').onclick=()=>{rightColumn.classList.remove('mobile-open','schedule-hidden');mobileTrigger.focus()};
  // Detail is a drawer, so opening it does not squeeze the three workspace columns.
  document.body.append(eventPane);eventPane.setAttribute('role','dialog');eventPane.setAttribute('aria-modal','true');
  const detailBase=showDetail;
  let restoreArtistAfterDetail=false,restoreDetailAfterArtist=false;
  const hideArtist=()=>{artistDrawer.classList.remove('open');artistDrawer.setAttribute('aria-hidden','true')};
  showDetail=async function(id){
    restoreArtistAfterDetail=artistDrawer.classList.contains('open');
    if(restoreArtistAfterDetail)hideArtist();
    restoreDetailAfterArtist=false;
    await detailBase(id);
    if(!embedded){
      const detailEvent=currentDetailEvent(id)||{};
      const feedbackContext={event_id:String(detailEvent.event_id||id||''),event_title:detailEvent.title||detailEvent.work_title||'',event_date:detailEvent.date||'',event_venue:[detailEvent.organization,detailEvent.venue,detailEvent.room].filter(Boolean).join(' · '),source_url:detailEvent.source_url||detailEvent.detail_url||''};
      window.ByelinguaFeedbackContext=feedbackContext;window.ByelinguaFeedback?.setContext(feedbackContext);
      const reportButton=document.createElement('button');reportButton.type='button';reportButton.className='secondary feedback-detail-action';reportButton.textContent=label('报告此演出的问题','Report an issue with this event');reportButton.onclick=()=>window.ByelinguaFeedback?.open(feedbackContext);eventPane.querySelector('[data-persistent-body]')?.append(reportButton);
    }
    layout.classList.remove('has-event-pane');
    eventPane.querySelector('[data-close-persistent]')?.focus();
  };
  const closeDetailButton=eventPane.querySelector('[data-close-persistent]');
  const closeDetailBase=closeDetailButton.onclick;
  closeDetailButton.onclick=event=>{
    closeDetailBase?.call(closeDetailButton,event);
    window.ByelinguaFeedbackContext={};window.ByelinguaFeedback?.clearContext();
    if(restoreArtistAfterDetail){
      restoreArtistAfterDetail=false;
      artistDrawer.classList.add('open');
      artistDrawer.setAttribute('aria-hidden','false');
      artistDrawer.querySelector('.artist-drawer-close')?.focus();
    }
  };
  closeDetailButton.addEventListener('click',()=>document.querySelector(`[data-detail="${CSS.escape(String(activeEventId||''))}"]`)?.focus());
  const openArtistBase=openArtistPanel;
  openArtistPanel=async function(id){
    restoreDetailAfterArtist=!eventPane.hidden;
    if(restoreDetailAfterArtist){eventPane.hidden=true;layout.classList.remove('has-event-pane')}
    restoreArtistAfterDetail=false;
    const result=await openArtistBase(id);
    artistDrawer.querySelector('.artist-drawer-close')?.focus();
    return result;
  };
  const closeArtistButton=artistDrawer.querySelector('.artist-drawer-close');
  const closeArtistBase=closeArtistButton.onclick;
  closeArtistButton.onclick=event=>{
    closeArtistBase?.call(closeArtistButton,event);
    if(restoreDetailAfterArtist&&activeEventId){
      restoreDetailAfterArtist=false;
      eventPane.hidden=false;
      eventPane.querySelector('[data-close-persistent]')?.focus();
    }
  };
  eventPane.addEventListener('click',event=>{
    const addButton=event.target.closest('[data-persistent-toggle]');
    if(!addButton||selectionStore.isSelected(activeEventId))return;
    setTimeout(()=>{if(!eventPane.hidden)closeDetailButton.click()},0);
  },true);
  document.addEventListener('keydown',event=>{if(event.key!=='Escape')return;if(!eventPane.hidden)closeDetailButton.click();else if(rightColumn.classList.contains('mobile-open'))rightColumn.classList.remove('mobile-open');else if(embedded)parent.postMessage({type:'byelingua-close-planner'},location.origin)});
  // Calendar writes only the existing date inputs; all API range semantics are retained.
  const calendar=document.createElement('section');calendar.className='planner-calendar';
  const from=document.getElementById('dateFrom'),to=document.getElementById('dateTo');
  let month=new Date();month.setDate(1);let pickingEnd=false;
  const iso=date=>`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
  function renderCalendar(){
    const first=new Date(month.getFullYear(),month.getMonth(),1),days=new Date(month.getFullYear(),month.getMonth()+1,0).getDate(),offset=(first.getDay()+6)%7;
    calendar.innerHTML=`<div class="calendar-heading"><button type="button" data-month-prev aria-label="${label('上个月','Previous month')}">‹</button><strong>${month.toLocaleDateString(english()?'en-GB':'zh-CN',{month:'long',year:'numeric'})}</strong><button type="button" data-month-next aria-label="${label('下个月','Next month')}">›</button></div><div class="calendar-days">${(english()?['M','T','W','T','F','S','S']:['一','二','三','四','五','六','日']).map(day=>`<span>${day}</span>`).join('')}${'<span></span>'.repeat(offset)}${Array.from({length:days},(_,i)=>{const value=iso(new Date(month.getFullYear(),month.getMonth(),i+1)),edge=value===from.value||value===to.value,inside=from.value&&to.value&&value>=from.value&&value<=to.value;return `<button type="button" data-calendar-date="${value}" class="${edge?'range-edge':inside?'in-range':''}" aria-label="${value}" aria-pressed="${!!(edge||inside)}">${i+1}</button>`}).join('')}</div><p class="hint">${label('依次选择开始与结束日期','Choose a start date, then an end date')}</p><button type="button" class="secondary" data-clear-dates>${label('清除日期','Clear dates')}</button>`;
    calendar.querySelector('[data-month-prev]').onclick=()=>{month.setMonth(month.getMonth()-1);renderCalendar()};calendar.querySelector('[data-month-next]').onclick=()=>{month.setMonth(month.getMonth()+1);renderCalendar()};
    calendar.querySelectorAll('[data-calendar-date]').forEach(button=>button.onclick=()=>{const value=button.dataset.calendarDate;if(!pickingEnd){from.value=value;to.value='';pickingEnd=true}else{if(value<from.value){to.value=from.value;from.value=value}else to.value=value;pickingEnd=false}from.dispatchEvent(new Event('change',{bubbles:true}));to.dispatchEvent(new Event('change',{bubbles:true}));renderCalendar()});
    calendar.querySelector('[data-clear-dates]').onclick=()=>{from.value='';to.value='';pickingEnd=false;from.dispatchEvent(new Event('change',{bubbles:true}));to.dispatchEvent(new Event('change',{bubbles:true}));renderCalendar()};
  }
  const locationField=document.getElementById('locationSearch').closest('.field');
  if(embedded){filterPanel.prepend(locationField);locationField.after(calendar)}else{
    const venueField=document.getElementById('venueSearch').closest('.field');
    const typeField=document.getElementById('eventType').closest('.field');
    const dateFilters=from.closest('.filters');
    const locationGroup=document.createElement('details');locationGroup.className='planner-filter-group planner-location-group';locationGroup.open=true;locationGroup.innerHTML=`<summary>${label('地点','Location')}</summary>`;
    const workGroup=document.createElement('details');workGroup.className='planner-filter-group planner-work-group';workGroup.open=true;workGroup.innerHTML=`<summary>${label('作品','Work')}</summary>`;
    const cityGroup=document.getElementById('cities').parentElement,organizationGroup=document.getElementById('organizations').parentElement,venueGroup=document.getElementById('venues').parentElement;
    locationGroup.append(locationField,venueField,cityGroup,organizationGroup,venueGroup);
    workGroup.append(typeField);if(entityGrid)workGroup.append(entityGrid);
    const filterStatus=document.getElementById('filterStatus'),entityStatus=document.getElementById('entityConditionStatus');
    filterPanel.replaceChildren(calendar,dateFilters,locationGroup,workGroup);if(entityStatus)filterPanel.append(entityStatus);if(filterStatus)filterPanel.append(filterStatus);if(searchButton)filterPanel.append(searchButton);
  }
  renderCalendar();[from,to].forEach(input=>input.addEventListener('change',renderCalendar));
  const generation=document.querySelector('[data-generate-live]'),generateBase=generation.onclick;
  let generating=false;const generationStatus=document.createElement('div');generationStatus.className='status';generationStatus.setAttribute('role','status');rightColumn.querySelector('.my-schedule-footer').after(generationStatus);
  generation.onclick=async event=>{if(!selected_event_ids.size||generating)return;generating=true;generation.disabled=true;generationStatus.textContent=label('正在生成日程…','Creating schedule…');try{await generateBase(event)}finally{generating=false;generation.disabled=generating||!selected_event_ids.size;generationStatus.textContent=''}};
  // Editing an existing server schedule keeps its own membership controller.
  if(!new URLSearchParams(location.search).get('schedule_id')){
    const store=window.ByelinguaPlannerState;
    let applying=false,publishing=false,lastIds=new Set(),selectionSignature=JSON.stringify(store.read().selected),searchSignature=JSON.stringify(store.read().search);
    const fieldIds=['locationSearch','venueSearch','dateFrom','dateTo','eventType','composerCondition','workCondition','characterCondition','artistCondition'];
    function searchSnapshot(){const fields={};fieldIds.forEach(id=>fields[id]=document.getElementById(id)?.value||'');return {fields,conditions:JSON.parse(JSON.stringify(conditionState)),cities:[...selectedCities],organizations:[...selectedOrganizations],venues:[...selectedVenues]}}
    function saveSearch(){if(!applying){updateSelected();const search=searchSnapshot();searchSignature=JSON.stringify(search);store.write({search})}}
    function restoreSearch(search){
      fieldIds.forEach(id=>{const input=document.getElementById(id);if(input)input.value=search.fields?.[id]||''});
      Object.keys(conditionState).forEach(key=>{
        const input=document.getElementById(`${key}Condition`),condition=search.conditions?.[key];
        const savedField=Object.prototype.hasOwnProperty.call(search.fields||{},input.id);
        // Empty saved text is a cleared filter, even if an older draft retained its ID.
        conditionState[key]=condition?.label&&(!savedField||input.value.trim())?condition:null;
        if(conditionState[key]&&!savedField)input.value=condition.label;
        conditionChoices[key]=[];syncConditionChip(key);renderConditionChoices(key);
      });
      window.scheduleSyncLocationSearch?.();
      for(const [set,values] of [[selectedCities,search.cities],[selectedOrganizations,search.organizations],[selectedVenues,search.venues]]){set.clear();(values||[]).forEach(value=>set.add(value))}
      window.scheduleProgressiveRefresh?.();renderCalendar();
    }
    function restoreSelection(rows){selected_event_ids.clear();for(const row of rows){if(!row?.event_id)continue;const id=String(row.event_id);selected_event_ids.add(id);scheduleSeenEvents.set(id,row);if(row.planner_intent)relationByEventKey.set(id,{intent_status:row.planner_intent,is_planned:true})}lastIds=new Set(selected_event_ids)}
    const updateBase=updateSelected;
    updateSelected=function(){updateBase();generation.disabled=generating||!selected_event_ids.size;if(applying||publishing)return;const records=new Map(selectedScheduleRecords().map(row=>[String(row.event_id),row]));const current=store.read().selected;const merged=new Map(current.map(row=>[String(row.event_id),row]));for(const id of lastIds)if(!selected_event_ids.has(id))merged.delete(id);for(const id of selected_event_ids){const row=records.get(String(id));if(row)merged.set(String(id),{...row,planner_intent:eventIntent(id)})}const rows=[...merged.values()];lastIds=new Set(selected_event_ids);if(JSON.stringify(rows)!==JSON.stringify(current)){publishing=true;selectionSignature=JSON.stringify(rows);store.write({selected:rows});publishing=false}};
    const initial=store.read();applying=true;restoreSearch(initial.search);restoreSelection(initial.selected);renderEvents();updateSelected();applying=false;
    document.addEventListener('click',event=>{if(event.target.closest('.selected-chip button'))queueMicrotask(saveSearch)});
    document.addEventListener('input',event=>{if(fieldIds.includes(event.target.id))queueMicrotask(saveSearch)});document.addEventListener('change',event=>{if(event.target.closest('.planner-filters,.planner-entity-panel'))queueMicrotask(saveSearch)});
    const searchBase=runEntitySearch;runEntitySearch=async function(...args){saveSearch();return searchBase(...args)};if(searchButton)searchButton.onclick=()=>runEntitySearch();
    store.subscribe(value=>{const signature=JSON.stringify(value.selected);if(publishing||signature===selectionSignature)return;selectionSignature=signature;applying=true;restoreSelection(value.selected);renderEvents();updateSelected();applying=false});
    window.addEventListener('storage',event=>{if(event.key!=='byelinguaPlannerDraft:v1')return;const search=store.read().search,signature=JSON.stringify(search);if(signature===searchSignature)return;searchSignature=signature;applying=true;restoreSearch(search);void searchBase();applying=false});
    // Refresh only saved selections; preserve live edits made while the lookup is pending.
    async function refreshSavedSelections(){
      const keys=[...new Set(store.read().selected.map(row=>String(row.event_id||'')).filter(Boolean))],resolved=new Map();
      if(!keys.length)return;
      try{
        for(let start=0;start<keys.length;start+=200){
          const result=await api({action:'resolve_event_keys',event_keys:keys.slice(start,start+200)});
          for(const row of result.resolutions||[])if(row?.event?.event_id)resolved.set(String(row.requested_event_id),row.event);
        }
        if(!resolved.size)return;
        const current=store.read().selected,metadata=new Map([...resolved.values()].map(row=>[String(row.event_id),row])),merged=new Map(),rank={interested:1,maybe_go:2,optional:2,must_go:3};
        for(const row of current){
          const fresh=resolved.get(String(row.event_id))||metadata.get(String(row.event_id)),next=fresh?{...row,...fresh}:{...row},key=String(next.event_id);
          const prior=merged.get(key);
          if(prior&&(rank[prior.planner_intent]||0)>(rank[next.planner_intent]||0))next.planner_intent=prior.planner_intent;
          merged.set(key,next);
        }
        const rows=[...merged.values()];if(JSON.stringify(rows)===JSON.stringify(current))return;
        publishing=true;selectionSignature=JSON.stringify(rows);store.write({selected:rows});publishing=false;
        applying=true;restoreSelection(rows);renderEvents();updateSelected();applying=false;
      }catch(_){/* Keep the saved draft usable when metadata cannot be refreshed. */}
    }
    void refreshSavedSelections();
    window.scheduleOptionsPromise?.then(()=>{applying=true;restoreSearch(store.read().search);applying=false;runEntitySearch()});
  }
  if(embedded){
    sidebar.open=true;sidebar.classList.add('embedded-filters');
    const advanced=document.createElement('details');advanced.className='planner-more';advanced.innerHTML=`<summary>${label('更多筛选','More filters')}</summary>`;
    const typeField=document.getElementById('eventType').closest('.field');const basics=document.createElement('section');basics.className='panel embedded-basics';basics.append(locationField,filterPanel.querySelector('.filters'));
    const keyword=document.getElementById('workCondition').closest('.field')||document.getElementById('workCondition').parentElement;basics.append(keyword);
    advanced.append(typeField,calendar);for(const child of [...filterPanel.children])advanced.append(child);
    const extraEntities=document.createElement('div');extraEntities.className='entity-condition-grid';if(entityGrid)while(entityGrid.firstChild)extraEntities.append(entityGrid.firstChild);advanced.append(extraEntities);
    basics.append(advanced);sidebar.replaceChildren(heading,basics);if(searchButton)basics.append(searchButton);if(entityPanel&&entityPanel!==filterPanel)entityPanel.hidden=true;
    const selectedButton=document.createElement('button');selectedButton.className='secondary embedded-selected';selectedButton.textContent=label('已选演出','Selected performances');selectedButton.onclick=openSelected;basics.append(selectedButton);
    window.addEventListener('message',event=>{if(event.origin===location.origin&&event.source===parent&&event.data?.type==='byelingua-show-selected')openSelected()});
  }
  generation.disabled=generating||!selected_event_ids.size;
})();
