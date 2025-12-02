// API Configuration
// Auto-detects environment and sets appropriate API host

(function() {
  'use strict';
  
  // Determine API host based on environment
  const getApiHost = () => {
    const hostname = window.location.hostname;
    
    // Local development
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '') {
      return 'localhost:8000';
    }
    
    // GitHub Pages (your-username.github.io)
    if (hostname.includes('github.io')) {
      // Replace with your actual backend URL
      return 'aers-api.onrender.com'; // or your Railway/Fly.io URL
    }
    
    // Custom domain or other hosting
    // Default to same hostname but different port/subdomain
    return hostname.replace('www.', 'api.'); // Assumes api.yourdomain.com
  };
  
  // Export to window for use in other scripts
  window.API_CONFIG = {
    host: getApiHost(),
    wsProtocol: window.location.protocol === 'https:' ? 'wss:' : 'ws:',
    httpProtocol: window.location.protocol === 'https:' ? 'https:' : 'http:',
    get wsUrl() {
      return `${this.wsProtocol}//${this.host}/ws/metrics`;
    },
    get apiBase() {
      return `${this.httpProtocol}//${this.host}/api`;
    }
  };
  
  console.log('API Config:', window.API_CONFIG);
})();



