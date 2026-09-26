"""
Wallet Accumulation Analyzer / محلل محافظ التجميع
====================================================
Bilingual (Arabic/English) monitoring system: single-token analysis, watchlist,
bulk analysis with alerts, and local API-key storage — 100% free data sources.

EVM networks (Ethereum, BSC, Polygon, Arbitrum, Base, Avalanche):
    Dexscreener + unified Etherscan API V2 (one key for all EVM chains)
Solana:
    Dexscreener + Helius API

Run with:
    streamlit run app.py
"""

import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

# ----------------------------------------------------------------------
# General config
# ----------------------------------------------------------------------
st.set_page_config(page_title="Wallet Accumulation Analyzer", layout="wide")

# ⚠️ عدّل هذا القسم يدوياً بعنوان محفظتك — لا توجد واجهة لتعديله من داخل التطبيق.
# ⚠️ Edit this section manually with your own wallet address — there is no in-app UI to change it.
DONATION_WALLET_ADDRESS = "YOUR_WALLET_ADDRESS_HERE"
DONATION_LABEL = "USDT (BEP20)"  # e.g. "USDT (BEP20)", "ETH (ERC20)", "SOL"...

# Etherscan stopped all old separate-domain API endpoints on 2025-08-15.
# All EVM chains now go through one unified V2 endpoint with a chainid param.
ETHERSCAN_V2_API = "https://api.etherscan.io/v2/api"

NETWORKS = {
    "Ethereum": {"type": "evm", "dexscreener_chain": "ethereum", "geckoterminal_network": "eth", "chain_id": 1},
    "BNB Smart Chain": {"type": "evm", "dexscreener_chain": "bsc", "geckoterminal_network": "bsc", "chain_id": 56},
    "Polygon": {"type": "evm", "dexscreener_chain": "polygon", "geckoterminal_network": "polygon_pos", "chain_id": 137},
    "Arbitrum": {"type": "evm", "dexscreener_chain": "arbitrum", "geckoterminal_network": "arbitrum", "chain_id": 42161},
    "Base": {"type": "evm", "dexscreener_chain": "base", "geckoterminal_network": "base", "chain_id": 8453},
    "Avalanche": {"type": "evm", "dexscreener_chain": "avalanche", "geckoterminal_network": "avax", "chain_id": 43114},
    "Solana": {"type": "solana", "dexscreener_chain": "solana", "geckoterminal_network": "solana", "chain_id": None},
}

SCORE_ALERT_THRESHOLD = 70


