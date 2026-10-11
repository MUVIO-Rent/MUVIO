/**
 * MUVIO Store — Rozetka-Style Quick Cart Modal Module (cart-modal.js)
 * 
 * Повнофункціональний ізольований модуль швидкого кошика у стилі Rozetka:
 * - Миттєве відкриття модального вікна при кліку на «КУПИТИ» / «ДОДАТИ В КОШИК» або на іконку кошика в шапці
 * - Фоновий оверлей із затемненням (backdrop blur + dark overlay) та закриття по кліку поза вікном або Escape
 * - Чекбокс «Вибрано X з Y» (можливість вибрати всі / зняти всі, стан indeterminate)
 * - Кнопка-іконка для масового видалення вибраних товарів
 * - Степпер кількості «− [ N ] +» (мінімум 1) із миттєвим перерахунком сум без перезавантаження сторінки
 * - Підтримка перекресленої старої ціни при знижці та актуальної суми за позицію
 * - Синхронізація лічильників шапки (#cart-count, #headerCartCount, .badge-cart) у реальному часі
 * - Повна персистентність у localStorage (ключі: muvio_cart та muvio_cart_items)
 * - Синхронізація стану кнопок на сторінці («Купити» ↔ «В кошику»)
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
                icon: item.icon || 'package',
                selected: item.selected !== false
            }));
        } catch (e) {
            console.error('MUVIO Cart: Помилка читання кошика:', e);
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
            console.error('MUVIO Cart: Помилка запису кошика:', e);
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

        // Оновлюємо всі лічильники кошика на сторінці
        document.querySelectorAll('#cart-count, #headerCartCount, .cart-count, .badge-cart').forEach(el => {
            el.textContent = totalQty;
        });

        const cartTotalEl = document.getElementById('headerCartTotal');
        if (cartTotalEl) {
            cartTotalEl.textContent = `${totalPrice.toLocaleString()} ₴`;
        }

        // Синхронізуємо кнопки «Купити» / «В кошику»
        window.syncProductCardButtons();
    };

    window.updateAllCartBadges = window.updateHeaderBadges;

    // 4. Синхронізація кнопок «Купити» / «В кошику» на активній сторінці
    window.syncProductCardButtons = function () {
        const cart = window.getCart();

        // Каталог товарів (accessories.html)
        if (typeof PRODUCTS_DB !== 'undefined' && Array.isArray(PRODUCTS_DB)) {
            PRODUCTS_DB.forEach(prod => {
                const btn = document.getElementById(`addToCartBtn-${prod.id}`);
                if (!btn) return;
                const isInCart = cart.some(item => (item.id === prod.id || item.name === prod.name));
                if (isInCart) {
                    btn.classList.add('in-cart');
                    btn.innerHTML = `<svg class="w-3.5 h-3.5 inline mr-1.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg><span>В кошику</span>`;
                } else {
                    btn.classList.remove('in-cart');
                    btn.innerHTML = `<svg class="w-3.5 h-3.5 inline mr-1.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/></svg><span>Купити</span>`;
                }
            });
        }

        // Детальна сторінка товару (product.html)
        const pdBuyBtn = document.getElementById('pdBuyBtn');
        if (pdBuyBtn) {
            let prodName = null;
            if (typeof currentProductId !== 'undefined' && typeof PRODUCTS_DB !== 'undefined' && Array.isArray(PRODUCTS_DB)) {
                const p = PRODUCTS_DB.find(item => item.id === currentProductId);
                if (p) prodName = p.name;
            }
            const isInCart = prodName
                ? cart.some(item => (item.id === currentProductId || item.name === prodName))
                : false;

            if (isInCart) {
                pdBuyBtn.classList.add('in-cart');
                pdBuyBtn.innerHTML = `<svg class="w-5 h-5 inline mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg><span>В кошику</span>`;
            } else {
                pdBuyBtn.classList.remove('in-cart');
                pdBuyBtn.innerHTML = `<svg class="w-5 h-5 inline mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/></svg><span>Купити</span>`;
            }
        }

        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    };

    // 5. Додавання товару в кошик з негайним відкриттям модалки
    window.addToCart = function (productOrId, options) {
        options = options || {};
        let prod = null;

        if (typeof productOrId === 'object' && productOrId !== null) {
            prod = productOrId;
        } else if (typeof PRODUCTS_DB !== 'undefined' && Array.isArray(PRODUCTS_DB)) {
            prod = PRODUCTS_DB.find(p => p.id === Number(productOrId) || p.id === productOrId);
        }

        if (!prod) {
            console.warn('MUVIO Cart: Товар не знайдено за ідентифікатором:', productOrId);
            return;
        }

        const cart = window.getCart();
        const existingIndex = cart.findIndex(item => (item.id === prod.id || item.name === prod.name));

        if (existingIndex > -1) {
            // Товар вже в кошику — активуємо його чекбокс
            cart[existingIndex].selected = true;
            if (options.increment) {
                cart[existingIndex].qty = (cart[existingIndex].qty || 1) + (options.qty || 1);
            }
        } else {
            // Новий товар
            cart.push({
                id: prod.id,
                name: prod.name,
                price: Number(prod.price) || 0,
                oldPrice: Number(prod.oldPrice) || 0,
                qty: Math.max(1, Number(options.qty) || 1),
                image: prod.image || (Array.isArray(prod.images) && prod.images[0]) || 'images/kolodkiaima.jpg',
                icon: prod.icon || 'package',
                selected: true
            });
        }

        window.saveCart(cart);

        if (typeof window.showToast === 'function') {
            window.showToast(`«${prod.name}» додано в кошик!`);
        }

        if (options.openModal !== false) {
            window.openCartModal();
        }
    };

    window.toggleCart = function (prodId) {
        window.addToCart(prodId);
    };

    // 6. Перевірка або створення розмітки модального вікна в кінці body
    function ensureCartModalDom() {
        if (document.getElementById('cartModalBackdrop')) return;

        const modalHtml = `
        <div id="cartModalBackdrop" class="cart-modal-backdrop hidden" onclick="handleCartBackdropClick(event)">
            <div class="cart-modal-window" role="dialog" aria-modal="true" aria-labelledby="cartModalTitle" onclick="event.stopPropagation()">
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
                            <svg class="cart-del-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                <line x1="10" y1="11" x2="10" y2="17"></line>
                                <line x1="14" y1="11" x2="14" y2="17"></line>
                            </svg>
                            <span class="cart-del-btn-text">Видалити вибрані</span>
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
                        <a href="cabinet.html#cart" onclick="try{localStorage.setItem('muvio_target_tab','cart');}catch(e){}" class="cart-checkout-btn" id="cartCheckoutBtn">
                            <span>Оформити замовлення</span>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                                <polyline points="12 5 19 12 12 19"></polyline>
                            </svg>
                        </a>
                    </div>
                </div>
            </div>
        </div>`;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    // 7. Відкриття та закриття модалки
    window.openCartModal = function () {
        ensureCartModalDom();
        window.renderCartModal();
        const modal = document.getElementById('cartModalBackdrop');
        if (modal) {
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
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

    // 8. Рендеринг вмісту модального вікна
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
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-2Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/>
                        </svg>
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
                selectAllCheck.indeterminate = false;
                selectAllCheck.disabled = true;
            }
            if (deleteSelectedBtn) {
                deleteSelectedBtn.disabled = true;
            }
            if (checkoutBtn) {
                checkoutBtn.classList.add('disabled');
                checkoutBtn.setAttribute('aria-disabled', 'true');
            }
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
            window.syncProductCardButtons();
            return;
        }

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
                    <input type="checkbox" class="cart-item-check" ${isSelected ? 'checked' : ''} onchange="toggleCartItemSelection(${idx}, this.checked)" aria-label="Вибрати ${item.name}">
                    
                    <a href="product.html?id=${prodId}" class="cart-item-thumb-box" title="${item.name}">
                        <img src="${item.image || 'images/kolodkiaima.jpg'}" alt="${item.name}" class="cart-item-thumb" onerror="this.src='images/kolodkiaima.jpg'">
                    </a>

                    <div class="cart-item-info">
                        <a href="product.html?id=${prodId}" class="cart-item-title">${item.name}</a>
                        <div class="cart-item-unit-price">${(item.price || 0).toLocaleString()} ₴ / шт.</div>
                    </div>

                    <div class="cart-item-bottom-row">
                        <div class="cart-item-stepper">
                            <button type="button" class="cart-step-btn" onclick="updateCartItemQty(${idx}, -1)" title="Зменшити" ${item.qty <= 1 ? 'disabled' : ''}>&minus;</button>
                            <input type="number" class="cart-step-input" value="${item.qty || 1}" min="1" max="99" onchange="setCartItemQty(${idx}, this.value)" aria-label="Кількість">
                            <button type="button" class="cart-step-btn" onclick="updateCartItemQty(${idx}, 1)" title="Збільшити">&plus;</button>
                        </div>

                        <div class="cart-item-price-block">
                            ${hasDiscount ? `<div class="cart-item-old-price">${oldSubtotal.toLocaleString()} ₴</div>` : ''}
                            <div class="cart-item-subtotal">${itemSubtotal.toLocaleString()} ₴</div>
                        </div>
                    </div>

                    <button type="button" class="cart-item-del-btn" onclick="removeCartItem(${idx})" title="Видалити товар" aria-label="Видалити товар">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            <line x1="10" y1="11" x2="10" y2="17"></line>
                            <line x1="14" y1="11" x2="14" y2="17"></line>
                        </svg>
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
            selectAllCheck.indeterminate = (selectedCount > 0 && selectedCount < cart.length);
        }

        if (deleteSelectedBtn) {
            deleteSelectedBtn.disabled = (selectedCount === 0);
        }

        if (checkoutBtn) {
            if (selectedCount === 0) {
                checkoutBtn.classList.add('disabled');
                checkoutBtn.setAttribute('aria-disabled', 'true');
            } else {
                checkoutBtn.classList.remove('disabled');
                checkoutBtn.removeAttribute('aria-disabled');
            }
        }

        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
        window.syncProductCardButtons();
    };

    // 9. Зміна кількості та вибору товарів
    window.updateCartItemQty = function (index, delta) {
        const cart = window.getCart();
        if (!cart[index]) return;
        let current = Number(cart[index].qty) || 1;
        let next = current + delta;
        if (next < 1) next = 1;
        if (next > 99) next = 99;
        cart[index].qty = next;
        window.saveCart(cart);
        window.renderCartModal();
    };

    window.setCartItemQty = function (index, value) {
        const cart = window.getCart();
        if (!cart[index]) return;
        let val = parseInt(value, 10);
        if (isNaN(val) || val < 1) val = 1;
        if (val > 99) val = 99;
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

    // 10. Обробник натискання клавіші Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            window.closeCartModal();
        }
    });

    // 11. Слухач міжвкладочної синхронізації (storage event)
    window.addEventListener('storage', (e) => {
        if (e.key === 'muvio_cart' || e.key === 'muvio_cart_items') {
            window.updateHeaderBadges();
            const modal = document.getElementById('cartModalBackdrop');
            if (modal && !modal.classList.contains('hidden')) {
                window.renderCartModal();
            }
        }
    });

    // 12. Початкова синхронізація при завантаженні документа
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.updateHeaderBadges();
        });
    } else {
        window.updateHeaderBadges();
    }

})();
