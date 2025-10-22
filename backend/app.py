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
from google.cloud import storage
import io

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="RTM Monitor API", version="1.0.0")

# CORS middleware for frontend access (locked down by env var)
# Configure allowed origins via comma-separated env var ALLOWED_ORIGINS
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
if not allowed_origins:
    # Sensible dev default; override via ALLOWED_ORIGINS in production
    allowed_origins = ["http://localhost:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Environment variables
OANDA_API_KEY = os.environ.get("OANDA_LIVE_API_KEY")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_LIVE_ACCOUNT_ID_3")
OANDA_URL = "https://api-fxtrade.oanda.com"

# Google Cloud Storage configuration
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "escobar-analysis-data")
ANALYSIS_FILE_NAME = "Analysis.xlsx"

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

# Global variable to cache analysis data
_analysis_data_cache = None
_analysis_cache_timestamp = None

def load_analysis_data():
    """Load analysis data from Google Cloud Storage or local file with caching"""
    global _analysis_data_cache, _analysis_cache_timestamp
    
    try:
        # Try local file first for development
        local_file_path = 'Analysis.xlsx'
        if os.path.exists(local_file_path):
            logger.info("Loading analysis data from local file for development")
            
            # Check file modification time for caching
            file_stat = os.stat(local_file_path)
            file_updated = datetime.fromtimestamp(file_stat.st_mtime)
            
            if (_analysis_data_cache is None or 
                _analysis_cache_timestamp is None or 
                file_updated > _analysis_cache_timestamp):
                
                # Read local Excel file
                df = pd.read_excel(local_file_path)
                
                # Validate and process (same logic as GCS version)
                required_columns = ['Date', 'Instrument', 'Bias']
                if not all(col in df.columns for col in required_columns):
                    logger.error(f"Analysis file missing required columns: {required_columns}")
                    return {}
                
                # Get the latest date's data
                latest_date = df['Date'].max()
                latest_data = df[df['Date'] == latest_date]
                
                # Create instrument -> bias mapping
                bias_mapping = {}
                for _, row in latest_data.iterrows():
                    instrument = row['Instrument']
                    bias = row['Bias']
                    if bias in ['Up', 'Down', 'Hold']:
                        bias_mapping[instrument] = bias
                    else:
                        logger.warning(f"Invalid bias value '{bias}' for {instrument}")
                
                # Update cache
                _analysis_data_cache = bias_mapping
                _analysis_cache_timestamp = file_updated
                
                logger.info(f"Loaded {len(bias_mapping)} bias mappings from local analysis data")
                
            return _analysis_data_cache
        
        # Try GCS for production
        try:
            # Initialize GCS client
            client = storage.Client()
            bucket = client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(ANALYSIS_FILE_NAME)
            
            # Check if file exists
            if not blob.exists():
                logger.warning(f"Analysis file {ANALYSIS_FILE_NAME} not found in bucket {GCS_BUCKET_NAME}")
                return {}
            
            # Check if we need to refresh cache (file updated or cache empty)
            file_updated = blob.updated
            if (_analysis_data_cache is None or 
                _analysis_cache_timestamp is None or 
                file_updated > _analysis_cache_timestamp):
                
                logger.info(f"Loading analysis data from GCS bucket: {GCS_BUCKET_NAME}")
                
                # Download file content
                content = blob.download_as_bytes()
                
                # Read Excel file from bytes
                df = pd.read_excel(io.BytesIO(content))
                
                # Validate required columns
                required_columns = ['Date', 'Instrument', 'Bias']
                if not all(col in df.columns for col in required_columns):
                    logger.error(f"Analysis file missing required columns: {required_columns}")
                    return {}
                
                # Get the latest date's data (assuming sorted by date descending)
                latest_date = df['Date'].max()
                latest_data = df[df['Date'] == latest_date]
                
                # Create instrument -> bias mapping
                bias_mapping = {}
                for _, row in latest_data.iterrows():
                    instrument = row['Instrument']
                    bias = row['Bias']
                    if bias in ['Up', 'Down', 'Hold']:
                        bias_mapping[instrument] = bias
                    else:
                        logger.warning(f"Invalid bias value '{bias}' for {instrument}")
                
                # Update cache
                _analysis_data_cache = bias_mapping
                _analysis_cache_timestamp = file_updated
                
                logger.info(f"Loaded {len(bias_mapping)} bias mappings from GCS analysis data")
                
            return _analysis_data_cache
            
        except Exception as gcs_error:
            logger.warning(f"Could not load from GCS, falling back to empty bias data: {gcs_error}")
            return {}
        
    except Exception as e:
        logger.error(f"Error loading analysis data: {e}")
        return {}

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
            
            # ========================================
            # RTM (Return to Mean) Calculation - UPDATED
            # ========================================
            
            # PREVIOUS CALCULATION (commented out):
            # Original formula scaled percentage deviation by 10000 but resulted in 
            # inconsistent ranges across different instruments due to varying volatilities.
            # Different instruments (e.g., EUR/USD vs Gold vs Nikkei) would have completely
            # different RTM ranges, making cross-instrument comparison impossible.
            # df['RTM'] = (-10000 * (df['ema_short'] - df['close_price']) / df['ema_short']).astype(int)
            
            # NEW NORMALIZED CALCULATION:
            # Calculate raw RTM first (percentage deviation from EMA)
            df['RTM_raw'] = -100 * (df['ema_short'] - df['close_price']) / df['ema_short']
            
            # Normalize using rolling Z-score to ensure consistent -100 to +100 range across all instruments
            # Benefits of this approach:
            # 1. Cross-instrument comparability: All instruments use same scale regardless of volatility
            # 2. Adaptive normalization: Uses rolling statistics so adapts to changing market conditions
            # 3. Consistent visualization: Charts, thresholds, and alerts work uniformly across instruments
            # 4. Risk assessment: Easy to identify extreme deviations using standardized scale
            
            rolling_window = min(50, len(df) - 1)  # Use 50 periods or available data, whichever is smaller
            if rolling_window > 10:  # Need minimum data for meaningful statistics
                # Calculate rolling standard deviation (no need for mean since we're not centering)
                rolling_std = df['RTM_raw'].rolling(window=rolling_window, min_periods=10).std()
                
                # Handle edge cases for standard deviation
                rolling_std = rolling_std.fillna(1.0)  # Replace NaN with 1.0
                rolling_std = rolling_std.replace(0.0, 1.0)  # Replace zero std with 1.0 (flat prices)
                
                # Calculate modified Z-score WITHOUT centering to preserve sign relationship
                # This preserves the fundamental meaning: positive RTM = price above EMA
                modified_z_score = df['RTM_raw'] / rolling_std
                
                # Scale to -100 to +100 range (±3 standard deviations = ±100)
                # A value of 33.33 scales a 3-sigma event to ±100
                normalized_rtm = np.clip(modified_z_score * 33.33, -100, 100)
                
                # Handle any remaining non-finite values (NaN, inf, -inf)
                normalized_rtm = np.where(np.isfinite(normalized_rtm), normalized_rtm, 0.0)
                
                df['RTM'] = normalized_rtm.astype(int)
            else:
                # Fallback for insufficient data: use raw values capped at ±100
                logger.warning(f"Insufficient data for rolling normalization for {self.symbol}, using fallback")
                fallback_rtm = np.clip(df['RTM_raw'], -100, 100)
                # Handle non-finite values in fallback case too
                fallback_rtm = np.where(np.isfinite(fallback_rtm), fallback_rtm, 0.0)
                df['RTM'] = fallback_rtm.astype(int)
            
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

