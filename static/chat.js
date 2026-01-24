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

    // --- Mobile Viewport and State Management ---
    const DEBUG_MOBILE = false; // Set to true for debugging
    let isChatOpen = true;
    let debugMode = false;

    // Get API Base URL from config.js or default to relative
    const API_BASE = (typeof getApiBaseUrl === 'function') ? getApiBaseUrl() : '';
    console.log('Chatbot API Base:', API_BASE);

    // --- Voice State ---
    let useHDMode = false; // HD = Groq Whisper, STD = Browser API
    let autoSpeak = false;
    let isSpeaking = false;
    let currentSpeakingMsgId = null;
    let voiceModeActive = false; // Full voice mode with ElevenLabs TTS
    let currentAudio = null; // Current audio element for ElevenLabs playback

    function setVH() {
        let vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
        if (DEBUG_MOBILE) {
            console.log('--- Chatbot Mobile Debug ---');
            console.log('window.innerHeight:', window.innerHeight);
        }
    }

    function lockBodyScroll() {
        if (window.innerWidth < 768) {
            document.body.style.overflow = 'hidden';
            document.body.style.position = 'fixed';
            document.body.style.width = '100%';
            document.body.style.height = '100dvh';
        }
    }

    function unlockBodyScroll() {
        document.body.style.overflow = '';
        document.body.style.position = '';
        document.body.style.width = '';
        document.body.style.height = '';
    }

    window.addEventListener('resize', setVH);
    window.addEventListener('orientationchange', setVH);
    setVH();
    lockBodyScroll();

    // --- Session Persistence ---
    let currentSessionId = localStorage.getItem('chatbot_session_id');

    // --- Speech Recognition Setup (Browser API - STD Mode) ---
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    let isRecording = false;

    // --- MediaRecorder for HD Mode (Groq Whisper) ---
    let mediaRecorder = null;
    let audioChunks = [];

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.lang = 'en-US';
        recognition.interimResults = true;

        recognition.onstart = () => {
            isRecording = true;
            micBtn.classList.add('recording');
        };

        recognition.onend = () => {
            isRecording = false;
            micBtn.classList.remove('recording');
        };

        recognition.onresult = (event) => {
            let finalTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                }
            }

            if (finalTranscript) {
                console.log("STT (STD) Final Result:", finalTranscript);
                userInput.value = finalTranscript;
                userInput.dispatchEvent(new Event('input'));

                // Stop listening before sending to prevent overlapping
                stopListening();

                // Auto-submit
                setTimeout(() => {
                    if (userInput.value.trim().length > 0) {
                        sendMessage();
                    }
                }, 400);
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error', event.error);
            isRecording = false;
            micBtn.classList.remove('recording');

            if (event.error === 'not-allowed') {
                alert("Microphone access denied. Please click the Lock icon in your browser's address bar and allow microphone permissions.");
            } else if (event.error === 'no-speech') {
                console.log("No speech detected.");
            } else if (event.error === 'network') {
                alert("STT requires an internet connection. Please check your network.");
            }
        };
    }

    // --- HD Toggle Button ---
    if (hdToggleBtn) {
        hdToggleBtn.addEventListener('click', () => {
            useHDMode = !useHDMode;
            hdToggleBtn.textContent = useHDMode ? 'HD' : 'STD';
            hdToggleBtn.classList.toggle('hd-active', useHDMode);
            hdToggleBtn.title = useHDMode ? 'HD Mode (Groq Whisper)' : 'Standard Mode (Browser API)';
        });
    }

    // --- Auto-Speak Toggle ---
    if (autoSpeakToggle) {
        autoSpeakToggle.addEventListener('change', (e) => {
            autoSpeak = e.target.checked;
        });
    }

    // --- Microphone Button Handler ---
    if (micBtn) {
        micBtn.addEventListener('click', () => {
            if (isRecording) {
                stopListening();
            } else {
                startListening();
            }
        });
    }

    async function startListening() {
        // Interruption logic: Stop any ongoing speech when user starts talking
        stopSpeakingElevenLabs();
        if ('speechSynthesis' in window) {
            try {
                window.speechSynthesis.cancel();
            } catch (e) { }
        }

        if (useHDMode) {
            // HD Mode: Record audio and send to Groq Whisper
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                audioChunks = [];

                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const formData = new FormData();
                    formData.append('audio', audioBlob, 'recording.webm');

                    micBtn.classList.add('processing');

                    try {
                        const response = await fetch(`${API_BASE}/api/transcribe`, {
                            method: 'POST',
                            body: formData
                        });
                        const data = await response.json();
                        if (data.success && data.text) {
                            userInput.value = data.text;
                            userInput.dispatchEvent(new Event('input'));
                            setTimeout(() => sendMessage(), 100);
                        } else {
                            console.error('Transcription failed:', data.error);
                            addErrorMessage('Transcription failed: ' + (data.error || 'Unknown error'));
                        }
                    } catch (err) {
                        console.error('Transcription error:', err);
                        addErrorMessage('Failed to transcribe audio');
                    }

                    micBtn.classList.remove('processing');
                    stream.getTracks().forEach(track => track.stop());
                };

                isRecording = true;
                micBtn.classList.add('recording');
                mediaRecorder.start();

                // Auto-stop after 30 seconds
                setTimeout(() => {
                    if (mediaRecorder && mediaRecorder.state === 'recording') {
                        stopListening();
                    }
                }, 30000);

            } catch (err) {
                console.error('Microphone error:', err);
                let errorMsg = 'Could not access microphone.';
                if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                    errorMsg = 'Microphone permission denied. Please allow access in your browser settings.';
                } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
                    errorMsg = 'No microphone found. Please check your input device settings.';
                } else if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
                    errorMsg = 'Microphone access requires HTTPS. Please use a secure connection.';
                }

                alert(errorMsg);
                addErrorMessage("Microphone Error: " + errorMsg);
            }
        } else {
            // STD Mode: Use browser Speech Recognition API
            if (recognition) {
                recognition.start();
            } else {
                alert("Your browser does not support Speech-to-Text. Please use Chrome, Edge, or Safari.");
            }
        }
    }

    function stopListening() {
        if (useHDMode && mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            isRecording = false;
            micBtn.classList.remove('recording');
        } else if (recognition) {
            recognition.stop();
        }
    }

    // --- Text-to-Speech Functions ---
    function speakText(text, msgId) {
        console.log('Browser TTS: speakText called with', text.substring(0, 50) + '...');

        if (!('speechSynthesis' in window)) {
            console.warn('Speech synthesis not supported');
            return;
        }

        // Cancel any ongoing speech
        window.speechSynthesis.cancel();

        // Clean text for speech (remove markdown, links, etc.)
        const cleanText = text
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // Remove markdown links
            .replace(/[#*_`~]/g, '') // Remove markdown formatting
            .replace(/<[^>]+>/g, '') // Remove HTML tags
            .replace(/\n+/g, '. '); // Replace newlines with pauses

        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        // Try to use a natural voice
        let voices = window.speechSynthesis.getVoices();

        // Final fallback for Windows PC where voices load slowly
        if (voices.length === 0) {
            setTimeout(() => {
                voices = window.speechSynthesis.getVoices();
            }, 100);
        }

        const preferredVoice = voices.find(v =>
            v.name.includes('Natural') ||
            v.name.includes('Online') ||
            v.name.includes('Google') ||
            v.name.includes('Samantha') ||
            v.name.includes('Microsoft David') ||
            v.name.includes('Microsoft Mark')
        );
        if (preferredVoice) {
            utterance.voice = preferredVoice;
        }

        utterance.onstart = () => {
            isSpeaking = true;
            currentSpeakingMsgId = msgId;
            updateSpeakButton(msgId, true);
        };

        utterance.onend = () => {
            console.log("Browser TTS ended");
            isSpeaking = false;
            currentSpeakingMsgId = null;
            updateSpeakButton(msgId, false);

            // Auto-listen trigger
            if (voiceModeActive && !isRecording) {
                console.log("Auto-listen: Starting mic after browser TTS");
                startListening();
            }
        };

        utterance.onerror = () => {
            isSpeaking = false;
            currentSpeakingMsgId = null;
            updateSpeakButton(msgId, false);
        };

        window.speechSynthesis.speak(utterance);
    }

    function stopSpeaking() {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            isSpeaking = false;
            if (currentSpeakingMsgId) {
                updateSpeakButton(currentSpeakingMsgId, false);
            }
            currentSpeakingMsgId = null;
        }
    }

    function updateSpeakButton(msgId, speaking) {
        const btn = document.querySelector(`[data-msg-id="${msgId}"] .speak-btn`);
        if (btn) {
            btn.classList.toggle('speaking', speaking);
            btn.innerHTML = speaking ? getSpeakingIcon() : getSpeakerIcon();
        }
    }

    function getSpeakerIcon() {
        return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
        </svg>`;
    }

    function getSpeakingIcon() {
        return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2"/>
        </svg>`;
    }

    // Load voices when available
    if ('speechSynthesis' in window) {
        window.speechSynthesis.onvoiceschanged = () => {
            window.speechSynthesis.getVoices();
        };
    }

    // --- Voice Mode Button Handler (ElevenLabs TTS with browser fallback) ---
    let elevenLabsAvailable = false; // Track if ElevenLabs is configured

    if (voiceModeBtn) {
        voiceModeBtn.addEventListener('click', async () => {
            voiceModeActive = !voiceModeActive;
            voiceModeBtn.classList.toggle('active', voiceModeActive);

            // Update button text
            const voiceText = voiceModeBtn.querySelector('.voice-text');
            if (voiceText) {
                voiceText.textContent = voiceModeActive ? 'Voice ON' : 'Voice Mode';
            }

            if (voiceModeActive) {
                // Check if ElevenLabs is available (only once per session)
                try {
                    const statusRes = await fetch(`${API_BASE}/api/status`);
                    const status = await statusRes.json();
                    // WORKAROUND: Force availability for testing per user request
                    elevenLabsAvailable = true;
                    // Original check: 
                    // elevenLabsAvailable = status.voice_agent && status.voice_agent.available;

                    if (elevenLabsAvailable) {
                        console.log('Voice mode: ElevenLabs/Google TTS forced active');
                        voiceModeBtn.querySelector('.voice-text').innerText = 'Voice: Premium';
                        voiceModeBtn.style.boxShadow = '0 0 20px rgba(0, 243, 255, 0.4)';
                    } else {
                        console.log('Voice mode: Using browser TTS (no API keys configured)');
                        voiceModeBtn.querySelector('.voice-text').innerText = 'Voice: Standard';
                    }
                } catch (err) {
                    console.warn('Voice status check failed, using browser TTS');
                    elevenLabsAvailable = false;
                }

                // Enable auto-speak
                autoSpeak = true;

                // Speak short status when voice mode activates (Interruption-friendly)
                speakWithElevenLabs("Voice mode active for Miami Loves Green. Ready for your questions.", null);
            } else {
                // Stop any current playback
                stopSpeakingElevenLabs();
                autoSpeak = false;
            }
        });
    }

    // --- ElevenLabs TTS Functions ---
    async function speakWithElevenLabs(text, msgId) {
        // If no API keys, use browser TTS immediately (saves API calls)
        if (!elevenLabsAvailable) {
            console.log('Using browser TTS (no API keys configured)');
            speakText(text, msgId);
            return;
        }

        try {
            console.log('Calling ElevenLabs TTS API...');
            // Use Direct Voice ID for Josh to prevent mapping errors
            // Use Direct Voice ID for Miami Custom Voice
            const voiceId = "s3TPKV1kjDlVtZbl4Ksh";
            const response = await fetch(`${API_BASE}/api/tts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, voice: voiceId })
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.warn('ElevenLabs TTS failed:', response.status, errorText);

                // If blocked (401 Unusual Activity) or Server Error (500), log but DO NOT permanent disable
                if (response.status === 401 || response.status === 500) {
                    console.error('Premium Voice blocked or failing. Falling back to browser TTS temporarily.');
                    // elevenLabsAvailable = false; // DISABLED: Allow retries
                }

                speakText(text, msgId); // Fallback to browser
                return;
            }

            const data = await response.json();
            console.log('TTS response:', data.success ? 'success' : 'failed', 'provider:', data.provider);

            if (data.success && data.audio_base64) {
                // Stop any current playback
                stopSpeakingElevenLabs();

                // Create audio element and play
                const audioBlob = base64ToBlob(data.audio_base64, data.content_type || 'audio/mpeg');
                const audioUrl = URL.createObjectURL(audioBlob);
                currentAudio = new Audio(audioUrl);

                isSpeaking = true;
                currentSpeakingMsgId = msgId;
                updateSpeakButton(msgId, true);

                currentAudio.onended = () => {
                    console.log("ElevenLabs audio ended");
                    isSpeaking = false;
                    currentSpeakingMsgId = null;
                    updateSpeakButton(msgId, false);
                    URL.revokeObjectURL(audioUrl);

                    // Auto-listen trigger
                    if (voiceModeActive && !isRecording) {
                        console.log("Auto-listen: Starting mic after ElevenLabs TTS");
                        startListening();
                    }
                };

                currentAudio.onerror = (e) => {
                    console.error('Audio playback error:', e);
                    isSpeaking = false;
                    currentSpeakingMsgId = null;
                    updateSpeakButton(msgId, false);
                    // Try browser TTS as last resort
                    speakText(text, msgId);
                };

                await currentAudio.play();
                console.log('Playing audio from', data.provider);
            } else {
                console.warn('TTS returned no audio, using browser TTS');
                speakText(text, msgId);
            }
        } catch (err) {
            console.error('ElevenLabs TTS error:', err);
            speakText(text, msgId); // Fallback
        }
    }

    function stopSpeakingElevenLabs() {
        if (currentAudio) {
            currentAudio.pause();
            currentAudio.currentTime = 0;
            currentAudio = null;
        }
        stopSpeaking(); // Also stop browser TTS
    }

    function base64ToBlob(base64, mimeType) {
        const byteCharacters = atob(base64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        return new Blob([byteArray], { type: mimeType });
    }

    // Auto-resize textarea
    userInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // Send on Enter (Shift+Enter for newline)
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);


    function startNewChat() {
        currentSessionId = null;
        localStorage.removeItem('chatbot_session_id');
        stopSpeaking(); // Stop any ongoing speech

        chatMessages.innerHTML = `
            <div class="message assistant-message first">
                <div class="message-content">
                    <strong>👋 Hello! I'm Miami Loves Green Landscaping Chatbot.</strong><br><br>
                    I'm here to help you with any questions about our landscaping services in Miami. How can I assist you today?
                </div>
            </div>
        `;
    }

    let messageIdCounter = 0;

    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text || sendBtn.disabled) return;

        if (text.toLowerCase() === '/debug') {
            debugMode = !debugMode;
            addErrorMessage(`Debug Mode: ${debugMode ? 'ON' : 'OFF'}`);
            userInput.value = '';
            return;
        }

        addUserMessage(text);
        userInput.value = '';
        userInput.style.height = 'auto';

        sendBtn.disabled = true;
        userInput.disabled = true;
        sendBtn.style.opacity = '0.5';

        const indicator = showTypingIndicator();

        try {
            const response = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    session_id: currentSessionId
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: "Network error or server failed to return JSON." }));
                indicator.remove();
                addErrorMessage(errorData.detail || "Failed to connect to backend.");
                sendBtn.disabled = false;
                userInput.disabled = false;
                sendBtn.style.opacity = '1';
                return;
            }

            const data = await response.json();
            indicator.remove();

            sendBtn.disabled = false;
            userInput.disabled = false;
            sendBtn.style.opacity = '1';

            if (data.response) {
                const botText = typeof data.response === 'string' ? data.response : (data.response.response || JSON.stringify(data.response));
                const msgId = addBotMessage(botText, data);

                // Auto-speak if enabled (use ElevenLabs if voice mode active)
                console.log('Auto-speak check:', { autoSpeak, msgId, voiceModeActive, elevenLabsAvailable });
                if (autoSpeak && msgId) {
                    console.log('Triggering voice for message:', msgId);
                    if (voiceModeActive) {
                        speakWithElevenLabs(botText, msgId);
                    } else {
                        speakText(botText, msgId);
                    }
                }


                if (data.session_id) {
                    currentSessionId = data.session_id;
                    localStorage.setItem('chatbot_session_id', data.session_id);
                }
            } else if (data.detail) {
                addErrorMessage("Error: " + data.detail);
            } else {
                addErrorMessage("Received empty response from server.");
            }
        } catch (error) {
            if (indicator) indicator.remove();
            console.error("Fetch error:", error);
            addErrorMessage("Backend connection failed or timed out.");

            sendBtn.disabled = false;
            userInput.disabled = false;
            sendBtn.style.opacity = '1';
        }
    }


    // Sidebar logic removed

    function addUserMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message user-message';
        msgDiv.innerHTML = `<div class="message-content">${escapeHTML(text)}</div>`;
        chatMessages.appendChild(msgDiv);
        scrollToBottom();
    }

    function addBotMessage(text, fullData = null) {
        const msgId = `msg-${++messageIdCounter}`;
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant-message';
        msgDiv.setAttribute('data-msg-id', msgId);

        // Message header with speak button
        const headerHtml = `
            <div class="message-header">
                <button class="speak-btn" title="Read aloud">${getSpeakerIcon()}</button>
            </div>
        `;

        let contentHtml = `<div class="message-content">${marked.parse(text)}</div>`;

        // Explicit Image Rendering
        if (fullData && (fullData.image_base64 || fullData.image_url)) {
            let imgHtml = '<div class="generated-image-container">';

            if (fullData.image_base64) {
                const mime = fullData.mime_type || 'image/png';
                imgHtml += `<img src="data:${mime};base64,${fullData.image_base64}" class="chat-image" alt="Generated Image">`;
            } else if (fullData.image_url) {
                imgHtml += `<img src="${fullData.image_url}" class="chat-image" alt="Generated Image">`;
                imgHtml += `<a href="${fullData.image_url}" target="_blank" class="fallback-link">🔗 Open Image in New Tab</a>`;
            }

            imgHtml += '</div>';

            if (!contentHtml.includes('<img')) {
                contentHtml += imgHtml;
            }
        }

        if (debugMode && fullData) {
            contentHtml += `<pre class="debug-json">${escapeHTML(JSON.stringify(fullData, null, 2))}</pre>`;
        }

        msgDiv.innerHTML = headerHtml + contentHtml;
        chatMessages.appendChild(msgDiv);

        // Add speak button click handler
        const speakBtn = msgDiv.querySelector('.speak-btn');
        if (speakBtn) {
            speakBtn.addEventListener('click', () => {
                if (isSpeaking && currentSpeakingMsgId === msgId) {
                    stopSpeaking();
                } else {
                    speakWithElevenLabs(text, msgId);
                }
            });
        }

        // Post-process images
        msgDiv.querySelectorAll('img').forEach(img => {
            if (!img.classList.contains('chat-image')) {
                img.classList.add('chat-image');
            }
            img.onerror = function () {
                console.error("Image failed to load:", this.src);
                const fallback = document.createElement('div');
                fallback.className = 'image-error-fallback';
                fallback.innerHTML = `<p>⚠️ Image failed to load</p>`;
                this.replaceWith(fallback);
            };
        });

        scrollToBottom();
        return msgId;
    }

    function addErrorMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant-message error-message';
        msgDiv.style.borderLeft = '4px solid var(--error)';
        msgDiv.innerHTML = `<div class="message-content">${text}</div>`;
        chatMessages.appendChild(msgDiv);
        scrollToBottom();
    }

    function showTypingIndicator() {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant-message typing-indicator-container';
        msgDiv.innerHTML = `
            <div class="typing-indicator">
                <div class="dot"></div>
                <div class="dot"></div>
                <div class="dot"></div>
            </div>
        `;
        chatMessages.appendChild(msgDiv);
        scrollToBottom();
        return msgDiv;
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function escapeHTML(str) {
        if (!str) return '';
        return str.replace(/[&<>"']/g, function (m) {
            return {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            }[m];
        });
    }


    async function init() {
        if (currentSessionId) {
            loadSessionContent(currentSessionId);
        }
    }

    async function loadSessionContent(sessionId) {
        try {
            const res = await fetch(`${API_BASE}/api/chat/${sessionId}`);
            const data = await res.json();

            chatMessages.innerHTML = '';

            if (data.history) {
                data.history.forEach(msg => {
                    if (msg.role === 'user') addUserMessage(msg.content);
                    else if (msg.role === 'assistant') {
                        if (msg.content) addBotMessage(msg.content);
                    }
                });
            }
            scrollToBottom();
        } catch (e) {
            console.error("Load session error:", e);
        }
    }

    init();
});
