// app/static/js/lighthouse-logo.js
// Animated lighthouse logo (M <-> lighthouse with a rotating beam), shared by every
// <canvas data-lighthouse-logo>: the user sidebar logo and the phone dashboard header.
// Extracted from user_sidebar.js (CLAUDE.md rule 3: no duplicated logic).
function startLighthouseLogo(c){
    if(!c||!c.getContext)return;
    var x=c.getContext('2d');
    var W=28,H=28;
    // data-hidpi: render at device pixel ratio (crisp on phones), drawing coordinates stay 28x28
    var dpr=c.hasAttribute('data-hidpi')?Math.max(1,Math.round(window.devicePixelRatio||1)):1;
    if(dpr>1){c.width=W*dpr;c.height=H*dpr;x.scale(dpr,dpr);}
    var CY=12000,ME=4000,LE=10000,BK=11000,SLIDE=600;
    if(!window._lhStart)window._lhStart=Date.now();
    var S=window._lhStart;

    function drawLH(beamT){
        var cx=W/2,top=4,bot=H-3;
        x.fillStyle='#fff';
        x.beginPath();
        x.moveTo(cx-1.2,top+3);x.lineTo(cx+1.2,top+3);
        x.lineTo(cx+2,bot);x.lineTo(cx-2,bot);
        x.closePath();x.fill();
        x.fillRect(cx-3,bot,6,2);
        x.fillStyle='#0B132B';
        x.fillRect(cx-0.8,top+6,1.6,0.9);
        x.fillRect(cx-0.8,top+9,1.6,0.9);
        x.fillRect(cx-0.8,top+12,1.6,0.9);
        x.fillStyle='#fff';
        x.fillRect(cx-2,top,4,3.5);
        x.beginPath();x.arc(cx,top,2,Math.PI,0);x.fill();
        var cosA=Math.cos(beamT*Math.PI*2),bv=Math.abs(cosA);
        if(bv>0.03){
            var dir=cosA>0?1:-1;
            var len=dir>0?(W-cx-1):(cx-1);
            x.save();x.translate(cx,top);
            var g=x.createLinearGradient(0,0,dir*len,0);
            g.addColorStop(0,'rgba(255,255,255,1)');
            g.addColorStop(0.4,'rgba(255,255,255,'+(bv*0.8)+')');
            g.addColorStop(1,'rgba(255,255,255,0)');
            x.fillStyle=g;
            var sp=bv*6;
            x.beginPath();x.moveTo(0,0);
            x.lineTo(dir*len,-sp);x.lineTo(dir*len,sp);
            x.closePath();x.fill();
            x.fillStyle='rgba(255,255,255,1)';
            x.beginPath();x.arc(0,0,1.8,0,6.28);x.fill();
            x.restore();
        }
    }

    function drawM(ox){
        x.fillStyle='#fff';x.font='bold 22px Georgia,serif';
        x.textAlign='center';x.textBaseline='middle';
        x.fillText('M',W/2+ox,H/2+1);
    }

    function bg(){
        x.clearRect(0,0,W,H);
        x.fillStyle='#0B132B';
        x.beginPath();x.moveTo(4,0);x.lineTo(24,0);
        x.quadraticCurveTo(W,0,W,4);x.lineTo(W,24);
        x.quadraticCurveTo(W,H,24,H);x.lineTo(4,H);
        x.quadraticCurveTo(0,H,0,24);x.lineTo(0,4);
        x.quadraticCurveTo(0,0,4,0);x.closePath();x.fill();
    }

    function fr(){
        if(c.hasAttribute('data-hidpi')&&c.offsetParent===null){requestAnimationFrame(fr);return;}   // hidden (desktop): skip drawing
        var now=Date.now(),t=(now-S)%CY,bt=(now%6000)/6000;
        bg();
        if(t<ME){drawM(0);}
        else if(t<ME+SLIDE){var p=(t-ME)/SLIDE;x.save();x.rect(0,0,W,H);x.clip();drawM(-W*p);x.restore();x.save();x.translate(W*(1-p),0);drawLH(bt);x.restore();}
        else if(t<LE){drawLH(bt);}
        else if(t<BK){var p=(t-LE)/SLIDE;x.save();x.translate(-W*p,0);drawLH(bt);x.restore();x.save();x.translate(W*(1-p),0);drawM(0);x.restore();}
        else{drawM(0);}
        requestAnimationFrame(fr);
    }
    fr();
}

function initLighthouseLogos() {
    document.querySelectorAll('canvas[data-lighthouse-logo]').forEach(startLighthouseLogo);
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initLighthouseLogos);
else initLighthouseLogos();
