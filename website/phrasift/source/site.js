"use strict";
// Decorative, deterministic waveforms. They contain no audio or user information.
document.querySelectorAll("svg.wave").forEach((svg,index)=>{
  const [, ,width,height]=svg.getAttribute("viewBox").split(" ").map(Number);
  const count=width>500?150:width>300?65:35,step=width/count;
  for(let i=0;i<count;i++){
    const envelope=.15+.85*Math.abs(Math.sin(i*.23+index)*Math.cos(i*.067+index));
    const barHeight=Math.max(3,Math.round((height-8)*envelope));
    const rect=document.createElementNS("http://www.w3.org/2000/svg","rect");
    for(const [key,value] of Object.entries({x:i*step,y:(height-barHeight)/2,width:Math.max(1.5,step*.42),height:barHeight,rx:1,fill:"currentColor"}))rect.setAttribute(key,String(value));
    svg.append(rect);
  }
});
const consolePanel=document.querySelector(".demo-console");
const versionButtons=[...document.querySelectorAll("[data-version]")];
const decisionButtons=[...document.querySelectorAll("[data-decision]")];
const status=document.querySelector("#demo-status");
function renderDemo(){
  const clean=versionButtons.some(b=>b.dataset.version==="clean"&&b.getAttribute("aria-pressed")==="true");
  consolePanel.classList.toggle("is-clean",clean);
  let count=0;
  decisionButtons.forEach(button=>{
    const cut=button.getAttribute("aria-pressed")==="true";if(cut)count++;
    const label=button.querySelector(".decision-state");label.textContent=cut?"Cut −":"Keep +";
    const marked=consolePanel.querySelector(`[data-edit="${button.dataset.decision}"]`);marked.classList.toggle("is-cut",cut);
    marked.setAttribute("aria-hidden",String(clean&&cut));
  });
  status.textContent=clean?`Your cut · ${count} example ${count===1?"decision":"decisions"} applied` : "Original · all example sounds are visible";
}
versionButtons.forEach(button=>button.addEventListener("click",()=>{versionButtons.forEach(b=>b.setAttribute("aria-pressed",String(b===button)));renderDemo();}));
decisionButtons.forEach(button=>button.addEventListener("click",()=>{button.setAttribute("aria-pressed",String(button.getAttribute("aria-pressed")!=="true"));renderDemo();}));
renderDemo();
const menu=document.querySelector(".menu-toggle"),nav=document.querySelector("#site-nav");
function setMenu(open){menu.setAttribute("aria-expanded",String(open));nav.classList.toggle("is-open",open);}
menu.addEventListener("click",()=>setMenu(menu.getAttribute("aria-expanded")!=="true"));
nav.querySelectorAll("a").forEach(a=>a.addEventListener("click",()=>setMenu(false)));
document.addEventListener("keydown",event=>{if(event.key==="Escape"&&menu.getAttribute("aria-expanded")==="true"){setMenu(false);menu.focus();}});

// Installation instructions work without guessing an Apple chip from the browser.
const installTabs=[...document.querySelectorAll('[data-install-tab]')];
function selectInstall(platform,focus=false){
  installTabs.forEach(tab=>{
    const selected=tab.dataset.installTab===platform;
    tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;
    document.getElementById(tab.getAttribute('aria-controls')).hidden=!selected;
    if(selected&&focus)tab.focus();
  });
}
installTabs.forEach((tab,index)=>{
  tab.addEventListener('click',()=>selectInstall(tab.dataset.installTab));
  tab.addEventListener('keydown',event=>{
    const next={ArrowRight:(index+1)%installTabs.length,ArrowLeft:(index+installTabs.length-1)%installTabs.length,Home:0,End:installTabs.length-1}[event.key];
    if(next===undefined)return;event.preventDefault();selectInstall(installTabs[next].dataset.installTab,true);
  });
});
const userAgent=navigator.userAgent||'';
const mobile=/Android|iPhone|iPad/i.test(userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
const isWindows=!mobile&&/Windows/i.test(userAgent),isMac=!mobile&&/Macintosh/i.test(userAgent);
if(isMac)selectInstall('mac');
document.getElementById('platform-hint').textContent=isWindows?'You’re on Windows. Choose the Windows installer.':isMac?'You’re on a Mac. Choose Apple Silicon or Intel below.':'Choose your Windows or Mac computer below.';
document.querySelectorAll('[data-platform-card]').forEach(card=>card.classList.toggle('is-recommended',isWindows?card.dataset.platformCard==='windows':isMac&&card.dataset.platformCard.startsWith('mac_')));

