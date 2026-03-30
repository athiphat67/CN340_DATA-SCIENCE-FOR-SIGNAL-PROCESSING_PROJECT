#!/usr/bin/env python3
"""
CLI Entry Point for Thai Gold Signal Backtest
Usage: python run_backtest_signal.py --timeframe 1h --days 30 --providers gemini,groq
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path if needed
sys.path.insert(0, str(Path(__file__).parent))

from backtest_signal_only import run_backtest


def main():
    parser = argparse.ArgumentParser(
        description='Thai Gold Signal Accuracy Backtest',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Test 1H timeframe for last 30 days (all providers)
  python run_backtest_signal.py --timeframe 1h --days 30
  
  # Test 4H timeframe for last 90 days (Gemini vs Groq only)
  python run_backtest_signal.py --timeframe 4h --days 90 --providers gemini,groq
  
  # Test with custom output filename
  python run_backtest_signal.py --timeframe 1h --days 15 --output my_backtest.csv
        '''
    )
    
    parser.add_argument(
        '--csv',
        type=str,
        default='data_XAU_THB/thai_gold_1m_dataset.csv',
        help='Path to CSV file (default: data_XAU_THB/thai_gold_1m_dataset.csv)'
    )
    
    parser.add_argument(
        '--timeframe',
        choices=['1h', '4h'],
        default='1h',
        help='Timeframe for candles (default: 1h)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        choices=[15, 30, 90],
        default=30,
        help='Number of days to backtest (default: 30)'
    )
    
    parser.add_argument(
        '--providers',
        type=str,
        default='gemini,groq,buy_hold,random,ma_crossover',
        help='Comma-separated list of providers (default: gemini,groq,buy_hold,random,ma_crossover)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='backtest_results',
        help='Output directory for results (default: backtest_results)'
    )
    
    parser.add_argument(
        '--filename',
        type=str,
        default=None,
        help='Custom output filename (auto-generated if not provided)'
    )
    
    args = parser.parse_args()
    
    # Parse providers
    providers = [p.strip() for p in args.providers.split(',')]
    
    print("\n" + "="*70)
    print("  THAI GOLD SIGNAL ACCURACY BACKTEST")
    print("="*70)
    print(f"CSV Source:    {args.csv}")
    print(f"Timeframe:     {args.timeframe}")
    print(f"Days:          {args.days}")
    print(f"Providers:     {', '.join(providers)}")
    print(f"Output Dir:    {args.output_dir}")
    print("="*70 + "\n")
    
    try:
        # Run backtest
        metrics = run_backtest(
            csv_path=args.csv,
            timeframe=args.timeframe,
            days=args.days,
            providers=providers,
            output_dir=args.output_dir,
            filename=args.filename
        )
        
        # Print summary
        print("\n" + "="*70)
        print("  RESULTS SUMMARY")
        print("="*70)
        
        for provider, metrics_dict in metrics.items():
            print(f"\n{provider.upper()}:")
            for key, value in metrics_dict.items():
                # Format key
                key_formatted = key.replace('_', ' ').title()
                print(f"  {key_formatted:<30} {value}")
        
        print("\n" + "="*70)
        print("✓ Backtest completed successfully!")
        print("="*70 + "\n")
        
        return 0
    
    except FileNotFoundError as e:
        print(f"\n✗ ERROR: File not found")
        print(f"  {str(e)}")
        print(f"\nMake sure CSV file exists at: {args.csv}")
        return 1
    
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
