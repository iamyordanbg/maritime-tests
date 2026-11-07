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
        if (popup.classList.contains('hidden')) {
            // Set email in popup header
            const emailEl = document.getElementById('userPopupEmail');
            if (emailEl) {
                const btn = document.getElementById('userMenuBtn');
                const title = btn ? btn.getAttribute('data-email') : '';
                if (title) emailEl.textContent = title;
            }
            popup.classList.remove('hidden');
        } else {
            popup.classList.add('hidden');
        }
    }

    document.addEventListener('click', e => {
        const btn = document.getElementById('userMenuBtn');
        const popup = document.getElementById('userMenuPopup');
        if (popup && btn && !btn.contains(e.target) && !popup.contains(e.target)) {
            popup.classList.add('hidden');
        }
    });

    // Animated lighthouse logo (sidebar + phone header): js/lighthouse-logo.js
    window.addEventListener('pageshow', function() {
        const popup = document.getElementById('userMenuPopup');
        if (popup) popup.classList.add('hidden');
    });


// Support ticket body character counter (data-on-input in user_sidebar.html).
function updateTicketBodyCount(textarea) {
    var counter = document.getElementById('ticketBodyCount');
    if (counter) counter.textContent = textarea.value.length + '/500';
}