def calculate_rtm_values_for_symbol(symbol: str) -> dict:
    """Calculate last 6 RTM values for a symbol for both H1 and H4 timeframes"""
    try:
        signal_generator = DirectionChange(OANDA_API_KEY, symbol)
        
        # Initialize result structure
        result = {
            "rtm_h1_20": [],
            "rtm_h1_34": []
        }
        
        # Calculate H1 RTM values
        try:
            hourly_data_20 = signal_generator.fetch_historical_data("H1", 100)
            if not hourly_data_20.empty:
                # Calculate EMA for H1
                hourly_data_20['ema_short'] = signal_generator.calculate_ema(hourly_data_20['close_price'], 20)
                
                if not hourly_data_20['ema_short'].empty:
                    # Calculate gradient and RTM for H1 20 EMA
                    signal_generator.calculate_ema_gradient(hourly_data_20)
                    
                    if 'RTM' in hourly_data_20.columns and len(hourly_data_20) >= 6:
                        result["rtm_h1_20"] = hourly_data_20['RTM'].iloc[-6:].values.tolist()
                    else:
                        logger.warning(f"Insufficient H1 data for RTM analysis for {symbol}")
                        result["rtm_h1_20"] = [0] * 6
                else:
                    logger.warning(f"H1 EMA calculation failed for {symbol}")
                    result["rtm_h1_20"] = [0] * 6
            else:
                logger.warning(f"No H1 historical data available for {symbol}")
                result["rtm_h1_20"] = [0] * 6
        except Exception as h1_error:
            logger.error(f"Error calculating H1 RTM for {symbol}: {h1_error}")
            result["rtm_h1_20"] = [0] * 6
        
        # Calculate H4 RTM values
        try:
            hourly_data_34 = signal_generator.fetch_historical_data("H1", 100)
            if not hourly_data_34.empty:
                # Calculate EMA for H4
                hourly_data_34['ema_short'] = signal_generator.calculate_ema(hourly_data_34['close_price'], 34)
                
                if not hourly_data_34['ema_short'].empty:
                    # Calculate gradient and RTM for H4
                    signal_generator.calculate_ema_gradient(hourly_data_34)
                    
                    if 'RTM' in hourly_data_34.columns and len(hourly_data_34) >= 6:
                        result["rtm_h1_34"] = hourly_data_34['RTM'].iloc[-6:].values.tolist()
                    else:
                        logger.warning(f"Insufficient H4 data for RTM analysis for {symbol}")
                        result["rtm_h1_34"] = [0] * 6
                else:
                    logger.warning(f"H4 EMA calculation failed for {symbol}")
                    result["rtm_h1_34"] = [0] * 6
            else:
                logger.warning(f"No H4 historical data available for {symbol}")
                result["rtm_h1_34"] = [0] * 6
        except Exception as h4_error:
            logger.error(f"Error calculating H4 RTM for {symbol}: {h4_error}")
            result["rtm_h1_34"] = [0] * 6
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculating RTM for {symbol}: {e}")
        return {"rtm_h1_20": [0] * 6, "rtm_h1_34": [0] * 6}

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

