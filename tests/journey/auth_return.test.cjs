const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.resolve(__dirname,'../../fe/auth.js'),'utf8');
async function callback(pathname, returnTo) {
    let redirected = null;
    const location = {origin:'https://example.test',hostname:'example.test',protocol:'https:',pathname,search:'?code=test&state=test',hash:'',href:'https://example.test'+pathname+'?code=test&state=test',replace(url){redirected=url;}};
    const sandbox = {URL,console,document:{title:''},window:{location,history:{replaceState(){location.search='';location.href=location.origin+pathname;}}},
        auth0:{async createAuth0Client(){return {async handleRedirectCallback(){return {appState:{returnTo}};}};}}};
    vm.runInNewContext(source,sandbox);await sandbox.initAuth0();return redirected;
}
(async()=>{
    for(const pathname of ['/index.html','/fe/index.html']) {
        const dest=pathname+'#data/portal/chart/gold?period=1y&method=download';
        assert.equal(await callback(pathname,dest),'https://example.test'+dest);
        assert.equal(await callback(pathname,'https://other.test/index.html'),null);
        assert.equal(await callback(pathname,pathname),null);
    }
    console.log('PASS: Auth0 same-path dataset resume and cross-origin rejection.');
})().catch(e=>{console.error(e);process.exitCode=1;});
