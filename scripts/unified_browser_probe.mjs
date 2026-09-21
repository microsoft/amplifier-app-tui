// Real web frontend + installed Ratatui client, labelled synthetic provider only.
import {spawn} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const {chromium,expect}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const fixture=spawn(process.env.AMPLIFIER_TEST_PYTHON,[fileURLToPath(new URL('../tests/fixtures/unified_browser_server.py',import.meta.url))],{stdio:['ignore','pipe','inherit']});
let browser;
try {
 const url=await new Promise((resolve,reject)=>{
  const timeout=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);let output='';
  fixture.once('exit',code=>{clearTimeout(timeout);reject(Error('Fixture exited '+code))});
  fixture.stdout.on('data',chunk=>{output+=chunk;for(const line of output.split('\n')){try{const value=JSON.parse(line);if(value.url){clearTimeout(timeout);resolve(value.url)}}catch{}}});
 });
 const headers={Authorization:'Bearer fixture-browser-control-token'};
 const inspect=async()=>await(await fetch(url+'/fixture',{headers})).json();
 const post=async(path,body)=>await fetch(url+path,{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify(body||{})});
 const {session}=await inspect();
 browser=await chromium.launch({headless:true});
 const context=await browser.newContext({extraHTTPHeaders:headers});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(url);
 await page.waitForFunction(()=>window.amplifier?.getState()?.client?.id);
 await page.evaluate(id=>window.amplifier.dispatch('session.select',{id}),session);
 const composer=page.getByRole('textbox',{name:'Message Amplifier'});
 await composer.fill('Private browser draft');
 await expect.poll(async()=>(await inspect()).terminal).toContain('UNIFIED');
 await post('/fixture/input',{text:'From installed terminal\r'});
 await expect.poll(async()=>(await inspect()).sent.length).toBe(1);
 await expect(page.getByText('From installed terminal',{exact:true}).first()).toBeVisible();
 await expect(composer).toHaveValue('Private browser draft');
 await post('/fixture/finish');
 await expect.poll(async()=>(await inspect()).terminal).toContain('Finished: From installed terminal');
 await post('/fixture/input',{text:'Private terminal draft'});
 await composer.fill('From web client');
 await page.getByRole('button',{name:'Send message',exact:true}).click();
 await expect.poll(async()=>(await inspect()).sent.length).toBe(2);
 await post('/fixture/finish');
 await expect.poll(async()=>(await inspect()).terminal).toContain('Finished: From web client');
 await expect.poll(async()=>(await inspect()).terminal).toContain('Private terminal draft');
 assert.equal((await inspect()).stopped.length,0);
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({installedTerminalAndWeb:true,sharedInputsAndResults:true,independentDrafts:true,browserErrors:0}));
} finally {
 await browser?.close();
 if(fixture.exitCode === null && fixture.signalCode === null) {
  await new Promise(resolve=>{
   const timeout=setTimeout(()=>fixture.kill('SIGKILL'),10000);
   fixture.once('exit',()=>{clearTimeout(timeout);resolve()});
   fixture.kill('SIGTERM');
  });
 }
}
