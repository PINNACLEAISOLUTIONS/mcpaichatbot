const BACKEND_URL = "https://miamilovesgreenlandscaping.onrender.com"; // Updated to your live URL

// Helper to determine API Base URL
function getApiBaseUrl() {
    // If running locally (localhost or 127.0.0.1), use local backend
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:8001';
    }
    // Otherwise use relative paths (empty string) for better reliability
    // This allows the browser to automatically use the current origin
    return '';
}
