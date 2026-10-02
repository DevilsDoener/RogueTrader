/*
 * Prevent double-submits: disable a form's submit button as soon as it's
 * submitted. Does not touch the sheet viewer's autosave, which saves via
 * fetch() on individual fields rather than a native form submit.
 * Loaded deferred by templates/base.html on every page.
 */
document.addEventListener("submit", function (event) {
  var form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  var submitButton = form.querySelector('button[type="submit"]');
  if (submitButton && !submitButton.disabled) {
    submitButton.disabled = true;
  }
});
