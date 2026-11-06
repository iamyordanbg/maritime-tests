// app/static/js/mobile-header.js
// Phone top bar: after a login the header starts in "intro" (lighthouse only); after a few seconds the
// lighthouse fades out and the brand fades in. Without the intro class nothing happens.
(function () {
    const header = document.querySelector('.mhdr--intro');
    if (header) setTimeout(() => header.classList.remove('mhdr--intro'), 4000);
})();