# ----------------------------------------------------------------------
# i18n — translation dictionary + helper
# ----------------------------------------------------------------------
TXT = {
    "app_title": {"ar": "🔍 محلل محافظ التجميع", "en": "🔍 Wallet Accumulation Analyzer"},
    "app_caption": {
        "ar": "نظام مراقبة متكامل: تحليل فردي، قائمة مراقبة، تحليل جماعي، وتنبيهات — مجاني بالكامل",
        "en": "A complete monitoring system: single analysis, watchlist, bulk analysis, and alerts — 100% free",
    },
    "donation_line": {
        "ar": "☕ إذا أعجبتك الأداة، يمكنك دعم المطوّر عبر المحفظة التالية:",
        "en": "☕ If you find this tool useful, you can support the developer via the wallet below:",
    },
    "tab_single": {"ar": "🔍 تحليل عملة واحدة", "en": "🔍 Single Token Analysis"},
    "tab_watchlist": {"ar": "📋 قائمة المراقبة", "en": "📋 Watchlist"},
    "tab_bulk": {"ar": "⚡ تحليل جماعي", "en": "⚡ Bulk Analysis"},
    "tab_settings": {"ar": "⚙️ الإعدادات", "en": "⚙️ Settings"},
    "tab_docs": {"ar": "📄 التوثيق", "en": "📄 Docs"},

    # Settings tab
    "settings_keys_header": {"ar": "🔑 مفاتيح API — تُحفظ محلياً وتُستخدم تلقائياً في كل مرة",
                              "en": "🔑 API Keys — saved locally and used automatically every time"},
    "workspace_header": {"ar": "🆔 معرّف مساحة العمل (Workspace)", "en": "🆔 Workspace ID"},
    "workspace_caption": {
        "ar": "كل مستخدم لديه مساحة عمل معزولة تماماً — لا يوجد أي تداخل بين المستخدمين. يمكنك مشاركة هذا المعرّف مع أي شخص آخر لتحميل بياناته.",
        "en": "Every user has a fully isolated workspace — zero overlap between users. Share this ID with someone else to load their data.",
    },
    "workspace_warning": {
        "ar": "⚠️ **لا تشارك معرّف مساحة عملك مع أي شخص تثق به** — من خلاله يمكن لآخرين الاطلاع على مفاتيح API وقائمة المراقبة الخاصة بك.",
        "en": "⚠️ **Do not share your workspace ID with anyone you trust** — it gives access to your API keys and watchlist.",
    },
    "workspace_switch_expander": {"ar": "🔄 تبديل مساحة العمل", "en": "🔄 Switch Workspace"},
    "workspace_switch_label": {"ar": "معرّف مساحة العمل الجديدة", "en": "New workspace ID"},
    "workspace_switch_btn": {"ar": "🔄 تبديل", "en": "🔄 Switch"},
    "workspace_switched_msg": {"ar": "✅ تم التبديل! يتم الآن تحميل بيانات مساحة العمل الجديدة.",
                              "en": "✅ Switched! Now loading the new workspace's data."},
    "settings_keys_caption": {
        "ar": "لن تحتاج لإدخالها مرة أخرى بعد الحفظ. مفتاح Etherscan الواحد يعمل على كل شبكات EVM.",
        "en": "You won't need to re-enter these after saving. One Etherscan key works for all EVM chains.",
    },
    "etherscan_key_label": {"ar": "Etherscan API Key (لكل شبكات EVM)", "en": "Etherscan API Key (all EVM chains)"},
    "helius_key_label": {"ar": "Helius API Key (لشبكة Solana)", "en": "Helius API Key (Solana)"},
    "save_keys_btn": {"ar": "💾 حفظ المفاتيح", "en": "💾 Save Keys"},
    "keys_saved_msg": {"ar": "✅ تم الحفظ! المفاتيح ستُستخدم تلقائياً في كل تحليل قادم.",
                        "en": "✅ Saved! These keys will be used automatically in every future analysis."},
    "keys_security_warning": {
        "ar": "⚠️ **تحذير أمني**: تُحفظ المفاتيح في ملف SQLite محلي (`wallet_memory.db`) **بدون تشفير**. "
              "لا تستخدم هذا على جهاز مشترك أو تشارك الملف مع أحد.",
        "en": "⚠️ **Security warning**: keys are stored **unencrypted** in a local SQLite file "
              "(`wallet_memory.db`). Don't use this on a shared machine or share that file with anyone.",
    },

    # Watchlist tab
    "discovery_header": {"ar": "🔎 اكتشاف عملات تلقائياً", "en": "🔎 Auto-Discover Tokens"},
    "discovery_source_label": {"ar": "المصدر", "en": "Source"},
    "src_trending": {"ar": "🔥 الأكثر تداولاً (GeckoTerminal)", "en": "🔥 Trending (GeckoTerminal)"},
    "src_new": {"ar": "🆕 الأحدث إصداراً (GeckoTerminal)", "en": "🆕 New Pools (GeckoTerminal)"},
    "src_binance": {"ar": "🟡 الأكثر ارتفاعاً (Binance)", "en": "🟡 Top Gainers (Binance)"},
    "binance_warning": {
        "ar": "⚠️ **Binance منصة مركزية (CEX)** — لا توجد فيها بيانات محافظ on-chain. يجلب هذا الوضع أعلى "
              "العملات ارتفاعاً على Binance، ثم يحاول مطابقتها بعنوان عقد on-chain فعلي عبر Dexscreener "
              "(تطابق تام للرمز على شبكاتنا المدعومة فقط). **تطابق الاسم لا يضمن أنها نفس المشروع** — "
              "أسماء العملات قابلة للتزوير على البلوكتشين، تحقق من العنوان بنفسك قبل الاعتماد عليه.",
        "en": "⚠️ **Binance is a centralized exchange (CEX)** — it has no on-chain wallet data. This mode "
              "fetches Binance's top 24h gainers, then tries to match each one to a real on-chain contract "
              "via Dexscreener (exact symbol match, our supported chains only). **A name match does not "
              "guarantee it's the same project** — token names can be freely copied on-chain. Always verify "
              "the address yourself before relying on it.",
    },
    "binance_limit_label": {"ar": "عدد أعلى العملات ارتفاعاً للفحص", "en": "How many top gainers to check"},
    "network_label": {"ar": "الشبكة", "en": "Network"},
    "pages_label": {"ar": "عدد الصفحات (~20/صفحة)", "en": "Pages (~20/page)"},
    "min_liquidity_label": {"ar": "الحد الأدنى للسيولة (USD) — لاستبعاد عملات ضعيفة السيولة",
                             "en": "Minimum liquidity (USD) — filters out illiquid tokens"},
    "search_btn": {"ar": "🔍 ابحث عن عملات", "en": "🔍 Search Tokens"},
    "matching_progress": {"ar": "جاري مطابقة الرموز بعناوين on-chain...", "en": "Matching symbols to on-chain addresses..."},
    "no_binance_match": {"ar": "لم يتم العثور على أي تطابق on-chain موثوق ضمن الشبكات المدعومة.",
                          "en": "No reliable on-chain match found within supported networks."},
    "found_n_tokens": {"ar": "تم العثور على **{n}** عملة:", "en": "Found **{n}** token(s):"},
    "col_add": {"ar": "إضافة", "en": "Add"},
    "col_network": {"ar": "الشبكة", "en": "Network"},
    "col_symbol": {"ar": "الرمز", "en": "Symbol"},
    "col_address": {"ar": "العنوان", "en": "Address"},
    "col_change24": {"ar": "تغيّر 24س %", "en": "24h Change %"},
    "col_volume24": {"ar": "فوليوم 24س (USD)", "en": "24h Volume (USD)"},
    "col_liquidity": {"ar": "السيولة (USD)", "en": "Liquidity (USD)"},
    "add_selected_btn": {"ar": "➕ أضف المحدد لقائمة المراقبة", "en": "➕ Add Selected to Watchlist"},
    "add_all_btn": {"ar": "➕➕ أضف كل النتائج", "en": "➕➕ Add All Results"},
    "added_n_tokens": {"ar": "✅ أُضيفت {n} عملة لقائمة المراقبة وحُفظت في قاعدة البيانات.",
                        "en": "✅ Added {n} token(s) to the watchlist and saved to the database."},
    "select_at_least_one": {"ar": "لم تحدد أي عملة (فعّل مربع 'إضافة' بجانبها أولاً).",
                             "en": "No token selected (tick the 'Add' box next to it first)."},
    "manual_add_header": {"ar": "➕ إضافة عملة يدوياً", "en": "➕ Add a Token Manually"},
    "address_input_label": {"ar": "عنوان العقد / Mint Address", "en": "Contract / Mint Address"},
    "label_input_label": {"ar": "ملاحظة / رمز العملة (اختياري)", "en": "Note / symbol (optional)"},
    "add_btn": {"ar": "➕ إضافة للقائمة", "en": "➕ Add to Watchlist"},
    "added_ok": {"ar": "تمت الإضافة!", "en": "Added!"},
    "enter_address_first": {"ar": "أدخل عنوان العملة أولاً.", "en": "Enter a token address first."},
    "current_list_header": {"ar": "📋 القائمة الحالية ({n} عملة)", "en": "📋 Current Watchlist ({n} tokens)"},
    "empty_watchlist": {"ar": "لا توجد عملات في القائمة بعد. أضف عملة من الأعلى.",
                         "en": "No tokens in the watchlist yet. Add one above."},
    "not_scanned_yet": {"ar": "لم يُفحص بعد", "en": "Not scanned yet"},

    # Single analysis tab
    "start_date_label": {"ar": "من تاريخ", "en": "From date"},
    "end_date_label": {"ar": "إلى تاريخ", "en": "To date"},
    "min_buys_label": {"ar": "الحد الأدنى لعدد مرات الشراء", "en": "Minimum buy count"},
    "range_days_label": {"ar": "عدد الأيام لتحليل الـ Range", "en": "Days for Range analysis"},
    "detect_clusters_label": {"ar": "🔗 كشف تكتلات المحافظ (Sybil)", "en": "🔗 Detect wallet clusters (Sybil)"},
    "max_cluster_label": {"ar": "عدد أعلى المحافظ للفحص", "en": "Top wallets to check"},
    "api_key_missing_warning": {
        "ar": "⚠️ لم يتم إدخال مفتاح API لهذه الشبكة بعد — اذهب لتبويب «⚙️ الإعدادات» أولاً.",
        "en": "⚠️ No API key set for this network yet — go to the «⚙️ Settings» tab first.",
    },
    "run_analysis_btn": {"ar": "🚀 ابدأ التحليل", "en": "🚀 Run Analysis"},
    "enter_token_address": {"ar": "الرجاء إدخال عنوان العملة.", "en": "Please enter a token address."},
    "date_order_warning": {"ar": "تاريخ البداية يجب أن يكون قبل تاريخ النهاية.",
                            "en": "The start date must be before the end date."},

    # Market pulse
    "price_change_header": {"ar": "#### ⚡ تغيّر السعر", "en": "#### ⚡ Price Change"},
    "volume_header": {"ar": "#### 💰 حجم التداول (Volume)", "en": "#### 💰 Trading Volume"},
    "volume_trend_header": {"ar": "#### 📊 اتجاه حجم التداول (Volume Trend)", "en": "#### 📊 Volume Trend"},
    "current_hour_volume": {"ar": "الفوليوم الحالي (آخر ساعة)", "en": "Current volume (last hour)"},
    "vs_6h_avg": {"ar": "مقارنة بمتوسط آخر 6 ساعات", "en": "vs. 6h average"},
    "vs_24h_avg": {"ar": "مقارنة بمتوسط آخر 24 ساعة", "en": "vs. 24h average"},
    "volume_rising": {"ar": "**🔼 الفوليوم في ارتفاع**", "en": "**🔼 Volume is rising**"},
    "volume_falling": {"ar": "**🔽 الفوليوم في انخفاض**", "en": "**🔽 Volume is falling**"},
    "momentum_header": {"ar": "#### 🧭 قراءة الزخم (الفوليوم × حركة السعر)", "en": "#### 🧭 Momentum Read (Volume × Price)"},
    "momentum_strong_up": {"ar": "🟢 **تأكيد صعودي قوي** — السعر والفوليوم يرتفعان معاً.",
                            "en": "🟢 **Strong bullish confirmation** — price and volume rising together."},
    "momentum_weak_up": {"ar": "🟡 **صعود ضعيف** — السعر يرتفع لكن الفوليوم ينخفض.",
                          "en": "🟡 **Weak rally** — price is up but volume is falling."},
    "momentum_dump": {"ar": "🔴 **ضغط بيع حقيقي (تصريف)** — السعر ينخفض والفوليوم يرتفع.",
                       "en": "🔴 **Real sell pressure (dump)** — price falling, volume rising."},
    "momentum_fading_down": {"ar": "🟠 **هبوط يفقد قوته** — السعر والفوليوم ينخفضان معاً.",
                              "en": "🟠 **Downtrend losing steam** — price and volume both falling."},
    "momentum_flat": {"ar": "⚪ حركة السعر شبه مستقرة حالياً.", "en": "⚪ Price action is roughly flat right now."},
    "daily_trend_caption": {"ar": "الاتجاه اليومي: {icon} ({pct:+.2f}% خلال 24 ساعة)",
                             "en": "24h trend: {icon} ({pct:+.2f}% over 24h)"},
    "buyers_sellers_header": {"ar": "#### 👥 المشترون والبائعون (آخر 24 ساعة)", "en": "#### 👥 Buyers & Sellers (last 24h)"},
    "buyers_count": {"ar": "عدد المشترين", "en": "Buyers"},
    "sellers_count": {"ar": "عدد البائعين", "en": "Sellers"},
    "buy_txns": {"ar": "صفقات الشراء", "en": "Buy transactions"},
    "sell_txns": {"ar": "صفقات البيع", "en": "Sell transactions"},
    "avg_buy_price": {"ar": "متوسط سعر الشراء لكل مشتري (USD)", "en": "Avg. buy value per buyer (USD)"},
    "avg_sell_price": {"ar": "متوسط سعر البيع لكل بائع (USD)", "en": "Avg. sell value per seller (USD)"},
    "smart_money_caption": {
        "ar": "يُحسب كـ: إجمالي قيمة الشراء/البيع خلال 24 ساعة ÷ عدد المحافظ الفريدة — منطق Smart Money.",
        "en": "Computed as: total 24h buy/sell value ÷ unique wallet count — the same logic as Smart Money trackers.",
    },
    "buy_sell_pressure": {"ar": "⚖️ {buy:.1f}% شراء / {sell:.1f}% بيع", "en": "⚖️ {buy:.1f}% buy / {sell:.1f}% sell"},

    # Range analysis
    "range_header": {"ar": "#### 📏 هل العملة في نطاق (Range) على المدى المتوسط؟ ({days} يوماً)",
                      "en": "#### 📏 Is the token range-bound medium-term? ({days} days)"},
    "no_range_data": {"ar": "لا توجد بيانات تاريخية كافية من GeckoTerminal لهذا الـ Pool لتحليل الـ Range.",
                       "en": "Not enough historical data from GeckoTerminal for this pool to analyze the range."},
    "period_high": {"ar": "أعلى سعر ({days} يوم)", "en": "Period high ({days}d)"},
    "period_low": {"ar": "أدنى سعر ({days} يوم)", "en": "Period low ({days}d)"},
    "position_in_range": {"ar": "موقع السعر ضمن النطاق", "en": "Price position in range"},
    "range_tight": {"ar": "🔒 **نطاق ضيّق (Range)** — الفرق بين القمة والقاع {pct:.1f}% فقط.",
                     "en": "🔒 **Tight range** — the high/low spread is only {pct:.1f}%."},
    "range_moderate": {"ar": "↔️ **تذبذب معتدل** — الفرق {pct:.1f}%.", "en": "↔️ **Moderate swing** — spread of {pct:.1f}%."},
    "range_trending": {"ar": "🚀 **اتجاه واضح** — الفرق {pct:.1f}%، الاتجاه {direction} ({chg:+.1f}%).",
                        "en": "🚀 **Clear trend** — spread {pct:.1f}%, direction {direction} ({chg:+.1f}%)."},
    "direction_up": {"ar": "صعودي 📈", "en": "up 📈"},
    "direction_down": {"ar": "هبوطي 📉", "en": "down 📉"},
    "range_position_caption": {"ar": "السعر الحالي عند {pos:.0f}% من عرض النطاق (0%=قاع، 100%=قمة).",
                                "en": "Current price sits at {pos:.0f}% of the range width (0%=low, 100%=high)."},

    # Sybil / clusters
    "clusters_header": {"ar": "🔗 تكتلات محافظ محتملة (نفس مصدر التمويل)", "en": "🔗 Possible Wallet Clusters (same funder)"},
    "cluster_wallets_msg": {"ar": "⚠️ **{n} محافظ** ممولة من نفس المصدر `{funder}`:",
                             "en": "⚠️ **{n} wallets** funded from the same source `{funder}`:"},

    # Accumulation table
    "table_header": {"ar": "🏆 المحافظ الأكثر تجميعاً", "en": "🏆 Top Accumulating Wallets"},
    "bot_disclaimer": {
        "ar": "⚠️ تصنيف النشاط تقديري (انتظام التوقيت وتطابق الكميات فقط)، وليس تحليلاً كاملاً لسلوك المحفظة.",
        "en": "⚠️ Activity classification is a heuristic (timing regularity + amount consistency only), not a full wallet-behavior analysis.",
    },
    "download_csv_btn": {"ar": "⬇️ تحميل CSV", "en": "⬇️ Download CSV"},
    "col_wallet": {"ar": "المحفظة", "en": "Wallet"},
    "col_buy_count": {"ar": "عدد مرات الشراء", "en": "Buy Count"},
    "col_total_amount": {"ar": "إجمالي الكمية", "en": "Total Amount"},
    "col_first_buy": {"ar": "أول عملية شراء", "en": "First Buy"},
    "col_last_buy": {"ar": "آخر عملية شراء", "en": "Last Buy"},
    "col_bot_label": {"ar": "تصنيف النشاط (تقديري)", "en": "Activity Label (heuristic)"},
    "col_smart_money": {"ar": "ظهرت سابقاً في عملات أخرى", "en": "Seen in other tokens before"},

    "bot_label_bot": {"ar": "🤖 يُحتمل بوت", "en": "🤖 Likely bot"},
    "bot_label_unclear": {"ar": "⚠️ نمط غير واضح", "en": "⚠️ Unclear pattern"},
    "bot_label_normal": {"ar": "🧑 يبدو طبيعي", "en": "🧑 Looks normal"},
    "bot_label_insufficient": {"ar": "بيانات غير كافية (أقل من 3 صفقات)", "en": "Not enough data (fewer than 3 trades)"},

    # Score
    "score_header": {"ar": "🧭 التقييم الإجمالي (Accumulation Score)", "en": "🧭 Overall Rating (Accumulation Score)"},
    "verdict_strong": {"ar": "🟢 إشارة تجميع قوية", "en": "🟢 Strong accumulation signal"},
    "verdict_watch": {"ar": "🟡 مراقبة", "en": "🟡 Watch"},
    "verdict_caution": {"ar": "🔴 حذر", "en": "🔴 Caution"},
    "why_score_expander": {"ar": "لماذا هذه الدرجة؟", "en": "Why this score?"},
    "score_disclaimer": {"ar": "⚠️ اجتهاد وليس توصية استثمارية.", "en": "⚠️ A heuristic estimate, not investment advice."},
    "no_wallets_for_score": {"ar": "لا توجد محافظ كافية لتقييم موثوق.", "en": "Not enough wallets for a reliable rating."},
    "not_enough_data_period": {"ar": "لا توجد بيانات كافية ضمن الفترة المحددة.", "en": "Not enough data in the selected period."},
    "missing_address_or_key": {"ar": "عنوان العملة أو مفتاح الـ API مفقود.", "en": "Missing token address or API key."},
    "no_dexscreener_data": {"ar": "لم يتم العثور على بيانات في Dexscreener لهذا العنوان/الشبكة.",
                             "en": "No Dexscreener data found for this address/network."},

    # Bulk tab
    "bulk_tokens_in_list": {"ar": "📋 **{n} عملة** في قائمة المراقبة", "en": "📋 **{n} token(s)** in the watchlist"},
    "bulk_empty_watchlist": {"ar": "أضف عملات في تبويب «📋 قائمة المراقبة» أولاً.",
                              "en": "Add tokens in the «📋 Watchlist» tab first."},
    "bulk_detect_clusters_label": {"ar": "🔗 كشف تكتلات المحافظ لكل عملة (أبطأ بكثير)",
                                    "en": "🔗 Detect wallet clusters for every token (much slower)"},
    "bulk_run_btn": {"ar": "🚀 شغّل التحليل الجماعي على كل القائمة", "en": "🚀 Run Bulk Analysis on the Whole List"},
    "bulk_progress": {"ar": "({i}/{n}) جاري تحليل {label}...", "en": "({i}/{n}) Analyzing {label}..."},
    "no_api_key_for_network": {"ar": "لا يوجد مفتاح API لهذه الشبكة", "en": "No API key set for this network"},
    "log_expander": {"ar": "سجل: {label} ({network})", "en": "Log: {label} ({network})"},
    "bulk_result_line": {"ar": "النتيجة: {verdict} — {score}/100 — {n} محفظة", "en": "Result: {verdict} — {score}/100 — {n} wallets"},
    "alerts_header": {"ar": "🔔 تنبيهات: {n} عملة بإشارة تجميع قوية!", "en": "🔔 Alerts: {n} token(s) with a strong accumulation signal!"},
    "alert_line": {"ar": "🟢 **{symbol}** ({network}) — Score: {score}/100 — {n} محفظة مجمّعة",
                   "en": "🟢 **{symbol}** ({network}) — Score: {score}/100 — {n} accumulating wallets"},
    "no_alerts": {"ar": "لا توجد تنبيهات تجميع قوية (Score ≥ 70) في آخر تحليل جماعي.",
                  "en": "No strong accumulation alerts (Score ≥ 70) in the last bulk run."},
    "bulk_summary_header": {"ar": "📊 ملخص كل عملات القائمة", "en": "📊 Summary of All Watchlist Tokens"},
    "bulk_col_network": {"ar": "الشبكة", "en": "Network"},
    "bulk_col_token": {"ar": "العملة", "en": "Token"},
    "bulk_col_address": {"ar": "العنوان", "en": "Address"},
    "bulk_col_verdict": {"ar": "التقييم", "en": "Verdict"},
    "bulk_col_wallets": {"ar": "عدد المحافظ", "en": "Wallets"},
    "bulk_col_note": {"ar": "ملاحظة", "en": "Note"},
    "download_summary_btn": {"ar": "⬇️ تحميل ملخص CSV", "en": "⬇️ Download Summary CSV"},

    # Reason templates for the score breakdown
    "reason_many_wallets": {"ar": "عدد جيد من المحافظ المجمّعة ({n}) (+10)", "en": "Good number of accumulating wallets ({n}) (+10)"},
    "reason_some_wallets": {"ar": "عدد معقول من المحافظ المجمّعة ({n}) (+5)", "en": "Reasonable number of accumulating wallets ({n}) (+5)"},
    "reason_bot_high": {"ar": "نسبة بوتات مرتفعة ({pct:.0%}) (-20)", "en": "High bot ratio ({pct:.0%}) (-20)"},
    "reason_bot_mid": {"ar": "نسبة بوتات متوسطة ({pct:.0%}) (-10)", "en": "Moderate bot ratio ({pct:.0%}) (-10)"},
    "reason_cluster_high": {"ar": "محافظ مرتبطة بنفس مصدر تمويل ({pct:.0%}) (-20)", "en": "Wallets linked to the same funding source ({pct:.0%}) (-20)"},
    "reason_cluster_mid": {"ar": "بعض المحافظ مرتبطة بنفس مصدر تمويل ({pct:.0%}) (-10)", "en": "Some wallets linked to the same funding source ({pct:.0%}) (-10)"},
    "reason_momentum_up": {"ar": "زخم صعودي مؤكد (سعر + فوليوم) (+15)", "en": "Confirmed bullish momentum (price + volume) (+15)"},
    "reason_momentum_down": {"ar": "ضغط بيع حقيقي (-15)", "en": "Real sell pressure (-15)"},
    "reason_range_low": {"ar": "السعر قريب من قاع النطاق ({pos:.0f}%) (+10)", "en": "Price near the bottom of the range ({pos:.0f}%) (+10)"},
    "reason_range_high": {"ar": "السعر قريب من قمة النطاق ({pos:.0f}%) (-10)", "en": "Price near the top of the range ({pos:.0f}%) (-10)"},
    "reason_smart_money_3plus": {"ar": "{n} محافظ لها سجل تاريخي (+10)", "en": "{n} wallets have prior history (+10)"},
    "reason_smart_money_1": {"ar": "{n} محفظة لها سجل تاريخي (+5)", "en": "{n} wallet has prior history (+5)"},

    # Docs tab content (long-form)
    "docs_title": {"ar": "📄 كيف تعمل هذه الأداة", "en": "📄 How This Tool Works"},
    "docs_body": {
        "ar": """
### فكرة الأداة
تستخرج هذه الأداة المحافظ التي تراكم شراء عملة معينة (نفس المحفظة اشترت أكثر من مرة)
عبر بيانات on-chain حقيقية، وتضيف عليها تحليل سوق (زخم، Range)، تقدير بوتات، كشف
تكتلات محافظ (Sybil)، وذاكرة تاريخية عبر عدة عملات — كل هذا مجاني بالكامل.

### مصادر البيانات
- **Dexscreener**: معلومات السوق العامة والـ Pools (بدون مفتاح)
- **Etherscan API V2**: تحويلات التوكن على كل شبكات EVM (مفتاح واحد مجاني)
- **Helius**: تحويلات التوكن على Solana (مفتاح مجاني)
- **GeckoTerminal**: شموع أسعار تاريخية + اكتشاف العملات الرائجة/الجديدة (بدون مفتاح)
- **Binance**: أعلى العملات ارتفاعاً (بدون مفتاح، اختياري)

### التبويبات
- **🔍 تحليل عملة واحدة**: فحص تفصيلي كامل لعملة محددة (نبض السوق، Range، جدول
  المحافظ، Accumulation Score)
- **📋 قائمة المراقبة**: اكتشف عملات تلقائياً (رائجة/جديدة/الأكثر ارتفاعاً على
  Binance) أو أضفها يدوياً، وتُحفظ دائماً في قاعدة بيانات محلية
- **⚡ تحليل جماعي**: يشغّل نفس الفحص الكامل على كل عملات القائمة بضغطة واحدة،
  ويعرض تنبيهات فورية لأي عملة بإشارة تجميع قوية (Score ≥ 70)
- **⚙️ الإعدادات**: أدخل مفاتيح API مرة واحدة، تُحفظ وتُستخدم تلقائياً في كل مكان

### Accumulation Score (0-100)
درجة واحدة تدمج: عدد المحافظ المجمّعة، نسبة البوتات المقدّرة، الزخم (سعر × فوليوم)،
موقع السعر ضمن الـ Range، تكتلات محافظ مشبوهة، وعدد المحافظ ذات السجل التاريخي.
كل سبب يظهر بالتفصيل — لا يوجد صندوق أسود.

### ⚠️ تنبيهات مهمة
- **هذه ليست توصية استثمارية.** كل الأرقام والتصنيفات (Score، تصنيف البوت، التكتلات)
  اجتهادات مبنية على بيانات متاحة، وقد تحتوي أخطاء أو تحيزات.
- **كشف البوتات تقديري وليس قاطعاً** — يعتمد فقط على انتظام التوقيت وتطابق الكميات.
- **تطابق أسماء Binance لا يضمن نفس المشروع** — تحقق دائماً بنفسك من العنوان.
- المفاتيح تُحفظ محلياً **بدون تشفير** — لا تستخدم الأداة على جهاز مشترك.
- كل البيانات (المفاتيح، قائمة المراقبة، الذاكرة التاريخية) في ملف واحد محلي:
  `wallet_memory.db` بجانب `app.py`. احذفه لتصفير كل شيء.
""",
        "en": """
### What this tool does
It finds wallets that repeatedly bought a given token (same wallet buying more than
once), using real on-chain data, then layers on market analysis (momentum, range),
bot-likelihood estimation, wallet-cluster (Sybil) detection, and cross-token
historical memory — all from free data sources.

### Data sources
- **Dexscreener**: general market info and pools (no key needed)
- **Etherscan API V2**: token transfers on every EVM chain (one free key)
- **Helius**: token transfers on Solana (free key)
- **GeckoTerminal**: historical price candles + trending/new token discovery (no key)
- **Binance**: top 24h gainers (no key, optional)

### Tabs
- **🔍 Single Token Analysis**: full detailed scan of one token (market pulse,
  range analysis, wallet table, Accumulation Score)
- **📋 Watchlist**: auto-discover tokens (trending / new / Binance top gainers) or
  add them manually — permanently saved to a local database
- **⚡ Bulk Analysis**: runs the same full scan across the entire watchlist in one
  click, and shows instant alerts for any token with a strong signal (Score ≥ 70)
- **⚙️ Settings**: enter your API keys once — they're saved and reused everywhere

### Accumulation Score (0-100)
A single score combining: number of accumulating wallets, estimated bot ratio,
momentum (price × volume), price position within its range, suspicious wallet
clusters, and wallets with prior cross-token history. Every contributing reason is
shown in detail — no black box.

### ⚠️ Important disclaimers
- **This is not investment advice.** Every number and label (Score, bot label,
  clusters) is a heuristic based on available data and may be wrong or biased.
- **Bot detection is a heuristic, not certain** — it only looks at timing
  regularity and amount consistency.
- **Binance name-matching does not guarantee the same project** — always verify
  the address yourself.

""",
    },
}


