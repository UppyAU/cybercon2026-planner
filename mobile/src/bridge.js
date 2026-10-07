// JavaScript the app runs inside the planner page after each load.
//
// App-only CSS: the WebView is edge to edge, so a strip the height of the status bar keeps scrolled
// content out from under the clock (above the header, z 30, below the page's overlays, z 45+), and the
// sticky filter bar stops below it. Print does nothing in a WebView.
const APP_CSS = '#cc26-sb{position:fixed;top:0;left:0;right:0;height:env(safe-area-inset-top);background:var(--bg);z-index:41;pointer-events:none}'
  + '#mbar{top:env(safe-area-inset-top)!important}[data-act="print"]{display:none!important}';
//
// The planner's own nativeSync() (src/planner.html) posts the plan whenever it changes. A copy of
// the site deployed before that hook existed doesn't have it, so this adds the same thing from
// outside: the page's top-level names (goList, DAYS, PV, remindMin, walkMin, download) are globals
// to a script injected into the same window. It also reports the page background so the status
// bar and safe-area padding match, and asks for a fresh sync (on start and when the app returns
// to the foreground, e.g. after the exact-alarm setting changed).
export const PAGE_SCRIPT = `(function(){
  var post=function(o){try{window.ReactNativeWebView.postMessage(JSON.stringify(o))}catch(e){}};
  if(!window.__cc26App){
    window.__cc26App=true;
    var st=document.createElement("style");st.textContent=${JSON.stringify(APP_CSS)};document.head.appendChild(st);
    var sb=document.createElement("div");sb.id="cc26-sb";document.body.appendChild(sb);
    if(typeof nativeSync!=="function"&&typeof goList==="function"){
      window.nativeSync=function(){
        if(PV)return;
        try{
          var gl=goList(),at=function(x,m){return Date.UTC(2026,9,DAYS[x.dayIdx].d,0,m-660)};
          var sessions=gl.map(function(x){
            var prev=gl.filter(function(y){return y.dayIdx===x.dayIdx&&y.f<=x.s&&x.s-y.f<=30}).sort(function(a,b){return a.f-b.f}).pop();
            var from=prev&&prev.location!==x.location?prev.location:null;
            return {id:x.id,title:x.title,loc:x.location,start:at(x,x.s),end:at(x,x.f),from:from,walk:from?walkMin(from,x.location):null};
          });
          post({type:"cc26-plan",v:1,remind:remindMin,sessions:sessions});
        }catch(e){}
      };
      var set=Storage.prototype.setItem;
      Storage.prototype.setItem=function(k,v){set.call(this,k,v);if(k==="cybercon2026-plan-v1"||k==="cybercon2026-remind-v1")setTimeout(window.nativeSync,0)};
      window.download=function(name,type,text){post({type:"cc26-file",name:name,mime:type,text:text})};
    }
    // Receive from another device: let the app offer its QR scanner as well as pasting the link
    // (capture phase, so the page's own prompt() never opens; previewing a shared plan still blocks it).
    if(typeof xferReceive==="function")document.addEventListener("click",function(e){
      var t=e.target.closest&&e.target.closest('[data-act="xrecv"]');if(!t||(typeof PV!=="undefined"&&PV))return;
      e.stopImmediatePropagation();e.preventDefault();
      document.querySelectorAll("details.more[open]").forEach(function(d){d.open=false});
      post({type:"cc26-receive"});
    },true);
    var bg=function(){post({type:"cc26-theme",bg:getComputedStyle(document.body).backgroundColor})};
    bg();try{matchMedia("(prefers-color-scheme: dark)").addEventListener("change",bg)}catch(e){}
  }
  if(typeof nativeSync==="function")nativeSync();
})();true;`;

// Hands a transfer link (scanned or pasted in the app) to the page's own Receive flow, which shows what
// would change and waits for "Use it on this device".
export const receiveLink = link => `(function(){if(typeof xferReceive==="function")xferReceive(${JSON.stringify(String(link))})})();true;`;
export const PASTE_LINK = `(function(){var v=prompt("Paste the transfer link from your other device:");if(v&&typeof xferReceive==="function")xferReceive(v)})();true;`;

// Opens the Now tab, e.g. after tapping a reminder.
export const SHOW_NOW = `(function(){var t=document.getElementById("tabNow");if(t)t.click();window.scrollTo(0,0)})();true;`;
