import React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import { PersonOutline, SmartToy } from '@mui/icons-material';

interface ChatMessageProps {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ role, content, timestamp }) => {
  const isUser = role === 'user';
  const isSystem = role === 'system';

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        mb: 2,
        animation: 'slideIn 0.3s ease-out',
        '@keyframes slideIn': {
          from: {
            opacity: 0,
            transform: isUser ? 'translateX(20px)' : 'translateX(-20px)',
          },
          to: {
            opacity: 1,
            transform: 'translateX(0)',
          },
        },
      }}
    >
      <Box
        sx={{
          display: 'flex',
          maxWidth: '80%',
          flexDirection: isUser ? 'row-reverse' : 'row',
          gap: 1.5,
        }}
      >
        {/* Avatar */}
        <Box
          sx={{
            width: 40,
            height: 40,
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            backgroundColor: isUser
              ? 'rgba(0, 255, 255, 0.2)'
              : isSystem
              ? 'rgba(255, 255, 0, 0.2)'
              : 'rgba(255, 0, 255, 0.2)',
            border: '2px solid',
            borderColor: isUser
              ? 'primary.main'
              : isSystem
              ? 'warning.main'
              : 'secondary.main',
            boxShadow: isUser
              ? '0 0 15px rgba(0, 255, 255, 0.4)'
              : isSystem
              ? '0 0 15px rgba(255, 255, 0, 0.4)'
              : '0 0 15px rgba(255, 0, 255, 0.4)',
          }}
        >
          {isUser ? (
            <PersonOutline sx={{ color: 'primary.main', fontSize: 22 }} />
          ) : (
            <SmartToy
              sx={{
                color: isSystem ? 'warning.main' : 'secondary.main',
                fontSize: 22,
              }}
            />
          )}
        </Box>

        {/* Message Content */}
        <Paper
          sx={{
            p: 2,
            backgroundColor: isUser
              ? 'rgba(0, 255, 255, 0.08)'
              : isSystem
              ? 'rgba(255, 255, 0, 0.08)'
              : 'rgba(255, 0, 255, 0.08)',
            border: '2px solid',
            borderColor: isUser
              ? 'rgba(0, 255, 255, 0.3)'
              : isSystem
              ? 'rgba(255, 255, 0, 0.4)'
              : 'rgba(255, 0, 255, 0.3)',
            borderRadius: '16px',
            backdropFilter: 'blur(10px)',
            boxShadow: isUser
              ? '0 4px 16px rgba(0, 255, 255, 0.15)'
              : isSystem
              ? '0 4px 16px rgba(255, 255, 0, 0.2)'
              : '0 4px 16px rgba(255, 0, 255, 0.15)',
          }}
        >
          <Typography
            variant="body1"
            sx={{
              color: 'text.primary',
              lineHeight: 1.7,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontSize: '0.95rem',
            }}
          >
            {content}
          </Typography>
          {timestamp && (
            <Typography
              variant="caption"
              sx={{
                display: 'block',
                mt: 1,
                color: 'text.secondary',
                textAlign: isUser ? 'right' : 'left',
                fontSize: '0.7rem',
                opacity: 0.6,
              }}
            >
              {new Date(timestamp).toLocaleTimeString()}
            </Typography>
          )}
        </Paper>
      </Box>
    </Box>
  );
};

export default ChatMessage;