def t(key: str, **kwargs) -> str:
    lang = st.session_state.get("lang", "ar")
    template = TXT.get(key, {}).get(lang, key)
    return template.format(**kwargs) if kwargs else template


BOT_LABEL_KEYS = {
    "bot": "bot_label_bot", "unclear": "bot_label_unclear",
    "normal": "bot_label_normal", "insufficient": "bot_label_insufficient",
}
VERDICT_KEYS = {"strong": "verdict_strong", "watch": "verdict_watch", "caution": "verdict_caution"}
VERDICT_KIND = {"strong": "success", "watch": "warning", "caution": "error"}


# ----------------------------------------------------------------------
# Local database (SQLite) — settings, watchlist, historical memory
# Local to your machine only, unencrypted, not shared/cloud.
# ----------------------------------------------------------------------
def _resolve_db_path() -> str:
    """
    Resolve the database file path.

    Priority:
      1. ``WALLET_MEMORY_DB`` environment variable (useful for Streamlit Cloud
         where you can mount a persistent volume — set this env var to the
         mounted path so data survives redeploys).
      2. Local ``wallet_memory.db`` next to this script (default, local dev).
    """
    env_path = os.environ.get("WALLET_MEMORY_DB", "").strip()
    if env_path:
        return env_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "wallet_memory.db")


