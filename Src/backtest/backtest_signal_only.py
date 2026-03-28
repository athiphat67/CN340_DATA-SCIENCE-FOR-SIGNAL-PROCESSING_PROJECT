"""
Thai Gold Backtest Engine (Signal Accuracy Only)
Timeframe: 1H, 4H
Metrics: Directional Accuracy, Signal Sensitivity, Net Profit/Loss with costs
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SPREAD_THB = 30  # Bid/Ask spread in THB
COMMISSION_THB = 3  # ออม NOW commission per trade
RISK_FREE_RATE = 0.01  # 1% per annum


class SignalOnlyBacktest:
    """
    Signal accuracy backtest for Thai Gold (ออม NOW)
    Validates signals against actual next candle direction
    Includes cost of trade (spread + commission) in calculations
    """
    
    def __init__(
        self, 
        csv_path: str = 'Src/backtest/data_XAU_THB/thai_gold_1m_dataset.csv',
        spread_thb: float = SPREAD_THB,
        commission_thb: float = COMMISSION_THB
    ):
        self.csv_path = csv_path
        self.spread_thb = spread_thb
        self.commission_thb = commission_thb
        self.df = None
        self.agg_df = None
        self.results = {}
        
        logger.info(f"Initialized backtest with CSV: {csv_path}")
        logger.info(f"Spread: {spread_thb} THB, Commission: {commission_thb} THB")
    
    def load_csv(self) -> pd.DataFrame:
        """Load 1-minute Thai gold data from CSV"""
        try:
            self.df = pd.read_csv(self.csv_path)
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
            self.df = self.df.sort_values('timestamp').reset_index(drop=True)
            
            logger.info(f"✓ Loaded {len(self.df)} rows from {self.csv_path}")
            logger.info(f"  Date range: {self.df['timestamp'].min()} to {self.df['timestamp'].max()}")
            logger.info(f"  Columns: {', '.join(self.df.columns.tolist())}")
            
            return self.df
        except FileNotFoundError:
            logger.error(f"✗ File not found: {self.csv_path}")
            raise
        except Exception as e:
            logger.error(f"✗ Error loading CSV: {str(e)}")
            raise
    
    def aggregate_candles(self, timeframe: str = '1h', days: int = 30) -> pd.DataFrame:
        """
        Aggregate 1-minute data to 1H or 4H candles
        
        Args:
            timeframe: '1h' or '4h'
            days: Number of days to look back (30 = 30 days ago)
        
        Returns:
            Aggregated OHLC DataFrame
        """
        if self.df is None:
            self.load_csv()
        
        # Filter by days
        cutoff_date = self.df['timestamp'].max() - timedelta(days=days)
        df_filtered = self.df[self.df['timestamp'] >= cutoff_date].copy()
        
        logger.info(f"Filtering last {days} days: {cutoff_date} to {df_filtered['timestamp'].max()}")
        
        # Set timestamp as index
        df_filtered = df_filtered.set_index('timestamp')
        
        # Aggregate based on timeframe
        if timeframe == '1h':
            freq = '1h'  # lowercase for newer pandas
        elif timeframe == '4h':
            freq = '4h'  # lowercase for newer pandas
        else:
            raise ValueError("Timeframe must be '1h' or '4h'")
        
        # OHLC aggregation
        agg_dict = {
            'open_thai': 'first',
            'high_thai': 'max',
            'low_thai': 'min',
            'close_thai': 'last',
            'gold_spot_usd': 'mean',
            'usd_thb_rate': 'mean'
        }
        
        self.agg_df = df_filtered.resample(freq).agg(agg_dict).dropna()
        self.agg_df = self.agg_df.reset_index()
        
        logger.info(f"✓ Aggregated to {timeframe}: {len(self.agg_df)} candles")
        logger.info(f"  Date range: {self.agg_df['timestamp'].min()} to {self.agg_df['timestamp'].max()}")
        
        return self.agg_df
    
    def generate_signals(self, providers: List[str] = None) -> pd.DataFrame:
        """
        Generate signals for each candle (mock implementation)
        Providers: 'gemini', 'groq', 'buy_hold', 'random', 'ma_crossover'
        
        Args:
            providers: List of provider names
        
        Returns:
            DataFrame with signals
        """
        if self.agg_df is None or len(self.agg_df) == 0:
            raise ValueError("Must aggregate candles first")
        
        if providers is None:
            providers = ['gemini', 'groq', 'buy_hold', 'random', 'ma_crossover']
        
        df = self.agg_df.copy()
        
        # Calculate technical indicators
        df['ema_20'] = df['close_thai'].ewm(span=20).mean()
        df['ema_50'] = df['close_thai'].ewm(span=50).mean()
        df['rsi'] = self._calculate_rsi(df['close_thai'])
        
        logger.info(f"Generating signals for {len(df)} candles...")
        
        # Generate signals for each provider
        for provider in providers:
            logger.info(f"  → {provider}...")
            
            if provider == 'gemini':
                df[f'{provider}_signal'], df[f'{provider}_confidence'] = self._mock_signal_gemini(df)
            elif provider == 'groq':
                df[f'{provider}_signal'], df[f'{provider}_confidence'] = self._mock_signal_groq(df)
            elif provider == 'buy_hold':
                df[f'{provider}_signal'], df[f'{provider}_confidence'] = self._mock_signal_buy_hold(df)
            elif provider == 'random':
                df[f'{provider}_signal'], df[f'{provider}_confidence'] = self._mock_signal_random(df)
            elif provider == 'ma_crossover':
                df[f'{provider}_signal'], df[f'{provider}_confidence'] = self._mock_signal_ma_crossover(df)
        
        self.agg_df = df
        logger.info(f"✓ Signals generated")
        
        return self.agg_df
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _mock_signal_gemini(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Mock Gemini signal generation"""
        signals = []
        confidences = []
        
        for idx, row in df.iterrows():
            rsi = row['rsi']
            ema_ratio = row['ema_20'] / row['ema_50'] if row['ema_50'] > 0 else 1.0
            
            if pd.isna(rsi):
                signals.append('HOLD')
                confidences.append(0.5)
            elif rsi > 70 and ema_ratio > 1.02:
                signals.append('SELL')
                confidences.append(min(0.9, (rsi - 70) / 30))
            elif rsi < 30 and ema_ratio < 0.98:
                signals.append('BUY')
                confidences.append(min(0.9, (30 - rsi) / 30))
            elif ema_ratio > 1.01:
                signals.append('BUY')
                confidences.append(0.65)
            elif ema_ratio < 0.99:
                signals.append('SELL')
                confidences.append(0.65)
            else:
                signals.append('HOLD')
                confidences.append(0.5)
        
        return pd.Series(signals), pd.Series(confidences)
    
    def _mock_signal_groq(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Mock Groq signal generation (more conservative)"""
        signals = []
        confidences = []
        
        for idx, row in df.iterrows():
            rsi = row['rsi']
            ema_ratio = row['ema_20'] / row['ema_50'] if row['ema_50'] > 0 else 1.0
            
            if pd.isna(rsi):
                signals.append('HOLD')
                confidences.append(0.5)
            elif rsi > 75 and ema_ratio > 1.03:
                signals.append('SELL')
                confidences.append(0.8)
            elif rsi < 25 and ema_ratio < 0.97:
                signals.append('BUY')
                confidences.append(0.8)
            else:
                signals.append('HOLD')
                confidences.append(0.5)
        
        return pd.Series(signals), pd.Series(confidences)
    
    def _mock_signal_buy_hold(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Buy & Hold baseline: BUY at first, then HOLD"""
        signals = []
        confidences = []
        
        for idx in range(len(df)):
            if idx == 0:
                signals.append('BUY')
                confidences.append(1.0)
            else:
                signals.append('HOLD')
                confidences.append(1.0)
        
        return pd.Series(signals), pd.Series(confidences)
    
    def _mock_signal_random(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Random baseline: 33% BUY, 33% SELL, 33% HOLD"""
        np.random.seed(42)
        choices = np.random.choice(['BUY', 'SELL', 'HOLD'], size=len(df))
        confidences = np.random.uniform(0.3, 0.7, size=len(df))
        
        return pd.Series(choices), pd.Series(confidences)
    
    def _mock_signal_ma_crossover(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """MA Crossover baseline: EMA20 > EMA50 = BUY, else SELL"""
        signals = []
        confidences = []
        
        for idx, row in df.iterrows():
            ema_20 = row['ema_20']
            ema_50 = row['ema_50']
            
            if pd.isna(ema_20) or pd.isna(ema_50):
                signals.append('HOLD')
                confidences.append(0.5)
            elif ema_20 > ema_50:
                signals.append('BUY')
                confidences.append(0.7)
            else:
                signals.append('SELL')
                confidences.append(0.7)
        
        return pd.Series(signals), pd.Series(confidences)
    
    def validate_signals(self, validation_horizon: int = 1) -> pd.DataFrame:
        """
        Validate signals against next candle direction
        
        Args:
            validation_horizon: Number of candles ahead to check (1 = next candle)
        
        Returns:
            DataFrame with validation results
        """
        df = self.agg_df.copy()
        providers = [col.replace('_signal', '') for col in df.columns if col.endswith('_signal')]
        
        logger.info(f"Validating signals with {validation_horizon} candle(s) horizon...")
        
        # Calculate next candle direction
        df['next_close'] = df['close_thai'].shift(-validation_horizon)
        df['price_change'] = df['next_close'] - df['close_thai']
        df['actual_direction'] = df['price_change'].apply(lambda x: 'UP' if x > 0 else ('DOWN' if x < 0 else 'FLAT'))
        
        # Calculate net profit/loss including costs
        # Net = Price Change - Spread - Commission
        df['gross_move_thb'] = df['price_change']
        total_cost = self.spread_thb + self.commission_thb
        df['net_profit_loss'] = df['gross_move_thb'] - total_cost
        
        # Validate each provider's signals
        for provider in providers:
            signal_col = f'{provider}_signal'
            correct_col = f'{provider}_correct'
            profitable_col = f'{provider}_profitable'
            
            # Check if signal matches actual direction
            df[correct_col] = df.apply(
                lambda row: self._check_signal_correct(row[signal_col], row['actual_direction']),
                axis=1
            )
            
            # Check if it would be profitable (after costs)
            df[profitable_col] = (df[correct_col]) & (df['net_profit_loss'] > 0)
        
        self.agg_df = df
        logger.info(f"✓ Signals validated")
        
        return self.agg_df
    
    def _check_signal_correct(self, signal: str, actual_direction: str) -> bool:
        """Check if signal matches actual direction"""
        if signal == 'HOLD':
            return actual_direction == 'FLAT'
        elif signal == 'BUY':
            return actual_direction == 'UP'
        elif signal == 'SELL':
            return actual_direction == 'DOWN'
        return False
    
    def calculate_metrics(self) -> Dict:
        """
        Calculate backtest metrics for all providers
        
        Returns:
            Dictionary with metrics per provider
        """
        df = self.agg_df.copy()
        providers = [col.replace('_signal', '') for col in df.columns if col.endswith('_signal')]
        
        logger.info(f"Calculating metrics for {len(providers)} providers...")
        
        metrics = {}
        
        for provider in providers:
            signal_col = f'{provider}_signal'
            correct_col = f'{provider}_correct'
            profitable_col = f'{provider}_profitable'
            confidence_col = f'{provider}_confidence'
            
            # Count signals
            total_signals = len(df[df[signal_col] != 'HOLD'])
            active_signals = df[df[signal_col] != 'HOLD']
            
            if len(active_signals) == 0:
                logger.warning(f"  {provider}: No active signals (all HOLD)")
                metrics[provider] = {
                    'directional_accuracy_pct': 0.0,
                    'signal_sensitivity_pct': 0.0,
                    'total_signals': 0,
                    'correct_signals': 0,
                    'correct_profitable': 0,
                    'avg_confidence': 0.0,
                    'avg_net_pnl_thb': 0.0
                }
                continue
            
            # Directional Accuracy
            correct_count = active_signals[correct_col].sum()
            directional_accuracy = (correct_count / len(active_signals)) * 100
            
            # Signal Sensitivity (BUY+SELL out of total candles)
            signal_sensitivity = (len(active_signals) / len(df)) * 100
            
            # Profitable signals (correct AND > 0 PnL)
            if profitable_col in df.columns:
                profitable_count = active_signals[profitable_col].sum()
            else:
                profitable_count = 0
            
            # Average confidence
            avg_confidence = active_signals[confidence_col].mean()
            
            # Average net P&L when correct
            correct_signals_df = active_signals[active_signals[correct_col]]
            if len(correct_signals_df) > 0:
                avg_net_pnl = correct_signals_df['net_profit_loss'].mean()
            else:
                avg_net_pnl = 0.0
            
            metrics[provider] = {
                'directional_accuracy_pct': round(directional_accuracy, 2),
                'signal_sensitivity_pct': round(signal_sensitivity, 2),
                'total_signals': len(active_signals),
                'correct_signals': int(correct_count),
                'correct_profitable': int(profitable_count),
                'avg_confidence': round(avg_confidence, 3),
                'avg_net_pnl_thb': round(avg_net_pnl, 2)
            }
            
            logger.info(
                f"  {provider}: "
                f"Accuracy={directional_accuracy:.1f}%, "
                f"Sensitivity={signal_sensitivity:.1f}%, "
                f"Signals={len(active_signals)}, "
                f"Correct={correct_count}, "
                f"Avg_PnL={avg_net_pnl:.1f} THB"
            )
        
        self.results = metrics
        return metrics
    
    def export_csv(
        self, 
        output_dir: str = 'backtest_results',
        filename: str = None,
        include_signal_log: bool = True
    ) -> str:
        """
        Export backtest results to CSV
        
        Args:
            output_dir: Output directory
            filename: Custom filename (auto-generated if None)
            include_signal_log: Include detailed signal log
        
        Returns:
            Path to exported file
        """
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        if filename is None:
            timeframe = '1h'  # Detect from data
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'backtest_signal_only_{timeframe}_{timestamp}.csv'
        
        filepath = os.path.join(output_dir, filename)
        
        df = self.agg_df.copy()
        providers = [col.replace('_signal', '') for col in df.columns if col.endswith('_signal')]
        
        # Build summary metrics
        summary_data = []
        for provider in providers:
            if provider in self.results:
                row = {'metric': provider}
                row.update(self.results[provider])
                summary_data.append(row)
        
        summary_df = pd.DataFrame(summary_data)
        
        # Build detailed signal log
        signal_log_cols = ['timestamp', 'close_thai', 'actual_direction', 'price_change', 'net_profit_loss']
        for provider in providers:
            signal_log_cols.extend([
                f'{provider}_signal',
                f'{provider}_confidence',
                f'{provider}_correct',
                f'{provider}_profitable'
            ])
        
        signal_log_df = df[signal_log_cols].copy()
        
        # Write to CSV with two sections
        with open(filepath, 'w', encoding='utf-8-sig') as f:
            # Summary section
            f.write("=== SUMMARY METRICS ===\n")
            summary_df.to_csv(f, index=False)
            f.write("\n\n")
            
            # Signal log section
            if include_signal_log:
                f.write("=== DETAILED SIGNAL LOG ===\n")
                signal_log_df.to_csv(f, index=False)
        
        logger.info(f"✓ Results exported to {filepath}")
        logger.info(f"  Summary rows: {len(summary_df)}")
        logger.info(f"  Signal log rows: {len(signal_log_df)}")
        
        return filepath


def run_backtest(
    csv_path: str = 'Src/backtest/data_XAU_THB/thai_gold_1m_dataset.csv',
    timeframe: str = '1h',
    days: int = 30,
    providers: List[str] = None,
    output_dir: str = 'backtest_results',
    filename: str = None
) -> Dict:
    """
    Run complete backtest pipeline
    
    Args:
        csv_path: Path to CSV file
        timeframe: '1h' or '4h'
        days: Number of days to backtest (30 = default)
        providers: List of providers to test
        output_dir: Output directory for results
        filename: Output filename
    
    Returns:
        Metrics dictionary
    """
    # Initialize
    backtest = SignalOnlyBacktest(csv_path)
    
    # Run pipeline
    backtest.load_csv()
    backtest.aggregate_candles(timeframe=timeframe, days=days)
    backtest.generate_signals(providers=providers)
    backtest.validate_signals(validation_horizon=1)
    metrics = backtest.calculate_metrics()
    
    # Export
    filepath = backtest.export_csv(output_dir=output_dir, filename=filename)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"BACKTEST COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Timeframe: {timeframe}")
    logger.info(f"Days: {days}")
    logger.info(f"Results: {filepath}")
    
    return metrics


if __name__ == '__main__':
    # Example usage
    metrics = run_backtest(
        csv_path='Src/backtest/data_XAU_THB/thai_gold_1m_dataset.csv',
        timeframe='1h',
        days=30,
        providers=['gemini', 'groq', 'buy_hold', 'random', 'ma_crossover'],
        output_dir='backtest_results'
    )
    
    print("\n✓ Backtest completed!")
