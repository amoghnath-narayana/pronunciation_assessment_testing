# Pronunciation Practice Frontend

A minimal, single-page web application for pronunciation assessment with animated mascot feedback.

## Features

✅ **Web-based audio recording** - Record directly in the browser
✅ **Real-time AI assessment** - Powered by Google Gemini API
✅ **Animated mascot feedback** - 6 emotional states using Lottie animations
✅ **Minimal dependencies** - Only 3 CDN resources (~130 KB total)
✅ **Responsive design** - Works on desktop and mobile
✅ **Dark mode support** - Automatic based on system preference

---

## Quick Start

### 1. Start the Server

```bash
just run
```

Or manually:
```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Open in Browser

Navigate to: **http://localhost:8000**

---

## How to Use

1. **Enter expected sentence** - Type the sentence you want to practice
2. **Click "Start Recording"** - Allow microphone access when prompted
3. **Speak the sentence** - Speak clearly into your microphone
4. **Click "Stop Recording"** - Recording stops automatically after you click
5. **View results** - Mascot shows emotional feedback based on your pronunciation

---

## Mascot Animations

The mascot displays different emotions based on your pronunciation:

| Errors | Animation | Expression |
|--------|-----------|------------|
| 0 errors | `winner` | 🎉 Perfect! Celebrating |
| 1-2 minor | `happy` | 😊 Great job! |
| 3-4 errors | `cheerful` | 🙂 Good effort! |
| 5+ errors | `upset` | 😔 Needs practice |
| Recording | `greetings` | 👋 Listening attentively |
| Idle | `idle` | 😌 Gentle breathing |

---

## Tech Stack

### Frontend
- **Pico CSS** (2.0.6) - Classless CSS framework
- **Lucide Icons** (latest) - Beautiful SVG icons
- **dotLottie Player** (2.7.12) - Lottie animation player

### Backend
- **FastAPI** - Python web framework
- **Google Gemini API** - AI pronunciation assessment
- **Uvicorn** - ASGI server

---

## File Structure

```
static/
  └── index.html          # Single-page application (complete)

assets/
  └── mascot/
      ├── idle/           # Default state
      ├── greetings/      # Recording state
      ├── happy/          # Good performance
      ├── cheerful/       # Encouraging
      ├── winner/         # Perfect score
      └── upset/          # Needs practice
```

---

## Configuration

Audio format is configured in `.env`:

```env
TEMP_FILE_EXTENSION=.webm
RECORDED_AUDIO_MIME_TYPE=audio/webm
```

The browser's MediaRecorder API outputs WebM format by default.

---

## Browser Compatibility

✅ Chrome/Edge (recommended)
✅ Firefox
✅ Safari (macOS/iOS)
⚠️ Requires microphone access permission

---

## API Endpoints

The frontend uses these backend endpoints:

- `GET /` - Serves the web application
- `POST /api/v1/assess` - Pronunciation assessment
- `GET /health` - Health check
- `GET /assets/*` - Static mascot animations

---

## Development

### Run with Auto-reload
```bash
just dev
```

### Check Logs
Server logs appear in the terminal, showing:
- Request timing
- Assessment results
- Error details

---

## Customization

### Change Mascot Animations

1. Replace files in `assets/mascot/[emotion]/`
2. Keep same folder structure
3. Use `.lottie` or `.json` format
4. Update `animations` object in `index.html` if needed

### Modify Styling

Edit the `<style>` section in `static/index.html`:
- Colors are controlled by Pico CSS variables
- Custom styles are minimal (< 100 lines)
- Uses CSS Grid/Flexbox for layout

### Add More Sentences

Update the default value in the input field:
```html
<input id="expectedText" value="Your sentence here">
```

---

## Troubleshooting

### Microphone Not Working
- Grant microphone permissions in browser
- Check browser console for errors
- Try HTTPS (required on some browsers)

### Animations Not Loading
- Check `/assets/mascot/` directory exists
- Verify `.lottie` files are present
- Check browser console for 404 errors

### API Errors
- Ensure Gemini API key is set in `.env`
- Check server logs for details
- Verify backend is running on port 8000

---

## Performance

**Total Page Size:** ~130 KB (CDN resources)
**Mascot Animations:** ~150 KB (all 6 animations)
**Initial Load:** < 1 second
**Assessment Time:** 2-5 seconds (Gemini API processing)

---

## Credits

**Icons:** [Lucide Icons](https://lucide.dev)
**CSS:** [Pico CSS](https://picocss.com)
**Animations:** [Lottie / dotLottie](https://lottiefiles.com)
**AI:** [Google Gemini API](https://ai.google.dev/gemini-api)
