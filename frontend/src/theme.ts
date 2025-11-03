import { createTheme } from '@mui/material/styles';

// Techno/Cyberpunk theme colors
const technoTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#00ffff', // Neon cyan
      light: '#66ffff',
      dark: '#00cccc',
      contrastText: '#0a0a0f',
    },
    secondary: {
      main: '#ff00ff', // Neon magenta
      light: '#ff66ff',
      dark: '#cc00cc',
      contrastText: '#0a0a0f',
    },
    background: {
      default: '#0a0a0f', // Dark background
      paper: '#151520', // Card background
    },
    text: {
      primary: '#ffffff',
      secondary: '#b8b8c8',
    },
    success: {
      main: '#39ff14', // Neon green
    },
    error: {
      main: '#ff073a', // Neon red
    },
  },
  typography: {
    fontFamily: '"Orbitron", "Rajdhani", "Roboto", sans-serif',
    h1: {
      fontFamily: '"Orbitron", sans-serif',
      fontWeight: 700,
      textShadow: '0 0 10px #00ffff, 0 0 20px #00ffff',
    },
    h2: {
      fontFamily: '"Orbitron", sans-serif',
      fontWeight: 600,
    },
    h3: {
      fontFamily: '"Orbitron", sans-serif',
      fontWeight: 600,
    },
    h4: {
      fontFamily: '"Orbitron", sans-serif',
      fontWeight: 600,
    },
    h5: {
      fontFamily: '"Orbitron", sans-serif',
      fontWeight: 500,
    },
    h6: {
      fontFamily: '"Orbitron", sans-serif',
      fontWeight: 500,
    },
    body1: {
      fontFamily: '"Rajdhani", sans-serif',
      fontSize: '1.1rem',
    },
    body2: {
      fontFamily: '"Rajdhani", sans-serif',
    },
    button: {
      fontFamily: '"Orbitron", sans-serif',
      fontWeight: 600,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          textTransform: 'uppercase',
          boxShadow: '0 0 10px rgba(0, 255, 255, 0.3)',
          transition: 'all 0.3s ease',
          '&:hover': {
            boxShadow: '0 0 20px rgba(0, 255, 255, 0.6)',
            transform: 'translateY(-2px)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          border: '1px solid rgba(0, 255, 255, 0.3)',
          boxShadow: '0 0 20px rgba(0, 255, 255, 0.1)',
          transition: 'all 0.3s ease',
          '&:hover': {
            border: '1px solid rgba(0, 255, 255, 0.6)',
            boxShadow: '0 0 30px rgba(0, 255, 255, 0.2)',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 0,
            '& fieldset': {
              borderColor: 'rgba(0, 255, 255, 0.3)',
            },
            '&:hover fieldset': {
              borderColor: 'rgba(0, 255, 255, 0.5)',
            },
            '&.Mui-focused fieldset': {
              borderColor: '#00ffff',
              boxShadow: '0 0 10px rgba(0, 255, 255, 0.3)',
            },
          },
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: 'rgba(0, 255, 255, 0.3)',
          },
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: 'rgba(0, 255, 255, 0.5)',
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: '#00ffff',
            boxShadow: '0 0 10px rgba(0, 255, 255, 0.3)',
          },
        },
      },
    },
  },
});

export default technoTheme;
