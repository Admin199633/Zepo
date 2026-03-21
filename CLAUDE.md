# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoSignalX-History is a cryptocurrency trading signal detection and backtesting system with a Streamlit-based Hebrew UI. It scans Binance for volatile coins, applies technical analysis strategies, checks TP/SL outcomes, and trains an ML model to predict signal quality.

## Commands

### Installation
```bash
pip install -r requirements.txt
pip install streamlit lightgbm scikit-learn
```

### Running the Full Pipeline
```bash
python main.py
```
This runs sequentially: scan → strategy signals → TP/SL check → launches Streamlit at `localhost:8501`.

### Running Individual Steps
```bash
python scan.py                  # Fetch volatile coins from Binance
python startagy_program.py      # Generate trading signals
python st_or_tp.py              # Backtest signals (TP/SL outcome)
streamlit run app.py            # Launch UI only
python ML/main.py               # Train/run ML pipeline
```

## Architecture

### Data Pipeline
```
Binance API → scan.py (volatile_symbols.txt)
           → startagy_program.py (strategy_signals_output.csv)
           → st_or_tp.py (strategy_signals_master.csv)
           → ML/main.py (LightGBM predictions)
           → Streamlit pages (visualization)
```

### Core Components

- **`config.py`** — Central config: date range, symbols, intervals, active strategies, SL/TP multipliers, indicator thresholds. Edit directly or via the Streamlit UI in `pages/6_Scan_coin.py`. `UI.py` performs regex-based edits to this file.
- **`scan.py`** — Multi-threaded Binance API scanner; filters coins by volume, volatility, and % change; outputs `logs/volatile_symbols.txt`.
- **`indector.py`** — Computes all technical indicators (RSI, MACD, ADX, EMA, Bollinger Bands, ATR, CCI, PSAR, VWAP, TRIX) via the `ta` library.
- **`startagy_program.py`** — Dynamically loads strategy modules via `importlib`, applies each to kline data, computes SL/TP using `SL = Entry − 1.5×ATR`, `TP = Entry + 3×ATR`.
- **`st_or_tp.py`** — Fetches 5m Binance candles after each signal to determine if TP or SL was hit first; enriches the master CSV with outcomes and PnL.

### Strategy System (`strategies/`)
Seven strategy modules: `strategy_rsi_macd`, `strategy_bollinger_macd`, `strategy_breakout_volume`, `strategy_breakout`, `strategy_candlestick`, `strategy_supertrend_macd`, `strategy_vwap_bounce`. Each returns `(score: int, reasons: List[str])`. Add a new strategy by creating a `.py` file here and adding its name to `ACTIVE_STRATEGIES` in `config.py`.

### ML Module (`ML/`)
- `data_loading.py` — Loads OHLCV candles from `data/historical_kline/{symbol}/{year}/{month}/{day}/{interval}/` disk cache.
- `feature_engineering.py` — Builds lag features, time features (hour, day-of-week) from signal history.
- `modeling.py` — LightGBM classifier; persists model to `ML/log/` and features to `ML/log/model_features.pkl`.

### Historical Data
Stored as daily CSV files: `data/historical_kline/{SYMBOL}/{YYYY}/{MM}/{DD}/{interval}/{filename}.csv`. This avoids loading all data into memory — code loads by date range.

### Output Files
| File | Description |
|------|-------------|
| `logs/volatile_symbols.txt` | Coins passing the scan filter |
| `strategy_signals_output.csv` | Raw signals with entry/SL/TP |
| `strategy_signals_master.csv` | Signals enriched with TP/SL outcomes |
| `model_performance_log.csv` | ML model metrics history |

### UI Notes
All user-facing text is in Hebrew. CSVs are saved with `encoding="utf-8-sig"` (BOM for Excel compatibility). The Streamlit pages are in `pages/` (numbered 6–8).
