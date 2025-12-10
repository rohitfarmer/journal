(function () {
  // --- Dark mode toggle ---
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

  // --- Copy-to-clipboard helpers ---
  function fallbackCopy(text) {
    var textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'absolute';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
    } catch (e) {
      // ignore
    }
    document.body.removeChild(textarea);
  }

  var copyToastTimeout = null;

  function showCopyToast() {
    var toast = document.getElementById('copy-toast');
    if (!toast) return;

    toast.classList.add('visible');
    if (copyToastTimeout) {
      clearTimeout(copyToastTimeout);
    }
    copyToastTimeout = setTimeout(function () {
      toast.classList.remove('visible');
    }, 2000);
  }

  function initShareLinks() {
    document.addEventListener('click', function (event) {
      var link = event.target.closest('.entry-permalink');
      if (!link) return;

      event.preventDefault();

      var href = link.getAttribute('href') || '';
      var url;
      try {
        url = new URL(href, window.location.href).toString();
      } catch (e) {
        url = window.location.href;
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(
          function () {
            showCopyToast();
          },
          function () {
            fallbackCopy(url);
            showCopyToast();
          }
        );
      } else {
        fallbackCopy(url);
        showCopyToast();
      }
    });
  }

  // --- Init both features ---
  function initAll() {
    initThemeToggle();
    initShareLinks();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
