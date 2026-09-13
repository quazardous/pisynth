<script>
  // One comic splash bubble (#2434): a spiky burst with a halftone shade, a thick black outline and a
  // drop shadow, drawn from lib/comic.js. Placed by the parent (absolute box); the pop is CSS.
  import { burstPath } from "./lib/comic.js";

  let { splash, text = true, width = "min(78vw, 360px)", kind = "combo" } = $props();
  const path = $derived(burstPath(splash.seed, { spikes: splash.spikes }));
  const dots = $derived(`dots-${splash.seed}`);
</script>

<div class="comic {kind}" style:--w={width} style:--s={splash.scale} style:--tilt="{splash.tilt}deg"
     style:--dx="{splash.dx}%" style:--dy="{splash.dy}%">
  <svg viewBox="-12 -12 224 144" aria-hidden="true">
    <defs>
      <pattern id={dots} width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <circle cx="3.5" cy="3.5" r="1.6" fill="rgba(0,0,0,.22)" />
      </pattern>
    </defs>
    <path d={path} transform="translate(5 7)" fill="#000" />
    <path d={path} fill={splash.color} stroke="#000" stroke-width="5" stroke-linejoin="miter" />
    <path d={path} fill="url(#{dots})" />
  </svg>
  {#if text}
    <span class="word">{splash.word}{#if splash.caption}<small>{splash.caption}</small>{/if}</span>
  {/if}
</div>

<style>
  .comic { position: absolute; left: 50%; top: 50%; width: var(--w); aspect-ratio: 224 / 144; pointer-events: none;
           translate: calc(-50% + var(--dx)) calc(-50% + var(--dy));
           transform: rotate(var(--tilt)) scale(var(--s)); animation: pop-fade 1.05s cubic-bezier(.2,1.8,.4,1) forwards; }
  svg { width: 100%; height: 100%; display: block; overflow: visible; }
  .word { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: .3em;
          font-family: Bangers, Impact, "Arial Black", system-ui, sans-serif; font-size: calc(var(--w) * .2); letter-spacing: .04em;
          color: #fff; -webkit-text-stroke: 3px #000; paint-order: stroke fill; text-shadow: 3px 4px 0 #000; }
  .word small { font-size: .55em; }
  /* Both pop in, then sink like a boat: going down right away, listing more and more, fading at the end. */
  .oops { animation: sink 1.1s cubic-bezier(.2,1.8,.4,1) forwards; }
  /* LEVEL UP: pops in, breathes three times, then melts away growing */
  .levelup { animation: breathe 3.4s cubic-bezier(.2,1.8,.4,1) forwards; }
  @keyframes breathe {
    0%   { transform: rotate(calc(var(--tilt) - 25deg)) scale(0); opacity: 0; }
    9%   { transform: rotate(var(--tilt)) scale(calc(var(--s) * 1.15)); opacity: 1; }
    15%  { transform: rotate(var(--tilt)) scale(var(--s)); animation-timing-function: ease-in-out; }
    28%  { transform: rotate(var(--tilt)) scale(calc(var(--s) * 1.08)); animation-timing-function: ease-in-out; }
    41%  { transform: rotate(var(--tilt)) scale(var(--s)); animation-timing-function: ease-in-out; }
    54%  { transform: rotate(var(--tilt)) scale(calc(var(--s) * 1.08)); animation-timing-function: ease-in-out; }
    67%  { transform: rotate(var(--tilt)) scale(var(--s)); animation-timing-function: ease-in-out; }
    80%  { transform: rotate(var(--tilt)) scale(calc(var(--s) * 1.08)); opacity: 1; animation-timing-function: ease-in; }
    100% { transform: rotate(var(--tilt)) scale(calc(var(--s) * 1.35)); opacity: 0; }
  }
  .levelup .word { flex-direction: column; gap: 0; line-height: .95; }
  @keyframes sink {
    0%   { transform: rotate(calc(var(--tilt) - 25deg)) scale(0); opacity: 0; }
    12%  { transform: rotate(var(--tilt)) scale(calc(var(--s) * 1.15)); opacity: 1; }
    20%  { transform: translateY(0) rotate(var(--tilt)) scale(var(--s)); opacity: 1; animation-timing-function: cubic-bezier(.35,0,.75,.7); }
    65%  { transform: translateY(80%) rotate(calc(var(--tilt) + 22deg)) scale(var(--s)); opacity: 1; animation-timing-function: linear; }
    92%  { opacity: 1; }                                        /* still whole as it goes under the line */
    100% { transform: translateY(190%) rotate(calc(var(--tilt) + 40deg)) scale(calc(var(--s) * .9)); opacity: 0; }
  }
  .combo { animation-name: pop-fade; }                      /* under the announcer: see-through, gone before the text */
  @keyframes pop-fade {
    0%   { transform: rotate(calc(var(--tilt) - 25deg)) scale(0); opacity: 0; }
    16%  { transform: rotate(var(--tilt)) scale(calc(var(--s) * 1.15)); opacity: .8; }
    30%  { transform: translateY(0) rotate(var(--tilt)) scale(var(--s)); opacity: .7; animation-timing-function: cubic-bezier(.35,0,.75,.7); }
    100% { transform: translateY(70%) rotate(calc(var(--tilt) + 28deg)) scale(var(--s)); opacity: 0; }
  }
</style>
