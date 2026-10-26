const {chromium:pw}=require(process.env.BONDLAB_PLAYWRIGHT || 'playwright');
const chromium=process.env.BONDLAB_CHROMIUM_MODULE ? require(process.env.BONDLAB_CHROMIUM_MODULE).default : null;
const {spawn}=require('child_process');const fs=require('fs');const crypto=require('crypto');
const path=require('path');const root=path.resolve(__dirname,'..');const port=Number(process.env.BONDLAB_TEST_PORT||18765);
const server=spawn(process.env.BONDLAB_PYTHON||'python',['app.py','--no-browser','--port',String(port)],{cwd:root,stdio:['ignore','pipe','pipe']});
let browser;const errors=[],checks=[];const check=(label,ok)=>{if(!ok)throw Error(label);checks.push(label)};
(async()=>{try{
 for(let i=0;i<100;i++){try{if((await fetch(`http://127.0.0.1:${port}/api/health`)).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
 const options={headless:true};if(chromium){options.executablePath=await chromium.executablePath();options.args=chromium.args;}
 browser=await pw.launch(options);
 const page=await browser.newPage({viewport:{width:1440,height:1080}});page.on('pageerror',e=>errors.push(e.message));
 await page.goto(`http://127.0.0.1:${port}`);await page.waitForFunction(()=>document.querySelector('#bondmetrics').textContent.includes('100.114150'));
 check('Official reopening price displayed',true);check('Dated cash flows displayed',await page.locator('#cashflows tbody tr').count()===21);
 await page.screenshot({path:path.join(require('os').tmpdir(),'bondlab2_desktop.png'),fullPage:true});
 await page.locator('#bondform [name=input_mode]').selectOption('price');await page.locator('#bondform').getByRole('button',{name:'Calculate valuation',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#bondmetrics').textContent.includes('4.235%'));check('Price-to-yield mode works',true);
 await page.locator('#addposition').click();await page.locator('#valueportfolio').click();await page.waitForFunction(()=>document.querySelectorAll('#positions tbody tr').length===1);check('Portfolio valuation works',true);
 await page.getByRole('button',{name:'Bond valuation',exact:true}).click();await page.locator('#bondform [name=face]').fill('2000');await page.locator('#bondform').getByRole('button',{name:'Calculate valuation',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#bondmetrics').textContent.includes('$2,009.56'));await page.locator('#addposition').click();await page.locator('#valueportfolio').click();await page.waitForFunction(()=>document.querySelectorAll('#positions tbody tr').length===2);check('Multiple-position portfolio works',true);
 await page.getByRole('button',{name:'Treasury bills',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#billmetrics').textContent.includes('99.648833'));check('Official bill price displayed',true);
 await page.getByRole('button',{name:'Carry explorer',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('#carrytable tbody tr').length===5);check('Carry explorer works',true);
 await page.getByRole('button',{name:'Strategy research',exact:true}).click();await page.locator('#runback').click();await page.waitForFunction(()=>document.querySelectorAll('#performance tbody tr').length===3);check('Real-data backtest displayed',await page.locator('#sourcelabel').innerText().then(x=>x.includes('191 periods')));check('Trading-cost sensitivity displayed',await page.locator('#costs tbody tr').count()===4);check('Yearly returns displayed',await page.locator('#yearly tbody tr').count()===16);
 let dlPromise=page.waitForEvent('download');await page.locator('#exporttrades').click();const dl=await dlPromise;check('CSV export works',dl.suggestedFilename()==='bondlab_monthly_results.csv');
 await page.screenshot({path:path.join(require('os').tmpdir(),'bondlab2_strategy.png'),fullPage:true});
 await page.getByRole('button',{name:'Validation & history',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('#treasurychecks tbody tr').length===4);check('Validation evidence displayed',true);await page.waitForFunction(()=>document.querySelectorAll('#history tbody tr').length>0);check('Audit history displayed',true);
 await page.getByRole('button',{name:'Bond valuation',exact:true}).click();await page.locator('#preset').selectOption('long');await page.waitForFunction(()=>document.querySelector('#bondmetrics').textContent.includes('93.557438'));check('Long Treasury preset works',true);
 await page.setViewportSize({width:390,height:844});console.log('mobile size',await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,wide:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2).slice(0,8).map(e=>({tag:e.tagName,id:e.id,width:e.getBoundingClientRect().width}))})));await page.screenshot({path:path.join(require('os').tmpdir(),'bondlab2_mobile.png'),fullPage:true});check('Mobile page fits viewport',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(require('os').tmpdir(),'bondlab2_mobile.png'),fullPage:true});
 check('No browser JavaScript errors',errors.length===0);
 const hash=f=>crypto.createHash('sha256').update(fs.readFileSync(root+'/'+f)).digest('hex');
 const out={status:'PASS',generated_utc:new Date().toISOString(),checks,errors,ui_source_sha256:hash('index.html'),app_source_sha256:hash('app.py'),engine_source_sha256:hash('dated_bonds.py'),browser:await browser.version()};fs.writeFileSync(root+'/validation/browser_checks.json',JSON.stringify(out,null,2));console.log(JSON.stringify(out,null,2));
 }finally{if(browser)await browser.close();server.kill('SIGTERM')}})().catch(e=>{console.error(e);process.exitCode=1});
