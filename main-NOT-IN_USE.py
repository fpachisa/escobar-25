import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pandas as pd
import numpy as np
import requests
import logging
import json
from typing import List, Dict, Optional, Tuple


OANDA_API_KEY = os.environ.get("OANDA_LIVE_API_KEY")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_LIVE_ACCOUNT_ID_3")
OANDA_URL = "https://api-fxtrade.oanda.com"
ENVIRONMENT = "live"


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class OandaTradeAnalyzer:
    def __init__(self, api_token: str, account_id: str, environment: str = ""):
        """
        Initialize OANDA API client
        
        Args:
            api_token: Your OANDA API token
            account_id: Your OANDA account ID
            environment: 'practice' for demo or 'trade' for live
            email_notifier: Optional EmailNotifier instance
        """
        self.api_token = api_token
        self.account_id = account_id
        
        # Set base URL based on environment

        self.base_url = "https://api-fxtrade.oanda.com"
        
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def get_all_open_trades(self) -> List[Dict]:
        """Get all open trades for the account"""
        url = f"{self.base_url}/v3/accounts/{self.account_id}/trades"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get('trades', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching trades: {e}")
            return []

    def display_trades(self) -> None:
        """Display formatted information about all open trades"""
        all_trades = self.get_all_open_trades()
        
        if not all_trades:
            print("No open trades found.")
            return
        
        print(f"Found {len(all_trades)} open trade(s):")
        print("-" * 80)
        
        for i, trade in enumerate(all_trades, 1):
            print(f"Trade #{i}")
            print(f"  Trade ID: {trade.get('id')}")
            print(f"  Instrument: {trade.get('instrument')}")
            print(f"  Units: {trade.get('currentUnits')}")
            print(f"  Open Price: {trade.get('price')}")
            print(f"  Current P&L: {trade.get('unrealizedPL')} {trade.get('instrument', '')[-3:]}")
            print("-" * 40)


class DirectionChange:
    def __init__(self, api_token: str, account_id: str, symbol: str):
        """Initialize OANDA API client for signal analysis"""
        self.api_token = api_token
        self.account_id = account_id
        self.symbol = symbol
        
        self.base_url = "https://api-fxtrade.oanda.com"
        
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    def fetch_historical_data(self, granularity: str, count: int = 100) -> pd.DataFrame:
        """Fetch historical candle data for a specified symbol and granularity"""
        url = f"{self.base_url}/v3/instruments/{self.symbol}/candles"
        params = {
            "count": count,
            "granularity": granularity,
            "price": "M"
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
    
            candles = response.json().get('candles', [])
            if not candles:
                logger.warning(f"No candle data found for {self.symbol}")
                return pd.DataFrame()
                
            data = {
                'time': [candle['time'] for candle in candles],
                'open_price': [float(candle['mid']['o']) for candle in candles],
                'high_price': [float(candle['mid']['h']) for candle in candles],
                'low_price': [float(candle['mid']['l']) for candle in candles],
                'close_price': [float(candle['mid']['c']) for candle in candles]
            }
            return pd.DataFrame(data)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching historical data for {self.symbol}: {e}")
            return pd.DataFrame()
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Error parsing data for {self.symbol}: {e}")
            return pd.DataFrame()

    def calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average (EMA) for given prices"""
        try:
            if data.empty:
                return pd.Series()
            return data.ewm(span=period, adjust=False).mean()
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return pd.Series()

    def calculate_ema_gradient(self, df: pd.DataFrame) -> None:
        """Calculate EMA gradient and related metrics"""
        try:
            if df.empty or 'ema_short' not in df.columns:
                logger.warning("Cannot calculate EMA gradient: missing data or EMA column")
                return
            
            # Calculate RTM (Return to Mean)
            df['RTM'] = (-10000 * (df['ema_short'] - df['close_price']) / df['ema_short']).astype(int)
            
            # Calculate EMA gradient
            if "JPY" in self.symbol:
                df['ema_gradient'] = df['ema_short'].diff() * 100
            else:
                df['ema_gradient'] = df['ema_short'].diff()
                max_gradient = df['ema_gradient'].abs().max()
                if max_gradient > 0:  # Avoid division by zero
                    df['ema_gradient'] = (df['ema_gradient'] / max_gradient) * 10
            
            # Calculate angles
            df['angle_radians'] = np.arctan(df['ema_gradient'])
            df['angle_degrees'] = np.degrees(df['angle_radians'])
            
        except Exception as e:
            logger.error(f"Error calculating EMA gradient: {e}")


def analyze_rtm_trend(symbol: str, trade_direction: str) -> Dict:
    """
    Analyze RTM trend for a given symbol - now returns data regardless of trend
    
    Args:
        symbol: Trading instrument symbol
        trade_direction: "Long" or "Short"
        
    Returns:
        Dictionary containing RTM analysis results
    """
    try:
        signal_generator = DirectionChange(OANDA_API_KEY, OANDA_ACCOUNT_ID, symbol)
        four_hourly_data = signal_generator.fetch_historical_data("H4", 100)
        
        if four_hourly_data.empty:
            logger.warning(f"No historical data available for {symbol}")
            return {
                "alert_needed": False, 
                "reason": "No data available",
                "rtm_values": [],
                "trend_description": "No data",
                "trade_direction": trade_direction
            }
        
        # Calculate EMA
        four_hourly_data['ema_short'] = signal_generator.calculate_ema(four_hourly_data['close_price'], 20)
        
        if four_hourly_data['ema_short'].empty:
            logger.warning(f"EMA calculation failed for {symbol}")
            return {
                "alert_needed": False, 
                "reason": "EMA calculation failed",
                "rtm_values": [],
                "trend_description": "EMA failed",
                "trade_direction": trade_direction
            }
        
        # Calculate gradient
        signal_generator.calculate_ema_gradient(four_hourly_data)
        
        if 'RTM' not in four_hourly_data.columns or len(four_hourly_data) < 3:
            logger.warning(f"Insufficient data for RTM analysis for {symbol}")
            return {
                "alert_needed": False, 
                "reason": "Insufficient RTM data",
                "rtm_values": [],
                "trend_description": "Insufficient data",
                "trade_direction": trade_direction
            }
        
        # Get last 3 RTM values
        rtm_values = four_hourly_data['RTM'].iloc[-3:].values.tolist()
        
        # Check RTM trend patterns
        is_rtm_decreasing = (rtm_values[1] <= rtm_values[0]) and (rtm_values[2] <= rtm_values[1])
        is_rtm_increasing = (rtm_values[1] >= rtm_values[0]) and (rtm_values[2] >= rtm_values[1])
        
        alert_needed = False
        alert_reason = ""
        trend_description = ""
        
        if trade_direction == "Long":
            # For long trades: Alert if RTM is negative AND decreasing
            if all(rtm <= 0 for rtm in rtm_values) and is_rtm_decreasing:
                alert_needed = True
                alert_reason = "Long position: RTM negative and decreasing (moving further from EMA)"
                trend_description = "RTM negative and decreasing"
        
        elif trade_direction == "Short":
            # For short trades: Alert if RTM is positive AND increasing
            if all(rtm >= 0 for rtm in rtm_values) and is_rtm_increasing:
                alert_needed = True
                alert_reason = "Short position: RTM positive and increasing (moving further from EMA)"
                trend_description = "RTM positive and increasing"
        
        if not trend_description:
            if is_rtm_increasing:
                trend_description = "RTM increasing"
            elif is_rtm_decreasing:
                trend_description = "RTM decreasing"
            else:
                trend_description = "RTM mixed/sideways"
        
        return {
            "alert_needed": alert_needed,
            "alert_reason": alert_reason,
            "rtm_values": rtm_values,
            "trend_description": trend_description,
            "trade_direction": trade_direction,
            "is_decreasing": is_rtm_decreasing,
            "is_increasing": is_rtm_increasing
        }
            
    except Exception as e:
        logger.error(f"Error analyzing RTM trend for {symbol}: {e}")
        return {
            "alert_needed": False, 
            "reason": f"Analysis error: {str(e)}",
            "rtm_values": [],
            "trend_description": "Analysis error",
            "trade_direction": trade_direction
        }


def rtm_alert_monitor(request):
    """Main execution function for RTM trend monitoring - sends single summary email"""
    try:
        # Validate environment variables
        if not all([OANDA_API_KEY, OANDA_ACCOUNT_ID):
            logger.error("Missing required environment variables")
            print("❌ Missing required environment variables")
            return False
        
        print("🔍 Starting RTM Alert Monitor...")
        print(f"Environment: {ENVIRONMENT}")
        
        
        # Initialize the analyzer with email notifications
        analyzer = OandaTradeAnalyzer(OANDA_API_KEY, OANDA_ACCOUNT_ID, ENVIRONMENT, email_notifier)
        
        # Display all trades
        print("\n=== All Open Trades ===")
        analyzer.display_trades()
        
        # Get trades for RTM analysis
        open_trades = analyzer.get_all_open_trades()
        
        if not open_trades:
            print("No open trades found to monitor.")
            return "No open trades found", 200
        
        # Collect all trade data for single email
        all_trades_data = []
        
        # Analyze each trade for RTM data
        for trade in open_trades:
            try:
                symbol = trade.get('instrument')
                trade_id = trade.get('id')
                current_units = trade.get('currentUnits')
                
                if not all([symbol, trade_id, current_units]):
                    logger.warning(f"Incomplete trade data for trade {trade_id}")
                    continue
                
                # Determine trade direction
                trade_direction = "Long" if float(current_units) > 0 else "Short"
                
                print(f"\n=== Analyzing Trade {trade_id} ===")
                print(f"Symbol: {symbol}")
                print(f"Trade Direction: {trade_direction}")
                print(f"Units: {current_units}")
                
                # Analyze RTM trend
                rtm_analysis = analyze_rtm_trend(symbol, trade_direction)
                
                # Add to collection for email (regardless of alert status)
                all_trades_data.append({
                    'trade_details': trade,
                    'rtm_analysis': rtm_analysis
                })
                
                if rtm_analysis.get("alert_needed", False):
                    print(f"🚨 RTM ALERT CONDITION DETECTED!")
                    print(f"Reason: {rtm_analysis.get('alert_reason')}")
                else:
                    print(f"✅ No RTM alert condition")
                
                print(f"RTM Values: {rtm_analysis.get('rtm_values', 'N/A')}")
                print(f"Trend: {rtm_analysis.get('trend_description', 'N/A')}")
                if rtm_analysis.get('reason'):
                    print(f"Reason: {rtm_analysis.get('reason')}")
                
                print("-" * 50)
                
            except Exception as e:
                logger.error(f"Error processing trade {trade.get('id', 'unknown')}: {e}")
                print(f"❌ Error processing trade {trade.get('id', 'unknown')}: {e}")
                continue
        
        # Send single summary email with all trades
        if all_trades_data:
            print(f"\n📧 Sending RTM summary email for {len(all_trades_data)} trade(s)...")
            success = email_notifier.send_rtm_summary_notification(all_trades_data)
            
            if success:
                result_message = f'RTM summary email sent successfully for {len(all_trades_data)} trade(s).'
                print(f"✅ {result_message}")
                return result_message, 200
            else:
                result_message = f'Failed to send RTM summary email for {len(all_trades_data)} trade(s).'
                print(f"❌ {result_message}")
                return result_message, 500
        else:
            result_message = 'No valid trade data found for RTM analysis.'
            print(f"❌ {result_message}")
            return result_message, 200
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        print(f"❌ RTM monitoring failed: {str(e)}")
        return f'RTM monitoring failed: {str(e)}', 500