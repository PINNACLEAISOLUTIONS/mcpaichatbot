const BACKEND_URL = "https://miamilovesgreenlandscaping.onrender.com"; // Updated to your live URL

// Helper to determine API Base URL
function getApiBaseUrl() {
    const hn = window.location.hostname;
    // If running locally or on local network (localhost, 127.0.0.1, 192.168.x.x, 10.x.x.x), use local backend
    if (hn === 'localhost' || hn === '127.0.0.1' || hn.startsWith('192.168.') || hn.startsWith('10.') || hn.startsWith('172.')) {
        return `http://${hn}:8001`; // Use local backend dynamically
    }
    // Otherwise use the production Render URL
    return BACKEND_URL;
}
