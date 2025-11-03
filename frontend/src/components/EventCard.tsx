import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Link,
  Stack,
} from '@mui/material';
import {
  Place as PlaceIcon,
  CalendarToday as CalendarIcon,
  People as PeopleIcon,
  MusicNote as MusicIcon,
  OpenInNew as LinkIcon,
  NearMe as DistanceIcon,
  DirectionsCar as DriveIcon,
  DirectionsWalk as WalkIcon,
} from '@mui/icons-material';
import type { Event } from '../types';

interface EventCardProps {
  event: Event;
}

const EventCard: React.FC<EventCardProps> = ({ event }) => {
  // Determine source color
  const getSourceColor = (source: string) => {
    if (source.toLowerCase().includes('ra')) return 'primary';
    if (source.toLowerCase().includes('goout') || source.toLowerCase().includes('go-out')) return 'secondary';
    return 'default';
  };

  const getSourceLabel = (source: string) => {
    if (source.toLowerCase().includes('ra')) return 'Resident Advisor';
    if (source.toLowerCase().includes('goout') || source.toLowerCase().includes('go-out')) return 'GO-OUT';
    return 'Database';
  };

  return (
    <Card
      sx={{
        position: 'relative',
        overflow: 'hidden',
        transition: 'all 0.3s ease',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: '0 0 40px rgba(0, 255, 255, 0.3)',
        },
      }}
    >
      <CardContent sx={{ p: 3 }}>
        {/* Source Badge */}
        <Box sx={{ mb: 2 }}>
          <Chip
            label={getSourceLabel(event.source)}
            color={getSourceColor(event.source)}
            size="small"
            sx={{
              fontWeight: 'bold',
              textTransform: 'uppercase',
              fontSize: '0.7rem',
            }}
          />
        </Box>

        {/* Event Title */}
        <Typography
          variant="h6"
          sx={{
            color: 'primary.main',
            mb: 2,
            fontWeight: 'bold',
            letterSpacing: 0.5,
          }}
        >
          {event.title}
        </Typography>

        {/* Event Details */}
        <Stack spacing={1.5}>
          {/* Venue */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <PlaceIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
            <Typography variant="body2" sx={{ color: 'text.primary' }}>
              {event.venue}
              {event.location && ` • ${event.location}`}
            </Typography>
          </Box>

          {/* Distance */}
          {event.distance_km !== undefined && event.distance_km !== null && event.distance_km !== Infinity && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <DistanceIcon sx={{ color: 'secondary.main', fontSize: 20 }} />
              <Typography variant="body2" sx={{ color: 'secondary.main', fontWeight: 'bold' }}>
                {event.distance_km.toFixed(1)} km away
              </Typography>
            </Box>
          )}

          {/* Driving Time */}
          {event.drive_time_min !== undefined && event.drive_time_min !== null && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <DriveIcon sx={{ color: 'info.main', fontSize: 20 }} />
              <Typography variant="body2" sx={{ color: 'text.primary' }}>
                {event.drive_time_min} min drive
              </Typography>
            </Box>
          )}

          {/* Walking Time */}
          {event.walk_time_min !== undefined && event.walk_time_min !== null && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <WalkIcon sx={{ color: 'success.main', fontSize: 20 }} />
              <Typography variant="body2" sx={{ color: 'text.primary' }}>
                {event.walk_time_min} min walk
              </Typography>
            </Box>
          )}

          {/* Date */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CalendarIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
            <Typography variant="body2" sx={{ color: 'text.primary' }}>
              {event.event_date}
            </Typography>
          </Box>

          {/* Attending */}
          {event.attending && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <PeopleIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
              <Typography variant="body2" sx={{ color: 'text.primary' }}>
                {event.attending} attending
              </Typography>
            </Box>
          )}

          {/* Music Types */}
          {event.music_types && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <MusicIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
              <Typography variant="body2" sx={{ color: 'text.primary' }}>
                {event.music_types}
              </Typography>
            </Box>
          )}

          {/* Link */}
          {event.url && (
            <Box sx={{ mt: 2 }}>
              <Link
                href={event.url}
                target="_blank"
                rel="noopener noreferrer"
                sx={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 0.5,
                  color: 'primary.main',
                  textDecoration: 'none',
                  fontWeight: 'bold',
                  fontSize: '0.9rem',
                  transition: 'all 0.2s',
                  '&:hover': {
                    textDecoration: 'underline',
                    gap: 1,
                  },
                }}
              >
                View Event <LinkIcon sx={{ fontSize: 16 }} />
              </Link>
            </Box>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default EventCard;
