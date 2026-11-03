const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const root = document.documentElement;

// Theme: every visit starts light; the toggle switches dark for this visit only (not saved).
$("#theme-toggle")?.addEventListener("click", () => {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
});

// Top-bar menu (collapsed below 1150px)
const toggle = $("#nav-toggle"), menu = $("#primary-nav");
const setNav = (open) => { menu.classList.toggle("is-open", open); toggle.setAttribute("aria-expanded", open); };
toggle?.addEventListener("click", () => setNav(!menu.classList.contains("is-open")));
$$("#primary-nav a").forEach((a) => a.addEventListener("click", () => setNav(false)));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") setNav(false); });

// Scrollspy + reveal
const spy = new IntersectionObserver((es) => es.forEach((e) => {
  if (!e.isIntersecting) return;
  $$("[data-scrollspy]").forEach((l) => l.classList.toggle("is-active", l.dataset.scrollspy === e.target.id));
}), { rootMargin: "-20% 0px -70% 0px" });
$$("[data-scrollspy]").forEach((l) => { const s = document.getElementById(l.dataset.scrollspy); if (s) spy.observe(s); });

// Hero carousel: always plays; ← → swap loops (loaded on demand).
// ❚❚ pauses all motion — the hero loop and the marquee (WCAG 2.2.2).
const hero = $(".hero__media");
if (hero) {
  const loops = JSON.parse(hero.dataset.loops), base = hero.dataset.base;
  const v = $("video", hero), pauseBtn = $(".hero__pause", hero), count = $(".hero__count", hero);
  let cur = 0, paused = false;
  pauseBtn.addEventListener("click", () => {
    paused = !paused;
    paused ? v.pause() : v.play();
    root.classList.toggle("motion-paused", paused);
    pauseBtn.textContent = paused ? "▶" : "❚❚";
    pauseBtn.setAttribute("aria-label", paused ? "Play animations" : "Pause animations");
  });
  const go = (i) => {
    cur = (i + loops.length) % loops.length;
    const l = loops[cur];
    v.poster = `${base}${l.slug}.webp`;
    v.src = `${base}${l.slug}.mp4`;
    v.setAttribute("aria-label", `${l.title}: seamless looping Blender render`);
    count.textContent = `${cur + 1} / ${loops.length} · ${l.title}`;
    if (!paused) v.play().catch(() => {}); // a src swap doesn't reliably re-trigger autoplay
  };
  $$("[data-loop-step]", hero).forEach((b) => b.addEventListener("click", () => go(cur + +b.dataset.loopStep)));
  go(+hero.dataset.start || 0);   // random loop picked by the inline script in the hero
}

if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
  root.classList.add("js-reveal");
  const rev = new IntersectionObserver((es) => es.forEach((e) => {
    if (e.isIntersecting) { e.target.classList.add("is-visible"); rev.unobserve(e.target); }
  }), { threshold: 0.08 });
  $$(".reveal").forEach((el) => rev.observe(el));
}

// Collapsible long text on phones: the toggle only shows when the text is actually cut off
const phone = matchMedia("(max-width: 700px)");
function syncClamps() {
  $$(".clamp").forEach((c) => {
    const btn = c.nextElementSibling;
    if (!btn?.classList.contains("clamp-toggle") || c.classList.contains("is-open")) return;
    c.classList.remove("is-short");
    const short = !phone.matches || c.scrollHeight <= c.clientHeight + 2;
    c.classList.toggle("is-short", short);
    btn.hidden = short;
  });
}
$$(".clamp-toggle").forEach((b) => b.addEventListener("click", (e) => {
  e.stopPropagation();
  const c = b.previousElementSibling, open = c.classList.toggle("is-open");
  b.textContent = open ? (b.dataset.less || "Less ↑") : (b.dataset.more || "More ↓");
  b.setAttribute("aria-expanded", open);
}));
// Folded lists: show the first N items (data-fold on desktop, data-fold-phone on phones), "+ N more" for the rest
function syncFolds() {
  $$(".fold").forEach((f) => {
    const btn = f.nextElementSibling, open = f.classList.contains("is-open");
    const limit = +(phone.matches ? f.dataset.foldPhone : f.dataset.fold) || Infinity;
    const items = [...f.children], extra = Math.max(0, items.length - limit);
    items.forEach((it, i) => (it.hidden = !open && i >= limit));
    btn.hidden = extra === 0;
    btn.textContent = open ? "Show less ↑" : `+ ${extra} more`;
    btn.setAttribute("aria-expanded", open);
  });
}
$$(".fold-toggle").forEach((b) => b.addEventListener("click", (e) => {
  e.stopPropagation();
  b.previousElementSibling.classList.toggle("is-open");
  syncFolds();
}));
phone.addEventListener("change", () => { syncClamps(); syncFolds(); });
document.fonts?.ready.then(syncClamps);
syncClamps();
syncFolds();

// Copy buttons
$$(".copy-btn").forEach((b) => b.addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(b.dataset.copy); } catch (e) { return; }
  const label = $(".copy-label", b) || b, old = label.textContent;   // only swap the label, not the whole tile
  label.textContent = "Copied!";
  setTimeout(() => (label.textContent = old), 1500);
}));

// Gallery filter
$$("[data-filter]").forEach((btn) => btn.addEventListener("click", () => {
  $$("[data-filter]").forEach((b) => b.classList.toggle("is-active", b === btn));
  $$("#gallery .tile").forEach((t) => (t.hidden = btn.dataset.filter !== "all" && t.dataset.cat !== btn.dataset.filter));
}));

// Lightbox
const box = $("#lightbox");
let tiles = [], idx = 0;
function show(i) {
  idx = (i + tiles.length) % tiles.length;
  const t = tiles[idx], media = $(".lightbox__media", box);
  media.replaceChildren();
  const el = document.createElement(t.dataset.video ? "video" : "img");
  if (t.dataset.video) Object.assign(el, { src: t.dataset.video, poster: t.dataset.full, controls: true, autoplay: true, loop: true, playsInline: true });
  else Object.assign(el, { src: t.dataset.full, alt: t.dataset.title });
  media.append(el);
  $(".lightbox__caption", box).textContent = `${t.dataset.title} · ${t.dataset.sub}`;
}
document.addEventListener("click", (e) => {
  const t = e.target.closest(".tile");
  if (!t) return;
  tiles = $$(".tile", t.parentElement).filter((x) => !x.hidden);
  show(tiles.indexOf(t));
  box.showModal();
});
$$("[data-step]", box).forEach((b) => b.addEventListener("click", () => show(idx + +b.dataset.step)));
box?.addEventListener("keydown", (e) => { if (e.key === "ArrowLeft") show(idx - 1); if (e.key === "ArrowRight") show(idx + 1); });
box?.addEventListener("click", (e) => { if (e.target === box) box.close(); });
box?.addEventListener("close", () => $(".lightbox__media", box).replaceChildren());
