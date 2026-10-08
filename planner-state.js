/* One persistent draft shared by the full planner and the embedded planner. */
(function(){
  const key='byelinguaPlannerDraft:v1',listeners=new Set();
  function read(){try{const value=JSON.parse(localStorage.getItem(key)||'{}');return {search:value.search||{},selected:Array.isArray(value.selected)?value.selected:[]}}catch{return {search:{},selected:[]}}}
  function notify(){const value=read();listeners.forEach(listener=>listener(value))}
  window.ByelinguaPlannerState={read,write(patch){const value={...read(),...patch};try{localStorage.setItem(key,JSON.stringify(value))}catch(error){console.warn('Planner draft could not be saved',error.name)}notify()},subscribe(listener){listeners.add(listener);return ()=>listeners.delete(listener)}};
  window.addEventListener('storage',event=>{if(event.key===key)notify()});
})();
