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
        mediaRecorder: null,
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
         *   [1.3] Create MediaRecorder to capture audio
         *   [1.4] Collect audio chunks as data becomes available
         *   [1.5] On stop, release microphone and trigger processRecording()
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
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

                // [1.3] Create recorder
                this.mediaRecorder = new MediaRecorder(stream);

                // [1.4] Collect chunks
                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) this.audioChunks.push(event.data);
                };

                // [1.5] On stop → process
                this.mediaRecorder.onstop = async () => {
                    stream.getTracks().forEach((track) => track.stop());
                    await this.processRecording();
                };

                this.mediaRecorder.start();
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
            if (this.mediaRecorder && this.state === AppState.RECORDING) {
                this.transitionTo(AppState.PROCESSING);
                this.currentAnimation = "idle";
                this.mediaRecorder.stop();
            }
        },

        /**
         * Step 3: Process recorded audio - sends to backend for assessment.
         *
         * Flow:
         *   [3.1] Validate expected text and audio chunks exist
         *   [3.2] Create audio blob from recorded chunks
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
                // [3.2] Create audio blob
                const audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });

                // [3.3] Send assessment request
                const formData = new FormData();
                formData.append("audio_file", audioBlob, "recording.webm");
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
                this.mediaRecorder = null;
                this.audioChunks = [];
            }
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
