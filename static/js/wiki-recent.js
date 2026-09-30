/*
 * Shared wiki helpers, loaded by base.html ahead of every script that uses
 * them:
 *
 * - RTWikiRecent: the reader's recent positions ("rt-wiki-recent" in
 *   localStorage), written by the chapter reader and read by the Bibliothek's
 *   "Weiterlesen" and the Auspex palette.
 * - RTWikiText: the case/ss folding and all-tokens matching behind the
 *   Bibliothek filter and the chapter outline filter.
 *
 * Stored shape: a JSON array, newest first, of {title, chapter, url}; one
 * entry per chapter path, at most MAX. The data is under the reader's control
 * (and any other script on the origin), so only same-site wiki paths are ever
 * handed out as link targets. Every storage access is guarded: without
 * storage the features that use it simply stay empty.
 */
(function () {
  "use strict";

  var KEY = "rt-wiki-recent";
  var MAX = 8;

  /* A root-relative path under one of `prefixes` (default: the wiki). A
     backslash is refused outright: browsers read "/\host" as "//host". */
  function isSafeUrl(url, prefixes) {
    if (typeof url !== "string" || url.indexOf("\\") !== -1) {
      return false;
    }
    return (prefixes || ["/wiki/"]).some(function (prefix) {
      return url.indexOf(prefix) === 0;
    });
  }

  function isValidEntry(entry) {
    return (
      !!entry &&
      typeof entry === "object" &&
      isSafeUrl(entry.url) &&
      typeof entry.title === "string" &&
      entry.title !== ""
    );
  }

  function load() {
    var raw;
    try {
      raw = window.localStorage.getItem(KEY);
    } catch (error) {
      return [];
    }
    if (!raw) {
      return [];
    }
    var parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (error) {
      return [];
    }
    return Array.isArray(parsed) ? parsed.filter(isValidEntry) : [];
  }

  /* The valid entries, newest first, at most `limit` (default MAX). */
  function read(limit) {
    return load().slice(0, typeof limit === "number" ? limit : MAX);
  }

  /* Put `entry` first, dropping the older position in the same chapter. */
  function record(entry) {
    if (!isValidEntry(entry)) {
      return;
    }
    var path = entry.url.split("#")[0];
    var kept = load().filter(function (other) {
      return other.url.split("#")[0] !== path;
    });
    kept.unshift(entry);
    try {
      window.localStorage.setItem(KEY, JSON.stringify(kept.slice(0, MAX)));
    } catch (error) {
      /* Storage full or disabled: "Weiterlesen" simply stays empty. */
    }
  }

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

  window.RTWikiRecent = { read: read, record: record, isSafeUrl: isSafeUrl };
  window.RTWikiText = { fold: fold, matchesAll: matchesAll };
})();
