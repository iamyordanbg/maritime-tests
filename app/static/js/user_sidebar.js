// app/static/js/user_sidebar.js
// User Sidebar (toggle + свързани функции) — извлечена от app/templates/layouts/user_sidebar.html (Правило 1).

function toggleUserSidebar() {
        const sidebar = document.getElementById('userSidebar');
        const isCollapsed = sidebar.getAttribute('data-collapsed') === 'true';
        const newCollapsed = !isCollapsed;
        document.cookie = 'sidebarCollapsed=' + newCollapsed + ';path=/;max-age=31536000';
        localStorage.setItem('sidebarCollapsed', newCollapsed);
        sidebar.setAttribute('data-collapsed', newCollapsed);
        sidebar.style.transition = 'width 0.2s ease';
        applySidebarState(newCollapsed);
        const btn = document.getElementById('sidebarToggleBtn');
        if (btn) btn.style.left = newCollapsed ? '34px' : '132px';
        const icon = document.getElementById('sidebarToggleIcon');
        if (icon) { icon.className = newCollapsed ? 'fa-solid fa-chevron-right text-[9px]' : 'fa-solid fa-chevron-left text-[9px]'; }
    }

    function applySidebarState(collapsed) {
        const sidebar = document.getElementById('userSidebar');
        const labels = sidebar.querySelectorAll('.sidebar-label');
        const icon = document.getElementById('sidebarToggleIcon');
        const menuBtn = document.getElementById('userMenuBtn');
        const logo = document.getElementById('sidebarLogo');
        const title = document.getElementById('sidebarTitle');
        const header = document.getElementById('sidebarHeader');
        const nav = sidebar.querySelector('nav');
        const bottomDiv = sidebar.querySelector('.border-t.border-slate-700\\/30.shrink-0');

        // Всички nav линкове
        const navLinks = sidebar.querySelectorAll('nav a, nav button');

        if (collapsed) {
            // Header
            if (header) { header.style.justifyContent = 'center'; header.style.padding = '0 2px'; }
            // Logo/Title
            if (title) { title.style.transition = 'opacity 0.15s'; title.style.opacity = '0'; setTimeout(() => { title.style.display = 'none'; title.style.opacity = '1'; if (logo) { logo.style.opacity = '0'; logo.style.display = 'block'; logo.style.transition = 'opacity 0.2s'; requestAnimationFrame(() => logo.style.opacity = '1'); } }, 150); }
            // Labels fade out
            labels.forEach(el => { el.style.opacity = '0'; el.style.transition = 'opacity 0.15s'; });
            setTimeout(() => {
                labels.forEach(el => el.style.display = 'none');
                sidebar.style.width = '34px';
                // Nav padding
                if (nav) { nav.style.padding = '8px 2px'; }
                if (bottomDiv) { bottomDiv.style.padding = '8px 2px'; }
                // Nav links — center
                navLinks.forEach(a => { a.style.justifyContent = 'center'; a.style.padding = '9px 0'; a.style.gap = '0'; });
                // Avatar btn — center
                if (menuBtn) { menuBtn.style.justifyContent = 'center'; menuBtn.style.padding = '8px 0'; menuBtn.style.gap = '0'; }
            }, 150);
            if (icon) { icon.classList.remove('fa-chevron-left'); icon.classList.add('fa-chevron-right'); }
        } else {
            // Header
            if (header) { header.style.justifyContent = 'flex-start'; header.style.padding = '0 14px'; }
            // Logo/Title
            if (logo) { logo.style.transition = 'opacity 0.15s'; logo.style.opacity = '0'; setTimeout(() => { logo.style.display = 'none'; logo.style.opacity = '1'; if (title) { title.style.opacity = '0'; title.style.display = 'block'; title.style.transition = 'opacity 0.2s'; requestAnimationFrame(() => title.style.opacity = '1'); } }, 150); }
            // Width first
            sidebar.style.width = '132px';
            if (nav) { nav.style.padding = '8px 3px'; }
            if (bottomDiv) { bottomDiv.style.padding = '8px 3px'; }
            // Nav links — left
            navLinks.forEach(a => { a.style.justifyContent = 'flex-start'; a.style.padding = '9px 5px'; a.style.gap = '8px'; });
            // Avatar btn — left
            if (menuBtn) { menuBtn.style.justifyContent = 'flex-start'; menuBtn.style.padding = '8px 5px'; menuBtn.style.gap = '8px'; }
            if (icon) { icon.classList.remove('fa-chevron-right'); icon.classList.add('fa-chevron-left'); }
            // Labels fade in
            setTimeout(() => {
                labels.forEach(el => { el.style.display = ''; el.style.opacity = '0'; requestAnimationFrame(() => { el.style.transition = 'opacity 0.15s'; el.style.opacity = '1'; }); });
            }, 200);
        }
    }

    function toggleUserMenu(e) {
        e.stopPropagation();
        const popup = document.getElementById('userMenuPopup');
        if (popup.style.display === 'none') {
            // Set email in popup header
            const emailEl = document.getElementById('userPopupEmail');
            if (emailEl) {
                const btn = document.getElementById('userMenuBtn');
                const title = btn ? btn.getAttribute('data-email') : '';
                if (title) emailEl.textContent = title;
            }
            popup.style.display = 'block';
        } else {
            popup.style.display = 'none';
        }
    }

    document.addEventListener('click', e => {
        const btn = document.getElementById('userMenuBtn');
        const popup = document.getElementById('userMenuPopup');
        if (popup && btn && !btn.contains(e.target) && !popup.contains(e.target)) {
            popup.style.display = 'none';
        }
    });

    // Анимиран фар в sidebar логото — синхронизиран с favicon
    (function(){
        var c=document.getElementById('sidebarLogo');
        if(!c||!c.getContext)return;
        var x=c.getContext('2d');
        var W=28,H=28;
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
    })();
    window.addEventListener('pageshow', function() {
        const popup = document.getElementById('userMenuPopup');
        if (popup) popup.style.display = 'none';
    });