def sort_instruments_by_bias_and_direction_change(rtm_data: List[Dict]) -> List[Dict]:
    """Sort instruments by bias first, then by direction change within each bias group"""
    # Load bias data
    bias_mapping = load_analysis_data()
    
    # Categorize instruments by bias
    up_bias = []
    down_bias = []
    hold_bias = []
    no_bias = []
    
    for item in rtm_data:
        instrument = item["instrument"]
        bias = bias_mapping.get(instrument)
        
        # Add bias information to the item
        item["bias"] = bias
        
        if bias == "Up":
            up_bias.append(item)
        elif bias == "Down":
            down_bias.append(item)
        elif bias == "Hold":
            hold_bias.append(item)
        else:
            no_bias.append(item)
    
    # Sort each bias group by direction change first, then by instrument name
    def sort_by_direction_change_and_name(items):
        direction_change_items = []
        normal_items = []
        
        for item in items:
            # Use H1 data for direction change detection (highlighting)
            h1_rtm_values = item.get("rtm_h1_20", [])
            if h1_rtm_values and detect_direction_change(h1_rtm_values):
                direction_change_items.append(item)
            else:
                normal_items.append(item)
        
        # Sort each group by instrument name
        direction_change_items.sort(key=lambda x: x["instrument"])
        normal_items.sort(key=lambda x: x["instrument"])
        
        return direction_change_items + normal_items
    
    # Sort each bias group
    sorted_up_bias = sort_by_direction_change_and_name(up_bias)
    sorted_down_bias = sort_by_direction_change_and_name(down_bias)
    sorted_hold_bias = sort_by_direction_change_and_name(hold_bias)
    sorted_no_bias = sort_by_direction_change_and_name(no_bias)
    
    # Return in order: Up bias, Down bias, Hold bias, No bias
    return sorted_up_bias + sorted_down_bias + sorted_hold_bias + sorted_no_bias

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

