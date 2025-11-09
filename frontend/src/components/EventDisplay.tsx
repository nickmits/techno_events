import React from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Grid,
} from '@mui/material';
import EventCard from './EventCard';
import type { EventsResponse } from '../types';

interface EventDisplayProps {
  response: EventsResponse | null;
  loading: boolean;
  error: string | null;
}

const EventDisplay: React.FC<EventDisplayProps> = ({
  response,
  loading,
  error,
}) => {
  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '300px',
          gap: 2,
        }}
      >
        <CircularProgress
          size={60}
          sx={{
            color: 'primary.main',
            filter: 'drop-shadow(0 0 10px rgba(0, 255, 255, 0.6))',
          }}
        />
        <Typography
          variant="h6"
          sx={{
            color: 'primary.main',
            animation: 'pulse 2s infinite',
            '@keyframes pulse': {
              '0%, 100%': { opacity: 1 },
              '50%': { opacity: 0.5 },
            },
          }}
        >
          SCANNING EVENTS DATABASE...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert
        severity="error"
        sx={{
          backgroundColor: 'rgba(255, 7, 58, 0.1)',
          border: '1px solid #ff073a',
          borderRadius: 0,
          color: '#ff073a',
          '& .MuiAlert-icon': {
            color: '#ff073a',
          },
        }}
      >
        <Typography variant="body1" fontWeight="bold">
          ERROR
        </Typography>
        <Typography variant="body2">{error}</Typography>
      </Alert>
    );
  }

  if (!response) {
    return null;
  }

  return (
    <Box sx={{ mt: 2 }}>

      {/* Events Grid */}
      {response.events && response.events.length > 0 && (
        <Box sx={{ mb: 4 }}>
          <Typography
            variant="h6"
            sx={{
              color: 'secondary.main',
              mb: 3,
              textTransform: 'uppercase',
              letterSpacing: 1,
            }}
          >
            {response.events.length} Event{response.events.length !== 1 ? 's' : ''} Found
          </Typography>

          <Grid container spacing={3}>
            {response.events.map((event, index) => (
              <Grid item xs={12} sm={6} md={4} key={index}>
                <EventCard event={event} />
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Footer */}
      <Typography
        variant="caption"
        sx={{
          display: 'block',
          mt: 3,
          color: 'text.secondary',
          textAlign: 'center',
        }}
      >
        Found {response.events?.length || 0} events •{' '}
        {new Date(response.timestamp).toLocaleString()}
      </Typography>
    </Box>
  );
};

export default EventDisplay;
