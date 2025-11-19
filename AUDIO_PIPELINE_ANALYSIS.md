# Audio Pipeline Analysis & Recommendations

## Current Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. BROWSER CAPTURE                                              │
│    getUserMedia() → MediaRecorder                               │
│    Format: audio/webm (Opus codec)                              │
│    Sample Rate: ~48kHz (browser default)                        │
│    Bitrate: Variable (Opus adaptive)                            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. HTTP TRANSMISSION                                            │
│    POST /api/v1/assess                                          │
│    FormData: audio/webm blob                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. BACKEND PROCESSING (gemini_service.py)                       │
│    Receives: audio/webm bytes                                   │
│    Converts: webm → WAV (pydub/ffmpeg)                          │
│    Uploads: WAV to Gemini API                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. GEMINI API PROCESSING                                        │
│    Receives: audio/wav                                          │
│    Performs: Speech-to-text + pronunciation analysis            │
│    Returns: JSON assessment                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Problems with Current Approach

### 1. **Quality Degradation**
- **WebM Opus Codec**: Lossy compression optimized for voice calls, not pronunciation assessment
- **Unnecessary Conversion**: webm → WAV introduces transcoding artifacts
- **Multiple Codecs**: Each conversion step loses audio fidelity

### 2. **No Noise Handling**
- Background noise affects pronunciation assessment
- No voice activity detection (VAD)
- Kids' environments are often noisy (classroom, home)

### 3. **Suboptimal for Kids' Voices**
- Kids' voices have higher fundamental frequency (250-300 Hz vs adult 100-150 Hz)
- Current pipeline doesn't account for this
- Sample rate and codec not optimized for clarity

### 4. **Inefficient Processing**
- Server-side conversion wastes CPU
- Increases latency for kids waiting for feedback
- Unnecessary file I/O operations

## Recommended Solution: WAV PCM Pipeline

### Optimal Format Specification

```
Format:       WAV (uncompressed PCM)
Sample Rate:  16kHz (speech recognition standard)
Bit Depth:    16-bit
Channels:     Mono (1 channel)
Codec:        PCM (no compression)
```

### Why This Format?

1. **Industry Standard for Speech Recognition**
   - Gemini API examples show 16kHz as optimal for speech
   - VAD library (ricky0123/vad) requires 16kHz Float32Array
   - No lossy compression = maximum clarity

2. **Best for Kids' Voices**
   - 16kHz Nyquist frequency (8kHz) captures full speech spectrum
   - Kids' fundamental frequencies: 250-300 Hz (well within range)
   - Formants: F1: 500-1500Hz, F2: 1500-3500Hz (all captured)

3. **Efficient Processing**
   - No codec conversions needed
   - Direct upload to Gemini
   - Smaller file sizes than 48kHz WebM

4. **VAD Integration Ready**
   - @ricky0123/vad-web works with 16kHz audio
   - Can process in-browser before upload
   - Removes silence/noise automatically

## Implementation Strategy

### Phase 1: Browser-Side Audio Capture (Recommended)

```javascript
// Use AudioContext for direct PCM capture
const audioContext = new AudioContext({ sampleRate: 16000 });
const stream = await navigator.mediaDevices.getUserMedia({
  audio: {
    channelCount: 1,
    sampleRate: 16000,
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true
  }
});

const source = audioContext.createMediaStreamSource(stream);
const processor = audioContext.createScriptProcessor(4096, 1, 1);

// Collect Float32 samples at 16kHz
processor.onaudioprocess = (e) => {
  const samples = e.inputBuffer.getChannelData(0);
  audioSamples.push(new Float32Array(samples));
};
```

**Benefits:**
- Native 16kHz capture (no resampling)
- Enables browser-side VAD
- Direct control over audio quality
- Can apply pre-processing (noise gate, normalization)

### Phase 2: VAD Integration (@ricky0123/vad-web)

