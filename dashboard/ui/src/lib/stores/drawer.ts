import { writable, derived } from 'svelte/store';
import { projectsStore } from '$lib/stores/projects';

export type DrawerMode = 'closed' | 'forge' | 'sift';

export const drawerMode = writable<DrawerMode>('closed');

export const drawerOpen = derived(drawerMode, m => m !== 'closed');

export function openForgeDrawer() {
  // Deselect project so the form starts blank
  projectsStore.selectProject(null, 'intake');
  drawerMode.set('forge');
}

export function openSiftDrawer() {
  drawerMode.set('sift');
}

export function openDrawer() {
  openForgeDrawer();
}

export function closeDrawer() {
  drawerMode.set('closed');
}
