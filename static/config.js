const BACKEND_URL = "https://miamilovesgreenlandscaping.onrender.com"; // Updated to your live URL

// Helper to determine API Base URL
function getApiBaseUrl() {
    // If running locally (localhost or 127.0.0.1), use local backend
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:8001';
    }
    // Otherwise use the production Render URL
    return BACKEND_URL;
}
