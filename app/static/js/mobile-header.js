// app/static/js/mobile-header.js
// Phone top bar: the centre of the header alternates between the animated logo (M -> lighthouse) and the site name,
// each shown for SHOW ms. After a login the page starts with the animation, otherwise with the name.
function initMobileHeader() {
    const header = document.querySelector('.mhdr');
    if (!header) return;
    const SHOW = 6000;
    const logo = header.querySelector('[data-lighthouse-restart]');
    function showLogo(on) {
        header.classList.toggle('mhdr--intro', on);
        if (on && logo) logo.dispatchEvent(new CustomEvent('lh-restart', { detail: { elapsed: 0 } }));
    }
    showLogo(header.classList.contains('mhdr--intro'));
    setInterval(() => showLogo(!header.classList.contains('mhdr--intro')), SHOW);
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initMobileHeader);
else initMobileHeader();
