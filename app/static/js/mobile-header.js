// app/static/js/mobile-header.js
// Phone top bar: the lighthouse takes the centre of the header for 6 s (right after a login, then every 10 min);
// afterwards the site name returns to the same spot. The last play time is kept per tab so page changes don't restart it.
function initMobileHeader() {
    const header = document.querySelector('.mhdr');
    if (!header) return;
    const SHOW = 6000, EVERY = 600000, KEY = 'mhdrLastIntro';
    let hideTimer = null;
    const store = {
        get() { try { return +sessionStorage.getItem(KEY) || 0; } catch (e) { return 0; } },
        set(v) { try { sessionStorage.setItem(KEY, String(v)); } catch (e) { /* storage blocked: fine */ } },
    };
    function play(startedAt) {
        header.classList.add('mhdr--intro');
        const logo = header.querySelector('[data-lighthouse-restart]');
        if (logo) logo.dispatchEvent(new CustomEvent('lh-restart', { detail: { elapsed: Date.now() - startedAt } }));
        clearTimeout(hideTimer);
        hideTimer = setTimeout(() => header.classList.remove('mhdr--intro'), Math.max(0, SHOW - (Date.now() - startedAt)));
        store.set(startedAt);
    }
    function schedule() {
        const wait = Math.max(0, store.get() + EVERY - Date.now());
        setTimeout(() => { play(Date.now()); schedule(); }, wait);
    }
    const last = store.get();
    if (header.classList.contains('mhdr--intro')) play(Date.now());                     // fresh login
    else if (last && Date.now() - last < SHOW) play(last);                              // page change during the 6 s
    if (!store.get()) store.set(Date.now());                                            // clock starts now: next play in 10 min
    schedule();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initMobileHeader);
else initMobileHeader();
