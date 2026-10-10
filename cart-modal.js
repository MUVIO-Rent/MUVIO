/**
 * MUVIO Store — Rozetka-Style Quick Cart Modal Module (cart-modal.js)
 * 
 * Повнофункціональний ізольований модуль швидкого кошика у стилі Rozetka:
 * - Відкриття модалки при додаванні товару («КУПИТИ» / «ДОДАТИ В КОШИК») або кліку на кошик у шапці
 * - Фоновий оверлей із затемненням та закриттям по кліку поза вікном або Escape
 * - Чекбокс «Вибрано X з Y» (вибрати все / зняти вибір)
 * - Кнопка масового видалення вибраних товарів
 * - Степпер кількості «- [ N ] +» з миттєвим перерахунком суми
 * - Синхронізація лічильників шапки (#cart-count, #headerCartCount) у реальному часі
 * - Повна персистентність у localStorage (ключ: muvio_cart)
 */

(function () {
    'use strict';

    // 1. Отримання даних кошика з localStorage
    window.getCart = function () {
        try {
            const raw = localStorage.getItem('muvio_cart') || localStorage.getItem('muvio_cart_items');
            if (!raw) return [];
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) return [];
            return parsed.map((item, idx) => ({
                id: item.id !== undefined ? item.id : (idx + 1),
                name: item.name || 'Товар MUVIO',
                price: Number(item.price) || 0,
                oldPrice: Number(item.oldPrice) || 0,
                qty: Math.max(1, Number(item.qty) || 1),
                image: item.image || 'images/kolodkiaima.jpg',
                selected: item.selected !== false
            }));
        } catch (e) {
            console.error('Помилка читання кошика:', e);
            return [];
        }
    };

    // 2. Збереження даних кошика у localStorage
    window.saveCart = function (cart) {
        try {
            const data = JSON.stringify(cart);
            localStorage.setItem('muvio_cart', data);
            localStorage.setItem('muvio_cart_items', data);
        } catch (e) {
            console.error('Помилка запису кошика:', e);
        }
        window.updateHeaderBadges();
        window.dispatchEvent(new CustomEvent('muvio-cart-updated', { detail: { cart } }));
    };

    // 3. Синхронізація лічильників у шапці сайту
    window.updateHeaderBadges = function () {
        const cart = window.getCart();
        const totalQty = cart.reduce((sum, item) => sum + (item.qty || 1), 0);
        let totalPrice = 0;
        cart.forEach(item => {
            const q = item.qty || 1;
            totalPrice += (item.price || 0) * q;
        });

        // Оновлюємо всі елементи лічильника кошика
        document.querySelectorAll('#headerCartCount, #cart-count, .cart-count, .badge-cart').forEach(el => {
            el.textContent = totalQty;
        });

        const cartTotalEl = document.getElementById('headerCartTotal');
        if (cartTotalEl) {
            cartTotalEl.textContent = `${totalPrice.toLocaleString()} ₴`;
        }

        // Синхронізуємо кнопки каталогу та детальної сторінки
        window.syncProductCardButtons();
    };

    // Аліас для зворотної сумісності
    window.updateAllCartBadges = window.updateHeaderBadges;

    // 4. Синхронізація кнопок «Купити» / «В кошику» на активній сторінці
    window.syncProductCardButtons = function () {
        const cart = window.getCart();

        // Каталог (accessories.html)
        if (typeof PRODUCTS_DB !== 'undefined' && Array.isArray(PRODUCTS_DB)) {
            PRODUCTS_DB.forEach(prod => {
                const btn = document.getElementById(`addToCartBtn-${prod.id}`);
                if (!btn) return;
                const isInCart = cart.some(item => (item.id === prod.id || item.name === prod.name));
                if (isInCart) {
                    btn.classList.add('in-cart');
                    btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5"></i> <span>В кошику</span>`;
                } else {
                    btn.classList.remove('in-cart');
                    btn.innerHTML = `<i data-lucide="shopping-cart" class="w-3.5 h-3.5"></i> <span>Купити</span>`;
                }
            });
        }

        // Детальна сторінка (product.html)
        if (typeof currentProductId !== 'undefined') {
            const prod = (typeof PRODUCTS_DB !== 'undefined' && Array.isArray(PRODUCTS_DB))
                ? PRODUCTS_DB.find(p => p.id === currentProductId)
                : null;
            if (prod && typeof updateBuyButtonState === 'function') {
                updateBuyButtonState(prod);
            }
        }

        if (window.lucide) window.lucide.createIcons();
    };

    // 5. Перевірка наявності розмітки модального вікна або авто-створення
    function ensureCartModalDom() {
        if (document.getElementById('cartModalBackdrop')) return;

        const modalHtml = `
        <div id="cartModalBackdrop" class="cart-modal-backdrop hidden" onclick="handleCartBackdropClick(event)">
            <div class="cart-modal-window" role="dialog" aria-modal="true" aria-labelledby="cartModalTitle">
                <!-- Header -->
                <div class="cart-modal-header">
                    <div class="cart-modal-title-wrap">
                        <h3 class="cart-modal-title" id="cartModalTitle">Кошик</h3>
                        <label class="cart-select-all-label">
                            <input type="checkbox" id="cartSelectAllCheckbox" onchange="toggleCartSelectAll(this.checked)">
                            <span id="cartSelectAllText">Вибрано 0 з 0</span>
                        </label>
                    </div>
                    <div class="cart-header-actions">
                        <button type="button" class="cart-delete-selected-btn" onclick="deleteSelectedCartItems()" title="Видалити вибрані товари" id="cartDeleteSelectedBtn">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                            <span>Видалити вибрані</span>
                        </button>
                        <button type="button" class="cart-modal-close-btn" onclick="closeCartModal()" title="Закрити кошик" aria-label="Закрити">
                            &times;
                        </button>
                    </div>
                </div>

                <!-- Body (List of Items) -->
                <div class="cart-modal-body" id="cartModalBody"></div>

                <!-- Footer -->
                <div class="cart-modal-footer">
                    <button type="button" class="cart-continue-btn" onclick="closeCartModal()">
                        &larr; Продовжити покупки
                    </button>
                    <div class="cart-footer-right">
                        <div class="cart-total-block">
                            <div class="cart-total-label">Всього до сплати:</div>
                            <div class="cart-total-amount" id="cartModalTotalAmount">0 ₴</div>
                        </div>
                        <a href="cabinet.html" class="cart-checkout-btn" id="cartCheckoutBtn">
                            <span>Оформити замовлення</span>
                            <i data-lucide="arrow-right" class="w-4 h-4"></i>
                        </a>
                    </div>
                </div>
            </div>
        </div>`;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    // 6. Відкриття та закриття модалки
    window.openCartModal = function () {
        ensureCartModalDom();
        window.renderCartModal();
        const modal = document.getElementById('cartModalBackdrop');
        if (modal) {
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }
        if (window.lucide) window.lucide.createIcons();
    };

    window.closeCartModal = function () {
        const modal = document.getElementById('cartModalBackdrop');
        if (modal) {
            modal.classList.add('hidden');
            document.body.style.overflow = '';
        }
    };

    window.handleCartBackdropClick = function (e) {
        if (e && e.target && e.target.id === 'cartModalBackdrop') {
            window.closeCartModal();
        }
    };

    // 7. Рендеринг вмісту модального вікна
    window.renderCartModal = function () {
        ensureCartModalDom();
        const body = document.getElementById('cartModalBody');
        const totalEl = document.getElementById('cartModalTotalAmount');
        const selectAllCheck = document.getElementById('cartSelectAllCheckbox');
        const selectAllText = document.getElementById('cartSelectAllText');
        const deleteSelectedBtn = document.getElementById('cartDeleteSelectedBtn');
        const checkoutBtn = document.getElementById('cartCheckoutBtn');
        if (!body) return;

        const cart = window.getCart();

        if (cart.length === 0) {
            body.innerHTML = `
                <div class="cart-empty-state">
                    <div class="w-16 h-16 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-4 text-zinc-500">
                        <i data-lucide="shopping-bag" class="w-8 h-8"></i>
                    </div>
                    <h4 class="text-base font-bold text-white mb-1">Кошик порожній</h4>
                    <p class="text-xs text-zinc-400 mb-5">Але це ніколи не пізно виправити :)</p>
                    <button type="button" onclick="closeCartModal(); if (!window.location.pathname.endsWith('accessories.html')) window.location.href='accessories.html';" class="px-5 py-2.5 bg-[#1AB370] text-black font-bold text-xs rounded uppercase tracking-wider hover:bg-[#169B60] transition-colors">
                        Перейти до каталогу
                    </button>
                </div>
            `;
            if (totalEl) totalEl.textContent = '0 ₴';
            if (selectAllText) selectAllText.textContent = 'Вибрано 0 з 0';
            if (selectAllCheck) {
                selectAllCheck.checked = false;
                selectAllCheck.disabled = true;
            }
            if (deleteSelectedBtn) deleteSelectedBtn.style.display = 'none';
            if (checkoutBtn) checkoutBtn.classList.add('opacity-50', 'pointer-events-none');
            if (window.lucide) window.lucide.createIcons();
            window.syncProductCardButtons();
            return;
        }

        if (checkoutBtn) checkoutBtn.classList.remove('opacity-50', 'pointer-events-none');
        if (deleteSelectedBtn) deleteSelectedBtn.style.display = 'inline-flex';

        let selectedCount = 0;
        let totalPrice = 0;

        const itemsHtml = cart.map((item, idx) => {
            const isSelected = item.selected !== false;
            if (isSelected) {
                selectedCount++;
                totalPrice += (item.price || 0) * (item.qty || 1);
            }

            const itemSubtotal = (item.price || 0) * (item.qty || 1);
            const hasDiscount = item.oldPrice && item.oldPrice > item.price;
            const oldSubtotal = hasDiscount ? item.oldPrice * (item.qty || 1) : 0;
            const prodId = item.id || ((typeof PRODUCTS_DB !== 'undefined' && Array.isArray(PRODUCTS_DB)) ? (PRODUCTS_DB.find(p => p.name === item.name) || {}).id : 1) || 1;

            return `
                <div class="cart-item-card">
                    <input type="checkbox" class="cart-item-check" ${isSelected ? 'checked' : ''} onchange="toggleCartItemSelection(${idx}, this.checked)">
                    
                    <a href="product.html?id=${prodId}" class="cart-item-thumb-box" title="${item.name}">
                        <img src="${item.image || 'images/kolodkiaima.jpg'}" alt="${item.name}" class="cart-item-thumb">
                    </a>

                    <div class="cart-item-info">
                        <a href="product.html?id=${prodId}" class="cart-item-title">${item.name}</a>
                        <div class="cart-item-unit-price">${(item.price || 0).toLocaleString()} ₴ / шт.</div>
                    </div>

                    <div class="cart-item-stepper">
                        <button type="button" class="cart-step-btn" onclick="updateCartItemQty(${idx}, -1)" title="Зменшити">&minus;</button>
                        <input type="number" class="cart-step-input" value="${item.qty || 1}" min="1" max="99" onchange="setCartItemQty(${idx}, this.value)">
                        <button type="button" class="cart-step-btn" onclick="updateCartItemQty(${idx}, 1)" title="Збільшити">&plus;</button>
                    </div>

                    <div class="cart-item-price-block">
                        ${hasDiscount ? `<div class="cart-item-old-price">${oldSubtotal.toLocaleString()} ₴</div>` : ''}
                        <div class="cart-item-subtotal">${itemSubtotal.toLocaleString()} ₴</div>
                    </div>

                    <button type="button" class="cart-item-del-btn" onclick="removeCartItem(${idx})" title="Видалити товар">
                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                    </button>
                </div>
            `;
        }).join('');

        body.innerHTML = itemsHtml;
        if (totalEl) totalEl.textContent = `${totalPrice.toLocaleString()} ₴`;
        if (selectAllText) selectAllText.textContent = `Вибрано ${selectedCount} з ${cart.length}`;
        if (selectAllCheck) {
            selectAllCheck.disabled = false;
            selectAllCheck.checked = (selectedCount === cart.length && cart.length > 0);
        }

        if (window.lucide) window.lucide.createIcons();
        window.syncProductCardButtons();
    };

    // 8. Зміна кількості та вибору
    window.updateCartItemQty = function (index, delta) {
        const cart = window.getCart();
        if (!cart[index]) return;
        let current = cart[index].qty || 1;
        let next = current + delta;
        if (next < 1) next = 1;
        cart[index].qty = next;
        window.saveCart(cart);
        window.renderCartModal();
    };

    window.setCartItemQty = function (index, value) {
        const cart = window.getCart();
        if (!cart[index]) return;
        let val = parseInt(value, 10);
        if (isNaN(val) || val < 1) val = 1;
        cart[index].qty = val;
        window.saveCart(cart);
        window.renderCartModal();
    };

    window.toggleCartItemSelection = function (index, checked) {
        const cart = window.getCart();
        if (!cart[index]) return;
        cart[index].selected = checked;
        window.saveCart(cart);
        window.renderCartModal();
    };

    window.toggleCartSelectAll = function (checked) {
        const cart = window.getCart();
        cart.forEach(item => { item.selected = checked; });
        window.saveCart(cart);
        window.renderCartModal();
    };

    window.removeCartItem = function (index) {
        const cart = window.getCart();
        if (!cart[index]) return;
        cart.splice(index, 1);
        window.saveCart(cart);
        window.renderCartModal();
    };

    window.deleteSelectedCartItems = function () {
        let cart = window.getCart();
        cart = cart.filter(item => item.selected === false);
        window.saveCart(cart);
        window.renderCartModal();
    };

    // 9. Закриття по Escape та глобальна ініціалізація
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            window.closeCartModal();
        }
    });

    // Слухач синхронізації між вкладками браузера
    window.addEventListener('storage', (e) => {
        if (e.key === 'muvio_cart' || e.key === 'muvio_cart_items') {
            window.updateHeaderBadges();
            const modal = document.getElementById('cartModalBackdrop');
            if (modal && !modal.classList.contains('hidden')) {
                window.renderCartModal();
            }
        }
    });

    document.addEventListener('DOMContentLoaded', () => {
        window.updateHeaderBadges();
    });

})();
