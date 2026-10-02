/*
 * Marks the page as script-capable so the CSS can show `.js-only` controls
 * and hide their no-script fallbacks. Loaded synchronously from <head> before
 * the stylesheet (templates/base.html) so the first paint already has the
 * class; keep it tiny and free of dependencies.
 */
document.documentElement.classList.add("js");
