import { writable, derived } from 'svelte/store';

export type DrawerMode = 'closed' | 'forge' | 'sift';

export const drawerMode = writable<DrawerMode>('closed');

export const drawerOpen = derived(drawerMode, m => m !== 'closed');

export function openForgeDrawer() {
  drawerMode.set('forge');
}

export function openSiftDrawer() {
  drawerMode.set('sift');
}

export function openDrawer() {
  drawerMode.set('forge');
}

export function closeDrawer() {
  drawerMode.set('closed');
}
