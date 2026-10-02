import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1d4ed8',
      dark: '#1e3a8a',
      light: '#dbeafe',
    },
    secondary: {
      main: '#0f766e',
      dark: '#115e59',
      light: '#ccfbf1',
    },
    success: {
      main: '#15803d',
      light: '#dcfce7',
    },
    warning: {
      main: '#b45309',
      light: '#fef3c7',
    },
    error: {
      main: '#b91c1c',
      light: '#fee2e2',
    },
    background: {
      default: '#eef2f6',
      paper: '#ffffff',
    },
    text: {
      primary: '#111827',
      secondary: '#5b677a',
    },
    divider: '#d8e0ea',
  },
  shape: {
    borderRadius: 8,
  },
  typography: {
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h1: {
      fontSize: '1.5rem',
      fontWeight: 850,
      letterSpacing: 0,
      lineHeight: 1.15,
    },
    h2: {
      fontSize: '1.12rem',
      fontWeight: 850,
      letterSpacing: 0,
      lineHeight: 1.25,
    },
    h3: {
      fontSize: '0.98rem',
      fontWeight: 850,
      letterSpacing: 0,
      lineHeight: 1.25,
    },
    body1: {
      fontSize: '0.95rem',
      lineHeight: 1.5,
    },
    body2: {
      fontSize: '0.86rem',
      lineHeight: 1.5,
    },
    caption: {
      fontSize: '0.75rem',
      lineHeight: 1.35,
    },
    button: {
      textTransform: 'none',
      fontWeight: 850,
      letterSpacing: 0,
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          minWidth: 320,
          overflowX: 'hidden',
        },
      },
    },
    MuiPaper: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          border: '1px solid #d8e0ea',
          backgroundImage: 'none',
        },
      },
    },
    MuiCard: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          border: '1px solid #d8e0ea',
          backgroundImage: 'none',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          minHeight: 44,
          borderRadius: 8,
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        size: 'small',
        variant: 'outlined',
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          backgroundColor: '#ffffff',
        },
        input: {
          fontWeight: 650,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          fontWeight: 800,
        },
      },
    },
  },
})
