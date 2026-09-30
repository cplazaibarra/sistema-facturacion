(() => {
    const source = document.getElementById('sales-view-data');
    if (!source) return;
    const sales = JSON.parse(source.textContent);
    const list = document.getElementById('sales-list-view');
    const alternate = document.getElementById('sales-alternate-view');
    const keys = ['number', 'customer', 'date', 'products', 'total', 'status', 'payment', 'due', 'seller'];
    const params = new URL(location.href).searchParams;
    document.querySelectorAll('#sales-list-view th.sf-th-sortable').forEach((heading, index) => {
        const key = keys[index];
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'sales-sort-button';
        button.append(...heading.childNodes);
        heading.append(button);
        const active = params.get('sort') === key;
        heading.setAttribute('aria-sort', active ? (params.get('direction') === 'asc' ? 'ascending' : 'descending') : 'none');
        button.addEventListener('click', () => {
            const url = new URL(location.href);
            const direction = url.searchParams.get('sort') === key && url.searchParams.get('direction') === 'asc' ? 'desc' : 'asc';
            url.searchParams.set('sort', key);
            url.searchParams.set('direction', direction);
            url.searchParams.set('page', '1');
            location.assign(url);
        });
    });
    const money = value => new Intl.NumberFormat('es-CL', {style:'currency', currency:'CLP', minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(value || 0));
    function element(tag, text, className) {
        const node = document.createElement(tag);
        if (text !== undefined) node.textContent = text;
        if (className) node.className = className;
        return node;
    }
    function card(sale) {
        const node = element('button', undefined, 'sales-card');
        node.type = 'button';
        node.append(element('strong', sale.sale_number), element('span', sale.customer?.name || 'Sin cliente'), element('span', money(sale.total_raw)));
        node.addEventListener('click', () => window.openVentaDetailModal(sale));
        return node;
    }
    const firstDate = sales.find(sale => /^\d{4}-\d{2}-\d{2}$/.test(sale.date || ''))?.date;
    let month = firstDate ? new Date(`${firstDate}T12:00:00`) : new Date();
    month = new Date(month.getFullYear(), month.getMonth(), 1);
    window.renderSalesView = name => {
        if (!['lista','kanban','calendario'].includes(name)) name = 'lista';
        list.hidden = name !== 'lista';
        alternate.hidden = name === 'lista';
        document.querySelectorAll('.sf-tab').forEach(tab => {
            const active = tab.getAttribute('onclick')?.includes(`'${name}'`);
            tab.classList.toggle('active', !!active);
            tab.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        const url = new URL(location.href);
        url.searchParams.set('view', name);
        history.replaceState(null, '', url);
        alternate.replaceChildren();
        if (name === 'lista') return;
        alternate.append(element('p', 'Ventas de esta página. Los filtros y la paginación también se aplican a esta vista.', 'sales-view-note'));
        if (!sales.length) { alternate.append(element('p', 'No hay ventas con los filtros actuales.')); return; }
        if (name === 'kanban') {
            const board = element('div', undefined, 'sales-board');
            const states = [...new Set(['Pendiente','En Preparación','Para Despacho','Completada','Cancelada', ...sales.map(sale => sale.status.label)])];
            for (const state of states) {
                const column = element('section', undefined, 'sales-column');
                const items = sales.filter(sale => sale.status.label === state);
                column.append(element('h3', `${state} (${items.length})`));
                items.forEach(sale => column.append(card(sale)));
                if (!items.length) column.append(element('p', 'Sin ventas en esta página'));
                board.append(column);
            }
            alternate.append(board);
        } else {
            const controls = element('div', undefined, 'sales-calendar-controls');
            for (const [text,delta] of [['Mes anterior',-1], ['Mes siguiente',1]]) {
                const button = element('button', text); button.type = 'button';
                button.addEventListener('click', () => {month = new Date(month.getFullYear(), month.getMonth()+delta, 1); window.renderSalesView('calendario');});
                controls.append(button);
            }
            controls.append(element('h3', month.toLocaleDateString('es-CL', {month:'long',year:'numeric'})));
            alternate.append(controls);
            const grid = element('div', undefined, 'sales-calendar');
            ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'].forEach(day => grid.append(element('strong', day)));
            for (let i=0; i<(month.getDay()+6)%7; i++) grid.append(element('div'));
            const count = new Date(month.getFullYear(),month.getMonth()+1,0).getDate();
            for (let day=1; day<=count; day++) {
                const cell = element('section', undefined, 'sales-day');
                cell.append(element('strong', String(day)));
                const date = `${month.getFullYear()}-${String(month.getMonth()+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
                sales.filter(sale => sale.date === date).forEach(sale => cell.append(card(sale)));
                grid.append(cell);
            }
            alternate.append(grid);
        }
    };
    window.renderSalesView(params.get('view') || 'lista');
})();
