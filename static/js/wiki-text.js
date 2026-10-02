/*
 * RTWikiText: the case/ss folding and all-tokens matching behind the
 * Bibliothek filter (wiki-library.js) and the chapter outline filter
 * (wiki-reader.js). Loaded by base.html ahead of every script that uses it.
 */
(function () {
  "use strict";

  /* Mirrors str.casefold() closely enough for German and English: the views
     build data-filter-text with casefold(), which turns "ß" into "ss". */
  function fold(text) {
    return String(text).toLowerCase().replace(/ß/g, "ss");
  }

  /* Whether every token occurs in `text` (both already folded). */
  function matchesAll(text, tokens) {
    return tokens.every(function (token) {
      return text.indexOf(token) !== -1;
    });
  }

  window.RTWikiText = { fold: fold, matchesAll: matchesAll };
})();
