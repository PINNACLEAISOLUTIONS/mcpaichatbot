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
    let useHDMode = false;
    let autoSpeak = false;
    let isSpeaking = false;
    let isRecording = false;
    let voiceModeActive = false;
    let currentSpeakingMsgId = null;
    let speechGen = 0;          // Bumped on stopSpeaking(); drops late TTS audio
    let silenceTimer = null;
    const systemAudio = new Audio();

    // Isolated Session Storage Key per Brand
    const sessionKey = 'chatbot_session_v2_' + activeBrand;
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

    // Synchronously unlock Audio for Mobile / Safari on user interaction
    function unlockAudio() {
        try {
            systemAudio.play().then(() => {
                systemAudio.pause();
                systemAudio.currentTime = 0;
            }).catch(() => { });
        } catch (e) { }

        if ('speechSynthesis' in window) {
            const u = new SpeechSynthesisUtterance('');
            u.volume = 0;
            window.speechSynthesis.speak(u);
        }
        document.body.removeEventListener('click', unlockAudio);
        document.body.removeEventListener('touchstart', unlockAudio);
    }
    document.body.addEventListener('click', unlockAudio, { once: true });
    document.body.addEventListener('touchstart', unlockAudio, { once: true });

    // --- Interactive Capability Chips ---
    function renderCapabilityChips() {
        const existing = document.getElementById('capability-chips-container');
        if (existing) existing.remove();

        const chipsContainer = document.createElement('div');
        chipsContainer.id = 'capability-chips-container';
        chipsContainer.className = 'capability-chips';

        const pinnacleChips = [
            {
                icon: '📞',
                title: '24/7 AI Phone Receptionist',
                desc: 'Zero missed calls, live calendar booking & CRM sync',
                prompt: 'How does an AI phone receptionist work for my business, and how does it book appointments and sync to CRM?'
            },
            {
                icon: '🤖',
                title: 'Autonomous AI Agents',
                desc: 'Multi-agent workflows, Zapier & n8n automation',
                prompt: 'What kind of custom autonomous AI agents and multi-agent workflows can you build for business operations?'
            },
            {
                icon: '🕷️',
                title: 'Custom Lead Scrapers',
                desc: 'Google Maps, social groups & directory extraction',
                prompt: 'Tell me about your custom lead scrapers for Google Maps, Craigslist, and public Facebook groups.'
            },
            {
                icon: '🚀',
                title: 'Auto-Posters & Marketing',
                desc: 'Scheduled social posting & AI video generation',
                prompt: 'How do your automated social media auto-posters and marketing workflows keep businesses visible?'
            },
            {
                icon: '🌐',
                title: 'Custom Web Platforms',
                desc: 'Next.js web apps with integrated 24/7 AI chat',
                prompt: 'Can you build a high-performance custom website or landing page with an integrated AI chatbot and instant lead SMS?'
            },
            {
                icon: '🎓',
                title: '1-on-1 Virtual Training',
                desc: 'Personalized AI coaching & free consultation',
                prompt: 'I want to learn about your 1-on-1 virtual training program and schedule a free AI consultation.'
            },
            {
                icon: '📞',
                title: 'Direct Line: (904) 686-6593',
                desc: 'Speak directly with an AI systems consultant',
                prompt: 'I would like to speak directly with an AI systems consultant at (904) 686-6593.'
            }
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
            if (item.title) {
                btn.className = 'chip-card';
                btn.innerHTML = `
                    <div class="chip-card-icon">${item.icon}</div>
                    <div class="chip-card-body">
                        <span class="chip-card-title">${item.title}</span>
                        <span class="chip-card-desc">${item.desc}</span>
                    </div>
                    <div class="chip-card-arrow">→</div>
                `;
            } else {
                btn.className = 'chip-btn';
                btn.innerHTML = item.label;
            }
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                userInput.value = item.prompt;
                sendMessage();
            });
            chipsContainer.appendChild(btn);
        });

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
        if (!voiceModeActive && !isRecording && !isSpeaking) {
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

    
    // --- Clean Spoken Transcript (Eliminates Browser Speech Stutter, Duplicates, and Overlaps) ---
    function cleanSpokenTranscript(text) {
        if (!text) return '';
        let s = text.replace(/\s+/g, ' ').trim();
        // Collapse repeated phrases (1 to 5 words repeated consecutively)
        s = s.replace(/\b((?:[a-zA-Z0-9']+\s+){1,5}[a-zA-Z0-9']+)\s+\1\b/gi, '$1');
        // Collapse single repeated words (e.g. "what what" -> "what", "is is" -> "is", "the the" -> "the", "us us" -> "us")
        s = s.replace(/\b([a-zA-Z0-9']+)\s+\1\b/gi, '$1');
        s = s.replace(/\b([a-zA-Z0-9']+)\s+\1\b/gi, '$1'); // second pass for triplicates
        // Acoustic corrections for common voice recognizer slips
        s = s.replace(/\bwhat\s+us\s+the\b/gi, 'what is the');
        s = s.replace(/\bwhat\s+us\b/gi, 'what is');
        return s;
    }

    // --- Web Speech Recognition (STD Mode) ---
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;

    if (!SpeechRecognition) {
        console.log("SpeechRecognition not supported in browser, using HD Mode.");
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
            if (voiceModeActive && !isSpeaking) {
                updateVisualizerState('listening', '<span>🎙️ Listening...</span> <small style="opacity:0.85;">(Speak now)</small>');
            }
        };

        recognition.onend = () => {
            isRecording = false;
            micBtn.classList.remove('recording');

            // If user finished speaking and text is present, auto-send
            if (userInput.value.trim() && voiceModeActive && !isSpeaking) {
                clearTimeout(silenceTimer);
                sendMessage();
                return;
            }

            // In Voice Mode, keep the listening loop active while bot is NOT speaking
            if (voiceModeActive && !isSpeaking) {
                setTimeout(() => {
                    if (voiceModeActive && !isSpeaking && !isRecording) {
                        safeStartRecognition();
                    }
                }, 200);
            }
        };

        recognition.onerror = (event) => {
            console.log("Speech recognition event:", event.error);
            if (event.error === 'no-speech') {
                return; // Normal pause; let onend handle clean loop
            }
            if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
                isRecording = false;
                micBtn.classList.remove('recording');
                voiceModeActive = false;
                if (voiceModeBtn) voiceModeBtn.classList.remove('active');
                updateVisualizerState('hidden', '');
                alert("Please enable microphone permissions in your browser to talk.");
            }
        };

        recognition.onresult = (event) => {
            // STRICT MUTE: Ignore all mic input while the bot is speaking (prevents blurry echo / self-interruption)
            if (isSpeaking) {
                return;
            }

            let interim = '';
            let final = '';
            for (let i = 0; i < event.results.length; ++i) {
                const res = event.results[i];
                if (res.isFinal) {
                    final += res[0].transcript + ' ';
                } else {
                    interim += res[0].transcript;
                }
            }

            const raw = (final + interim).trim();
            const cleanTranscript = cleanSpokenTranscript(raw);
            if (!cleanTranscript) return;

            // Clear, live transcription feedback for the user without duplicates
            userInput.value = cleanTranscript;
            userInput.dispatchEvent(new Event('input'));
            updateVisualizerState('listening', '<span>🎙️ ' + cleanTranscript.slice(-36) + '</span>');

            // Auto-send after 1.3s of clean silence once user finishes speaking
            clearTimeout(silenceTimer);
            silenceTimer = setTimeout(() => {
                if (userInput.value.trim() && (voiceModeActive || isRecording) && !isSpeaking) {
                    stopListening();
                    setTimeout(() => {
                        if (userInput.value.trim()) sendMessage();
                    }, 80);
                }
            }, 1300);
        };
    }

    function safeStartRecognition() {
        if (!recognition || isSpeaking) return;
        try {
            recognition.abort(); // Cancel and flush any pending internal audio/result queue
        } catch (e) { }
        try {
            recognition.start();
            isRecording = true;
            micBtn.classList.add('recording');
        } catch (e) {
            if (e.name !== 'InvalidStateError') {
                console.warn("Recognition start note:", e);
            }
        }
    }

    // --- MediaRecorder (HD Mode) ---
    let mediaRecorder = null;
    let audioChunks = [];

    async function startListening() {
        if (isSpeaking) {
            stopSpeaking();
        }
        if (isRecording) return;

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
            safeStartRecognition();
        }
    }

    function stopListening() {
        isRecording = false;
        if (useHDMode && mediaRecorder && mediaRecorder.state === 'recording') {
            try { mediaRecorder.stop(); } catch (e) { }
        } else if (recognition) {
            try { recognition.stop(); } catch (e) { }
        }
        micBtn.classList.remove('recording');
    }

    // --- Stop Speaking (Immediate Cutoff & Barge-In) ---
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
        if (currentSpeakingMsgId) updateSpeakButton(currentSpeakingMsgId, false);
        currentSpeakingMsgId = null;
    }

    function getPreferredVoice() {
        return 'roger';
    }

    // Clean text into natural conversational spoken English
    function extractSpeechText(rawText) {
        let clean = rawText
            .replace(/```[\s\S]*?```/g, '')
            .replace(/`([^`]+)`/g, '$1')
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
            .replace(/!\[[^\]]*\]\([^)]+\)/g, '')
            .replace(/https?:\/\/\S+/g, '')
            .replace(/^#+\s*/gm, '')
            .replace(/^\s*[-*+]\s+/gm, '')
            .replace(/[*_~]{1,3}([^*_~]+)[*_~]{1,3}/g, '$1')
            .replace(/\((\d{3})\)\s*(\d{3})-(\d{4})/g, '$1, $2, $3')
            .replace(/(\d{3})-(\d{3})-(\d{4})/g, '$1, $2, $3')
            .replace(/\n+/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();

        // Speak the full returned paragraph completely (capped safely at 3500 chars to avoid memory issues)
        if (clean.length > 3500) {
            clean = clean.substring(0, 3500).trim();
        }
        return clean;
    }

    // --- High-Quality TTS (ElevenLabs -> Edge TTS -> Browser Fallback) ---
    async function speakWithElevenLabs(text, msgId) {
        stopSpeaking();
        // Crucial: STOP mic while speaking so the speaker NEVER bleeds into the mic
        stopListening();

        const gen = ++speechGen;
        const spoken = extractSpeechText(text);
        if (!spoken) return;

        if (voiceModeActive) {
            updateVisualizerState('speaking', '<span>🔊 Speaking...</span> <small style="opacity:0.85;">(Tap to interrupt)</small>');
        }

        try {
            const voiceTarget = getPreferredVoice();
            const response = await fetch(`${API_BASE}/api/tts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: spoken,
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
                        userInput.value = '';
                        if (msgId) updateSpeakButton(msgId, false);

                        // Seamless turn-taking loop: automatically open mic after speech finishes
                        if (voiceModeActive) {
                            updateVisualizerState('listening', '<span>🎙️ Listening...</span> <small style="opacity:0.85;">(Speak now)</small>');
                            setTimeout(() => {
                                if (voiceModeActive && !isSpeaking && !isRecording) {
                                    startListening();
                                }
                            }, 200);
                        }
                    };

                    await systemAudio.play();
                    return;
                }
            }
            // Fallback to browser speech if API fails
            speakTextBrowser(spoken, msgId);
        } catch (err) {
            if (gen === speechGen) speakTextBrowser(spoken, msgId);
        }
    }

    function speakTextBrowser(cleanText, msgId) {
        if (!('speechSynthesis' in window)) return;
        window.speechSynthesis.cancel();
        stopListening();

        const utterance = new SpeechSynthesisUtterance(cleanText);
        const maleVoice = pickMaleBrowserVoice();
        if (maleVoice) utterance.voice = maleVoice;

        // Chrome/Chromium 15-second speech synthesis garbage collection & cutoff fix
        let resumeInterval = setInterval(() => {
            if (!isSpeaking) {
                clearInterval(resumeInterval);
            } else if (window.speechSynthesis && window.speechSynthesis.speaking) {
                window.speechSynthesis.pause();
                window.speechSynthesis.resume();
            }
        }, 8000);

        utterance.onstart = () => {
            isSpeaking = true;
            currentSpeakingMsgId = msgId;
            if (msgId) updateSpeakButton(msgId, true);
            if (voiceModeActive) {
                updateVisualizerState('speaking', '<span>🔊 Speaking...</span> <small style="opacity:0.85;">(Tap to interrupt)</small>');
            }
        };

        utterance.onend = () => {
            clearInterval(resumeInterval);
            isSpeaking = false;
            userInput.value = '';
            if (msgId) updateSpeakButton(msgId, false);
            if (voiceModeActive) {
                updateVisualizerState('listening', '<span>🎙️ Listening...</span> <small style="opacity:0.85;">(Speak now)</small>');
                setTimeout(() => {
                    if (voiceModeActive && !isSpeaking && !isRecording) {
                        startListening();
                    }
                }, 200);
            }
        };

        utterance.onerror = () => {
            clearInterval(resumeInterval);
            isSpeaking = false;
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

    function getCopyIcon() {
        return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
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

    // --- Tap/Click Interruption (Barge-In) ---
    if (voiceVisualizer) {
        voiceVisualizer.addEventListener('click', (e) => {
            e.preventDefault();
            if (isSpeaking) {
                console.log("Tap on Visualizer interrupted speech.");
                stopSpeaking();
                userInput.value = '';
                startListening();
            } else if (isRecording) {
                stopListening();
                if (userInput.value.trim()) sendMessage();
            } else {
                startListening();
            }
        });
    }

    if (micBtn) {
        micBtn.addEventListener('click', (e) => {
            e.preventDefault();
            unlockAudio();
            if (isSpeaking) {
                stopSpeaking();
                userInput.value = '';
                startListening();
                return;
            }
            if (isRecording) {
                stopListening();
                if (userInput.value.trim()) sendMessage();
            } else {
                startListening();
            }
        });
    }

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && isSpeaking) {
            stopSpeaking();
            userInput.value = '';
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

    // --- Voice Mode Toggle (Clear & Easy: Does NOT talk over user!) ---
    if (voiceModeBtn) {
        voiceModeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            unlockAudio();

            voiceModeActive = !voiceModeActive;
            voiceModeBtn.classList.toggle('active', voiceModeActive);
            autoSpeak = voiceModeActive;
            if (autoSpeakToggle) autoSpeakToggle.checked = autoSpeak;

            console.log(`Voice Mode: ${voiceModeActive ? 'ENABLED' : 'DISABLED'}`);

            if (voiceModeActive) {
                // Instantly open the mic cleanly so the user can speak immediately!
                stopSpeaking();
                stopListening();
                userInput.value = '';
                updateVisualizerState('listening', '<span>🎙️ Listening...</span> <small style="opacity:0.85;">(Speak now)</small>');
                setTimeout(() => {
                    startListening();
                }, 150);
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
    let isSendingMessage = false;
    async function sendMessage() {
        if (isSendingMessage) return;
        const text = cleanSpokenTranscript(userInput.value.trim());
        if (!text || sendBtn.disabled) return;

        stopSpeaking();
        stopListening();
        clearTimeout(silenceTimer);
        addUserMessage(text);
        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.disabled = true;
        isSendingMessage = true;

        if (voiceModeActive) {
            updateVisualizerState('thinking', '<span>⚡ Thinking...</span>');
        }

        const loader = showTypingIndicator();

        try {
            const resp = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream'
                },
                body: JSON.stringify({
                    message: text,
                    session_id: currentSessionId,
                    brand: activeBrand,
                    stream: true
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
            isSendingMessage = false;
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
                    <button class="action-btn copy-btn" title="Copy response">${getCopyIcon()} <span>Copy</span></button>
                    <button class="action-btn speak-btn" title="Listen with voice">${getSpeakerIcon()} <span>Listen</span></button>
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
            const streamCopyBtn = div.querySelector('.copy-btn');
            if (streamCopyBtn) {
                streamCopyBtn.addEventListener('click', () => {
                    navigator.clipboard.writeText(displayText).then(() => {
                        streamCopyBtn.innerHTML = `✓ <span>Copied!</span>`;
                        setTimeout(() => {
                            streamCopyBtn.innerHTML = `${getCopyIcon()} <span>Copy</span>`;
                        }, 2000);
                    }).catch(() => {});
                });
            }
            scrollToBottom();

            // Auto-speak in voice mode (clean, natural, concise ElevenLabs voice)
            if (autoSpeak) {
                speakWithElevenLabs(displayText, msgId);
            }

        } catch (err) {
            loader.remove();
            addErrorMessage("Connection error. Please try again.");
            if (voiceModeActive) {
                updateVisualizerState('listening', '<span>🎙️ Listening...</span> <small style="opacity:0.85;">(Speak now)</small>');
                startListening();
            }
        }
        sendBtn.disabled = false;
            isSendingMessage = false;
    }

    function addUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'message user-message';
        div.innerHTML = `<div class="message-content">${escapeHTML(text)}</div>`;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function addAssistantMessage(text) {
        const msgId = 'msg_' + Date.now();
        const div = document.createElement('div');
        div.className = 'message assistant-message';
        div.setAttribute('data-msg-id', msgId);
        div.innerHTML = `
            <div class="message-content">${marked.parse(text)}</div>
            <div class="message-actions">
                <button class="action-btn copy-btn" title="Copy response">${getCopyIcon()} <span>Copy</span></button>
                <button class="action-btn speak-btn" title="Listen with voice">${getSpeakerIcon()} <span>Listen</span></button>
            </div>
        `;
        chatMessages.appendChild(div);
        div.querySelector('.speak-btn').addEventListener('click', () => {
            if (isSpeaking && currentSpeakingMsgId === msgId) stopSpeaking();
            else speakWithElevenLabs(text, msgId);
        });
        const copyBtn = div.querySelector('.copy-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(text).then(() => {
                    copyBtn.innerHTML = `✓ <span>Copied!</span>`;
                    setTimeout(() => {
                        copyBtn.innerHTML = `${getCopyIcon()} <span>Copy</span>`;
                    }, 2000);
                }).catch(() => {});
            });
        }
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
