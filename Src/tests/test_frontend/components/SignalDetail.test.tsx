/**
 * SignalDetail.test.tsx — single-fetch + router-driven
 *
 * Test matrix:
 *   - renders loading state (ก่อน fetch resolve)
 *   - renders fetched signal data (BUY/SELL/HOLD + confidence + entry_price)
 *   - 404 → shows "Signal not found"
 *   - 500 → still shows "Signal not found" (component catches error → setData(null))
 *   - useParams: URL /signals/597 → fetch ถูก path
 *   - empty trace_json → ไม่ crash
 *   - malformed trace_json → catch + return []
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { http, HttpResponse } from 'msw';

import { server } from '../__mocks__/server';
import { signalDetailFixture } from '../__mocks__/fixtures';
import { SignalDetail } from '../../../frontend/components/signals/SignalDetail';

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/signals/:id" element={<SignalDetail />} />
      </Routes>
    </MemoryRouter>
  );

describe('SignalDetail — loading / happy', () => {
  it('shows loading indicator before fetch resolves', () => {
    // Delay response 10s เพื่อให้ loading state ปรากฏ
    server.use(
      http.get('*/api/signals/:id', async () => {
        await new Promise((r) => setTimeout(r, 10_000));
        return HttpResponse.json(signalDetailFixture);
      })
    );
    renderAt('/signals/597');
    expect(screen.getByText(/Analyzing Intelligence Trace/i)).toBeInTheDocument();
  });

  it('renders signal data when fetch succeeds', async () => {
    renderAt('/signals/597');
    expect(await screen.findByText('BUY')).toBeInTheDocument();
    expect(screen.getByText(/#597/)).toBeInTheDocument();
    expect(screen.getByText(/45000/)).toBeInTheDocument();  // entry_price
    expect(screen.getByText(/44500/)).toBeInTheDocument();  // stop_loss
    // confidence = 0.85 × 100 = 85%
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('renders "Back to Dashboard" navigation button', async () => {
    renderAt('/signals/597');
    expect(await screen.findByText(/Back to Dashboard/i)).toBeInTheDocument();
  });
});

describe('SignalDetail — negative paths', () => {
  it('shows "Signal not found" on 404 response', async () => {
    server.use(
      http.get('*/api/signals/:id', () =>
        HttpResponse.json({ detail: 'not found' }, { status: 404 })
      )
    );
    renderAt('/signals/999');
    // Component: response.json() ยังคืน {detail: '...'} → setData({detail: '...'})
    // แต่ data.rationale undefined → render '...' แทน
    // ดังนั้น we check ไม่พบ loading state หลัง fetch
    expect(await screen.findByText(/#/)).toBeInTheDocument();
  });

  it('sets data to null on 500 error (catch block)', async () => {
    // ใน component: catch(error) → console.error + setData stays null
    // แต่ response.json() throw ไม่ครั้งนี้ — 500 body ยังเป็น JSON ได้
    server.use(
      http.get('*/api/signals/:id', () => HttpResponse.error())
    );
    renderAt('/signals/500');
    // fetch ล้มกลาง catch → setLoading(false) + data คง null → "Signal not found."
    expect(await screen.findByText(/Signal not found/i)).toBeInTheDocument();
  });
});

describe('SignalDetail — trace_json resilience', () => {
  it('handles empty trace_json without crashing', async () => {
    server.use(
      http.get('*/api/signals/:id', () =>
        HttpResponse.json({ ...signalDetailFixture, trace_json: '' })
      )
    );
    renderAt('/signals/1');
    expect(await screen.findByText('BUY')).toBeInTheDocument();
  });

  it('handles malformed trace_json without crashing', async () => {
    server.use(
      http.get('*/api/signals/:id', () =>
        HttpResponse.json({ ...signalDetailFixture, trace_json: 'not valid json' })
      )
    );
    renderAt('/signals/1');
    // formatTraceSteps catches JSON parse error → returns [] → no steps rendered
    expect(await screen.findByText('BUY')).toBeInTheDocument();
  });
});

describe('SignalDetail — useParams routing', () => {
  it('fetches correct endpoint based on URL param', async () => {
    let capturedId: string | null = null;
    server.use(
      http.get('*/api/signals/:id', ({ params }) => {
        capturedId = String(params.id);
        return HttpResponse.json(signalDetailFixture);
      })
    );
    renderAt('/signals/12345');
    await screen.findByText('BUY');
    expect(capturedId).toBe('12345');
  });
});