@app.get("/api/analysis")
async def get_analysis_data():
    """Get current bias analysis data"""
    try:
        bias_mapping = load_analysis_data()
        
        # Group by bias for frontend
        bias_groups = {
            "up": [],
            "down": [],
            "hold": []
        }
        
        for instrument, bias in bias_mapping.items():
            if bias == "Up":
                bias_groups["up"].append(instrument)
            elif bias == "Down":
                bias_groups["down"].append(instrument)
            elif bias == "Hold":
                bias_groups["hold"].append(instrument)
        
        return {
            "bias_mapping": bias_mapping,
            "bias_groups": bias_groups,
            "total_instruments": len(bias_mapping),
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching analysis data: {e}")
        return {
            "bias_mapping": {},
            "bias_groups": {"up": [], "down": [], "hold": []},
            "total_instruments": 0,
            "error": str(e)
        }

@app.get("/api/rtm/currencies")
async def get_currencies_rtm():
    """Get RTM data for all currency pairs"""
    symbols = load_symbols()
    currencies = symbols.get("currencies", [])
    
    rtm_data = []
    for symbol in currencies:
        if oanda_configured:
            # Real data from OANDA for both H1 and H4 timeframes
            rtm_result = calculate_rtm_values_for_symbol(symbol)
            rtm_data.append({
                "instrument": symbol,
                "rtm_h1_20": rtm_result.get("rtm_h1_20", [0] * 6),
                "rtm_h1_34": rtm_result.get("rtm_h1_34", [0] * 6),
                "last_updated": datetime.now().isoformat(),
                "error": None if (rtm_result.get("rtm_h1_20") and rtm_result.get("rtm_h1_34")) else "Failed to fetch data"
            })
    
    # Sort instruments by bias and direction changes (using H1 data)
    sorted_rtm_data = sort_instruments_by_bias_and_direction_change(rtm_data)
    
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
            # Real data from OANDA for both H1 and H4 timeframes
            rtm_result = calculate_rtm_values_for_symbol(symbol)
            rtm_data.append({
                "instrument": symbol,
                "rtm_h1_20": rtm_result.get("rtm_h1_20", [0] * 6),
                "rtm_h1_34": rtm_result.get("rtm_h1_34", [0] * 6),
                "last_updated": datetime.now().isoformat(),
                "error": None if (rtm_result.get("rtm_h1_20") and rtm_result.get("rtm_h1_34")) else "Failed to fetch data"
            })
    
    # Sort instruments by bias and direction changes (using H1 data)
    sorted_rtm_data = sort_instruments_by_bias_and_direction_change(rtm_data)
    
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
            # Real data from OANDA for both H1 and H4 timeframes
            rtm_result = calculate_rtm_values_for_symbol(symbol)
            rtm_data.append({
                "instrument": symbol,
                "rtm_h1_20": rtm_result.get("rtm_h1_20", [0] * 6),
                "rtm_h1_34": rtm_result.get("rtm_h1_34", [0] * 6),
                "last_updated": datetime.now().isoformat(),
                "error": None if (rtm_result.get("rtm_h1_20") and rtm_result.get("rtm_h1_34")) else "Failed to fetch data"
            })
    
    # Sort instruments by bias and direction changes (using H1 data)
    sorted_rtm_data = sort_instruments_by_bias_and_direction_change(rtm_data)
    
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
            
            # Get RTM values for this instrument (both H1 and H4)
            rtm_result = calculate_rtm_values_for_symbol(symbol)
            
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
                    "rtm_h1_20": rtm_result.get("rtm_h1_20", [0] * 6),
                    "rtm_h1_34": rtm_result.get("rtm_h1_34", [0] * 6),
                    "last_updated": datetime.now().isoformat(),
                    "error": None if (rtm_result.get("rtm_h1_20") and rtm_result.get("rtm_h1_34")) else "Failed to fetch RTM data"
                })
            
            # Handle short position  
            if short_units != 0:
                short_pnl = float(short_data.get('unrealizedPL', '0'))
                positions_data.append({
                    "instrument": symbol,
                    "direction": "Short", 
                    "units": abs(short_units),
                    "unrealized_pnl": short_pnl,
                    "rtm_h1_20": rtm_result.get("rtm_h1_20", [0] * 6),
                    "rtm_h1_34": rtm_result.get("rtm_h1_34", [0] * 6),
                    "last_updated": datetime.now().isoformat(),
                    "error": None if (rtm_result.get("rtm_h1_20") and rtm_result.get("rtm_h1_34")) else "Failed to fetch RTM data"
                })
            
            # If neither long nor short has units, log it
            if long_units == 0 and short_units == 0:
                logger.warning(f"No open units found for {symbol}")
            
        except Exception as e:
            logger.error(f"Error processing position for {position.get('instrument', 'unknown')}: {e}")
            continue
    
    # Sort positions by bias and direction changes
    sorted_positions = sort_instruments_by_bias_and_direction_change(positions_data)
    
    return {
        "category": "positions",
        "data": sorted_positions,
        "total_positions": len(positions_data)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
