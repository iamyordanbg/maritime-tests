// app/static/js/news_avatar.js
// The author's avatar in front of a news title - ONE implementation for the dashboard strip, the opened post of the
// dashboard reader, the News Center and the /feed page. Data comes from the API: p.author (name) and p.author_avatar (URL, or '').
// The initial (shown when there is no photo) is drawn by CSS from data-initial, so it never ends up in the title's textContent.
(function () {
    function esc(s) {
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    // HTML of the avatar ('' when the post has no known author).
    window.newsAuthorAvatarHTML = function (p) {
        if (!p || !p.author) return '';
        const img = p.author_avatar
            ? `<img src="${esc(p.author_avatar)}" alt="" data-on-error='[["@style","$this","display","none"]]'>` : '';
        return `<span class="news-avatar" data-initial="${esc(p.author.charAt(0).toUpperCase())}" title="${esc(p.author)}" role="img" aria-label="Published by ${esc(p.author)}">${img}</span>`;
    };

    // Fill a title element: [avatar] title text (the text is set with textContent, so it is always safe).
    window.setNewsTitle = function (el, p) {
        el.textContent = '';
        el.insertAdjacentHTML('afterbegin', window.newsAuthorAvatarHTML(p));
        const text = document.createElement('span');
        text.className = 'news-title-text';
        text.textContent = p.title;
        el.appendChild(text);
        el.classList.toggle('has-news-avatar', !!el.querySelector('.news-avatar'));
    };
})();
