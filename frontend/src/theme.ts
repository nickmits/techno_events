import { createTheme } from '@mui/material/styles';

// Techno Rave theme colors
const technoTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#00ffff', // Bright cyan (rave lights)
      light: '#66ffff',
      dark: '#00cccc',
      contrastText: '#000000',
    },
    secondary: {
      main: '#ff00ff', // Magenta (rave lights)
      light: '#ff66ff',
      dark: '#cc00cc',
      contrastText: '#000000',
    },
    background: {
      default: '#0a0014', // Deep purple-black
      paper: '#150020', // Dark purple
    },
    text: {
      primary: '#ffffff',
      secondary: '#b8b8ff',
    },
    success: {
      main: '#39ff14', // Neon green
    },
    error: {
      main: '#ff073a', // Neon pink
    },
    warning: {
      main: '#ffff00', // Electric yellow
    },
    info: {
      main: '#00ddff', // Bright cyan
    },
  },
  typography: {
    fontFamily: '"Rajdhani", "Arial Black", sans-serif',
    h1: {
      fontFamily: '"Russo One", sans-serif',
      fontWeight: 400,
      textShadow: '0 0 20px #00ffff, 0 0 40px #ff00ff, 0 0 60px #00ffff',
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
    },
    h2: {
      fontFamily: '"Russo One", sans-serif',
      fontWeight: 400,
      textShadow: '0 0 15px #00ffff, 0 0 30px #ff00ff',
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
    },
    h3: {
      fontFamily: '"Russo One", sans-serif',
      fontWeight: 400,
      textShadow: '0 0 10px #00ffff, 0 0 20px #ff00ff',
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
    },
    h4: {
      fontFamily: '"Rajdhani", sans-serif',
      fontWeight: 700,
      letterSpacing: '0.04em',
    },
    h5: {
      fontFamily: '"Rajdhani", sans-serif',
      fontWeight: 700,
      letterSpacing: '0.03em',
    },
    h6: {
      fontFamily: '"Rajdhani", sans-serif',
      fontWeight: 700,
      letterSpacing: '0.02em',
    },
    body1: {
      fontFamily: '"Rajdhani", sans-serif',
      fontSize: '1.05rem',
      fontWeight: 500,
    },
    body2: {
      fontFamily: '"Rajdhani", sans-serif',
      fontSize: '0.95rem',
      fontWeight: 500,
    },
    button: {
      fontFamily: '"Rajdhani", sans-serif',
      fontWeight: 700,
      letterSpacing: '0.12em',
      textTransform: 'uppercase',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '30px',
          textTransform: 'uppercase',
          padding: '12px 32px',
          border: '2px solid',
          boxShadow: '0 0 20px rgba(0, 255, 255, 0.5), 0 0 40px rgba(255, 0, 255, 0.3)',
          transition: 'all 0.3s ease',
          position: 'relative',
          overflow: 'hidden',
          background: 'linear-gradient(135deg, rgba(0, 255, 255, 0.1), rgba(255, 0, 255, 0.1))',
          '&:hover': {
            boxShadow: '0 0 30px rgba(0, 255, 255, 0.8), 0 0 60px rgba(255, 0, 255, 0.6)',
            transform: 'scale(1.05) translateY(-2px)',
          },
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: '-100%',
            width: '100%',
            height: '100%',
            background: 'linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent)',
            transition: 'left 0.5s',
          },
          '&:hover::before': {
            left: '100%',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: '16px',
          border: '2px solid',
          borderColor: 'rgba(0, 255, 255, 0.3)',
          boxShadow: '0 8px 32px rgba(0, 255, 255, 0.2), 0 0 16px rgba(255, 0, 255, 0.1)',
          background: 'linear-gradient(135deg, rgba(10, 0, 20, 0.95) 0%, rgba(20, 0, 30, 0.95) 100%)',
          backdropFilter: 'blur(10px)',
          transition: 'all 0.4s ease',
          position: 'relative',
          overflow: 'hidden',
          '&:hover': {
            borderColor: 'rgba(0, 255, 255, 0.8)',
            boxShadow: '0 12px 48px rgba(0, 255, 255, 0.4), 0 0 32px rgba(255, 0, 255, 0.3)',
            transform: 'translateY(-8px) scale(1.02)',
          },
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: '-100%',
            width: '100%',
            height: '100%',
            background: 'linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent)',
            transition: 'left 0.6s',
          },
          '&:hover::before': {
            left: '100%',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: '12px',
            backgroundColor: 'rgba(10, 0, 20, 0.8)',
            '& fieldset': {
              borderColor: 'rgba(0, 255, 255, 0.4)',
              borderWidth: '2px',
            },
            '&:hover fieldset': {
              borderColor: 'rgba(0, 255, 255, 0.7)',
            },
            '&.Mui-focused fieldset': {
              borderColor: '#00ffff',
              boxShadow: '0 0 20px rgba(0, 255, 255, 0.5), 0 0 40px rgba(255, 0, 255, 0.3)',
            },
          },
          '& .MuiInputBase-input': {
            color: '#ffffff',
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: '20px',
          fontWeight: 700,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
  },
});

export default technoTheme;