```javascript
import { MicVAD } from "@ricky0123/vad-web"

const vad = await MicVAD.new({
  onSpeechStart: () => {
    // Start recording only when speech detected
  },
  onSpeechEnd: (audio) => {
    // audio is Float32Array at 16kHz - perfect for upload!
    const wavBlob = convertFloat32ToWav(audio, 16000);
    uploadToAPI(wavBlob);
  }
})
```

**Benefits for Kids:**
- Automatic noise removal
- Only captures actual speech
- Reduces "silence" uploads
- Better assessment accuracy

### Phase 3: Server-Side Simplification

```python
def _upload_audio_file(self, audio_data_bytes: bytes):
    """Upload WAV audio directly to Gemini - no conversion needed."""
    with temp_audio_file(audio_data_bytes, '.wav') as temp_path:
        return self.client.files.upload(
            file=temp_path,
            config=types.UploadFileConfig(
                mime_type='audio/wav'
            )
        )
```

**Benefits:**
- Remove pydub dependency
- No CPU-intensive conversion
- Faster response times
- Simpler code

## Migration Path

### Option A: Quick Fix (Keep Current, Add Conversion)
**Status: DONE** ✅
- Already implemented webm → WAV conversion
- Works with existing MediaRecorder
- No frontend changes needed

**Pros:**
- Immediate fix for compatibility
- No breaking changes

**Cons:**
- Still has quality loss
- No VAD/noise handling
- Inefficient processing

### Option B: Optimal Solution (Recommended)
**Effort: Medium | Impact: High**

1. **Replace MediaRecorder with AudioContext**
   - Capture at 16kHz mono from start
   - Enable built-in noise suppression
   - Direct PCM capture

2. **Integrate @ricky0123/vad-web**
   - Install: `npm install @ricky0123/vad-web`
   - Use MicVAD for automatic speech detection
   - Only upload when kid is speaking

3. **Remove Backend Conversion**
   - Accept WAV directly
   - Remove pydub conversion logic
   - Faster API responses

4. **Update Environment**
   ```env
   TEMP_FILE_EXTENSION=.wav
   RECORDED_AUDIO_MIME_TYPE=audio/wav
   ```

### Option C: Hybrid Approach (Pragmatic)
**Effort: Low | Impact: Medium**

1. **Keep current MediaRecorder**
2. **Add browser-side resampling**
   ```javascript
   // Resample webm to 16kHz WAV in browser before upload
   const audioContext = new AudioContext({ sampleRate: 16000 });
   const audioBuffer = await audioContext.decodeAudioData(webmBlob);
   const wavBlob = audioBufferToWav(audioBuffer);
   ```
3. **Remove server-side conversion**

## Recommendation for Kids' Pronunciation App

**Go with Option B (Optimal Solution)**

### Rationale:
1. **Best Audio Quality**: No lossy compression = clearer pronunciation assessment
2. **Noise Handling**: VAD removes background noise (critical for kids' environments)
3. **Better UX**: Faster processing, immediate feedback
4. **Future-Proof**: Standard format for speech AI applications
5. **Cost-Effective**: Less server processing = lower costs at scale

### Timeline:
- Week 1: Implement AudioContext + WAV export (2-3 days)
- Week 2: Integrate VAD library (2-3 days)
- Week 3: Testing with real kids' voices (3-5 days)
- Week 4: Remove backend conversion, deploy

### Testing Considerations:
- Test with various ages (5-12 years)
- Test in noisy environments (classroom simulation)
- Compare pronunciation accuracy: WebM vs WAV
- Measure latency improvements

## Technical References

- **Gemini Audio Docs**: Uses PCM/WAV examples throughout
- **VAD Library**: https://github.com/ricky0123/vad
- **Speech Recognition Standard**: 16kHz mono PCM
- **Kids' Voice Frequencies**: 250-400 Hz (fundamental), up to 4kHz (formants)
