<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { fade, fly } from 'svelte/transition';

  export let open = false;
  export let title = '';

  const dispatch = createEventDispatcher();

  function close() {
    dispatch('close');
  }

  function onBackdropClick() {
    close();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') close();
  }
</script>

<svelte:window on:keydown={onKeydown} />

{#if open}
  <!-- Backdrop -->
  <div class="drawer-backdrop" transition:fade={{ duration: 200 }} on:click={onBackdropClick}></div>

  <!-- Drawer panel -->
  <div class="drawer-panel" transition:fly={{ x: -400, duration: 300, opacity: 1 }}>
    <div class="drawer-header">
      <h2 class="drawer-title">{title}</h2>
      <button class="drawer-close" on:click={close} title="Close">
        <svg width="18" height="18" viewBox="0 0 18 18">
          <path d="M4 4 L14 14 M14 4 L4 14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </button>
    </div>
    <div class="drawer-body">
      <slot />
    </div>
  </div>
{/if}

<style>
  .drawer-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 100;
  }

  .drawer-panel {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: min(520px, 90vw);
    background: var(--color-bg-base);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 8px 0 40px rgba(0, 0, 0, 0.6);
    z-index: 101;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    flex-shrink: 0;
  }

  .drawer-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .drawer-close {
    background: none;
    border: none;
    color: var(--color-text-muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: color 0.15s, background-color 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .drawer-close:hover {
    color: var(--color-text-primary);
    background: rgba(255, 255, 255, 0.06);
  }

  .drawer-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px 24px;
  }

  .drawer-body::-webkit-scrollbar {
    width: 6px;
  }

  .drawer-body::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
  }

  @media (max-width: 768px) {
    .drawer-panel {
      left: 0;
      width: 100vw;
    }
  }
</style>
