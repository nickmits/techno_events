import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import EventDisplay from './EventDisplay';
import technoTheme from '../theme';

describe('EventDisplay', () => {
  it('should display loading state', () => {
    render(
      <ThemeProvider theme={technoTheme}>
        <EventDisplay response={null} loading={true} error={null} />
      </ThemeProvider>
    );

    expect(screen.getByText(/SCANNING EVENTS DATABASE/i)).toBeInTheDocument();
  });

  it('should display error message', () => {
    render(
      <ThemeProvider theme={technoTheme}>
        <EventDisplay
          response={null}
          loading={false}
          error="Test error message"
        />
      </ThemeProvider>
    );

    expect(screen.getByText(/ERROR/i)).toBeInTheDocument();
    expect(screen.getByText(/Test error message/i)).toBeInTheDocument();
  });

  it('should render null when no response and not loading', () => {
    const { container } = render(
      <ThemeProvider theme={technoTheme}>
        <EventDisplay response={null} loading={false} error={null} />
      </ThemeProvider>
    );

    expect(container.firstChild).toBeNull();
  });

  it('should display event sources when response is provided', () => {
    const mockResponse = {
      query: 'Test query',
      source: 'test',
      events: [],
      sources: [
        {
          name: 'Test Source',
          content: 'Test content paragraph',
        },
      ],
      total_sources: 1,
      timestamp: new Date().toISOString(),
    };

    render(
      <ThemeProvider theme={technoTheme}>
        <EventDisplay response={mockResponse} loading={false} error={null} />
      </ThemeProvider>
    );

    expect(screen.getByText(/Results for: Test query/i)).toBeInTheDocument();
    expect(screen.getByText(/Test Source/i)).toBeInTheDocument();
    expect(screen.getByText(/Test content paragraph/i)).toBeInTheDocument();
  });
});
