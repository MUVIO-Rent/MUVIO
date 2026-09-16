/**
 * ==========================================================================
 * MUVIO — GLOBAL THEME, LANGUAGE & ZOOM SYNCHRONIZATION MODULE
 * (theme-settings.js)
 * Architecture: Single Source of Truth for Strict Blackout, I18N, CSS Zoom & Cross-Tab Sync
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
            settings_font_label: "МАСШТАБ (ZOOM)",

            // Index landing elements
            hero_tag: "MUVIO — ТВОЄ ELECTRO CITY",
            hero_title: "ОРЕНДА КУР'ЄРСЬКОГО ТА ТУРИСТИЧНОГО<br>ЕЛЕКТРОТРАНСПОРТУ В ОДЕСІ",
            hero_subtitle: "Каталог скутерів та велосипедів у зборі з АКБ. Офіційний договір, повне планове сервісне обслуговування та фіксований щотижневий платіж.",
            hero_btn_choose: "ОБРАТИ СКУТЕР",
            hero_btn_calc: "КАЛЬКУЛЯТОР ОРЕНДИ",
            hero_badge_rent: "ОРЕНДА",
            hero_from_800: "ВІД 800 ГРН",
            hero_from_1800: "ВІД 1 800 ГРН",
            hero_from_6000: "ВІД 6 000 ГРН",
            hero_per_day: "/ ДОБА",
            hero_per_week: "/ ТИЖДЕНЬ",
            hero_per_month: "/ МІСЯЦЬ",
            hero_feat_range: "ДО 160 КМ НА ОДНОМУ ЗАРЯДІ",
            hero_feat_range_sub: "З можливістю взяти другий знімний АКБ",
            hero_feat_address: "ОДЕСА, ВУЛ. ПРИМОРСЬКА, 22",
            hero_feat_address_sub: "ПН — НД: з 11:00 до 22:00",
            hero_feat_bot: "ОНЛАЙН БОТ У TELEGRAM 24/7",
            hero_feat_bot_sub: "Особистий кабінет з автоматичним розрахунком та оплатою днів оренди",
            cat_tag: "ОФІЦІЙНИЙ АВТОПАРК MUVIO",
            cat_title: "КАТАЛОГ ТЕХНІКИ В НАЯВНОСТІ",
            cat_desc: "Всі моделі укомплектовані знімним АКБ та зарядним пристроєм. Реальні тарифи оренди.",
            filter_all: "ВСІ МОДЕЛІ",
            filter_scooters: "🛵 СКУТЕРИ",
            filter_bikes: "🚲 ВЕЛОСИПЕДИ",

            // Calculator
            calc_section_tag: "ТАРИФИ ТА РОЗРАХУНОК",
            calc_section_title: "КАЛЬКУЛЯТОР ОРЕНДИ",
            calc_section_desc: "Оберіть модель транспорту, термін оренди та додаткові опції. Що довший термін оренди — то нижча вартість за добу.",
            calc_step1_label: "1. ОБЕРІТЬ МОДЕЛЬ ТРАНСПОРТУ:",
            calc_step2_label: "2. ОБЕРІТЬ ТЕРМІН ОРЕНДИ:",
            calc_step3_label: "3. ДОДАТКОВІ ОПЦІЇ ТА ОБЛАДНАННЯ:",
            calc_summary_heading: "ПІДСУМОК ОРЕНДИ",
            calc_total_label: "РАЗОМ ДО ОПЛАТИ:",
            calc_deposit_label: "ЗАСТАВА ЗА ТРАНСПОРТ:",
            calc_deposit_note: "Або <b>без застави</b> за умови верифікації через сервіс Дія",
            calc_send_telegram: "НАДІСЛАТИ ЗАЯВКУ В TELEGRAM",
            calc_base_rate_prefix: "Базовий тариф моделі:",
            calc_slider_exact_label: "Або вкажіть точну кількість діб:",
            calc_bot_note: "Сформована заявка надсилається до офіційного бота @muviobot",

            // Rental Formats
            section_formats_tag: "УМОВИ СПІВПРАЦІ",
            section_formats_title: "ФОРМАТИ ОРЕНДИ ТА ВИКУПУ",
            section_formats_desc: "Офіційне оформлення, прозорі договірні зобов'язання та чіткі умови без зайвих нарахувань.",
            card_classic_rent_title: "КЛАСИЧНА ОРЕНДА",
            card_buyout_title: "ПРОГРАМА ВИКУПУ",

            // Service & Hub
            section_maintenance_title: "ТЕХНІЧНЕ ОБСЛУГОВУВАННЯ ТА ВИДАЧА",
            feature_tires_title: "ШИНОМОНТАЖ",
            feature_brakes_title: "ГАЛЬМІВНІ СИСТЕМИ",
            feature_replacement_title: "ПІДМІННИЙ ТРАНСПОРТ",
            section_location_title: "ОФІЦІЙНА ЛОКАЦІЯ ТА ГРАФІК",

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
            settings_font_label: "ZOOM SCALE",

            // Index landing elements
            hero_tag: "MUVIO — YOUR ELECTRO CITY",
            hero_title: "RENTAL OF COURIER & TOURIST<br>ELECTRIC VEHICLES IN ODESA",
            hero_subtitle: "Catalog of scooters and e-bikes complete with battery. Official agreement, full scheduled maintenance and fixed weekly payment.",
            hero_btn_choose: "CHOOSE SCOOTER",
            hero_btn_calc: "RENTAL CALCULATOR",
            hero_badge_rent: "RENTAL",
            hero_from_800: "FROM 800 UAH",
            hero_from_1800: "FROM 1 800 UAH",
            hero_from_6000: "FROM 6 000 UAH",
            hero_per_day: "/ DAY",
            hero_per_week: "/ WEEK",
            hero_per_month: "/ MONTH",
            hero_feat_range: "UP TO 160 KM PER CHARGE",
            hero_feat_range_sub: "Option to take a second removable battery",
            hero_feat_address: "ODESA, 22 PRYMORSKA STR.",
            hero_feat_address_sub: "MON — SUN: 11:00 to 22:00",
            hero_feat_bot: "ONLINE TELEGRAM BOT 24/7",
            hero_feat_bot_sub: "Personal account with automated calculation & payment of rental days",
            cat_tag: "OFFICIAL MUVIO FLEET",
            cat_title: "IN-STOCK FLEET CATALOG",
            cat_desc: "All models equipped with removable battery and fast charger. Live verified rental rates.",
            filter_all: "ALL MODELS",
            filter_scooters: "🛵 SCOOTERS",
            filter_bikes: "🚲 E-BIKES",

            // Calculator
            calc_section_tag: "RATES & CALCULATION",
            calc_section_title: "RENTAL CALCULATOR",
            calc_section_desc: "Select a vehicle model, rental duration and additional options. Longer rental periods mean lower daily rates.",
            calc_step1_label: "1. SELECT VEHICLE MODEL:",
            calc_step2_label: "2. SELECT RENTAL PERIOD:",
            calc_step3_label: "3. ADDITIONAL OPTIONS & GEAR:",
            calc_summary_heading: "RENTAL SUMMARY",
            calc_total_label: "TOTAL TO PAY:",
            calc_deposit_label: "SECURITY DEPOSIT:",
            calc_deposit_note: "Or <b>without deposit</b> subject to Diia verification",
            calc_send_telegram: "SEND APPLICATION TO TELEGRAM",
            calc_base_rate_prefix: "Base model rate:",
            calc_slider_exact_label: "Or specify exact number of days:",
            calc_bot_note: "Application will be sent directly to @muviobot",

            // Rental Formats
            section_formats_tag: "TERMS OF SERVICE",
            section_formats_title: "RENTAL & BUYOUT OPTIONS",
            section_formats_desc: "Official contract, transparent commitments and clear terms without hidden fees.",
            card_classic_rent_title: "CLASSIC RENTAL",
            card_buyout_title: "BUYOUT PROGRAM",

            // Service & Hub
            section_maintenance_title: "MAINTENANCE & PICKUP HUB",
            feature_tires_title: "TIRE SERVICE",
            feature_brakes_title: "BRAKE SYSTEMS",
            feature_replacement_title: "REPLACEMENT VEHICLE",
            section_location_title: "OFFICIAL LOCATION & HOURS",

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

    // Calculator i18n pills & addons dictionary
    window.MUVIO_CALC_I18N = {
        ua: {
            pills: {
                1: { label: "1 ДЕНЬ" },
                2: { label: "2 ДНІ" },
                3: { label: "3 ДНІ" },
                7: { label: "7 ДНІВ (ТИЖДЕНЬ)" },
                28: { label: "28 ДНІВ (МІСЯЦЬ)" },
                30: { label: "28 ДНІВ (МІСЯЦЬ)" }
            },
            addons: {
                helmet: { title: "ШОЛОМ + ТРИМАЧ ДЛЯ ТЕЛЕФОНУ", desc: "+200 грн", badge: "+200 грн", price: 200 },
                battery40: { title: "ДРУГИЙ АКБ 40Ah (ЗНІМНИЙ)", desc: "+800 грн", badge: "+800 грн", price: 800 },
                battery60: { title: "ДРУГИЙ АКБ 60Ah (ЗНІМНИЙ)", desc: "+1 000 грн", badge: "+1 000 грн", price: 1000 }
            },
            tg_btn: "НАДІСЛАТИ ЗАЯВКУ В TELEGRAM ({price} ГРН)",
            tg_btn_base: "НАДІСЛАТИ ЗАЯВКУ В TELEGRAM",
            rate_unit: "грн/доба",
            rate_day_pill: "грн/доба",
            days_badge_1: "1 день (доба)",
            days_badge_2: "2 дні",
            days_badge_3: "3 дні",
            days_badge_7: "7 днів (тиждень)",
            days_badge_28: "28 днів (місяць)",
            days_badge_30: "28 днів (місяць)",
            days_unit: "дн.",
            options_count: "обрано"
        },
        en: {
            pills: {
                1: { label: "1 DAY" },
                2: { label: "2 DAYS" },
                3: { label: "3 DAYS" },
                7: { label: "7 DAYS (WEEK)" },
                28: { label: "28 DAYS (MONTH)" },
                30: { label: "28 DAYS (MONTH)" }
            },
            addons: {
                helmet: { title: "HELMET + PHONE MOUNT", desc: "+200 UAH", badge: "+200 UAH", price: 200 },
                battery40: { title: "SECOND BATTERY 40Ah (REMOVABLE)", desc: "+800 UAH", badge: "+800 UAH", price: 800 },
                battery60: { title: "SECOND BATTERY 60Ah (REMOVABLE)", desc: "+1,000 UAH", badge: "+1,000 UAH", price: 1000 }
            },
            tg_btn: "SEND APPLICATION TO TELEGRAM ({price} UAH)",
            tg_btn_base: "SEND APPLICATION TO TELEGRAM",
            rate_unit: "UAH/day",
            rate_day_pill: "UAH/day",
            days_badge_1: "1 day (day)",
            days_badge_2: "2 days",
            days_badge_3: "3 days",
            days_badge_7: "7 days (week)",
            days_badge_28: "28 days (month)",
            days_badge_30: "28 days (month)",
            days_unit: "days",
            options_count: "selected"
        }
    };

    const DEFAULT_SETTINGS = {
        theme: 'light',
        lang: 'ua',
        fontScale: 100,
        zoom: 100
    };

    // --------------------------------------------------------------------------
    // 2. SETTINGS GET / SAVE HELPERS
    // --------------------------------------------------------------------------
    function getSiteSettings() {
        try {
            const raw = localStorage.getItem('muvio_site_settings');
            let lang = localStorage.getItem('muvio_lang');
            if (raw) {
                const parsed = JSON.parse(raw);
                let z = parsed.zoom !== undefined ? parsed.zoom : parsed.fontScale;
                z = parseInt(z, 10);
                if (isNaN(z) || z < 80 || z > 120) z = 100;
                parsed.zoom = z;
                parsed.fontScale = z;
                if (lang) parsed.lang = (lang === 'en') ? 'en' : 'ua';
                return Object.assign({}, DEFAULT_SETTINGS, parsed);
            }
            if (lang) {
                return Object.assign({}, DEFAULT_SETTINGS, { lang: lang === 'en' ? 'en' : 'ua' });
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
    // 3. SYNCHRONOUS ANTI-FLICKER & ZOOM & LANG INITIALIZATION
    // --------------------------------------------------------------------------
    try {
        // Instant synchronous lang setup on documentElement
        let initialLang = 'uk';
        try {
            const rawLang = localStorage.getItem('muvio_lang');
            if (rawLang === 'en') {
                initialLang = 'en';
            } else if (!rawLang) {
                const rawSettings = localStorage.getItem('muvio_site_settings');
                if (rawSettings) {
                    const parsed = JSON.parse(rawSettings);
                    if (parsed && (parsed.lang === 'en' || parsed.lang === 'eng')) initialLang = 'en';
                }
            }
        } catch (err) {}
        document.documentElement.setAttribute('lang', initialLang);

        const initS = getSiteSettings();
        if (initS.theme === 'dark') {
            document.documentElement.classList.add('theme-dark', 'dark');
            document.documentElement.setAttribute('data-theme', 'dark');
            if (document.body) {
                document.body.classList.add('theme-dark', 'dark');
                document.body.setAttribute('data-theme', 'dark');
            }
        } else {
            document.documentElement.classList.remove('theme-dark', 'dark');
            document.documentElement.setAttribute('data-theme', 'light');
            if (document.body) {
                document.body.classList.remove('theme-dark', 'dark');
                document.body.setAttribute('data-theme', 'light');
            }
        }
        const initialZoom = Math.max(80, Math.min(120, parseInt(initS.zoom || initS.fontScale, 10) || 100));
        if (document.body) {
            document.body.style.zoom = (initialZoom / 100);
        }
        document.addEventListener('DOMContentLoaded', () => {
            if (document.body) {
                document.body.style.zoom = (initialZoom / 100);
                if (getSiteSettings().theme === 'dark') {
                    document.body.classList.add('theme-dark', 'dark');
                    document.body.setAttribute('data-theme', 'dark');
                }
            }
            const curTheme = getSiteSettings().theme;
            const toggleButtons = document.querySelectorAll('#theme-toggle, [data-theme-toggle]');
            toggleButtons.forEach(btn => {
                const moon = btn.querySelector('.moon-icon');
                const sun = btn.querySelector('.sun-icon');
                if (moon && sun) {
                    if (curTheme === 'dark') {
                        moon.style.setProperty('display', 'none', 'important');
                        sun.style.setProperty('display', 'block', 'important');
                    } else {
                        moon.style.setProperty('display', 'block', 'important');
                        sun.style.setProperty('display', 'none', 'important');
                    }
                }
            });
        });
        document.documentElement.style.fontSize = '';
    } catch (e) {}

    // --------------------------------------------------------------------------
    // 4. THEME CONTROLLER
    // --------------------------------------------------------------------------
    function setSiteTheme(theme) {
        const settings = getSiteSettings();
        if (settings.theme === theme) return;
        settings.theme = theme;
        saveSiteSettings(settings);
        applySiteTheme(theme);
    }

    function applySiteTheme(theme) {
        const btnLight = document.getElementById('themeBtnLight');
        const btnDark = document.getElementById('themeBtnDark');
        const badge = document.getElementById('currentThemeBadge');
        const metaThemeColor = document.querySelector('meta[name="theme-color"]');

        if (theme === 'dark') {
            document.documentElement.classList.add('theme-dark', 'dark');
            document.documentElement.setAttribute('data-theme', 'dark');
            if (document.body) {
                document.body.classList.add('theme-dark', 'dark');
                document.body.setAttribute('data-theme', 'dark');
            }
            if (metaThemeColor) metaThemeColor.setAttribute('content', '#0F1411');
            if (badge) badge.textContent = 'DARK';
            if (btnDark) {
                btnDark.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-[#1D5D3B] text-white';
            }
            if (btnLight) {
                btnLight.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-slate-100 text-slate-700 hover:bg-slate-200';
            }
        } else {
            document.documentElement.classList.remove('theme-dark', 'dark');
            document.documentElement.setAttribute('data-theme', 'light');
            if (document.body) {
                document.body.classList.remove('theme-dark', 'dark');
                document.body.setAttribute('data-theme', 'light');
            }
            if (metaThemeColor) metaThemeColor.setAttribute('content', '#FFFFFF');
            if (badge) badge.textContent = 'LIGHT';
            if (btnLight) {
                btnLight.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-[#1D5D3B] text-white';
            }
            if (btnDark) {
                btnDark.className = 'py-2 px-3 text-xs font-brand font-bold uppercase tracking-wider chamfer-badge flex items-center justify-center gap-1.5 transition-all bg-slate-100 text-slate-700 hover:bg-slate-200';
            }
        }

        // Synchronize all theme-toggle button icons (Moon for light theme, Sun for dark theme)
        const toggleButtons = document.querySelectorAll('#theme-toggle, [data-theme-toggle]');
        toggleButtons.forEach(btn => {
            const moon = btn.querySelector('.moon-icon');
            const sun = btn.querySelector('.sun-icon');
            if (moon && sun) {
                if (theme === 'dark') {
                    moon.style.setProperty('display', 'none', 'important');
                    sun.style.setProperty('display', 'block', 'important');
                } else {
                    moon.style.setProperty('display', 'block', 'important');
                    sun.style.setProperty('display', 'none', 'important');
                }
            }
        });
    }

    // --------------------------------------------------------------------------
    // 5. LANGUAGE CONTROLLER (CSS-Based Dual .lang-ua / .lang-en & Placeholders)
    // --------------------------------------------------------------------------
    function updateFormPlaceholders(lang) {
        const isEn = (lang === 'en');
        document.querySelectorAll('[data-placeholder-ua], [data-placeholder-en]').forEach(el => {
            const ph = isEn ? el.getAttribute('data-placeholder-en') : el.getAttribute('data-placeholder-ua');
            if (ph !== null) {
                el.setAttribute('placeholder', ph);
            }
        });
    }

    function setSiteLanguage(lang) {
        const normalized = (lang === 'en') ? 'en' : 'uk';
        document.documentElement.setAttribute('lang', normalized);
        try {
            localStorage.setItem('muvio_lang', normalized);
            const settings = getSiteSettings();
            settings.lang = normalized === 'en' ? 'en' : 'ua';
            saveSiteSettings(settings);
        } catch (e) {}
        applySiteLanguage(normalized);
    }

    function applySiteLanguage(lang) {
        const normalized = (lang === 'en') ? 'en' : 'uk';
        document.documentElement.setAttribute('lang', normalized);

        const btnUa = document.getElementById('langBtnUa');
        const btnEn = document.getElementById('langBtnEn');
        const badge = document.getElementById('currentLangBadge');

        if (normalized === 'en') {
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

        // Update form inputs with data-placeholder-ua and data-placeholder-en
        updateFormPlaceholders(normalized);

        // Fallback for any elements still using data-i18n
        const dict = MUVIO_I18N[normalized === 'en' ? 'en' : 'ua'] || MUVIO_I18N.ua;
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key && dict[key]) {
                if (dict[key].includes('<br>') || dict[key].includes('<span') || dict[key].includes('<b>')) {
                    el.innerHTML = dict[key];
                } else {
                    el.textContent = dict[key];
                }
            }
        });

        // Trigger dynamic page re-renders
        if (typeof window.renderCatalog === 'function' && typeof window.currentCatalogFilter !== 'undefined') {
            try { window.renderCatalog(window.currentCatalogFilter); } catch (err) {}
        }
        if (typeof window.renderCalculatorI18n === 'function') {
            try { window.renderCalculatorI18n(); } catch (err) {}
        }
        if (typeof window.updateCalcModelOptions === 'function') {
            try { window.updateCalcModelOptions(); } catch (err) {}
        }
        if (typeof window.updateCalc === 'function') {
            try { window.updateCalc(); } catch (err) {}
        }
        if (typeof window.renderCabinetI18n === 'function') {
            try { window.renderCabinetI18n(); } catch (err) {}
        }

        updateHeaderUserName();
        window.dispatchEvent(new CustomEvent('muvio:langchange', { detail: { lang: normalized } }));
    }

    // --------------------------------------------------------------------------
    // 6. ZOOM / SCALE CONTROLLER (CSS Zoom 80% - 120%, Safe & Stable)
    // --------------------------------------------------------------------------
    function applySiteZoom(val) {
        val = parseInt(val, 10);
        if (isNaN(val)) val = 100;
        val = Math.max(80, Math.min(120, val));

        // Smooth CSS zoom on body without reflowing font-size
        if (document.body) {
            document.body.style.zoom = (val / 100);
        }
        document.documentElement.style.fontSize = '';

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

    function saveSiteZoom(val) {
        val = parseInt(val, 10);
        if (isNaN(val)) val = 100;
        val = Math.max(80, Math.min(120, val));

        const settings = getSiteSettings();
        if (settings.zoom !== val) {
            settings.zoom = val;
            settings.fontScale = val;
            saveSiteSettings(settings);
        }
    }

    function setSiteFontScale(val) {
        applySiteZoom(val);
        saveSiteZoom(val);
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
        applySiteZoom(settings.zoom || settings.fontScale || 100);

        // Bind slider with safe min=80, max=120, step=5
        const slider = document.getElementById('font-scale-slider');
        if (slider) {
            slider.min = "80";
            slider.max = "120";
            slider.step = "5";
            slider.value = settings.zoom || settings.fontScale || 100;
            // On dragging (input): live zoom only, zero storage writes
            slider.oninput = function () {
                applySiteZoom(this.value);
            };
            // On release (change): persist to storage
            slider.onchange = function () {
                saveSiteZoom(this.value);
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

        // Bind settings toggle button (#options-btn or #settingsBtn)
        const gearBtn = document.getElementById('options-btn') || document.getElementById('settingsBtn');
        if (gearBtn) gearBtn.onclick = toggleSettingsModal;

        // Mobile drawer toggle if exists
        const burgerBtn = document.getElementById('burger-btn') || document.querySelector('[data-burger]') || document.getElementById('mobileMenuBtn');
        const mobileMenu = document.getElementById('mobile-menu') || document.querySelector('[data-mobile-menu]') || document.getElementById('mobileMenu');
        if (burgerBtn && mobileMenu) {
            burgerBtn.onclick = (e) => {
                e.stopPropagation();
                mobileMenu.classList.toggle('hidden');
            };
            mobileMenu.querySelectorAll('a, button, .mobile-nav-link').forEach(link => {
                link.addEventListener('click', () => {
                    mobileMenu.classList.add('hidden');
                });
            });
            const closeBtn = document.getElementById('mobile-menu-close');
            if (closeBtn) {
                closeBtn.onclick = (e) => {
                    e.stopPropagation();
                    mobileMenu.classList.add('hidden');
                };
            }
            document.addEventListener('click', (e) => {
                if (!mobileMenu.classList.contains('hidden')) {
                    if (!mobileMenu.contains(e.target) && !burgerBtn.contains(e.target)) {
                        mobileMenu.classList.add('hidden');
                    }
                }
            });
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && !mobileMenu.classList.contains('hidden')) {
                    mobileMenu.classList.add('hidden');
                }
            });
        }
    }

    // Click outside closes modal
    document.addEventListener('click', (e) => {
        const drop = document.getElementById('settingsDropdown');
        const btn = document.getElementById('options-btn') || document.getElementById('settingsBtn');
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
    // 10. HIGH-PERFORMANCE 120Hz PROMOTION SCROLL ENGINE (Repaint/Reflow Suppressor)
    // --------------------------------------------------------------------------
    let scrollTimeout;
    window.addEventListener('scroll', () => {
        if (!document.body.classList.contains('is-scrolling')) {
            document.body.classList.add('is-scrolling');
        }
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
            document.body.classList.remove('is-scrolling');
        }, 120);
    }, { passive: true });

    // --------------------------------------------------------------------------
    // 11. CROSS-TAB SYNCHRONIZATION
    // --------------------------------------------------------------------------
    window.addEventListener('storage', (e) => {
        if (e.key === 'muvio_site_settings' || e.key === 'muvio_lang') {
            const settings = getSiteSettings();
            applySiteTheme(settings.theme);
            applySiteLanguage(settings.lang);
            applySiteZoom(settings.zoom || settings.fontScale || 100);
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
    // 12. GLOBAL PRELOADER CONTROLLER (Fade out opacity-0 -> hidden after 200-300ms)
    // --------------------------------------------------------------------------
    function hidePagePreloader() {
        const preloader = document.getElementById('page-preloader');
        if (!preloader || preloader.dataset.hidden === 'true') return;
        preloader.dataset.hidden = 'true';
        preloader.style.transition = 'opacity 0.25s ease';
        preloader.style.opacity = '0';
        setTimeout(() => {
            preloader.classList.add('hidden');
            preloader.style.display = 'none';
        }, 250);
    }

    if (document.readyState === 'complete') {
        setTimeout(hidePagePreloader, 150);
    } else {
        window.addEventListener('load', () => setTimeout(hidePagePreloader, 150));
        document.addEventListener('DOMContentLoaded', () => setTimeout(hidePagePreloader, 350));
    }
    // Fallback timer ensures preloader never hangs
    setTimeout(hidePagePreloader, 2000);

    // --------------------------------------------------------------------------
    // 13. GLOBAL API EXPORTS
    // --------------------------------------------------------------------------
    window.setSiteTheme = setSiteTheme;
    window.applySiteTheme = applySiteTheme;
    window.setSiteLanguage = setSiteLanguage;
    window.applySiteLanguage = applySiteLanguage;
    window.setSiteFontScale = setSiteFontScale;
    window.applySiteFontScale = applySiteZoom;
    window.applySiteZoom = applySiteZoom;
    window.saveSiteZoom = saveSiteZoom;
    window.toggleSettingsModal = toggleSettingsModal;
    window.closeSettingsModal = closeSettingsModal;
    window.getSiteSettings = getSiteSettings;
    window.saveSiteSettings = saveSiteSettings;
    window.updateHeaderUserName = updateHeaderUserName;
    window.initSettingsUI = initSettingsUI;
    window.hidePagePreloader = hidePagePreloader;
    window.hidePreloader = hidePagePreloader;

})();
