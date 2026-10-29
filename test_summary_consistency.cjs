const assert=require('node:assert/strict'),S=require('./schedule-summary-display.js');
for(const [title,work]of[['PARSIFAL','Parsifal'],['Tosca','Tosca'],['Tannhäuser','Tannhäuser']]){
 const event={event_type:'opera',title,summary:{programme:[{title:work,composer:'Recorded composer'}]}};
 for(const lang of ['en','zh']){
  const sections=S.sections(event,lang);assert.equal(sections.length,1);assert.ok(sections[0].lines[0].includes('Recorded composer'));assert.ok(sections[0].lines[0].includes(work));
 }
}
const event={event_type:'concert',summary:{vocalists:[{artist_name:'A',function:'soprano'},{artist_name:'B',function:'alto'},{artist_name:'C',function:'tenor'},{artist_name:'D',function:'bass'}]}};
assert.deepEqual(S.sections(event,'en'),[{label:'Recorded vocalists',lines:['A (soprano)','B (alto)','2 more recorded vocalists']}]);
assert.equal(S.sections(event,'zh')[0].label,'已收录演唱者');
assert.equal(S.sections({summary:{}},'en').length,0);
const html=S.html({summary:{vocalists:[{artist_name:'<script>',function:'tenor'}]}},'en');assert.ok(!html.includes('<script>'));assert.ok(html.includes('&lt;script&gt;'));
console.log('PASS: all-venue same-title opera programme, vocal credits, bilingual text and escaping.');
