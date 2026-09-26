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
    const voiceVisualizerLabel = document.getElementById('voice-visualizer-label');
    const historyList = document.getElementById('history-list');
    const newChatBtn = document.getElementById('new-chat-btn');

    // --- Brand Determination ---
    const activeBrand = (typeof getActiveBrand === 'function') ? getActiveBrand() : 'pinnacle';
    console.log(`Active Chatbot Brand: ${activeBrand}`);

    // --- State Management ---
    let useHDMode = false; // HD = Groq Whisper, STD = Browser Web Speech
    let autoSpeak = false;
    let isSpeaking = false;
    let isRecording = false;
    let voiceModeActive = false;
    let currentSpeakingMsgId = null;
    let speechGen = 0;          // Bumped on stopSpeaking(); drops late TTS audio
    let spokenText = '';        // Current bot utterance for echo rejection
    let speechStartTime = 0;    // Timestamp when speech started (barge-in grace period)
    let silenceTimer = null;
    let mediaStreamTrack = null; // For hardware echo cancellation
    const systemAudio = new Audio();

    // Isolated Session Storage Key per Brand
    const sessionKey = 'chatbot_session_id_' + activeBrand;
    let currentSessionId = localStorage.getItem(sessionKey);
    if (!currentSessionId) {
        currentSessionId = 'sess_' + activeBrand + '_' + Math.random().toString(36).substring(2, 10);
        localStorage.setItem(sessionKey, currentSessionId);
    }

    // API Base URL
    const API_BASE = (typeof getApiBaseUrl === 'function') ? getApiBaseUrl() : '';

    // Mobile viewport height fix
    function setVH() {
        let vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    }
    window.addEventListener('resize', setVH);
    setVH();

    // Unlock Audio for Mobile Safari on first touch
    function unlockAudio() {
        if (!systemAudio.src) {
            systemAudio.src = 'data:audio/mp3;base64,//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq';
            systemAudio.play().catch(() => { });
        }
        if ('speechSynthesis' in window) {
            const u = new SpeechSynthesisUtterance('');
            u.volume = 0;
            window.speechSynthesis.speak(u);
        }
        document.body.removeEventListener('click', unlockAudio);
        document.body.removeEventListener('touchstart', unlockAudio);
    }
    document.body.addEventListener('click', unlockAudio);
    document.body.addEventListener('touchstart', unlockAudio);

    // --- Hardware Echo Cancellation Setup ---
    async function requestHardwareEchoCancellation() {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia && !mediaStreamTrack) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
                });
                mediaStreamTrack = stream.getAudioTracks()[0];
                console.log("Hardware Acoustic Echo Cancellation (AEC) active.");
            } catch (e) {
                console.log("AEC note:", e);
            }
        }
    }

    // --- Interactive Capability Chips ---
    function renderCapabilityChips() {
        const existing = document.getElementById('capability-chips-container');
        if (existing) existing.remove();

        const chipsContainer = document.createElement('div');
        chipsContainer.id = 'capability-chips-container';
        chipsContainer.className = 'capability-chips';

        const pinnacleChips = [
            { label: '📞 AI Phone Receptionist', prompt: 'How does an AI phone receptionist work for my business?' },
            { label: '🤖 Autonomous AI Agents', prompt: 'What kind of autonomous AI workflows and agents can you build?' },
            { label: '🕷️ Stealth Lead Scrapers', prompt: 'Tell me about your Google Maps, Craigslist, and directory scrapers.' },
            { label: '🚀 Auto-Posters', prompt: 'How do your automated social and marketplace auto-posters work?' },
            { label: '🌐 Web Apps & Chatbots', prompt: 'Can you build a high-performance web app with an integrated AI chatbot?' },
            { label: '🎨 Generate AI Concept', prompt: 'Generate a futuristic 3D cyberpunk concept image for an AI agency' },
            { label: '📞 Call (904) 686-6593', prompt: 'I want to schedule a consultation with Pinnacle AI Solutions.' }
        ];

        const miamiChips = [
            { label: '🌴 Landscape Design', prompt: 'What landscape design and 3D visualization services do you offer in Miami?' },
            { label: '🧱 Patios & Hardscaping', prompt: 'Tell me about custom pavers, pergolas, gazebos, and outdoor hardscaping.' },
            { label: '💧 Smart Irrigation', prompt: 'How do smart irrigation systems protect Miami landscapes and save water?' },
            { label: '🌿 Palm & Tree Trimming', prompt: 'What palm care, tree trimming, and hurricane prep services do you provide?' },
            { label: '💡 Outdoor Night Lighting', prompt: 'How does architectural nightscape lighting enhance a luxury yard?' },
            { label: '🚜 Ongoing Maintenance', prompt: 'What are your ongoing garden care, turf, and mulching maintenance plans?' },
            { label: '🎨 Visualize Yard Design', prompt: 'Generate a luxury tropical pool patio design with lush palms and pavers in Miami' },
            { label: '📞 Free Estimate: (786) 570-3215', prompt: 'I would like a free estimate from AZ and the team for my yard.' }
        ];

        const chips = (activeBrand === 'miami') ? miamiChips : pinnacleChips;

        chips.forEach(item => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'chip-btn';
            btn.innerHTML = item.label;
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                userInput.value = item.prompt;
                sendMessage();
            });
            chipsContainer.appendChild(btn);
        });

        // Insert below the first assistant message
        const firstMsg = chatMessages.querySelector('.assistant-message.first');
        if (firstMsg) {
            firstMsg.appendChild(chipsContainer);
        } else {
            chatMessages.appendChild(chipsContainer);
        }
    }
    renderCapabilityChips();

    // --- Visualizer Status Helper ---
    function updateVisualizerState(state, label) {
        if (!voiceVisualizer) return;
        if (!voiceModeActive) {
            voiceVisualizer.classList.add('hidden');
            return;
        }
        voiceVisualizer.classList.remove('hidden');
        if (voiceVisualizerLabel) {
            voiceVisualizerLabel.innerHTML = label || '';
        }
        const bars = voiceVisualizer.querySelector('.v-bars');
        if (bars) {
            bars.className = 'v-bars ' + state;
        }
    }

    // --- Web Speech API (STD Mode) ---
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;

    if (!SpeechRecognition) {
        console.log("SpeechRecognition not supported in browser, forcing HD Mode.");
        useHDMode = true;
        if (hdToggleBtn) {
            hdToggleBtn.textContent = 'HD';
            hdToggleBtn.classList.add('hd-active');
            hdToggleBtn.disabled = true;
        }
    } else {
        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            isRecording = true;
            micBtn.classList.add('recording');
            if (voiceModeActive) {
                if (isSpeaking) {
                    updateVisualizerState('speaking', '<span>🔊 Speaking...</span> <small style="opacity:0.8;">(Tap or say "Stop" to interrupt)</small>');
                } else {
                    updateVisualizerState('listening', '<span>🎙️ Listening...</span> <small style="opacity:0.8;">(Speak now)</small>');
                }
            }
        };

        recognition.onend = () => {
            if (isRecording && !useHDMode) {
                // If silence caused onend and we have captured text, send it
                if (userInput.value.trim() && voiceModeActive && !isSpeaking) {
                    isRecording = false;
                    micBtn.classList.remove('recording');
                    sendMessage();
                    return;
                }
                // Restart recognition to keep session continuous
                setTimeout(() => {
                    try {
                        if (isRecording || (voiceModeActive && !isSpeaking)) {
                            recognition.start();
                        }
                    } catch (e) {
                        isRecording = false;
                        micBtn.classList.remove('recording');
                    }
                }, 200);
            } else if (!isRecording) {
                micBtn.classList.remove('recording');
            }
        };

        recognition.onerror = (event) => {
            console.warn("Speech recognition error:", event.error);
            if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
                isRecording = false;
                micBtn.classList.remove('recording');
                voiceModeActive = false;
                if (voiceModeBtn) voiceModeBtn.classList.remove('active');
                updateVisualizerState('hidden', '');
            }
        };

        // Words that immediately trigger an instant barge-in interruption
        const STOP_KEYWORDS = new Set([
            'stop', 'wait', 'hold', 'pause', 'cancel', 'quiet', 'shh', 'listen',
            'shut up', 'hush', 'hold up', 'excuse me', 'no', 'hey'
        ]);

        recognition.onresult = (event) => {
            let transcript = '';
            for (let i = 0; i < event.results.length; ++i) {
                transcript += event.results[i][0].transcript;
            }
            const cleanTranscript = transcript.trim();
            if (!cleanTranscript) return;

            // --- BARGE-IN INTERRUPTION HANDLING ---
            if (isSpeaking) {
                const now = Date.now();
                // 350ms grace period so audio startup doesn't falsely trip
                if (now - speechStartTime > 350) {
                    const words = cleanTranscript.toLowerCase().split(/\s+/);
                    const hasStopWord = words.some(w => STOP_KEYWORDS.has(w.replace(/[.,!?]/g, '')));

                    // Check if user is asking a substantial new question
                    const botWords = new Set(spokenText.toLowerCase().split(/\s+/));
                    const newWords = words.filter(w => !botWords.has(w));

                    if (hasStopWord || newWords.length >= 2) {
                        console.log("⚡ Voice Barge-In Interruption Detected:", cleanTranscript);
                        stopSpeaking();
                        userInput.value = hasStopWord ? '' : cleanTranscript;
                        updateVisualizerState('listening', '<span>🎙️ Listening...</span> <small style="opacity:0.8;">(Speak now)</small>');
                        return;
                    }
                }
                return; // Ignore echo while speaking
            }

            // Normal transcription while user speaks
            userInput.value = cleanTranscript;
            userInput.dispatchEvent(new Event('input'));
            updateVisualizerState('listening', '<span>🎙️ ' + cleanTranscript.slice(-35) + '</span>');

            // Silence timer: auto-send after 1.6s of silence
            clearTimeout(silenceTimer);
            silenceTimer = setTimeout(() => {
                if (userInput.value.trim() && (voiceModeActive || isRecording) && !isSpeaking) {
                    stopListening();
                    setTimeout(() => {
                        if (userInput.value.trim()) sendMessage();
                    }, 200);
                }
            }, 1600);
        };
    }

    // --- MediaRecorder (HD Mode) ---
    let mediaRecorder = null;
    let audioChunks = [];

    async function startListening(keepSpeaking = false) {
        if (isRecording) return;
        if (!keepSpeaking) stopSpeaking();

        await requestHardwareEchoCancellation();

        if (useHDMode) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
                });
                mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                audioChunks = [];
                mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const formData = new FormData();
                    formData.append('audio', audioBlob, 'recording.webm');
                    micBtn.classList.add('processing');
                    updateVisualizerState('thinking', '<span>⚡ Transcribing HD Audio...</span>');
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
                updateVisualizerState('listening', '<span>🎙️ Listening HD...</span>');
                mediaRecorder.start();
            } catch (err) {
                console.error('Microphone access failed:', err);
                isRecording = false;
            }
        } else if (recognition) {
            try {
                recognition.start();
            } catch (e) {
                if (e.name !== 'InvalidStateError') {
                    console.warn("Recognition start note:", e);
                    isRecording = false;
                }
            }
        }
    }

    function stopListening() {
        isRecording = false;
        if (useHDMode && mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
        } else if (recognition) {
            try { recognition.stop(); } catch (e) { }
        }
        micBtn.classList.remove('recording');
    }

    // --- Stop Speaking (Immediate Cutoff) ---
    function stopSpeaking() {
        speechGen++;
        if (systemAudio && !systemAudio.paused) {
            systemAudio.pause();
            systemAudio.currentTime = 0;
        }
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
        isSpeaking = false;
        spokenText = '';
        if (currentSpeakingMsgId) updateSpeakButton(currentSpeakingMsgId, false);
        currentSpeakingMsgId = null;
    }

    // --- Best Voice Determination ---
    // Pinnacle: Antoni (ElevenLabs) / AndrewNeural (Edge)
    // Miami: Eric (ElevenLabs) / AndrewNeural (Edge)
    function getPreferredVoice() {
        // Returns activeBrand to let backend select flagship ElevenLabs male voice (Adam)
        // or environment variable overrides (ELEVENLABS_VOICE_ID_PINNACLE / ELEVENLABS_VOICE_ID_MIAMI)
        return activeBrand;
    }

    // --- High-Quality TTS (ElevenLabs -> Edge TTS -> Browser Fallback) ---
    async function speakWithElevenLabs(text, msgId) {
        stopSpeaking();
        const gen = ++speechGen;
        speechStartTime = Date.now();
        spokenText = text.replace(/[#*_`~]/g, '').replace(/\[.*?\]\(.*?\)/g, '');

        if (voiceModeActive) {
            updateVisualizerState('speaking', '<span>🔊 Speaking...</span> <small style="opacity:0.8;">(Tap or say "Stop" to interrupt)</small>');
        }

        try {
            const voiceTarget = getPreferredVoice();
            const response = await fetch(`${API_BASE}/api/tts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: spokenText,
                    voice: voiceTarget,
                    brand: activeBrand
                })
            });

            if (gen !== speechGen) return; // Interrupted while loading

            if (response.ok) {
                const data = await response.json();
                if (gen !== speechGen) return;

                if (data.success && data.audio_base64) {
                    const audioBlob = base64ToBlob(data.audio_base64, data.content_type || 'audio/mpeg');
                    systemAudio.src = URL.createObjectURL(audioBlob);
                    isSpeaking = true;
                    currentSpeakingMsgId = msgId;
                    if (msgId) updateSpeakButton(msgId, true);

                    systemAudio.onended = () => {
                        isSpeaking = false;
                        spokenText = '';
                        if (msgId) updateSpeakButton(msgId, false);
                        // Natural conversational loop: open mic for next turn
                        if (voiceModeActive) {
                            setTimeout(() => {
                                if (voiceModeActive && !isSpeaking && !isRecording) {
                                    startListening();
                                }
                            }, 180);
                        }
                    };

                    await systemAudio.play();
                    // Keep mic open for barge-in if in voice mode
                    if (voiceModeActive && !useHDMode && recognition && !isRecording) {
                        try { recognition.start(); } catch (e) { }
                    }
                    return;
                }
            }
            // Fallback to browser speech if API fails
            speakTextBrowser(spokenText, msgId);
        } catch (err) {
            if (gen === speechGen) speakTextBrowser(spokenText, msgId);
        }
    }

    function speakTextBrowser(cleanText, msgId) {
        if (!('speechSynthesis' in window)) return;
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(cleanText);
        const maleVoice = pickMaleBrowserVoice();
        if (maleVoice) utterance.voice = maleVoice;

        utterance.onstart = () => {
            isSpeaking = true;
            speechStartTime = Date.now();
            currentSpeakingMsgId = msgId;
            if (msgId) updateSpeakButton(msgId, true);
            if (voiceModeActive) {
                updateVisualizerState('speaking', '<span>🔊 Speaking...</span> <small style="opacity:0.8;">(Tap or say "Stop" to interrupt)</small>');
                if (!useHDMode && recognition && !isRecording) {
                    try { recognition.start(); } catch (e) { }
                }
            }
        };

        utterance.onend = () => {
            isSpeaking = false;
            spokenText = '';
            if (msgId) updateSpeakButton(msgId, false);
            if (voiceModeActive) {
                setTimeout(() => {
                    if (voiceModeActive && !isSpeaking && !isRecording) {
                        startListening();
                    }
                }, 180);
            }
        };

        utterance.onerror = () => {
            isSpeaking = false;
            spokenText = '';
            if (msgId) updateSpeakButton(msgId, false);
            if (voiceModeActive && !isRecording) startListening();
        };

        window.speechSynthesis.speak(utterance);
    }

    function pickMaleBrowserVoice() {
        const voices = window.speechSynthesis.getVoices().filter(v => v.lang.startsWith('en'));
        const prefs = ['Andrew', 'Brian', 'Christopher', 'Guy', 'Eric', 'Google US English Male', 'Daniel', 'Alex', 'David', 'Mark', 'Male'];
        for (const p of prefs) {
            const v = voices.find(v => v.name.includes(p));
            if (v) return v;
        }
        return null;
    }

    function updateSpeakButton(msgId, speaking) {
        const btn = document.querySelector(`[data-msg-id="${msgId}"] .speak-btn`);
        if (btn) btn.innerHTML = speaking ? getSpeakingIcon() : getSpeakerIcon();
    }

    function getSpeakerIcon() {
        return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>`;
    }

    function getSpeakingIcon() {
        return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>`;
    }

    function base64ToBlob(base64, mimeType) {
        const bytes = atob(base64);
        const arr = new Uint8Array(bytes.length);
        for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
        return new Blob([arr], { type: mimeType });
    }

    // --- Click & Touch Interruption ---
    if (voiceVisualizer) {
        voiceVisualizer.addEventListener('click', (e) => {
            e.preventDefault();
            if (isSpeaking) {
                console.log("Tap on Visualizer interrupted speech.");
                stopSpeaking();
                startListening();
            } else if (isRecording) {
                stopListening();
            } else {
                startListening();
            }
        });
    }

    if (micBtn) {
        micBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (isSpeaking) {
                stopSpeaking();
                startListening();
                return;
            }
            if (isRecording) stopListening();
            else startListening();
        });
    }

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && isSpeaking) {
            stopSpeaking();
            if (voiceModeActive) startListening();
        }
    });

    if (hdToggleBtn) {
        hdToggleBtn.addEventListener('click', () => {
            useHDMode = !useHDMode;
            hdToggleBtn.textContent = useHDMode ? 'HD' : 'STD';
            hdToggleBtn.classList.toggle('hd-active', useHDMode);
        });
    }

    if (autoSpeakToggle) {
        autoSpeakToggle.addEventListener('change', e => {
            autoSpeak = e.target.checked;
        });
    }

    // --- Voice Mode Toggle ---
    if (voiceModeBtn) {
        voiceModeBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            voiceModeActive = !voiceModeActive;
            voiceModeBtn.classList.toggle('active', voiceModeActive);
            autoSpeak = voiceModeActive;
            if (autoSpeakToggle) autoSpeakToggle.checked = autoSpeak;

            console.log(`Voice Mode: ${voiceModeActive ? 'ENABLED' : 'DISABLED'}`);

            if (voiceModeActive) {
                stopSpeaking();
                stopListening();
                await requestHardwareEchoCancellation();
                const greeting = (activeBrand === 'miami')
                    ? "Welcome to Miami Loves Green. Voice mode active. How can I help with your yard?"
                    : "Welcome to Pinnacle AI. Voice mode active. I'm listening.";
                speakWithElevenLabs(greeting, null);
            } else {
                stopSpeaking();
                stopListening();
                updateVisualizerState('hidden', '');
            }
        });
    }

    userInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    sendBtn.addEventListener('click', sendMessage);

    if (newChatBtn) {
        newChatBtn.addEventListener('click', () => {
            stopSpeaking();
            stopListening();
            currentSessionId = 'sess_' + activeBrand + '_' + Math.random().toString(36).substring(2, 10);
            localStorage.setItem(sessionKey, currentSessionId);
            chatMessages.innerHTML = '';

            const greetingHTML = (activeBrand === 'miami')
                ? `<strong>🌴 Welcome to Miami Loves Green!</strong><br><br>I'm your landscaping assistant. Ask me about <strong>landscape design</strong>, <strong>hardscaping</strong>, <strong>irrigation</strong>, <strong>tree care</strong>, <strong>lighting</strong> or <strong>maintenance</strong>.<br><br><em>Want a free estimate? Just ask, or call <a href="tel:+17865703215">(786) 570-3215</a>.</em>`
                : `<strong>🚀 Pinnacle AI Solutions - Expert Systems</strong><br><br>Welcome! I'm here to help you architect <strong>AI Phone Receptionists</strong>, <strong>Autonomous AI Agents</strong>, <strong>Stealth Lead Scrapers</strong>, <strong>Auto-Posters</strong>, and <strong>High-Performance Web Platforms</strong>.<br><br><em>Call us directly at <a href="tel:+19046866593">(904) 686-6593</a> or let's discuss your project!</em>`;

            const firstDiv = document.createElement('div');
            firstDiv.className = 'message assistant-message first';
            firstDiv.innerHTML = `<div class="message-content">${greetingHTML}</div>`;
            chatMessages.appendChild(firstDiv);
            renderCapabilityChips();
        });
    }

    // --- Send Message & Stream ---
    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text || sendBtn.disabled) return;

        stopSpeaking();
        clearTimeout(silenceTimer);
        addUserMessage(text);
        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.disabled = true;

        if (voiceModeActive) {
            updateVisualizerState('thinking', '<span>⚡ Thinking...</span>');
        }

        const loader = showTypingIndicator();

        try {
            const resp = await fetch(`${API_BASE}/api/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    session_id: currentSessionId,
                    brand: activeBrand
                })
            });

            loader.remove();

            if (!resp.ok || !resp.body) {
                // Fallback to non-streaming endpoint
                const fallResp = await fetch(`${API_BASE}/api/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: text,
                        session_id: currentSessionId,
                        brand: activeBrand
                    })
                });
                const fallData = await fallResp.json();
                addAssistantMessage(fallData.response || "No response received.");
                sendBtn.disabled = false;
                if (autoSpeak) speakWithElevenLabs(fallData.response, null);
                return;
            }

            // Stream response
            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let accumulated = '';
            let finalResponse = '';

            const msgId = 'msg_' + Date.now();
            const div = document.createElement('div');
            div.className = 'message assistant-message';
            div.setAttribute('data-msg-id', msgId);
            div.innerHTML = `
                <div class="message-content"></div>
                <div class="message-actions" style="display:none;">
                    <button class="action-btn speak-btn" title="Speak">${getSpeakerIcon()}</button>
                </div>
            `;
            chatMessages.appendChild(div);
            const contentDiv = div.querySelector('.message-content');
            const actionsDiv = div.querySelector('.message-actions');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const payload = JSON.parse(line.slice(6));
                        if (payload.type === 'token') {
                            accumulated += payload.content;
                            contentDiv.innerHTML = marked.parse(accumulated + '<span class="streaming-cursor">▊</span>');
                            scrollToBottom();
                        } else if (payload.type === 'response') {
                            finalResponse = payload.content;
                        } else if (payload.type === 'image') {
                            const imgContainer = document.createElement('div');
                            imgContainer.className = 'generated-image-container';
                            imgContainer.innerHTML = `<img src="${payload.image_url}" class="generated-image" alt="Generated Image" loading="lazy">`;
                            contentDiv.appendChild(imgContainer);
                        } else if (payload.type === 'session') {
                            currentSessionId = payload.session_id;
                            localStorage.setItem(sessionKey, currentSessionId);
                        }
                    } catch (e) { }
                }
            }

            const displayText = finalResponse || accumulated;
            contentDiv.innerHTML = marked.parse(displayText);
            actionsDiv.style.display = '';
            div.querySelector('.speak-btn').addEventListener('click', () => {
                if (isSpeaking && currentSpeakingMsgId === msgId) stopSpeaking();
                else speakWithElevenLabs(displayText, msgId);
            });
            scrollToBottom();

            // Auto-speak in voice mode
            if (autoSpeak) {
                speakWithElevenLabs(displayText, msgId);
            }

        } catch (err) {
            loader.remove();
            addErrorMessage("Connection error. Please try again.");
            if (voiceModeActive) {
                updateVisualizerState('listening', '<span>🎙️ Listening...</span>');
            }
        }
        sendBtn.disabled = false;
    }

    function addUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'message user-message';
        div.innerHTML = `<div class="message-content">${escapeHTML(text)}</div>`;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function addAssistantMessage(text) {
        const div = document.createElement('div');
        div.className = 'message assistant-message';
        div.innerHTML = `<div class="message-content">${marked.parse(text)}</div>`;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function addErrorMessage(text) {
        const div = document.createElement('div');
        div.className = 'message system-message error';
        div.innerHTML = `<div class="message-content">${escapeHTML(text)}</div>`;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function showTypingIndicator() {
        const div = document.createElement('div');
        div.className = 'typing-indicator';
        div.innerHTML = `<span></span><span></span><span></span>`;
        chatMessages.appendChild(div);
        scrollToBottom();
        return div;
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function escapeHTML(str) {
        const p = document.createElement('p');
        p.textContent = str;
        return p.innerHTML;
    }
});
