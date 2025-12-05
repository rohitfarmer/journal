(function () {
  function initThemeToggle() {
    var toggle = document.getElementById('theme-toggle');
    if (!toggle) return;

    var saved = localStorage.getItem('theme');
    if (saved === 'dark') {
      toggle.checked = true;
    } else if (saved === 'light') {
      toggle.checked = false;
    }

    toggle.addEventListener('change', function () {
      localStorage.setItem('theme', toggle.checked ? 'dark' : 'light');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initThemeToggle);
  } else {
    initThemeToggle();
  }
})();
