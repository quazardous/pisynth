// The playing aids of the musician playing, shared by every screen (see lib/aids.js). Set under the
// cog → Display; switching musician switches their aids.

import { AIDS, loadAids, saveAids } from "./aids.js";
import { storeKey, onMusicianChange } from "./musician.svelte.js";

const KEY = "pisynth.aids";
const storage = () => globalThis.localStorage;

export const aids = $state(loadAids(storage(), storeKey(KEY)));

onMusicianChange(() => Object.assign(aids, loadAids(storage(), storeKey(KEY))));

export function setAid(name, on) {
  if (!AIDS.includes(name)) return;
  aids[name] = !!on;
  saveAids(aids, storage(), storeKey(KEY));
}
