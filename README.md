# Pronunciation Assessment System

Pronunciation assessment for Indian English learners using Azure Speech + Gemini.

## Pipeline

```
User Audio → Azure Speech API → Gemini Analysis → TTS Feedback
```

1. User records audio speaking a reference sentence
2. Audio sent to Azure Speech Pronunciation Assessment
3. Azure returns scores (pronunciation, accuracy, fluency, completeness, prosody)
4. Gemini analyzes scores and generates kid-friendly feedback
5. TTS converts feedback to audio

## Environment Variables

Create `.env` file:

```bash
# Azure Speech (required)
SPEECH_KEY=your_azure_speech_key
SPEECH_REGION=centralindia

# Gemini (required)
GEMINI_API_KEY=your_gemini_api_key
MODEL_NAME=gemini-2.0-flash

# TTS (required)
TTS_MODEL_NAME=gemini-2.5-flash-preview-tts
TTS_VOICE_NAME=Kore
```

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## API

### POST `/api/v1/assess`

Returns JSON with scores and feedback.

**Request:** `audio_file` (WAV) + `expected_text` (form)

**Response:**
```json
{
  "summary_text": "Great job!",
  "overall_scores": {"pronunciation": 85, "accuracy": 88, "fluency": 82, "completeness": 100, "prosody": 78},
  "word_level_feedback": [{"word": "the", "issue": "th sound soft", "suggestion": "tongue between teeth", "severity": "minor"}],
  "prosody_feedback": null
}
```

### POST `/api/v1/assess/tts`

Returns WAV audio with spoken feedback.

## Test

```bash
python scripts/test_azure_pipeline.py --test-connection
python scripts/test_azure_pipeline.py --audio sample.wav --text "The cat is on the mat"
```
