document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    const micBtn = document.getElementById('mic-btn');
    const hdToggleBtn = document.getElementById('hd-toggle-btn');
    const autoSpeakToggle = document.getElementById('auto-speak-toggle');
    const voiceModeBtn = document.getElementById('voice-mode-btn');
    const voiceVisualizer = document.getElementById('voice-visualizer');
    const historyList = document.getElementById('history-list');
    const newChatBtn = document.getElementById('new-chat-btn');

    // --- State Management ---
    const DEBUG_MOBILE = false;
    let isChatOpen = true;
    let debugMode = false;
    let currentSessionId = localStorage.getItem('chatbot_session_id');
    let useHDMode = false; // HD = Groq Whisper, STD = Browser API
    let autoSpeak = false;
    let isSpeaking = false;
    let currentSpeakingMsgId = null;
    let voiceModeActive = false;
    let currentAudio = null;
    let elevenLabsAvailable = true; // Assume true, fallback handles failures
    let isRecording = false;

    // Get API Base URL
    const API_BASE = (typeof getApiBaseUrl === 'function') ? getApiBaseUrl() : '';

    function setVH() {
        let vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    }
    window.addEventListener('resize', setVH);
    setVH();

    // --- Speech Recognition (STD Mode) ---
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = true;\n        recognition.interimResults = true;\n        recognition.maxAlternatives = 1;
        recognition.lang = 'en-US';
        recognition.interimResults = true;

        recognition.onstart = () => {
            isRecording = true;
            micBtn.classList.add('recording');
            if (voiceVisualizer) voiceVisualizer.classList.remove('hidden');
            stopSpeaking(); // Barge-in
        };

        recognition.onend = () => {
            if (isRecording && !useHDMode) {
                console.log("Recognition ended (normal or timeout). Restarting to keep session alive...");
                // Aggressive restart for Desktop
                setTimeout(() => {
                    try { 
                        if (isRecording) recognition.start(); 
                    } catch(e) { 
                        console.error("Auto-restart failed:", e); 
                        // If it fails, force the UI to reflect state
                        if (!isSpeaking) {
                           isRecording = false;
                           micBtn.classList.remove('recording');
                        }
                    }
                }, 300);
            } else if (!isRecording) {
                micBtn.classList.remove('recording');
                if (voiceVisualizer) voiceVisualizer.classList.add('hidden');
            }
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error:", event.error);
            // Don't kill the session on 'no-speech' or 'audio-capture' errors
            if (event.error === 'no-speech') {
                 console.log("No speech detected. Keeping mic open...");
            }
        };

        recognition.onresult = (event) => {
            // BARGE-IN: Stop speaking immediately if any speech is detected (even interim)
            if (isSpeaking) {
                console.log("Barge-in detected (speech started)");
                stopSpeaking();
            }

            let finalTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                }
            }
            if (finalTranscript) {
                userInput.value = finalTranscript;
                userInput.dispatchEvent(new Event('input'));
                stopListening();
                setTimeout(() => { if (userInput.value.trim()) sendMessage(); }, 400);
            }
        };
    }

    // --- MediaRecorder (HD Mode) ---
    let mediaRecorder = null;
    let audioChunks = [];

    async function startListening() {
        stopSpeaking();
        if (useHDMode) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                audioChunks = [];
                mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const formData = new FormData();
                    formData.append('audio', audioBlob, 'recording.webm');
                    micBtn.classList.add('processing');
                    try {
                        const response = await fetch(`${API_BASE}/api/transcribe`, { method: 'POST', body: formData });
                        const data = await response.json();
                        if (data.success && data.text) {
                            userInput.value = data.text;
                            sendMessage();
                        }
                    } catch (err) { console.error('Transcription error:', err); }
                    micBtn.classList.remove('processing');
                    stream.getTracks().forEach(track => track.stop());
                };
                isRecording = true;
                micBtn.classList.add('recording');
                if (voiceVisualizer) voiceVisualizer.classList.remove('hidden');
                mediaRecorder.start();
            } catch (err) { alert('Microphone access failed.'); }
        } else if (recognition) {
            recognition.start();
        }
    }

    function stopListening() {
        if (useHDMode && mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            isRecording = false;
            micBtn.classList.remove('recording');
            if (voiceVisualizer) voiceVisualizer.classList.add('hidden');
        } else if (recognition) {
            recognition.stop();
        }
    }

    // --- TTS Logic (Premium with Fallback) ---
    async function speakWithElevenLabs(text, msgId) {
        if (!elevenLabsAvailable) { speakTextBrowser(text, msgId); return; }
        try {
            const response = await fetch(`${API_BASE}/api/tts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            });
            if (!response.ok) { speakTextBrowser(text, msgId); return; }
            const data = await response.json();
            if (data.success && data.audio_base64) {
                stopSpeaking();
                const audioBlob = base64ToBlob(data.audio_base64, data.content_type || 'audio/mpeg');
                currentAudio = new Audio(URL.createObjectURL(audioBlob));
                isSpeaking = true;
                currentSpeakingMsgId = msgId;
                updateSpeakButton(msgId, true);
                currentAudio.onended = () => {
                    isSpeaking = false;
                    updateSpeakButton(msgId, false);
                    if (voiceModeActive && !isRecording) startListening();
                };
                await currentAudio.play();
            } else { speakTextBrowser(text, msgId); }
        } catch (err) { speakTextBrowser(text, msgId); }
    }

    function speakTextBrowser(text, msgId) {
        if (!('speechSynthesis' in window)) return;
        window.speechSynthesis.cancel();
        const cleanText = text.replace(/[#*_`~]/g, '').replace(/\[.*?\]\(.*?\)/g, '');
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.onstart = () => { isSpeaking = true; currentSpeakingMsgId = msgId; updateSpeakButton(msgId, true); };
        utterance.onend = () => {
            isSpeaking = false; updateSpeakButton(msgId, false);
            if (voiceModeActive && !isRecording) startListening();
        };
        window.speechSynthesis.speak(utterance);
    }

    function stopSpeaking() {
        if (currentAudio) { currentAudio.pause(); currentAudio = null; }
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        isSpeaking = false;
        if (currentSpeakingMsgId) updateSpeakButton(currentSpeakingMsgId, false);
        currentSpeakingMsgId = null;
    }

    function updateSpeakButton(msgId, speaking) {
        const btn = document.querySelector(`[data-msg-id="${msgId}"] .speak-btn`);
        if (btn) btn.innerHTML = speaking ? getSpeakingIcon() : getSpeakerIcon();
    }

    function getSpeakerIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>`; }
    function getSpeakingIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>`; }

    function base64ToBlob(base64, mimeType) {
        const bytes = atob(base64);
        const arr = new Uint8Array(bytes.length);
        for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
        return new Blob([arr], { type: mimeType });
    }

    // --- Event Handlers ---
    if (micBtn) micBtn.addEventListener('click', () => { if (isRecording) stopListening(); else startListening(); });
    if (hdToggleBtn) hdToggleBtn.addEventListener('click', () => {
        useHDMode = !useHDMode; hdToggleBtn.textContent = useHDMode ? 'HD' : 'STD';
        hdToggleBtn.classList.toggle('hd-active', useHDMode);
    });
    if (autoSpeakToggle) autoSpeakToggle.addEventListener('change', e => { autoSpeak = e.target.checked; });
    let voiceBtnCooldown = false;
    if (voiceModeBtn) voiceModeBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (voiceBtnCooldown) return;

        voiceBtnCooldown = true;
        voiceModeActive = !voiceModeActive;

        // Premium Visual Feedback
        voiceModeBtn.classList.add('working');
        voiceModeBtn.classList.toggle('active', voiceModeActive);
        autoSpeak = voiceModeActive;
        if (autoSpeakToggle) autoSpeakToggle.checked = autoSpeak;

        console.log(`Voice Mode: ${voiceModeActive ? 'Enabling' : 'Disabling'}`);

        try {
            if (voiceModeActive) {
                // Ensure we stop any existing audio first
                stopSpeaking();
                // Activation handshake
                await speakWithElevenLabs("Pinnacle AI Voice Mode active. How can I assist?", null);
            } else {
                stopSpeaking();
                stopListening();
            }
        } catch (err) {
            console.error("Voice Mode Toggle Error:", err);
        } finally {
            setTimeout(() => {
                voiceModeBtn.classList.remove('working');
                voiceBtnCooldown = false;
            }, 800); // 800ms debounce
        }
    });

    userInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    sendBtn.addEventListener('click', sendMessage);
    if (newChatBtn) newChatBtn.addEventListener('click', startNewChat);

    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text || sendBtn.disabled) return;
        addUserMessage(text);
        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.disabled = true;
        const loader = showTypingIndicator();

        try {
            const resp = await fetch(`${API_BASE}/api/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, session_id: currentSessionId })
            });

            loader.remove();

            if (!resp.ok || !resp.body) {
                // Fallback to non-streaming endpoint
                const fallResp = await fetch(`${API_BASE}/api/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, session_id: currentSessionId })
                });
                const rawText = await fallResp.text();
                try {
                    const data = JSON.parse(rawText);
                    if (data.response) {
                        const botText = typeof data.response === 'string' ? data.response : data.response.response;
                        const msgId = addBotMessage(botText, data);
                        if (autoSpeak && msgId) { if (voiceModeActive) speakWithElevenLabs(botText, msgId); else speakTextBrowser(botText, msgId); }
                        if (data.session_id) { currentSessionId = data.session_id; localStorage.setItem('chatbot_session_id', data.session_id); updateHistory(); }
                    }
                } catch (parseErr) {
                    console.error("Failed to parse chat response JSON:", parseErr);
                    console.error("Raw response content:", rawText);
                    addErrorMessage("The server signature was invalid. Please try again.");
                }
                sendBtn.disabled = false;
                return;
            }

            // Create bot message div for streaming
            const msgId = `msg-${++messageIdCounter}`;
            const div = document.createElement('div');
            div.className = 'message assistant-message';
            div.setAttribute('data-msg-id', msgId);
            div.innerHTML = `
                <div class="message-content"><span class="streaming-cursor">▊</span></div>
                <div class="message-actions" style="display:none;">
                    <button class="speak-btn" title="Speak message">${getSpeakerIcon()}</button>
                </div>
            `;
            chatMessages.appendChild(div);
            scrollToBottom();

            const contentDiv = div.querySelector('.message-content');
            const actionsDiv = div.querySelector('.message-actions');
            let accumulated = '';
            let finalResponse = '';

            // Read SSE stream
            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const payload = JSON.parse(line.slice(6));
                        // ... payload processing ...
                    } catch (parseErr) {
                        if (line.trim() !== "data: [DONE]" && !line.startsWith(":")) {
                            console.warn("SSE Parse Error:", parseErr, "Line:", line);
                        }
                    }
                }
            }

            // Finalize message
            const displayText = finalResponse || accumulated;
            contentDiv.innerHTML = marked.parse(displayText);
            actionsDiv.style.display = '';
            div.querySelector('.speak-btn').addEventListener('click', () => {
                if (isSpeaking && currentSpeakingMsgId === msgId) stopSpeaking();
                else if (voiceModeActive) speakWithElevenLabs(displayText, msgId);
                else speakTextBrowser(displayText, msgId);
            });
            scrollToBottom();

            // Auto-speak after stream completes
            if (autoSpeak && msgId) {
                if (voiceModeActive) speakWithElevenLabs(displayText, msgId);
                else speakTextBrowser(displayText, msgId);
            }

        } catch (err) { loader.remove(); addErrorMessage("Connection failed."); }
        sendBtn.disabled = false;
    }

    function addUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'message user-message';
        div.innerHTML = `<div class="message-content">${escapeHTML(text)}</div>`;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    let messageIdCounter = 0;
    function addBotMessage(text, data) {
        const msgId = `msg-${++messageIdCounter}`;
        const div = document.createElement('div');
        div.className = 'message assistant-message';
        div.setAttribute('data-msg-id', msgId);

        let contentHtml = marked.parse(text);
        if (data && data.image_url) {
            contentHtml += `<div class="generated-image-container"><img src="${data.image_url}" class="generated-image" alt="Generated Image" loading="lazy"></div>`;
        }

        div.innerHTML = `
            <div class="message-content">${contentHtml}</div>
            <div class="message-actions">
                <button class="speak-btn" title="Speak message">${getSpeakerIcon()}</button>
            </div>
        `;

        div.querySelector('.speak-btn').addEventListener('click', () => {
            if (isSpeaking && currentSpeakingMsgId === msgId) stopSpeaking();
            else if (voiceModeActive) speakWithElevenLabs(text, msgId);
            else speakTextBrowser(text, msgId);
        });

        chatMessages.appendChild(div);
        scrollToBottom();
        return msgId;
    }

    function showTypingIndicator() {
        const div = document.createElement('div');
        div.className = 'message assistant-message typing';
        div.innerHTML = `<div class="typing-indicator"><span></span><span></span><span></span></div>`;
        chatMessages.appendChild(div);
        scrollToBottom();
        return div;
    }

    function addErrorMessage(text) {
        const div = document.createElement('div');
        div.className = 'message error-message';
        div.innerHTML = `<div class="message-content">⚠️ ${text}</div>`;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function startNewChat() {
        currentSessionId = null;
        localStorage.removeItem('chatbot_session_id');
        chatMessages.innerHTML = '';
        addBotMessage("🚀 **Pinnacle AI Expert Systems**\n\nWelcome! I'm here to help you architect **Elite AI Agents**, **Stealthy Scrapers**, and **Scalable Web Applications**.\n\n*Ready to transform your business with AI? Let's discuss your project!*");
        updateHistory();
    }

    async function updateHistory() {
        if (!historyList) return;
        try {
            const resp = await fetch(`${API_BASE}/api/history/sessions`);
            const sessions = await resp.json();
            historyList.innerHTML = sessions.map(s => `
                <div class="history-item ${s.id === currentSessionId ? 'active' : ''}" onclick="loadSession('${s.id}')">
                    <div class="history-title">${escapeHTML(s.title || 'New Project')}</div>
                    <div class="history-date">${new Date(s.timestamp * 1000).toLocaleDateString()}</div>
                </div>
            `).join('');
        } catch (err) { console.warn('Failed to load history'); }
    }

    window.loadSession = async (id) => {
        currentSessionId = id;
        localStorage.setItem('chatbot_session_id', id);
        chatMessages.innerHTML = '<div class="loader-small"></div>';
        try {
            const resp = await fetch(`${API_BASE}/api/history/${id}`);
            const data = await resp.json();
            chatMessages.innerHTML = '';
            data.messages.forEach(m => {
                if (m.role === 'user') addUserMessage(m.content);
                else addBotMessage(m.content, m.data);
            });
            updateHistory();
        } catch (err) { addErrorMessage("Failed to load session."); }
    };

    function scrollToBottom() { chatMessages.scrollTop = chatMessages.scrollHeight; }
    function escapeHTML(str) { return str.replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m])); }

    updateHistory();
});