DB_PATH = _resolve_db_path()


def get_conn():
    return sqlite3.connect(DB_PATH)


def cur_ws() -> str:
    """Return the current session's workspace ID (fallback to a shared default)."""
    return st.session_state.get("workspace_id", "default")


def init_db():
    """
    كل جدول يحمل عمود workspace_id لعزل بيانات كل مستخدم عن الآخر — ضروري عند
    النشر على استضافة مشتركة (مثل Streamlit Cloud) حيث كل الزوّار يستخدمون نفس
    الملف الفعلي على القرص.
    Every table carries a workspace_id column to isolate each user's data —
    essential when deployed on shared hosting (e.g. Streamlit Cloud) where all
    visitors hit the same physical file on disk.
    """
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS settings (workspace_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT, PRIMARY KEY (workspace_id, key))")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL,
            network TEXT NOT NULL, token_address TEXT NOT NULL, label TEXT,
            added_date TEXT NOT NULL, UNIQUE(workspace_id, network, token_address)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wallet_sightings (
            workspace_id TEXT NOT NULL,
            wallet TEXT NOT NULL, network TEXT NOT NULL, token_address TEXT NOT NULL,
            token_symbol TEXT, buy_count INTEGER, total_amount REAL,
            bot_label TEXT, scan_date TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_scores (
            workspace_id TEXT NOT NULL,
            network TEXT NOT NULL, token_address TEXT NOT NULL, token_symbol TEXT,
            score INTEGER, verdict TEXT, scan_date TEXT NOT NULL,
            PRIMARY KEY (workspace_id, network, token_address)
        )
    """)
    conn.commit()
    conn.close()


def get_setting(workspace_id: str, key: str):
    conn = get_conn()
    cur = conn.execute("SELECT value FROM settings WHERE workspace_id = ? AND key = ?", (workspace_id, key))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def set_setting(workspace_id: str, key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (workspace_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(workspace_id, key) DO UPDATE SET value = excluded.value",
        (workspace_id, key, value),
    )
    conn.commit()
    conn.close()


def add_to_watchlist(workspace_id: str, network: str, token_address: str, label: str):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (workspace_id, network, token_address, label, added_date) VALUES (?,?,?,?,?)",
            (workspace_id, network, token_address.strip(), (label or "").strip(), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def remove_from_watchlist(workspace_id: str, item_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM watchlist WHERE id = ? AND workspace_id = ?", (item_id, workspace_id))
    conn.commit()
    conn.close()


def get_watchlist(workspace_id: str) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM watchlist WHERE workspace_id = ? ORDER BY added_date DESC", conn, params=(workspace_id,)
    )
    conn.close()
    return df


def save_wallet_sightings(workspace_id: str, df: pd.DataFrame, network_name: str, token_address: str, token_symbol: str):
    if df.empty:
        return
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (workspace_id, r["wallet"], network_name, token_address.lower(), token_symbol,
         int(r["buy_count"]), float(r["total_amount"]), r["bot_label"], now)
        for _, r in df.iterrows()
    ]
    conn.executemany(
        "INSERT INTO wallet_sightings "
        "(workspace_id, wallet, network, token_address, token_symbol, buy_count, total_amount, bot_label, scan_date) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()


def get_wallet_history(workspace_id: str, wallets: list, current_token_address: str):
    """dict: wallet -> count of distinct other tokens it appeared in before, within the same workspace only."""
    if not wallets:
        return {}
    conn = get_conn()
    placeholders = ",".join("?" for _ in wallets)
    query = f"""
        SELECT wallet, COUNT(DISTINCT token_address) AS token_count
        FROM wallet_sightings
        WHERE workspace_id = ? AND wallet IN ({placeholders}) AND token_address != ?
        GROUP BY wallet
    """
    cur = conn.execute(query, [workspace_id, *wallets, current_token_address.lower()])
    result = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return result


def upsert_token_score(workspace_id: str, network: str, token_address: str, token_symbol: str, score: int, verdict_code: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO token_scores (workspace_id, network, token_address, token_symbol, score, verdict, scan_date) "
        "VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(workspace_id, network, token_address) DO UPDATE SET "
        "token_symbol=excluded.token_symbol, score=excluded.score, verdict=excluded.verdict, scan_date=excluded.scan_date",
        (workspace_id, network, token_address.lower(), token_symbol, score, verdict_code, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_token_scores(workspace_id: str) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM token_scores WHERE workspace_id = ?", conn, params=(workspace_id,))
    conn.close()
    return df


init_db()


def _ensure_migration():
    """
    Safe migration: if an older DB exists without workspace_id column in tables
    that need it, migrate it. This is a no-op for fresh databases.
    """
    tables = {
        "settings": ["workspace_id"],
        "watchlist": ["workspace_id"],
        "wallet_sightings": ["workspace_id"],
        "token_scores": ["workspace_id"],
    }
    conn = get_conn()
    for table, cols in tables.items():
        try:
            existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            for col in cols:
                if col not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT NOT NULL DEFAULT 'default'")
            conn.commit()
        except Exception:
            pass
    conn.close()


_ensure_migration()


# ----------------------------------------------------------------------
# Dexscreener
# ----------------------------------------------------------------------
def get_dexscreener_info(token_address: str, chain: str):
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        return [p for p in pairs if p.get("chainId") == chain]
    except Exception as e:
        st.error(f"Dexscreener error: {e}")
        return []


def compute_market_metrics(pair: dict) -> dict:
    price_change = pair.get("priceChange", {}) or {}
    volume = pair.get("volume", {}) or {}
    volume_buy = pair.get("volumeBuy", {}) or {}
    volume_sell = pair.get("volumeSell", {}) or {}
    txns = pair.get("txns", {}) or {}
    buyers = pair.get("buyers", {}) or {}
    sellers = pair.get("sellers", {}) or {}

    h1_vol = volume.get("h1") or 0
    h6_avg_hourly = (volume.get("h6") or 0) / 6
    h24_avg_hourly = (volume.get("h24") or 0) / 24
    price_h1 = price_change.get("h1") or 0
    price_h24 = price_change.get("h24") or 0
    volume_rising = h1_vol > h6_avg_hourly and h1_vol > h24_avg_hourly

    b24 = buyers.get("h24")
    s24 = sellers.get("h24")
    buys24 = (txns.get("h24") or {}).get("buys")
    sells24 = (txns.get("h24") or {}).get("sells")
    vol_buy24 = volume_buy.get("h24")
    vol_sell24 = volume_sell.get("h24")

    # Compute buyer/seller pressure percentages for the UI progress bar
    buy_ratio = (buys24 / (buys24 + sells24) * 100) if (buys24 and sells24 and (buys24 + sells24) > 0) else None

    return {
        "price_change": price_change, "volume": volume,
        "price_h1": price_h1, "price_h24": price_h24,
        "h1_vol": h1_vol, "h6_avg_hourly": h6_avg_hourly, "h24_avg_hourly": h24_avg_hourly,
        "volume_rising": volume_rising,
        "buyers_h24": b24, "sellers_h24": s24, "buys_h24": buys24, "sells_h24": sells24,
        "avg_buy_price": (vol_buy24 / b24) if (vol_buy24 and b24) else None,
        "avg_sell_price": (vol_sell24 / s24) if (vol_sell24 and s24) else None,
        "buy_ratio": buy_ratio,
    }


def render_market_pulse(pair: dict) -> dict:
    m = compute_market_metrics(pair)
    tf_labels = {"m5": "5m", "h1": "1h", "h6": "6h", "h24": "24h"}

    st.markdown(t("price_change_header"))
    cols = st.columns(4)
    for col, tf in zip(cols, ["m5", "h1", "h6", "h24"]):
        val = m["price_change"].get(tf)
        col.metric(tf_labels[tf], f"{val:+.2f}%" if val is not None else "—")

    st.markdown(t("volume_header"))
    cols = st.columns(4)
    for col, tf in zip(cols, ["m5", "h1", "h6", "h24"]):
        val = m["volume"].get(tf)
        col.metric(tf_labels[tf], f"${val:,.0f}" if val is not None else "—")

    vol_change_vs_6h = ((m["h1_vol"] - m["h6_avg_hourly"]) / m["h6_avg_hourly"] * 100) if m["h6_avg_hourly"] else None
    vol_change_vs_24h = ((m["h1_vol"] - m["h24_avg_hourly"]) / m["h24_avg_hourly"] * 100) if m["h24_avg_hourly"] else None

    st.markdown(t("volume_trend_header"))
    v1, v2, v3 = st.columns(3)
    v1.metric(t("current_hour_volume"), f"${m['h1_vol']:,.0f}")
    v2.metric(t("vs_6h_avg"), f"{vol_change_vs_6h:+.1f}%" if vol_change_vs_6h is not None else "—")
    v3.metric(t("vs_24h_avg"), f"{vol_change_vs_24h:+.1f}%" if vol_change_vs_24h is not None else "—")
    st.markdown(t("volume_rising") if m["volume_rising"] else t("volume_falling"))

    st.markdown(t("momentum_header"))
    if m["price_h1"] > 0 and m["volume_rising"]:
        st.success(t("momentum_strong_up"))
    elif m["price_h1"] > 0 and not m["volume_rising"]:
        st.warning(t("momentum_weak_up"))
    elif m["price_h1"] < 0 and m["volume_rising"]:
        st.error(t("momentum_dump"))
    elif m["price_h1"] < 0 and not m["volume_rising"]:
        st.warning(t("momentum_fading_down"))
    else:
        st.info(t("momentum_flat"))

    trend_icon = "📈" if m["price_h24"] > 0 else "📉" if m["price_h24"] < 0 else "➖"
    st.caption(t("daily_trend_caption", icon=trend_icon, pct=m["price_h24"]))

    st.markdown(t("buyers_sellers_header"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("buyers_count"), f"{m['buyers_h24']:,}" if m["buyers_h24"] is not None else "—")
    c2.metric(t("sellers_count"), f"{m['sellers_h24']:,}" if m["sellers_h24"] is not None else "—")
    c3.metric(t("buy_txns"), f"{m['buys_h24']:,}" if m["buys_h24"] is not None else "—")
    c4.metric(t("sell_txns"), f"{m['sells_h24']:,}" if m["sells_h24"] is not None else "—")

    c5, c6 = st.columns(2)
    c5.metric(t("avg_buy_price"), f"${m['avg_buy_price']:,.2f}" if m["avg_buy_price"] else "—")
    c6.metric(t("avg_sell_price"), f"${m['avg_sell_price']:,.2f}" if m["avg_sell_price"] else "—")
    st.caption(t("smart_money_caption"))

    if m["buy_ratio"] is not None:
        st.progress(int(m["buy_ratio"]), text=t("buy_sell_pressure", buy=m["buy_ratio"], sell=100 - m["buy_ratio"]))

    return m


# ----------------------------------------------------------------------
# EVM chains (unified Etherscan API V2)
# ----------------------------------------------------------------------
def get_explorer_transfers(chain_id: int, token_address: str, api_key: str,
                            from_ts: int, to_ts: int, max_pages: int = 30, show_progress: bool = True):
    all_transfers = []
    page = 1
    offset = 1000
    progress = st.progress(0) if show_progress else None

    while page <= max_pages:
        params = {
            "chainid": chain_id, "module": "account", "action": "tokentx",
            "contractaddress": token_address, "page": page, "offset": offset,
            "sort": "desc", "apikey": api_key,
        }
        try:
            resp = requests.get(ETHERSCAN_V2_API, params=params, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            st.error(f"Explorer API error: {e}")
            break

        if payload.get("status") != "1":
            result = payload.get("result", "")
            if "No transactions found" not in str(result) and show_progress:
                st.warning(f"API response: {payload.get('message', '')} — {result}")
            break

        batch = payload.get("result", [])
        if not batch:
            break

        all_transfers.extend(batch)
        oldest_ts_in_batch = int(batch[-1]["timeStamp"])
        if progress:
            progress.progress(min(page / max_pages, 1.0))

        if oldest_ts_in_batch < from_ts or len(batch) < offset:
            break
        page += 1
        time.sleep(0.25)

    if progress:
        progress.empty()
    return [tx for tx in all_transfers if from_ts <= int(tx["timeStamp"]) <= to_ts]


def get_wallet_funder(chain_id: int, wallet_address: str, api_key: str):
    params = {
        "chainid": chain_id, "module": "account", "action": "txlist",
        "address": wallet_address, "startblock": 0, "endblock": 99999999,
        "page": 1, "offset": 5, "sort": "asc", "apikey": api_key,
    }
    try:
        resp = requests.get(ETHERSCAN_V2_API, params=params, timeout=15)
        data = resp.json()
        if data.get("status") != "1":
            return None
        for tx in data.get("result", []):
            if (tx.get("to") or "").lower() == wallet_address.lower():
                return (tx.get("from") or "").lower()
    except Exception:
        return None
    return None


def detect_wallet_clusters(chain_id: int, wallets: list, api_key: str, max_wallets: int = 15, show_progress: bool = True):
    funders = {}
    checked = wallets[:max_wallets]
    if not checked:
        return {}
    progress = st.progress(0) if show_progress else None
    for i, wallet in enumerate(checked):
        funder = get_wallet_funder(chain_id, wallet, api_key)
        if funder:
            funders.setdefault(funder, []).append(wallet)
        if progress:
            progress.progress((i + 1) / len(checked))
        time.sleep(0.25)
    if progress:
        progress.empty()
    return {f: ws for f, ws in funders.items() if len(ws) >= 2}


def normalize_evm_transfers(transfers: list):
    rows = []
    for tx in transfers:
        try:
            decimals = int(tx.get("tokenDecimal", 18))
            amount = int(tx.get("value", 0)) / (10 ** decimals)
        except (TypeError, ValueError):
            amount = 0
        try:
            ts = datetime.fromtimestamp(int(tx["timeStamp"]), tz=timezone.utc)
        except (KeyError, ValueError, TypeError):
            ts = pd.NaT
        rows.append({
            "from": (tx.get("from") or "").lower(), "wallet": (tx.get("to") or "").lower(),
            "amount": amount, "tx_hash": tx.get("hash"), "date": ts,
        })
    return rows


# ----------------------------------------------------------------------
# Solana (Helius)
# ----------------------------------------------------------------------
def get_helius_transactions(token_mint: str, api_key: str, from_ts: int, to_ts: int,
                             max_pages: int = 30, show_progress: bool = True):
    url = f"https://api.helius.xyz/v1/addresses/{token_mint}/transactions"
    all_tx = []
    before = None
    progress = st.progress(0) if show_progress else None

    for page in range(max_pages):
        params = {"api-key": api_key, "limit": 100}
        if before:
            params["before"] = before
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            batch = resp.json()
        except Exception as e:
            st.error(f"Helius error: {e}")
            break
        if not batch:
            break
        all_tx.extend(batch)
        before = batch[-1].get("signature")
        oldest_ts = batch[-1].get("timestamp", 0)
        if progress:
            progress.progress(min((page + 1) / max_pages, 1.0))
        if not before or oldest_ts < from_ts:
            break
        time.sleep(0.15)

    if progress:
        progress.empty()
    return [tx for tx in all_tx if from_ts <= tx.get("timestamp", 0) <= to_ts]


def normalize_solana_transfers(transactions: list, token_mint: str):
    rows = []
    for tx in transactions:
        ts_raw = tx.get("timestamp")
        ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc) if ts_raw else pd.NaT
        for tt in tx.get("tokenTransfers", []):
            if tt.get("mint") != token_mint:
                continue
            rows.append({
                "from": (tt.get("fromUserAccount") or "").lower(), "wallet": (tt.get("toUserAccount") or "").lower(),
                "amount": tt.get("tokenAmount", 0) or 0, "tx_hash": tx.get("signature"), "date": ts,
            })
    return rows


# ----------------------------------------------------------------------
# Wallet analysis + bot heuristic
# ----------------------------------------------------------------------
def estimate_bot_likelihood(dates: list, amounts: list):
    """Returns an internal code: 'bot' | 'unclear' | 'normal' | 'insufficient'."""
    if len(dates) < 3:
        return None, "insufficient"
    sorted_dates = sorted(dates)
    gaps = [(sorted_dates[i + 1] - sorted_dates[i]).total_seconds() for i in range(len(sorted_dates) - 1)]
    gap_mean = sum(gaps) / len(gaps) if gaps else 0
    gap_std = (sum((g - gap_mean) ** 2 for g in gaps) / len(gaps)) ** 0.5 if gaps else 0
    gap_cv = (gap_std / gap_mean) if gap_mean > 0 else None

    amt_mean = sum(amounts) / len(amounts) if amounts else 0
    amt_std = (sum((a - amt_mean) ** 2 for a in amounts) / len(amounts)) ** 0.5 if amounts else 0
    amt_cv = (amt_std / amt_mean) if amt_mean > 0 else None

    score = 0
    if gap_cv is not None:
        score += 50 if gap_cv < 0.15 else (25 if gap_cv < 0.35 else 0)
    if amt_cv is not None:
        score += 50 if amt_cv < 0.05 else (25 if amt_cv < 0.15 else 0)

    code = "bot" if score >= 50 else ("unclear" if score >= 25 else "normal")
    return score, code


def build_accumulation_table(rows: list, pool_addresses: set) -> pd.DataFrame:
    """Internal English column names throughout: wallet, buy_count, total_amount, first_buy, last_buy, bot_label."""
    pool_addresses_lower = {p.lower() for p in pool_addresses}
    buy_rows = [r for r in rows if (r["from"] in pool_addresses_lower if pool_addresses_lower else True) and r["wallet"]]

    cols = ["wallet", "buy_count", "total_amount", "first_buy", "last_buy", "bot_label"]
    if not buy_rows:
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(buy_rows)
    grouped = df.groupby("wallet").agg(
        buy_count=("wallet", "count"), total_amount=("amount", "sum"),
        first_buy=("date", "min"), last_buy=("date", "max"),
    ).reset_index()

    bot_codes = []
    for wallet in grouped["wallet"]:
        sub = df[df["wallet"] == wallet]
        _, code = estimate_bot_likelihood(list(sub["date"]), list(sub["amount"]))
        bot_codes.append(code)
    grouped["bot_label"] = bot_codes

    return grouped.sort_values(by=["buy_count", "total_amount"], ascending=[False, False])


def localize_wallet_table(df: pd.DataFrame) -> pd.DataFrame:
    """Rename internal English columns + translate bot_label codes for display, in the current language."""
    if df.empty:
        return df
    out = df.copy()
    out["bot_label"] = out["bot_label"].apply(lambda code: t(BOT_LABEL_KEYS.get(code, "bot_label_insufficient")))
    rename_map = {
        "wallet": t("col_wallet"), "buy_count": t("col_buy_count"), "total_amount": t("col_total_amount"),
        "first_buy": t("col_first_buy"), "last_buy": t("col_last_buy"), "bot_label": t("col_bot_label"),
        "smart_money_count": t("col_smart_money"),
    }
    return out.rename(columns=rename_map)


# ----------------------------------------------------------------------
# Range analysis (GeckoTerminal, free, no key)
# ----------------------------------------------------------------------
def get_ohlcv_data(gt_network: str, pool_address: str, days: int = 30):
    url = f"https://api.geckoterminal.com/api/v2/networks/{gt_network}/pools/{pool_address}/ohlcv/day"
    params = {"aggregate": 1, "limit": days, "currency": "usd"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        ohlcv_list = resp.json().get("data", {}).get("attributes", {}).get("ohlcv_list", [])
        return sorted(ohlcv_list, key=lambda x: x[0])
    except Exception as e:
        st.error(f"GeckoTerminal error: {e}")
        return []


def compute_range_metrics(ohlcv: list, days: int):
    if len(ohlcv) < 5:
        return None
    dates = [datetime.fromtimestamp(c[0], tz=timezone.utc) for c in ohlcv]
    closes = [c[4] for c in ohlcv]
    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    period_high, period_low = max(highs), min(lows)
    current_price, first_price = closes[-1], closes[0]
    range_pct = ((period_high - period_low) / period_low * 100) if period_low else 0
    position_in_range = ((current_price - period_low) / (period_high - period_low) * 100) if period_high > period_low else 50
    overall_change = ((current_price - first_price) / first_price * 100) if first_price else 0
    return {
        "dates": dates, "closes": closes, "period_high": period_high, "period_low": period_low,
        "range_pct": range_pct, "position_in_range": position_in_range,
        "overall_change": overall_change, "days": days,
    }


def render_range_analysis(gt_network: str, pool_address: str, days: int):
    ohlcv = get_ohlcv_data(gt_network, pool_address, days)
    rm = compute_range_metrics(ohlcv, days)
    if rm is None:
        st.info(t("no_range_data"))
        return None

    price_label = "Price" if st.session_state.get("lang") == "en" else "السعر"
    date_label = "Date" if st.session_state.get("lang") == "en" else "التاريخ"
    chart_df = pd.DataFrame({date_label: rm["dates"], price_label: rm["closes"]}).set_index(date_label)
    st.line_chart(chart_df)

    c1, c2, c3 = st.columns(3)
    c1.metric(t("period_high", days=days), f"${rm['period_high']:,.6f}")
    c2.metric(t("period_low", days=days), f"${rm['period_low']:,.6f}")
    c3.metric(t("position_in_range"), f"{rm['position_in_range']:.0f}%")

    if rm["range_pct"] < 15:
        st.success(t("range_tight", pct=rm["range_pct"]))
    elif rm["range_pct"] < 40:
        st.warning(t("range_moderate", pct=rm["range_pct"]))
    else:
        direction = t("direction_up") if rm["overall_change"] > 0 else t("direction_down")
        st.info(t("range_trending", pct=rm["range_pct"], direction=direction, chg=rm["overall_change"]))

    st.caption(t("range_position_caption", pos=rm["position_in_range"]))
    return rm


# ----------------------------------------------------------------------
# Discovery: GeckoTerminal trending/new pools + Binance top gainers
# ----------------------------------------------------------------------
def get_trending_pools(gt_network: str, mode: str = "trending", pages: int = 1):
    endpoint = "trending_pools" if mode == "trending" else "new_pools"
    url = f"https://api.geckoterminal.com/api/v2/networks/{gt_network}/{endpoint}"
    results = []

    for page in range(1, pages + 1):
        params = {"include": "base_token", "page": page}
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            st.error(f"GeckoTerminal error: {e}")
            break

        included = {item["id"]: item for item in data.get("included", [])}
        pool_list = data.get("data", [])
        if not pool_list:
            break

        for pool in pool_list:
            attrs = pool.get("attributes", {}) or {}
            base_ref = ((pool.get("relationships", {}) or {}).get("base_token", {}) or {}).get("data", {}) or {}
            token_attrs = (included.get(base_ref.get("id"), {}) or {}).get("attributes", {}) or {}
            results.append({
                "pool_address": attrs.get("address"),
                "token_address": token_attrs.get("address"),
                "symbol": token_attrs.get("symbol"),
                "name": token_attrs.get("name"),
                "price_change_h24": (attrs.get("price_change_percentage") or {}).get("h24"),
                "volume_h24": attrs.get("volume_usd", {}).get("h24") if attrs.get("volume_usd") else None,
                "liquidity_usd": attrs.get("reserve_in_usd"),
            })
        time.sleep(0.3)

    return results


def get_binance_top_gainers(limit: int = 20, quote: str = "USDT"):
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        st.error(f"Binance error: {e} (may be geo-blocked, HTTP 451, in some countries)")
        return []

    filtered = [d for d in data if isinstance(d, dict) and d.get("symbol", "").endswith(quote)]
    for d in filtered:
        try:
            d["_pct"] = float(d.get("priceChangePercent", 0))
        except (TypeError, ValueError):
            d["_pct"] = 0.0
    filtered.sort(key=lambda d: d["_pct"], reverse=True)

    return [
        {"symbol": d["symbol"][: -len(quote)], "price_change_percent": d["_pct"], "volume_quote": float(d.get("quoteVolume", 0) or 0)}
        for d in filtered[:limit]
    ]


def match_symbol_to_chain_token(symbol: str):
    url = "https://api.dexscreener.com/latest/dex/search"
    try:
        resp = requests.get(url, params={"q": symbol}, timeout=15)
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
    except Exception:
        return None

    supported_chains = {v["dexscreener_chain"]: k for k, v in NETWORKS.items()}
    candidates = [
        p for p in pairs
        if p.get("chainId") in supported_chains
        and (p.get("baseToken", {}) or {}).get("symbol", "").upper() == symbol.upper()
    ]
    if not candidates:
        return None

    best = max(candidates, key=lambda p: (p.get("liquidity") or {}).get("usd", 0))
    base = best.get("baseToken", {}) or {}
    return {
        "network": supported_chains[best["chainId"]], "token_address": base.get("address"),
        "symbol": base.get("symbol"), "liquidity_usd": (best.get("liquidity") or {}).get("usd"),
    }


# ----------------------------------------------------------------------
# Unified Accumulation Score
# ----------------------------------------------------------------------
def compute_accumulation_score(filtered_table: pd.DataFrame, market_metrics, range_metrics, smart_money_map, cluster_wallets):
    """Returns (score, reasons) where reasons is a list of (translation_key, kwargs) tuples."""
    score = 50
    reasons = []
    n_wallets = len(filtered_table)
    if n_wallets == 0:
        return 50, [("no_wallets_for_score", {})]

    if n_wallets >= 10:
        score += 10; reasons.append(("reason_many_wallets", {"n": n_wallets}))
    elif n_wallets >= 5:
        score += 5; reasons.append(("reason_some_wallets", {"n": n_wallets}))

    bot_ratio = (filtered_table["bot_label"] == "bot").sum() / n_wallets
    if bot_ratio > 0.4:
        score -= 20; reasons.append(("reason_bot_high", {"pct": bot_ratio}))
    elif bot_ratio > 0.2:
        score -= 10; reasons.append(("reason_bot_mid", {"pct": bot_ratio}))

    if cluster_wallets:
        cluster_ratio = sum(1 for w in filtered_table["wallet"] if w in cluster_wallets) / n_wallets
        if cluster_ratio > 0.3:
            score -= 20; reasons.append(("reason_cluster_high", {"pct": cluster_ratio}))
        elif cluster_ratio > 0.1:
            score -= 10; reasons.append(("reason_cluster_mid", {"pct": cluster_ratio}))

    if market_metrics:
        if market_metrics["price_h1"] > 0 and market_metrics["volume_rising"]:
            score += 15; reasons.append(("reason_momentum_up", {}))
        elif market_metrics["price_h1"] < 0 and market_metrics["volume_rising"]:
            score -= 15; reasons.append(("reason_momentum_down", {}))

    if range_metrics:
        pos = range_metrics["position_in_range"]
        if pos <= 35:
            score += 10; reasons.append(("reason_range_low", {"pos": pos}))
        elif pos >= 80:
            score -= 10; reasons.append(("reason_range_high", {"pos": pos}))

    if smart_money_map:
        returning = sum(1 for w in filtered_table["wallet"] if smart_money_map.get(w, 0) > 0)
        if returning >= 3:
            score += 10; reasons.append(("reason_smart_money_3plus", {"n": returning}))
        elif returning >= 1:
            score += 5; reasons.append(("reason_smart_money_1", {"n": returning}))

    return max(0, min(100, score)), reasons


def score_verdict_code(score: int) -> str:
    if score >= 70:
        return "strong"
    if score >= 45:
        return "watch"
    return "caution"


# ----------------------------------------------------------------------
# Unified analysis pipeline — used by both single and bulk modes
# ----------------------------------------------------------------------
def analyze_token(workspace_id: str, network_name: str, token_address: str, api_key: str,
                   start_date, end_date, min_buys: int, range_days: int,
                   detect_clusters: bool, max_cluster_wallets: int, verbose: bool = True):
    network = NETWORKS[network_name]
    is_solana = network["type"] == "solana"
    result = {
        "network_name": network_name, "token_address": token_address, "token_symbol": "",
        "score": 0, "verdict_code": "caution", "wallet_count": 0, "table": pd.DataFrame(), "reasons": [],
        "error": None,
    }

    if not token_address or not api_key:
        result["error"] = t("missing_address_or_key")
        return result

    pairs = get_dexscreener_info(token_address, network["dexscreener_chain"])
    pool_addresses = set()
    market_metrics = None
    range_metrics = None

    if pairs:
        best = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd", 0))
        base = best.get("baseToken", {})
        result["token_symbol"] = base.get("symbol", "")
        pool_addresses = {p.get("pairAddress") for p in pairs if p.get("pairAddress")}

        if verbose:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(t("col_symbol"), base.get("symbol", "—"))
            c2.metric("USD", best.get("priceUsd", "—"))
            c3.metric(t("col_liquidity"), f"{best.get('liquidity', {}).get('usd', 0):,.0f}")
            c4.metric("#Pairs", len(pairs))
            st.divider()
            market_metrics = render_market_pulse(best)
            st.divider()
            st.markdown(t("range_header", days=range_days))
            if best.get("pairAddress") and network.get("geckoterminal_network"):
                range_metrics = render_range_analysis(network["geckoterminal_network"], best["pairAddress"], range_days)
        else:
            market_metrics = compute_market_metrics(best)
            if best.get("pairAddress") and network.get("geckoterminal_network"):
                ohlcv = get_ohlcv_data(network["geckoterminal_network"], best["pairAddress"], range_days)
                range_metrics = compute_range_metrics(ohlcv, range_days)
    elif verbose:
        st.info(t("no_dexscreener_data"))

    from_ts = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    to_ts = int(datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc).timestamp())

    if is_solana:
        raw_tx = get_helius_transactions(token_address, api_key, from_ts, to_ts, show_progress=verbose)
        rows = normalize_solana_transfers(raw_tx, token_address)
    else:
        raw_tx = get_explorer_transfers(network["chain_id"], token_address, api_key, from_ts, to_ts, show_progress=verbose)
        rows = normalize_evm_transfers(raw_tx)

    table = build_accumulation_table(rows, pool_addresses)
    if table.empty:
        result["error"] = t("not_enough_data_period")
        return result

    filtered = table[table["buy_count"] >= min_buys].copy()
    wallets_list = list(filtered["wallet"])
    smart_money_map = get_wallet_history(workspace_id, wallets_list, token_address)
    filtered["smart_money_count"] = filtered["wallet"].apply(lambda w: smart_money_map.get(w, 0))

    cluster_wallets = set()
    if detect_clusters and not is_solana and wallets_list:
        top_wallets = list(filtered.sort_values("buy_count", ascending=False)["wallet"])
        clusters = detect_wallet_clusters(network["chain_id"], top_wallets, api_key, max_cluster_wallets, show_progress=verbose)
        for ws in clusters.values():
            cluster_wallets.update(ws)
        if verbose and clusters:
            st.divider()
            st.subheader(t("clusters_header"))
            for funder, ws in clusters.items():
                st.warning(t("cluster_wallets_msg", n=len(ws), funder=funder))
                st.code("\n".join(ws))

    score, reasons = compute_accumulation_score(filtered, market_metrics, range_metrics, smart_money_map, cluster_wallets)
    verdict_code = score_verdict_code(score)

    save_wallet_sightings(workspace_id, filtered, network_name, token_address, result["token_symbol"])
    upsert_token_score(workspace_id, network_name, token_address, result["token_symbol"], score, verdict_code)

    result.update({
        "score": score, "verdict_code": verdict_code,
        "wallet_count": len(filtered), "table": filtered, "reasons": reasons,
    })

    if verbose:
        st.divider()
        st.subheader(t("table_header"))
        st.caption(t("bot_disclaimer"))
        display_df = localize_wallet_table(filtered)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        if len(filtered) > 0:
            chart_series = filtered.head(15).set_index("wallet")["buy_count"]
            st.bar_chart(chart_series)
        csv = display_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(t("download_csv_btn"), csv, "accumulation_wallets.csv", "text/csv", key=f"dl_{token_address}")

        st.divider()
        st.subheader(t("score_header"))
        getattr(st, VERDICT_KIND[verdict_code])(f"### {t(VERDICT_KEYS[verdict_code])} — {score}/100")
        with st.expander(t("why_score_expander")):
            for key, kwargs in reasons:
                st.markdown(f"- {t(key, **kwargs)}")
        st.caption(t("score_disclaimer"))

    return result


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------
if "lang" not in st.session_state:
    st.session_state.lang = "en"

# Persistent workspace ID per visitor: stored in the URL query string so it
# survives page refreshes and can be shared/bookmarked. Falls back to a
# random ID for first-time visitors.
_ws_param = st.query_params.get("ws", "")
if "workspace_id" not in st.session_state:
    st.session_state.workspace_id = _ws_param if _ws_param else secrets.token_hex(4)
if _ws_param and _ws_param != st.session_state.workspace_id:
    st.query_params["ws"] = st.session_state.workspace_id

if "etherscan_key" not in st.session_state:
    st.session_state.etherscan_key = get_setting(st.session_state.workspace_id, "etherscan_key")
if "helius_key" not in st.session_state:
    st.session_state.helius_key = get_setting(st.session_state.workspace_id, "helius_key")

_lang_col1, _lang_col2 = st.columns([5, 1])
with _lang_col2:
    lang_choice = st.radio("lang", ["🇸🇦 عربي", "🇬🇧 EN"], horizontal=True, label_visibility="collapsed", key="lang_radio")
    st.session_state.lang = "ar" if "عربي" in lang_choice else "en"

if st.session_state.lang == "ar":
    st.markdown(
        "<style>.block-container{direction:rtl;} .stRadio > div{direction:rtl;}</style>",
        unsafe_allow_html=True,
    )

with _lang_col1:
    st.title(t("app_title"))
    st.caption(t("app_caption"))

if DONATION_WALLET_ADDRESS and DONATION_WALLET_ADDRESS != "YOUR_WALLET_ADDRESS_HERE":
    st.info(t("donation_line"))
    st.code(f"{DONATION_WALLET_ADDRESS}  ({DONATION_LABEL})", language=None)

tab_single, tab_watchlist, tab_bulk, tab_settings, tab_docs = st.tabs([
    t("tab_single"), t("tab_watchlist"), t("tab_bulk"), t("tab_settings"), t("tab_docs"),
])


def get_api_key_for(network_name: str) -> str:
    return st.session_state.helius_key if NETWORKS[network_name]["type"] == "solana" else st.session_state.etherscan_key


# ---------------- Settings tab ----------------
with tab_settings:
    st.subheader(t("workspace_header"))
    st.caption(t("workspace_caption"))
    st.code(st.session_state.workspace_id, language=None)
    st.warning(t("workspace_warning"))

    with st.expander(t("workspace_switch_expander")):
        switch_input = st.text_input(t("workspace_switch_label"), key="workspace_switch_input")
        if st.button(t("workspace_switch_btn")):
            if switch_input.strip():
                st.session_state.workspace_id = switch_input.strip()
                st.session_state.etherscan_key = get_setting(st.session_state.workspace_id, "etherscan_key")
                st.session_state.helius_key = get_setting(st.session_state.workspace_id, "helius_key")
                st.success(t("workspace_switched_msg"))
                st.rerun()
            else:
                st.warning(t("enter_address_first"))

    st.divider()
    st.subheader(t("settings_keys_header"))
    st.caption(t("settings_keys_caption"))

    etherscan_input = st.text_input(t("etherscan_key_label"), value=st.session_state.etherscan_key, type="password",
                                     help="https://etherscan.io/apis")
    helius_input = st.text_input(t("helius_key_label"), value=st.session_state.helius_key, type="password",
                                  help="https://www.helius.dev")

    if st.button(t("save_keys_btn"), type="primary"):
        set_setting(st.session_state.workspace_id, "etherscan_key", etherscan_input)
        set_setting(st.session_state.workspace_id, "helius_key", helius_input)
        st.session_state.etherscan_key = etherscan_input
        st.session_state.helius_key = helius_input
        st.success(t("keys_saved_msg"))

    st.warning(t("keys_security_warning"))

# ---------------- Watchlist tab ----------------
with tab_watchlist:
    st.subheader(t("discovery_header"))

    disc_source = st.radio(
        t("discovery_source_label"), [t("src_trending"), t("src_new"), t("src_binance")],
        key="disc_source", horizontal=True,
    )
    is_binance_mode = disc_source == t("src_binance")

    if is_binance_mode:
        st.warning(t("binance_warning"))
        binance_limit = st.slider(t("binance_limit_label"), 5, 30, 10, key="disc_binance_limit")
    else:
        c1, c2 = st.columns(2)
        with c1:
            disc_network = st.selectbox(t("network_label"), list(NETWORKS.keys()), key="disc_network")
        with c2:
            disc_pages = st.slider(t("pages_label"), 1, 5, 1, key="disc_pages")

    disc_min_liq = st.number_input(t("min_liquidity_label"), min_value=0, value=10000, step=1000, key="disc_min_liq")

    if st.button(t("search_btn"), key="disc_search"):
        discovered = []
        if is_binance_mode:
            gainers = get_binance_top_gainers(binance_limit)
            if gainers:
                match_progress = st.progress(0, text=t("matching_progress"))
                for i, g in enumerate(gainers):
                    match = match_symbol_to_chain_token(g["symbol"])
                    if match and match["token_address"] and (
                        match["liquidity_usd"] is None or float(match["liquidity_usd"]) >= disc_min_liq
                    ):
                        discovered.append({
                            "network": match["network"], "token_address": match["token_address"],
                            "symbol": match["symbol"], "price_change_h24": g["price_change_percent"],
                            "volume_h24": g["volume_quote"], "liquidity_usd": match["liquidity_usd"],
                        })
                    match_progress.progress((i + 1) / len(gainers))
                    time.sleep(0.25)
                match_progress.empty()
                if not discovered:
                    st.warning(t("no_binance_match"))
        else:
            mode = "trending" if disc_source == t("src_trending") else "new"
            gt_network = NETWORKS[disc_network]["geckoterminal_network"]
            raw = get_trending_pools(gt_network, mode, disc_pages)
            for d in raw:
                if d["token_address"] and (d["liquidity_usd"] is None or float(d["liquidity_usd"]) >= disc_min_liq):
                    discovered.append({**d, "network": disc_network})

        st.session_state["discovered_tokens"] = discovered

    if st.session_state.get("discovered_tokens"):
        discovered = st.session_state["discovered_tokens"]
        disc_df = pd.DataFrame([
            {
                t("col_add"): False, t("col_network"): d["network"], t("col_symbol"): d["symbol"] or "—",
                t("col_address"): d["token_address"],
                t("col_change24"): f"{float(d['price_change_h24']):+.1f}%" if d["price_change_h24"] else "—",
                t("col_volume24"): f"${float(d['volume_h24']):,.0f}" if d["volume_h24"] else "—",
                t("col_liquidity"): f"${float(d['liquidity_usd']):,.0f}" if d["liquidity_usd"] else "—",
            }
            for d in discovered
        ])

        st.write(t("found_n_tokens", n=len(discovered)))
        edited = st.data_editor(
            disc_df, hide_index=True, use_container_width=True, key="disc_editor",
            column_config={t("col_add"): st.column_config.CheckboxColumn(default=False)},
            disabled=[t("col_network"), t("col_symbol"), t("col_address"), t("col_change24"), t("col_volume24"), t("col_liquidity")],
        )

        b1, b2 = st.columns(2)
        if b1.button(t("add_selected_btn")):
            added = 0
            for i, sel in enumerate(edited[t("col_add")]):
                if sel:
                    d = discovered[i]
                    add_to_watchlist(cur_ws(), d["network"], d["token_address"], d["symbol"] or "")
                    added += 1
            if added:
                st.success(t("added_n_tokens", n=added))
                st.rerun()
            else:
                st.warning(t("select_at_least_one"))
        if b2.button(t("add_all_btn")):
            for d in discovered:
                add_to_watchlist(cur_ws(), d["network"], d["token_address"], d["symbol"] or "")
            st.success(t("added_n_tokens", n=len(discovered)))
            st.rerun()

    st.divider()
    st.subheader(t("manual_add_header"))
    c1, c2 = st.columns([1, 2])
    with c1:
        wl_network = st.selectbox(t("network_label"), list(NETWORKS.keys()), key="wl_network")
    with c2:
        wl_address = st.text_input(t("address_input_label"), key="wl_address")
    wl_label = st.text_input(t("label_input_label"), key="wl_label")

    if st.button(t("add_btn")):
        if wl_address.strip():
            add_to_watchlist(cur_ws(), wl_network, wl_address, wl_label)
            st.success(t("added_ok"))
            st.rerun()
        else:
            st.warning(t("enter_address_first"))

    st.divider()
    watchlist_df = get_watchlist(cur_ws())
    scores_df = get_token_scores(cur_ws())

    st.subheader(t("current_list_header", n=len(watchlist_df)))
    if watchlist_df.empty:
        st.info(t("empty_watchlist"))
    else:
        for _, row in watchlist_df.iterrows():
            score_row = scores_df[
                (scores_df["network"] == row["network"]) & (scores_df["token_address"] == row["token_address"].lower())
            ] if not scores_df.empty else pd.DataFrame()

            c1, c2, c3, c4, c5 = st.columns([1.5, 3, 1.5, 1.5, 0.7])
            c1.write(f"**{row['network']}**")
            c2.code(row["token_address"], language=None)
            c3.write(row["label"] or "—")
            if not score_row.empty:
                sr = score_row.iloc[0]
                c4.write(f"{t(VERDICT_KEYS.get(sr['verdict'], 'verdict_caution'))} ({int(sr['score'])})")
            else:
                c4.write(t("not_scanned_yet"))
            if c5.button("🗑️", key=f"del_{row['id']}"):
                remove_from_watchlist(cur_ws(), row["id"])
                st.rerun()

# ---------------- Single analysis tab ----------------
with tab_single:
    c1, c2 = st.columns(2)
    with c1:
        network_name = st.selectbox(t("network_label"), list(NETWORKS.keys()), key="single_network")
    with c2:
        token_address = st.text_input(t("address_input_label"), key="single_address")

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input(t("start_date_label"), value=datetime.now() - timedelta(days=7), key="single_start")
    with c2:
        end_date = st.date_input(t("end_date_label"), value=datetime.now(), key="single_end")

    c1, c2 = st.columns(2)
    with c1:
        min_buys = st.slider(t("min_buys_label"), 1, 20, 2, key="single_min_buys")
    with c2:
        range_days = st.slider(t("range_days_label"), 20, 30, 25, key="single_range_days")

    is_solana_single = NETWORKS[network_name]["type"] == "solana"
    c1, c2 = st.columns(2)
    with c1:
        detect_clusters = st.checkbox(t("detect_clusters_label"), value=False, disabled=is_solana_single, key="single_clusters")
    with c2:
        max_cluster_wallets = st.slider(t("max_cluster_label"), 5, 25, 15,
                                         disabled=(not detect_clusters or is_solana_single), key="single_max_cluster")

    api_key_missing = not get_api_key_for(network_name)
    if api_key_missing:
        st.warning(t("api_key_missing_warning"))

    if st.button(t("run_analysis_btn"), type="primary", disabled=api_key_missing, key="single_run"):
        if not token_address:
            st.warning(t("enter_token_address"))
        elif start_date >= end_date:
            st.warning(t("date_order_warning"))
        else:
            analyze_token(
                network_name, token_address, get_api_key_for(network_name),
                start_date, end_date, min_buys, range_days,
                detect_clusters, max_cluster_wallets, verbose=True,
            )

# ---------------- Bulk analysis tab ----------------
with tab_bulk:
    watchlist_df = get_watchlist(cur_ws())
    st.write(t("bulk_tokens_in_list", n=len(watchlist_df)))

    if watchlist_df.empty:
        st.info(t("bulk_empty_watchlist"))
    else:
        c1, c2 = st.columns(2)
        with c1:
            bulk_start = st.date_input(t("start_date_label"), value=datetime.now() - timedelta(days=7), key="bulk_start")
        with c2:
            bulk_end = st.date_input(t("end_date_label"), value=datetime.now(), key="bulk_end")

        c1, c2 = st.columns(2)
        with c1:
            bulk_min_buys = st.slider(t("min_buys_label"), 1, 20, 2, key="bulk_min_buys")
        with c2:
            bulk_range_days = st.slider(t("range_days_label"), 20, 30, 25, key="bulk_range_days")

        bulk_detect_clusters = st.checkbox(t("bulk_detect_clusters_label"), value=False, key="bulk_clusters")

        if st.button(t("bulk_run_btn"), type="primary", key="bulk_run"):
            results = []
            overall_progress = st.progress(0)

            for i, row in watchlist_df.iterrows():
                api_key = get_api_key_for(row["network"])
                label = row["label"] or row["token_address"][:12]
                overall_progress.progress(i / len(watchlist_df), text=t("bulk_progress", i=i + 1, n=len(watchlist_df), label=label))

                if not api_key:
                    results.append({
                        "network_name": row["network"], "token_address": row["token_address"],
                        "token_symbol": row["label"] or "", "score": 0, "verdict_code": "caution",
                        "wallet_count": 0, "error": t("no_api_key_for_network"),
                    })
                    continue

                with st.expander(t("log_expander", label=label, network=row["network"]), expanded=False):
                    res = analyze_token(
                        row["network"], row["token_address"], api_key,
                        bulk_start, bulk_end, bulk_min_buys, bulk_range_days,
                        bulk_detect_clusters, 10, verbose=False,
                    )
                    if res["error"]:
                        st.warning(res["error"])
                    else:
                        st.write(t("bulk_result_line", verdict=t(VERDICT_KEYS[res["verdict_code"]]), score=res["score"], n=res["wallet_count"]))
                results.append(res)

            overall_progress.empty()
            st.session_state["bulk_results"] = results

        if "bulk_results" in st.session_state:
            results = st.session_state["bulk_results"]
            alerts = [r for r in results if not r.get("error") and r["score"] >= SCORE_ALERT_THRESHOLD]

            if alerts:
                st.subheader(t("alerts_header", n=len(alerts)))
                for a in sorted(alerts, key=lambda x: -x["score"]):
                    st.success(t(
                        "alert_line",
                        symbol=a["token_symbol"] or a["token_address"][:12],
                        network=a["network_name"], score=a["score"], n=a["wallet_count"],
                    ))
            else:
                st.info(t("no_alerts"))

            st.divider()
            st.subheader(t("bulk_summary_header"))
            summary_rows = [
                {
                    t("bulk_col_network"): r["network_name"],
                    t("bulk_col_token"): r.get("token_symbol") or r["token_address"][:12],
                    t("bulk_col_address"): r["token_address"],
                    t("bulk_col_verdict"): t(VERDICT_KEYS.get(r.get("verdict_code"), "verdict_caution")),
                    "Score": r.get("score", 0),
                    t("bulk_col_wallets"): r.get("wallet_count", 0),
                    t("bulk_col_note"): r.get("error") or "",
                }
                for r in results
            ]
            summary_df = pd.DataFrame(summary_rows).sort_values("Score", ascending=False)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            csv = summary_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(t("download_summary_btn"), csv, "bulk_scan_summary.csv", "text/csv", key="dl_summary")

# ---------------- Docs tab ----------------
with tab_docs:
    st.markdown(f"## {t('docs_title')}")
    st.markdown(t("docs_body"))