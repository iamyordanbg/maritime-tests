// Quota exceeded popup — идва от server-side redirect (?quota_exceeded=1),
// когато потребител се опита да зареди тест/mix/mistakes/simulator, но
// притежаващият grant вече е изчерпал лимита си от тестове.
(function() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('quota_exceeded') === '1') {
        document.getElementById('quotaExceededModal')?.classList.remove('hidden');
        params.delete('quota_exceeded');
        const newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
        window.history.replaceState({}, '', newUrl);
    }
})();
