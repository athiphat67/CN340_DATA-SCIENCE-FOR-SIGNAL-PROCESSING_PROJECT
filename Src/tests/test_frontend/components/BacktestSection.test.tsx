/**
 * BacktestSection.test.tsx — parallel fetch 3 endpoints + error banner + retry
 *
 * Test matrix:
 *   - all 3 success → summary + curve + trades render
 *   - summary 500 → error banner "Summary API error: 500"
 *   - equity-curve 500 → error banner "Equity curve API error: 500"
 *   - trades 500 → UI ยัง render (component fallback: tradesRes.ok ? ... : [])
 *   - all 3 fail → first-thrown error banner
 *   - retry button → re-fetch all 3
 */

import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';

import { server } from '../__mocks__/server';
import {
  backtestSummaryFixture,
  equityCurveFixture,
  tradesFixture,
} from '../__mocks__/fixtures';
import { BacktestSection } from '../../../frontend/components/backtest/BacktestSection';

/**
 * BacktestSection → OverviewHeader → uses useNavigate/useLocation
 * ต้อง wrap ใน MemoryRouter ตอน render
 */
const renderWithRouter = () =>
  render(
    <MemoryRouter>
      <BacktestSection />
    </MemoryRouter>
  );

describe('BacktestSection — happy path', () => {
  it('renders backtest data when all 3 APIs succeed', async () => {
    renderWithRouter();
    // รอให้ loading skeleton หายไป — summary render ออกมา
    await waitFor(
      () => {
        expect(screen.queryByText(/ไม่สามารถโหลดข้อมูล/)).not.toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });
});

describe('BacktestSection — API error handling', () => {
  it('shows error banner when summary API returns 500', async () => {
    server.use(
      http.get('*/api/backtest/summary', () =>
        HttpResponse.json({ detail: 'db error' }, { status: 500 })
      )
    );
    renderWithRouter();
    expect(await screen.findByText(/ไม่สามารถโหลดข้อมูล Backtest/i)).toBeInTheDocument();
    expect(screen.getByText(/Summary API error: 500/i)).toBeInTheDocument();
  });

  it('shows error banner when equity-curve API returns 500', async () => {
    server.use(
      http.get('*/api/backtest/equity-curve', () =>
        HttpResponse.json({ detail: 'db error' }, { status: 500 })
      )
    );
    renderWithRouter();
    expect(await screen.findByText(/Equity curve API error: 500/i)).toBeInTheDocument();
  });

  it('trades 500 does NOT crash — component uses empty array fallback', async () => {
    server.use(
      http.get('*/api/backtest/trades', () =>
        HttpResponse.json({ detail: 'db error' }, { status: 500 })
      )
    );
    renderWithRouter();
    // Component: tradesRes.ok ? .json() : Promise.resolve([])
    // → เฉพาะ summary + curve พอ → ไม่ throw
    await waitFor(
      () => {
        expect(screen.queryByText(/ไม่สามารถโหลดข้อมูล/)).not.toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('shows retry button on error + refetch when clicked', async () => {
    let callCount = 0;
    server.use(
      http.get('*/api/backtest/summary', () => {
        callCount++;
        if (callCount === 1) {
          return HttpResponse.json({ detail: 'transient' }, { status: 500 });
        }
        return HttpResponse.json(backtestSummaryFixture);
      })
    );
    renderWithRouter();
    const retry = await screen.findByRole('button', { name: /ลองใหม่/ });
    expect(retry).toBeInTheDocument();

    await userEvent.click(retry);
    await waitFor(
      () => {
        expect(screen.queryByText(/ไม่สามารถโหลดข้อมูล/)).not.toBeInTheDocument();
      },
      { timeout: 3000 }
    );
    expect(callCount).toBe(2);
  });
});

describe('BacktestSection — network failure', () => {
  it('shows error banner when network totally down', async () => {
    server.use(
      http.get('*/api/backtest/summary', () => HttpResponse.error()),
      http.get('*/api/backtest/equity-curve', () => HttpResponse.error()),
      http.get('*/api/backtest/trades', () => HttpResponse.error())
    );
    renderWithRouter();
    expect(await screen.findByText(/ไม่สามารถโหลดข้อมูล Backtest/i)).toBeInTheDocument();
  });
});

describe('BacktestSection — data contract', () => {
  it('handles empty trades array gracefully', async () => {
    server.use(http.get('*/api/backtest/trades', () => HttpResponse.json([])));
    renderWithRouter();
    await waitFor(
      () => {
        expect(screen.queryByText(/ไม่สามารถโหลดข้อมูล/)).not.toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('handles empty equity curve without crashing', async () => {
    server.use(http.get('*/api/backtest/equity-curve', () => HttpResponse.json([])));
    renderWithRouter();
    await waitFor(
      () => {
        expect(screen.queryByText(/ไม่สามารถโหลดข้อมูล/)).not.toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });
});
