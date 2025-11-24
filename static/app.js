/**
 * Pronunciation Assessment Frontend Application.
 *
 * Complete Flow:
 *   [1] User clicks record button → startRecording()
 *   [2] MediaRecorder captures audio chunks (WebM format)
 *   [3] User clicks stop → stopRecording() → processRecording()
 *   [4] POST to /api/v1/assess with audio + expected_text
 *   [5] Backend returns: { scores, feedback }
 *   [6] displayResults() shows scores and feedback
 *   [7] Auto-reset to IDLE after 5 seconds
 */

const AppState = {
    IDLE: 'idle',
    RECORDING: 'recording',
    PROCESSING: 'processing',
    RESULTS: 'results'
};

document.addEventListener('alpine:init', () => {
    Alpine.data('pronunciationApp', () => ({
        // Core State
        state: AppState.IDLE,

        // Data
        expectedText: "The apple is red",
        results: false,
        resultTitle: "",
        resultMessage: "",
        errors: [],
        scores: null,
        audioContext: null,
        audioInput: null,
        audioRecorder: null,
        recordingStream: null,
        audioChunks: [],

        // UI State
        statusMessage: "Ready to practice!",
        statusIcon: "info-circle",
        currentAnimation: "idle",

        // Animation Assets
        animations: {
            idle: "/assets/mascot/idle/idle.lottie",
            greetings: "/assets/mascot/greetings/greetings.lottie",
            happy: "/assets/mascot/happy/happy_minified.lottie",
            cheerful: "/assets/mascot/cheerful/cheerful.lottie",
            winner: "/assets/mascot/winner/winner.lottie",
            upset: "/assets/mascot/upset/upset_minified.lottie",
        },

        // State Configuration
        get config() {
            return {
                [AppState.IDLE]: {
                    btnIcon: 'mic',
                    btnVariant: 'primary',
                    status: { msg: 'Ready to practice!', icon: 'info-circle' }
                },
                [AppState.RECORDING]: {
                    btnIcon: 'stop-circle',
                    btnVariant: 'danger',
                    status: { msg: 'Recording... Speak clearly!', icon: 'mic' }
                },
                [AppState.PROCESSING]: {
                    btnIcon: 'loader',
                    btnVariant: 'warning',
                    status: { msg: 'Processing your pronunciation...', icon: 'loader' }
                },
                [AppState.RESULTS]: {
                    btnIcon: 'mic',
                    btnVariant: 'primary',
                    status: null // Results state has dynamic status
                }
            }[this.state];
        },

        // Computed Properties (Getters)
        get buttonIcon() { return this.config.btnIcon; },
        get buttonVariant() { return this.config.btnVariant; },
        get isRecording() { return this.state === AppState.RECORDING; },
        get isProcessing() { return this.state === AppState.PROCESSING; },
        get statusHtml() { return `<sl-icon name="${this.statusIcon}"></sl-icon> ${this.statusMessage}`; },

        init() {
            this.preloadAnimations();
        },

        // State Transition Helper
        transitionTo(newState, customMsg = null, customIcon = null) {
            this.state = newState;

            // Apply default status from config if no custom message provided
            const defaultStatus = this.config.status;
            if (defaultStatus && !customMsg) {
                this.statusMessage = defaultStatus.msg;
                this.statusIcon = defaultStatus.icon;
            } else if (customMsg) {
                this.statusMessage = customMsg;
                this.statusIcon = customIcon || 'info-circle';
            }
        },

        async toggleRecording() {
            if (this.state === AppState.IDLE || this.state === AppState.RESULTS) {
                await this.startRecording();
            } else if (this.state === AppState.RECORDING) {
                await this.stopRecording();
            }
        },

        /**
         * Step 1: Start recording user's voice.
         *
         * Flow:
         *   [1.1] Reset previous results and audio chunks
         *   [1.2] Request microphone access via getUserMedia
         *   [1.3] Create AudioContext and ScriptProcessor for WAV recording
         *   [1.4] Collect audio samples
         *   [1.5] On stop, convert to WAV and trigger processRecording()
         */
        async startRecording() {
            // [1.1] Reset state
            this.results = false;
            this.audioChunks = [];
            this.scores = null;
            this.transitionTo(AppState.RECORDING);
            this.currentAnimation = "greetings";

            try {
                // [1.2] Request microphone
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        sampleRate: 16000,
                        echoCancellation: true,
                        noiseSuppression: true
                    }
                });

                // [1.3] Create AudioContext for WAV recording
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                this.audioInput = this.audioContext.createMediaStreamSource(stream);
                this.audioRecorder = this.audioContext.createScriptProcessor(4096, 1, 1);

                this.recordingStream = stream;
                this.audioChunks = [];

                // [1.4] Collect audio samples
                this.audioRecorder.onaudioprocess = (e) => {
                    if (this.state === AppState.RECORDING) {
                        const channelData = e.inputBuffer.getChannelData(0);
                        this.audioChunks.push(new Float32Array(channelData));
                    }
                };

                this.audioInput.connect(this.audioRecorder);
                this.audioRecorder.connect(this.audioContext.destination);

            } catch (error) {
                console.error("Error accessing microphone:", error);
                alert("Could not access microphone. Please check permissions.");
                this.transitionTo(AppState.IDLE);
            }
        },

        /**
         * Step 2: Stop recording and trigger processing.
         */
        async stopRecording() {
            if (this.audioRecorder && this.state === AppState.RECORDING) {
                this.transitionTo(AppState.PROCESSING);
                this.currentAnimation = "idle";

                // Disconnect audio nodes
                this.audioRecorder.disconnect();
                this.audioInput.disconnect();

                // Stop microphone stream
                if (this.recordingStream) {
                    this.recordingStream.getTracks().forEach((track) => track.stop());
                }

                // Close audio context
                if (this.audioContext) {
                    await this.audioContext.close();
                }

                await this.processRecording();
            }
        },

        /**
         * Step 3: Process recorded audio - sends to backend for assessment.
         *
         * Flow:
         *   [3.1] Validate expected text and audio chunks exist
         *   [3.2] Convert Float32Array chunks to WAV blob
         *   [3.3] Send POST request to /api/v1/assess
         *   [3.4] Parse response containing scores and feedback
         *   [3.5] Display results
         */
        async processRecording() {
            // [3.1] Validate inputs
            const expectedSentence = this.expectedText.trim();

            if (!expectedSentence) {
                alert("Please enter an expected sentence first!");
                this.transitionTo(AppState.IDLE);
                return;
            }

            if (this.audioChunks.length === 0) {
                alert("No audio recorded. Please try again.");
                this.transitionTo(AppState.IDLE);
                return;
            }

            try {
                // [3.2] Convert to WAV blob
                const audioBlob = this.exportWAV(this.audioChunks, 16000);

                // [3.3] Send assessment request
                const formData = new FormData();
                formData.append("audio_file", audioBlob, "recording.wav");
                formData.append("expected_text", expectedSentence);

                const response = await fetch("/api/v1/assess", {
                    method: "POST",
                    body: formData,
                });

                if (!response.ok) {
                    throw new Error(`API error ${response.status}`);
                }

                // [3.4] Parse response (scores + feedback)
                const data = await response.json();

                this.displayResults(data);
            } catch (error) {
                console.error("Error:", error);
                alert(`Failed: ${error.message}`);
                this.transitionTo(AppState.IDLE, "Error occurred. Try again.", "x-circle");
            } finally {
                this.audioRecorder = null;
                this.audioChunks = [];
            }
        },

        /**
         * Convert Float32Array audio chunks to WAV blob.
         * 
         * @param {Float32Array[]} chunks - Array of audio sample chunks
         * @param {number} sampleRate - Sample rate (e.g., 16000)
         * @returns {Blob} WAV audio blob
         */
        exportWAV(chunks, sampleRate) {
            // Merge all chunks into single Float32Array
            const totalLength = chunks.reduce((acc, chunk) => acc + chunk.length, 0);
            const samples = new Float32Array(totalLength);
            let offset = 0;
            for (const chunk of chunks) {
                samples.set(chunk, offset);
                offset += chunk.length;
            }

            // Convert Float32 to Int16
            const buffer = new ArrayBuffer(44 + samples.length * 2);
            const view = new DataView(buffer);

            // WAV header
            const writeString = (offset, string) => {
                for (let i = 0; i < string.length; i++) {
                    view.setUint8(offset + i, string.charCodeAt(i));
                }
            };

            writeString(0, 'RIFF');
            view.setUint32(4, 36 + samples.length * 2, true);
            writeString(8, 'WAVE');
            writeString(12, 'fmt ');
            view.setUint32(16, 16, true); // fmt chunk size
            view.setUint16(20, 1, true); // PCM format
            view.setUint16(22, 1, true); // mono
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * 2, true); // byte rate
            view.setUint16(32, 2, true); // block align
            view.setUint16(34, 16, true); // bits per sample
            writeString(36, 'data');
            view.setUint32(40, samples.length * 2, true);

            // Write PCM samples
            let index = 44;
            for (let i = 0; i < samples.length; i++) {
                const s = Math.max(-1, Math.min(1, samples[i]));
                view.setInt16(index, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
                index += 2;
            }

            return new Blob([buffer], { type: 'audio/wav' });
        },

        /**
         * Step 4: Display assessment results.
         *
         * Flow:
         *   [4.1] Extract scores and feedback from API response
         *   [4.2] Select mascot animation based on pronunciation score
         *   [4.3] Update UI with results
         *   [4.4] Auto-reset to IDLE after 5 seconds
         *
         * @param {Object} data - API response with scores and feedback
         */
        displayResults(data) {
            // [4.1] Extract data from response
            const errors = data.word_level_feedback || [];
            const scores = data.overall_scores || {};
            const summaryText = data.summary_text || "";

            this.errors = errors;
            this.scores = scores;

            const pronScore = scores.pronunciation || 0;

            // [4.2] Select animation based on score
            let animation = "winner";
            let title = "Perfect Pronunciation!";
            let message = summaryText || "Amazing! No errors detected.";
            let statusIcon = "check-circle";

            if (pronScore >= 90) {
                animation = "winner";
                title = "Perfect Pronunciation!";
                statusIcon = "check-circle";
            } else if (pronScore >= 75) {
                animation = "happy";
                title = "Great Job!";
                statusIcon = "hand-thumbs-up";
            } else if (pronScore >= 60) {
                animation = "cheerful";
                title = "Good Effort!";
                statusIcon = "emoji-smile";
            } else {
                animation = "upset";
                title = "Needs Practice";
                statusIcon = "exclamation-circle";
            }

            if (summaryText) {
                message = summaryText;
            }

            // [4.3] Update UI
            this.currentAnimation = animation;
            this.resultTitle = title;
            this.resultMessage = message;
            this.results = true;

            const statusMsg = pronScore >= 85
                ? `Score: ${Math.round(pronScore)}% - Excellent!`
                : `Score: ${Math.round(pronScore)}% - ${errors.length} area(s) to improve`;
            this.transitionTo(AppState.RESULTS, statusMsg, statusIcon);

            // [4.4] Auto-reset after 5 seconds
            setTimeout(() => {
                if (this.state === AppState.RESULTS) {
                    this.currentAnimation = "idle";
                    this.transitionTo(AppState.IDLE, "Ready to practice again!", "info-circle");
                }
            }, 5000);
        },

        preloadAnimations() {
            Object.values(this.animations).forEach((url) => {
                const link = document.createElement("link");
                link.rel = "prefetch";
                link.href = url;
                document.head.appendChild(link);
            });
        },
    }));
});
