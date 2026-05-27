<script lang="ts">
  import { createEventDispatcher, afterUpdate } from 'svelte';

  export let slug: string;
  export let disabled: boolean = false;

  const dispatch = createEventDispatcher<{
    committed: { ticketsCreated: number };
  }>();

  interface Ticket {
    id: string;
    gate: number;
    description: string;
    required_output_files: string[];
    depends_on: string[];
    is_parent: boolean;
  }

  interface Plan {
    tickets: Ticket[];
    gate_count: number;
    total_tickets: number;
    errors: string[];
  }

  let plan: Plan | null = null;
  let decomposing = false;
  let committing = false;
  let error = '';
  let streamingTickets: Ticket[] = [];

  // Group tickets by gate — use streaming tickets during decompose, plan tickets after
  $: displayTickets = plan ? plan.tickets : streamingTickets;
  $: gateGroups = displayTickets.length > 0 ? groupByGate(displayTickets) : [];
  $: ticketCount = displayTickets.length;

  let gateListEl: HTMLDivElement;

  afterUpdate(() => {
    // Auto-scroll to bottom when new tickets arrive during streaming
    if (decomposing && gateListEl) {
      gateListEl.scrollTop = gateListEl.scrollHeight;
    }
  });

  function groupByGate(tickets: Ticket[]): { gate: number; tickets: Ticket[] }[] {
    const groups = new Map<number, Ticket[]>();
    for (const t of tickets) {
      const arr = groups.get(t.gate) ?? [];
      arr.push(t);
      groups.set(t.gate, arr);
    }
    return Array.from(groups.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([gate, tickets]) => ({ gate, tickets }));
  }

  async function decompose() {
    decomposing = true;
    error = '';
    plan = null;
    streamingTickets = [];

    try {
      const resp = await fetch(`/api/projects/${slug}/decompose`, {
        method: 'POST',
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(data.detail || `HTTP ${resp.status}`);
      }

      // Read SSE stream
      const reader = resp.body?.getReader();
      if (!reader) throw new Error('No response body');
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer
        const parts = buf.split('\n\n');
        buf = parts.pop() ?? '';  // Keep incomplete last part

        for (const part of parts) {
          const lines = part.split('\n');
          let eventType = '';
          let eventData = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) eventType = line.slice(7);
            else if (line.startsWith('data: ')) eventData = line.slice(6);
          }
          if (!eventType || !eventData) continue;

          if (eventType === 'ticket') {
            try {
              const ticket: Ticket = JSON.parse(eventData);
              streamingTickets = [...streamingTickets, ticket];
            } catch { /* skip malformed */ }
          } else if (eventType === 'plan') {
            try {
              plan = JSON.parse(eventData);
            } catch { /* skip */ }
          } else if (eventType === 'error') {
            try {
              const errData = JSON.parse(eventData);
              error = errData.detail || 'Decomposition failed';
            } catch {
              error = 'Decomposition failed';
            }
          }
          // 'done' event — just let the loop end
        }
      }

      if (!plan && streamingTickets.length === 0 && !error) {
        error = 'No tickets generated';
      }
      if (plan && plan.errors?.length) {
        error = `Warnings: ${plan.errors.join('; ')}`;
      }
    } catch (e: any) {
      error = e.message || 'Decomposition failed';
    }
    decomposing = false;
  }

  async function commitPlan() {
    if (!plan || committing) return;
    committing = true;
    error = '';

    try {
      const resp = await fetch(`/api/projects/${slug}/decompose/commit`, {
        method: 'POST',
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(data.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      dispatch('committed', { ticketsCreated: data.tickets_created });
    } catch (e: any) {
      error = e.message || 'Failed to commit plan';
    }
    committing = false;
  }
</script>

<section class="decomp-section">
  <div class="decomp-header">
    <h2 class="section-header">TICKET DECOMPOSITION</h2>
    {#if !plan}
      <p class="decomp-hint">Generate a ticket plan from your PRD and Q&A decisions.</p>
    {/if}
  </div>

  <!-- Error -->
  {#if error}
    <div class="decomp-error">
      <span>⚠ {error}</span>
      <button class="dismiss-btn" on:click={() => error = ''}>✕</button>
    </div>
  {/if}

  <!-- No plan yet -->
  {#if !plan && !decomposing}
    <button
      class="btn-decompose"
      on:click={decompose}
      {disabled}
    >
      Decompose PRD into Tickets
    </button>
  {/if}

  <!-- Decomposing spinner + live ticket count -->
  {#if decomposing}
    <div class="decomp-loading">
      <span class="spinner"></span>
      <span>
        {#if streamingTickets.length > 0}
          Generating tickets… <strong class="ticket-counter">{streamingTickets.length}</strong> found
        {:else}
          Analyzing PRD and generating tickets…
        {/if}
      </span>
    </div>
  {/if}

  <!-- Plan review (or live streaming preview) -->
  {#if (plan && plan.tickets.length > 0) || (decomposing && streamingTickets.length > 0)}
    <div class="plan-summary">
      <span class="summary-stat">{ticketCount} ticket{ticketCount !== 1 ? 's' : ''}</span>
      <span class="summary-dot">·</span>
      <span class="summary-stat">{gateGroups.length} phase{gateGroups.length !== 1 ? 's' : ''}</span>
      {#if decomposing}
        <span class="summary-live">LIVE</span>
      {/if}
    </div>

    <div class="gate-list" bind:this={gateListEl}>
      {#each gateGroups as group}
        <div class="gate-group">
          <h3 class="gate-header">Phase {group.gate}</h3>
          <div class="ticket-list">
            {#each group.tickets as ticket}
              <div class="ticket-card" class:parent={ticket.is_parent}>
                <div class="ticket-id">{ticket.id}</div>
                <div class="ticket-desc">{ticket.description.slice(0, 200)}{ticket.description.length > 200 ? '...' : ''}</div>
                {#if ticket.required_output_files.length > 0}
                  <div class="ticket-files">
                    {#each ticket.required_output_files as f}
                      <span class="file-badge">{f}</span>
                    {/each}
                  </div>
                {/if}
                {#if ticket.depends_on.length > 0}
                  <div class="ticket-deps">
                    Depends on: {ticket.depends_on.join(', ')}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>

    {#if plan && !decomposing}
      <div class="plan-actions">
        <button
          class="btn-approve"
          on:click={commitPlan}
          disabled={committing || disabled}
        >
          {committing ? 'Committing...' : `Approve & Create ${plan.total_tickets} Tickets`}
        </button>
        <button
          class="btn-retry"
          on:click={decompose}
          disabled={decomposing || disabled}
        >
          Re-decompose
        </button>
      </div>
    {/if}
  {/if}
</section>

<style>
  .decomp-section {
    background: var(--bg-card, #16202E);
    border: 1px solid rgba(58, 190, 255, 0.12);
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .decomp-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .section-header {
    font-family: var(--font-ui);
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-primary, #E6EDF3);
    margin: 0;
  }

  .decomp-hint {
    font-size: 0.75rem;
    color: var(--color-text-muted, #6B7A8D);
    margin: 0;
  }

  /* Error */
  .decomp-error {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: rgba(255, 80, 80, 0.1);
    border: 1px solid rgba(255, 80, 80, 0.3);
    border-radius: 6px;
    font-size: 0.8rem;
    color: #FF6B6B;
  }

  .dismiss-btn {
    background: none;
    border: none;
    color: #FF6B6B;
    cursor: pointer;
    padding: 0 4px;
    font-size: 0.85rem;
  }

  /* Loading */
  .decomp-loading {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 20px;
    justify-content: center;
    color: var(--color-text-secondary, #8B9DC3);
    font-size: 0.85rem;
  }

  .spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(58, 190, 255, 0.2);
    border-top-color: var(--color-accent-primary, #3ABEFF);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .ticket-counter {
    color: var(--color-accent-primary, #3ABEFF);
    font-size: 1.1em;
    font-variant-numeric: tabular-nums;
  }

  .summary-live {
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(58, 190, 255, 0.15);
    color: var(--color-accent-primary, #3ABEFF);
    animation: pulse-live 1.5s ease-in-out infinite;
  }

  @keyframes pulse-live {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  /* Decompose button */
  .btn-decompose {
    background: var(--color-accent-primary, #3ABEFF);
    color: #0B1220;
    border: none;
    border-radius: 8px;
    padding: 14px 24px;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 150ms, box-shadow 150ms;
    width: 100%;
  }

  .btn-decompose:hover:not(:disabled) {
    background: #5BCEFF;
    box-shadow: 0 0 16px rgba(58, 190, 255, 0.25);
  }

  .btn-decompose:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Plan summary */
  .plan-summary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    background: rgba(58, 190, 255, 0.06);
    border: 1px solid rgba(58, 190, 255, 0.15);
    border-radius: 8px;
  }

  .summary-stat {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--color-accent-primary, #3ABEFF);
  }

  .summary-dot {
    color: var(--color-text-muted, #6B7A8D);
  }

  /* Gate groups */
  .gate-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-height: 500px;
    overflow-y: auto;
    padding-right: 4px;
  }

  .gate-header {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-secondary, #8B9DC3);
    margin: 0 0 8px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .ticket-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .ticket-card {
    padding: 10px 14px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .ticket-card.parent {
    border-left: 3px solid var(--color-accent-primary, #3ABEFF);
  }

  .ticket-id {
    font-size: 0.7rem;
    font-weight: 700;
    font-family: var(--font-mono, monospace);
    color: var(--color-accent-primary, #3ABEFF);
    letter-spacing: 0.03em;
  }

  .ticket-desc {
    font-size: 0.8rem;
    line-height: 1.4;
    color: var(--color-text-primary, #E6EDF3);
  }

  .ticket-files {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .file-badge {
    font-size: 0.65rem;
    font-family: var(--font-mono, monospace);
    padding: 2px 6px;
    background: rgba(58, 190, 255, 0.08);
    border: 1px solid rgba(58, 190, 255, 0.15);
    border-radius: 4px;
    color: var(--color-text-secondary, #8B9DC3);
  }

  .ticket-deps {
    font-size: 0.7rem;
    color: var(--color-text-muted, #6B7A8D);
    font-style: italic;
  }

  /* Actions */
  .plan-actions {
    display: flex;
    gap: 10px;
    padding-top: 8px;
  }

  .btn-approve {
    flex: 1;
    background: #3ABE55;
    color: #0B1220;
    border: none;
    border-radius: 8px;
    padding: 12px 20px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 150ms;
  }

  .btn-approve:hover:not(:disabled) {
    background: #4DD66A;
  }

  .btn-approve:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-retry {
    background: transparent;
    color: var(--color-text-secondary, #8B9DC3);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: border-color 150ms, color 150ms;
  }

  .btn-retry:hover:not(:disabled) {
    border-color: rgba(255, 255, 255, 0.3);
    color: var(--color-text-primary, #E6EDF3);
  }

  .btn-retry:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
