<script lang="ts">
  import { onMount } from 'svelte';
  import '../app.css';
  import { connection } from '$lib/stores/connection';
  import { projectsStore } from '$lib/stores/projects';
  import { researchStore } from '$lib/stores/research';
  import { drawerOpen, openDrawer, closeDrawer } from '$lib/stores/drawer';
  import StatusBanner from '$lib/components/StatusBanner.svelte';
  import Drawer from '$lib/components/Drawer.svelte';
  import IntakeView from '$lib/components/IntakeView.svelte';

  onMount(() => {
    connection.start();
    projectsStore.startPolling();
    researchStore.startPolling();
    return () => {
      connection.stop();
      projectsStore.stopPolling();
      researchStore.stopPolling();
    };
  });

  function onDrawerClose() {
    closeDrawer();
  }
</script>

<div class="layout-root">
  <!-- Left edge tab to open drawer -->
  {#if !$drawerOpen}
    <button class="drawer-tab" on:click={openDrawer} title="New Project">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 4v12M4 10h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
    </button>
  {/if}

  <main class="main-content">
    <StatusBanner />
    <slot />
  </main>

  <Drawer open={$drawerOpen} title="New Project" on:close={onDrawerClose}>
    <IntakeView on:decompose-started={onDrawerClose} />
  </Drawer>
</div>

<style>
  .layout-root {
    display: flex;
    min-height: 100vh;
    width: 100%;
    position: relative;
  }

  .main-content {
    flex: 1;
    min-width: 0;
    overflow-x: hidden;
    overflow-y: auto;
    padding: var(--spacing-panel-gap);
  }

  .drawer-tab {
    position: fixed;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    z-index: 50;
    width: 36px;
    height: 48px;
    background: var(--color-bg-panel);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-left: none;
    border-radius: 0 8px 8px 0;
    color: var(--color-text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.15s, background-color 0.15s, width 0.15s;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.3);
  }

  .drawer-tab:hover {
    color: var(--color-accent-primary);
    background: var(--color-bg-panel-raised);
    width: 42px;
  }
</style>
