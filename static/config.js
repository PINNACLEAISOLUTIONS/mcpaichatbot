// Helper to determine API Base URL
function getApiBaseUrl() {
    const hn = window.location.hostname;
    if (hn === 'localhost' || hn === '127.0.0.1' || hn.startsWith('192.168.') || hn.startsWith('10.') || hn.startsWith('172.')) {
        return `http://${hn}:8001`;
    }
    return window.location.origin;
}

// Helper to determine Active Brand from URL or Body class
function getActiveBrand() {
    const urlParams = new URLSearchParams(window.location.search);
    const qb = urlParams.get('brand');
    if (qb) {
        const lower = qb.toLowerCase();
        if (lower.includes('miami') || lower.includes('green') || lower.includes('landscap')) return 'miami';
        return 'pinnacle';
    }
    if (document.body && document.body.classList.contains('brand-miami')) return 'miami';
    return 'pinnacle';
}
