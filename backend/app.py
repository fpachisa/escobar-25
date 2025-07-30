from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
import json
import os
import logging
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="RTM Monitor API", version="1.0.0")

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Environment variables
OANDA_API_KEY = os.environ.get("OANDA_LIVE_API_KEY")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_LIVE_ACCOUNT_ID_3")
OANDA_URL = "https://api-fxtrade.oanda.com"

# Response models - using dict instead of Pydantic for simplicity
# class RTMData(BaseModel):
#     instrument: str
#     rtm_values: List[int]
#     last_updated: str
#     error: Optional[str] = None

# class RTMResponse(BaseModel):
#     category: str
#     data: List[RTMData]
#     total_instruments: int

# Load symbols from JSON
def load_symbols():
    try:
        with open('symbol.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("symbol.json not found")
        return {"currencies": [], "indices": [], "commodities": []}

class DirectionChange:
    def __init__(self, api_token: str, symbol: str):
        """Initialize OANDA API client for signal analysis"""
        self.api_token = api_token
        self.symbol = symbol
        
        self.base_url = OANDA_URL
        
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

def calculate_rtm_values_for_symbol(symbol: str) -> List[int]:
    """Calculate last 6 RTM values for a symbol using original logic"""
    try:
        signal_generator = DirectionChange(OANDA_API_KEY, symbol)
        four_hourly_data = signal_generator.fetch_historical_data("H4", 100)
        
        if four_hourly_data.empty:
            logger.warning(f"No historical data available for {symbol}")
            return []
        
        # Calculate EMA using original logic
        four_hourly_data['ema_short'] = signal_generator.calculate_ema(four_hourly_data['close_price'], 20)
        
        if four_hourly_data['ema_short'].empty:
            logger.warning(f"EMA calculation failed for {symbol}")
            return []
        
        # Calculate gradient and RTM using original logic
        signal_generator.calculate_ema_gradient(four_hourly_data)
        
        if 'RTM' not in four_hourly_data.columns or len(four_hourly_data) < 6:
            logger.warning(f"Insufficient data for RTM analysis for {symbol}")
            return []
        
        # Get last 6 RTM values
        rtm_values = four_hourly_data['RTM'].iloc[-6:].values.tolist()
        return rtm_values
        
    except Exception as e:
        logger.error(f"Error calculating RTM for {symbol}: {e}")
        return []

def detect_direction_change(rtm_values: List[int]) -> bool:
    """
    Detect if there's a direction change in RTM values
    Returns True if last 2-3 RTMs have different signs from first 3-4 RTMs
    """
    if len(rtm_values) < 6:
        return False
    
    def get_sign(value):
        if value > 0:
            return 1
        elif value < 0:
            return -1
        else:
            return 0
    
    # Get signs of all RTM values
    signs = [get_sign(val) for val in rtm_values]
    
    # Debug logging
    logger.debug(f"RTM values: {rtm_values}")
    logger.debug(f"Signs: {signs}")
    
    # Check pattern 1: First 4 vs Last 2
    first_4_signs = signs[:4]
    last_2_signs = signs[4:]
    
    # Check if first 4 are predominantly one sign and last 2 are different sign
    first_4_positive = sum(1 for s in first_4_signs if s > 0)
    first_4_negative = sum(1 for s in first_4_signs if s < 0)
    
    last_2_positive = sum(1 for s in last_2_signs if s > 0)
    last_2_negative = sum(1 for s in last_2_signs if s < 0)
    
    # Pattern 1: First 4 predominantly positive, last 2 predominantly negative
    # Need at least 3 out of 4 positive AND at least 1 out of 2 negative
    if first_4_positive >= 3 and last_2_negative >= 1:
        logger.debug("Direction change detected - Pattern 1: First 4 positive, last 2 negative")
        return True
    
    # Pattern 1: First 4 predominantly negative, last 2 predominantly positive  
    # Need at least 3 out of 4 negative AND at least 1 out of 2 positive
    if first_4_negative >= 3 and last_2_positive >= 1:
        logger.debug("Direction change detected - Pattern 1: First 4 negative, last 2 positive")
        return True
    
    # Check pattern 2: First 3 vs Last 3
    first_3_signs = signs[:3]
    last_3_signs = signs[3:]
    
    first_3_positive = sum(1 for s in first_3_signs if s > 0)
    first_3_negative = sum(1 for s in first_3_signs if s < 0)
    
    last_3_positive = sum(1 for s in last_3_signs if s > 0)
    last_3_negative = sum(1 for s in last_3_signs if s < 0)
    
    # Pattern 2: First 3 predominantly positive, last 3 predominantly negative
    # Need at least 2 out of 3 positive AND at least 2 out of 3 negative
    if first_3_positive >= 2 and last_3_negative >= 2:
        logger.debug("Direction change detected - Pattern 2: First 3 positive, last 3 negative")
        return True
    
    # Pattern 2: First 3 predominantly negative, last 3 predominantly positive
    # Need at least 2 out of 3 negative AND at least 2 out of 3 positive
    if first_3_negative >= 2 and last_3_positive >= 2:
        logger.debug("Direction change detected - Pattern 2: First 3 negative, last 3 positive")
        return True
    
    return False

def sort_instruments_by_direction_change(rtm_data: List[Dict]) -> List[Dict]:
    """Sort instruments putting direction changes at the top"""
    direction_change_instruments = []
    normal_instruments = []
    
    for item in rtm_data:
        if detect_direction_change(item["rtm_values"]):
            direction_change_instruments.append(item)
        else:
            normal_instruments.append(item)
    
    # Sort direction change instruments by instrument name
    direction_change_instruments.sort(key=lambda x: x["instrument"])
    # Sort normal instruments by instrument name  
    normal_instruments.sort(key=lambda x: x["instrument"])
    
    # Return direction change instruments first, then normal ones
    return direction_change_instruments + normal_instruments

def get_open_positions() -> List[Dict]:
    """Get all open positions from OANDA using your original logic"""
    if not oanda_configured:
        return []
    
    url = f"{OANDA_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/openPositions"
    headers = {
        "Authorization": f"Bearer {OANDA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        return data.get('positions', [])
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching positions: {e}")
        return []

# Check if OANDA API is configured
oanda_configured = bool(OANDA_API_KEY and OANDA_ACCOUNT_ID)

@app.on_event("startup")
async def startup_event():
    global oanda_configured
    if not OANDA_API_KEY:
        logger.error("OANDA_API_KEY not found in environment variables")
        logger.error("Please set OANDA_LIVE_API_KEY and OANDA_LIVE_ACCOUNT_ID_3 environment variables")
        oanda_configured = False
    else:
        logger.info("OANDA API configured successfully")
        oanda_configured = True

@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "RTM Monitor API is running"}

@app.get("/api/rtm/currencies")
async def get_currencies_rtm():
    """Get RTM data for all currency pairs"""
    symbols = load_symbols()
    currencies = symbols.get("currencies", [])
    
    rtm_data = []
    for symbol in currencies:
        if oanda_configured:
            # Real data from OANDA using your original logic
            rtm_values = calculate_rtm_values_for_symbol(symbol)
            rtm_data.append({
                "instrument": symbol,
                "rtm_values": rtm_values if rtm_values else [0] * 6,
                "last_updated": datetime.now().isoformat(),
                "error": None if rtm_values else "Failed to fetch data"
            })
    
    # Sort instruments with direction changes at the top
    sorted_rtm_data = sort_instruments_by_direction_change(rtm_data)
    
    return {
        "category": "currencies",
        "data": sorted_rtm_data,
        "total_instruments": len(currencies)
    }

@app.get("/api/rtm/indices")
async def get_indices_rtm():
    """Get RTM data for all indices"""
    symbols = load_symbols()
    indices = symbols.get("indices", [])
    
    rtm_data = []
    for symbol in indices:
        if oanda_configured:
            # Real data from OANDA using your original logic
            rtm_values = calculate_rtm_values_for_symbol(symbol)
            rtm_data.append({
                "instrument": symbol,
                "rtm_values": rtm_values if rtm_values else [0] * 6,
                "last_updated": datetime.now().isoformat(),
                "error": None if rtm_values else "Failed to fetch data"
            })
    
    # Sort instruments with direction changes at the top
    sorted_rtm_data = sort_instruments_by_direction_change(rtm_data)
    
    return {
        "category": "indices",
        "data": sorted_rtm_data,
        "total_instruments": len(indices)
    }

@app.get("/api/rtm/commodities")
async def get_commodities_rtm():
    """Get RTM data for all commodities"""
    symbols = load_symbols()
    commodities = symbols.get("commodities", [])
    
    rtm_data = []
    for symbol in commodities:
        if oanda_configured:
            # Real data from OANDA using your original logic
            rtm_values = calculate_rtm_values_for_symbol(symbol)
            rtm_data.append({
                "instrument": symbol,
                "rtm_values": rtm_values if rtm_values else [0] * 6,
                "last_updated": datetime.now().isoformat(),
                "error": None if rtm_values else "Failed to fetch data"
            })
    
    # Sort instruments with direction changes at the top
    sorted_rtm_data = sort_instruments_by_direction_change(rtm_data)
    
    return {
        "category": "commodities",
        "data": sorted_rtm_data,
        "total_instruments": len(commodities)
    }

@app.get("/api/positions")
async def get_positions():
    """Get all open positions with RTM data"""
    if not oanda_configured:
        return {
            "category": "positions",
            "data": [],
            "total_positions": 0,
            "error": "OANDA API not configured"
        }
    
    open_positions = get_open_positions()
    
    if not open_positions:
        return {
            "category": "positions",
            "data": [],
            "total_positions": 0
        }
    
    positions_data = []
    
    for position in open_positions:
        logger.debug(f"Processing position: {position}")
        try:
            symbol = position.get('instrument')
            
            if not symbol:
                logger.warning(f"No instrument found in position data")
                continue
            
            # Get RTM values for this instrument
            rtm_values = calculate_rtm_values_for_symbol(symbol)
            
            # Check if we have long or short positions (or both)
            long_data = position.get('long', {})
            short_data = position.get('short', {})
            
            long_units = float(long_data.get('units', '0'))
            short_units = float(short_data.get('units', '0'))
            
            # Handle long position
            if long_units != 0:
                long_pnl = float(long_data.get('unrealizedPL', '0'))
                positions_data.append({
                    "instrument": symbol,
                    "direction": "Long",
                    "units": abs(long_units),
                    "unrealized_pnl": long_pnl,
                    "rtm_values": rtm_values if rtm_values else [0] * 6,
                    "last_updated": datetime.now().isoformat(),
                    "error": None if rtm_values else "Failed to fetch RTM data"
                })
            
            # Handle short position  
            if short_units != 0:
                short_pnl = float(short_data.get('unrealizedPL', '0'))
                positions_data.append({
                    "instrument": symbol,
                    "direction": "Short", 
                    "units": abs(short_units),
                    "unrealized_pnl": short_pnl,
                    "rtm_values": rtm_values if rtm_values else [0] * 6,
                    "last_updated": datetime.now().isoformat(),
                    "error": None if rtm_values else "Failed to fetch RTM data"
                })
            
            # If neither long nor short has units, log it
            if long_units == 0 and short_units == 0:
                logger.warning(f"No open units found for {symbol}")
            
        except Exception as e:
            logger.error(f"Error processing position for {position.get('instrument', 'unknown')}: {e}")
            continue
    
    # Sort positions with direction changes at the top
    sorted_positions = sort_instruments_by_direction_change(positions_data)
    
    return {
        "category": "positions",
        "data": sorted_positions,
        "total_positions": len(positions_data)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)