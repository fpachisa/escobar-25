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
import anthropic
from google import genai

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silence noisy third-party loggers
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('google_genai').setLevel(logging.WARNING)

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

# AI Configuration
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini")  # claude or gemini
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
AI_MODEL = os.environ.get("AI_MODEL")  # Optional: specific model version

# Initialize AI clients
anthropic_client = None
gemini_client = None

if AI_PROVIDER == "claude" and ANTHROPIC_API_KEY:
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    logger.info("Claude AI client initialized")

if AI_PROVIDER == "gemini" and GOOGLE_API_KEY:
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    logger.info("Gemini AI client initialized")

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

def analyze_daily_market_condition(instrument: str, rtm_d1_20: List[int], rtm_d1_34: List[int]) -> dict:
    """
    Use AI to analyze daily market condition based on RTM values
    Returns: {"condition": "...", "reasoning": "...", "analyzed_at": "..."}
    """
    try:
        # Skip analysis if no AI provider is configured
        if not AI_PROVIDER or (AI_PROVIDER == "claude" and not ANTHROPIC_API_KEY) or (AI_PROVIDER == "gemini" and not GOOGLE_API_KEY):
            logger.warning(f"AI provider not configured, skipping analysis for {instrument}")
            return {
                "condition": "Analysis Unavailable",
                "reasoning": "AI provider not configured. Please set AI_PROVIDER and corresponding API key.",
                "analyzed_at": datetime.now().isoformat()
            }

        # Prepare the prompt
        prompt = f"""Analyze these daily RTM (Return-to-Mean) values for {instrument}:
- D1-20EMA (last 20 days): {rtm_d1_20}
- D1-34EMA (last 20 days): {rtm_d1_34}

RTM Scale: -100 to +100 (negative = price below EMA, positive = price above EMA)

Determine the current daily market condition by analyzing patterns, momentum, and trend:
1. "Trending Up" - consistent upward momentum, price staying above EMAs
2. "Trending Down" - consistent downward momentum, price staying below EMAs
3. "Ranging" - sideways movement, oscillating around EMAs with no clear direction
4. "Direction Change Imminent" - clear signs of reversal (crossing EMAs, divergence, momentum shift)

Provide:
1. Condition: exactly one of the four options above
2. Reasoning: brief 2-3 sentence explanation focusing on the pattern and key signals you observe

Respond ONLY with valid JSON in this format:
{{"condition": "one of the four conditions", "reasoning": "your brief analysis"}}"""

        # Call appropriate AI provider
        if AI_PROVIDER == "claude":
            model = AI_MODEL or "claude-3-5-sonnet-20241022"
            response = anthropic_client.messages.create(
                model=model,
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            ai_response = response.content[0].text

        elif AI_PROVIDER == "gemini":
            model_name = AI_MODEL or "gemini-2.5-flash"
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            ai_response = response.text

        else:
            raise ValueError(f"Unknown AI provider: {AI_PROVIDER}")

        # Parse JSON response
        # Remove markdown code blocks if present
        ai_response = ai_response.strip()
        if ai_response.startswith("```json"):
            ai_response = ai_response[7:]
        if ai_response.startswith("```"):
            ai_response = ai_response[3:]
        if ai_response.endswith("```"):
            ai_response = ai_response[:-3]
        ai_response = ai_response.strip()

        result = json.loads(ai_response)
        result["analyzed_at"] = datetime.now().isoformat()

        logger.info(f"AI analysis for {instrument}: {result['condition']}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response for {instrument}: {e}")
        return {
            "condition": "Analysis Error",
            "reasoning": "Failed to parse AI response. Please try again.",
            "analyzed_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error analyzing daily condition for {instrument}: {e}")
        return {
            "condition": "Analysis Error",
            "reasoning": f"Error during analysis: {str(e)}",
            "analyzed_at": datetime.now().isoformat()
        }

def calculate_rtm_values_for_symbol(symbol: str) -> dict:
    """Calculate RTM values for a symbol for H1 (6 candles) and D1 (20 candles) timeframes"""
    try:
        logger.info(f"Analyzing {symbol}...")
        signal_generator = DirectionChange(OANDA_API_KEY, symbol)

        # Initialize result structure
        result = {
            "rtm_h1_20": [],
            "rtm_h1_34": [],
            "rtm_d1_20": [],
            "rtm_d1_34": []
        }

        # Calculate H1-20EMA RTM values (last 6)
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
                        logger.warning(f"Insufficient H1-20 data for RTM analysis for {symbol}")
                        result["rtm_h1_20"] = [0] * 6
                else:
                    logger.warning(f"H1-20 EMA calculation failed for {symbol}")
                    result["rtm_h1_20"] = [0] * 6
            else:
                logger.warning(f"No H1-20 historical data available for {symbol}")
                result["rtm_h1_20"] = [0] * 6
        except Exception as h1_20_error:
            logger.error(f"Error calculating H1-20 RTM for {symbol}: {h1_20_error}")
            result["rtm_h1_20"] = [0] * 6

        # Calculate H1-34EMA RTM values (last 6)
        try:
            hourly_data_34 = signal_generator.fetch_historical_data("H1", 100)
            if not hourly_data_34.empty:
                # Calculate EMA for H1-34
                hourly_data_34['ema_short'] = signal_generator.calculate_ema(hourly_data_34['close_price'], 34)

                if not hourly_data_34['ema_short'].empty:
                    # Calculate gradient and RTM for H1-34
                    signal_generator.calculate_ema_gradient(hourly_data_34)

                    if 'RTM' in hourly_data_34.columns and len(hourly_data_34) >= 6:
                        result["rtm_h1_34"] = hourly_data_34['RTM'].iloc[-6:].values.tolist()
                    else:
                        logger.warning(f"Insufficient H1-34 data for RTM analysis for {symbol}")
                        result["rtm_h1_34"] = [0] * 6
                else:
                    logger.warning(f"H1-34 EMA calculation failed for {symbol}")
                    result["rtm_h1_34"] = [0] * 6
            else:
                logger.warning(f"No H1-34 historical data available for {symbol}")
                result["rtm_h1_34"] = [0] * 6
        except Exception as h1_34_error:
            logger.error(f"Error calculating H1-34 RTM for {symbol}: {h1_34_error}")
            result["rtm_h1_34"] = [0] * 6

        # Calculate D1-20EMA RTM values (last 20)
        try:
            daily_data_20 = signal_generator.fetch_historical_data("D", 120)
            if not daily_data_20.empty:
                # Calculate 20-period EMA for Daily
                daily_data_20['ema_short'] = signal_generator.calculate_ema(daily_data_20['close_price'], 20)

                if not daily_data_20['ema_short'].empty:
                    # Calculate gradient and RTM for D1-20
                    signal_generator.calculate_ema_gradient(daily_data_20)

                    if 'RTM' in daily_data_20.columns and len(daily_data_20) >= 20:
                        result["rtm_d1_20"] = daily_data_20['RTM'].iloc[-20:].values.tolist()
                    else:
                        logger.warning(f"Insufficient D1-20 data for RTM analysis for {symbol}")
                        result["rtm_d1_20"] = [0] * 20
                else:
                    logger.warning(f"D1-20 EMA calculation failed for {symbol}")
                    result["rtm_d1_20"] = [0] * 20
            else:
                logger.warning(f"No D1-20 historical data available for {symbol}")
                result["rtm_d1_20"] = [0] * 20
        except Exception as d1_20_error:
            logger.error(f"Error calculating D1-20 RTM for {symbol}: {d1_20_error}")
            result["rtm_d1_20"] = [0] * 20

        # Calculate D1-34EMA RTM values (last 20)
        try:
            daily_data_34 = signal_generator.fetch_historical_data("D", 120)
            if not daily_data_34.empty:
                # Calculate 34-period EMA for Daily
                daily_data_34['ema_short'] = signal_generator.calculate_ema(daily_data_34['close_price'], 34)

                if not daily_data_34['ema_short'].empty:
                    # Calculate gradient and RTM for D1-34
                    signal_generator.calculate_ema_gradient(daily_data_34)

                    if 'RTM' in daily_data_34.columns and len(daily_data_34) >= 20:
                        result["rtm_d1_34"] = daily_data_34['RTM'].iloc[-20:].values.tolist()
                    else:
                        logger.warning(f"Insufficient D1-34 data for RTM analysis for {symbol}")
                        result["rtm_d1_34"] = [0] * 20
                else:
                    logger.warning(f"D1-34 EMA calculation failed for {symbol}")
                    result["rtm_d1_34"] = [0] * 20
            else:
                logger.warning(f"No D1-34 historical data available for {symbol}")
                result["rtm_d1_34"] = [0] * 20
        except Exception as d1_34_error:
            logger.error(f"Error calculating D1-34 RTM for {symbol}: {d1_34_error}")
            result["rtm_d1_34"] = [0] * 20

        # Perform AI analysis on daily data
        daily_analysis = analyze_daily_market_condition(
            symbol,
            result["rtm_d1_20"],
            result["rtm_d1_34"]
        )
        result["daily_condition"] = daily_analysis.get("condition", "Analysis Unavailable")
        result["daily_reasoning"] = daily_analysis.get("reasoning", "No reasoning available")
        result["daily_analyzed_at"] = daily_analysis.get("analyzed_at", datetime.now().isoformat())

        logger.info(f"✓ Completed {symbol} - Condition: {result['daily_condition']}")
        return result

    except Exception as e:
        logger.error(f"Error calculating RTM for {symbol}: {e}")
        return {
            "rtm_h1_20": [0] * 6,
            "rtm_h1_34": [0] * 6,
            "rtm_d1_20": [0] * 20,
            "rtm_d1_34": [0] * 20,
            "daily_condition": "Analysis Error",
            "daily_reasoning": f"Error: {str(e)}",
            "daily_analyzed_at": datetime.now().isoformat()
        }

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
        return True

    # Pattern 1: First 4 predominantly negative, last 2 predominantly positive
    # Need at least 3 out of 4 negative AND at least 1 out of 2 positive
    if first_4_negative >= 3 and last_2_positive >= 1:
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
        return True

    # Pattern 2: First 3 predominantly negative, last 3 predominantly positive
    # Need at least 2 out of 3 negative AND at least 2 out of 3 positive
    if first_3_negative >= 2 and last_3_positive >= 2:
        return True
    
    return False

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
    logger.info(f"Fetching RTM data for {len(currencies)} currencies")

    rtm_data = []
    for symbol in currencies:
        if oanda_configured:
            # Real data from OANDA for H1 and D1 timeframes with AI analysis
            rtm_result = calculate_rtm_values_for_symbol(symbol)
            rtm_data.append({
                "instrument": symbol,
                "rtm_h1_20": rtm_result.get("rtm_h1_20", [0] * 6),
                "rtm_h1_34": rtm_result.get("rtm_h1_34", [0] * 6),
                "rtm_d1_20": rtm_result.get("rtm_d1_20", [0] * 20),
                "rtm_d1_34": rtm_result.get("rtm_d1_34", [0] * 20),
                "daily_condition": rtm_result.get("daily_condition", "Analysis Unavailable"),
                "daily_reasoning": rtm_result.get("daily_reasoning", "No reasoning available"),
                "daily_analyzed_at": rtm_result.get("daily_analyzed_at", datetime.now().isoformat()),
                "last_updated": datetime.now().isoformat(),
                "error": None if (rtm_result.get("rtm_h1_20") and rtm_result.get("rtm_h1_34") and rtm_result.get("rtm_d1_20") and rtm_result.get("rtm_d1_34")) else "Failed to fetch data"
            })

    # Sort instruments alphabetically
    rtm_data.sort(key=lambda x: x["instrument"])

    return {
        "category": "currencies",
        "data": rtm_data,
        "total_instruments": len(currencies)
    }

@app.get("/api/rtm/indices")
async def get_indices_rtm():
    """Get RTM data for all indices"""
    symbols = load_symbols()
    indices = symbols.get("indices", [])
    logger.info(f"Fetching RTM data for {len(indices)} indices")

    rtm_data = []
    for symbol in indices:
        if oanda_configured:
            # Real data from OANDA for H1 and D1 timeframes with AI analysis
            rtm_result = calculate_rtm_values_for_symbol(symbol)
            rtm_data.append({
                "instrument": symbol,
                "rtm_h1_20": rtm_result.get("rtm_h1_20", [0] * 6),
                "rtm_h1_34": rtm_result.get("rtm_h1_34", [0] * 6),
                "rtm_d1_20": rtm_result.get("rtm_d1_20", [0] * 20),
                "rtm_d1_34": rtm_result.get("rtm_d1_34", [0] * 20),
                "daily_condition": rtm_result.get("daily_condition", "Analysis Unavailable"),
                "daily_reasoning": rtm_result.get("daily_reasoning", "No reasoning available"),
                "daily_analyzed_at": rtm_result.get("daily_analyzed_at", datetime.now().isoformat()),
                "last_updated": datetime.now().isoformat(),
                "error": None if (rtm_result.get("rtm_h1_20") and rtm_result.get("rtm_h1_34") and rtm_result.get("rtm_d1_20") and rtm_result.get("rtm_d1_34")) else "Failed to fetch data"
            })

    # Sort instruments alphabetically
    rtm_data.sort(key=lambda x: x["instrument"])

    return {
        "category": "indices",
        "data": rtm_data,
        "total_instruments": len(indices)
    }

@app.get("/api/rtm/commodities")
async def get_commodities_rtm():
    """Get RTM data for all commodities"""
    symbols = load_symbols()
    commodities = symbols.get("commodities", [])
    logger.info(f"Fetching RTM data for {len(commodities)} commodities")

    rtm_data = []
    for symbol in commodities:
        if oanda_configured:
            # Real data from OANDA for H1 and D1 timeframes with AI analysis
            rtm_result = calculate_rtm_values_for_symbol(symbol)
            rtm_data.append({
                "instrument": symbol,
                "rtm_h1_20": rtm_result.get("rtm_h1_20", [0] * 6),
                "rtm_h1_34": rtm_result.get("rtm_h1_34", [0] * 6),
                "rtm_d1_20": rtm_result.get("rtm_d1_20", [0] * 20),
                "rtm_d1_34": rtm_result.get("rtm_d1_34", [0] * 20),
                "daily_condition": rtm_result.get("daily_condition", "Analysis Unavailable"),
                "daily_reasoning": rtm_result.get("daily_reasoning", "No reasoning available"),
                "daily_analyzed_at": rtm_result.get("daily_analyzed_at", datetime.now().isoformat()),
                "last_updated": datetime.now().isoformat(),
                "error": None if (rtm_result.get("rtm_h1_20") and rtm_result.get("rtm_h1_34") and rtm_result.get("rtm_d1_20") and rtm_result.get("rtm_d1_34")) else "Failed to fetch data"
            })

    # Sort instruments alphabetically
    rtm_data.sort(key=lambda x: x["instrument"])

    return {
        "category": "commodities",
        "data": rtm_data,
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

    logger.info("Fetching open positions...")
    open_positions = get_open_positions()
    
    if not open_positions:
        return {
            "category": "positions",
            "data": [],
            "total_positions": 0
        }
    
    positions_data = []

    for position in open_positions:
        try:
            symbol = position.get('instrument')
            
            if not symbol:
                logger.warning(f"No instrument found in position data")
                continue
            
            # Get RTM values for this instrument (H1 and D1 timeframes)
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
                    "rtm_d1_20": rtm_result.get("rtm_d1_20", [0] * 20),
                    "rtm_d1_34": rtm_result.get("rtm_d1_34", [0] * 20),
                    "daily_condition": rtm_result.get("daily_condition", "Analysis Unavailable"),
                    "daily_reasoning": rtm_result.get("daily_reasoning", "No reasoning available"),
                    "daily_analyzed_at": rtm_result.get("daily_analyzed_at", datetime.now().isoformat()),
                    "last_updated": datetime.now().isoformat(),
                    "error": None if (rtm_result.get("rtm_h1_20") and rtm_result.get("rtm_h1_34") and rtm_result.get("rtm_d1_20") and rtm_result.get("rtm_d1_34")) else "Failed to fetch RTM data"
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
                    "rtm_d1_20": rtm_result.get("rtm_d1_20", [0] * 20),
                    "rtm_d1_34": rtm_result.get("rtm_d1_34", [0] * 20),
                    "daily_condition": rtm_result.get("daily_condition", "Analysis Unavailable"),
                    "daily_reasoning": rtm_result.get("daily_reasoning", "No reasoning available"),
                    "daily_analyzed_at": rtm_result.get("daily_analyzed_at", datetime.now().isoformat()),
                    "last_updated": datetime.now().isoformat(),
                    "error": None if (rtm_result.get("rtm_h1_20") and rtm_result.get("rtm_h1_34") and rtm_result.get("rtm_d1_20") and rtm_result.get("rtm_d1_34")) else "Failed to fetch RTM data"
                })
            
            # If neither long nor short has units, log it
            if long_units == 0 and short_units == 0:
                logger.warning(f"No open units found for {symbol}")
            
        except Exception as e:
            logger.error(f"Error processing position for {position.get('instrument', 'unknown')}: {e}")
            continue

    # Sort positions alphabetically by instrument
    positions_data.sort(key=lambda x: x["instrument"])

    return {
        "category": "positions",
        "data": positions_data,
        "total_positions": len(positions_data)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
