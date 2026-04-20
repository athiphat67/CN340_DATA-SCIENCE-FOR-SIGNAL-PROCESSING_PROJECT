/**
 * MSW v2 handlers — intercept fetch() ที่ component ทำไปยัง /api/*
 * ใช้ '*' match URL เพื่อรองรับทั้ง `import.meta.env.VITE_API_URL` และ hardcode 'http://localhost:8000'
 */

import { http, HttpResponse } from 'msw';
import {
  signalDetailFixture,
  portfolioFixture,
  latestSignalFixture,
  backtestSummaryFixture,
  equityCurveFixture,
  tradesFixture,
} from './fixtures';

export const handlers = [
  // ── Signals ───────────────────────────────────────────────────
  http.get('*/api/signals/:id', ({ params }) => {
    if (params.id === '404') return HttpResponse.json({ detail: 'Signal not found' }, { status: 404 });
    if (params.id === '500') return HttpResponse.json({ detail: 'db error' }, { status: 500 });
    return HttpResponse.json({ ...signalDetailFixture, id: Number(params.id) });
  }),
  http.get('*/api/latest-signal', () => HttpResponse.json(latestSignalFixture)),
  http.get('*/api/recent-signals', () => HttpResponse.json([latestSignalFixture])),

  // ── Portfolio / dashboard ────────────────────────────────────
  http.get('*/api/portfolio', () => HttpResponse.json(portfolioFixture)),
  http.get('*/api/active-positions', () => HttpResponse.json([])),
  http.get('*/api/market-bias', () =>
    HttpResponse.json({ direction: 'Bullish', conviction: 0.8, reason: 'Uptrend' })
  ),
  http.get('*/api/agent-health', () =>
    HttpResponse.json({
      latency: 1500,
      iterations: 3,
      api_status: 'Stable',
      accuracy: 0.85,
      last_update: '30s ago',
      quality_score: 95,
    })
  ),

  // ── Market data ──────────────────────────────────────────────
  http.get('*/api/gold-prices', () =>
    HttpResponse.json({ hsh_sell: 45200, hsh_buy: 44900, spot_price: 2350, usd_thb: 34.5 })
  ),
  http.get('*/api/market-state', () =>
    HttpResponse.json({ ask_96: 45200, bid_96: 44900, spot_price: 2350, usd_thb: 34.5 })
  ),
  http.get('*/api/performance-chart', () =>
    HttpResponse.json([{ time: '19 Apr 10:00', price: 45000, signalId: 1, action: 'BUY' }])
  ),

  // ── Backtest ─────────────────────────────────────────────────
  http.get('*/api/backtest/summary', () => HttpResponse.json(backtestSummaryFixture)),
  http.get('*/api/backtest/equity-curve', () => HttpResponse.json(equityCurveFixture)),
  http.get('*/api/backtest/trades', () => HttpResponse.json(tradesFixture)),
];
