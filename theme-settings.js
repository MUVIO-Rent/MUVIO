/**
 * ==========================================================================
 * MUVIO — GLOBAL THEME, LANGUAGE & FONT-SCALE SYNCHRONIZATION MODULE
 * (theme-settings.js)
 * Architecture: Single Source of Truth for Dark Theme, I18N, Range Slider & Cross-Tab Sync
 * ==========================================================================
 */

(function () {
    'use strict';

    // --------------------------------------------------------------------------
    // 1. UNIFIED I18N TRANSLATIONS DICTIONARY (UA / EN)
    // --------------------------------------------------------------------------
    const MUVIO_I18N = {
        ua: {
            nav_catalog: "КАТАЛОГ",
            nav_calculator: "КАЛЬКУЛЯТОР",
            nav_service: "СЕРВІС",
            nav_terms: "УМОВИ ОРЕНДИ",
            nav_franchise: "ФРАНШИЗА",
            nav_login: "ВХІД",
            mobile_catalog: "КАТАЛОГ СКУТЕРІВ",
            mobile_calc: "КАЛЬКУЛЯТОР ОРЕНДИ",
            mobile_service: "СЕРВІС: ВУЛ. ПРИМОРСЬКА, 22",
            mobile_terms: "УМОВИ ОРЕНДИ ТА ВІДПОВІДАЛЬНІСТЬ",
            mobile_franchise: "ФРАНШИЗА ТА ПАРТНЕРСТВО",
            mobile_cabinet: "ОСОБИСТИЙ КАБІНЕТ",
            settings_title_short: "ОПЦІЇ",
            settings_heading: "НАЛАШТУВАННЯ",
            settings_theme_label: "ТЕМА САЙТУ",
            theme_light: "СВІТЛА",
            theme_dark: "ТЕМНА",
            settings_lang_label: "МОВА / LANGUAGE",
            lang_ua: "УКР",
            lang_en: "ENG",
            settings_font_label: "РОЗМІР ТЕКСТУ",

            // Index landing elements
            hero_tag: "MUVIO — ТВОЄ ELECTRO CITY",
            hero_title: "ОРЕНДА ТА ВИКУП<br>КУР'ЄРСЬКОГО ТА ТУРИСТИЧНОГО<br>ЕЛЕКТРОТРАНСПОРТУ В ОДЕСІ",
            hero_subtitle: "Каталог скутерів та велосипедів у зборі з АКБ. Офіційний договір, повне планове сервісне обслуговування, фіксований щотижневий платіж та прозора програма викупу (Rent-to-Own).",
            hero_btn_choose: "ОБРАТИ СКУТЕР",
            hero_btn_calc: "КАЛЬКУЛЯТОР ОРЕНДИ",
            hero_badge_rent: "ОРЕНДА",
            hero_per_day: "/ ДОБА",
            hero_per_week: "/ ТИЖДЕНЬ",
            hero_per_month: "/ МІСЯЦЬ",
            hero_feat_range: "ДО 160 КМ НА ОДНОМУ ЗАРЯДІ",
            hero_feat_range_sub: "З можливістю взяти другий знімний АКБ",
            hero_feat_address: "ОДЕСА, ВУЛ. ПРИМОРСЬКА, 22",
            hero_feat_address_sub: "ПН — НД: з 11:00 до 22:00",
            hero_feat_bot: "ОНЛАЙН БОТ У TELEGRAM 24/7",
            hero_feat_bot_sub: "Особистий кабінет з автоматичним розрахунком та оплатою днів оренди і викупу",
            cat_tag: "ОФІЦІЙНИЙ АВТОПАРК MUVIO",
            cat_title: "КАТАЛОГ ТЕХНІКИ В НАЯВНОСТІ",
            cat_desc: "Всі моделі укомплектовані знімним АКБ та зарядним пристроєм. Реальні тарифи оренди та повної вартості викупу.",
            filter_all: "ВСІ МОДЕЛІ",
            filter_scooters: "🛵 СКУТЕРИ",
            filter_bikes: "🚲 ВЕЛОСИПЕДИ",

            // Cabinet elements
            cabinet_title: "ОСОБИСТИЙ КАБІНЕТ",
            cabinet_subtitle: "Увійдіть або зареєструйтесь для доступу до вашого кабінету, оренди та бонусів.",
            auth_tab_login: "ВХІД",
            auth_tab_register: "РЕЄСТРАЦІЯ",
            login_ident_label: "ЛОГІН АБО ТЕЛЕФОН",
            login_pass_label: "ПАРОЛЬ",
            login_forgot_btn: "Забули пароль?",
            login_btn_text: "УВІЙТИ В КАБІНЕТ",
            reg_login_label: "ЛОГІН",
            reg_phone_label: "НОМЕР ТЕЛЕФОНУ",
            reg_pass_label: "ПАРОЛЬ",
            reg_btn_text: "ЗАРЕЄСТРУВАТИСЯ",
            card_active_status: "АКТИВНА ОРЕНДА",
            lbl_frame_id: "Номер рами / ID:",
            lbl_contract: "Договір:",
            lbl_valid_until: "Діє до:",
            lbl_rate_topay: "Тариф / До сплати:",
            lbl_bonus_bal: "Бонусний баланс:",
            lbl_service_hub: "Сервісний хаб:",
            lbl_timeline: "ШКАЛА РОЗРАХУНКОВОГО ПЕРІОДУ",
            lbl_timeline_start: "Початок періоду",
            lbl_timeline_mid: "Екватор тижня",
            lbl_timeline_paid: "Оплачено",
            btn_pay_rent: "ОПЛАТА ОРЕНДИ",
            btn_buyout_req: "ПОДАТИ ЗАЯВКУ НА ВИКУП",
            btn_report_issue: "ПОВІДОМИТИ ПРО ПОЛОМКУ",
            tab_payments: "💳 ІСТОРІЯ ПЛАТЕЖІВ",
            tab_repairs: "🛠 ІСТОРІЯ ТО ТА РЕМОНТІВ",
            tab_service: "📍 СЕРВІСНИЙ ХАБ ТА SOS"
        },
        en: {
            nav_catalog: "CATALOG",
            nav_calculator: "CALCULATOR",
            nav_service: "SERVICE",
            nav_terms: "TERMS",
            nav_franchise: "FRANCHISE",
            nav_login: "LOGIN",
            mobile_catalog: "SCOOTER CATALOG",
            mobile_calc: "RENTAL CALCULATOR",
            mobile_service: "SERVICE HUB: 22 PRYMORSKA ST.",
            mobile_terms: "RENTAL TERMS & CONDITIONS",
            mobile_franchise: "FRANCHISE & PARTNERSHIP",
            mobile_cabinet: "DASHBOARD",
            settings_title_short: "OPTIONS",
            settings_heading: "SETTINGS",
            settings_theme_label: "SITE THEME",
            theme_light: "LIGHT",
            theme_dark: "DARK",
            settings_lang_label: "LANGUAGE",
            lang_ua: "UKR",
            lang_en: "ENG",
            settings_font_label: "TEXT SIZE",

            // Index landing elements
            hero_tag: "MUVIO — YOUR ELECTRO CITY",
            hero_title: "RENTAL & BUYOUT OF COMMERCIAL ELECTRIC VEHICLES IN ODESA",
            hero_subtitle: "Catalog of scooters and e-bikes with battery pack. Official contract, full scheduled maintenance, fixed weekly payment and transparent Rent-to-Own buyout program.",
            hero_btn_choose: "CHOOSE SCOOTER",
            hero_btn_calc: "RENTAL CALCULATOR",
            hero_badge_rent: "RENTAL",
            hero_per_day: "/ DAY",
            hero_per_week: "/ WEEK",
            hero_per_month: "/ MONTH",
            hero_feat_range: "UP TO 160 KM PER CHARGE",
            hero_feat_range_sub: "Option to take a second removable battery",
            hero_feat_address: "ODESA, 22 PRYMORSKA STR.",
            hero_feat_address_sub: "MON — SUN: 11:00 to 22:00",
            hero_feat_bot: "ONLINE TELEGRAM BOT 24/7",
            hero_feat_bot_sub: "Client dashboard with automated calculation and payment of rental & buyout days",
            cat_tag: "OFFICIAL MUVIO FLEET",
            cat_title: "IN-STOCK FLEET CATALOG",
            cat_desc: "All models equipped with removable battery and fast charger. Live rental rates and complete buyout terms.",
            filter_all: "ALL MODELS",
            filter_scooters: "🛵 SCOOTERS",
            filter_bikes: "🚲 E-BIKES",

            // Cabinet elements
            cabinet_title: "CLIENT DASHBOARD",
            cabinet_subtitle: "Log in or register to access your account, rental status and bonuses.",
            auth_tab_login: "LOGIN",
            auth_tab_register: "REGISTER",
            login_ident_label: "LOGIN OR PHONE",
            login_pass_label: "PASSWORD",
            login_forgot_btn: "Forgot password?",
            login_btn_text: "SIGN IN TO DASHBOARD",
            reg_login_label: "LOGIN",
            reg_phone_label: "PHONE NUMBER",
            reg_pass_label: "PASSWORD",
            reg_btn_text: "CREATE ACCOUNT",
            card_active_status: "ACTIVE RENTAL",
            lbl_frame_id: "Frame ID:",
            lbl_contract: "Contract:",
            lbl_valid_until: "Valid until:",
            lbl_rate_topay: "Rate / To pay:",
            lbl_bonus_bal: "Bonus balance:",
            lbl_service_hub: "Service hub:",
            lbl_timeline: "BILLING CYCLE TIMELINE",
            lbl_timeline_start: "Cycle start",
            lbl_timeline_mid: "Midweek",
            lbl_timeline_paid: "Paid",
            btn_pay_rent: "PAY RENT",
            btn_buyout_req: "APPLY FOR BUYOUT",
            btn_report_issue: "REPORT BREAKDOWN",
            tab_payments: "💳 PAYMENT HISTORY",
            tab_repairs: "🛠 MAINTENANCE & REPAIRS",
            tab_service: "📍 SERVICE HUB & SOS"
        }
    };

    window.MUVIO_I18N = MUVIO_I18N;

    const DEFAULT_SETTINGS = {
        theme: 'light',
        lang: 'ua',
        fontScale: 100
    };

    // --------------------------------------------------------------------------
    // 2. SETTINGS GET / SAVE HELPERS
    // --------------------------------------------------------------------------
    function getSiteSettings() {
        try {
            const raw = localStorage.getItem('muvio_site_settings');
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed.fontScale === undefined) {
                    if (parsed.fontSize === 'small') parsed.fontScale = 90;
                    else if (parsed.fontSize === 'large') parsed.fontScale = 110;
                    else parsed.fontScale = 100;
                }
                return Object.assign({}, DEFAULT_SETTINGS, parsed);
            }
        } catch (e) {
            console.warn('Failed to parse muvio_site_settings:', e);
        }
        return Object.assign({}, DEFAULT_SETTINGS);
    }

    function saveSiteSettings(settings) {
        try {
            localStorage.setItem('muvio_site_settings', JSON.stringify(settings));
        } catch (e) {
            console.warn('Failed to save muvio_site_settings:', e);
        }
    }

    // --------------------------------------------------------------------------
    // 3. SYNCHRONOUS ANTI-FLICKER EXECUTION
    // --------------------------------------------------------------------------
    try {
        const initS = getSiteSettings();
        if (initS.theme === 'dark') {
            document.documentElement.classList.add('theme-dark');
        } else {
            document.documentElement.classList.remove('theme-dark');
        }
        const scaleVal = Math.max(50, Math.min(150, parseInt(initS.fontScale, 10) || 100));
        document.documentElement.style.fontSize = (scaleVal / 100 * 16) + 'px';
    } catch (e) {}

    // --------------------------------------------------------------------------
    // 4. THEME CONTROLLER
    // --------------------------------------------------------------------------
    function setSiteTheme(theme) {
        const settings = getSiteSettings();
        settings.theme = theme;
        saveSiteSettings(settings);
        applySiteTheme(theme);
    }

    function applySiteTheme(theme) {
        const btnLight = document.getElementById('themeBtnLight');
        const btnDark = document.getElementById('themeBtnDark');
        const badge = document.getElementById('currentThemeBadge');

        if (theme === 'dark') {
            document.documentElement.classList.add('theme-dark');
            if (badge) badge.textContent = 'DARK';
            if (btnDark) {
                btnDark.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-[#1D5D3B] text-white';
            }
            if (btnLight) {
                btnLight.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-slate-100 text-slate-700 hover:bg-slate-200';
            }
        } else {
            document.documentElement.classList.remove('theme-dark');
            if (badge) badge.textContent = 'LIGHT';
            if (btnLight) {
                btnLight.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-[#1D5D3B] text-white';
            }
            if (btnDark) {
                btnDark.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-slate-100 text-slate-700 hover:bg-slate-200';
            }
        }
    }

    // --------------------------------------------------------------------------
    // 5. LANGUAGE CONTROLLER
    // --------------------------------------------------------------------------
    function setSiteLanguage(lang) {
        const settings = getSiteSettings();
        settings.lang = lang;
        saveSiteSettings(settings);
        applySiteLanguage(lang);
    }

    function applySiteLanguage(lang) {
        const btnUa = document.getElementById('langBtnUa');
        const btnEn = document.getElementById('langBtnEn');
        const badge = document.getElementById('currentLangBadge');

        if (lang === 'en') {
            if (badge) badge.textContent = 'EN';
            if (btnEn) {
                btnEn.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-[#1D5D3B] text-white';
            }
            if (btnUa) {
                btnUa.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-slate-100 text-slate-700 hover:bg-slate-200';
            }
        } else {
            if (badge) badge.textContent = 'UA';
            if (btnUa) {
                btnUa.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-[#1D5D3B] text-white';
            }
            if (btnEn) {
                btnEn.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-slate-100 text-slate-700 hover:bg-slate-200';
            }
        }

        const dict = MUVIO_I18N[lang] || MUVIO_I18N.ua;
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key && dict[key]) {
                if (dict[key].includes('<br>') || dict[key].includes('<span')) {
                    el.innerHTML = dict[key];
                } else {
                    el.textContent = dict[key];
                }
            }
        });

        if (typeof window.renderCatalog === 'function' && typeof window.currentCatalogFilter !== 'undefined') {
            try { window.renderCatalog(window.currentCatalogFilter); } catch (err) {}
        }

        updateHeaderUserName();
    }

    // --------------------------------------------------------------------------
    // 6. FONT SCALE RANGE SLIDER CONTROLLER
    // --------------------------------------------------------------------------
    function setSiteFontScale(val) {
        val = parseInt(val, 10);
        if (isNaN(val)) val = 100;
        val = Math.max(50, Math.min(150, val));

        const settings = getSiteSettings();
        settings.fontScale = val;
        saveSiteSettings(settings);
        applySiteFontScale(val);
    }

    function applySiteFontScale(val) {
        val = parseInt(val, 10);
        if (isNaN(val)) val = 100;
        val = Math.max(50, Math.min(150, val));

        // Dynamic base font size
        document.documentElement.style.fontSize = (val / 100 * 16) + 'px';

        const slider = document.getElementById('font-scale-slider');
        if (slider && parseInt(slider.value, 10) !== val) {
            slider.value = val;
        }

        const valueDisplay = document.getElementById('font-scale-value');
        if (valueDisplay) {
            valueDisplay.textContent = val + '%';
        }

        const badge = document.getElementById('currentFontBadge');
        if (badge) {
            badge.textContent = val + '%';
        }
    }

    // --------------------------------------------------------------------------
    // 7. HEADER USER NAME DISPLAY
    // --------------------------------------------------------------------------
    function updateHeaderUserName(nameOverride) {
        const els = document.querySelectorAll('.header-user-name, #header-user-name');
        if (!els || els.length === 0) return;
        const settings = getSiteSettings();
        const defaultLoginText = (settings.lang === 'en') ? 'LOGIN' : 'ВХІД';
        let displayName = defaultLoginText;
        if (nameOverride && typeof nameOverride === 'string') {
            displayName = nameOverride.trim().toUpperCase() || defaultLoginText;
        } else {
            try {
                const activeSaved = localStorage.getItem('muvio_active_user');
                if (activeSaved) {
                    const active = JSON.parse(activeSaved);
                    const login = (active.login || '').trim();
                    if (login) displayName = login.toUpperCase();
                } else {
                    const saved = localStorage.getItem('muvio_user');
                    if (saved) {
                        const u = JSON.parse(saved);
                        const n = (u.login || u.name || u.first_name || u.username || '').trim();
                        if (n) displayName = n.toUpperCase();
                    }
                }
            } catch (e) {}
        }
        els.forEach(el => {
            el.textContent = displayName;
        });
    }

    // --------------------------------------------------------------------------
    // 8. MODAL TOGGLE & CLOSE
    // --------------------------------------------------------------------------
    function toggleSettingsModal(e) {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        const drop = document.getElementById('settingsDropdown');
        if (drop) {
            drop.classList.toggle('hidden');
        }
    }

    function closeSettingsModal() {
        const drop = document.getElementById('settingsDropdown');
        if (drop) {
            drop.classList.add('hidden');
        }
    }

    // --------------------------------------------------------------------------
    // 9. INITIALIZE SETTINGS UI & BIND EVENTS
    // --------------------------------------------------------------------------
    function initSettingsUI() {
        const settings = getSiteSettings();
        applySiteTheme(settings.theme);
        applySiteLanguage(settings.lang);
        applySiteFontScale(settings.fontScale);

        // Bind slider input event
        const slider = document.getElementById('font-scale-slider');
        if (slider) {
            slider.value = settings.fontScale;
            slider.oninput = function () {
                setSiteFontScale(this.value);
            };
        }

        // Bind theme buttons
        const btnLight = document.getElementById('themeBtnLight');
        if (btnLight) btnLight.onclick = () => setSiteTheme('light');

        const btnDark = document.getElementById('themeBtnDark');
        if (btnDark) btnDark.onclick = () => setSiteTheme('dark');

        // Bind language buttons
        const btnUa = document.getElementById('langBtnUa');
        if (btnUa) btnUa.onclick = () => setSiteLanguage('ua');

        const btnEn = document.getElementById('langBtnEn');
        if (btnEn) btnEn.onclick = () => setSiteLanguage('en');

        // Bind settings toggle button
        const gearBtn = document.getElementById('settingsBtn');
        if (gearBtn) gearBtn.onclick = toggleSettingsModal;

        // Mobile drawer toggle if exists
        const mobileBtn = document.getElementById('mobileMenuBtn');
        const mobileDrawer = document.getElementById('mobileMenu');
        if (mobileBtn && mobileDrawer) {
            mobileBtn.onclick = () => {
                mobileDrawer.classList.toggle('hidden');
            };
        }
    }

    // Click outside closes modal
    document.addEventListener('click', (e) => {
        const drop = document.getElementById('settingsDropdown');
        const btn = document.getElementById('settingsBtn');
        if (drop && !drop.classList.contains('hidden')) {
            if (!drop.contains(e.target) && (!btn || !btn.contains(e.target))) {
                closeSettingsModal();
            }
        }
    });

    // Escape closes modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeSettingsModal();
    });

    // --------------------------------------------------------------------------
    // 10. CROSS-TAB SYNCHRONIZATION
    // --------------------------------------------------------------------------
    window.addEventListener('storage', (e) => {
        if (e.key === 'muvio_site_settings') {
            const settings = getSiteSettings();
            applySiteTheme(settings.theme);
            applySiteLanguage(settings.lang);
            applySiteFontScale(settings.fontScale);
        } else if (e.key === 'muvio_active_user' || e.key === 'muvio_user') {
            updateHeaderUserName();
        }
    });

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initSettingsUI();
            updateHeaderUserName();
        });
    } else {
        initSettingsUI();
        updateHeaderUserName();
    }

    // --------------------------------------------------------------------------
    // 11. GLOBAL API EXPORTS
    // --------------------------------------------------------------------------
    window.setSiteTheme = setSiteTheme;
    window.applySiteTheme = applySiteTheme;
    window.setSiteLanguage = setSiteLanguage;
    window.applySiteLanguage = applySiteLanguage;
    window.setSiteFontScale = setSiteFontScale;
    window.applySiteFontScale = applySiteFontScale;
    window.toggleSettingsModal = toggleSettingsModal;
    window.closeSettingsModal = closeSettingsModal;
    window.getSiteSettings = getSiteSettings;
    window.saveSiteSettings = saveSiteSettings;
    window.updateHeaderUserName = updateHeaderUserName;
    window.initSettingsUI = initSettingsUI;

})();
