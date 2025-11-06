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
    if (source.toLowerCase().includes('goout') || source.toLowerCase().includes('go-out')) return 'error';
    return 'success';
  };

  const getSourceLabel = (source: string) => {
    if (source.toLowerCase().includes('ra')) return 'RA';
    if (source.toLowerCase().includes('goout') || source.toLowerCase().includes('go-out')) return 'GO-OUT';
    return 'SAVED';
  };

  return (
    <Card
      sx={{
        position: 'relative',
        overflow: 'hidden',
        transition: 'all 0.4s ease',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <CardContent sx={{ p: 3, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Source Badge */}
        <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Chip
            label={getSourceLabel(event.source)}
            color={getSourceColor(event.source)}
            size="small"
            sx={{
              fontWeight: 700,
              textTransform: 'uppercase',
              fontSize: '0.7rem',
              letterSpacing: '0.08em',
            }}
          />
          {event.attending && parseInt(event.attending) > 0 && (
            <Chip
              label={`${event.attending} attending`}
              size="small"
              sx={{
                backgroundColor: 'rgba(255, 0, 255, 0.2)',
                color: 'secondary.main',
                fontWeight: 600,
                fontSize: '0.7rem',
                border: '2px solid',
                borderColor: 'secondary.main',
              }}
            />
          )}
        </Box>

        {/* Event Title */}
        <Typography
          variant="h6"
          sx={{
            color: 'text.primary',
            mb: 2,
            fontWeight: 700,
            letterSpacing: '0.02em',
            fontSize: '1.05rem',
            lineHeight: 1.4,
          }}
        >
          {event.title}
        </Typography>

        {/* Event Details */}
        <Stack spacing={1.5} sx={{ flexGrow: 1 }}>
          {/* Venue */}
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <PlaceIcon sx={{ color: 'primary.main', fontSize: 18, mt: 0.3 }} />
            <Typography variant="body2" sx={{ color: 'text.primary', fontSize: '0.85rem', lineHeight: 1.5 }}>
              {event.venue}
            </Typography>
          </Box>

          {/* Distance */}
          {event.distance_km !== undefined && event.distance_km !== null && event.distance_km !== Infinity && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                p: 1,
                border: '1px solid',
                borderColor: 'error.main',
                backgroundColor: 'rgba(255, 7, 58, 0.05)',
              }}
            >
              <DistanceIcon sx={{ color: 'error.main', fontSize: 18 }} />
              <Typography variant="body2" sx={{ color: 'error.main', fontWeight: 'bold', fontSize: '0.85rem' }}>
                {event.distance_km.toFixed(1)} KM
              </Typography>
            </Box>
          )}

          {/* Travel Times */}
          {(event.drive_time_min !== undefined || event.walk_time_min !== undefined) && (
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {event.drive_time_min !== undefined && event.drive_time_min !== null && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <DriveIcon sx={{ color: 'info.main', fontSize: 16 }} />
                  <Typography variant="body2" sx={{ color: 'info.main', fontSize: '0.75rem' }}>
                    {event.drive_time_min}m
                  </Typography>
                </Box>
              )}
              {event.walk_time_min !== undefined && event.walk_time_min !== null && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <WalkIcon sx={{ color: 'success.main', fontSize: 16 }} />
                  <Typography variant="body2" sx={{ color: 'success.main', fontSize: '0.75rem' }}>
                    {event.walk_time_min}m
                  </Typography>
                </Box>
              )}
            </Box>
          )}

          {/* Date */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CalendarIcon sx={{ color: 'primary.main', fontSize: 18 }} />
            <Typography variant="body2" sx={{ color: 'primary.main', fontWeight: 700, fontSize: '0.85rem' }}>
              {event.event_date}
            </Typography>
          </Box>

          {/* Music Types */}
          {event.music_types && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <MusicIcon sx={{ color: 'primary.main', fontSize: 18 }} />
              <Typography variant="body2" sx={{ color: 'text.primary', fontSize: '0.8rem' }}>
                {event.music_types}
              </Typography>
            </Box>
          )}

          {/* Link */}
          {event.url && (
            <Box sx={{ mt: 'auto', pt: 2 }}>
              <Link
                href={event.url}
                target="_blank"
                rel="noopener noreferrer"
                sx={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 1,
                  width: '100%',
                  px: 3,
                  py: 1.5,
                  borderRadius: '30px',
                  border: '2px solid',
                  borderColor: 'primary.main',
                  backgroundColor: 'rgba(0, 255, 255, 0.1)',
                  color: 'primary.main',
                  textDecoration: 'none',
                  fontWeight: 700,
                  fontSize: '0.85rem',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  transition: 'all 0.3s',
                  boxShadow: '0 0 15px rgba(0, 255, 255, 0.3)',
                  '&:hover': {
                    backgroundColor: 'rgba(0, 255, 255, 0.2)',
                    boxShadow: '0 0 25px rgba(0, 255, 255, 0.6), 0 0 40px rgba(255, 0, 255, 0.3)',
                    transform: 'translateY(-2px) scale(1.02)',
                  },
                }}
              >
                View Event <LinkIcon sx={{ fontSize: 18 }} />
              </Link>
            </Box>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default EventCard;
