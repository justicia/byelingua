(function(){
  if(new URLSearchParams(location.search).has('event_key'))return;
  const home=document.getElementById('reviewHome');
  if(!home)return;
  const section=document.createElement('section');
  section.className='review-search';
  section.innerHTML='<h2 id="reviewSearchTitle"></h2><p id="reviewSearchIntro"></p><form id="reviewSearchForm"><div class="review-search-grid">'+
    '<div class="review-search-field"><label for="reviewDateFrom" data-search-copy="dateFrom"></label><input id="reviewDateFrom" type="date"></div>'+
    '<div class="review-search-field"><label for="reviewDateTo" data-search-copy="dateTo"></label><input id="reviewDateTo" type="date"></div>'+
    '<div class="review-search-field"><label for="reviewEventType" data-search-copy="eventType"></label><select id="reviewEventType"></select></div>'+
    '<div class="review-search-field"><label for="reviewLocation" data-search-copy="location"></label><input id="reviewLocation" autocomplete="off"></div>'+
    '<div class="review-search-field"><label for="reviewOrganization" data-search-copy="organization"></label><select id="reviewOrganization"></select></div>'+
    '<div class="review-search-field"><label for="reviewVenue" data-search-copy="venue"></label><input id="reviewVenue" autocomplete="off"></div>'+
    '<div class="review-search-field"><label for="reviewWork" data-search-copy="work"></label><input id="reviewWork" autocomplete="off"><div id="reviewWorkSuggestions" class="review-search-suggestions"></div></div>'+
    '<div class="review-search-field"><label for="reviewCharacter" data-search-copy="character"></label><input id="reviewCharacter" autocomplete="off"><div id="reviewCharacterSuggestions" class="review-search-suggestions"></div></div>'+
    '<div class="review-search-field"><label for="reviewArtist" data-search-copy="artist"></label><input id="reviewArtist" autocomplete="off"><div id="reviewArtistSuggestions" class="review-search-suggestions"></div></div>'+
    '</div><div class="review-search-actions"><button type="submit" id="reviewSearchButton"></button><span id="reviewSearchStatus" class="review-search-status" role="status"></span></div></form><div id="reviewSearchResults" class="review-search-results" aria-live="polite"></div>';
  home.querySelector('.home-section').before(section);

  const get=id=>document.getElementById(id);
  const names={work:'reviewWork',character:'reviewCharacter',artist:'reviewArtist'};
  const selected={work:null,character:null,artist:null};
  const revisions={work:0,character:0,artist:0};
  const labels={
    zh:{title:'搜索演出',intro:'按日期、地点、作品或艺术家找到一场演出，打开详情后打分。',dateFrom:'开始日期',dateTo:'结束日期',eventType:'演出类型',location:'国家／城市',organization:'机构',venue:'场馆',work:'作品／作曲家',character:'角色',artist:'艺术家',search:'搜索演出',allTypes:'全部类型',allOrganizations:'全部机构',locationPlaceholder:'例如：法国、巴黎',venuePlaceholder:'例如：巴黎歌剧院',workPlaceholder:'例如：Parsifal、Wagner',characterPlaceholder:'例如：Kundry',artistPlaceholder:'例如：Piotr Beczała',searching:'正在搜索…',found:n=>`找到 ${n} 场演出`,limited:'（仅显示前 1000 场）',empty:'没有找到符合条件的演出。',needFilter:'请至少填写一个搜索条件。',more:'显示更多'},
    en:{title:'Find a performance',intro:'Search by date, place, work, or artist. Open a performance to rate it.',dateFrom:'Date from',dateTo:'Date to',eventType:'Event type',location:'Country / city',organization:'Organization',venue:'Venue',work:'Work / composer',character:'Character',artist:'Artist',search:'Search performances',allTypes:'All types',allOrganizations:'All organizations',locationPlaceholder:'e.g. France, Paris',venuePlaceholder:'e.g. Opéra de Paris',workPlaceholder:'e.g. Parsifal, Wagner',characterPlaceholder:'e.g. Kundry',artistPlaceholder:'e.g. Piotr Beczała',searching:'Searching…',found:n=>`Found ${n} performances`,limited:' (first 1000 only)',empty:'No performances match these filters.',needFilter:'Enter at least one search condition.',more:'Show more'}
  };
  const language=()=>window.ByelinguaI18n.getUiLanguage()==='en'?'en':'zh';
  const copy=key=>labels[language()][key];
  const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const api=async payload=>{const response=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw Error(data.error||'Search failed');return data};
  let options={event_types:[],organizations:[]},rows=[],visible=15,searched=false,searchRevision=0;

  function renderLanguage(){
    get('reviewSearchTitle').textContent=copy('title');get('reviewSearchIntro').textContent=copy('intro');
    section.querySelectorAll('[data-search-copy]').forEach(node=>node.textContent=copy(node.dataset.searchCopy));
    get('reviewSearchButton').textContent=copy('search');
    for(const [id,key] of [['reviewLocation','locationPlaceholder'],['reviewVenue','venuePlaceholder'],['reviewWork','workPlaceholder'],['reviewCharacter','characterPlaceholder'],['reviewArtist','artistPlaceholder']])get(id).placeholder=copy(key);
    const typeValue=get('reviewEventType').value,orgValue=get('reviewOrganization').value;
    get('reviewEventType').innerHTML='<option value="">'+copy('allTypes')+'</option>'+options.event_types.map(row=>'<option value="'+escapeHtml(row.value)+'">'+escapeHtml((typeof EVENT_TYPES!=='undefined'&&EVENT_TYPES[language()]?.[row.value])||row.label||row.value)+'</option>').join('');
    get('reviewOrganization').innerHTML='<option value="">'+copy('allOrganizations')+'</option>'+options.organizations.map(row=>'<option value="'+escapeHtml(row.name)+'">'+escapeHtml(row.name)+'</option>').join('');
    get('reviewEventType').value=typeValue;get('reviewOrganization').value=orgValue;
    if(searched)renderResults();
  }

  function renderSuggestions(kind,items){
    const box=get(names[kind]+'Suggestions');box.innerHTML='';
    for(const item of items.slice(0,5)){
      const button=document.createElement('button');button.type='button';
      const detail=kind==='work'?(item.composer||''):kind==='character'?(item.work_title||''):(item.roles||[]).slice(0,2).join(' · ');
      button.innerHTML='<strong>'+escapeHtml(item.label)+'</strong>'+(detail?'<small>'+escapeHtml(detail)+'</small>':'');
      button.onclick=()=>{selected[kind]=item;get(names[kind]).value=item.label||'';box.innerHTML=''};
      box.append(button);
    }
  }

  async function suggest(kind){
    const query=get(names[kind]).value.trim(),revision=++revisions[kind];selected[kind]=null;
    if(query.length<2){renderSuggestions(kind,[]);return}
    try{
      const result=await api({action:'entity_options',query,work_id:selected.work?.type==='work'?selected.work.id:''});
      if(revision!==revisions[kind])return;
      renderSuggestions(kind,kind==='work'?[...(result.composers||[]),...(result.works||[])]:result[kind==='artist'?'artists':'characters']||[]);
    }catch(error){if(revision===revisions[kind])renderSuggestions(kind,[])}
  }
  for(const kind of Object.keys(names)){
    const input=get(names[kind]);let timer;
    input.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>suggest(kind),220)});
    input.addEventListener('focus',()=>{if(input.value.trim().length>=2&&!selected[kind])suggest(kind)});
  }
  document.addEventListener('click',event=>{if(section.contains(event.target)&&event.target.closest('.review-search-field'))return;for(const kind of Object.keys(names))renderSuggestions(kind,[])});

  function payload(){
    const value=id=>get(id).value.trim();
    const query={action:'combined_entity_events',date_from:value('reviewDateFrom'),date_to:value('reviewDateTo'),event_type:value('reviewEventType'),location_query:value('reviewLocation'),venue_query:value('reviewVenue')};
    if(value('reviewOrganization'))query.organizations=[value('reviewOrganization')];
    if(selected.work?.type==='composer')query.composer_query=selected.work.composer;
    else if(selected.work?.id)query.work_id=selected.work.id;
    else if(value('reviewWork'))query.work_query=value('reviewWork');
    if(selected.character?.id)query.character_id=selected.character.id;
    else if(value('reviewCharacter'))query.character_query=value('reviewCharacter');
    if(selected.artist?.id)query.artist_id=selected.artist.id;
    else if(value('reviewArtist'))query.artist_query=value('reviewArtist');
    return query;
  }

  function renderResults(){
    const host=get('reviewSearchResults');if(!searched){host.innerHTML='';return}
    if(!rows.length){host.innerHTML='<div class="home-empty">'+copy('empty')+'</div>';return}
    const cards=rows.slice(0,visible).map(row=>{
      const key=row.event_id||row.event_key||'';
      const place=[row.organization,row.venue,row.city].filter((part,index,array)=>part&&array.indexOf(part)===index).join(' · ');
      return '<a class="home-card" href="/review.html?event_key='+encodeURIComponent(key)+'"><small>'+escapeHtml(row.date||'')+(row.start_time?' · '+escapeHtml(row.start_time.slice(0,5)):'')+'<span class="home-type">'+escapeHtml((typeof EVENT_TYPES!=='undefined'&&EVENT_TYPES[language()]?.[row.event_type])||row.event_type||'')+'</span></small><strong>'+escapeHtml(row.title||'—')+'</strong><span class="home-meta">'+escapeHtml(place)+'</span></a>';
    }).join('');
    host.innerHTML='<div class="home-grid">'+cards+'</div>'+(visible<rows.length?'<button type="button" class="review-search-more">'+copy('more')+'</button>':'');
    host.querySelector('.review-search-more')?.addEventListener('click',()=>{visible+=15;renderResults()});
  }

  get('reviewSearchForm').addEventListener('submit',async event=>{
    event.preventDefault();const query=payload(),status=get('reviewSearchStatus');
    if(Object.keys(query).every(key=>key==='action'||!query[key]||Array.isArray(query[key])&&!query[key].length)){
      status.className='review-search-status error';status.textContent=copy('needFilter');return;
    }
    const revision=++searchRevision;status.className='review-search-status';status.textContent=copy('searching');get('reviewSearchButton').disabled=true;
    for(const kind of Object.keys(names))renderSuggestions(kind,[]);
    try{const result=await api(query);if(revision!==searchRevision)return;rows=result.events||[];visible=15;searched=true;status.textContent=copy('found')(rows.length)+(rows.length>=1000?copy('limited'):'');renderResults()}
    catch(error){if(revision!==searchRevision)return;status.className='review-search-status error';status.textContent=error.message}
    finally{if(revision===searchRevision)get('reviewSearchButton').disabled=false}
  });
  window.addEventListener('byelingua-language-change',renderLanguage);
  renderLanguage();
  api({action:'schedule_options'}).then(data=>{options=data;renderLanguage()}).catch(()=>{});
})();
