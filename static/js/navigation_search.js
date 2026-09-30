(() => {
    const input = document.getElementById('global-menu-search');
    const results = document.getElementById('global-menu-results');
    if (!input || !results) return;
    const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
    const links = [...document.querySelectorAll('.nav-menu a[href]')];
    function search() {
        results.replaceChildren();
        const query = normalize(input.value);
        results.hidden = !query;
        if (!query) return;
        const matches = links.filter(link => normalize(link.textContent).includes(query));
        for (const link of matches) {
            const result = document.createElement('a');
            result.href = link.href;
            result.textContent = link.textContent.trim();
            results.append(result);
        }
        if (!matches.length) results.textContent = 'No hay módulos con ese nombre. Busca productos o pedidos dentro de su módulo.';
    }
    input.addEventListener('input', search);
    input.addEventListener('keydown', event => {
        if (event.key === 'Escape') results.hidden = true;
        if (event.key === 'Enter') { event.preventDefault(); search(); }
        if (event.key === 'ArrowDown') { event.preventDefault(); results.querySelector('a')?.focus(); }
    });
    document.addEventListener('click', event => {
        if (!event.target.closest('.global-search')) results.hidden = true;
    });
})();
