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
        expectedText: "The cat is on the mat",
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

        async startRecording() {
            this.results = false;
            this.audioChunks = [];
            this.scores = null;
            this.transitionTo(AppState.RECORDING);
            this.currentAnimation = "greetings";

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                this.mediaRecorder = new MediaRecorder(stream);

                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) this.audioChunks.push(event.data);
                };

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

        async stopRecording() {
            if (this.mediaRecorder && this.state === AppState.RECORDING) {
                this.transitionTo(AppState.PROCESSING);
                this.currentAnimation = "idle";
                this.mediaRecorder.stop();
            }
        },

        async processRecording() {
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
                const audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });

                // Prepare FormData
                const formData1 = new FormData();
                formData1.append("audio_file", audioBlob, "recording.webm");
                formData1.append("expected_text", expectedSentence);

                const formData2 = new FormData();
                formData2.append("audio_file", audioBlob, "recording.webm");
                formData2.append("expected_text", expectedSentence);

                // Parallel Requests
                const [assessmentResponse, ttsResponse] = await Promise.all([
                    fetch("/api/v1/assess", { method: "POST", body: formData1 }),
                    fetch("/api/v1/assess/tts", { method: "POST", body: formData2 }),
                ]);

                if (!assessmentResponse.ok) {
                    throw new Error(`API error ${assessmentResponse.status}`);
                }

                const data = await assessmentResponse.json();

                let audioUrl = null;
                if (ttsResponse.ok) {
                    const blob = await ttsResponse.blob();
                    audioUrl = URL.createObjectURL(blob);
                }

                this.displayResults(data, audioUrl);
            } catch (error) {
                console.error("Error:", error);
                alert(`Failed: ${error.message}`);
                this.transitionTo(AppState.IDLE, "Error occurred. Try again.", "x-circle");
            } finally {
                this.mediaRecorder = null;
                this.audioChunks = [];
            }
        },

        displayResults(data, audioUrl = null) {
            // New Azure-based response format
            const errors = data.word_level_feedback || [];
            const scores = data.overall_scores || {};
            const summaryText = data.summary_text || "";

            this.errors = errors;
            this.scores = scores;

            // Use pronunciation score to determine result state
            const pronScore = scores.pronunciation || 0;

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

            // Override message with summary_text if available
            if (summaryText) {
                message = summaryText;
            }

            this.currentAnimation = animation;
            this.resultTitle = title;
            this.resultMessage = message;
            this.results = true;

            const statusMsg = pronScore >= 85
                ? `Score: ${Math.round(pronScore)}% - Excellent!`
                : `Score: ${Math.round(pronScore)}% - ${errors.length} area(s) to improve`;
            this.transitionTo(AppState.RESULTS, statusMsg, statusIcon);

            // Play Audio
            if (audioUrl) {
                const audio = new Audio(audioUrl);
                audio.play().catch(e => console.error(e));
                audio.onended = () => URL.revokeObjectURL(audioUrl);
            }

            // Auto-reset after delay
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
