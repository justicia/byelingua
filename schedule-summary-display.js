(function(root,factory){const value=factory();if(typeof module==='object'&&module.exports)module.exports=value;else root.ByelinguaScheduleSummary=value})(typeof window==='undefined'?this:window,function(){
 'use strict';
 const copy={en:{conductor:'Conductor',soloists:'Recorded soloists',soloistsPartial:'Soloists (partial)',programme:'Recorded programme',partial:'Programme (partial)',cast:'Principal cast · selection',castDetails:'Cast: see performance details',moreWorks:n=>`${n} more recorded programme items`,moreSoloists:n=>`${n} more recorded soloists`,moreCast:n=>`${n} more principal-role credits`},zh:{conductor:'指挥',soloists:'已收录独奏／独唱',soloistsPartial:'独奏／独唱（信息不完整）',programme:'已收录曲目',partial:'曲目（信息不完整）',cast:'主要阵容 · 节选',castDetails:'阵容见演出详情',moreWorks:n=>`另${n}项已收录曲目`,moreSoloists:n=>`另${n}位已收录独奏／独唱`,moreCast:n=>`另${n}条主要角色出演`}};
 const normalize=v=>String(v||'').normalize('NFKD').replace(/\p{M}/gu,'').toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');
 function sections(event,language){
  const t=copy[language]||copy.en,s=event.summary||{},result=[];
  const people=(s.conductors||[]).map(p=>p.artist_name).filter(Boolean);if(people.length)result.push({label:t.conductor,lines:[people.join(' · ')]});
  const solo=s.soloists||[];if(solo.length)result.push({label:s.soloists_status==='partial'?t.soloistsPartial:t.soloists,lines:[...solo.slice(0,2).map(p=>`${p.artist_name}${p.function?' ('+String(p.function).replace(/_/g,' ')+')':''}`),...(solo.length>2?[t.moreSoloists(solo.length-2)]:[])]});
  const programme=s.programme||[],singleOpera=['opera','operetta'].includes(event.event_type)&&programme.length===1&&normalize(programme[0].title)===normalize(event.title);
  if(programme.length&&!singleOpera)result.push({label:s.programme_status==='partial'?t.partial:t.programme,lines:[...programme.slice(0,3).map(p=>[p.composer,p.title].filter(Boolean).join(' — ')),...(programme.length>3?[t.moreWorks(programme.length-3)]:[])]});
  const cast=s.principal_cast||[];if(cast.length)result.push({label:t.cast,lines:[...cast.slice(0,4).map(p=>`${p.character} — ${p.artist_name}`),...(cast.length>4?[t.moreCast(cast.length-4)]:[])]});
  else if(s.cast_status==='unclassified')result.push({label:'',lines:[t.castDetails]});
  return result;
 }
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function html(event,language){return sections(event,language).map(s=>`<div class="summary-section">${s.label?`<div class="summary-label">${esc(s.label)}</div>`:''}${s.lines.map(line=>`<div>${esc(line)}</div>`).join('')}</div>`).join('')}
 function compareRows(a,b){const x=a.event||{},y=b.event||{};return String(x.date||'9999').localeCompare(String(y.date||'9999'))||String(x.start_time||'99:99').localeCompare(String(y.start_time||'99:99'))}
 function wrap(ctx,text,maxWidth){
  const lines=[];for(const paragraph of String(text||'').split('\n')){let line='';for(const char of paragraph){if(line&&ctx.measureText(line+char).width>maxWidth){lines.push(line);line=char}else line+=char}lines.push(line)}return lines;
 }
 const fonts={title:'600 19px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',meta:'16px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',label:'700 14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'};
 function measureRow(ctx,row,language){
  const event=row.event||{},left=[],right=[];let ly=25,ry=25;
  function add(target,text,font,x,width,lineHeight,y){ctx.font=font;for(const line of wrap(ctx,text,width)){target.push({text:line,font,x,y,color:font===fonts.meta?'#68716b':null});y+=lineHeight}return y}
  ly=add(left,event.title||event.work_title||'Event',fonts.title,200,500,23,ly);
  ly=add(left,[event.venue,event.city||event.location_city].filter(Boolean).join(' · '),fonts.meta,200,500,20,ly);
  for(const section of sections(event,language)){if(section.label)ry=add(right,section.label,fonts.label,750,580,20,ry);for(const line of section.lines)ry=add(right,line,fonts.meta,750,580,20,ry);ry+=8}
  return {row,left,right,height:Math.max(74,ly+10,ry+10)};
 }
 function header(ctx,schedule){ctx.font='700 28px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';const titleLines=wrap(ctx,schedule.title||'Schedule',1260),rangeY=Math.max(150,112+(titleLines.length-1)*32+38);return {titleLines,rangeY,height:Math.max(220,rangeY+70)}}
 function layout(ctx,rows,language,maxHeight=7000,schedule={}){
  const pages=[],head=header(ctx,schedule);let page={blocks:[],height:head.height},y=head.height,lastDate=null;
  function finish(){if(page.blocks.length){page.height=y+28;pages.push(page)}page={blocks:[],height:head.height};y=head.height;lastDate=null}
  for(const row of [...rows].sort(compareRows)){
   const date=String(row.event?.date||'').slice(0,10)||'—',item=measureRow(ctx,row,language);
   if(item.height+head.height+62+28>maxHeight)throw Error('SCHEDULE_IMAGE_ROW_TOO_TALL');
   const daySpace=date!==lastDate?62+(lastDate?28:0):0;
   if(page.blocks.length&&y+daySpace+item.height+28>maxHeight)finish();
   if(date!==lastDate){if(lastDate)y+=28;page.blocks.push({type:'day',date,y});y+=62;lastDate=date}
   page.blocks.push({type:'event',...item,y});y+=item.height;
  }
  finish();return pages;
 }
 function draw(canvas,page,schedule){
  const width=1400,scale=2;canvas.width=width*scale;canvas.height=page.height*scale;const ctx=canvas.getContext('2d');ctx.scale(scale,scale);
  ctx.fillStyle='#f5f2e9';ctx.fillRect(0,0,width,page.height);ctx.fillStyle='#214d3a';ctx.font='700 34px Georgia,serif';ctx.fillText('BYELINGUA',70,65);ctx.fillStyle='#17201b';ctx.font='700 28px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';
  const head=header(ctx,schedule);let titleY=112;for(const line of head.titleLines){ctx.fillText(line,70,titleY);titleY+=32}
  ctx.fillStyle='#68716b';ctx.font='18px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';ctx.fillText(`${schedule.start_date||''} – ${schedule.end_date||''}`,70,head.rangeY);
  for(const block of page.blocks){
   if(block.type==='day'){ctx.fillStyle='#e8eee9';ctx.fillRect(70,block.y,1260,54);ctx.fillStyle='#214d3a';ctx.font='700 21px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';ctx.fillText(block.date,88,block.y+35);continue}
   ctx.fillStyle='#17201b';ctx.font='700 20px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';ctx.fillText(String(block.row.event?.start_time||'').slice(0,5)||'—',82,block.y+25);
   for(const [side,colour] of [[block.left,'#17201b'],[block.right,'#68716b']])for(const line of side){ctx.font=line.font;ctx.fillStyle=line.color||colour;ctx.fillText(line.text,line.x,block.y+line.y)}
   ctx.strokeStyle='#d7d7ce';ctx.beginPath();ctx.moveTo(70,block.y+block.height-8);ctx.lineTo(1330,block.y+block.height-8);ctx.stroke();
  }
  return canvas;
 }
 return {sections,html,compareRows,wrap,measureRow,layout,draw};
});
