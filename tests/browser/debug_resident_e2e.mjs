import { chromium } from 'playwright';
const BASE = process.argv[2] || 'http://127.0.0.1:8766';
async function main() {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(BASE + '/examples/page-agent/resident/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const result = await page.evaluate(async () => {
    var turns = [];
    window.PageAgentMockModel.respond = async function(input, init) {
      var body = JSON.parse(init.body);
      var rawMessage = body.messages?.filter(m => m.role === 'user').pop()?.content || '';
      var bsMatch = rawMessage.match(/<browser_state>([\s\S]*?)<\/browser_state>/);
      var browserState = bsMatch ? bsMatch[1] : '';
      
      var hasComplaint = /data-action-target=nav-complaint-category/.test(browserState);
      var hasCivil = /data-action-target=nav-civil-service/.test(browserState);
      var targets = [];
      var lines = browserState.split('\n');
      for (var l of lines) {
        var m = l.match(/data-action-target=([^\s>]+)/);
        if (m) targets.push(m[1]);
      }
      
      turns.push({
        turn: turns.length + 1,
        hasComplaintCategory: hasComplaint,
        hasCivilService: hasCivil,
        targets: targets,
        route: window.CitizenActionDemoCanvas.getCurrentRouteId(),
      });
      
      // Return click on first turn, stop on subsequent
      if (turns.length === 1) {
        // Find nav-civil-service index
        var idxMatch = browserState.match(/\*\[(\d+)\].*?data-action-target=nav-civil-service/);
        var idx = idxMatch ? parseInt(idxMatch[1]) : 6;
        var body = JSON.parse(init.body);
        var macroName = (body.tools && body.tools[0] && body.tools[0].function && body.tools[0].function.name) || 'AgentOutput';
        return new Response(JSON.stringify({choices:[{index:0,message:{role:'assistant',content:null,tool_calls:[{id:'c1',type:'function',function:{name:macroName,arguments:'{"action":{"click_element_by_index":{"index":' + idx + '}}}'}}]},finish_reason:'tool_calls'}]}), {status:200,headers:{'Content-Type':'application/json'}});
      }
      return new Response(JSON.stringify({choices:[{index:0,message:{role:'assistant',content:null,tool_calls:[{id:'c2',type:'function',function:{name:'AgentOutput',arguments:'{"action":{"done":{"success":true,"text":"done"}}}'}}]},finish_reason:'tool_calls'}]}), {status:200,headers:{'Content-Type':'application/json'}});
    };
    
    var inp = document.getElementById('chat-input');
    var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(inp, 'test');
    inp.dispatchEvent(new Event('input', {bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', code:'Enter', bubbles:true, cancelable:true}));
    await new Promise(r => setTimeout(r, 8000));
    return {turns};
  });
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
}
main().catch(e => { console.error(e); process.exit(1); });
