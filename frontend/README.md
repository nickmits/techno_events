# Techno Events - Frontend

A cyberpunk-themed React + TypeScript application for discovering techno and electronic music events with conversational AI responses.

## Features

✨ **Conversational AI** - Natural language event search with intelligent responses
🎨 **Techno Theme** - Dark, neon-lit cyberpunk design with animated effects
🎵 **Background Music** - Optional ambient music player
📱 **Responsive** - Works perfectly on mobile, tablet, and desktop
⚡ **Real-time Search** - Instant event discovery from multiple sources
🔍 **Smart Filters** - Location and date range filtering

## Tech Stack

- **React** 19.1.1 with TypeScript
- **Material UI (MUI)** v6.5.0 - Modern component library
- **Vite** 7.1.7 - Fast build tool and dev server
- **Emotion** - CSS-in-JS styling for MUI
- **Axios** - HTTP client for API requests
- **Vitest** - Fast unit test framework
- **React Testing Library** - Component testing utilities

## Prerequisites

- Node.js (v18 or higher)
- npm or pnpm
- Backend API running on `http://localhost:8000`

## Installation

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment:**
   - The `.env` file is configured for local development
   - For production, update `VITE_API_URL` in `.env`

## Running the App

### Development Mode

```bash
npm run dev
```

The app will open at `http://localhost:3000`

### Production Build

```bash
npm run build
```

This creates an optimized production build in the `dist/` folder.

### Preview Production Build

```bash
npm run preview
```

## Testing

### Run Tests

```bash
npm test
```

### Run Tests with UI

```bash
npm run test:ui
```

### Run Tests with Coverage

```bash
npm run test:coverage
```

## Project Structure

```
frontend/
├── public/
│   └── (static assets)
├── src/
│   ├── components/
│   │   ├── EventDisplay.tsx       # Event response display component
│   │   └── EventDisplay.test.tsx  # Component tests
│   ├── services/
│   │   └── api.ts                 # Backend API integration
│   ├── test/
│   │   └── setup.ts               # Vitest configuration
│   ├── App.tsx                    # Main application component
│   ├── main.tsx                   # React entry point
│   ├── theme.ts                   # MUI theme configuration
│   └── types.ts                   # TypeScript type definitions
├── .env                           # Environment variables
├── .gitignore                     # Git ignore rules
├── index.html                     # HTML template
├── package.json                   # Dependencies & scripts
├── tsconfig.json                  # TypeScript configuration
├── vite.config.ts                 # Vite & Vitest configuration
└── README.md                      # This file
```

## Usage

### Basic Search

1. Type your query in natural language:
   - "What events are happening this weekend?"
   - "Find techno events in Athens"
   - "Will Coordinatas organize any events?"

2. Add optional filters:
   - **Location**: Select from Athens, Berlin, London, Amsterdam
   - **Dates**: Set start and end dates

3. Click **SEARCH EVENTS** or press Enter

### Quick Searches

Use the predefined quick search chips for common queries

### Background Music

Click the 🔊/🔇 button in the top-right corner to toggle ambient music

## Design Theme

### Color Palette

- **Neon Cyan**: `#00ffff` - Primary accent
- **Neon Magenta**: `#ff00ff` - Secondary accent
- **Dark Background**: `#0a0a0f` - Main background
- **Card Background**: `#151520` - Content cards

### Typography

- **Orbitron**: Headings and buttons (cyberpunk feel)
- **Rajdhani**: Body text (clean readability)

### Animations

- Grid background animation
- Neon glow effects
- Flicker text animation
- Shimmer card effects
- Pulse loader

## API Integration

The frontend connects to your FastAPI backend at `/api/events`:

**Request (TypeScript):**
```typescript
interface EventsRequest {
  query: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  days_ahead?: number;
}
```

**Response (TypeScript):**
```typescript
interface EventsResponse {
  query: string;
  sources: EventSource[];
  total_sources: number;
  timestamp: string;
}

interface EventSource {
  name: string;
  content: string;
}
```

## Customization

### Change Theme Colors

Edit `src/theme.ts`:
```typescript
const technoTheme = createTheme({
  palette: {
    primary: {
      main: '#00ffff', // Change primary color
    },
    secondary: {
      main: '#ff00ff', // Change secondary color
    },
  },
});
```

### Change Background Music

Edit `src/App.tsx`:
```typescript
<audio
  ref={audioRef}
  loop
  src="YOUR_MUSIC_URL_HERE"
/>
```

### Modify Quick Searches

Edit `src/App.tsx`:
```typescript
const quickSearches = [
  'Your custom search 1',
  'Your custom search 2',
  // ...
];
```

## Troubleshooting

### Backend Connection Error

**Issue:** "Unable to connect to server"

**Solution:**
1. Ensure backend is running: `python -m uvicorn backend.main:app --reload --port 8000`
2. Check `.env` file has correct `VITE_API_URL`
3. Verify CORS is enabled on backend

### Build Errors

**Issue:** Module not found

**Solution:**
```bash
rm -rf node_modules package-lock.json
npm install
```

### TypeScript Errors

**Issue:** Type errors during build

**Solution:**
```bash
npm run build -- --mode development
```

### Styling Issues

**Issue:** Fonts not loading

**Solution:** Check internet connection (Google Fonts require internet)

## Performance Tips

- Background music is optional and won't affect functionality
- Vite provides instant hot module replacement (HMR)
- MUI components are tree-shakeable for optimal bundle size
- API responses can be cached by the backend

## Browser Support

- Chrome (recommended)
- Firefox
- Safari
- Edge

## Contributing

Feel free to customize the design, add new features, or improve the user experience!

## License

MIT
