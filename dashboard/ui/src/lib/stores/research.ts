import { writable, derived } from 'svelte/store';

export interface ResearchTicket {
  id: string;
  ticket_description: string | null;
  queue_status: string | null;
  display_status: string;
  priority: number | null;
  report_path: string | null;
  enqueued_at: string | null;
  last_note: string | null;
  attempt_count: number;
}

interface ResearchState {
  tickets: ResearchTicket[];
  loading: boolean;
  error: string | null;
}

function createResearchStore() {
  const { subscribe, set, update } = writable<ResearchState>({
    tickets: [],
    loading: true,
    error: null,
  });

  let interval: ReturnType<typeof setInterval> | null = null;

  async function fetchTickets() {
    try {
      const res = await fetch('/api/research/tickets');
      if (res.ok) {
        const data = await res.json();
        update(s => ({ ...s, tickets: data.tickets ?? [], loading: false, error: null }));
      } else {
        update(s => ({ ...s, tickets: [], loading: false, error: null }));
      }
    } catch (e) {
      update(s => ({ ...s, loading: false, error: null }));
    }
  }

  function startPolling() {
    fetchTickets();
    interval = setInterval(fetchTickets, 15000);
  }

  function stopPolling() {
    if (interval) { clearInterval(interval); interval = null; }
  }

  return { subscribe, startPolling, stopPolling, fetchTickets };
}

export const researchStore = createResearchStore();

// Selected research ticket id + which view
export const selectedResearchId = writable<string | null>(null);
export const researchView = writable<'intake' | 'report'>('intake');

export function selectResearch(id: string, view: 'intake' | 'report' = 'report') {
  selectedResearchId.set(id);
  researchView.set(view);
}

export function newResearch() {
  selectedResearchId.set(null);
  researchView.set('intake');
}

// Colour logic: same hues as project dots
export function researchStatusColor(displayStatus: string): string {
  if (displayStatus === 'complete') return '#63d38f';         // green
  if (displayStatus === 'in_progress' || displayStatus === 'awaiting_review') return '#ffd166'; // yellow
  if (displayStatus === 'failed') return '#ff6b6b';           // red
  return 'var(--color-accent-primary)';                       // blue — queued
}

export function researchStatusLabel(displayStatus: string, queueStatus: string | null): string {
  const labels: Record<string, string> = {
    queued: 'queued',
    in_progress: 'in progress',
    awaiting_review: 'awaiting review',
    complete: 'complete',
    failed: 'failed',
  };
  return labels[displayStatus] ?? queueStatus ?? displayStatus;
}
