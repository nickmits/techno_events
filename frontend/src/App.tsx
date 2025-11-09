import React, { useState, useRef, useEffect } from 'react';
import {
  ThemeProvider,
  CssBaseline,
  Container,
  Box,
  Typography,
  TextField,
  Button,
  IconButton,
  Chip,
  Paper,
} from '@mui/material';
import {
  Send as SendIcon,
  VolumeUp as VolumeUpIcon,
  VolumeOff as VolumeOffIcon,
} from '@mui/icons-material';
import technoTheme from './theme';
import EventDisplay from './components/EventDisplay';
import ChatMessage from './components/ChatMessage';
import { fetchEvents } from './services/api';
import type { EventsResponse } from './types';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  response?: EventsResponse;
}

function App() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [musicPlaying, setMusicPlaying] = useState(false);

  // Interrupt handling for human-in-the-loop
  const [pendingInterrupt, setPendingInterrupt] = useState<{
    threadId: string;
    originalQuery: string;
  } | null>(null);

  const audioRef = useRef<HTMLAudioElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const quickSearches = [
    'What events are happening this weekend?',
    'Tell me about techno events next week',
    'Find underground events in Athens',
  ];

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (messageText?: string) => {
    const textToSend = messageText || input.trim();
    if (!textToSend) return;

    // Clear input immediately
    setInput('');

    // Add user message to chat
    const userMessage: Message = {
      role: 'user',
      content: textToSend,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    setLoading(true);
    setError(null);

    try {
      let data: EventsResponse;

      // Check if this is a response to an interrupt (location request)
      if (pendingInterrupt) {
        // Resume the interrupted thread
        data = await fetchEvents(pendingInterrupt.originalQuery, {
          thread_id: pendingInterrupt.threadId,
          resume_value: textToSend,
        });
        setPendingInterrupt(null);
      } else {
        // New query
        data = await fetchEvents(textToSend);
      }

      // Check if response contains an interrupt (asking for location)
      if (data.interrupt && data.thread_id) {
        // Store the interrupt state
        setPendingInterrupt({
          threadId: data.thread_id,
          originalQuery: textToSend,
        });

        // Add system message asking for location
        const systemMessage: Message = {
          role: 'system',
          content: data.interrupt.message,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, systemMessage]);
      } else if (data.final_response || data.intro) {
        // Add assistant response with events
        const assistantMessage: Message = {
          role: 'assistant',
          content: data.final_response || data.intro || 'Here are the events I found:',
          timestamp: new Date().toISOString(),
          response: data,
        };
        setMessages((prev) => [...prev, assistantMessage]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      const errorMessage: Message = {
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'An error occurred'}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickSearch = (searchQuery: string) => {
    handleSend(searchQuery);
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

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <ThemeProvider theme={technoTheme}>
      <CssBaseline />
      <Box
        sx={{
          minHeight: '100vh',
          background: 'linear-gradient(135deg, #0a0014 0%, #1a0030 50%, #0a0014 100%)',
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          '&::before': {
            content: '""',
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundImage: `
              radial-gradient(circle at 20% 50%, rgba(0, 255, 255, 0.15) 0%, transparent 50%),
              radial-gradient(circle at 80% 80%, rgba(255, 0, 255, 0.15) 0%, transparent 50%),
              radial-gradient(circle at 40% 20%, rgba(57, 255, 20, 0.1) 0%, transparent 50%)
            `,
            animation: 'colorPulse 8s ease-in-out infinite',
            pointerEvents: 'none',
            '@keyframes colorPulse': {
              '0%, 100%': { opacity: 0.6 },
              '50%': { opacity: 1 },
            },
          },
          '&::after': {
            content: '""',
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundImage: `
              linear-gradient(rgba(0, 255, 255, 0.02) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255, 0, 255, 0.02) 1px, transparent 1px)
            `,
            backgroundSize: '60px 60px',
            animation: 'gridFloat 20s linear infinite',
            pointerEvents: 'none',
            '@keyframes gridFloat': {
              '0%': { transform: 'translate(0, 0)' },
              '100%': { transform: 'translate(60px, 60px)' },
            },
          },
        }}
      >
        <Container
          maxWidth="lg"
          sx={{
            position: 'relative',
            py: 2,
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            maxHeight: '100vh',
          }}
        >
          {/* Header */}
          <Box sx={{ textAlign: 'center', mb: 4, position: 'relative' }}>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
              <IconButton
                onClick={toggleMusic}
                sx={{
                  color: 'primary.main',
                  backgroundColor: 'rgba(0, 255, 255, 0.1)',
                  border: '2px solid',
                  borderColor: 'primary.main',
                  boxShadow: '0 0 20px rgba(0, 255, 255, 0.4)',
                  '&:hover': {
                    backgroundColor: 'rgba(0, 255, 255, 0.2)',
                    boxShadow: '0 0 30px rgba(0, 255, 255, 0.6)',
                    transform: 'scale(1.1)',
                  },
                }}
              >
                {musicPlaying ? <VolumeUpIcon /> : <VolumeOffIcon />}
              </IconButton>
            </Box>

            <Box
              sx={{
                position: 'relative',
                display: 'inline-block',
                animation: 'float 3s ease-in-out infinite',
                '@keyframes float': {
                  '0%, 100%': { transform: 'translateY(0)' },
                  '50%': { transform: 'translateY(-10px)' },
                },
              }}
            >
              <Typography
                variant="h3"
                sx={{
                  fontWeight: 'bold',
                  mb: 1,
                  background: 'linear-gradient(90deg, #00ffff, #ff00ff, #00ffff)',
                  backgroundSize: '200% 100%',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  animation: 'gradientShift 3s ease-in-out infinite',
                  '@keyframes gradientShift': {
                    '0%, 100%': { backgroundPosition: '0% 50%' },
                    '50%': { backgroundPosition: '100% 50%' },
                  },
                }}
              >
                ▶ Athens TechnoMate AI
              </Typography>
              <Typography
                variant="body1"
                sx={{
                  color: 'secondary.main',
                  textTransform: 'uppercase',
                  letterSpacing: '0.15em',
                  fontWeight: 600,
                  opacity: 0.9,
                }}
              >
                Your AI Techno Guide
              </Typography>
            </Box>
          </Box>

          {/* Quick Searches */}
          {messages.length === 0 && (
            <Box sx={{ mb: 3 }}>
              <Typography
                variant="subtitle2"
                sx={{
                  color: 'text.secondary',
                  mb: 2,
                  textTransform: 'uppercase',
                  letterSpacing: '0.15em',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                }}
              >
                Quick Searches
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
                {quickSearches.map((search, index) => (
                  <Chip
                    key={index}
                    label={search}
                    onClick={() => handleQuickSearch(search)}
                    sx={{
                      backgroundColor: 'rgba(0, 255, 255, 0.1)',
                      border: '2px solid rgba(0, 255, 255, 0.4)',
                      color: 'primary.main',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                      py: 2.5,
                      transition: 'all 0.3s ease',
                      '&:hover': {
                        backgroundColor: 'rgba(0, 255, 255, 0.2)',
                        borderColor: 'primary.main',
                        boxShadow: '0 0 20px rgba(0, 255, 255, 0.5), 0 0 40px rgba(255, 0, 255, 0.3)',
                        transform: 'translateY(-3px)',
                      },
                    }}
                  />
                ))}
              </Box>
            </Box>
          )}

          {/* Chat Messages Area */}
          <Paper
            sx={{
              flex: 1,
              mb: 2,
              p: 3,
              backgroundColor: 'rgba(10, 0, 20, 0.7)',
              backdropFilter: 'blur(20px)',
              border: '2px solid rgba(0, 255, 255, 0.2)',
              borderRadius: '20px',
              boxShadow: '0 8px 32px rgba(0, 255, 255, 0.2), 0 0 16px rgba(255, 0, 255, 0.1)',
              overflowY: 'auto',
              minHeight: '400px',
              maxHeight: 'calc(100vh - 320px)',
            }}
          >
            {messages.length === 0 ? (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                  flexDirection: 'column',
                  gap: 2,
                }}
              >
                <Typography
                  variant="h6"
                  sx={{ color: 'text.secondary', textAlign: 'center' }}
                >
                  Ask me about techno events in Athens
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ color: 'text.secondary', textAlign: 'center' }}
                >
                  Try: "What's happening this weekend?" or "Find events at SMUT"
                </Typography>
              </Box>
            ) : (
              <>
                {messages.map((message, index) => (
                  <React.Fragment key={index}>
                    <ChatMessage
                      role={message.role}
                      content={message.content}
                      timestamp={message.timestamp}
                    />
                    {/* Show events if this message has a response */}
                    {message.response && (
                      <Box sx={{ mb: 2 }}>
                        <EventDisplay
                          response={message.response}
                          loading={false}
                          error={null}
                        />
                      </Box>
                    )}
                  </React.Fragment>
                ))}
                {loading && (
                  <ChatMessage
                    role="assistant"
                    content="Searching for events..."
                    timestamp={new Date().toISOString()}
                  />
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </Paper>

          {/* Input Area */}
          <Paper
            sx={{
              p: 2,
              backgroundColor: 'rgba(10, 0, 20, 0.8)',
              backdropFilter: 'blur(20px)',
              borderRadius: '20px',
              border: '2px solid',
              borderColor: pendingInterrupt
                ? 'warning.main'
                : 'rgba(0, 255, 255, 0.3)',
              boxShadow: pendingInterrupt
                ? '0 0 30px rgba(255, 255, 0, 0.5), 0 0 60px rgba(255, 255, 0, 0.3)'
                : '0 8px 32px rgba(0, 255, 255, 0.2), 0 0 16px rgba(255, 0, 255, 0.1)',
            }}
          >
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                fullWidth
                multiline
                maxRows={3}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={
                  pendingInterrupt
                    ? 'Enter your location...'
                    : 'Ask about events in Athens...'
                }
                variant="outlined"
                autoFocus
                disabled={loading}
              />
              <Button
                variant="contained"
                onClick={() => handleSend()}
                disabled={loading || !input.trim()}
                sx={{
                  minWidth: '60px',
                  '&:disabled': {
                    opacity: 0.4,
                  },
                }}
              >
                <SendIcon />
              </Button>
            </Box>
          </Paper>
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
