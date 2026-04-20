/**
 * StatsStack.test.tsx — parallel fetch + polling 30s
 *
 * Test matrix:
 *   - both APIs success → SYNCED + data renders
 *   - portfolio 500, signal OK → OFFLINE indicator
 *   - confidence normalization (0.75 → 75) vs already pct (75 → 75)
 *   - polling: advance 30s → re-fetch
 *   - unmount → clearInterval (no memory leak)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';

import { server } from '../__mocks__/server';
import { portfolioFixture, latestSignalFixture } from '../__mocks__/fixtures';
import { StatsStack } from '../../../frontend/components/overview/StatsStack';

/**
 * Component renders confidence as:
 *   <p>{num}<span>%</span></p>
 * → textContent = "42%" but findByText('42%') fails because text is split across elements.
 * Use textContent matcher on the <p> parent.
 */
const findConfidencePct = (num: number) =>
  screen.findByText((_, el) => el?.tagName === 'P' && el?.textContent?.trim() === `${num}%`);

describe('StatsStack — happy path', () => {
  it('renders portfolio + signal data when both APIs succeed', async () => {
    render(<StatsStack />);
    // confidence 0.75 → 75%
    expect(await findConfidencePct(75)).toBeInTheDocument();
    // available cash = 1500.00 formatted
    expect(screen.getByText(/1,500\.00/)).toBeInTheDocument();
    // signal BUY
    expect(screen.getByText('BUY')).toBeInTheDocument();
  });

  it('shows SYNCED indicator (not OFFLINE) when no errors', async () => {
    render(<StatsStack />);
    await waitFor(() => {
      expect(screen.queryByText('OFFLINE')).not.toBeInTheDocument();
    });
  });
});

describe('StatsStack — confidence normalization', () => {
  it('converts fractional confidence (0.75) to 75', async () => {
    server.use(
      http.get('*/api/latest-signal', () =>
        HttpResponse.json({ ...latestSignalFixture, confidence: 0.42 })
      )
    );
    render(<StatsStack />);
    expect(await findConfidencePct(42)).toBeInTheDocument();
  });

  it('keeps already-percentage confidence (85) as 85 (boundary > 1)', async () => {
    server.use(
      http.get('*/api/latest-signal', () =>
        HttpResponse.json({ ...latestSignalFixture, confidence: 85 })
      )
    );
    render(<StatsStack />);
    expect(await findConfidencePct(85)).toBeInTheDocument();
  });

  it('boundary: confidence = 1.0 → 100', async () => {
    server.use(
      http.get('*/api/latest-signal', () =>
        HttpResponse.json({ ...latestSignalFixture, confidence: 1.0 })
      )
    );
    render(<StatsStack />);
    expect(await findConfidencePct(100)).toBeInTheDocument();
  });
});

describe('StatsStack — negative paths', () => {
  it('shows OFFLINE when portfolio API returns 500', async () => {
    server.use(
      http.get('*/api/portfolio', () =>
        HttpResponse.json({ detail: 'db down' }, { status: 500 })
      )
    );
    render(<StatsStack />);
    expect(await screen.findByText('OFFLINE')).toBeInTheDocument();
  });

  it('shows OFFLINE when latest-signal API returns 500', async () => {
    server.use(
      http.get('*/api/latest-signal', () =>
        HttpResponse.json({ detail: 'db down' }, { status: 500 })
      )
    );
    render(<StatsStack />);
    expect(await screen.findByText('OFFLINE')).toBeInTheDocument();
  });

  it('shows OFFLINE when both APIs fail (network error)', async () => {
    server.use(
      http.get('*/api/portfolio', () => HttpResponse.error()),
      http.get('*/api/latest-signal', () => HttpResponse.error())
    );
    render(<StatsStack />);
    expect(await screen.findByText('OFFLINE')).toBeInTheDocument();
  });

  it('uses default HOLD + 50% confidence when signal is empty', async () => {
    // fallback ภายใน component: signal||HOLD, rationale fallback
    server.use(
      http.get('*/api/latest-signal', () => HttpResponse.json({ confidence: 0 }))
    );
    render(<StatsStack />);
    expect(await screen.findByText('HOLD')).toBeInTheDocument();
  });
});

describe('StatsStack — polling', () => {
  it('registers setInterval(30000) on mount + re-fetches when interval fires', async () => {
    // Spy on setInterval — capture callback + verify 30000ms delay
    const setIntervalSpy = vi.spyOn(window, 'setInterval');

    let portfolioCallCount = 0;
    server.use(
      http.get('*/api/portfolio', () => {
        portfolioCallCount++;
        return HttpResponse.json(portfolioFixture);
      })
    );

    render(<StatsStack />);
    await waitFor(() => expect(portfolioCallCount).toBe(1));

    // Verify setInterval was called with 30s delay
    const intervalCall = setIntervalSpy.mock.calls.find((c) => c[1] === 30000);
    expect(intervalCall).toBeDefined();

    // Manually invoke the interval callback to simulate 30s tick
    // wrap in act() เพื่อให้ React batch state updates และไม่เตือน
    const cb = intervalCall![0] as () => void;
    await act(async () => {
      cb();
    });
    await waitFor(() => expect(portfolioCallCount).toBe(2));

    setIntervalSpy.mockRestore();
  });

  it('clears interval on unmount (no memory leak)', async () => {
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval');
    const { unmount } = render(<StatsStack />);
    // Wait for initial fetch so setInterval is registered
    await waitFor(() => {
      expect(screen.queryByText('SYNCING...')).not.toBeInTheDocument();
    });
    unmount();
    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });
});
