(function(){
  'use strict';
  if(new URLSearchParams(location.search).get('embed')==='1')return;
  const copy={
    en:{launcher:'Feedback',title:'Report an issue',context:'About',type:'What went wrong?',choose:'Select a type',incorrect:'Incorrect event information',problem:'Website problem',suggestion:'Suggestion',other:'Other',details:'Details',detailsPlaceholder:'Tell us what happened and what you expected.',email:'Email — optional',emailHint:'Only used if we need to follow up about this report.',privacy:'The current page and relevant event details are included automatically.',cancel:'Cancel',send:'Send report',sending:'Sending…',success:'Thank you — your report has been received.',error:'We could not send your report. Your text has been kept; please try again.',close:'Close feedback'},
    zh:{launcher:'反馈',title:'报告问题',context:'相关内容',type:'问题类型',choose:'请选择类型',incorrect:'演出资料错误',problem:'网站功能故障',suggestion:'建议',other:'其他',details:'具体问题',detailsPlaceholder:'请说明发生了什么，以及你原本期望的结果。',email:'邮箱（选填）',emailHint:'仅在需要进一步确认问题时联系你。',privacy:'当前页面及相关演出信息会自动附在报告中。',cancel:'取消',send:'提交反馈',sending:'正在提交…',success:'谢谢，反馈已经收到。',error:'反馈暂时无法提交。你填写的内容仍然保留，请稍后重试。',close:'关闭反馈'}
  };
  let dialog,form,status,contextBox,launcher,context={};
  const language=()=>window.ByelinguaI18n?.getUiLanguage?.()==='en'||localStorage.getItem('byelinguaUiLanguage')==='en'?'en':'zh';
  const c=key=>copy[language()][key];
  function currentContext(){return {...(window.ByelinguaFeedbackContext||{}),...context}}
  function render(){
    if(!dialog)return;
    launcher.textContent=c('launcher');dialog.querySelector('[data-feedback-title]').textContent=c('title');dialog.querySelector('[data-feedback-close]').setAttribute('aria-label',c('close'));
    const labels={type:'type',details:'details',email:'email'};for(const [name,key] of Object.entries(labels))dialog.querySelector(`[data-feedback-label="${name}"]`).textContent=c(key);
    const options=dialog.querySelectorAll('option');['choose','incorrect','problem','suggestion','other'].forEach((key,index)=>options[index].textContent=c(key));
    dialog.querySelector('[name="message"]').placeholder=c('detailsPlaceholder');dialog.querySelector('[data-feedback-email-hint]').textContent=c('emailHint');dialog.querySelector('[data-feedback-privacy]').textContent=c('privacy');dialog.querySelector('[data-feedback-cancel]').textContent=c('cancel');dialog.querySelector('[data-feedback-submit]').textContent=c('send');
    const value=currentContext();contextBox.hidden=!value.event_title;contextBox.textContent=value.event_title?`${c('context')}: ${[value.event_title,value.event_date,value.event_venue].filter(Boolean).join(' · ')}`:'';
  }
  function setContext(value){context=value&&typeof value==='object'?{...value}:{};render()}
  function open(value){if(value)setContext(value);status.textContent='';status.className='feedback-status';render();dialog.showModal();dialog.querySelector('[name="category"]').focus()}
  function close(){dialog.close()}
  async function submit(event){
    event.preventDefault();if(!form.reportValidity())return;
    const button=dialog.querySelector('[data-feedback-submit]'),value=currentContext(),data=new FormData(form);button.disabled=true;button.textContent=c('sending');status.textContent='';status.className='feedback-status';
    const params=new URLSearchParams(location.search);
    const payload={action:'submit_feedback',category:data.get('category'),message:data.get('message'),email:data.get('email'),website:data.get('website'),page_path:`${location.pathname}${location.search}${location.hash}`,schedule_id:value.schedule_id||params.get('schedule_id')||'',event_id:value.event_id||'',event_title:value.event_title||'',event_date:value.event_date||'',event_venue:value.event_venue||'',source_url:value.source_url||'',language:language()};
    try{
      const response=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),result=await response.json();
      if(!response.ok)throw new Error(result.error||c('error'));
      status.textContent=c('success');status.className='feedback-status success';form.reset();
    }catch(error){status.textContent=error.message||c('error');status.className='feedback-status error'}finally{button.disabled=false;button.textContent=c('send')}
  }
  function mount(){
    if(dialog||document.querySelector('.feedback-dialog'))return;
    launcher=document.createElement('button');launcher.type='button';launcher.className='feedback-launcher';launcher.setAttribute('aria-haspopup','dialog');
    dialog=document.createElement('dialog');dialog.className='feedback-dialog';dialog.innerHTML='<section class="feedback-panel"><div class="feedback-head"><h2 data-feedback-title></h2><button type="button" class="feedback-close" data-feedback-close>×</button></div><p class="feedback-context" data-feedback-context hidden></p><form class="feedback-form"><div class="feedback-field"><label data-feedback-label="type" for="feedbackCategory"></label><select id="feedbackCategory" name="category" required><option value=""></option><option value="incorrect_event"></option><option value="site_problem"></option><option value="suggestion"></option><option value="other"></option></select></div><div class="feedback-field"><label data-feedback-label="details" for="feedbackMessage"></label><textarea id="feedbackMessage" name="message" minlength="10" maxlength="4000" required></textarea></div><div class="feedback-field"><label data-feedback-label="email" for="feedbackEmail"></label><input id="feedbackEmail" name="email" type="email" autocomplete="email" maxlength="254"><p class="feedback-hint" data-feedback-email-hint></p></div><label class="feedback-honeypot" aria-hidden="true">Website<input name="website" tabindex="-1" autocomplete="off"></label><p class="feedback-hint" data-feedback-privacy></p><p class="feedback-status" role="status" aria-live="polite"></p><div class="feedback-actions"><button type="button" class="feedback-cancel" data-feedback-cancel></button><button type="submit" data-feedback-submit></button></div></form></section>';
    form=dialog.querySelector('form');status=dialog.querySelector('.feedback-status');contextBox=dialog.querySelector('[data-feedback-context]');document.body.append(launcher,dialog);
    launcher.onclick=()=>open();dialog.querySelector('[data-feedback-close]').onclick=close;dialog.querySelector('[data-feedback-cancel]').onclick=close;dialog.addEventListener('click',event=>{if(event.target===dialog)close()});form.addEventListener('submit',submit);render();
    window.addEventListener('byelingua-language-change',render);
    document.addEventListener('click',event=>{if(event.target.closest('[data-ui-language],[data-shared-language]'))queueMicrotask(render)},true);
  }
  window.ByelinguaFeedback={mount,open,setContext,clearContext:()=>setContext({})};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
