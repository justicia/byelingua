(function(){
  'use strict';
  const dictionaries={
    en:{unknownError:'Something went wrong. Please try again.',permissionDenied:'You do not have permission to access this schedule.',networkError:'Network error. Please check your connection.',events:'events',event:'event',planning:'Planning',confirmed:'Confirmed',completed:'Completed',archived:'Archived',continueEditing:'Continue editing',viewSchedule:'View schedule',downloadIcs:'Download ICS',emailSchedule:'Email this schedule',rename:'Rename',delete:'Delete',archive:'Archive',restore:'Restore',confirm:'Confirm',moveToDraft:'Move back to Drafting',save:'Save',cancel:'Cancel',scheduleTitle:'Schedule title',deleteSchedule:'Delete this schedule? Events and intent data will be kept.',noFilter:'No performances match these filters.',confirming:'Confirming schedule…',changesSaved:'Changes saved. Please confirm the schedule again.'},
    zh:{unknownError:'操作失败，请稍后重试。',permissionDenied:'你没有权限访问此行程。',networkError:'网络错误，请检查连接。',events:'场演出',event:'场演出',planning:'规划中',confirmed:'已确认',completed:'已完成',archived:'已归档',continueEditing:'继续编辑',viewSchedule:'查看行程',downloadIcs:'下载 ICS',emailSchedule:'发送到邮箱',rename:'重命名',delete:'删除',archive:'归档',restore:'恢复',confirm:'确认行程',moveToDraft:'退回规划中',save:'保存',cancel:'取消',scheduleTitle:'行程名称',deleteSchedule:'删除此行程？演出和意向数据将保留。',noFilter:'没有找到符合筛选条件的演出。',confirming:'正在确认行程…',changesSaved:'修改已保存，请重新确认行程。'}
  };
  function valid(value){return value==='en'||value==='zh'?value:null}
  function getUiLanguage(){
    const url=new URL(window.location.href);
    const fromUrl=valid(url.searchParams.get('lang'));
    const preferred=valid(window.__byelinguaPreferredLanguage);
    const stored=valid(localStorage.getItem('byelinguaUiLanguage'));
    return fromUrl||preferred||stored||'zh';
  }
  function setUiLanguage(value){
    const language=valid(value)||'zh', previous=valid(localStorage.getItem('byelinguaUiLanguage'));
    localStorage.setItem('byelinguaUiLanguage',language);
    document.documentElement.lang=language==='en'?'en-GB':'zh-CN';
    if(previous!==language)window.dispatchEvent(new CustomEvent('byelingua-language-change',{detail:language}));
    return language;
  }
  function t(key,vars){
    const language=getUiLanguage(), template=(dictionaries[language]&&dictionaries[language][key])||dictionaries.en[key]||key;
    return String(template).replace(/\{(\w+)\}/g,(_,name)=>vars&&vars[name]!=null?String(vars[name]):'');
  }
  function dateValue(value){
    if(!value)return null;
    const match=String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
    return match?new Date(Number(match[1]),Number(match[2])-1,Number(match[3])):new Date(value);
  }
  function formatDate(value,language){
    const date=dateValue(value); if(!date||Number.isNaN(date.getTime()))return value||'';
    const lang=valid(language)||getUiLanguage();
    return new Intl.DateTimeFormat(lang==='en'?'en-GB':'zh-CN',{year:'numeric',month:'2-digit',day:'2-digit'}).format(date);
  }
  function formatTime(value){
    if(!value)return '';
    const match=String(value).match(/(\d{1,2}):(\d{2})/); return match?`${String(match[1]).padStart(2,'0')}:${match[2]}`:String(value);
  }
  function formatDateRange(start,end,language){
    if(!start&&!end)return '';
    const left=start?formatDate(start,language):''; const right=end?formatDate(end,language):'';
    return left&&right&&left!==right?`${left} – ${right}`:left||right;
  }
  function formatEventCount(count,language){const n=Number(count)||0;return language==='en'?`${n} ${n===1?'event':'events'}`:`${n} 场演出`}
  function formatScheduleStatus(status,language){const lang=valid(language)||getUiLanguage();return dictionaries[lang][status]||status||''}
  function localizeApiError(payload){
    const code=payload&&payload.error_code;
    if(code==='permission_denied')return t('permissionDenied');
    if(code==='network_error')return t('networkError');
    return code&&dictionaries[getUiLanguage()][code]||t('unknownError');
  }
  window.ByelinguaI18n={getUiLanguage,setUiLanguage,t,formatDate,formatTime,formatDateRange,formatEventCount,formatScheduleStatus,localizeApiError};
  document.documentElement.lang=getUiLanguage()==='en'?'en-GB':'zh-CN';
})();
