# 🔍 Wallet Accumulation Analyzer

نظام مراقبة متكامل لتحليل محافظ التجميع على البلوكتشين — يدعم شبكات EVM و Solana مع تحليل سوق، كشف بوتات، وتكتلات محافظ.

A complete on-chain wallet accumulation monitoring system — supports EVM chains & Solana with market analysis, bot detection, and wallet cluster (Sybil) identification.

[العربية](#العربية) | [English](#english)

---

<a name="english"></a>
## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Single Token Analysis** | Full detailed scan — market pulse, range analysis, top wallets table, Accumulation Score |
| 📋 **Watchlist** | Auto-discover tokens (trending / new / Binance gainers) or add manually — saved to local database |
| ⚡ **Bulk Analysis** | Run the same full scan across your entire watchlist in one click |
| 🔔 **Smart Alerts** | Instant alerts for tokens with a strong accumulation signal (Score >= 70) |
| 🌐 **Multi-Chain** | Ethereum, BSC, Polygon, Arbitrum, Base, Avalanche, Solana |
| 🌍 **Bilingual** | Full Arabic + English interface |
| 🔑 **API Key Storage** | Keys saved locally, reused automatically — one Etherscan key covers all EVM chains |
| 🆔 **User Isolation** | Every visitor gets an isolated workspace — zero data overlap between users |

---

## 🚀 Quick Start

### Local Run

```bash
# Clone the repository
git clone [https://github.com/Mohkadd98/wallet-accumulation-analyzer.git](https://github.com/Mohkadd98/Wallet-Accumulation-Analyzer.git)
cd wallet-accumulation-analyzer

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```



Your app will be live at `[here](https://wallet-accumulation-analyzer.streamlit.app/)`

---

## 📊 Accumulation Score (0–100)

A single score combining:

| Factor | Weight | Description |
|--------|--------|-------------|
| Accumulating wallets | +10 / +5 | Based on unique wallet count |
| Estimated bot ratio | -20 / -10 | Timing regularity + amount consistency |
| Wallet clusters | -20 / -10 | Same funding source detection |
| Momentum | +15 / -15 | Price + volume correlation |
| Range position | +10 / -10 | Current price within period high/low |
| Smart money | +10 / +5 | Wallets seen in other tokens before |

---

## 🗄️ User Isolation (Workspace System)

Every visitor automatically gets a **unique workspace ID**:

- Generated on first visit
- Stored in the URL (`?ws=abc123`) — survives page refreshes
- Fully isolated data: API keys, watchlist, and history are per-workspace
- Shareable: anyone with your workspace ID can view your data

**To switch workspaces:** Go to **⚙️ Settings** > **🔄 Switch Workspace** and enter a workspace ID.

---

## 🔑 API Keys

| Provider | Key Required | Free Tier |
|----------|-------------|-----------|
| [Etherscan V2](https://etherscan.io/apis) | All EVM chains | ✅ 5 calls/sec |
| [Helius](https://www.helius.dev) | Solana | ✅ Free tier |
| Dexscreener | Discovery & market data | ✅ No key needed |
| GeckoTerminal | Historical candles | ✅ No key needed |

---

## 📁 Project Structure

```
wallet-accumulation-analyzer/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── .gitignore         # Excludes local DB from git
├── README.md          # This file
└── wallet_memory.db   # Auto-created on first run (per-user data)
```

---

## ⚠️ Disclaimers

- **Not investment advice** — every number and label is a heuristic
- **Bot detection is a heuristic** — timing regularity + amount consistency only
- **API keys are stored locally** (unencrypted) — do not use on shared machines
- **Binance name-matching does not guarantee same project** — always verify the address

---

<a name="العربية"></a>
## 🇸🇦 بالعربية

### المميزات

| الميزة | الوصف |
|--------|-------|
| 🔍 تحليل فردي | فحص تفصيلي كامل — نبض السوق، Range، جدول المحافظ، Accumulation Score |
| 📋 قائمة المراقبة | اكتشاف تلقائي للعملات (رائجة/جديدة/أعلى ارتفاعاً) أو إضافة يدوية |
| ⚡ تحليل جماعي | تشغيل نفس الفحص الكامل على كل عملات القائمة بضغطة واحدة |
| 🔔 تنبيهات ذكية | تنبيهات فورية للعملات بإشارة تجميع قوية |
| 🌐 متعددة الشبكات | Ethereum, BSC, Polygon, Arbitrum, Base, Avalanche, Solana |
| 🌍 ثنائية اللغة | واجهة كاملة بالعربية والإنجليزية |
| 🆔 عزل المستخدمين | كل زائر يحصل على مساحة عمل معزولة تماماً |

### التشغيل المحلي

```bash
pip install -r requirements.txt
streamlit run app.py
```

