from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import math
import requests
from cachetools import LRUCache, cached
import logging
import sys
from dotenv import load_dotenv
import os

# ----------------------------
# Logging Configuration
# ----------------------------
logger = logging.getLogger("tileproxy")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ----------------------------
# FastAPI App Setup
# ----------------------------
app = FastAPI()

# Add CORS middleware (allow all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    logger.info("Tile proxy server started.")

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}

# Load environment variables from .env file
load_dotenv()

# ----------------------------
# Constants (from environment)
# ----------------------------
GEOSERVER_URL = os.getenv("GEOSERVER_URL", "http://localhost:8080/geoserver/wms")
CACHE_SIZE = int(os.getenv("CACHE_SIZE", "10000"))
TILE_SIZE = int(os.getenv("TILE_SIZE", "256"))
DEBUG = os.getenv("DEBUG", "True").lower() in ("1", "true", "yes")

# ----------------------------
# Tile to BBOX Conversion
# ----------------------------
def tile_xyz_to_bbox(z, x, y):
    n = 2.0 ** z
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    def lonlat_to_webmerc(lon, lat):
        x = lon * 20037508.34 / 180
        y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
        y = y * 20037508.34 / 180
        return x, y
    minx, miny = lonlat_to_webmerc(lon_min, lat_min)
    maxx, maxy = lonlat_to_webmerc(lon_max, lat_max)
    return minx, miny, maxx, maxy

# ----------------------------
# WMS Tile Fetching
# ----------------------------
@cached(LRUCache(maxsize=CACHE_SIZE))
def get_wms_tile(layer, z, x, y):
    minx, miny, maxx, maxy = tile_xyz_to_bbox(z, x, y)
    bbox_width = maxx - minx
    bbox_height = maxy - miny

    logger.info(f"Zoom {z}, Tile {x},{y} => BBOX: {minx},{miny},{maxx},{maxy}")
    logger.info(f"BBOX size: {bbox_width} x {bbox_height} meters")

    if bbox_width <= 0 or bbox_height <= 0:
        logger.error("Invalid BBOX dimensions — skipping request.")
        raise HTTPException(status_code=400, detail="Invalid BBOX dimensions")

    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.0",
        "REQUEST": "GetMap",
        "LAYERS": layer,
        "STYLES": "",
        "FORMAT": "image/png",
        "TRANSPARENT": "TRUE",
        "SRS": "EPSG:3857",
        "BBOX": f"{minx},{miny},{maxx},{maxy}",
        "WIDTH": TILE_SIZE,
        "HEIGHT": TILE_SIZE
    }

    if DEBUG:
        logger.info(f"WMS Request Params: {params}")

    try:
        r = requests.get(GEOSERVER_URL, params=params, stream=True, verify=False, timeout=10)
    except Exception as e:
        logger.error(f"Exception during WMS request: {e}")
        raise HTTPException(status_code=500, detail=f"Exception during WMS request: {e}")

    if r.status_code != 200:
        logger.error(f"GeoServer returned {r.status_code}: {r.text}")
        raise HTTPException(status_code=r.status_code, detail=f"GeoServer error: {r.text}")

    return r

# ----------------------------
# Tile Endpoint
# ----------------------------
@app.get("/tiles/{layer}/{z}/{x}/{y}.png")
def serve_tile(layer: str, z: int, x: int, y: int):
    logger.info(f"Received tile request: /tiles/{layer}/{z}/{x}/{y}.png")

    if not (0 <= z <= 22):
        raise HTTPException(status_code=400, detail=f"Zoom level {z} is out of range (0–22).")

    response = get_wms_tile(layer, z, x, y)
    return StreamingResponse(response.raw, media_type="image/png", background=lambda: response.close())
