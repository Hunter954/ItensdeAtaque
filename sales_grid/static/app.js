// URL preview helper for admin pages
(function () {
  function updatePreview(input) {
    const wrap = input.closest('div');
    const prev = wrap ? wrap.querySelector('.preview') : null;
    if (!prev) return;
    const url = (input.value || '').trim();
    prev.innerHTML = '';
    if (!url) return;
    const img = document.createElement('img');
    img.src = url;
    img.alt = 'preview';
    img.style.maxHeight = '80px';
    img.style.maxWidth = '100%';
    img.style.borderRadius = '10px';
    img.onerror = () => { prev.innerHTML = '<div class="text-danger small">Preview indisponível</div>'; };
    prev.appendChild(img);
  }

  document.addEventListener('input', (e) => {
    const t = e.target;
    if (t && t.classList && t.classList.contains('url-preview')) updatePreview(t);
  });

  window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.url-preview').forEach(updatePreview);
  });
})();
