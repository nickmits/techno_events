import React, { useState, useRef } from 'react';
import {
  ThemeProvider,
  CssBaseline,
  Container,
  Box,
  Typography,
  TextField,
  Button,
  Grid,
  IconButton,
  Chip,
  Paper,
} from '@mui/material';
import {
  Search as SearchIcon,
  VolumeUp as VolumeUpIcon,
  VolumeOff as VolumeOffIcon,
  PlayArrow as PlayArrowIcon,
} from '@mui/icons-material';
import technoTheme from './theme';
import EventDisplay from './components/EventDisplay';
import { fetchEvents } from './services/api';
import type { EventsResponse } from './types';

function App() {
  const [query, setQuery] = useState('');
  const [userLocation, setUserLocation] = useState('');
  const [response, setResponse] = useState<EventsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [musicPlaying, setMusicPlaying] = useState(false);

  const audioRef = useRef<HTMLAudioElement>(null);

  const quickSearches = [
    'What events are happening this weekend in Athens?',
    'Tell me about techno events next week',
    'Will Coordinatas have any events?',
    'Find underground events in Athens',
  ];

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const data = await fetchEvents(
        query,
        userLocation || undefined
      );
      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickSearch = (searchQuery: string) => {
    setQuery(searchQuery);
  };

  const toggleMusic = () => {
    if (audioRef.current) {
      if (musicPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setMusicPlaying(!musicPlaying);
    }
  };

  return (
    <ThemeProvider theme={technoTheme}>
      <CssBaseline />
      <Box
        sx={{
          minHeight: '100vh',
          background: 'linear-gradient(180deg, #0a0a0f 0%, #1a0a1f 100%)',
          position: 'relative',
          overflow: 'hidden',
          '&::before': {
            content: '""',
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundImage: `
              linear-gradient(rgba(0, 255, 255, 0.03) 1px, transparent 1px),
              linear-gradient(90deg, rgba(0, 255, 255, 0.03) 1px, transparent 1px)
            `,
            backgroundSize: '50px 50px',
            animation: 'gridMove 20s linear infinite',
            pointerEvents: 'none',
            '@keyframes gridMove': {
              '0%': { transform: 'translateY(0)' },
              '100%': { transform: 'translateY(50px)' },
            },
          },
        }}
      >
        <Container maxWidth="lg" sx={{ position: 'relative', py: 4 }}>
          {/* Header */}
          <Box sx={{ textAlign: 'center', mb: 6 }}>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2, gap: 1 }}>
              <IconButton
                onClick={toggleMusic}
                sx={{
                  color: 'primary.main',
                  '&:hover': {
                    backgroundColor: 'rgba(0, 255, 255, 0.1)',
                  },
                }}
              >
                {musicPlaying ? <VolumeUpIcon /> : <VolumeOffIcon />}
              </IconButton>
            </Box>

            <Typography
              variant="h2"
              sx={{
                fontWeight: 'bold',
                mb: 1,
                animation: 'flicker 3s infinite alternate',
                '@keyframes flicker': {
                  '0%, 100%': { opacity: 1 },
                  '41%, 43%': { opacity: 0.8 },
                  '47%, 50%': { opacity: 0.9 },
                },
              }}
            >
              <PlayArrowIcon
                sx={{ fontSize: 'inherit', verticalAlign: 'middle', mr: 1 }}
              />
              TECHNO EVENTS
            </Typography>
            <Typography
              variant="h6"
              sx={{
                color: 'secondary.main',
                textTransform: 'uppercase',
                letterSpacing: 3,
              }}
            >
              Discover the Underground
            </Typography>
          </Box>

          {/* Search Form */}
          <Paper
            component="form"
            onSubmit={handleSearch}
            sx={{
              p: 3,
              mb: 4,
              backgroundColor: 'rgba(21, 21, 32, 0.8)',
              backdropFilter: 'blur(10px)',
              border: '1px solid rgba(0, 255, 255, 0.2)',
            }}
          >
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="What events are you looking for?"
                  variant="outlined"
                  InputProps={{
                    startAdornment: (
                      <SearchIcon sx={{ mr: 1, color: 'primary.main' }} />
                    ),
                  }}
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  value={userLocation}
                  onChange={(e) => setUserLocation(e.target.value)}
                  placeholder="Your location (e.g., Syntagma Square, Monastiraki)"
                  variant="outlined"
                  helperText="Enter your location to see distances and travel times"
                  sx={{
                    '& .MuiFormHelperText-root': {
                      color: 'text.secondary',
                    },
                  }}
                />
              </Grid>

              <Grid item xs={12}>
                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  size="large"
                  disabled={loading || !query.trim()}
                  sx={{
                    py: 1.5,
                    fontSize: '1.1rem',
                  }}
                >
                  {loading ? 'SEARCHING...' : 'SEARCH EVENTS'}
                </Button>
              </Grid>
            </Grid>
          </Paper>

          {/* Quick Searches */}
          <Box sx={{ mb: 4 }}>
            <Typography
              variant="subtitle1"
              sx={{
                color: 'text.secondary',
                mb: 2,
                textTransform: 'uppercase',
                letterSpacing: 1,
              }}
            >
              Quick Searches
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {quickSearches.map((search, index) => (
                <Chip
                  key={index}
                  label={search}
                  onClick={() => handleQuickSearch(search)}
                  sx={{
                    backgroundColor: 'rgba(0, 255, 255, 0.1)',
                    border: '1px solid rgba(0, 255, 255, 0.3)',
                    color: 'primary.main',
                    '&:hover': {
                      backgroundColor: 'rgba(0, 255, 255, 0.2)',
                      borderColor: 'primary.main',
                    },
                  }}
                />
              ))}
            </Box>
          </Box>

          {/* Event Display */}
          <EventDisplay response={response} loading={loading} error={error} />
        </Container>

        {/* Background Music */}
        <audio
          ref={audioRef}
          loop
          src="https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3"
        />
      </Box>
    </ThemeProvider>
  );
}

export default App;
