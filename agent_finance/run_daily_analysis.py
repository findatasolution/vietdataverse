"""
Daily Gold Analysis Runner
Wrapper script to be run by GitHub Actions daily
Generates gold market analysis and stores in database
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gold_analysis_agent import main

if __name__ == "__main__":
    print("Starting daily gold analysis...")
    success = main()

    if success:
        print("\n✅ Daily analysis completed successfully")
        sys.exit(0)
    else:
        print("\n❌ Daily analysis failed")
        sys.exit(1)