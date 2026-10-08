"use strict";

// The one-use activation secret travels in the fragment, never in a URL query.
const activationForm = document.querySelector("[data-activation-form]");
if (activationForm && window.location.hash) {
  const fragment = window.location.hash.slice(1);
  const token = fragment.startsWith("token=")
    ? new URLSearchParams(fragment).get("token")
    : fragment;
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  const tokenInput = activationForm.querySelector('input[name="token"]');
  if (tokenInput && token) tokenInput.value = token;
}
